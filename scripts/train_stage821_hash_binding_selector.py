#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import re
from typing import Any

import torch
import torch.nn.functional as F


TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9_]*\b|\b\d+\b")
KV_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]*?)=([^\s;]+)")
TARGET_OPS = {
    "atomic_fact",
    "relation",
    "composition",
    "counterfactual_false_claim",
    "exception",
}
STOP_TOKENS = {
    "answer",
    "collision_key",
    "direct_answer",
    "query",
    "statement",
    "structured",
    "selector_dropout",
    "has",
    "true",
    "false",
}
TOKEN_TYPES = ("general", "entity", "slot", "claim", "pair")


def _load_retrieval_eval(repo_root: Path):
    path = repo_root / "legacy_src" / "scripts" / "evaluate_agentkernel_lite_retrieval_embeddings.py"
    spec = importlib.util.spec_from_file_location("evaluate_agentkernel_lite_retrieval_embeddings", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load retrieval evaluator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _direct_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("task_type") == "active_agent_direct_answer"
        and str(row.get("operation", "") or "") in TARGET_OPS
        and str(row.get("retrieval_query_text", "") or "").strip()
        and str(row.get("retrieval_doc_text", "") or "").strip()
    ]


def _parse_operation_loss_weights(value: str) -> dict[str, float]:
    weights: dict[str, float] = {}
    for item in str(value or "").split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(f"operation loss weight must be OP:WEIGHT, got {item!r}")
        operation, weight = item.split(":", 1)
        weights[operation.strip()] = float(weight)
    return weights


def _collision_key(row: dict[str, Any]) -> str:
    value = str(row.get("collision_key_value", "") or "").strip()
    if value:
        return value
    name = str(row.get("collision_key_name", "") or "").strip()
    if name and str(row.get(name, "") or "").strip():
        return str(row.get(name, "") or "").strip()
    return str(row.get("operation", "") or "global")


def _kv(text: str) -> dict[str, str]:
    return {str(key): str(value) for key, value in KV_RE.findall(str(text or ""))}


def _tokens(text: str) -> list[str]:
    values = _kv(text)
    answer_value = str(values.get("answer", "") or "").lower()
    tokens = []
    for token in TOKEN_RE.findall(str(text or "")):
        lowered = token.lower()
        if lowered in STOP_TOKENS or lowered.startswith("ak_op_") or lowered == answer_value:
            continue
        tokens.append(lowered)
    return tokens


def _token_type(token: str) -> str:
    lowered = str(token).lower()
    if lowered.startswith("qent_") or lowered.startswith("dent_"):
        return "entity"
    if lowered.startswith("qslot_") or lowered.startswith("dslot_"):
        return "slot"
    if lowered.startswith("qclaim_") or lowered.startswith("dclaim_"):
        return "claim"
    if lowered.startswith("qpair_") or lowered.startswith("dpair_"):
        return "pair"
    return "general"


def _hash_token(token: str, buckets: int, *, namespace: str) -> int:
    digest = hashlib.blake2b(f"{namespace}|{token}".encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "little") % int(buckets)


def _bag(tokens: list[str], buckets: int, *, namespace: str, typed_token_bags: bool = False) -> torch.Tensor:
    if typed_token_bags:
        type_to_index = {token_type: index for index, token_type in enumerate(TOKEN_TYPES)}
        vector = torch.zeros(int(buckets) * len(TOKEN_TYPES), dtype=torch.float32)
        for token in tokens:
            token_type = _token_type(token)
            offset = type_to_index[token_type] * int(buckets)
            vector[offset + _hash_token(token, int(buckets), namespace=f"{namespace}:{token_type}")] += 1.0
        total = vector.sum().clamp_min(1.0)
        return vector / total
    vector = torch.zeros(int(buckets), dtype=torch.float32)
    for token in tokens:
        vector[_hash_token(token, int(buckets), namespace=namespace)] += 1.0
    total = vector.sum().clamp_min(1.0)
    return vector / total


def _typed_bridge_index(alias: str, buckets: int, *, namespace: str, typed_token_bags: bool) -> int:
    token = str(alias).lower()
    if not typed_token_bags:
        return _hash_token(token, int(buckets), namespace=namespace)
    type_to_index = {token_type: index for index, token_type in enumerate(TOKEN_TYPES)}
    token_type = _token_type(token)
    return type_to_index[token_type] * int(buckets) + _hash_token(token, int(buckets), namespace=f"{namespace}:{token_type}")


def _bridge_pairs(rows: list[dict[str, Any]], buckets: int, *, typed_token_bags: bool = False) -> list[tuple[int, int]]:
    pairs: set[tuple[int, int]] = set()
    for row in rows:
        binding = row.get("stage819_hardened_binding") or {}
        if not isinstance(binding, dict):
            continue
        query_aliases = binding.get("query_aliases") or {}
        doc_aliases = binding.get("doc_aliases") or {}
        if not isinstance(query_aliases, dict) or not isinstance(doc_aliases, dict):
            continue
        for original, query_alias in query_aliases.items():
            doc_alias = doc_aliases.get(original)
            if not doc_alias:
                continue
            pairs.add(
                (
                    _typed_bridge_index(str(query_alias).lower(), int(buckets), namespace="query", typed_token_bags=typed_token_bags),
                    _typed_bridge_index(str(doc_alias).lower(), int(buckets), namespace="doc", typed_token_bags=typed_token_bags),
                )
            )
        query_pair_suffixes = {
            token.removeprefix("qpair_")
            for token in _tokens(str(row.get("retrieval_query_text", "") or row.get("encoder_text", "") or ""))
            if token.startswith("qpair_")
        }
        doc_pair_suffixes = {
            token.removeprefix("dpair_")
            for token in _tokens(str(row.get("retrieval_doc_text", "") or ""))
            if token.startswith("dpair_")
        }
        for suffix in sorted(query_pair_suffixes & doc_pair_suffixes):
            pairs.add(
                (
                    _typed_bridge_index(f"qpair_{suffix}", int(buckets), namespace="query", typed_token_bags=typed_token_bags),
                    _typed_bridge_index(f"dpair_{suffix}", int(buckets), namespace="doc", typed_token_bags=typed_token_bags),
                )
            )
    return sorted(pairs)


def _unique_docs(rows: list[dict[str, Any]]) -> tuple[list[str], dict[str, int], dict[str, list[int]]]:
    docs: list[str] = []
    doc_to_index: dict[str, int] = {}
    groups: dict[str, list[int]] = {}
    for row in rows:
        doc = str(row.get("retrieval_doc_text", "") or "").strip()
        if not doc:
            continue
        index = doc_to_index.get(doc)
        if index is None:
            index = len(docs)
            doc_to_index[doc] = index
            docs.append(doc)
        key = _collision_key(row)
        groups.setdefault(key, [])
        if index not in groups[key]:
            groups[key].append(index)
    return docs, doc_to_index, groups


def _doc_matches_expected(expected: str, doc: str) -> bool:
    return bool(expected and expected in doc)


class HashBindingSelector(torch.nn.Module):
    def __init__(
        self,
        buckets: int,
        hash_dim: int,
        operations: list[str],
        hidden_dim: int,
        operation_specific_scorers: bool = False,
        operation_adapter_rank: int = 0,
    ) -> None:
        super().__init__()
        self.query_embed = torch.nn.Linear(int(buckets), int(hash_dim), bias=False)
        self.doc_embed = torch.nn.Linear(int(buckets), int(hash_dim), bias=False)
        self.operation_to_index = {operation: index for index, operation in enumerate(operations)}
        self.operation_specific_scorers = bool(operation_specific_scorers)
        feature_dim = int(hash_dim) * 4 + 1 + len(operations)
        self.operation_adapter_rank = int(operation_adapter_rank)
        if self.operation_adapter_rank > 0:
            self.operation_adapters = torch.nn.ModuleDict(
                {
                    operation: torch.nn.Sequential(
                        torch.nn.Linear(feature_dim, self.operation_adapter_rank, bias=False),
                        torch.nn.GELU(),
                        torch.nn.Linear(self.operation_adapter_rank, feature_dim, bias=False),
                    )
                    for operation in operations
                }
            )
        def make_scorer() -> torch.nn.Sequential:
            return torch.nn.Sequential(
                torch.nn.Linear(feature_dim, int(hidden_dim)),
                torch.nn.GELU(),
                torch.nn.Linear(int(hidden_dim), 1),
            )
        if self.operation_specific_scorers:
            self.scorers = torch.nn.ModuleDict({operation: make_scorer() for operation in operations})
        else:
            self.scorer = make_scorer()
        for module in self.modules():
            if isinstance(module, torch.nn.Linear):
                torch.nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    torch.nn.init.zeros_(module.bias)

    def forward(self, query_bag: torch.Tensor, doc_bags: torch.Tensor, operation: str) -> torch.Tensor:
        query_vec = self.query_embed(query_bag)
        doc_vecs = self.doc_embed(doc_bags)
        query_expanded = query_vec.unsqueeze(0).expand_as(doc_vecs)
        dot = (query_expanded * doc_vecs).sum(dim=-1, keepdim=True)
        op = torch.zeros((doc_bags.shape[0], len(self.operation_to_index)), dtype=doc_bags.dtype, device=doc_bags.device)
        op[:, self.operation_to_index[str(operation)]] = 1.0
        features = torch.cat([query_expanded, doc_vecs, query_expanded * doc_vecs, (query_expanded - doc_vecs).abs(), dot, op], dim=-1)
        if self.operation_adapter_rank > 0:
            features = features + self.operation_adapters[str(operation)](features)
        if self.operation_specific_scorers:
            return self.scorers[str(operation)](features).squeeze(-1)
        return self.scorer(features).squeeze(-1)

    def bridge_loss(self, pairs: list[tuple[int, int]], device: torch.device, max_pairs: int = 512) -> torch.Tensor:
        if not pairs:
            return torch.tensor(0.0, device=device)
        selected = pairs
        if len(selected) > int(max_pairs):
            selected = random.sample(selected, int(max_pairs))
        query_indices = torch.tensor([pair[0] for pair in selected], dtype=torch.long, device=device)
        doc_indices = torch.tensor([pair[1] for pair in selected], dtype=torch.long, device=device)
        query_columns = F.normalize(self.query_embed.weight.t().index_select(0, query_indices), dim=-1)
        doc_columns = F.normalize(self.doc_embed.weight.t().index_select(0, doc_indices), dim=-1)
        logits = query_columns @ doc_columns.t()
        labels = torch.arange(len(selected), dtype=torch.long, device=device)
        return 0.5 * (F.cross_entropy(logits, labels) + F.cross_entropy(logits.t(), labels))


class FusionGate(torch.nn.Module):
    def __init__(self, feature_dim: int, hidden_dim: int) -> None:
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(int(feature_dim), int(hidden_dim)),
            torch.nn.GELU(),
            torch.nn.Linear(int(hidden_dim), 1),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.net(features).squeeze(-1)


def _make_matrices(
    rows: list[dict[str, Any]],
    docs: list[str],
    buckets: int,
    *,
    typed_token_bags: bool = False,
) -> tuple[torch.Tensor, torch.Tensor]:
    query_bags = torch.stack(
        [
            _bag(
                _tokens(str(row.get("retrieval_query_text", "") or row.get("encoder_text", ""))),
                buckets,
                namespace="query",
                typed_token_bags=typed_token_bags,
            )
            for row in rows
        ],
        dim=0,
    )
    doc_bags = torch.stack([_bag(_tokens(doc), buckets, namespace="doc", typed_token_bags=typed_token_bags) for doc in docs], dim=0)
    return query_bags, doc_bags


def _evaluate(
    model: HashBindingSelector,
    rows: list[dict[str, Any]],
    docs: list[str],
    doc_to_index: dict[str, int],
    groups: dict[str, list[int]],
    query_bags: torch.Tensor,
    doc_bags: torch.Tensor,
    device: torch.device,
) -> dict[str, Any]:
    model.eval()
    answer = 0
    exact = 0
    reciprocal = 0.0
    by_operation: dict[str, dict[str, int]] = {}
    with torch.no_grad():
        for row_index, row in enumerate(rows):
            operation = str(row.get("operation", "") or "unknown")
            stats = by_operation.setdefault(operation, {"examples": 0, "answer_correct": 0, "exact_correct": 0})
            stats["examples"] += 1
            group = groups[_collision_key(row)]
            label = group.index(doc_to_index[str(row.get("retrieval_doc_text", "") or "").strip()])
            scores = model(query_bags[row_index].to(device), doc_bags[group].to(device), operation).detach().cpu()
            order = torch.argsort(scores, descending=True).tolist()
            pred = int(order[0])
            rank = int(order.index(label)) + 1
            reciprocal += 1.0 / float(rank)
            predicted_doc = docs[group[pred]]
            expected = str(row.get("expected_content", "") or "")
            if pred == label:
                exact += 1
                stats["exact_correct"] += 1
            if pred == label or _doc_matches_expected(expected, predicted_doc):
                answer += 1
                stats["answer_correct"] += 1
    total = len(rows)
    return {
        "examples": total,
        "answer_correct": int(answer),
        "exact_correct": int(exact),
        "mrr": reciprocal / float(total or 1),
        "by_operation": by_operation,
    }


def _embed_frozen_queries(
    retrieval_eval,
    model,
    tokenizer,
    rows: list[dict[str, Any]],
    *,
    max_tokens: int,
    batch_size: int,
    device: torch.device,
) -> torch.Tensor:
    chunks: list[torch.Tensor] = []
    with torch.no_grad():
        for offset in range(0, len(rows), int(batch_size)):
            texts = [
                str(row.get("retrieval_query_text", "") or row.get("encoder_text", "") or "")
                for row in rows[offset : offset + int(batch_size)]
            ]
            chunks.append(
                retrieval_eval._embed_query(model, tokenizer, texts, max_tokens=int(max_tokens), device=device)
                .detach()
                .float()
                .cpu()
            )
    return torch.cat(chunks, dim=0)


def _embed_frozen_docs(
    retrieval_eval,
    model,
    tokenizer,
    docs: list[str],
    *,
    max_tokens: int,
    batch_size: int,
    device: torch.device,
) -> torch.Tensor:
    chunks: list[torch.Tensor] = []
    with torch.no_grad():
        for offset in range(0, len(docs), int(batch_size)):
            chunks.append(
                retrieval_eval._embed_doc(
                    model,
                    tokenizer,
                    docs[offset : offset + int(batch_size)],
                    max_tokens=int(max_tokens),
                    device=device,
                )
                .detach()
                .float()
                .cpu()
            )
    return torch.cat(chunks, dim=0)


def _normalize(scores: torch.Tensor) -> torch.Tensor:
    return (scores - scores.mean()) / scores.std(unbiased=False).clamp_min(1e-6)


def _evaluate_fusion(
    model: HashBindingSelector,
    rows: list[dict[str, Any]],
    docs: list[str],
    doc_to_index: dict[str, int],
    groups: dict[str, list[int]],
    query_bags: torch.Tensor,
    doc_bags: torch.Tensor,
    frozen_queries: torch.Tensor,
    frozen_docs: torch.Tensor,
    device: torch.device,
    alphas: list[float],
) -> dict[str, Any]:
    model.eval()
    results: dict[str, dict[str, Any]] = {
        str(alpha): {"answer_correct": 0, "exact_correct": 0, "mrr": 0.0, "by_operation": {}} for alpha in alphas
    }
    with torch.no_grad():
        for row_index, row in enumerate(rows):
            group = groups[_collision_key(row)]
            label = group.index(doc_to_index[str(row.get("retrieval_doc_text", "") or "").strip()])
            selector_scores = model(
                query_bags[row_index].to(device),
                doc_bags[group].to(device),
                str(row.get("operation", "") or "unknown"),
            ).detach().cpu()
            base_scores = (frozen_queries[row_index].unsqueeze(0) * frozen_docs[group]).sum(dim=-1).detach().cpu()
            expected = str(row.get("expected_content", "") or "")
            for alpha in alphas:
                operation = str(row.get("operation", "") or "unknown")
                fused = _normalize(selector_scores) + float(alpha) * _normalize(base_scores)
                order = torch.argsort(fused, descending=True).tolist()
                pred = int(order[0])
                rank = int(order.index(label)) + 1
                bucket = results[str(alpha)]
                op_stats = bucket["by_operation"].setdefault(
                    operation,
                    {"examples": 0, "answer_correct": 0, "exact_correct": 0, "mrr": 0.0},
                )
                op_stats["examples"] += 1
                bucket["mrr"] += 1.0 / float(rank)
                op_stats["mrr"] += 1.0 / float(rank)
                predicted_doc = docs[group[pred]]
                if pred == label:
                    bucket["exact_correct"] += 1
                    op_stats["exact_correct"] += 1
                if pred == label or _doc_matches_expected(expected, predicted_doc):
                    bucket["answer_correct"] += 1
                    op_stats["answer_correct"] += 1
    total = len(rows)
    for bucket in results.values():
        bucket["mrr"] /= float(total or 1)
        for op_stats in bucket.get("by_operation", {}).values():
            op_stats["mrr"] /= float(op_stats.get("examples", 0) or 1)
    best_answer_alpha = max(results, key=lambda key: (results[key]["answer_correct"], results[key]["exact_correct"]))
    best_exact_alpha = max(results, key=lambda key: (results[key]["exact_correct"], results[key]["answer_correct"]))
    return {
        "alphas": results,
        "best_answer_alpha": best_answer_alpha,
        "best_answer": results[best_answer_alpha],
        "best_exact_alpha": best_exact_alpha,
        "best_exact": results[best_exact_alpha],
    }


def _select_operation_alphas(fusion_eval: dict[str, Any], operations: list[str]) -> dict[str, str]:
    selected: dict[str, str] = {}
    for operation in operations:
        best_alpha = max(
            fusion_eval["alphas"],
            key=lambda alpha: (
                fusion_eval["alphas"][alpha].get("by_operation", {})
                .get(operation, {"answer_correct": 0, "exact_correct": 0, "mrr": 0.0})
                .get("answer_correct", 0),
                fusion_eval["alphas"][alpha].get("by_operation", {})
                .get(operation, {"answer_correct": 0, "exact_correct": 0, "mrr": 0.0})
                .get("exact_correct", 0),
                fusion_eval["alphas"][alpha].get("by_operation", {})
                .get(operation, {"answer_correct": 0, "exact_correct": 0, "mrr": 0.0})
                .get("mrr", 0.0),
            ),
        )
        selected[operation] = str(best_alpha)
    return selected


def _evaluate_fusion_operation_alphas(fusion_eval: dict[str, Any], operation_alphas: dict[str, str]) -> dict[str, Any]:
    answer = 0
    exact = 0
    mrr = 0.0
    by_operation: dict[str, dict[str, int]] = {}
    for operation, alpha in sorted(operation_alphas.items()):
        alpha_bucket = fusion_eval["alphas"].get(str(alpha))
        if not alpha_bucket:
            continue
        op_stats = alpha_bucket.get("by_operation", {}).get(operation)
        if not op_stats:
            continue
        copied = {
            "examples": int(op_stats.get("examples", 0)),
            "answer_correct": int(op_stats.get("answer_correct", 0)),
            "exact_correct": int(op_stats.get("exact_correct", 0)),
            "mrr": float(op_stats.get("mrr", 0.0)),
            "selected_alpha": str(alpha),
        }
        by_operation[operation] = copied
        answer += copied["answer_correct"]
        exact += copied["exact_correct"]
        mrr += copied["mrr"] * float(copied["examples"])
    examples = sum(stats["examples"] for stats in by_operation.values())
    return {
        "operation_alphas": {operation: str(alpha) for operation, alpha in sorted(operation_alphas.items())},
        "examples": examples,
        "answer_correct": int(answer),
        "exact_correct": int(exact),
        "mrr": mrr / float(examples or 1),
        "by_operation": by_operation,
    }


def _margin(scores: torch.Tensor) -> torch.Tensor:
    if scores.numel() < 2:
        return torch.tensor(0.0, dtype=scores.dtype, device=scores.device)
    top2 = torch.topk(scores, k=2).values
    return top2[0] - top2[1]


def _fusion_gate_features(
    selector_scores: torch.Tensor,
    base_scores: torch.Tensor,
    operation: str,
    operation_to_index: dict[str, int],
) -> torch.Tensor:
    selector = _normalize(selector_scores.float())
    base = _normalize(base_scores.float())
    selector_margin = _margin(selector).expand_as(selector)
    base_margin = _margin(base).expand_as(base)
    op = torch.zeros((selector.shape[0], len(operation_to_index)), dtype=selector.dtype)
    op[:, operation_to_index[str(operation)]] = 1.0
    return torch.cat(
        [
            selector.unsqueeze(-1),
            base.unsqueeze(-1),
            (selector * base).unsqueeze(-1),
            (selector - base).abs().unsqueeze(-1),
            selector_margin.unsqueeze(-1),
            base_margin.unsqueeze(-1),
            op,
        ],
        dim=-1,
    )


def _iter_fusion_gate_examples(
    model: HashBindingSelector,
    rows: list[dict[str, Any]],
    docs: list[str],
    doc_to_index: dict[str, int],
    groups: dict[str, list[int]],
    query_bags: torch.Tensor,
    doc_bags: torch.Tensor,
    frozen_queries: torch.Tensor,
    frozen_docs: torch.Tensor,
    device: torch.device,
    operation_to_index: dict[str, int],
) -> list[tuple[torch.Tensor, int, dict[str, Any], list[int]]]:
    model.eval()
    examples: list[tuple[torch.Tensor, int, dict[str, Any], list[int]]] = []
    with torch.no_grad():
        for row_index, row in enumerate(rows):
            operation = str(row.get("operation", "") or "unknown")
            group = groups[_collision_key(row)]
            label = group.index(doc_to_index[str(row.get("retrieval_doc_text", "") or "").strip()])
            selector_scores = model(
                query_bags[row_index].to(device),
                doc_bags[group].to(device),
                operation,
            ).detach().cpu()
            base_scores = (frozen_queries[row_index].unsqueeze(0) * frozen_docs[group]).sum(dim=-1).detach().cpu()
            features = _fusion_gate_features(selector_scores, base_scores, operation, operation_to_index)
            examples.append((features, int(label), row, list(group)))
    return examples


def _evaluate_fusion_gate(gate: FusionGate, examples: list[tuple[torch.Tensor, int, dict[str, Any], list[int]]], docs: list[str]) -> dict[str, Any]:
    gate.eval()
    answer = 0
    exact = 0
    reciprocal = 0.0
    by_operation: dict[str, dict[str, Any]] = {}
    with torch.no_grad():
        for features, label, row, group in examples:
            operation = str(row.get("operation", "") or "unknown")
            scores = gate(features)
            order = torch.argsort(scores, descending=True).tolist()
            pred = int(order[0])
            rank = int(order.index(label)) + 1
            predicted_doc = docs[group[pred]]
            expected = str(row.get("expected_content", "") or "")
            stats = by_operation.setdefault(operation, {"examples": 0, "answer_correct": 0, "exact_correct": 0, "mrr": 0.0})
            stats["examples"] += 1
            reciprocal += 1.0 / float(rank)
            stats["mrr"] += 1.0 / float(rank)
            if pred == label:
                exact += 1
                stats["exact_correct"] += 1
            if pred == label or _doc_matches_expected(expected, predicted_doc):
                answer += 1
                stats["answer_correct"] += 1
    total = len(examples)
    for stats in by_operation.values():
        stats["mrr"] /= float(stats.get("examples", 0) or 1)
    return {
        "examples": total,
        "answer_correct": int(answer),
        "exact_correct": int(exact),
        "mrr": reciprocal / float(total or 1),
        "by_operation": by_operation,
    }


def _train_fusion_gate(
    calibration_examples: list[tuple[torch.Tensor, int, dict[str, Any], list[int]]],
    eval_examples: list[tuple[torch.Tensor, int, dict[str, Any], list[int]]],
    calibration_docs: list[str],
    eval_docs: list[str],
    *,
    feature_dim: int,
    hidden_dim: int,
    epochs: int,
    learning_rate: float,
    weight_decay: float,
    seed: int,
) -> dict[str, Any]:
    torch.manual_seed(int(seed) + 847)
    gate = FusionGate(int(feature_dim), int(hidden_dim))
    optimizer = torch.optim.AdamW(gate.parameters(), lr=float(learning_rate), weight_decay=float(weight_decay))
    history: list[dict[str, Any]] = []
    order = list(range(len(calibration_examples)))
    for epoch in range(1, int(epochs) + 1):
        random.shuffle(order)
        total_loss = 0.0
        gate.train()
        for index in order:
            features, label, _row, _group = calibration_examples[index]
            scores = gate(features)
            loss = F.cross_entropy(scores.unsqueeze(0), torch.tensor([label], dtype=torch.long))
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach().item())
        if epoch == 1 or epoch == int(epochs) or epoch % max(int(epochs) // 5, 1) == 0:
            history.append(
                {
                    "epoch": epoch,
                    "mean_loss": total_loss / float(len(order) or 1),
                    "calibration_answer_correct": _evaluate_fusion_gate(gate, calibration_examples, calibration_docs)["answer_correct"],
                }
            )
    return {
        "feature_dim": int(feature_dim),
        "hidden_dim": int(hidden_dim),
        "epochs": int(epochs),
        "learning_rate": float(learning_rate),
        "weight_decay": float(weight_decay),
        "parameter_count": sum(parameter.numel() for parameter in gate.parameters()),
        "history": history,
        "calibration": _evaluate_fusion_gate(gate, calibration_examples, calibration_docs),
        "eval": _evaluate_fusion_gate(gate, eval_examples, eval_docs),
    }


def train(args: argparse.Namespace) -> dict[str, Any]:
    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    device = torch.device(str(args.device))
    operation_loss_weights = _parse_operation_loss_weights(str(args.operation_loss_weights))
    manifest = json.loads(Path(args.dataset_manifest).read_text(encoding="utf-8"))
    train_rows = _direct_rows(_iter_jsonl(Path(manifest["train_dataset_path"])))
    eval_rows = _direct_rows(_iter_jsonl(Path(manifest["eval_dataset_path"])))
    external_calibration_path = str(args.calibration_dataset_path or manifest.get("calibration_dataset_path", "") or "").strip()
    external_calibration_rows: list[dict[str, Any]] = []
    if external_calibration_path:
        external_calibration_rows = _direct_rows(_iter_jsonl(Path(external_calibration_path)))
    if int(args.max_train_examples) > 0:
        train_rows = train_rows[: int(args.max_train_examples)]
    if int(args.max_eval_examples) > 0:
        eval_rows = eval_rows[: int(args.max_eval_examples)]
    calibration_rows: list[dict[str, Any]] = []
    if external_calibration_rows:
        calibration_rows = external_calibration_rows
    calibration_examples = 0 if calibration_rows else int(args.calibration_examples)
    if not calibration_rows and calibration_examples <= 0 and float(args.calibration_fraction) > 0.0:
        calibration_examples = int(round(len(train_rows) * float(args.calibration_fraction)))
    if not calibration_rows and calibration_examples > 0:
        calibration_examples = min(max(calibration_examples, 1), max(len(train_rows) - 1, 1))
        if bool(args.calibration_stratified):
            rng = random.Random(int(args.seed) + 828)
            by_operation: dict[str, list[dict[str, Any]]] = {}
            for row in train_rows:
                by_operation.setdefault(str(row.get("operation", "") or "unknown"), []).append(row)
            selected_ids: set[int] = set()
            for rows_for_operation in by_operation.values():
                take = int(round(len(rows_for_operation) * (calibration_examples / float(len(train_rows)))))
                take = min(max(take, 1), max(len(rows_for_operation) - 1, 1))
                shuffled = list(rows_for_operation)
                rng.shuffle(shuffled)
                selected_ids.update(id(row) for row in shuffled[:take])
            calibration_rows = [row for row in train_rows if id(row) in selected_ids]
            train_rows = [row for row in train_rows if id(row) not in selected_ids]
        else:
            calibration_rows = train_rows[-calibration_examples:]
            train_rows = train_rows[:-calibration_examples]
    train_docs, train_doc_to_index, train_groups = _unique_docs(train_rows)
    eval_docs, eval_doc_to_index, eval_groups = _unique_docs(eval_rows)
    calibration_docs: list[str] = []
    calibration_doc_to_index: dict[str, int] = {}
    calibration_groups: dict[str, list[int]] = {}
    if calibration_rows:
        calibration_docs, calibration_doc_to_index, calibration_groups = _unique_docs(calibration_rows)
    typed_token_bags = bool(args.typed_token_bags)
    input_buckets = int(args.hash_buckets) * (len(TOKEN_TYPES) if typed_token_bags else 1)
    train_q, train_d = _make_matrices(train_rows, train_docs, int(args.hash_buckets), typed_token_bags=typed_token_bags)
    eval_q, eval_d = _make_matrices(eval_rows, eval_docs, int(args.hash_buckets), typed_token_bags=typed_token_bags)
    calibration_q = torch.empty((0, input_buckets), dtype=torch.float32)
    calibration_d = torch.empty((0, input_buckets), dtype=torch.float32)
    if calibration_rows:
        calibration_q, calibration_d = _make_matrices(
            calibration_rows,
            calibration_docs,
            int(args.hash_buckets),
            typed_token_bags=typed_token_bags,
        )
    train_bridge_pairs = _bridge_pairs(train_rows, int(args.hash_buckets), typed_token_bags=typed_token_bags)
    eval_bridge_pairs = _bridge_pairs(eval_rows, int(args.hash_buckets), typed_token_bags=typed_token_bags)
    operations = sorted({str(row.get("operation", "") or "unknown") for row in [*train_rows, *eval_rows]})
    model = HashBindingSelector(
        input_buckets,
        int(args.hash_dim),
        operations,
        int(args.hidden_dim),
        operation_specific_scorers=bool(args.operation_specific_scorers),
        operation_adapter_rank=int(args.operation_adapter_rank),
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(args.learning_rate), weight_decay=float(args.weight_decay))
    order = list(range(len(train_rows)))
    history: list[dict[str, float | int]] = []
    for step in range(1, int(args.steps) + 1):
        random.shuffle(order)
        losses: list[torch.Tensor] = []
        model.train()
        for row_index in order[: int(args.rows_per_step)]:
            row = train_rows[row_index]
            group = list(train_groups[_collision_key(row)])
            if int(args.max_candidates_per_group) > 0 and len(group) > int(args.max_candidates_per_group):
                positive = train_doc_to_index[str(row.get("retrieval_doc_text", "") or "").strip()]
                negatives = [index for index in group if index != positive]
                random.shuffle(negatives)
                group = [positive, *negatives[: int(args.max_candidates_per_group) - 1]]
                random.shuffle(group)
            label = group.index(train_doc_to_index[str(row.get("retrieval_doc_text", "") or "").strip()])
            scores = model(train_q[row_index].to(device), train_d[group].to(device), str(row.get("operation", "") or "unknown"))
            row_loss = F.cross_entropy(scores.unsqueeze(0), torch.tensor([label], dtype=torch.long, device=device))
            row_loss = row_loss * float(operation_loss_weights.get(str(row.get("operation", "") or "unknown"), 1.0))
            losses.append(row_loss)
        loss = torch.stack(losses).mean()
        if float(args.bridge_loss_weight) > 0.0:
            loss = loss + float(args.bridge_loss_weight) * model.bridge_loss(
                train_bridge_pairs,
                device,
                max_pairs=int(args.bridge_max_pairs),
            )
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % int(args.log_every) == 0:
            train_eval = _evaluate(model, train_rows[: min(len(train_rows), 640)], train_docs, train_doc_to_index, train_groups, train_q[: min(len(train_rows), 640)], train_d, device)
            history.append({"step": step, "loss": float(loss.detach().cpu().item()), "train_answer_top1": train_eval["answer_correct"]})
    train_eval = _evaluate(model, train_rows, train_docs, train_doc_to_index, train_groups, train_q, train_d, device)
    eval_eval = _evaluate(model, eval_rows, eval_docs, eval_doc_to_index, eval_groups, eval_q, eval_d, device)
    fusion_eval = None
    if str(args.fusion_bundle_dir).strip():
        repo_root = Path(args.repo_root).resolve()
        retrieval_eval = _load_retrieval_eval(repo_root)
        frozen_model, tokenizer, _manifest = retrieval_eval._load_model(
            Path(args.fusion_bundle_dir).resolve(),
            repo_root=repo_root,
            device=device,
        )
        frozen_model.eval()
        for parameter in frozen_model.parameters():
            parameter.requires_grad_(False)
        frozen_queries = _embed_frozen_queries(
            retrieval_eval,
            frozen_model,
            tokenizer,
            eval_rows,
            max_tokens=int(args.fusion_max_query_tokens),
            batch_size=int(args.fusion_embed_batch_size),
            device=device,
        )
        frozen_docs = _embed_frozen_docs(
            retrieval_eval,
            frozen_model,
            tokenizer,
            eval_docs,
            max_tokens=int(args.fusion_max_doc_tokens),
            batch_size=int(args.fusion_embed_batch_size),
            device=device,
        )
        fusion_eval = _evaluate_fusion(
            model,
            eval_rows,
            eval_docs,
            eval_doc_to_index,
            eval_groups,
            eval_q,
            eval_d,
            frozen_queries,
            frozen_docs,
            device,
            [float(value) for value in str(args.fusion_alphas).split(",") if value.strip()],
        )
        if bool(args.fusion_calibrate_on_train):
            calibration_source_rows = calibration_rows if calibration_rows else train_rows
            calibration_source_docs = calibration_docs if calibration_rows else train_docs
            calibration_source_doc_to_index = calibration_doc_to_index if calibration_rows else train_doc_to_index
            calibration_source_groups = calibration_groups if calibration_rows else train_groups
            calibration_source_q = calibration_q if calibration_rows else train_q
            calibration_source_d = calibration_d if calibration_rows else train_d
            frozen_train_queries = _embed_frozen_queries(
                retrieval_eval,
                frozen_model,
                tokenizer,
                calibration_source_rows,
                max_tokens=int(args.fusion_max_query_tokens),
                batch_size=int(args.fusion_embed_batch_size),
                device=device,
            )
            frozen_train_docs = _embed_frozen_docs(
                retrieval_eval,
                frozen_model,
                tokenizer,
                calibration_source_docs,
                max_tokens=int(args.fusion_max_doc_tokens),
                batch_size=int(args.fusion_embed_batch_size),
                device=device,
            )
            train_fusion_eval = _evaluate_fusion(
                model,
                calibration_source_rows,
                calibration_source_docs,
                calibration_source_doc_to_index,
                calibration_source_groups,
                calibration_source_q,
                calibration_source_d,
                frozen_train_queries,
                frozen_train_docs,
                device,
                [float(value) for value in str(args.fusion_alphas).split(",") if value.strip()],
            )
            selected_alpha = train_fusion_eval["best_answer_alpha"]
            calibration_operation_alphas = _select_operation_alphas(train_fusion_eval, operations)
            eval_operation_alphas = _select_operation_alphas(fusion_eval, operations)
            learned_gate_eval = None
            if int(args.fusion_gate_epochs) > 0:
                operation_to_index = {operation: index for index, operation in enumerate(operations)}
                calibration_gate_examples = _iter_fusion_gate_examples(
                    model,
                    calibration_source_rows,
                    calibration_source_docs,
                    calibration_source_doc_to_index,
                    calibration_source_groups,
                    calibration_source_q,
                    calibration_source_d,
                    frozen_train_queries,
                    frozen_train_docs,
                    device,
                    operation_to_index,
                )
                eval_gate_examples = _iter_fusion_gate_examples(
                    model,
                    eval_rows,
                    eval_docs,
                    eval_doc_to_index,
                    eval_groups,
                    eval_q,
                    eval_d,
                    frozen_queries,
                    frozen_docs,
                    device,
                    operation_to_index,
                )
                learned_gate_eval = _train_fusion_gate(
                    calibration_gate_examples,
                    eval_gate_examples,
                    calibration_source_docs,
                    eval_docs,
                    feature_dim=6 + len(operations),
                    hidden_dim=int(args.fusion_gate_hidden_dim),
                    epochs=int(args.fusion_gate_epochs),
                    learning_rate=float(args.fusion_gate_learning_rate),
                    weight_decay=float(args.fusion_gate_weight_decay),
                    seed=int(args.seed),
                )
            fusion_eval["train_calibration"] = {
                "selected_alpha": selected_alpha,
                "calibration_source": "external_calibration" if external_calibration_rows else ("heldout_train_calibration" if calibration_rows else "train"),
                "calibration_dataset_path": external_calibration_path,
                "calibration_examples": len(calibration_source_rows),
                "train_best_answer": train_fusion_eval["best_answer"],
                "train_best_exact": train_fusion_eval["best_exact"],
                "eval_at_selected_alpha": fusion_eval["alphas"][str(selected_alpha)],
                "operation_selected_alphas": calibration_operation_alphas,
                "eval_at_operation_selected_alphas": _evaluate_fusion_operation_alphas(
                    fusion_eval,
                    calibration_operation_alphas,
                ),
                "eval_oracle_operation_alphas": eval_operation_alphas,
                "eval_at_eval_oracle_operation_alphas": _evaluate_fusion_operation_alphas(
                    fusion_eval,
                    eval_operation_alphas,
                ),
                "learned_score_feature_gate": learned_gate_eval,
            }
    summary = {
        "artifact_kind": "stage821_hash_binding_selector_eval",
        "dataset_manifest": str(Path(args.dataset_manifest).resolve()),
        "train_examples": len(train_rows),
        "calibration_examples": len(calibration_rows),
        "external_calibration_examples": len(external_calibration_rows),
        "calibration_dataset_path": external_calibration_path,
        "eval_examples": len(eval_rows),
        "train_candidate_docs": len(train_docs),
        "eval_candidate_docs": len(eval_docs),
        "hash_buckets": int(args.hash_buckets),
        "input_buckets": input_buckets,
        "typed_token_bags": typed_token_bags,
        "token_types": list(TOKEN_TYPES) if typed_token_bags else [],
        "hash_dim": int(args.hash_dim),
        "hidden_dim": int(args.hidden_dim),
        "selector_parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "operation_specific_scorers": bool(args.operation_specific_scorers),
        "operation_adapter_rank": int(args.operation_adapter_rank),
        "steps": int(args.steps),
        "rows_per_step": int(args.rows_per_step),
        "max_candidates_per_group": int(args.max_candidates_per_group),
        "calibration_fraction": float(args.calibration_fraction),
        "calibration_stratified": bool(args.calibration_stratified),
        "operations": operations,
        "operation_loss_weights": operation_loss_weights,
        "bridge_loss_weight": float(args.bridge_loss_weight),
        "bridge_max_pairs": int(args.bridge_max_pairs),
        "train_bridge_pairs": len(train_bridge_pairs),
        "eval_bridge_pairs": len(eval_bridge_pairs),
        "history": history,
        "train": train_eval,
        "eval": eval_eval,
        "fusion_eval": fusion_eval,
        "deterministic_overlap_baseline": {"answer_correct": 40, "exact_correct": 39},
        "decision_hint": "Accepted only if eval beats the Stage820 deterministic overlap baseline without exact token identity.",
    }
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(_repo_root()))
    parser.add_argument("--dataset-manifest", required=True)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--hash-buckets", type=int, default=512)
    parser.add_argument("--typed-token-bags", action="store_true")
    parser.add_argument("--hash-dim", type=int, default=32)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--rows-per-step", type=int, default=128)
    parser.add_argument("--max-candidates-per-group", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=0.002)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--bridge-loss-weight", type=float, default=0.0)
    parser.add_argument("--bridge-max-pairs", type=int, default=512)
    parser.add_argument("--operation-loss-weights", default="")
    parser.add_argument("--operation-specific-scorers", action="store_true")
    parser.add_argument("--operation-adapter-rank", type=int, default=0)
    parser.add_argument("--fusion-bundle-dir", default="")
    parser.add_argument("--fusion-alphas", default="-2,-1,-0.5,-0.25,0,0.25,0.5,1,2")
    parser.add_argument("--fusion-calibrate-on-train", action="store_true")
    parser.add_argument("--fusion-gate-epochs", type=int, default=0)
    parser.add_argument("--fusion-gate-hidden-dim", type=int, default=32)
    parser.add_argument("--fusion-gate-learning-rate", type=float, default=0.01)
    parser.add_argument("--fusion-gate-weight-decay", type=float, default=0.001)
    parser.add_argument("--fusion-max-query-tokens", type=int, default=128)
    parser.add_argument("--fusion-max-doc-tokens", type=int, default=256)
    parser.add_argument("--fusion-embed-batch-size", type=int, default=128)
    parser.add_argument("--seed", type=int, default=821)
    parser.add_argument("--log-every", type=int, default=100)
    parser.add_argument("--max-train-examples", type=int, default=0)
    parser.add_argument("--max-eval-examples", type=int, default=0)
    parser.add_argument("--calibration-examples", type=int, default=0)
    parser.add_argument("--calibration-fraction", type=float, default=0.0)
    parser.add_argument("--calibration-stratified", action="store_true")
    parser.add_argument("--calibration-dataset-path", default="")
    parser.add_argument("--output-json", required=True)
    train(parser.parse_args())


if __name__ == "__main__":
    main()

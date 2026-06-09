#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import random
import re
from typing import Any

import torch
import torch.nn.functional as F


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_retrieval_eval(repo_root: Path):
    path = repo_root / "legacy_src" / "scripts" / "evaluate_agentkernel_lite_retrieval_embeddings.py"
    spec = importlib.util.spec_from_file_location("evaluate_agentkernel_lite_retrieval_embeddings", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load retrieval evaluator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        if str(row.get("task_type", "") or "") == "active_agent_direct_answer"
        and str(row.get("retrieval_query_text", "") or "").strip()
        and str(row.get("retrieval_doc_text", "") or "").strip()
    ]


def _collision_key(row: dict[str, Any]) -> str:
    value = str(row.get("collision_key_value", "") or "").strip()
    if value:
        return value
    name = str(row.get("collision_key_name", "") or "").strip()
    if name and str(row.get(name, "") or "").strip():
        return str(row.get(name, "") or "").strip()
    return str(row.get("operation", "") or "global")


_KEY_VALUE_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]*?)=([^\s;]+)")
_ENTITY_RE = re.compile(r"\b(gdom_\d+_e\d+|gdom_999_e\d+)\b")
_TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9_]*\b|\b\d+\b")
_STOP_TOKENS = {
    "ak_op_atomic_fact",
    "ak_op_code_api_semantics",
    "ak_op_composition",
    "ak_op_counterfactual_false_claim",
    "ak_op_exception",
    "ak_op_math_identity",
    "ak_op_relation",
    "ak_op_schema",
    "answer",
    "collision_key",
    "direct_answer",
    "domain",
    "family",
    "gsel",
    "has",
    "op",
    "query",
    "selector_dropout",
    "statement",
    "structured",
    "true",
}


def _kv(text: str) -> dict[str, str]:
    return {str(key): str(value) for key, value in _KEY_VALUE_RE.findall(str(text or ""))}


def _gsel_parts(text: str) -> list[str]:
    return str(_kv(text).get("gsel", "") or "").split("|")


def _field_hint(text: str) -> str:
    values = _kv(text)
    gsel = str(values.get("gsel", "") or "")
    parts = gsel.split("|")
    if len(parts) >= 3 and parts[2]:
        return parts[2]
    if len(parts) >= 4 and parts[3]:
        return parts[3]
    match = re.search(r"\bhas\s+([A-Za-z][A-Za-z0-9_]*)\b", str(text or ""))
    if match:
        return str(match.group(1))
    return str(values.get("field", "") or values.get("relation", "") or "")


def _domain_hint(text: str) -> str:
    values = _kv(text)
    if str(values.get("domain", "") or ""):
        return str(values["domain"])
    parts = _gsel_parts(text)
    if len(parts) >= 2:
        return parts[1]
    match = re.search(r"\b(gdom_\d+)\b", str(text or ""))
    return str(match.group(1)) if match else ""


def _text_tokens(text: str) -> set[str]:
    values = _kv(text)
    answer_value = str(values.get("answer", "") or "").lower()
    tokens = {token.lower() for token in _TOKEN_RE.findall(str(text or ""))}
    return {token for token in tokens if token not in _STOP_TOKENS and token != answer_value}


def _route_features(query_text: str, doc_text: str) -> list[float]:
    query_values = _kv(query_text)
    doc_values = _kv(doc_text)
    query_domain = _domain_hint(query_text)
    doc_domain = _domain_hint(doc_text)
    query_field = _field_hint(query_text)
    doc_field = _field_hint(doc_text)
    query_entities = set(_ENTITY_RE.findall(str(query_text or "")))
    doc_entities = set(_ENTITY_RE.findall(str(doc_text or "")))
    query_tokens = _text_tokens(query_text)
    doc_tokens = _text_tokens(doc_text)
    intersection = query_tokens & doc_tokens
    union = query_tokens | doc_tokens
    query_gsel = _gsel_parts(query_text)
    doc_gsel = _gsel_parts(doc_text)
    return [
        1.0 if query_domain and query_domain == doc_domain else 0.0,
        1.0 if query_field and query_field == doc_field else 0.0,
        1.0 if query_entities and bool(query_entities & doc_entities) else 0.0,
        float(len(query_entities & doc_entities)),
        float(len(intersection)),
        float(len(intersection)) / float(len(union) or 1),
        1.0 if str(query_values.get("op", "") or "") and str(query_values.get("op", "") or "") == str(doc_values.get("op", "") or "") else 0.0,
        1.0 if len(query_gsel) >= 2 and len(doc_gsel) >= 2 and query_gsel[1] == doc_gsel[1] else 0.0,
        1.0 if len(query_gsel) >= 3 and len(doc_gsel) >= 3 and query_gsel[2] == doc_gsel[2] else 0.0,
        float(len(query_tokens)),
        float(len(doc_tokens)),
    ]


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
        groups.setdefault(_collision_key(row), [])
        if index not in groups[_collision_key(row)]:
            groups[_collision_key(row)].append(index)
    return docs, doc_to_index, groups


def _embed_query_rows(
    retrieval_eval,
    model,
    tokenizer,
    rows: list[dict[str, Any]],
    *,
    query_source: str,
    max_tokens: int,
    batch_size: int,
    device: torch.device,
) -> torch.Tensor:
    chunks: list[torch.Tensor] = []
    with torch.no_grad():
        for offset in range(0, len(rows), int(batch_size)):
            texts = [
                str(row.get(query_source, "") or row.get("retrieval_query_text", "") or row.get("encoder_text", ""))
                for row in rows[offset : offset + int(batch_size)]
            ]
            if query_source == "encoder_text":
                embed = retrieval_eval._embed(model, tokenizer, texts, max_tokens=int(max_tokens), device=device)
            else:
                embed = retrieval_eval._embed_query(model, tokenizer, texts, max_tokens=int(max_tokens), device=device)
            chunks.append(embed.detach().float().cpu())
    return torch.cat(chunks, dim=0)


def _embed_docs(
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
            embed = retrieval_eval._embed_doc(
                model,
                tokenizer,
                docs[offset : offset + int(batch_size)],
                max_tokens=int(max_tokens),
                device=device,
            )
            chunks.append(embed.detach().float().cpu())
    return torch.cat(chunks, dim=0)


class PairRanker(torch.nn.Module):
    def __init__(
        self,
        input_dim: int,
        hidden_dim: int,
        route_target_dim: int = 0,
        predicted_route_feedback: bool = False,
        atomic_target_dim: int = 0,
        predicted_atomic_feedback: bool = False,
    ) -> None:
        super().__init__()
        self.route_target_dim = int(route_target_dim)
        self.predicted_route_feedback = bool(predicted_route_feedback)
        self.atomic_target_dim = int(atomic_target_dim)
        self.predicted_atomic_feedback = bool(predicted_atomic_feedback)
        if int(hidden_dim) <= 0:
            self.trunk = torch.nn.Identity()
            trunk_dim = int(input_dim)
        else:
            self.trunk = torch.nn.Sequential(torch.nn.Linear(int(input_dim), int(hidden_dim)), torch.nn.GELU())
            trunk_dim = int(hidden_dim)
        self.route_head = torch.nn.Linear(trunk_dim, self.route_target_dim) if self.route_target_dim > 0 else None
        self.atomic_head = torch.nn.Linear(trunk_dim, self.atomic_target_dim) if self.atomic_target_dim > 0 else None
        score_input_dim = trunk_dim + (self.route_target_dim if self.predicted_route_feedback else 0)
        score_input_dim += self.atomic_target_dim if self.predicted_atomic_feedback else 0
        self.score_head = torch.nn.Linear(score_input_dim, 1)
        for module in self.modules():
            if isinstance(module, torch.nn.Linear):
                torch.nn.init.xavier_uniform_(module.weight)
                torch.nn.init.zeros_(module.bias)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        trunk_hidden = self.trunk(features)
        hidden = trunk_hidden
        if self.predicted_route_feedback:
            if self.route_head is None:
                raise RuntimeError("predicted route feedback requires a route head")
            route_pred = self.route_head(trunk_hidden)
            hidden = torch.cat([hidden, route_pred], dim=-1)
        if self.predicted_atomic_feedback:
            if self.atomic_head is None:
                raise RuntimeError("predicted atomic feedback requires an atomic head")
            atomic_pred = self.atomic_head(trunk_hidden)
            hidden = torch.cat([hidden, atomic_pred], dim=-1)
        return self.score_head(hidden)

    def predict_route(self, features: torch.Tensor) -> torch.Tensor | None:
        if self.route_head is None:
            return None
        hidden = self.trunk(features)
        return self.route_head(hidden)

    def predict_atomic(self, features: torch.Tensor) -> torch.Tensor | None:
        if self.atomic_head is None:
            return None
        hidden = self.trunk(features)
        return self.atomic_head(hidden)


class OperationConditionedPairRanker(torch.nn.Module):
    def __init__(
        self,
        operations: list[str],
        input_dim: int,
        hidden_dim: int,
        route_target_dim: int = 0,
        predicted_route_feedback: bool = False,
        atomic_target_dim: int = 0,
        predicted_atomic_feedback: bool = False,
    ) -> None:
        super().__init__()
        if not operations:
            raise ValueError("operation-conditioned ranker requires at least one operation")
        self.operation_to_key = {operation: f"op_{index}" for index, operation in enumerate(operations)}
        self.key_to_operation = {key: operation for operation, key in self.operation_to_key.items()}
        self.rankers = torch.nn.ModuleDict(
            {
                key: PairRanker(
                    int(input_dim),
                    int(hidden_dim),
                    int(route_target_dim),
                    bool(predicted_route_feedback),
                    int(atomic_target_dim),
                    bool(predicted_atomic_feedback),
                )
                for key in self.operation_to_key.values()
            }
        )

    def _ranker(self, operation: str) -> PairRanker:
        key = self.operation_to_key.get(str(operation or "unknown"))
        if key is None:
            raise KeyError(f"unknown operation for operation-conditioned ranker: {operation}")
        return self.rankers[key]

    def forward(self, features: torch.Tensor, operation: str | None = None) -> torch.Tensor:
        if operation is None:
            raise RuntimeError("operation-conditioned ranker requires operation")
        return self._ranker(str(operation))(features)

    def predict_route(self, features: torch.Tensor, operation: str | None = None) -> torch.Tensor | None:
        if operation is None:
            raise RuntimeError("operation-conditioned ranker requires operation")
        return self._ranker(str(operation)).predict_route(features)

    def predict_atomic(self, features: torch.Tensor, operation: str | None = None) -> torch.Tensor | None:
        if operation is None:
            raise RuntimeError("operation-conditioned ranker requires operation")
        return self._ranker(str(operation)).predict_atomic(features)


def _make_scorer(
    input_dim: int,
    hidden_dim: int,
    route_target_dim: int = 0,
    predicted_route_feedback: bool = False,
    atomic_target_dim: int = 0,
    predicted_atomic_feedback: bool = False,
    operation_conditioned: bool = False,
    operations: list[str] | None = None,
) -> PairRanker:
    if bool(operation_conditioned):
        return OperationConditionedPairRanker(
            sorted(set(operations or [])),
            int(input_dim),
            int(hidden_dim),
            int(route_target_dim),
            bool(predicted_route_feedback),
            int(atomic_target_dim),
            bool(predicted_atomic_feedback),
        )
    return PairRanker(
        int(input_dim),
        int(hidden_dim),
        int(route_target_dim),
        bool(predicted_route_feedback),
        int(atomic_target_dim),
        bool(predicted_atomic_feedback),
    )


def _pair_features(
    query: torch.Tensor,
    docs: torch.Tensor,
    route_features: torch.Tensor | None = None,
    operation_features: torch.Tensor | None = None,
) -> torch.Tensor:
    query_expanded = query.unsqueeze(0).expand_as(docs)
    base_score = (query_expanded * docs).sum(dim=-1, keepdim=True)
    features = [query_expanded, docs, query_expanded * docs, (query_expanded - docs).abs(), base_score]
    if route_features is not None:
        features.append(route_features.to(device=docs.device, dtype=docs.dtype))
    if operation_features is not None:
        features.append(operation_features.to(device=docs.device, dtype=docs.dtype))
    return torch.cat(features, dim=-1)


def _route_feature_matrix(query_text: str, doc_texts: list[str], *, enabled: bool) -> torch.Tensor | None:
    if not enabled:
        return None
    return torch.tensor([_route_features(query_text, doc_text) for doc_text in doc_texts], dtype=torch.float32)


def _route_target_indices(mode: str) -> list[int]:
    normalized = str(mode or "all11").strip().lower()
    if normalized == "all11":
        return list(range(11))
    if normalized in {"binding9", "slots9"}:
        return list(range(9))
    if normalized in {"binary6", "slots6"}:
        return [0, 1, 2, 6, 7, 8]
    raise ValueError(f"unknown route target mode: {mode}")


def _select_route_targets(features: torch.Tensor, mode: str) -> torch.Tensor:
    indices = torch.tensor(_route_target_indices(mode), dtype=torch.long, device=features.device)
    return features.index_select(dim=-1, index=indices)


def _select_atomic_slot_targets(features: torch.Tensor) -> torch.Tensor:
    indices = torch.tensor([1, 2, 3, 4, 5, 8], dtype=torch.long, device=features.device)
    return features.index_select(dim=-1, index=indices)


def _select_atomic_binary_targets(features: torch.Tensor) -> torch.Tensor:
    indices = torch.tensor([1, 2, 8], dtype=torch.long, device=features.device)
    return features.index_select(dim=-1, index=indices).clamp(0.0, 1.0)


def _parse_operation_loss_weights(value: str) -> dict[str, float]:
    weights: dict[str, float] = {}
    for item in str(value or "").split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(f"operation loss weight must be OP:WEIGHT, got {item!r}")
        operation, weight_text = item.split(":", 1)
        operation = operation.strip()
        if not operation:
            raise ValueError(f"empty operation in loss weight item {item!r}")
        weights[operation] = float(weight_text)
    return weights


def _parse_operation_filter(value: str) -> set[str]:
    return {item.strip() for item in str(value or "").split(",") if item.strip()}


def _build_route_cache(
    rows: list[dict[str, Any]],
    docs: list[str],
    groups: dict[str, list[int]],
    *,
    enabled: bool,
) -> list[dict[int, torch.Tensor]] | None:
    if not enabled:
        return None
    cache: list[dict[int, torch.Tensor]] = []
    for row in rows:
        query_text = str(row.get("retrieval_query_text", "") or row.get("encoder_text", ""))
        row_cache: dict[int, torch.Tensor] = {}
        for doc_index in groups[_collision_key(row)]:
            row_cache[int(doc_index)] = torch.tensor(_route_features(query_text, docs[int(doc_index)]), dtype=torch.float32)
        cache.append(row_cache)
    return cache


def _row_label(row: dict[str, Any], doc_to_index: dict[str, int], group: list[int]) -> int:
    positive = doc_to_index[str(row.get("retrieval_doc_text", "") or "").strip()]
    return group.index(positive)


def _score_split(
    *,
    scorer: torch.nn.Module,
    queries: torch.Tensor,
    docs: torch.Tensor,
    rows: list[dict[str, Any]],
    doc_to_index: dict[str, int],
    groups: dict[str, list[int]],
    retrieval_eval,
    device: torch.device,
    max_failures: int,
    route_cache: list[dict[int, torch.Tensor]] | None,
    operation_to_index: dict[str, int] | None,
) -> dict[str, Any]:
    scorer.eval()
    exact = 0
    answer = 0
    base_exact = 0
    base_answer = 0
    reciprocal = 0.0
    failures: list[dict[str, Any]] = []
    by_operation: dict[str, dict[str, int]] = {}
    with torch.no_grad():
        for row_index, row in enumerate(rows):
            operation = str(row.get("operation", "") or "unknown")
            op_stats = by_operation.setdefault(
                operation,
                {
                    "examples": 0,
                    "exact_top1_correct": 0,
                    "answer_top1_correct": 0,
                    "base_exact_top1_correct": 0,
                    "base_answer_top1_correct": 0,
                },
            )
            op_stats["examples"] += 1
            group = groups[_collision_key(row)]
            group_docs = docs[group].to(device)
            query = queries[row_index].to(device)
            route_features = (
                torch.stack([route_cache[row_index][int(group_index)] for group_index in group], dim=0)
                if route_cache is not None
                else None
            )
            operation_features = None
            if operation_to_index is not None:
                operation_features = torch.zeros((len(group), len(operation_to_index)), dtype=torch.float32)
                operation_features[:, int(operation_to_index[operation])] = 1.0
            features = _pair_features(query, group_docs, route_features, operation_features)
            scores = scorer(features, operation=operation).squeeze(-1).detach().cpu() if getattr(scorer, "_operation_conditioned", False) else scorer(features).squeeze(-1).detach().cpu()
            base_scores = (query.detach().cpu().unsqueeze(0) * docs[group]).sum(dim=-1)
            label = _row_label(row, doc_to_index, group)
            order = torch.argsort(scores, descending=True)
            base_order = torch.argsort(base_scores, descending=True)
            predicted_group_index = int(order[0].item())
            predicted_doc = docs.new_empty(0)
            del predicted_doc
            predicted_text = next(text for text, idx in doc_to_index.items() if idx == group[predicted_group_index])
            base_predicted_text = next(text for text, idx in doc_to_index.items() if idx == group[int(base_order[0].item())])
            if predicted_group_index == label:
                exact += 1
                op_stats["exact_top1_correct"] += 1
            if int(base_order[0].item()) == label:
                base_exact += 1
                op_stats["base_exact_top1_correct"] += 1
            expected_content = str(row.get("expected_content", "") or "")
            if predicted_group_index == label or retrieval_eval._doc_matches_expected_content(expected_content, predicted_text):
                answer += 1
                op_stats["answer_top1_correct"] += 1
            if int(base_order[0].item()) == label or retrieval_eval._doc_matches_expected_content(expected_content, base_predicted_text):
                base_answer += 1
                op_stats["base_answer_top1_correct"] += 1
            rank = int((order == label).nonzero(as_tuple=False)[0].item()) + 1
            reciprocal += 1.0 / float(rank)
            if predicted_group_index != label and len(failures) < int(max_failures):
                failures.append(
                    {
                        "source_id": row.get("source_id", ""),
                        "collision_key": _collision_key(row),
                        "candidate_count": len(group),
                        "expected_content": expected_content,
                        "rank": rank,
                        "top5": [
                            {
                                "source_id": rows[row_index].get("source_id", ""),
                                "score": float(scores[int(candidate)].item()),
                                "doc": next(text for text, idx in doc_to_index.items() if idx == group[int(candidate)]),
                            }
                            for candidate in order[:5]
                        ],
                    }
                )
    total = len(rows)
    by_operation_rates = {}
    for operation, stats in sorted(by_operation.items()):
        examples = int(stats["examples"])
        by_operation_rates[operation] = {
            **stats,
            "exact_top1_accuracy": float(stats["exact_top1_correct"]) / float(examples or 1),
            "answer_top1_accuracy": float(stats["answer_top1_correct"]) / float(examples or 1),
            "base_exact_top1_accuracy": float(stats["base_exact_top1_correct"]) / float(examples or 1),
            "base_answer_top1_accuracy": float(stats["base_answer_top1_correct"]) / float(examples or 1),
        }
    return {
        "examples": total,
        "exact_top1_correct": int(exact),
        "exact_top1_accuracy": float(exact) / float(total or 1),
        "answer_top1_correct": int(answer),
        "answer_top1_accuracy": float(answer) / float(total or 1),
        "mrr": reciprocal / float(total or 1),
        "base_exact_top1_correct": int(base_exact),
        "base_exact_top1_accuracy": float(base_exact) / float(total or 1),
        "base_answer_top1_correct": int(base_answer),
        "base_answer_top1_accuracy": float(base_answer) / float(total or 1),
        "by_operation": by_operation_rates,
        "failures": failures,
    }


def train(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(args.repo_root).resolve()
    retrieval_eval = _load_retrieval_eval(repo_root)
    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    device = torch.device(str(args.device))
    operation_loss_weights = _parse_operation_loss_weights(str(args.operation_loss_weights))

    dataset_manifest = json.loads(Path(args.dataset_manifest).read_text(encoding="utf-8"))
    train_rows = _direct_rows(_iter_jsonl(Path(dataset_manifest["train_dataset_path"])))
    eval_rows = _direct_rows(_iter_jsonl(Path(dataset_manifest["eval_dataset_path"])))
    include_operations = _parse_operation_filter(str(args.include_operations))
    if include_operations:
        train_rows = [row for row in train_rows if str(row.get("operation", "") or "unknown") in include_operations]
        eval_rows = [row for row in eval_rows if str(row.get("operation", "") or "unknown") in include_operations]
        if not train_rows or not eval_rows:
            raise RuntimeError(f"operation filter left empty train/eval split: {sorted(include_operations)}")
    if int(args.max_train_examples) > 0:
        train_rows = train_rows[: int(args.max_train_examples)]
    if int(args.max_eval_examples) > 0:
        eval_rows = eval_rows[: int(args.max_eval_examples)]

    model, tokenizer, model_manifest = retrieval_eval._load_model(
        Path(args.bundle_dir).resolve(),
        repo_root=repo_root,
        device=device,
    )
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    model.eval()

    train_docs, train_doc_to_index, train_groups = _unique_docs(train_rows)
    eval_docs, eval_doc_to_index, eval_groups = _unique_docs(eval_rows)
    train_q = _embed_query_rows(
        retrieval_eval,
        model,
        tokenizer,
        train_rows,
        query_source=str(args.query_source),
        max_tokens=int(args.max_query_tokens),
        batch_size=int(args.embed_batch_size),
        device=device,
    )
    eval_q = _embed_query_rows(
        retrieval_eval,
        model,
        tokenizer,
        eval_rows,
        query_source=str(args.query_source),
        max_tokens=int(args.max_query_tokens),
        batch_size=int(args.embed_batch_size),
        device=device,
    )
    train_d = _embed_docs(
        retrieval_eval,
        model,
        tokenizer,
        train_docs,
        max_tokens=int(args.max_doc_tokens),
        batch_size=int(args.embed_batch_size),
        device=device,
    )
    eval_d = _embed_docs(
        retrieval_eval,
        model,
        tokenizer,
        eval_docs,
        max_tokens=int(args.max_doc_tokens),
        batch_size=int(args.embed_batch_size),
        device=device,
    )
    needs_route_targets = (
        bool(args.route_features)
        or float(args.route_target_loss_weight) > 0.0
        or float(args.atomic_binary_target_loss_weight) > 0.0
        or float(args.atomic_hard_negative_margin_weight) > 0.0
        or float(args.atomic_partition_score_loss_weight) > 0.0
    )
    train_route_cache = _build_route_cache(train_rows, train_docs, train_groups, enabled=needs_route_targets)
    eval_route_cache = _build_route_cache(eval_rows, eval_docs, eval_groups, enabled=needs_route_targets)

    route_feature_dim = len(_route_features("op=a domain=gdom_000 query=gdom_000_e001 has color", "op=a domain=gdom_000 gsel=factgrp|gdom_000|color statement=gdom_000_e001 has color")) if bool(args.route_features) else 0
    route_target_dim = len(_route_target_indices(str(args.route_target_mode))) if float(args.route_target_loss_weight) > 0.0 else 0
    atomic_target_dim = 3 if float(args.atomic_binary_target_loss_weight) > 0.0 else 0
    operations = sorted({str(row.get("operation", "") or "unknown") for row in [*train_rows, *eval_rows]})
    operation_to_index = {operation: index for index, operation in enumerate(operations)} if bool(args.operation_features) else None
    operation_feature_dim = len(operations) if operation_to_index is not None else 0
    feature_dim = int(train_q.shape[1]) * 4 + 1 + int(route_feature_dim) + int(operation_feature_dim)
    scorer = _make_scorer(
        feature_dim,
        int(args.hidden_dim),
        route_target_dim,
        predicted_route_feedback=bool(args.predicted_route_feedback),
        atomic_target_dim=atomic_target_dim,
        predicted_atomic_feedback=bool(args.predicted_atomic_feedback),
        operation_conditioned=bool(args.operation_conditioned_scorer),
        operations=operations,
    ).to(device)
    setattr(scorer, "_use_route_features", bool(args.route_features))
    setattr(scorer, "_operation_conditioned", bool(args.operation_conditioned_scorer))
    optimizer = torch.optim.AdamW(scorer.parameters(), lr=float(args.learning_rate), weight_decay=float(args.weight_decay))
    train_order = list(range(len(train_rows)))
    pretrain_history: list[dict[str, float | int]] = []
    if int(args.route_pretrain_steps) > 0:
        if route_target_dim <= 0 or train_route_cache is None:
            raise RuntimeError("--route-pretrain-steps requires --route-target-loss-weight > 0")
        for step in range(1, int(args.route_pretrain_steps) + 1):
            random.shuffle(train_order)
            batch_losses = []
            for row_index in train_order[: int(args.rows_per_step)]:
                row = train_rows[row_index]
                group = train_groups[_collision_key(row)]
                if int(args.max_candidates_per_group) > 0 and len(group) > int(args.max_candidates_per_group):
                    positive = train_doc_to_index[str(row.get("retrieval_doc_text", "") or "").strip()]
                    negatives = [index for index in group if index != positive]
                    random.shuffle(negatives)
                    group = [positive, *negatives[: int(args.max_candidates_per_group) - 1]]
                    random.shuffle(group)
                route_features = (
                    torch.stack([train_route_cache[row_index][int(group_index)] for group_index in group], dim=0)
                    if train_route_cache is not None and bool(args.route_features)
                    else None
                )
                operation_features = None
                if operation_to_index is not None:
                    operation = str(row.get("operation", "") or "unknown")
                    operation_features = torch.zeros((len(group), len(operation_to_index)), dtype=torch.float32)
                    operation_features[:, int(operation_to_index[operation])] = 1.0
                features = _pair_features(train_q[row_index].to(device), train_d[group].to(device), route_features, operation_features)
                route_targets = torch.stack([train_route_cache[row_index][int(group_index)] for group_index in group], dim=0).to(device)
                route_targets = _select_route_targets(route_targets, str(args.route_target_mode))
                route_pred = scorer.predict_route(features, operation=str(row.get("operation", "") or "unknown")) if bool(args.operation_conditioned_scorer) else scorer.predict_route(features)
                if route_pred is None:
                    raise RuntimeError("route pretrain requested but scorer has no route head")
                batch_losses.append(F.smooth_l1_loss(route_pred, route_targets))
            loss = torch.stack(batch_losses).mean()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            if step == 1 or step == int(args.route_pretrain_steps) or step % int(args.log_every) == 0:
                pretrain_history.append({"step": step, "route_loss": float(loss.detach().cpu().item())})
    history: list[dict[str, float | int]] = []
    for step in range(1, int(args.steps) + 1):
        random.shuffle(train_order)
        batch_losses: list[torch.Tensor] = []
        for row_index in train_order[: int(args.rows_per_step)]:
            row = train_rows[row_index]
            group = train_groups[_collision_key(row)]
            if int(args.max_candidates_per_group) > 0 and len(group) > int(args.max_candidates_per_group):
                positive = train_doc_to_index[str(row.get("retrieval_doc_text", "") or "").strip()]
                negatives = [index for index in group if index != positive]
                random.shuffle(negatives)
                group = [positive, *negatives[: int(args.max_candidates_per_group) - 1]]
                random.shuffle(group)
            label = _row_label(row, train_doc_to_index, group)
            route_features = (
                torch.stack([train_route_cache[row_index][int(group_index)] for group_index in group], dim=0)
                if train_route_cache is not None and bool(args.route_features)
                else None
            )
            operation_features = None
            if operation_to_index is not None:
                operation = str(row.get("operation", "") or "unknown")
                operation_features = torch.zeros((len(group), len(operation_to_index)), dtype=torch.float32)
                operation_features[:, int(operation_to_index[operation])] = 1.0
            features = _pair_features(train_q[row_index].to(device), train_d[group].to(device), route_features, operation_features)
            scores = scorer(features, operation=str(row.get("operation", "") or "unknown")).squeeze(-1) if bool(args.operation_conditioned_scorer) else scorer(features).squeeze(-1)
            row_loss = F.cross_entropy(scores.unsqueeze(0), torch.tensor([label], dtype=torch.long, device=device))
            if float(args.route_target_loss_weight) > 0.0:
                route_targets = torch.stack([train_route_cache[row_index][int(group_index)] for group_index in group], dim=0).to(device)
                route_targets = _select_route_targets(route_targets, str(args.route_target_mode))
                route_pred = scorer.predict_route(features, operation=str(row.get("operation", "") or "unknown")) if bool(args.operation_conditioned_scorer) else scorer.predict_route(features)
                if route_pred is None:
                    raise RuntimeError("route target loss requested but scorer has no route head")
                row_loss = row_loss + float(args.route_target_loss_weight) * F.smooth_l1_loss(route_pred, route_targets)
                if str(row.get("operation", "") or "unknown") == "atomic_fact" and float(args.atomic_slot_target_loss_weight) > 0.0:
                    if str(args.route_target_mode) != "all11":
                        raise RuntimeError("--atomic-slot-target-loss-weight requires --route-target-mode all11")
                    row_loss = row_loss + float(args.atomic_slot_target_loss_weight) * F.smooth_l1_loss(
                        _select_atomic_slot_targets(route_pred),
                        _select_atomic_slot_targets(route_targets),
                    )
            if str(row.get("operation", "") or "unknown") == "atomic_fact" and float(args.atomic_binary_target_loss_weight) > 0.0:
                atomic_targets = torch.stack([train_route_cache[row_index][int(group_index)] for group_index in group], dim=0).to(device)
                atomic_targets = _select_atomic_binary_targets(atomic_targets)
                atomic_pred = scorer.predict_atomic(features, operation=str(row.get("operation", "") or "unknown")) if bool(args.operation_conditioned_scorer) else scorer.predict_atomic(features)
                if atomic_pred is None:
                    raise RuntimeError("atomic binary target loss requested but scorer has no atomic head")
                row_loss = row_loss + float(args.atomic_binary_target_loss_weight) * F.binary_cross_entropy_with_logits(
                    atomic_pred,
                    atomic_targets,
                )
            if str(row.get("operation", "") or "unknown") == "atomic_fact" and float(args.atomic_hard_negative_margin_weight) > 0.0:
                atomic_route_features = torch.stack([train_route_cache[row_index][int(group_index)] for group_index in group], dim=0).to(device)
                hard_mask = (
                    (atomic_route_features[:, 1] > 0.5)
                    | (atomic_route_features[:, 2] > 0.5)
                    | (atomic_route_features[:, 8] > 0.5)
                )
                hard_mask[int(label)] = False
                if bool(hard_mask.any().item()):
                    positive_score = scores[int(label)]
                    hard_negative_scores = scores[hard_mask]
                    margin = torch.tensor(float(args.atomic_hard_negative_margin), dtype=scores.dtype, device=device)
                    row_loss = row_loss + float(args.atomic_hard_negative_margin_weight) * F.softplus(
                        margin - positive_score + hard_negative_scores
                    ).mean()
            if str(row.get("operation", "") or "unknown") == "atomic_fact" and float(args.atomic_partition_score_loss_weight) > 0.0:
                atomic_route_features = torch.stack([train_route_cache[row_index][int(group_index)] for group_index in group], dim=0).to(device)
                partition_targets = ((atomic_route_features[:, 1] > 0.5) & (atomic_route_features[:, 2] > 0.5)).to(
                    dtype=scores.dtype,
                    device=device,
                )
                positive_count = partition_targets.sum().clamp_min(1.0)
                negative_count = torch.tensor(float(len(group)), dtype=scores.dtype, device=device) - positive_count
                pos_weight = (negative_count / positive_count).clamp_min(1.0)
                row_loss = row_loss + float(args.atomic_partition_score_loss_weight) * F.binary_cross_entropy_with_logits(
                    scores,
                    partition_targets,
                    pos_weight=pos_weight,
                )
            row_loss = row_loss * float(operation_loss_weights.get(str(row.get("operation", "") or "unknown"), 1.0))
            batch_losses.append(row_loss)
        loss = torch.stack(batch_losses).mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % int(args.log_every) == 0:
            history.append({"step": step, "loss": float(loss.detach().cpu().item())})

    train_eval = _score_split(
        scorer=scorer,
        queries=train_q,
        docs=train_d,
        rows=train_rows,
        doc_to_index=train_doc_to_index,
        groups=train_groups,
        retrieval_eval=retrieval_eval,
        device=device,
        max_failures=int(args.max_failures),
        route_cache=train_route_cache if bool(args.route_features) else None,
        operation_to_index=operation_to_index,
    )
    eval_eval = _score_split(
        scorer=scorer,
        queries=eval_q,
        docs=eval_d,
        rows=eval_rows,
        doc_to_index=eval_doc_to_index,
        groups=eval_groups,
        retrieval_eval=retrieval_eval,
        device=device,
        max_failures=int(args.max_failures),
        route_cache=eval_route_cache if bool(args.route_features) else None,
        operation_to_index=operation_to_index,
    )
    scorer_params = sum(parameter.numel() for parameter in scorer.parameters())
    base_params = int(model_manifest.get("parameter_count") or model_manifest.get("training_summary", {}).get("parameter_count") or 0)
    summary = {
        "artifact_kind": "frozen_query_candidate_value_ranker_eval",
        "bundle_dir": str(Path(args.bundle_dir).resolve()),
        "dataset_manifest": str(Path(args.dataset_manifest).resolve()),
        "query_source": str(args.query_source),
        "train_examples": len(train_rows),
        "eval_examples": len(eval_rows),
        "include_operations": sorted(include_operations),
        "train_candidate_docs": len(train_docs),
        "eval_candidate_docs": len(eval_docs),
        "train_collision_groups": len(train_groups),
        "eval_collision_groups": len(eval_groups),
        "embedding_dim": int(train_q.shape[1]),
        "feature_dim": int(feature_dim),
        "route_feature_dim": int(route_feature_dim),
        "operation_feature_dim": int(operation_feature_dim),
        "route_target_dim": int(route_target_dim),
        "atomic_target_dim": int(atomic_target_dim),
        "route_target_mode": str(args.route_target_mode),
        "route_target_loss_weight": float(args.route_target_loss_weight),
        "atomic_slot_target_loss_weight": float(args.atomic_slot_target_loss_weight),
        "atomic_binary_target_loss_weight": float(args.atomic_binary_target_loss_weight),
        "atomic_hard_negative_margin_weight": float(args.atomic_hard_negative_margin_weight),
        "atomic_hard_negative_margin": float(args.atomic_hard_negative_margin),
        "atomic_partition_score_loss_weight": float(args.atomic_partition_score_loss_weight),
        "predicted_route_feedback": bool(args.predicted_route_feedback),
        "predicted_atomic_feedback": bool(args.predicted_atomic_feedback),
        "operation_conditioned_scorer": bool(args.operation_conditioned_scorer),
        "operation_features": bool(args.operation_features),
        "operation_loss_weights": operation_loss_weights,
        "operations": operations,
        "base_parameter_count": int(base_params),
        "ranker_parameter_count": int(scorer_params),
        "total_with_ranker_parameter_count": int(base_params + scorer_params),
        "hidden_dim": int(args.hidden_dim),
        "route_pretrain_steps": int(args.route_pretrain_steps),
        "steps": int(args.steps),
        "rows_per_step": int(args.rows_per_step),
        "max_candidates_per_group": int(args.max_candidates_per_group),
        "route_pretrain_history": pretrain_history,
        "history": history,
        "train": train_eval,
        "eval": eval_eval,
        "decision_hint": "Use eval answer/exact gains over base same-collision ranking as evidence for reusable value-ranking internalization.",
    }
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if str(args.output_ranker).strip():
        torch.save({"state_dict": scorer.state_dict(), "summary": summary}, str(Path(args.output_ranker)))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(_repo_root()))
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--dataset-manifest", required=True)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--query-source", choices=("retrieval_query_text", "encoder_text"), default="retrieval_query_text")
    parser.add_argument("--include-operations", default="")
    parser.add_argument("--max-train-examples", type=int, default=0)
    parser.add_argument("--max-eval-examples", type=int, default=0)
    parser.add_argument("--max-query-tokens", type=int, default=128)
    parser.add_argument("--max-doc-tokens", type=int, default=256)
    parser.add_argument("--embed-batch-size", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--route-features", action="store_true")
    parser.add_argument("--operation-features", action="store_true")
    parser.add_argument("--route-target-loss-weight", type=float, default=0.0)
    parser.add_argument("--route-target-mode", choices=("all11", "binding9", "binary6"), default="all11")
    parser.add_argument("--atomic-slot-target-loss-weight", type=float, default=0.0)
    parser.add_argument("--atomic-binary-target-loss-weight", type=float, default=0.0)
    parser.add_argument("--atomic-hard-negative-margin-weight", type=float, default=0.0)
    parser.add_argument("--atomic-hard-negative-margin", type=float, default=1.0)
    parser.add_argument("--atomic-partition-score-loss-weight", type=float, default=0.0)
    parser.add_argument("--predicted-route-feedback", action="store_true")
    parser.add_argument("--predicted-atomic-feedback", action="store_true")
    parser.add_argument("--operation-conditioned-scorer", action="store_true")
    parser.add_argument("--operation-loss-weights", default="")
    parser.add_argument("--route-pretrain-steps", type=int, default=0)
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--rows-per-step", type=int, default=128)
    parser.add_argument("--max-candidates-per-group", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--log-every", type=int, default=100)
    parser.add_argument("--seed", type=int, default=791)
    parser.add_argument("--max-failures", type=int, default=20)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-ranker", default="")
    args = parser.parse_args()
    summary = train(args)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

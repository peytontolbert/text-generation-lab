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


TARGET_OPS = {
    "atomic_fact",
    "relation",
    "composition",
    "counterfactual_false_claim",
    "exception",
}
TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9_]*\b|\b\d+\b")
ENTITY_RE = re.compile(r"^gdom_\d+_e\d+$")
VALUE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*_v\d+$")
TOKEN_TYPES = ("general", "entity", "slot", "claim", "pair")
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
        if row.get("task_type") == "active_agent_direct_answer"
        and str(row.get("operation", "") or "") in TARGET_OPS
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


def _unique_docs(rows: list[dict[str, Any]]) -> tuple[list[str], dict[str, int], dict[str, list[int]], dict[str, dict[str, Any]]]:
    docs: list[str] = []
    doc_to_index: dict[str, int] = {}
    groups: dict[str, list[int]] = {}
    doc_to_row: dict[str, dict[str, Any]] = {}
    for row in rows:
        doc = str(row.get("retrieval_doc_text", "") or "").strip()
        if not doc:
            continue
        index = doc_to_index.get(doc)
        if index is None:
            index = len(docs)
            doc_to_index[doc] = index
            docs.append(doc)
            doc_to_row[doc] = row
        key = _collision_key(row)
        groups.setdefault(key, [])
        if index not in groups[key]:
            groups[key].append(index)
    return docs, doc_to_index, groups, doc_to_row


def _binding(row: dict[str, Any]) -> dict[str, Any]:
    binding = row.get("stage819_hardened_binding") or {}
    return binding if isinstance(binding, dict) else {}


def _originals(row: dict[str, Any], side: str, kind: str) -> set[str]:
    aliases = _binding(row).get(f"{side}_aliases") or {}
    if not isinstance(aliases, dict):
        return set()
    originals = set(str(original) for original in aliases)
    if kind == "all":
        return originals
    if kind == "entity":
        return {value for value in originals if ENTITY_RE.match(value)}
    if kind == "value":
        return {value for value in originals if VALUE_RE.match(value)}
    if kind == "slot":
        return {value for value in originals if not ENTITY_RE.match(value) and not VALUE_RE.match(value)}
    raise ValueError(f"unknown kind: {kind}")


def _teacher_partition(row: dict[str, Any], candidate_row: dict[str, Any]) -> bool:
    operation = str(row.get("operation", "") or "")
    entity_match = _teacher_entity_partition(row, candidate_row)
    if operation in {"atomic_fact", "counterfactual_false_claim"}:
        return entity_match and _teacher_slot_partition(row, candidate_row)
    if operation in {"composition", "relation", "exception"}:
        return entity_match
    return True


def _teacher_entity_partition(row: dict[str, Any], candidate_row: dict[str, Any]) -> bool:
    query_entity = _originals(row, "query", "entity")
    doc_entity = _originals(candidate_row, "doc", "entity")
    return bool(query_entity and query_entity & doc_entity)


def _teacher_slot_partition(row: dict[str, Any], candidate_row: dict[str, Any]) -> bool:
    query_slot = _originals(row, "query", "slot")
    doc_slot = _originals(candidate_row, "doc", "slot")
    return bool(query_slot and query_slot & doc_slot)


def _tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for token in TOKEN_RE.findall(str(text or "")):
        lowered = token.lower()
        if lowered in STOP_TOKENS or lowered.startswith("ak_op_"):
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


def _normalize_side_prefix(token: str) -> str:
    lowered = str(token).lower()
    replacements = (
        ("qent_", "ent_"),
        ("dent_", "ent_"),
        ("qslot_", "slot_"),
        ("dslot_", "slot_"),
        ("qclaim_", "claim_"),
        ("dclaim_", "claim_"),
        ("qpair_", "pair_"),
        ("dpair_", "pair_"),
    )
    for prefix, replacement in replacements:
        if lowered.startswith(prefix):
            return replacement + lowered[len(prefix) :]
    return lowered


def _hash_token(token: str, buckets: int, *, namespace: str) -> int:
    digest = hashlib.blake2b(f"{namespace}|{token}".encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "little") % int(buckets)


def _bag(tokens: list[str], buckets: int, *, normalize_side_prefixes: bool = False) -> torch.Tensor:
    type_to_index = {token_type: index for index, token_type in enumerate(TOKEN_TYPES)}
    vector = torch.zeros(int(buckets) * len(TOKEN_TYPES), dtype=torch.float32)
    for token in tokens:
        token_type = _token_type(token)
        if normalize_side_prefixes:
            token = _normalize_side_prefix(token)
        offset = type_to_index[token_type] * int(buckets)
        vector[offset + _hash_token(token, int(buckets), namespace=token_type)] += 1.0
    total = vector.sum().clamp_min(1.0)
    return vector / total


def _make_matrices(rows: list[dict[str, Any]], docs: list[str], buckets: int, *, normalize_side_prefixes: bool = False) -> tuple[torch.Tensor, torch.Tensor]:
    query = torch.stack([
        _bag(_tokens(str(row.get("retrieval_query_text", "") or row.get("encoder_text", ""))), buckets, normalize_side_prefixes=normalize_side_prefixes)
        for row in rows
    ])
    doc = torch.stack([_bag(_tokens(doc_text), buckets, normalize_side_prefixes=normalize_side_prefixes) for doc_text in docs])
    return query, doc


def _training_group(row: dict[str, Any], group: list[int], doc_to_index: dict[str, int], max_candidates: int) -> list[int]:
    if int(max_candidates) <= 0 or len(group) <= int(max_candidates):
        return group
    gold_index = doc_to_index[str(row.get("retrieval_doc_text", "") or "").strip()]
    candidates = [index for index in group if index != gold_index]
    sampled = random.sample(candidates, k=min(len(candidates), int(max_candidates) - 1))
    return [gold_index, *sampled]


class PartitionPredictor(torch.nn.Module):
    def __init__(
        self,
        input_dim: int,
        hash_dim: int,
        operations: list[str],
        hidden_dim: int,
        *,
        typed_slot_heads: bool = False,
        typed_role_heads: bool = False,
        role_mix_alpha: float = 1.0,
        role_rerank_beta: float = 0.0,
    ) -> None:
        super().__init__()
        self.typed_slot_heads = bool(typed_slot_heads)
        self.typed_role_heads = bool(typed_role_heads)
        self.role_mix_alpha = float(role_mix_alpha)
        self.role_rerank_beta = float(role_rerank_beta)
        self.query_embed = torch.nn.Linear(int(input_dim), int(hash_dim), bias=False)
        self.doc_embed = torch.nn.Linear(int(input_dim), int(hash_dim), bias=False)
        self.operation_to_index = {operation: index for index, operation in enumerate(operations)}
        feature_dim = int(hash_dim) * 4 + 1 + len(operations)
        self.scorer = torch.nn.Sequential(
            torch.nn.Linear(feature_dim, int(hidden_dim)),
            torch.nn.GELU(),
            torch.nn.Linear(int(hidden_dim), 1),
        )
        if self.typed_slot_heads:
            self.entity_scorer = torch.nn.Sequential(
                torch.nn.Linear(feature_dim, int(hidden_dim)),
                torch.nn.GELU(),
                torch.nn.Linear(int(hidden_dim), 1),
            )
            self.slot_scorer = torch.nn.Sequential(
                torch.nn.Linear(feature_dim, int(hidden_dim)),
                torch.nn.GELU(),
                torch.nn.Linear(int(hidden_dim), 1),
            )
        if self.typed_slot_heads and self.typed_role_heads:
            self.role_scorer = torch.nn.Sequential(
                torch.nn.Linear(feature_dim, int(hidden_dim)),
                torch.nn.GELU(),
                torch.nn.Linear(int(hidden_dim), 1),
            )
        for module in self.modules():
            if isinstance(module, torch.nn.Linear):
                torch.nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    torch.nn.init.zeros_(module.bias)

    def _features(self, query_bag: torch.Tensor, doc_bags: torch.Tensor, operation: str) -> torch.Tensor:
        query_vec = self.query_embed(query_bag)
        doc_vecs = self.doc_embed(doc_bags)
        query_expanded = query_vec.unsqueeze(0).expand_as(doc_vecs)
        dot = (query_expanded * doc_vecs).sum(dim=-1, keepdim=True)
        op = torch.zeros((doc_bags.shape[0], len(self.operation_to_index)), dtype=doc_bags.dtype, device=doc_bags.device)
        op[:, self.operation_to_index[str(operation)]] = 1.0
        return torch.cat([query_expanded, doc_vecs, query_expanded * doc_vecs, (query_expanded - doc_vecs).abs(), dot, op], dim=-1)

    def forward(self, query_bag: torch.Tensor, doc_bags: torch.Tensor, operation: str) -> torch.Tensor:
        return self.scorer(self._features(query_bag, doc_bags, operation)).squeeze(-1)

    def forward_typed(self, query_bag: torch.Tensor, doc_bags: torch.Tensor, operation: str) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        if not self.typed_slot_heads:
            raise RuntimeError("typed slot heads are disabled")
        features = self._features(query_bag, doc_bags, operation)
        entity_logits = self.entity_scorer(features).squeeze(-1)
        slot_logits = self.slot_scorer(features).squeeze(-1)
        if self.typed_role_heads:
            role_logits = self.role_scorer(features).squeeze(-1)
        else:
            role_logits = torch.zeros_like(slot_logits)
        return entity_logits, slot_logits, role_logits


def _partition_probabilities(predictor: PartitionPredictor, query_bag: torch.Tensor, doc_bags: torch.Tensor, operation: str) -> torch.Tensor:
    if not predictor.typed_slot_heads:
        return torch.sigmoid(predictor(query_bag, doc_bags, operation))
    entity_logits, slot_logits, role_logits = predictor.forward_typed(query_bag, doc_bags, operation)
    entity_probs = torch.sigmoid(entity_logits)
    slot_probs = torch.sigmoid(slot_logits)
    if operation in {"atomic_fact", "counterfactual_false_claim"}:
        return entity_probs * slot_probs
    if operation in {"composition", "relation"} and predictor.typed_role_heads:
        role_probs = torch.sigmoid(role_logits)
        alpha = float(predictor.role_mix_alpha)
        return entity_probs * ((1.0 - alpha) + alpha * role_probs)
    return entity_probs


def _role_rerank_probabilities(predictor: PartitionPredictor, query_bag: torch.Tensor, doc_bags: torch.Tensor, operation: str) -> torch.Tensor | None:
    if not predictor.typed_slot_heads or not predictor.typed_role_heads or operation not in {"composition", "relation"}:
        return None
    _entity_logits, _slot_logits, role_logits = predictor.forward_typed(query_bag, doc_bags, operation)
    return torch.sigmoid(role_logits)


def _embed_queries(retrieval_eval, model, tokenizer, rows: list[dict[str, Any]], *, max_tokens: int, batch_size: int, device: torch.device) -> torch.Tensor:
    chunks: list[torch.Tensor] = []
    with torch.no_grad():
        for offset in range(0, len(rows), int(batch_size)):
            texts = [str(row.get("retrieval_query_text", "") or row.get("encoder_text", "") or "") for row in rows[offset : offset + int(batch_size)]]
            chunks.append(retrieval_eval._embed_query(model, tokenizer, texts, max_tokens=int(max_tokens), device=device).detach().float().cpu())
    return torch.cat(chunks, dim=0)


def _embed_docs(retrieval_eval, model, tokenizer, docs: list[str], *, max_tokens: int, batch_size: int, device: torch.device) -> torch.Tensor:
    chunks: list[torch.Tensor] = []
    with torch.no_grad():
        for offset in range(0, len(docs), int(batch_size)):
            chunks.append(retrieval_eval._embed_doc(model, tokenizer, docs[offset : offset + int(batch_size)], max_tokens=int(max_tokens), device=device).detach().float().cpu())
    return torch.cat(chunks, dim=0)


def _doc_matches_expected(expected: str, doc: str) -> bool:
    return bool(expected and expected in doc)


def _evaluate(
    predictor: PartitionPredictor,
    rows: list[dict[str, Any]],
    docs: list[str],
    doc_to_index: dict[str, int],
    groups: dict[str, list[int]],
    doc_to_row: dict[str, dict[str, Any]],
    query_bags: torch.Tensor,
    doc_bags: torch.Tensor,
    frozen_queries: torch.Tensor,
    frozen_docs: torch.Tensor,
    thresholds: list[float],
    device: torch.device,
) -> dict[str, Any]:
    predictor.eval()
    results: dict[str, dict[str, Any]] = {
        str(threshold): {"examples": len(rows), "answer_correct": 0, "exact_correct": 0, "mrr": 0.0, "positive_coverage": 0, "mean_partition_size": 0.0, "by_operation": {}}
        for threshold in thresholds
    }
    with torch.no_grad():
        for row_index, row in enumerate(rows):
            operation = str(row.get("operation", "") or "unknown")
            group = groups[_collision_key(row)]
            label_index = doc_to_index[str(row.get("retrieval_doc_text", "") or "").strip()]
            label = group.index(label_index)
            query_bag = query_bags[row_index].to(device)
            doc_group_bags = doc_bags[group].to(device)
            probs = _partition_probabilities(predictor, query_bag, doc_group_bags, operation).detach().cpu()
            role_rerank = _role_rerank_probabilities(predictor, query_bag, doc_group_bags, operation)
            role_rerank_cpu = role_rerank.detach().cpu() if role_rerank is not None else None
            base_scores = (frozen_queries[row_index].unsqueeze(0) * frozen_docs[group]).sum(dim=-1).detach().cpu()
            if role_rerank_cpu is not None and float(predictor.role_rerank_beta) != 0.0:
                base_scores = base_scores + float(predictor.role_rerank_beta) * role_rerank_cpu
            teacher_positive = [_teacher_partition(row, doc_to_row[docs[index]]) for index in group]
            expected = str(row.get("expected_content", "") or "")
            for threshold in thresholds:
                selected = [i for i, prob in enumerate(probs.tolist()) if prob >= float(threshold)]
                if not selected:
                    selected = [int(torch.argmax(probs).item())]
                partition_label_present = label in selected
                scores = base_scores[selected]
                order = torch.argsort(scores, descending=True).tolist()
                pred_local = int(order[0])
                pred_group_offset = selected[pred_local]
                rank = selected.index(label) + 1 if partition_label_present else len(selected) + 1
                if partition_label_present:
                    ranked = [selected[index] for index in order]
                    rank = ranked.index(label) + 1
                bucket = results[str(threshold)]
                bucket["mean_partition_size"] += len(selected)
                if partition_label_present:
                    bucket["positive_coverage"] += 1
                bucket["mrr"] += 1.0 / float(rank)
                op_stats = bucket["by_operation"].setdefault(operation, {"examples": 0, "answer_correct": 0, "exact_correct": 0, "mrr": 0.0, "positive_coverage": 0})
                op_stats["examples"] += 1
                op_stats["mrr"] += 1.0 / float(rank)
                if partition_label_present:
                    op_stats["positive_coverage"] += 1
                predicted_doc = docs[group[pred_group_offset]]
                if pred_group_offset == label:
                    bucket["exact_correct"] += 1
                    op_stats["exact_correct"] += 1
                if pred_group_offset == label or _doc_matches_expected(expected, predicted_doc):
                    bucket["answer_correct"] += 1
                    op_stats["answer_correct"] += 1
    for bucket in results.values():
        total = float(bucket["examples"] or 1)
        bucket["mrr"] /= total
        bucket["mean_partition_size"] /= total
        for stats in bucket["by_operation"].values():
            stats["mrr"] /= float(stats["examples"] or 1)
    best_answer_threshold = max(results, key=lambda key: (results[key]["answer_correct"], results[key]["exact_correct"]))
    best_exact_threshold = max(results, key=lambda key: (results[key]["exact_correct"], results[key]["answer_correct"]))
    return {
        "thresholds": results,
        "best_answer_threshold": best_answer_threshold,
        "best_answer": results[best_answer_threshold],
        "best_exact_threshold": best_exact_threshold,
        "best_exact": results[best_exact_threshold],
    }


def _materialize_partitions(
    predictor: PartitionPredictor,
    rows: list[dict[str, Any]],
    docs: list[str],
    doc_to_index: dict[str, int],
    groups: dict[str, list[int]],
    query_bags: torch.Tensor,
    doc_bags: torch.Tensor,
    frozen_queries: torch.Tensor,
    frozen_docs: torch.Tensor,
    threshold: float,
    device: torch.device,
) -> list[dict[str, Any]]:
    predictor.eval()
    materialized: list[dict[str, Any]] = []
    with torch.no_grad():
        for row_index, row in enumerate(rows):
            operation = str(row.get("operation", "") or "unknown")
            group = groups[_collision_key(row)]
            label_index = doc_to_index[str(row.get("retrieval_doc_text", "") or "").strip()]
            label = group.index(label_index)
            query_bag = query_bags[row_index].to(device)
            doc_group_bags = doc_bags[group].to(device)
            probs = _partition_probabilities(predictor, query_bag, doc_group_bags, operation).detach().cpu()
            selected = [i for i, prob in enumerate(probs.tolist()) if prob >= float(threshold)]
            if not selected:
                selected = [int(torch.argmax(probs).item())]
            base_scores = (frozen_queries[row_index].unsqueeze(0) * frozen_docs[group]).sum(dim=-1).detach().cpu()
            candidates: list[dict[str, Any]] = []
            for group_offset in selected:
                doc_index = group[group_offset]
                doc_text = docs[doc_index]
                candidates.append(
                    {
                        "base_score": float(base_scores[group_offset].item()),
                        "doc_index": int(doc_index),
                        "group_offset": int(group_offset),
                        "is_answer_match": _doc_matches_expected(str(row.get("expected_content", "") or ""), doc_text),
                        "is_exact": bool(group_offset == label),
                        "partition_probability": float(probs[group_offset].item()),
                    }
                )
            candidates.sort(key=lambda item: item["base_score"], reverse=True)
            materialized.append(
                {
                    "collision_key": _collision_key(row),
                    "expected_content": str(row.get("expected_content", "") or ""),
                    "label_group_offset": int(label),
                    "operation": operation,
                    "partition_label_present": bool(label in selected),
                    "query_index": int(row_index),
                    "selected_count": len(selected),
                    "top_candidate_exact": bool(candidates and candidates[0]["is_exact"]),
                    "top_candidate_answer_match": bool(candidates and (candidates[0]["is_exact"] or candidates[0]["is_answer_match"])),
                    "unit_id": str(row.get("unit_id", "") or ""),
                    "candidates": candidates,
                }
            )
    return materialized


def train(args: argparse.Namespace) -> dict[str, Any]:
    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    device = torch.device(str(args.device))
    manifest = json.loads(Path(args.dataset_manifest).read_text(encoding="utf-8"))
    train_rows = _direct_rows(_iter_jsonl(Path(manifest["train_dataset_path"])))
    eval_rows = _direct_rows(_iter_jsonl(Path(manifest["eval_dataset_path"])))
    calibration_path = manifest.get("calibration_dataset_path")
    calibration_rows = _direct_rows(_iter_jsonl(Path(calibration_path))) if calibration_path else []
    train_docs, train_doc_to_index, train_groups, train_doc_to_row = _unique_docs(train_rows)
    eval_docs, eval_doc_to_index, eval_groups, eval_doc_to_row = _unique_docs(eval_rows)
    calibration_docs, calibration_doc_to_index, calibration_groups, calibration_doc_to_row = _unique_docs(calibration_rows)
    input_dim = int(args.hash_buckets) * len(TOKEN_TYPES)
    train_q, train_d = _make_matrices(train_rows, train_docs, int(args.hash_buckets), normalize_side_prefixes=bool(args.normalize_side_prefixes))
    eval_q, eval_d = _make_matrices(eval_rows, eval_docs, int(args.hash_buckets), normalize_side_prefixes=bool(args.normalize_side_prefixes))
    calibration_q, calibration_d = _make_matrices(calibration_rows, calibration_docs, int(args.hash_buckets), normalize_side_prefixes=bool(args.normalize_side_prefixes)) if calibration_rows else (torch.empty((0, input_dim)), torch.empty((0, input_dim)))
    operations = sorted({str(row.get("operation", "") or "unknown") for row in [*train_rows, *eval_rows, *calibration_rows]})
    predictor = PartitionPredictor(
        input_dim,
        int(args.hash_dim),
        operations,
        int(args.hidden_dim),
        typed_slot_heads=bool(args.typed_slot_heads),
        typed_role_heads=bool(args.typed_role_heads),
        role_mix_alpha=float(args.role_mix_alpha),
        role_rerank_beta=float(args.role_rerank_beta),
    ).to(device)
    optimizer = torch.optim.AdamW(predictor.parameters(), lr=float(args.learning_rate), weight_decay=float(args.weight_decay))
    order = list(range(len(train_rows)))
    history: list[dict[str, Any]] = []
    for step in range(1, int(args.steps) + 1):
        random.shuffle(order)
        losses: list[torch.Tensor] = []
        predictor.train()
        for row_index in order[: int(args.rows_per_step)]:
            row = train_rows[row_index]
            group = _training_group(row, train_groups[_collision_key(row)], train_doc_to_index, int(args.max_train_candidates))
            operation = str(row.get("operation", "") or "unknown")
            if predictor.typed_slot_heads:
                entity_labels = torch.tensor(
                    [1.0 if _teacher_entity_partition(row, train_doc_to_row[train_docs[index]]) else 0.0 for index in group],
                    dtype=torch.float32,
                    device=device,
                )
                slot_labels = torch.tensor(
                    [1.0 if _teacher_slot_partition(row, train_doc_to_row[train_docs[index]]) else 0.0 for index in group],
                    dtype=torch.float32,
                    device=device,
                )
                query_bag = train_q[row_index].to(device)
                doc_group_bags = train_d[group].to(device)
                entity_logits, slot_logits, role_logits = predictor.forward_typed(query_bag, doc_group_bags, operation)
                entity_weight = (entity_labels.numel() - entity_labels.sum()).clamp_min(1.0) / entity_labels.sum().clamp_min(1.0)
                slot_weight = (slot_labels.numel() - slot_labels.sum()).clamp_min(1.0) / slot_labels.sum().clamp_min(1.0)
                typed_loss = F.binary_cross_entropy_with_logits(entity_logits, entity_labels, pos_weight=entity_weight)
                if operation in {"atomic_fact", "counterfactual_false_claim"}:
                    typed_loss = typed_loss + F.binary_cross_entropy_with_logits(slot_logits, slot_labels, pos_weight=slot_weight)
                if predictor.typed_role_heads and operation in {"composition", "relation"}:
                    if bool(args.detach_role_loss):
                        role_features = predictor._features(query_bag, doc_group_bags, operation).detach()
                        role_logits = predictor.role_scorer(role_features).squeeze(-1)
                    typed_loss = typed_loss + F.binary_cross_entropy_with_logits(role_logits, slot_labels, pos_weight=slot_weight)
                losses.append(typed_loss)
            else:
                labels = torch.tensor(
                    [1.0 if _teacher_partition(row, train_doc_to_row[train_docs[index]]) else 0.0 for index in group],
                    dtype=torch.float32,
                    device=device,
                )
                logits = predictor(train_q[row_index].to(device), train_d[group].to(device), operation)
                positive_weight = (labels.numel() - labels.sum()).clamp_min(1.0) / labels.sum().clamp_min(1.0)
                losses.append(F.binary_cross_entropy_with_logits(logits, labels, pos_weight=positive_weight))
        loss = torch.stack(losses).mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % int(args.log_every) == 0:
            history.append({"step": step, "loss": float(loss.detach().cpu().item())})
    repo_root = Path(args.repo_root).resolve()
    retrieval_eval = _load_retrieval_eval(repo_root)
    frozen_model, tokenizer, _manifest = retrieval_eval._load_model(Path(args.bundle_dir).resolve(), repo_root=repo_root, device=device)
    frozen_model.eval()
    for parameter in frozen_model.parameters():
        parameter.requires_grad_(False)
    frozen_train_q = _embed_queries(retrieval_eval, frozen_model, tokenizer, train_rows, max_tokens=int(args.max_query_tokens), batch_size=int(args.embed_batch_size), device=device)
    frozen_train_d = _embed_docs(retrieval_eval, frozen_model, tokenizer, train_docs, max_tokens=int(args.max_doc_tokens), batch_size=int(args.embed_batch_size), device=device)
    frozen_calibration_q = _embed_queries(retrieval_eval, frozen_model, tokenizer, calibration_rows, max_tokens=int(args.max_query_tokens), batch_size=int(args.embed_batch_size), device=device) if calibration_rows else torch.empty((0, frozen_train_q.shape[-1]))
    frozen_calibration_d = _embed_docs(retrieval_eval, frozen_model, tokenizer, calibration_docs, max_tokens=int(args.max_doc_tokens), batch_size=int(args.embed_batch_size), device=device) if calibration_docs else torch.empty((0, frozen_train_d.shape[-1]))
    frozen_eval_q = _embed_queries(retrieval_eval, frozen_model, tokenizer, eval_rows, max_tokens=int(args.max_query_tokens), batch_size=int(args.embed_batch_size), device=device)
    frozen_eval_d = _embed_docs(retrieval_eval, frozen_model, tokenizer, eval_docs, max_tokens=int(args.max_doc_tokens), batch_size=int(args.embed_batch_size), device=device)
    thresholds = [float(value) for value in str(args.thresholds).split(",") if value.strip()]
    train_eval = _evaluate(predictor, train_rows, train_docs, train_doc_to_index, train_groups, train_doc_to_row, train_q, train_d, frozen_train_q, frozen_train_d, thresholds, device)
    calibration_eval = _evaluate(predictor, calibration_rows, calibration_docs, calibration_doc_to_index, calibration_groups, calibration_doc_to_row, calibration_q, calibration_d, frozen_calibration_q, frozen_calibration_d, thresholds, device) if calibration_rows else None
    eval_eval = _evaluate(predictor, eval_rows, eval_docs, eval_doc_to_index, eval_groups, eval_doc_to_row, eval_q, eval_d, frozen_eval_q, frozen_eval_d, thresholds, device)
    if str(args.selection_split) == "calibration":
        if calibration_eval is None:
            raise ValueError("selection_split=calibration requested, but manifest has no calibration_dataset_path")
        selected_threshold = calibration_eval["best_answer_threshold"]
    else:
        selected_threshold = train_eval["best_answer_threshold"]
    summary = {
        "artifact_kind": "stage850_partition_predictor_eval",
        "dataset_manifest": str(Path(args.dataset_manifest).resolve()),
        "bundle_dir": str(Path(args.bundle_dir).resolve()),
        "train_examples": len(train_rows),
        "calibration_examples": len(calibration_rows),
        "eval_examples": len(eval_rows),
        "train_candidate_docs": len(train_docs),
        "calibration_candidate_docs": len(calibration_docs),
        "eval_candidate_docs": len(eval_docs),
        "operations": operations,
        "thresholds": thresholds,
        "selection_split": str(args.selection_split),
        "selected_threshold": selected_threshold,
        "train_at_selected_threshold": train_eval["thresholds"][selected_threshold],
        "calibration_at_selected_threshold": calibration_eval["thresholds"][selected_threshold] if calibration_eval is not None else None,
        "eval_at_selected_threshold": eval_eval["thresholds"][selected_threshold],
        "train": train_eval,
        "calibration": calibration_eval,
        "eval": eval_eval,
        "parameter_count": sum(parameter.numel() for parameter in predictor.parameters()),
        "typed_slot_heads": bool(args.typed_slot_heads),
        "typed_role_heads": bool(args.typed_role_heads),
        "role_mix_alpha": float(args.role_mix_alpha),
        "role_rerank_beta": float(args.role_rerank_beta),
        "detach_role_loss": bool(args.detach_role_loss),
        "normalize_side_prefixes": bool(args.normalize_side_prefixes),
        "history": history,
        "decision_hint": "Accepted only if eval_at_selected_threshold improves held-out alias target rows without metadata at eval.",
    }
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.output_partitions_json:
        partition_output = Path(args.output_partitions_json)
        partition_output.parent.mkdir(parents=True, exist_ok=True)
        selected_threshold_float = float(selected_threshold)
        partitions = {
            "artifact_kind": "stage859_frozen_partition_dataset",
            "dataset_manifest": str(Path(args.dataset_manifest).resolve()),
            "source_eval_json": str(output.resolve()),
            "selected_threshold": selected_threshold,
            "selection_split": str(args.selection_split),
            "train": _materialize_partitions(
                predictor,
                train_rows,
                train_docs,
                train_doc_to_index,
                train_groups,
                train_q,
                train_d,
                frozen_train_q,
                frozen_train_d,
                selected_threshold_float,
                device,
            ),
            "calibration": _materialize_partitions(
                predictor,
                calibration_rows,
                calibration_docs,
                calibration_doc_to_index,
                calibration_groups,
                calibration_q,
                calibration_d,
                frozen_calibration_q,
                frozen_calibration_d,
                selected_threshold_float,
                device,
            ) if calibration_rows else [],
            "eval": _materialize_partitions(
                predictor,
                eval_rows,
                eval_docs,
                eval_doc_to_index,
                eval_groups,
                eval_q,
                eval_d,
                frozen_eval_q,
                frozen_eval_d,
                selected_threshold_float,
                device,
            ),
        }
        partition_output.write_text(json.dumps(partitions, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(_repo_root()))
    parser.add_argument("--dataset-manifest", required=True)
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--hash-buckets", type=int, default=512)
    parser.add_argument("--hash-dim", type=int, default=32)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--typed-slot-heads", action="store_true")
    parser.add_argument("--typed-role-heads", action="store_true")
    parser.add_argument("--role-mix-alpha", type=float, default=1.0)
    parser.add_argument("--role-rerank-beta", type=float, default=0.0)
    parser.add_argument("--detach-role-loss", action="store_true")
    parser.add_argument("--normalize-side-prefixes", action="store_true")
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--rows-per-step", type=int, default=128)
    parser.add_argument("--max-train-candidates", type=int, default=0)
    parser.add_argument("--learning-rate", type=float, default=0.002)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--thresholds", default="0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9")
    parser.add_argument("--selection-split", choices=["train", "calibration"], default="train")
    parser.add_argument("--max-query-tokens", type=int, default=128)
    parser.add_argument("--max-doc-tokens", type=int, default=256)
    parser.add_argument("--embed-batch-size", type=int, default=128)
    parser.add_argument("--seed", type=int, default=850)
    parser.add_argument("--log-every", type=int, default=100)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-partitions-json", default="")
    train(parser.parse_args())


if __name__ == "__main__":
    main()

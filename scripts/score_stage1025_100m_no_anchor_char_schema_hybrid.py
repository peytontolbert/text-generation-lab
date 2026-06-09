#!/usr/bin/env python3
"""Score a loadable 100M bundle plus no-anchor learned char schema equality."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import torch

ENTITY_RE = re.compile(r"\b(?:qent|dent|entity)_([A-Za-z0-9]+)\b")
SLOT_RE = re.compile(r"\b(?:qslot|dslot|slot)_([A-Za-z0-9]+)\b")
STATEMENT_ENTITY_RE = re.compile(r"\bstatement=(?:claim\s+)?dent_([A-Za-z0-9]+)\b")
DEFAULT_KIND_RE = re.compile(r"\bdefault\s+([A-Za-z0-9]+)\b")
ANSWER_KIND_RE = re.compile(r"\banswer=([A-Za-z0-9]+)_v[0-9A-Za-z]+\b")
DEFAULT_POLICY_RE = re.compile(r"\bstatement=default\s+([A-Za-z0-9]+)\s+policy\b")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _candidate_hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _base_order(candidates: list[dict[str, Any]]) -> list[int]:
    return sorted(
        range(len(candidates)),
        key=lambda idx: (-float(candidates[idx].get("base_score", 0.0) or 0.0), int(candidates[idx].get("rank", idx + 1) or idx + 1), idx),
    )


def _label_index(candidates: list[dict[str, Any]]) -> int:
    for index, candidate in enumerate(candidates):
        if candidate.get("is_exact"):
            return index
    for index, candidate in enumerate(candidates):
        if candidate.get("is_answer_match"):
            return index
    return -1


def _score_pair_interface_row(
    *,
    row: dict[str, Any],
    pair_module,
    pair_router,
    selected_arities: dict[str, int],
    threshold: float,
    fallback_to_base: bool,
    device: torch.device,
) -> tuple[int | None, str]:
    candidates = list(row.get("candidates", []) or [])
    if not candidates:
        return None, "missing"
    operation = str(row.get("operation", "") or "")
    qpair = (row.get("query_bridge", {}) or {}).get("qpair", [])
    selected_arity = int(selected_arities.get(operation, 0))
    predicted: list[int] = []
    with torch.no_grad():
        pair_router.eval()
        for index, candidate in enumerate(candidates):
            bridge = candidate.get("bridge", {}) or {}
            pair_overlap_count = pair_module.suffix_overlap(qpair, bridge.get("dpair", []))
            features = pair_router.features(
                operation=operation,
                pair_overlap_count=int(pair_overlap_count),
                selected_min_pair_overlap=selected_arity,
                base_score=float(candidate.get("base_score", 0.0) or 0.0),
                rank=int(candidate.get("rank", 9999) or 9999),
                device=device,
            )
            if torch.sigmoid(pair_router.logit(features)).item() >= float(threshold):
                predicted.append(index)
    if predicted:
        pool = predicted
        policy_detail = "pair_interface"
    elif fallback_to_base:
        pool = list(range(len(candidates)))
        policy_detail = "pair_interface_fallback_base"
    else:
        return None, "pair_interface_missing"
    top = max(
        pool,
        key=lambda idx: (float(candidates[idx].get("base_score", 0.0) or 0.0), -int(candidates[idx].get("rank", 9999) or 9999), -idx),
    )
    return int(top), policy_detail


def _match_count(*, model, feature_fn, q_values: list[str], d_values: list[str], threshold: float, device: torch.device) -> int:
    count = 0
    model.eval()
    with torch.no_grad():
        for q_value in q_values:
            matched = False
            for d_value in d_values:
                features = feature_fn(q_value, d_value).to(device).unsqueeze(0)
                prob = torch.sigmoid(model(features)).item()
                matched = matched or float(prob) >= float(threshold)
            count += int(matched)
    return count


def _score_schema_equality_row(
    *,
    row: dict[str, Any],
    entity_model,
    slot_model,
    feature_fn,
    selected_policy: dict[str, tuple[int, int]],
    entity_threshold: float,
    slot_threshold: float,
    fallback_to_base: bool,
    device: torch.device,
) -> tuple[int | None, str]:
    candidates = list(row.get("candidates", []) or [])
    if not candidates:
        return None, "missing"
    operation = str(row.get("operation", "") or "")
    ent_min, slot_min = selected_policy.get(operation, (0, 0))
    q_ent = ENTITY_RE.findall(str(row.get("query_text", "") or ""))
    q_slot = SLOT_RE.findall(str(row.get("query_text", "") or ""))
    pool: list[int] = []
    for index, candidate in enumerate(candidates):
        doc = str(candidate.get("doc_text", "") or "")
        ent_overlap = (
            _match_count(
                model=entity_model,
                feature_fn=feature_fn,
                q_values=q_ent,
                d_values=ENTITY_RE.findall(doc),
                threshold=entity_threshold,
                device=device,
            )
            if ent_min > 0
            else ent_min
        )
        slot_overlap = (
            _match_count(
                model=slot_model,
                feature_fn=feature_fn,
                q_values=q_slot,
                d_values=SLOT_RE.findall(doc),
                threshold=slot_threshold,
                device=device,
            )
            if slot_min > 0
            else slot_min
        )
        if ent_overlap >= ent_min and slot_overlap >= slot_min:
            pool.append(index)
    if pool:
        policy_detail = "learned_char_schema_equality"
    elif fallback_to_base:
        pool = list(range(len(candidates)))
        policy_detail = "learned_char_schema_equality_fallback_base"
    else:
        return None, "learned_char_schema_equality_missing"
    top = max(
        pool,
        key=lambda idx: (float(candidates[idx].get("base_score", 0.0) or 0.0), -int(candidates[idx].get("rank", 9999) or 9999), -idx),
    )
    return int(top), policy_detail


def _score_relation_source_schema_row(
    *,
    row: dict[str, Any],
    entity_model,
    slot_model,
    feature_fn,
    entity_threshold: float,
    slot_threshold: float,
    fallback_to_base: bool,
    device: torch.device,
) -> tuple[int | None, str]:
    candidates = list(row.get("candidates", []) or [])
    if not candidates:
        return None, "missing"
    q_ent = ENTITY_RE.findall(str(row.get("query_text", "") or ""))
    q_slot = SLOT_RE.findall(str(row.get("query_text", "") or ""))
    pool: list[int] = []
    for index, candidate in enumerate(candidates):
        doc = str(candidate.get("doc_text", "") or "")
        source_matches = _match_count(
            model=entity_model,
            feature_fn=feature_fn,
            q_values=q_ent,
            d_values=STATEMENT_ENTITY_RE.findall(doc),
            threshold=entity_threshold,
            device=device,
        )
        slot_matches = _match_count(
            model=slot_model,
            feature_fn=feature_fn,
            q_values=q_slot,
            d_values=SLOT_RE.findall(doc),
            threshold=slot_threshold,
            device=device,
        )
        if source_matches >= 1 and slot_matches >= 1:
            pool.append(index)
    if pool:
        policy_detail = "learned_char_relation_source_schema"
    elif fallback_to_base:
        pool = list(range(len(candidates)))
        policy_detail = "learned_char_relation_source_schema_fallback_base"
    else:
        return None, "learned_char_relation_source_schema_missing"
    top = max(
        pool,
        key=lambda idx: (float(candidates[idx].get("base_score", 0.0) or 0.0), -int(candidates[idx].get("rank", 9999) or 9999), -idx),
    )
    return int(top), policy_detail


def _score_counterfactual_source_schema_row(
    *,
    row: dict[str, Any],
    entity_model,
    slot_model,
    feature_fn,
    entity_threshold: float,
    slot_threshold: float,
    fallback_to_base: bool,
    device: torch.device,
) -> tuple[int | None, str]:
    candidates = list(row.get("candidates", []) or [])
    if not candidates:
        return None, "missing"
    q_ent = ENTITY_RE.findall(str(row.get("query_text", "") or ""))
    q_slot = SLOT_RE.findall(str(row.get("query_text", "") or ""))
    pool: list[int] = []
    for index, candidate in enumerate(candidates):
        doc = str(candidate.get("doc_text", "") or "")
        source_matches = _match_count(
            model=entity_model,
            feature_fn=feature_fn,
            q_values=q_ent,
            d_values=STATEMENT_ENTITY_RE.findall(doc),
            threshold=entity_threshold,
            device=device,
        )
        slot_matches = _match_count(
            model=slot_model,
            feature_fn=feature_fn,
            q_values=q_slot,
            d_values=SLOT_RE.findall(doc),
            threshold=slot_threshold,
            device=device,
        )
        if source_matches >= 1 and slot_matches >= 1:
            pool.append(index)
    if pool:
        policy_detail = "learned_char_counterfactual_source_schema"
    elif fallback_to_base:
        pool = list(range(len(candidates)))
        policy_detail = "learned_char_counterfactual_source_schema_fallback_base"
    else:
        return None, "learned_char_counterfactual_source_schema_missing"
    top = max(
        pool,
        key=lambda idx: (float(candidates[idx].get("base_score", 0.0) or 0.0), -int(candidates[idx].get("rank", 9999) or 9999), -idx),
    )
    return int(top), policy_detail


def _score_exception_source_kind_row(
    *,
    row: dict[str, Any],
    entity_model,
    feature_fn,
    entity_threshold: float,
    fallback_to_base: bool,
    device: torch.device,
) -> tuple[int | None, str]:
    candidates = list(row.get("candidates", []) or [])
    if not candidates:
        return None, "missing"
    query = str(row.get("query_text", "") or "")
    q_ent = ENTITY_RE.findall(query)
    default_kinds = set(DEFAULT_KIND_RE.findall(query))
    pool: list[int] = []
    for index, candidate in enumerate(candidates):
        doc = str(candidate.get("doc_text", "") or "")
        answer_kinds = set(ANSWER_KIND_RE.findall(doc))
        policy_kinds = set(DEFAULT_POLICY_RE.findall(doc))
        kind_matches = bool(default_kinds.intersection(answer_kinds)) if default_kinds else True
        if q_ent:
            source_matches = _match_count(
                model=entity_model,
                feature_fn=feature_fn,
                q_values=q_ent,
                d_values=STATEMENT_ENTITY_RE.findall(doc),
                threshold=entity_threshold,
                device=device,
            )
            structure_matches = source_matches >= 1
        else:
            structure_matches = bool(default_kinds.intersection(policy_kinds))
        if structure_matches and kind_matches:
            pool.append(index)
    if pool:
        policy_detail = "learned_char_exception_source_kind"
    elif fallback_to_base:
        pool = list(range(len(candidates)))
        policy_detail = "learned_char_exception_source_kind_fallback_base"
    else:
        return None, "learned_char_exception_source_kind_missing"
    top = max(
        pool,
        key=lambda idx: (float(candidates[idx].get("base_score", 0.0) or 0.0), -int(candidates[idx].get("rank", 9999) or 9999), -idx),
    )
    return int(top), policy_detail


def _score_model_blend_row(
    *,
    row_index: int,
    row: dict[str, Any],
    query_embeddings: torch.Tensor,
    doc_embeddings: torch.Tensor,
    doc_to_index: dict[str, int],
    alpha: float,
) -> int | None:
    candidates = list(row.get("candidates", []) or [])
    if not candidates:
        return None
    doc_indices = [doc_to_index[str(candidate.get("doc_text", "") or "")] for candidate in candidates]
    model_scores = torch.mv(doc_embeddings.index_select(0, torch.tensor(doc_indices, dtype=torch.long)), query_embeddings[row_index])
    base_scores = torch.tensor([float(candidate.get("base_score", 0.0) or 0.0) for candidate in candidates], dtype=torch.float32)
    scores = base_scores + float(alpha) * model_scores
    order = sorted(range(len(candidates)), key=lambda idx: (-float(scores[idx].item()), idx))
    return int(order[0])


def _score_split(
    *,
    rows: list[dict[str, Any]],
    policy_by_operation: dict[str, str],
    model_alpha: float,
    query_embeddings: torch.Tensor,
    doc_embeddings: torch.Tensor,
    doc_to_index: dict[str, int],
    pair_module,
    pair_router,
    entity_model,
    slot_model,
    feature_fn,
    selected_arities: dict[str, int],
    schema_policy: dict[str, tuple[int, int]],
    entity_threshold: float,
    slot_threshold: float,
    threshold: float,
    fallback_to_base: bool,
    device: torch.device,
    relation_source_role: bool,
    counterfactual_source_role: bool,
    exception_source_kind: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    answer = exact = base_answer = base_exact = recoverable_answer = recoverable_exact = 0
    mrr = 0.0
    by_operation: dict[str, dict[str, int]] = {}
    predictions: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        candidates = list(row.get("candidates", []) or [])
        if not candidates:
            continue
        operation = str(row.get("operation", "") or "")
        stats = by_operation.setdefault(operation, {"rows": 0, "answer": 0, "exact": 0, "base_answer": 0, "base_exact": 0})
        stats["rows"] += 1
        policy = policy_by_operation.get(operation, "base")
        if policy == "stage968_counted_pair_overlap":
            predicted_index, policy_detail = _score_pair_interface_row(
                row=row,
                pair_module=pair_module,
                pair_router=pair_router,
                selected_arities=selected_arities,
                threshold=threshold,
                fallback_to_base=fallback_to_base,
                device=device,
            )
        elif policy == "stage1024_learned_char_schema_equality" and relation_source_role and operation == "relation":
            predicted_index, policy_detail = _score_relation_source_schema_row(
                row=row,
                entity_model=entity_model,
                slot_model=slot_model,
                feature_fn=feature_fn,
                entity_threshold=entity_threshold,
                slot_threshold=slot_threshold,
                fallback_to_base=fallback_to_base,
                device=device,
            )
        elif policy == "stage1024_learned_char_schema_equality" and counterfactual_source_role and operation == "counterfactual_false_claim":
            predicted_index, policy_detail = _score_counterfactual_source_schema_row(
                row=row,
                entity_model=entity_model,
                slot_model=slot_model,
                feature_fn=feature_fn,
                entity_threshold=entity_threshold,
                slot_threshold=slot_threshold,
                fallback_to_base=fallback_to_base,
                device=device,
            )
        elif policy == "stage1024_learned_char_schema_equality" and exception_source_kind and operation == "exception":
            predicted_index, policy_detail = _score_exception_source_kind_row(
                row=row,
                entity_model=entity_model,
                feature_fn=feature_fn,
                entity_threshold=entity_threshold,
                fallback_to_base=fallback_to_base,
                device=device,
            )
        elif policy == "stage1024_learned_char_schema_equality":
            predicted_index, policy_detail = _score_schema_equality_row(
                row=row,
                entity_model=entity_model,
                slot_model=slot_model,
                feature_fn=feature_fn,
                selected_policy=schema_policy,
                entity_threshold=entity_threshold,
                slot_threshold=slot_threshold,
                fallback_to_base=fallback_to_base,
                device=device,
            )
        elif policy == "stage976_model_owned_blend":
            predicted_index = _score_model_blend_row(
                row_index=row_index,
                row=row,
                query_embeddings=query_embeddings,
                doc_embeddings=doc_embeddings,
                doc_to_index=doc_to_index,
                alpha=float(model_alpha),
            )
            policy_detail = "model_owned_blend"
        else:
            predicted_index = _base_order(candidates)[0]
            policy_detail = "base"
        if predicted_index is None:
            continue
        base_index = _base_order(candidates)[0]
        top = candidates[predicted_index]
        base_top = candidates[base_index]
        ans, ex = _candidate_hit(top)
        bans, bex = _candidate_hit(base_top)
        answer += ans
        exact += ex
        base_answer += bans
        base_exact += bex
        stats["answer"] += ans
        stats["exact"] += ex
        stats["base_answer"] += bans
        stats["base_exact"] += bex
        recoverable_answer += int(any(_candidate_hit(candidate)[0] for candidate in candidates))
        recoverable_exact += int(any(_candidate_hit(candidate)[1] for candidate in candidates))
        label = _label_index(candidates)
        rank = None
        if label >= 0:
            if policy == "stage976_model_owned_blend":
                doc_indices = [doc_to_index[str(candidate.get("doc_text", "") or "")] for candidate in candidates]
                model_scores = torch.mv(doc_embeddings.index_select(0, torch.tensor(doc_indices, dtype=torch.long)), query_embeddings[row_index])
                base_scores = torch.tensor([float(candidate.get("base_score", 0.0) or 0.0) for candidate in candidates], dtype=torch.float32)
                scores = base_scores + float(model_alpha) * model_scores
                order = sorted(range(len(candidates)), key=lambda idx: (-float(scores[idx].item()), idx))
            else:
                order = _base_order(candidates)
            rank = order.index(label) + 1 if label in order else None
            if rank is not None:
                mrr += 1.0 / float(rank)
        predictions.append(
            {
                "row_index": row_index,
                "operation": operation,
                "policy": policy,
                "policy_detail": policy_detail,
                "predicted_candidate_index": int(predicted_index),
                "base_candidate_index": int(base_index),
                "answer_hit": ans,
                "exact_hit": ex,
                "base_answer_hit": bans,
                "base_exact_hit": bex,
                "label_rank": rank,
            }
        )
    return (
        {
            "rows": len(rows),
            "answer": answer,
            "exact": exact,
            "base_answer": base_answer,
            "base_exact": base_exact,
            "recoverable_answer": recoverable_answer,
            "recoverable_exact": recoverable_exact,
            "mrr": mrr / float(len(rows) or 1),
            "by_operation": by_operation,
        },
        predictions,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", type=Path, default=Path("runs/local/artifacts/pocketpal_controller_100m_stage976_stage975_pair_teacher_loadable_v415"))
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1013_no_anchor_targets.jsonl"))
    parser.add_argument("--router-state", type=Path, default=Path("runs/local/artifacts/stage966_pair_arity_router_state.pt"))
    parser.add_argument("--policy-json", type=Path, default=Path("runs/local/artifacts/stage964_operation_pair_arity_policy_summary.json"))
    parser.add_argument("--char-state", type=Path, default=Path("runs/local/artifacts/stage1024_char_schema_equality_counted_state.pt"))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1025_100m_no_anchor_char_schema_hybrid_summary.json"))
    parser.add_argument("--predictions-jsonl", type=Path, default=Path("runs/local/artifacts/stage1025_100m_no_anchor_char_schema_hybrid_predictions.jsonl"))
    parser.add_argument("--artifact-kind", default="stage1025_100m_no_anchor_char_schema_hybrid")
    parser.add_argument("--status", default="completed_no_anchor_learned_char_schema_hybrid_scorer")
    parser.add_argument("--composition-policy", default="")
    parser.add_argument("--relation-policy", default="")
    parser.add_argument("--relation-source-role", action="store_true")
    parser.add_argument("--counterfactual-source-role", action="store_true")
    parser.add_argument("--exception-source-kind", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--query-batch-size", type=int, default=64)
    parser.add_argument("--doc-batch-size", type=int, default=64)
    parser.add_argument("--max-query-tokens", type=int, default=128)
    parser.add_argument("--max-doc-tokens", type=int, default=128)
    parser.add_argument("--model-alpha", type=float, default=0.75)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    stage974 = _load_module(repo_root / "scripts/score_stage974_model_owned_candidate_ranking.py", "stage974")
    stage968 = _load_module(repo_root / "scripts/score_stage968_loadable_pair_router.py", "stage968")
    stage1024 = _load_module(repo_root / "scripts/train_stage1023_char_schema_equality.py", "stage1024_char_eq")
    retrieval_eval = stage974.load_retrieval_eval(repo_root)
    device = torch.device(str(args.device))
    rows_by_split = stage974.rows_by_split(args.targets_jsonl)
    all_docs = stage974.unique_docs([row for split_rows in rows_by_split.values() for row in split_rows])
    doc_to_index = {doc: idx for idx, doc in enumerate(all_docs)}
    model, tokenizer, manifest = retrieval_eval._load_model(args.bundle_dir.resolve(), repo_root=repo_root, device=device)
    model.eval()
    doc_embeddings = stage974.encode_embeddings(
        retrieval_eval=retrieval_eval,
        tokenizer=tokenizer,
        model=model,
        texts=all_docs,
        side="doc",
        max_tokens=int(args.max_doc_tokens),
        batch_size=int(args.doc_batch_size),
        device=device,
    )
    query_embeddings = {
        split: stage974.encode_embeddings(
            retrieval_eval=retrieval_eval,
            tokenizer=tokenizer,
            model=model,
            texts=[str(row.get("query_text", "") or "") for row in rows],
            side="query",
            max_tokens=int(args.max_query_tokens),
            batch_size=int(args.query_batch_size),
            device=device,
        )
        for split, rows in rows_by_split.items()
    }

    state = torch.load(args.router_state, map_location=device)
    pair_router = stage968.PairArityRouter(list(state["operations"]), int(state["hidden_dim"])).to(device)
    pair_router.load_state_dict(state["state_dict"])
    char_state = torch.load(args.char_state, map_location=device)
    entity_model = stage1024.CharEq(int(char_state["dim"]), int(char_state["hidden_dim"])).to(device)
    slot_model = stage1024.CharEq(int(char_state["dim"]), int(char_state["hidden_dim"])).to(device)
    entity_model.load_state_dict(char_state["entity_model_state"])
    slot_model.load_state_dict(char_state["slot_model_state"])
    entity_model.eval()
    slot_model.eval()
    selected_arities = stage968.selected_arities_from_policy(args.policy_json)
    policy_by_operation = {
        "atomic_fact": "base",
        "composition": "stage1024_learned_char_schema_equality",
        "counterfactual_false_claim": "stage1024_learned_char_schema_equality" if bool(args.counterfactual_source_role) else "base",
        "exception": "stage1024_learned_char_schema_equality" if bool(args.exception_source_kind) else "stage976_model_owned_blend",
        "relation": "stage1024_learned_char_schema_equality",
    }
    schema_policy = {key: tuple(int(x) for x in value) for key, value in dict(char_state["schema_policy"]).items()}
    if str(args.composition_policy).strip():
        schema_policy["composition"] = tuple(int(x) for x in str(args.composition_policy).split(","))
    if str(args.relation_policy).strip():
        schema_policy["relation"] = tuple(int(x) for x in str(args.relation_policy).split(","))
    entity_threshold = float(char_state["entity_threshold"])
    slot_threshold = float(char_state["slot_threshold"])
    split_scores: dict[str, Any] = {}
    split_predictions: dict[str, list[dict[str, Any]]] = {}
    for split, rows in rows_by_split.items():
        split_scores[split], split_predictions[split] = _score_split(
            rows=rows,
            policy_by_operation=policy_by_operation,
            model_alpha=float(args.model_alpha),
            query_embeddings=query_embeddings[split],
            doc_embeddings=doc_embeddings,
            doc_to_index=doc_to_index,
            pair_module=stage968,
            pair_router=pair_router,
            entity_model=entity_model,
            slot_model=slot_model,
            feature_fn=stage1024._features,
            selected_arities=selected_arities,
            schema_policy=schema_policy,
            entity_threshold=entity_threshold,
            slot_threshold=slot_threshold,
            threshold=float(state["threshold"]),
            fallback_to_base=bool(state["fallback_to_base"]),
            device=device,
            relation_source_role=bool(args.relation_source_role),
            counterfactual_source_role=bool(args.counterfactual_source_role),
            exception_source_kind=bool(args.exception_source_kind),
        )
    eval_score = split_scores["eval"]
    summary = {
        "artifact_kind": str(args.artifact_kind),
        "status": str(args.status),
        "bundle_dir": str(args.bundle_dir),
        "targets_jsonl": str(args.targets_jsonl),
        "router_state": str(args.router_state),
        "policy_json": str(args.policy_json),
        "char_state": str(args.char_state),
        "parameter_count": int(manifest.get("parameter_count", 0)),
        "router_parameter_count": sum(p.numel() for p in pair_router.parameters()),
        "char_schema_parameter_count": int(sum(p.numel() for p in entity_model.parameters()) + sum(p.numel() for p in slot_model.parameters())),
        "total_counted_parameter_count": int(manifest.get("parameter_count", 0))
        + int(sum(p.numel() for p in entity_model.parameters()))
        + int(sum(p.numel() for p in slot_model.parameters())),
        "model_alpha": float(args.model_alpha),
        "policy_by_operation": policy_by_operation,
        "selected_arities": selected_arities,
        "schema_policy": {key: list(value) for key, value in schema_policy.items()},
        "relation_source_role": bool(args.relation_source_role),
        "counterfactual_source_role": bool(args.counterfactual_source_role),
        "exception_source_kind": bool(args.exception_source_kind),
        "entity_threshold": entity_threshold,
        "slot_threshold": slot_threshold,
        "threshold": float(state["threshold"]),
        "split_scores": split_scores,
        "implied_full_answer_exact": [230 + int(eval_score["answer"]), 229 + int(eval_score["exact"])],
        "decision": "Loadable scorer combining Stage976 100M model-owned exception residual with a counted learned character schema-equality circuit for no-anchor composition and relation. This removes deterministic suffix set-intersection but remains a declared comparator interface, not encoder-owned natural-language equality.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with args.predictions_jsonl.open("w", encoding="utf-8") as handle:
        for split, predictions in split_predictions.items():
            for prediction in predictions:
                item = dict(prediction)
                item["split"] = split
                handle.write(json.dumps(item, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

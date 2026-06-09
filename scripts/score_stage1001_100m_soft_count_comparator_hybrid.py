#!/usr/bin/env python3
"""Score a loadable 100M bundle plus the learned Stage1000 soft-count comparator."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import torch


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


def _score_learned_pair_row(
    *,
    row_index: int,
    row: dict[str, Any],
    q_pair_spans: list[dict[str, Any]],
    d_pair_spans: list[dict[str, Any]],
    pair_doc_to_index: dict[str, int],
    learned_pair_model,
    selected_arities: dict[str, int],
    thresholds_by_operation: dict[str, float],
    fallback_to_base: bool,
) -> tuple[int | None, str]:
    candidates = list(row.get("candidates", []) or [])
    if not candidates:
        return None, "missing"
    operation = str(row.get("operation", "") or "")
    selected_arity = int(selected_arities.get(operation, 0))
    threshold = float(thresholds_by_operation.get(operation, thresholds_by_operation.get("default", 0.5)))
    q = q_pair_spans[row_index]
    predicted: list[int] = []
    with torch.no_grad():
        learned_pair_model.eval()
        for index, candidate in enumerate(candidates):
            d = d_pair_spans[pair_doc_to_index[str(candidate.get("doc_text", "") or "")]]
            count = 0
            if len(q["vectors"]) and len(d["vectors"]) and selected_arity > 0:
                for qi in range(len(q["vectors"])):
                    matched = False
                    for di in range(len(d["vectors"])):
                        prob = torch.sigmoid(learned_pair_model(q["vectors"][qi].unsqueeze(0), d["vectors"][di].unsqueeze(0))).item()
                        matched = matched or prob >= threshold
                    count += int(matched)
            if selected_arity > 0 and count >= selected_arity:
                predicted.append(index)
    if predicted:
        pool = predicted
        policy_detail = "learned_pair_comparator"
    elif fallback_to_base:
        pool = list(range(len(candidates)))
        policy_detail = "learned_pair_comparator_fallback_base"
    else:
        return None, "learned_pair_comparator_missing"
    top = max(
        pool,
        key=lambda idx: (float(candidates[idx].get("base_score", 0.0) or 0.0), -int(candidates[idx].get("rank", 9999) or 9999), -idx),
    )
    return int(top), policy_detail


def _score_soft_count_row(
    *,
    row_index: int,
    row: dict[str, Any],
    q_pair_spans: list[dict[str, Any]],
    d_pair_spans: list[dict[str, Any]],
    pair_doc_to_index: dict[str, int],
    pair_model,
    soft_count_model,
    stage1000,
    alpha: float,
) -> tuple[int | None, str]:
    candidates = list(row.get("candidates", []) or [])
    if not candidates:
        return None, "missing"
    q = q_pair_spans[row_index]
    scored: list[tuple[int, float]] = []
    with torch.no_grad():
        soft_count_model.eval()
        for index, candidate in enumerate(candidates):
            d = d_pair_spans[pair_doc_to_index[str(candidate.get("doc_text", "") or "")]]
            features = stage1000._features(pair_model, row, candidate, q, d).unsqueeze(0)
            logit = float(soft_count_model(features).item())
            base = float(candidate.get("base_score", 0.0) or 0.0)
            scored.append((index, logit + float(alpha) * base))
    top = max(scored, key=lambda item: (item[1], -item[0]))[0]
    return int(top), "learned_soft_count_comparator"


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
    q_pair_spans: list[dict[str, Any]],
    d_pair_spans: list[dict[str, Any]],
    pair_doc_to_index: dict[str, int],
    learned_pair_model,
    learned_thresholds_by_operation: dict[str, float],
    soft_count_model,
    soft_count_alpha: float,
    stage1000,
    selected_arities: dict[str, int],
    threshold: float,
    fallback_to_base: bool,
    device: torch.device,
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
        elif policy == "stage996_learned_pair_comparator":
            predicted_index, policy_detail = _score_learned_pair_row(
                row_index=row_index,
                row=row,
                q_pair_spans=q_pair_spans,
                d_pair_spans=d_pair_spans,
                pair_doc_to_index=pair_doc_to_index,
                learned_pair_model=learned_pair_model,
                selected_arities=selected_arities,
                thresholds_by_operation=learned_thresholds_by_operation,
                fallback_to_base=fallback_to_base,
            )
        elif policy == "stage1000_soft_count_comparator":
            predicted_index, policy_detail = _score_soft_count_row(
                row_index=row_index,
                row=row,
                q_pair_spans=q_pair_spans,
                d_pair_spans=d_pair_spans,
                pair_doc_to_index=pair_doc_to_index,
                pair_model=learned_pair_model,
                soft_count_model=soft_count_model,
                stage1000=stage1000,
                alpha=float(soft_count_alpha),
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
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage975_pair_overlap_teacher_targets.jsonl"))
    parser.add_argument("--router-state", type=Path, default=Path("runs/local/artifacts/stage966_pair_arity_router_state.pt"))
    parser.add_argument("--learned-comparator-state", type=Path, default=Path("runs/local/artifacts/stage996_encoder_span_pair_equality_comparator_state.pt"))
    parser.add_argument("--soft-count-state", type=Path, default=Path("runs/local/artifacts/stage1000_encoder_soft_count_candidate_scorer_state.pt"))
    parser.add_argument("--policy-json", type=Path, default=Path("runs/local/artifacts/stage964_operation_pair_arity_policy_summary.json"))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1001_100m_soft_count_comparator_hybrid_summary.json"))
    parser.add_argument("--predictions-jsonl", type=Path, default=Path("runs/local/artifacts/stage1001_100m_soft_count_comparator_hybrid_predictions.jsonl"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--query-batch-size", type=int, default=64)
    parser.add_argument("--doc-batch-size", type=int, default=64)
    parser.add_argument("--max-query-tokens", type=int, default=128)
    parser.add_argument("--max-doc-tokens", type=int, default=128)
    parser.add_argument("--model-alpha", type=float, default=0.75)
    parser.add_argument("--use-text-regex-suffixes", action="store_true")
    parser.add_argument("--pair-token-prefix", default="")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    stage974 = _load_module(repo_root / "scripts/score_stage974_model_owned_candidate_ranking.py", "stage974")
    stage968 = _load_module(repo_root / "scripts/score_stage968_loadable_pair_router.py", "stage968")
    stage995 = _load_module(repo_root / "scripts/train_stage995_encoder_span_pair_equality_comparator.py", "stage995")
    stage1000 = _load_module(repo_root / "scripts/train_stage1000_encoder_soft_count_candidate_scorer.py", "stage1000")
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
    learned_state = torch.load(args.learned_comparator_state, map_location="cpu")
    learned_pair_model = stage995.PairEq(int(learned_state["dim"]), int(learned_state["hidden_dim"]))
    learned_pair_model.load_state_dict(learned_state["model_state"])
    learned_thresholds_by_operation = {
        str(key): float(value)
        for key, value in dict(learned_state.get("thresholds_by_operation", {})).items()
    }
    soft_state = torch.load(args.soft_count_state, map_location="cpu")
    soft_count_model = stage1000.CandidateScorer(int(soft_state["dim"]), int(soft_state["hidden_dim"]))
    soft_count_model.load_state_dict(soft_state["model_state"])
    soft_count_alpha = float(soft_state["alpha"])
    selected_arities = stage968.selected_arities_from_policy(args.policy_json)
    use_bridge_fields = not bool(args.use_text_regex_suffixes)
    query_prefix = str(args.pair_token_prefix or "qpair")
    doc_prefix = str(args.pair_token_prefix or "dpair")
    query_pattern = stage995._prefix_re(query_prefix)
    doc_pattern = stage995._prefix_re(doc_prefix)
    pair_docs = {split: stage995._unique_docs(split_rows, use_bridge_fields=use_bridge_fields, doc_pattern=doc_pattern) for split, split_rows in rows_by_split.items()}
    pair_doc_to_index = {
        split: {str(doc["text"]): idx for idx, doc in enumerate(split_docs)}
        for split, split_docs in pair_docs.items()
    }
    pair_query_records = {
        split: [
            {
                "text": str(row.get("query_text", "") or ""),
                "suffixes": [str(item) for item in (row.get("query_bridge", {}) or {}).get("qpair", []) or []] if use_bridge_fields else [],
            }
            for row in split_rows
        ]
        for split, split_rows in rows_by_split.items()
    }
    q_pair_spans = {
        split: stage995._span_vectors_with_suffixes(
            model,
            tokenizer,
            pair_query_records[split],
            prefix=query_prefix,
            pattern=query_pattern,
            max_tokens=int(args.max_query_tokens),
            device=device,
        )
        for split in rows_by_split
    }
    d_pair_spans = {
        split: stage995._span_vectors_with_suffixes(
            model,
            tokenizer,
            pair_docs[split],
            prefix=doc_prefix,
            pattern=doc_pattern,
            max_tokens=int(args.max_doc_tokens),
            device=device,
        )
        for split in rows_by_split
    }
    policy_by_operation = {
        "atomic_fact": "base",
        "composition": "stage1000_soft_count_comparator",
        "counterfactual_false_claim": "base",
        "exception": "stage976_model_owned_blend",
        "relation": "stage1000_soft_count_comparator",
    }
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
            q_pair_spans=q_pair_spans[split],
            d_pair_spans=d_pair_spans[split],
            pair_doc_to_index=pair_doc_to_index[split],
            learned_pair_model=learned_pair_model,
            learned_thresholds_by_operation=learned_thresholds_by_operation,
            soft_count_model=soft_count_model,
            soft_count_alpha=soft_count_alpha,
            stage1000=stage1000,
            selected_arities=selected_arities,
            threshold=float(state["threshold"]),
            fallback_to_base=bool(state["fallback_to_base"]),
            device=device,
        )
    eval_score = split_scores["eval"]
    summary = {
        "artifact_kind": "stage1001_100m_soft_count_comparator_hybrid",
        "status": "completed_loadable_soft_count_comparator_hybrid_scorer",
        "bundle_dir": str(args.bundle_dir),
        "targets_jsonl": str(args.targets_jsonl),
        "router_state": str(args.router_state),
        "learned_comparator_state": str(args.learned_comparator_state),
        "soft_count_state": str(args.soft_count_state),
        "suffix_source": "rendered_text_regex" if bool(args.use_text_regex_suffixes) else "structured_bridge_fields",
        "pair_token_prefix": str(args.pair_token_prefix or "side_specific_qpair_dpair"),
        "policy_json": str(args.policy_json),
        "parameter_count": int(manifest.get("parameter_count", 0)),
        "router_parameter_count": sum(p.numel() for p in pair_router.parameters()),
        "learned_comparator_parameter_count": sum(p.numel() for p in learned_pair_model.parameters()),
        "soft_count_parameter_count": sum(p.numel() for p in soft_count_model.parameters()),
        "total_counted_parameter_count": int(manifest.get("parameter_count", 0)) + sum(p.numel() for p in pair_router.parameters()) + sum(p.numel() for p in learned_pair_model.parameters()) + sum(p.numel() for p in soft_count_model.parameters()),
        "model_alpha": float(args.model_alpha),
        "policy_by_operation": policy_by_operation,
        "selected_arities": selected_arities,
        "learned_thresholds_by_operation": learned_thresholds_by_operation,
        "soft_count_alpha": soft_count_alpha,
        "threshold": float(state["threshold"]),
        "split_scores": split_scores,
        "implied_full_answer_exact": [230 + int(eval_score["answer"]), 229 + int(eval_score["exact"])],
        "decision": "Loadable scorer combining Stage976 100M model-owned exception residual with the Stage1000 learned encoder pair-probability soft-count comparator for composition and relation. Eval does not use qpair/dpair suffix set intersection, but still uses qpair/dpair marker tokens as the located comparison interface.",
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

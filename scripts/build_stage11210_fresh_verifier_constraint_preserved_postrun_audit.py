#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _write_bounded_choice_eval_audit

ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11210
NAME = "stage11210_fresh_verifier_constraint_preserved_postrun_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_verifier_constraint_preserved_postrun_audit.json"

RUNTIME_BUNDLE = ARTIFACTS / "stage11209_fresh_verifier_constraint_preserved_probe/runtime_model/runtime_model_bundle.json"
STRICT_ROWS = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
VALIDATION_ROWS = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_validation.jsonl"
BANK_ROWS = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"
BANK_SUMMARY = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.json"
BASELINE_100M = ARTIFACTS / "stage11196_clean_residual_successor_100m_score/clean_residual_successor_100m_score.json"
GEMMA_BASELINE = ARTIFACTS / "stage11197_clean_residual_successor_gemma_comparison/clean_residual_successor_gemma_comparison.json"

TORCH_THREADS = max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))
torch.set_num_threads(TORCH_THREADS)
torch.set_num_interop_threads(max(1, min(4, TORCH_THREADS)))
EVAL_DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer, dict[str, Any]]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    model.to(EVAL_DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tokenizer, init_card


def root_id(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("row_id") or "missing")


def enrich(card: dict[str, Any], source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(row.get("row_id") or ""): row for row in source_rows}
    out = []
    for row in card.get("row_cards") or []:
        source = by_id.get(str(row.get("row_id") or ""), {})
        merged = dict(row)
        for key in [
            "language_family",
            "repo_family",
            "task_type",
            "root_id",
            "source_root_id",
            "residual_successor_source",
            "replacement_for_blocked_row_id",
            "replaces_quarantined_row_id",
        ]:
            merged[key] = source.get(key)
        projection = source.get("standalone_projection_source") or {}
        merged["gold_value"] = projection.get("gold_value") or source.get("gold_value")
        out.append(merged)
    return out


def metric(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get("constrained_choice_match"), bool)]
    correct = sum(1 for row in scored if row.get("constrained_choice_match") is True)
    return {
        "rows": len(rows),
        "scored_rows": len(scored),
        "correct": correct,
        "exact_accuracy": correct / len(scored) if scored else None,
    }


def group(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(field) or "unknown")].append(row)
    return {key: metric(value) for key, value in sorted(buckets.items())}


def cluster_metric(rows: list[dict[str, Any]]) -> dict[str, Any]:
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        clusters[root_id(row)].append(row)
    solved = 0
    scored_clusters = 0
    cards = []
    for rid, cluster_rows in sorted(clusters.items()):
        scored = [row for row in cluster_rows if isinstance(row.get("constrained_choice_match"), bool)]
        if not scored:
            cards.append({"root_id": rid, "rows": len(cluster_rows), "scored_rows": 0, "solved": None})
            continue
        scored_clusters += 1
        ok = all(row.get("constrained_choice_match") is True for row in scored)
        solved += 1 if ok else 0
        cards.append({"root_id": rid, "rows": len(cluster_rows), "scored_rows": len(scored), "solved": ok})
    return {
        "clusters": len(clusters),
        "scored_clusters": scored_clusters,
        "solved_clusters": solved,
        "cluster_exact_accuracy": solved / scored_clusters if scored_clusters else None,
        "cluster_cards": cards,
    }


def misses(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "row_id": row.get("row_id"),
            "root_id": root_id(row),
            "language_family": row.get("language_family"),
            "repo_family": row.get("repo_family"),
            "task_type": row.get("task_type"),
            "gold_value": row.get("gold_value"),
            "target_text": row.get("target_text"),
            "predicted": row.get("constrained_choice_top1_label"),
            "full_vocab_top1_text": row.get("full_vocab_top1_text"),
            "target_rank_full_vocab": row.get("target_rank_full_vocab"),
        }
        for row in rows
        if row.get("constrained_choice_match") is False
    ]


def score_rows(
    *,
    model: AgentKernelLiteTransformerSeq2Seq,
    tokenizer: AgentKernelBPETokenizer,
    rows: list[dict[str, Any]],
    split_name: str,
    scorer: str,
) -> list[dict[str, Any]]:
    card = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name=split_name,
        bounded_choice_aux_source=scorer,
        eval_batch_size=8,
    )
    return enrich(card, rows)


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_metric": metric(rows),
        "cluster_metric": cluster_metric(rows),
        "by_language": group(rows, "language_family"),
        "by_task": group(rows, "task_type"),
        "by_gold_value": group(rows, "gold_value"),
        "by_source": group(rows, "residual_successor_source"),
        "misses": misses(rows),
    }


def nested_get(payload: dict[str, Any], path: list[str], default: Any = None) -> Any:
    cur: Any = payload
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def main() -> None:
    strict_rows = load_jsonl(STRICT_ROWS)
    validation_rows = load_jsonl(VALIDATION_ROWS)
    bank_rows = load_jsonl(BANK_ROWS)
    bank_summary = load_json(BANK_SUMMARY)
    baseline_100m = load_json(BASELINE_100M)
    gemma = load_json(GEMMA_BASELINE)

    model, tokenizer, init_card = load_runtime()
    product_scorer = "encoder_option_retrieval_verifier_conditioned"
    diagnostic_scorers = [
        "encoder_option_retrieval",
        product_scorer,
        "encoder_option_retrieval_evidence_ledger_head",
    ]

    strict_product_rows = score_rows(
        model=model,
        tokenizer=tokenizer,
        rows=strict_rows,
        split_name=f"strict_eval_{product_scorer}",
        scorer=product_scorer,
    )
    validation_product_rows = score_rows(
        model=model,
        tokenizer=tokenizer,
        rows=validation_rows,
        split_name=f"validation_{product_scorer}",
        scorer=product_scorer,
    )

    bank_by_scorer = {}
    for scorer in diagnostic_scorers:
        scored = score_rows(
            model=model,
            tokenizer=tokenizer,
            rows=bank_rows,
            split_name=f"clean_residual_successor_{scorer}",
            scorer=scorer,
        )
        bank_by_scorer[scorer] = summarize_rows(scored)

    product_bank = bank_by_scorer[product_scorer]
    baseline_product = baseline_100m.get("productized_result") or {}
    baseline_row_acc = nested_get(baseline_product, ["row_metric", "exact_accuracy"])
    baseline_cluster_acc = nested_get(baseline_product, ["cluster_metric", "cluster_exact_accuracy"])
    product_row_acc = nested_get(product_bank, ["row_metric", "exact_accuracy"])
    product_cluster_acc = nested_get(product_bank, ["cluster_metric", "cluster_exact_accuracy"])

    gemma_row_acc = nested_get(gemma, ["gemma_result", "row_metric", "exact_accuracy"])
    gemma_cluster_acc = nested_get(gemma, ["gemma_result", "cluster_metric", "cluster_exact_accuracy"])
    if gemma_row_acc is None:
        gemma_row_acc = nested_get(gemma, ["comparison", "gemma_row_accuracy"])
    if gemma_cluster_acc is None:
        gemma_cluster_acc = nested_get(gemma, ["comparison", "gemma_cluster_accuracy"])
    if gemma_row_acc is None:
        gemma_row_acc = nested_get(gemma, ["gemma12b", "overall", "exact_accuracy"])
    if gemma_cluster_acc is None:
        gemma_cluster_acc = nested_get(gemma, ["gemma12b", "clustered", "cluster_exact_accuracy"])

    strict_metric = metric(strict_product_rows)
    validation_metric = metric(validation_product_rows)
    strict_ok = strict_metric["correct"] >= 22 and strict_metric["scored_rows"] == 22
    residual_improved = (
        product_row_acc is not None
        and baseline_row_acc is not None
        and product_row_acc > baseline_row_acc
    )
    beats_gemma = (
        product_row_acc is not None
        and gemma_row_acc is not None
        and product_row_acc > gemma_row_acc
    )

    decision = "diagnostic_negative_no_residual_gain"
    if residual_improved and strict_ok and beats_gemma:
        decision = "diagnostic_positive_residual_gain_beats_gemma"
    elif residual_improved and strict_ok:
        decision = "diagnostic_partial_residual_gain_not_gemma_win"
    elif not strict_ok:
        decision = "diagnostic_rejected_strict_regression"

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": decision,
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "strict_rows": rel(STRICT_ROWS),
            "validation_rows": rel(VALIDATION_ROWS),
            "bank_rows": rel(BANK_ROWS),
            "bank_summary": rel(BANK_SUMMARY),
            "baseline_100m": rel(BASELINE_100M),
            "gemma_baseline": rel(GEMMA_BASELINE),
        },
        "bank_gate": {
            "bank_passed": bank_summary.get("passed"),
            "promotion_eligible": bank_summary.get("promotion_eligible"),
            "score_reporting_requirement": bank_summary.get("score_reporting_requirement"),
            "bank_counts": bank_summary.get("counts"),
        },
        "productized_scorer": product_scorer,
        "clean_strict": summarize_rows(strict_product_rows),
        "clean_validation": summarize_rows(validation_product_rows),
        "clean_residual_successor": {
            "productized_result": product_bank,
            "all_scorer_results": bank_by_scorer,
            "baseline_100m_productized_row_accuracy": baseline_row_acc,
            "baseline_100m_productized_cluster_accuracy": baseline_cluster_acc,
            "gemma_row_accuracy": gemma_row_acc,
            "gemma_cluster_accuracy": gemma_cluster_acc,
            "row_accuracy_delta_vs_baseline_100m": product_row_acc - baseline_row_acc if product_row_acc is not None and baseline_row_acc is not None else None,
            "cluster_accuracy_delta_vs_baseline_100m": product_cluster_acc - baseline_cluster_acc if product_cluster_acc is not None and baseline_cluster_acc is not None else None,
            "row_accuracy_delta_vs_gemma": product_row_acc - gemma_row_acc if product_row_acc is not None and gemma_row_acc is not None else None,
            "cluster_accuracy_delta_vs_gemma": product_cluster_acc - gemma_cluster_acc if product_cluster_acc is not None and gemma_cluster_acc is not None else None,
        },
        "promotion_gate": {
            "strict_preserved_22_of_22": strict_ok,
            "residual_improved_vs_stage11196": residual_improved,
            "beats_gemma_on_clean_residual_successor": beats_gemma,
            "promotable": bool(strict_ok and residual_improved and beats_gemma),
        },
        "runtime_initialization": init_card,
        "outputs": {"summary_json": rel(SUMMARY_JSON)},
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

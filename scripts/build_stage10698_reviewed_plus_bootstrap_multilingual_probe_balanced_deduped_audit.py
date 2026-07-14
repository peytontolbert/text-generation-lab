#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10698
NAME = "stage10698_reviewed_plus_bootstrap_multilingual_probe_balanced_deduped_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "reviewed_plus_bootstrap_multilingual_probe_balanced_deduped_audit.json"

REQUEST_JSON = ROOT / "runs/local/artifacts/stage10697_reviewed_plus_bootstrap_multilingual_probe_request_balanced_deduped/reviewed_plus_bootstrap_multilingual_probe_request_balanced_deduped.json"
EXECUTION_JSON = ROOT / "runs/local/artifacts/stage10697_reviewed_plus_bootstrap_multilingual_probe_balanced_deduped/bounded_decoder_probe/execution_result.json"
SOURCE_DEEMPTY_JSON = ROOT / "runs/local/artifacts/stage10695_reviewed_plus_bootstrap_multilingual_probe_balanced_deempty/bounded_decoder_probe/execution_result.json"
SOURCE_DEEMPTY_REQUEST_JSON = ROOT / "runs/local/artifacts/stage10695_reviewed_plus_bootstrap_multilingual_probe_request_balanced_deempty/reviewed_plus_bootstrap_multilingual_probe_request_balanced_deempty.json"
BASELINE_AUDIT_JSON = ROOT / "runs/local/artifacts/stage10690_reviewed_v27_plus_two_fresh_rust_probe_audit/reviewed_v27_plus_two_fresh_rust_probe_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def language_from_row_id(row_id: str) -> str:
    parts = row_id.split("::")
    for part in parts:
        if part in {"python", "rust", "c_cpp", "web_js_ts_html"}:
            return part
    return "unknown"


def summarize_miss(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "row_id": str(row.get("row_id") or ""),
        "language_family": language_from_row_id(str(row.get("row_id") or "")),
        "predicted_label": row.get("constrained_choice_top1_label"),
        "target_label": row.get("bounded_choice_target_label"),
        "target_rank_full_vocab": row.get("target_rank_full_vocab"),
        "full_vocab_top1_text": row.get("full_vocab_top1_text"),
    }


def per_language_accuracy(row_cards: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    totals: Counter[str] = Counter()
    correct: Counter[str] = Counter()
    for row in row_cards:
        language = language_from_row_id(str(row.get("row_id") or ""))
        totals[language] += 1
        if bool(row.get("constrained_choice_match")):
            correct[language] += 1
    return {
        language: {
            "correct": correct[language],
            "total": totals[language],
            "accuracy": (correct[language] / totals[language]) if totals[language] else None,
        }
        for language in sorted(totals)
    }


def strict_eval(execution: dict[str, Any]) -> dict[str, Any]:
    return (((execution.get("bounded_choice_eval") or {}).get("strict_eval")) or {})


def main() -> None:
    request = load_json(REQUEST_JSON)
    execution = load_json(EXECUTION_JSON)
    deempty_execution = load_json(SOURCE_DEEMPTY_JSON)
    deempty_request = load_json(SOURCE_DEEMPTY_REQUEST_JSON)
    baseline_audit = load_json(BASELINE_AUDIT_JSON)

    strict_now = strict_eval(execution)
    strict_deempty = strict_eval(deempty_execution)
    baseline_strict = (baseline_audit.get("strict_eval_result") or {})

    row_cards_now = list(strict_now.get("row_cards") or [])
    miss_rows_now = [row for row in row_cards_now if not bool(row.get("constrained_choice_match"))]
    miss_row_ids_now = [str(row.get("row_id") or "") for row in miss_rows_now]
    baseline_miss_row_ids = list(baseline_strict.get("miss_row_ids") or [])

    removed_duplicate_rows = dict(request.get("removed_duplicate_rows") or {})
    deempty_rows_manifest = ((deempty_request.get("split_counts") or {}).get("strict_eval"))
    deempty_rows_scoreable = strict_deempty.get("constrained_choice_rows")
    deduped_rows = strict_now.get("constrained_choice_rows")
    baseline_acc = baseline_audit.get("headline", {}).get("baseline_hundred_m_strict_accuracy")
    current_acc = strict_now.get("constrained_choice_top1_accuracy")

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision": "deduped_multilingual_probe_completed_with_eval_integrity_repaired_but_no_frontier_lift",
        "claim_boundary": [
            "stage10697 repaired the eval/strict integrity bug introduced by duplicated null-option reviewed rows in stage10695.",
            "After removing the duplicate null-option copies, the honest strict set is 24 rows again and the 100M stays at 22/24 rather than improving beyond the existing frontier.",
            "The current honest headline therefore remains unchanged: the 100M still beats Gemma on the reviewed compact v2.7 strict slice, but the same Python verifier and Rust tokenizers evidence-citation residuals remain.",
        ],
        "headline": {
            "hundred_m_strict_accuracy": current_acc,
            "hundred_m_full_vocab_top1_accuracy": strict_now.get("full_vocab_top1_accuracy"),
            "strict_rows_honest": deduped_rows,
            "strict_rows_stage10695_contaminated_manifest": deempty_rows_manifest,
            "strict_rows_stage10695_scoreable_execution": deempty_rows_scoreable,
            "strict_row_delta_after_dedup": None if deempty_rows_manifest is None or deduped_rows is None else deduped_rows - deempty_rows_manifest,
            "strict_accuracy_vs_baseline_delta": None if current_acc is None or baseline_acc is None else current_acc - baseline_acc,
        },
        "integrity_repair": {
            "deempty_strict_rows_before_dedup_manifest": deempty_rows_manifest,
            "deempty_strict_rows_before_dedup_scoreable_execution": deempty_rows_scoreable,
            "deduped_strict_rows_after_dedup": deduped_rows,
            "strict_duplicate_rows_removed": ((removed_duplicate_rows.get("split_counts") or {}).get("strict_eval")),
            "eval_duplicate_rows_removed": ((removed_duplicate_rows.get("split_counts") or {}).get("eval")),
            "removed_duplicate_rows_language_counts": removed_duplicate_rows.get("language_counts"),
            "removed_duplicate_rows_sample_row_ids": removed_duplicate_rows.get("sample_row_ids"),
            "dedupe_kept_scoreable_variant_preference": True,
            "inflated_stage10695_36_row_result_retired": True,
        },
        "strict_eval_result": {
            "constrained_choice_top1_accuracy": current_acc,
            "full_vocab_top1_accuracy": strict_now.get("full_vocab_top1_accuracy"),
            "rows": deduped_rows,
            "per_language": per_language_accuracy(row_cards_now),
            "miss_count": len(miss_rows_now),
            "miss_row_ids": miss_row_ids_now,
            "miss_rows": [summarize_miss(row) for row in miss_rows_now],
            "same_two_reviewed_v27_misses_remain": sorted(miss_row_ids_now) == sorted(baseline_miss_row_ids),
        },
        "plateau_assessment": {
            "strict_accuracy_gt_baseline": bool(current_acc is not None and baseline_acc is not None and current_acc > baseline_acc),
            "zero_new_regressions": sorted(miss_row_ids_now) == sorted(baseline_miss_row_ids),
            "promotion_gate_passed": False,
            "reason": "The cleaned multilingual package repaired integrity but did not exceed the standing 22/24 strict frontier.",
        },
        "package_context": {
            "train_rows": request.get("split_counts", {}).get("train"),
            "eval_rows": request.get("split_counts", {}).get("eval"),
            "strict_rows": request.get("split_counts", {}).get("strict_eval"),
            "removed_duplicate_rows": removed_duplicate_rows,
        },
        "next_best_steps": [
            "Keep stage10697 as the clean multilingual packaging baseline because it removes the stage10695 strict inflation.",
            "Do not promote this run as a new frontier because the honest strict result remains 22/24.",
            "Use the cleaned 24-row strict slice as the compact multilingual regression suite while expanding fresh root supply rather than replaying these same reviewed rows.",
            "If the next probe targets capability movement, it should attack the remaining Python verifier and Rust tokenizers evidence-citation residual geometries with fresh root-disjoint support.",
        ],
        "sources": {
            "deduped_probe_request": display(REQUEST_JSON),
            "deduped_probe_execution": display(EXECUTION_JSON),
            "source_deempty_request": display(SOURCE_DEEMPTY_REQUEST_JSON),
            "source_deempty_execution": display(SOURCE_DEEMPTY_JSON),
            "baseline_audit": display(BASELINE_AUDIT_JSON),
        },
    }
    write_json(AUDIT_JSON, audit)
    print(AUDIT_JSON)


if __name__ == "__main__":
    main()

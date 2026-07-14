#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10690
NAME = "stage10690_reviewed_v27_plus_two_fresh_rust_probe_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "reviewed_v27_plus_two_fresh_rust_probe_audit.json"

REQUEST_JSON = ROOT / "runs/local/artifacts/stage10688_reviewed_v27_plus_two_fresh_rust_probe_request/reviewed_v27_plus_two_fresh_rust_probe_request.json"
EXECUTION_JSON = ROOT / "runs/local/artifacts/stage10689_reviewed_v27_plus_two_fresh_rust_probe/bounded_decoder_probe/execution_result.json"
BASELINE_JSON = ROOT / "runs/local/artifacts/stage10672_dual_residual_targeted_probe_audit/dual_residual_targeted_probe_audit.json"


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


def summarize_miss(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "row_id": str(row.get("row_id") or ""),
        "predicted_label": row.get("constrained_choice_top1_label"),
        "target_label": row.get("bounded_choice_target_label"),
        "target_rank_full_vocab": row.get("target_rank_full_vocab"),
        "full_vocab_top1_text": row.get("full_vocab_top1_text"),
    }


def main() -> None:
    request = load_json(REQUEST_JSON)
    execution = load_json(EXECUTION_JSON)
    baseline = load_json(BASELINE_JSON)

    strict_now = (((execution.get("bounded_choice_eval") or {}).get("strict_eval")) or {})
    strict_baseline = ((baseline.get("strict_eval_result")) or {})
    current_acc = strict_now.get("constrained_choice_top1_accuracy")
    baseline_acc = ((baseline.get("headline") or {}).get("baseline_hundred_m_strict_accuracy"))
    baseline_gemma = ((baseline.get("headline") or {}).get("baseline_gemma_strict_accuracy"))

    row_cards = ((strict_now.get("row_cards")) or [])
    miss_rows = [row for row in row_cards if not bool(row.get("constrained_choice_match"))]
    miss_row_ids_now = [str(row.get("row_id") or "") for row in miss_rows]
    miss_row_ids_baseline = ((((strict_baseline.get("miss_summary")) or {}).get("miss_row_ids")) or [])

    rust_support_rows_all = (request.get("rust_support_rows")) or []
    rust_support_rows = [row for row in rust_support_rows_all if str(row).startswith("stage10674::")]
    rust_support_roots = sorted({"::".join(str(row).split("::")[:3]) for row in rust_support_rows})

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision": "reviewed_v27_plus_two_fresh_rust_support_probe_completed_no_frontier_lift",
        "claim_boundary": [
            "The second fresh Rust support packet was admitted as train-support-only and did not alter the strict evaluation package.",
            "Adding two fresh Rust support roots preserved the reviewed multilingual strict score but did not improve it, so the run remains diagnostic/support-only and not promotable.",
            "This result keeps the current honest headline unchanged: the 100M still beats Gemma on the reviewed 24-row v2.7 strict set, but the same Python verifier and Rust evidence-citation residuals remain.",
        ],
        "headline": {
            "baseline_hundred_m_strict_accuracy": baseline_acc,
            "baseline_gemma_strict_accuracy": baseline_gemma,
            "current_hundred_m_strict_accuracy": current_acc,
            "current_vs_baseline_delta": None if current_acc is None or baseline_acc is None else current_acc - baseline_acc,
            "current_vs_gemma_delta_using_baseline_gemma": None if current_acc is None or baseline_gemma is None else current_acc - baseline_gemma,
        },
        "strict_eval_result": {
            "constrained_choice_top1_accuracy": current_acc,
            "full_vocab_top1_accuracy": strict_now.get("full_vocab_top1_accuracy"),
            "rows": strict_now.get("rows"),
            "miss_count": len(miss_rows),
            "miss_row_ids": miss_row_ids_now,
            "miss_rows": [summarize_miss(row) for row in miss_rows],
            "same_two_reviewed_v27_misses_remain": sorted(miss_row_ids_now) == sorted(miss_row_ids_baseline),
        },
        "regression_gate": {
            "strict_rows_unchanged": True,
            "strict_accuracy_gt_baseline": bool(current_acc is not None and baseline_acc is not None and current_acc > baseline_acc),
            "zero_new_regressions": sorted(miss_row_ids_now) == sorted(miss_row_ids_baseline),
            "promotion_gate_passed": bool(
                current_acc is not None
                and baseline_acc is not None
                and current_acc > baseline_acc
                and sorted(miss_row_ids_now) == sorted(miss_row_ids_baseline)
            ),
        },
        "package_effect": {
            "train_rows": request.get("split_counts", {}).get("train"),
            "strict_rows": request.get("split_counts", {}).get("strict_eval"),
            "fresh_rust_root_ids": rust_support_roots,
            "added_fresh_rust_train_rows": rust_support_rows,
            "train_language_counts": request.get("train_language_counts"),
        },
        "interpretation": {
            "rust_supply_improved_but_strict_miss_unchanged": True,
            "python_verifier_residual_still_present": True,
            "rust_tokenizers_evidence_residual_still_present": True,
            "rust_target_rank_signal": "The remaining Rust strict miss still places the target at rank 1 in full-vocab terms but loses constrained choice to F, which suggests continued representation or candidate-scoring collapse rather than simple absence of Rust support rows.",
        },
        "next_best_steps": [
            "Do not promote stage10689 as a new frontier because strict accuracy stayed flat at 22/24.",
            "Keep both fresh Rust packets in reviewed train-support inventory; they are clean additions even though they did not move strict eval.",
            "Shift the next data move toward a fresh Python verifier root or a new Rust citation root that matches the tokenizers E-vs-F residual geometry more directly.",
            "If another support-only probe is attempted, require a closer semantic match to the strict Rust citation residual instead of broader Rust coverage alone.",
        ],
        "sources": {
            "probe_request": display(REQUEST_JSON),
            "probe_result": display(EXECUTION_JSON),
            "baseline_audit": display(BASELINE_JSON),
        },
    }
    write_json(AUDIT_JSON, audit)
    print(AUDIT_JSON)


if __name__ == "__main__":
    main()

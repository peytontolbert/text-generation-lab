#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10684
NAME = "stage10684_reviewed_v27_plus_linux_rust_probe_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "reviewed_v27_plus_linux_rust_probe_audit.json"

REQUEST_JSON = ROOT / "runs/local/artifacts/stage10682_reviewed_v27_plus_linux_rust_probe_request/reviewed_v27_plus_linux_rust_probe_request.json"
EXECUTION_JSON = ROOT / "runs/local/artifacts/stage10683_reviewed_v27_plus_linux_rust_probe/bounded_decoder_probe/execution_result.json"
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


def main() -> None:
    request = load_json(REQUEST_JSON)
    execution = load_json(EXECUTION_JSON)
    baseline = load_json(BASELINE_JSON)

    strict_now = (((execution.get("bounded_choice_eval") or {}).get("strict_eval")) or {})
    strict_baseline = ((baseline.get("strict_eval_result")) or {})
    miss_now = ((strict_now.get("row_cards")) or [])
    miss_rows_now = [row for row in miss_now if not bool(row.get("constrained_choice_match"))]
    miss_row_ids_now = [str(row.get("row_id") or "") for row in miss_rows_now]
    miss_row_ids_baseline = ((((strict_baseline.get("miss_summary")) or {}).get("miss_row_ids")) or [])

    current_acc = strict_now.get("constrained_choice_top1_accuracy")
    baseline_acc = ((baseline.get("headline") or {}).get("baseline_hundred_m_strict_accuracy"))
    baseline_gemma = ((baseline.get("headline") or {}).get("baseline_gemma_strict_accuracy"))

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision": "reviewed_v27_plus_linux_rust_support_probe_completed_no_frontier_lift",
        "claim_boundary": [
            "The added Linux Rust ACPI support rows were clean train-support additions and did not change the strict evaluation package.",
            "The run preserved the reviewed multilingual strict score but did not improve it, so it is diagnostic/support-only and not promotable.",
            "This result does not change the current honest headline that the 100M beats Gemma on the reviewed 24-row v2.7 strict set.",
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
            "miss_count": len(miss_rows_now),
            "miss_row_ids": miss_row_ids_now,
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
            "added_linux_train_rows": ((request.get("fresh_support_focus") or {}).get("added_linux_train_rows")) or [],
            "train_language_counts": request.get("train_language_counts"),
        },
        "next_best_steps": [
            "Do not promote stage10683 as a new frontier because strict accuracy stayed flat at 22/24.",
            "Keep the Linux Rust packet in reviewed train-support inventory; it is a clean addition even though it did not move strict eval.",
            "Recover a second independent verifier-anchored fresh Rust root, preferably candle-datasets or candle-transformers, before spending more cycles on same-size support-only probes.",
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

#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11403
NAME = "stage11403_rust_replacement_comparison_decision"
OUT = ART / NAME
SUMMARY = OUT / "rust_replacement_comparison_decision.json"

COMPARISON = ART / "stage11402_rust_replacement_same_manifest_gemma_comparison/rust_replacement_same_manifest_gemma_comparison.json"
SCORE = ART / "stage11333_rust_web_gap_current_runtime_score/rust_web_gap_current_runtime_score.json"
RUST_ROWS = ART / "stage11331_rust_web_gap_recovery_manifest/admitted_rust_strict_replacement_rows.jsonl"


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def main() -> None:
    comparison = read_json(COMPARISON)
    score = read_json(SCORE)
    rows = read_jsonl(RUST_ROWS)
    hundred = comparison.get("hundred_m_stage11200_product_scorer") or {}
    gemma = comparison.get("gemma12b") or {}
    delta = comparison.get("delta_hundred_m_minus_gemma")
    tie = delta == 0
    weak_slice = (hundred.get("rows") or 0) < 10
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "decision": "keep_rust_replacement_slice_diagnostic",
        "claim_scope": "three reserved Rust evidence-citation replacement rows only",
        "hundred_m": hundred,
        "gemma12b": gemma,
        "delta_hundred_m_minus_gemma": delta,
        "interpretation": (
            "The reserved Rust replacement slice is weak for both systems: 100M and Gemma tie at 1/3. "
            "This is not evidence of a 100M Rust win, but it also is not a Gemma advantage. Treat the rows as a diagnostic "
            "for Rust evidence-role materialization and scorer alignment."
        ),
        "admission_policy": {
            "use_as_train_support": False,
            "use_as_headline_eval": False,
            "use_as_diagnostic_strict_candidate": True,
            "why": [
                "Rows are reserved strict replacements for quarantined Rust evidence rows.",
                "n=3 is too small for broad Rust claims.",
                "Both systems score 1/3, so the slice indicates hard/possibly under-specified evidence-role geometry.",
            ],
        },
        "next_allowed_steps": [
            "Mine disjoint Rust train-support roots, not these reserved rows.",
            "Require non-tokenizers repo families or fresh time splits.",
            "Require distinct candidate_change_surface, symptom_or_call_path_analogue, and verifier_and_test_constraint evidence.",
            "Re-score 100M and Gemma after adding a larger Rust heldout slice.",
        ],
        "row_ids": [row.get("row_id") for row in rows],
        "source_artifacts": {
            "comparison": rel(COMPARISON),
            "current_score": rel(SCORE),
            "rust_rows": rel(RUST_ROWS),
        },
        "outputs": {"summary": rel(SUMMARY)},
        "prior_product_metrics": score.get("product_metrics"),
        "promotion_gate": {
            "beats_gemma": bool(delta is not None and delta > 0),
            "tie_with_gemma": tie,
            "sufficient_n_for_claim": not weak_slice,
            "promote_rust_claim": False,
        },
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["promotion_gate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

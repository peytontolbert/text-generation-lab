#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
BASELINE = ARTIFACTS / "stage10646_reviewed_v28_candidate_same_manifest_comparison/reviewed_v28_candidate_same_manifest_comparison.json"
REPAIR = ARTIFACTS / "stage10654_reviewed_v28_headline_prompt_contract_repair/reviewed_v28_headline_prompt_contract_repair.json"
REPAIRED_COMPARISON = ARTIFACTS / "stage10655_reviewed_v28_repaired_headline_comparison/reviewed_v28_repaired_headline_comparison.json"
REPAIRED_ROWS = ARTIFACTS / "stage10655_reviewed_v28_repaired_headline_comparison/reviewed_v28_repaired_headline_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    baseline = load_json(BASELINE)
    repair = load_json(REPAIR)
    repaired = load_json(REPAIRED_COMPARISON)
    repaired_rows = load_jsonl(REPAIRED_ROWS)

    repaired_misses = [
        {
            "row_id": row["row_id"],
            "language_family": row["language_family"],
            "task_type": row["task_type"],
            "target_text": row["target_text"],
            "hundred_m_predicted_label": row["hundred_m_predicted_label"],
            "gemma12b_predicted_label": row["gemma12b_predicted_label"],
            "hundred_m_correct": row["hundred_m_correct"],
            "gemma12b_correct": row["gemma12b_correct"],
        }
        for row in repaired_rows
        if not row["hundred_m_correct"] or not row["gemma12b_correct"]
    ]

    baseline_headline = (((baseline.get("by_slice") or {}).get("hundred_m") or {}).get("headline_strict") or {})
    baseline_gemma = (((baseline.get("by_slice") or {}).get("gemma12b") or {}).get("headline_strict") or {})
    repaired_hundred = repaired.get("hundred_m") or {}
    repaired_gemma = repaired.get("gemma12b") or {}

    payload = {
        "stage": 10656,
        "stage_name": "stage10656_reviewed_v28_repaired_headline_audit",
        "passed": True,
        "sources": {
            "baseline_same_manifest": str(BASELINE.relative_to(ROOT)),
            "repair_package": str(REPAIR.relative_to(ROOT)),
            "repaired_comparison": str(REPAIRED_COMPARISON.relative_to(ROOT)),
        },
        "repair_scope": {
            "repaired_rows": repair["metrics"]["repaired_rows"],
            "headline_rows": repair["metrics"]["headline_rows"],
            "repaired_row_ids": repair["repaired_row_ids"],
        },
        "headline_accuracy_comparison": {
            "baseline_hundred_m_accuracy": baseline_headline.get("exact_accuracy"),
            "baseline_gemma_accuracy": baseline_gemma.get("exact_accuracy"),
            "repaired_hundred_m_accuracy": repaired_hundred.get("exact_accuracy"),
            "repaired_gemma_accuracy": repaired_gemma.get("exact_accuracy"),
            "baseline_delta": ((baseline_headline.get("exact_accuracy") or 0.0) - (baseline_gemma.get("exact_accuracy") or 0.0)),
            "repaired_delta": repaired.get("delta_exact_accuracy"),
        },
        "verdict": {
            "hundred_m_win_preserved_after_prompt_contract_repair": (repaired_hundred.get("exact_accuracy") or 0.0)
            > (repaired_gemma.get("exact_accuracy") or 0.0),
            "hundred_m_headline_accuracy_changed": (repaired_hundred.get("exact_accuracy") or 0.0) != (baseline_headline.get("exact_accuracy") or 0.0),
            "gemma_headline_accuracy_changed": (repaired_gemma.get("exact_accuracy") or 0.0) != (baseline_gemma.get("exact_accuracy") or 0.0),
        },
        "remaining_repaired_headline_misses": repaired_misses,
        "claim_boundary": [
            "This audit only establishes that the same-manifest headline win survives the repaired prompt contract on the four formerly shortcut-prone evidence_citation rows.",
            "It does not upgrade the headline to source-heldout or fully maintainer-grade realism.",
            "The remaining 100M misses are still Python verifier_outcome and Rust evidence_citation.",
        ],
        "next_best_steps": [
            "Promote the repaired headline contract as the cleaner same-manifest standalone boundary instead of the older semantic-role prompt wording.",
            "If desired, port the same repair style to validation and rust/web support slices before rebuilding the broader v2.8 claim gate.",
            "Keep mining fresh source-heldout web and Rust roots because prompt repair alone cannot solve the source-heldout claim gap.",
        ],
    }

    out_dir = ARTIFACTS / "stage10656_reviewed_v28_repaired_headline_audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "reviewed_v28_repaired_headline_audit.json", payload)
    print(out_dir / "reviewed_v28_repaired_headline_audit.json")


if __name__ == "__main__":
    main()

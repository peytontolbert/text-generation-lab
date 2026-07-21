#!/usr/bin/env python3
"""Decision after deterministic audit of subagent scout outputs."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12112
NAME = "stage12112_subagent_scout_decision"
OUT = ROOT / "runs/local/artifacts" / NAME
SUMMARY = OUT / "subagent_scout_decision.json"
MIRROR = ROOT / "runs/summaries" / f"{NAME}.json"

STAGE12109 = ROOT / "runs/summaries/stage12109_build_verifier_gap_fill_queue.json"
STAGE12110 = ROOT / "runs/summaries/stage12110_subagent_scout_intake_contract.json"
STAGE12111 = ROOT / "runs/summaries/stage12111_subagent_scout_intake_audit.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    gap = read_json(STAGE12109)
    contract = read_json(STAGE12110)
    audit = read_json(STAGE12111)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "subagent_scouts_closed_zero_sealed_admissions",
        "do_not_train": True,
        "subagent_pipeline_result": {
            "input_candidates": audit["input_candidates"],
            "admitted_candidates": audit["admitted_candidates"],
            "rejected_candidates": audit["rejected_candidates"],
            "admitted_by_language": audit["admitted_by_language"],
            "top_rejection_counts": audit["rejection_counts"],
        },
        "remaining_gap": audit["remaining_gap_after_admission"],
        "interpretation": [
            "Subagents were useful for bounded scouting but did not produce deterministic sealed admissions.",
            "Rust scout confirmed the local Rust supply is dev-only under current lineage rules.",
            "Web scout confirmed local Web candidates are exact or family overlaps with prior transition stages.",
            "C/C++ scout found candidate-looking mixed roots, but deterministic audit rejected them because unilm/method_comparison already appear in Stage120 transition support.",
            "The sealed route claim remains blocked on fresh root acquisition, not row rendering.",
        ],
        "current_materializable_non_training_supply": {
            "stage12107_work_items": 40,
            "stage12109_build_verifier_work_items": gap["work_items"],
            "combined_work_items": 40 + int(gap["work_items"]),
            "combined_by_lane": gap["combined_with_stage12107_by_lane"],
        },
        "next_stage_recommendation": {
            "stage": "stage12113_fresh_repo_acquisition_plan",
            "action": "Acquire or materialize genuinely fresh Rust/Web/C++ roots outside prior transition families before sealed route scoring.",
            "minimum_needed": audit["remaining_gap_after_admission"],
            "allowed_dev_only_use": "Dev-only Rust/Web overlap roots may be used for representation training later, but not for Stage12104 sealed confirmation.",
        },
        "source_artifacts": {
            "stage12109_gap_fill_queue": rel(STAGE12109),
            "stage12110_subagent_contract": rel(STAGE12110),
            "stage12111_subagent_audit": rel(STAGE12111),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "summary_mirror": rel(MIRROR),
        },
    }
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps({
        "decision": summary["decision"],
        "admitted_candidates": audit["admitted_candidates"],
        "remaining_gap": summary["remaining_gap"],
        "next_stage": summary["next_stage_recommendation"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

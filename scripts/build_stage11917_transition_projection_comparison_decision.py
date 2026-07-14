#!/usr/bin/env python3
"""Freeze the Stage11916 transition-projection Gemma comparison decision."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 11917
NAME = "stage11917_transition_projection_comparison_decision"
OUT = ROOT / "runs/local/artifacts" / NAME
SUMMARY = OUT / "transition_projection_comparison_decision.json"

STAGE11915 = ROOT / "runs/local/artifacts/stage11915_routed_transition_candidate_decision/routed_transition_candidate_decision.json"
STAGE11916 = ROOT / "runs/local/artifacts/stage11916_transition_projection_same_manifest_gemma_comparison/transition_projection_same_manifest_gemma_comparison.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    candidate = read_json(STAGE11915)
    comparison = read_json(STAGE11916)
    hundred = comparison["hundred_m"]["overall"]
    gemma = comparison["gemma12b"]["overall"]
    delta = hundred["accuracy"] - gemma["accuracy"]
    wins_by_language = comparison["verdict_by_language"]["_summary"]
    wins_by_task = comparison["verdict_by_task"]["_summary"]

    protected_gates = candidate["gates"]
    protected_passed = all(
        [
            protected_gates["filtered_strict_preserved"],
            protected_gates["old_canary_strict_preserved"],
            protected_gates["filtered_validation_preserved"],
            protected_gates["old_canary_validation_preserved"],
            protected_gates["residual_preserved"],
        ]
    )
    beats_gemma = delta > 0
    decision = (
        "do_not_promote_as_transition_projection_win"
        if not beats_gemma
        else "promote_routed_transition_projection_candidate"
    )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "summary": {
            "protected_gates_preserved": protected_passed,
            "same_manifest_transition_projection_beats_gemma": beats_gemma,
            "hundred_m_correct": hundred["correct"],
            "hundred_m_rows": hundred["scored_rows"],
            "hundred_m_accuracy": hundred["accuracy"],
            "gemma12b_correct": gemma["correct"],
            "gemma12b_rows": gemma["scored_rows"],
            "gemma12b_accuracy": gemma["accuracy"],
            "delta_vs_gemma12b": delta,
            "language_verdicts": wins_by_language,
            "task_verdicts": wins_by_task,
        },
        "interpretation": [
            "Stage11912 routed semantic transition head is useful versus Stage11507 on transition projection rows while preserving compact protected gates.",
            "Stage11916 shows the routed 100M transition scorer does not beat Gemma overall on the same 640-row transition-projection manifest.",
            "The loss is concentrated in C/C++ and in next_action, verifier_transition, and continue_or_stop target types.",
            "Keep Stage11912/11914 as a diagnostic routed capability candidate, not as a promoted transition-projection product frontier.",
        ],
        "recommended_next_work": [
            "Do not broaden the routed transition claim yet.",
            "Build C/C++ transition analogues with the canonical renderer before another transition comparison.",
            "Add task-specific supervision for transition_next_action and transition_verifier_transition instead of only semantic candidate head routing.",
            "Keep Stage11507 as the compact public-safe frontier unless a future routed package beats Gemma while preserving protected gates.",
        ],
        "source_artifacts": {
            "routed_candidate_decision": rel(STAGE11915),
            "same_manifest_gemma_comparison": rel(STAGE11916),
        },
        "outputs": {"summary": rel(SUMMARY)},
        "claim_boundary": [
            "This decision concerns compact transition-projection rows only.",
            "It does not change the Stage11507 compact bounded-choice maintainer scorer headline.",
            "It does not establish full-product patch repair, freeform generation, or broad source-heldout maintainer superiority.",
        ],
    }
    write_json(SUMMARY, payload)
    print(json.dumps({"summary": rel(SUMMARY), "decision": decision, "delta_vs_gemma12b": delta}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

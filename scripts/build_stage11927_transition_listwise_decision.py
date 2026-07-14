#!/usr/bin/env python3
"""Freeze Stage11923-11926 transition listwise outcome."""

from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 11927
NAME = "stage11927_transition_listwise_decision"
OUT = ROOT / "runs/local/artifacts" / NAME
SUMMARY = OUT / "transition_listwise_decision.json"

STAGE11922 = ROOT / "runs/local/artifacts/stage11922_transition_contrast_decision/transition_contrast_decision.json"
STAGE11925 = ROOT / "runs/local/artifacts/stage11925_transition_listwise_routed_postrun_audit/transition_listwise_routed_postrun_audit.json"
STAGE11926 = ROOT / "runs/local/artifacts/stage11926_transition_listwise_same_manifest_comparison/transition_listwise_same_manifest_comparison.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    prior = read_json(STAGE11922)
    audit = read_json(STAGE11925)
    comparison = read_json(STAGE11926)
    current_correct = int(comparison["hundred_m"]["overall"]["correct"])
    prior_correct = int(prior["facts"]["stage11921_100m_correct"])
    gemma_correct = int(comparison["gemma12b"]["overall"]["correct"])
    gates = audit["gates"]
    protected_preserved = all(
        gates[key]
        for key in [
            "filtered_strict_preserved",
            "filtered_validation_preserved",
            "old_canary_strict_preserved",
            "old_canary_validation_preserved",
            "residual_preserved",
            "smoke_preserved",
        ]
    )
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "transition_listwise_helpful_but_not_promotable",
        "facts": {
            "stage11921_100m_correct": prior_correct,
            "stage11926_100m_correct": current_correct,
            "gemma12b_correct": gemma_correct,
            "rows": comparison["rows"],
            "delta_rows_vs_stage11921": current_correct - prior_correct,
            "delta_rows_vs_gemma12b": current_correct - gemma_correct,
            "protected_gates_preserved": protected_preserved,
            "same_manifest_transition_projection_beats_gemma": current_correct > gemma_correct,
        },
        "breakdown": {
            "by_language": comparison["verdict_by_language"],
            "by_task": comparison["verdict_by_task"],
        },
        "interpretation": [
            "Same-role and verifier-value listwise losses helped: transition projection improved from 354/640 to 364/640 while preserving routed protected gates.",
            "The result is still not promotable because Gemma remains 386/640 on the unchanged transition manifest.",
            "The model now beats Gemma on transition_candidate_selection and transition_next_action, but still loses transition_continue_or_stop and transition_verifier_transition.",
            "The language blocker is concentrated in C/C++: 100M 83/256 versus Gemma 132/256.",
        ],
        "recommended_next_work": [
            "Run a C/C++-focused diagnostic starting from Stage11924 to test whether the remaining gap is learnable by the semantic head.",
            "Target transition_verifier_transition and transition_continue_or_stop rows first.",
            "Do not promote unless same-manifest transition projection beats Gemma and routed protected gates remain preserved.",
        ],
        "source_artifacts": {
            "prior_transition_contrast_decision": rel(STAGE11922),
            "routed_postrun_audit": rel(STAGE11925),
            "same_manifest_comparison": rel(STAGE11926),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, payload)
    print(json.dumps({"decision": payload["decision"], "delta_rows_vs_stage11921": current_correct - prior_correct, "delta_rows_vs_gemma12b": current_correct - gemma_correct}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

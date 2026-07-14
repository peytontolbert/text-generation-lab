#!/usr/bin/env python3
"""Freeze the Stage11918-11921 transition contrast outcome and next target."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 11922
NAME = "stage11922_transition_contrast_decision"
OUT = ROOT / "runs/local/artifacts" / NAME
SUMMARY = OUT / "transition_contrast_decision.json"

STAGE11917 = ROOT / "runs/local/artifacts/stage11917_transition_projection_comparison_decision/transition_projection_comparison_decision.json"
STAGE11920 = ROOT / "runs/local/artifacts/stage11920_transition_contrast_routed_postrun_audit/transition_contrast_routed_postrun_audit.json"
STAGE11921 = ROOT / "runs/local/artifacts/stage11921_transition_contrast_same_manifest_comparison/transition_contrast_same_manifest_comparison.json"


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
    before = read_json(STAGE11917)
    audit = read_json(STAGE11920)
    comparison = read_json(STAGE11921)
    previous_correct = int(before["summary"]["hundred_m_correct"])
    current_correct = int(comparison["hundred_m"]["overall"]["correct"])
    gemma_correct = int(comparison["gemma12b"]["overall"]["correct"])
    delta_rows_vs_previous = current_correct - previous_correct
    delta_rows_vs_gemma = current_correct - gemma_correct
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
    decision = "transition_contrast_helpful_but_not_promotable"
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "facts": {
            "stage11916_100m_correct": previous_correct,
            "stage11921_100m_correct": current_correct,
            "gemma12b_correct": gemma_correct,
            "rows": comparison["rows"],
            "delta_rows_vs_stage11916": delta_rows_vs_previous,
            "delta_rows_vs_gemma12b": delta_rows_vs_gemma,
            "protected_gates_preserved": protected_preserved,
            "same_manifest_transition_projection_beats_gemma": delta_rows_vs_gemma > 0,
        },
        "breakdown": {
            "by_language": comparison["verdict_by_language"],
            "by_task": comparison["verdict_by_task"],
        },
        "interpretation": [
            "Transition-specific contrast is a real mechanism improvement: 100M moved from 339/640 to 354/640 while preserving routed protected gates.",
            "The result is still not promotable because Gemma remains 386/640 on the unchanged same-manifest transition rows.",
            "100M now beats Gemma on Python and Rust transition projections but loses C/C++ by a large margin.",
            "The remaining task gaps are transition_verifier_transition, transition_continue_or_stop, and transition_next_action.",
        ],
        "recommended_next_work": [
            "Do not rerun generic transition support with the same objective.",
            "Build C/C++ transition analogues specifically for verifier-transition and continue/stop decisions.",
            "Add same-role listwise or verifier-value listwise pressure for transition_verifier_transition instead of only pairwise contrast.",
            "Promote only when same-manifest transition projection beats Gemma and routed protected gates remain preserved.",
        ],
        "source_artifacts": {
            "stage11917_prior_decision": rel(STAGE11917),
            "stage11920_routed_postrun_audit": rel(STAGE11920),
            "stage11921_same_manifest_comparison": rel(STAGE11921),
        },
        "outputs": {"summary": rel(SUMMARY)},
        "claim_boundary": [
            "This stage does not change the selected compact public-safe frontier.",
            "This is evidence that the contrast objective helps transition projections, not evidence of a transition-projection win over Gemma.",
            "This is not full-product patch repair or freeform generation.",
        ],
    }
    write_json(SUMMARY, summary)
    print(json.dumps({"decision": decision, "delta_rows_vs_stage11916": delta_rows_vs_previous, "delta_rows_vs_gemma12b": delta_rows_vs_gemma}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Record the Stage11914 routed transition semantic-head decision."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11915
NAME = "stage11915_routed_transition_candidate_decision"
OUT = ART / NAME
SUMMARY = OUT / "routed_transition_candidate_decision.json"

ROUTED_AUDIT = ART / "stage11914_routed_transition_semantic_head_audit/routed_transition_semantic_head_audit.json"
FULL_MODEL_ANALOGUE_AUDIT = ART / "stage11908_transition_projection_compact_analogue_replay_postrun_audit/transition_projection_compact_analogue_replay_postrun_audit.json"
PROTECTED_REPLAY_AUDIT = ART / "stage11904_transition_projection_protected_replay_postrun_audit/transition_projection_protected_replay_postrun_audit.json"
HEAD_ONLY_RUNTIME = ART / "stage11912_transition_projection_semantic_head_only_probe/runtime_model/runtime_model_bundle.json"
SELECTED_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"


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


def metric(audit: dict[str, Any], runtime: str, rowset: str) -> dict[str, Any]:
    item = audit["results"][runtime][rowset]
    return {"correct": item.get("correct"), "rows": item.get("rows"), "accuracy": item.get("accuracy")}


def main() -> None:
    routed = read_json(ROUTED_AUDIT)
    full_model = read_json(FULL_MODEL_ANALOGUE_AUDIT)
    protected_replay = read_json(PROTECTED_REPLAY_AUDIT)
    selected = "stage11507_selected_frontier"
    candidate = "stage11912_semantic_head_only"
    facts = {
        "selected_transition_routed": metric(routed, selected, "transition_projection_routed"),
        "candidate_transition_routed": metric(routed, candidate, "transition_projection_routed"),
        "candidate_filtered_strict": metric(routed, candidate, "protected::filtered_strict"),
        "candidate_filtered_validation": metric(routed, candidate, "protected::filtered_validation"),
        "candidate_old_canary_strict": metric(routed, candidate, "protected::old_canary_strict"),
        "candidate_old_canary_validation": metric(routed, candidate, "protected::old_canary_validation"),
        "candidate_residual": metric(routed, candidate, "protected::residual_bank"),
        "candidate_smoke": metric(routed, candidate, "protected::verifier_grounded_source_heldout_smoke"),
        "full_model_compact_analogue_gates": full_model.get("gates"),
        "protected_replay_gates": protected_replay.get("gates"),
    }
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "routed_transition_semantic_head_candidate_ready_for_next_comparison",
        "selected_promotable_frontier_before_this_stage": rel(SELECTED_RUNTIME),
        "candidate_runtime": rel(HEAD_ONLY_RUNTIME),
        "route_policy": routed.get("route_policy"),
        "gates": routed.get("gates"),
        "facts": facts,
        "interpretation": [
            "Full-model heldout-safe analogue replay learned transition projections but damaged compact protected gates.",
            "Semantic-candidate head-only training learned transition projections without changing the compact evidence-judgment route.",
            "Routed scoring uses semantic_candidate_head only for transition_projection rows and evidence_judgment_head for compact maintainer rows.",
            "Under that route, Stage11912 improves transition projections from 116/640 to 339/640 while preserving filtered strict, old canary strict, validation, residual, and smoke gates.",
        ],
        "next_required_work": [
            "Run same-manifest Gemma comparison for the transition_projection rowset, or build a compact comparable baseline if Gemma lacks this route.",
            "Package the routed scorer contract explicitly so downstream harness knows when to call semantic_candidate_head versus evidence_judgment_head.",
            "Expand transition records from real LHTB/Harbor-style rollouts with selected verifier transitions, especially web and fail-to-pass tasks.",
            "Do not claim full software repair or freeform generation from this result; it is a routed compact transition-policy improvement.",
        ],
        "source_artifacts": {
            "routed_audit": rel(ROUTED_AUDIT),
            "full_model_analogue_audit": rel(FULL_MODEL_ANALOGUE_AUDIT),
            "protected_replay_audit": rel(PROTECTED_REPLAY_AUDIT),
        },
        "outputs": {"summary": rel(SUMMARY)},
        "claim_boundary": [
            "This is a routed scorer candidate, not a replacement for all compact scoring.",
            "The current public-safe compact frontier remains Stage11507 unless the routed scorer is explicitly adopted and frozen.",
            "The result supports transition-projection capability improvement, not broad full-product repair.",
        ],
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "gates": artifact["gates"], "facts": facts}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

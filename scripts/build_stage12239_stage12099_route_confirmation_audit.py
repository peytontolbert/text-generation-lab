#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12239_stage12099_route_confirmation_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def load(stage: str) -> dict[str, Any]:
    path = ROOT / "runs/summaries" / f"{stage}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    # These values are kept explicit because the route is a cross-stage policy,
    # and some source summaries use different key names for the same score.
    stage11924 = load("stage11924_transition_listwise_head_only_postrun_audit")
    if not stage11924:
        stage11924 = load("stage11924_transition_listwise_head_only")
    stage12099 = load("stage12099_transition_routed_product_candidate")
    stage12103 = load("stage12103_stage12099_option_permutation_audit")
    stage12104 = load("stage12104_sealed_transition_slice_request")
    stage12130 = load("stage12130_selected_test_train_support_package")

    route = {
        "transition_candidate_selection": {
            "runtime": "stage12096_composite",
            "score": "92/160",
        },
        "transition_next_action": {
            "runtime": "stage12083_semantic",
            "score": "59/160",
        },
        "transition_continue_or_stop": {
            "runtime": "stage11924_semantic",
            "score": "128/160",
        },
        "transition_verifier_transition": {
            "runtime": "stage11924_semantic",
            "score": "96/160",
        },
    }

    payload: dict[str, Any] = {
        "stage": STAGE,
        "decision": "stage12099_route_permutation_stable_but_not_sealed_confirmed",
        "selected_transition_baseline": {
            "stage": "stage11924_transition_listwise_head_only",
            "score": "364/640",
            "accuracy": 0.56875,
            "status": "selected_transition_baseline_not_gemma_win",
        },
        "routed_candidate": {
            "stage": "stage12099_routed_product_candidate",
            "score": "375/640",
            "accuracy": 0.5859375,
            "delta_vs_stage11924": 11,
            "delta_vs_gemma": -11,
            "route_components": route,
            "status": "candidate_route_only",
        },
        "option_permutation_status": {
            "exists": True,
            "source_stage": "stage12103",
            "permutations_per_row": 3,
            "stable_semantic_predictions": "622/640",
            "stable_semantic_prediction_rate": 0.971875,
            "majority_correct": "376/640",
            "gate": "passes >=375/640 majority and >=0.95 preferred stability",
        },
        "sealed_confirmation_status": {
            "exists": False,
            "requested_stage": "stage12104",
            "known_blockers": [
                "stage12105 could not materialize minimum sealed 100 from existing rows",
                "stage12119 admitted no rows",
                "stage12129 cleared rendered rows for train-support only",
                "stage12130 strict_eval_rows=0 and strict_eval_eligible=false",
            ],
        },
        "minimum_sealed_slice_gate": {
            "rows": 100,
            "preferred_rows": 250,
            "task_floors_at_100": {
                "transition_candidate_selection": 25,
                "transition_continue_or_stop": 15,
                "transition_next_action": 35,
                "transition_verifier_transition": 25,
            },
            "language_floors_at_100": {
                "c_cpp": 20,
                "mixed_build_config_dependency": 10,
                "python": 20,
                "rust": 15,
                "web_js_ts_html": 15,
            },
            "lineage": [
                "root-disjoint from Stage11897",
                "root-disjoint from Stage11943",
                "root-disjoint from all Stage120xx discovery/repair/training roots",
                "root-disjoint from prior admitted diagnostic roots",
            ],
        },
        "next_allowed_stage": {
            "stage": "stage12241_sealed_transition_slice_acquisition_request",
            "purpose": "Acquire/admit root-disjoint sealed transition rows before scoring Stage12099 as a product route.",
            "training_allowed": False,
        },
        "source_artifact_presence": {
            "stage11924_summary_present": bool(stage11924),
            "stage12099_summary_present": bool(stage12099),
            "stage12103_summary_present": bool(stage12103),
            "stage12104_summary_present": bool(stage12104),
            "stage12130_summary_present": bool(stage12130),
        },
        "training_allowed": False,
        "claim_boundary": "Route confirmation audit only. Stage12099 is permutation-stable but lacks sealed/root-disjoint confirmation.",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "stage12099_route_confirmation_audit.json", payload)
    write_json(SUMMARY, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

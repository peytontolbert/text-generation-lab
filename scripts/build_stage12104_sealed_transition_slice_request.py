#!/usr/bin/env python3
"""Request a sealed transition slice after the Stage12099 route passed permutation audit."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12104
NAME = "stage12104_sealed_transition_slice_request"
OUT = ROOT / "runs/local/artifacts" / NAME
SUMMARY = OUT / "sealed_transition_slice_request.json"
MIRROR = ROOT / "runs/summaries" / f"{NAME}.json"

STAGE12100 = ROOT / "runs/summaries/stage12100_task_routed_transition_decision.json"
STAGE12102 = ROOT / "runs/summaries/stage12102_task_routed_gap_targeted_data_plan.json"
STAGE12103 = ROOT / "runs/summaries/stage12103_task_routed_option_permutation_stability_audit.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    route_decision = read_json(STAGE12100)
    data_plan = read_json(STAGE12102)
    permutation = read_json(STAGE12103)

    stability = permutation["stability"]
    permuted_score = permutation["permuted_score"]
    route = route_decision["product_routed_transition_candidate"]

    permutation_passed = (
        permutation.get("decision") == "option_permutation_stability_passed"
        and stability["majority_correct_rows"] >= 375
        and stability["stable_semantic_prediction_rate"] >= 0.90
        and permutation["row_counts"]["missing_route_cards"] == 0
        and permutation["row_counts"]["blocked_rows"] == 0
    )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": (
            "sealed_transition_slice_requested_after_permutation_pass"
            if permutation_passed
            else "blocked_permutation_gate_not_clean"
        ),
        "do_not_train": True,
        "reason": (
            "Stage12099 routed product candidate passed semantic option-permutation stability; next evidence must come from root-disjoint sealed rows."
            if permutation_passed
            else "Stage12103 did not satisfy the minimum route stability gate."
        ),
        "frozen_route_under_test": route["route_policy"],
        "current_scores": {
            "standalone_selected_stage11924": route_decision["standalone_selected_transition_frontier"]["score"],
            "product_routed_stage12099": route["score"],
            "gemma_same_manifest_target": {"correct": 386, "rows": 640},
            "product_route_delta_vs_gemma": route["delta_vs_gemma_386"],
        },
        "stage12103_permutation_gate": {
            "decision": permutation.get("decision"),
            "permutations_per_row": 3,
            "majority_correct_rows": stability["majority_correct_rows"],
            "majority_correct_accuracy": stability["majority_correct_accuracy"],
            "stable_semantic_prediction_rows": stability["stable_semantic_prediction_rows"],
            "stable_semantic_prediction_rate": stability["stable_semantic_prediction_rate"],
            "unanimous_correct_rows": stability["unanimous_correct_rows"],
            "permuted_correct": permuted_score["correct"],
            "permuted_rows": permuted_score["rows"],
            "missing_route_cards": permutation["row_counts"]["missing_route_cards"],
            "blocked_rows": permutation["row_counts"]["blocked_rows"],
            "passed": permutation_passed,
        },
        "sealed_slice_contract": {
            "minimum_rows": 100,
            "preferred_rows": 250,
            "split": "strict sealed confirmation only; no training/support rows from this slice",
            "root_lineage": [
                "root_id disjoint from Stage11897 transition projection rows",
                "root_lineage_key disjoint from Stage11897/11943/120xx discovery and repair rows",
                "repo_family overlap allowed only with explicit time/snapshot boundary and audit flag",
            ],
            "task_balance": {
                "transition_next_action": {"target_fraction": 0.35, "minimum_rows_at_100": 35, "preferred_rows_at_250": 88},
                "transition_candidate_selection": {"target_fraction": 0.25, "minimum_rows_at_100": 25, "preferred_rows_at_250": 62},
                "transition_verifier_transition": {"target_fraction": 0.25, "minimum_rows_at_100": 25, "preferred_rows_at_250": 62},
                "transition_continue_or_stop": {"target_fraction": 0.15, "minimum_rows_at_100": 15, "preferred_rows_at_250": 38},
            },
            "language_floor_at_100_rows": {
                "python": 20,
                "c_cpp": 20,
                "rust": 15,
                "web_js_ts_html": 15,
                "mixed_build_config_dependency": 10,
            },
            "quality_gates": [
                "visible source/test/verifier evidence before candidates",
                "semantic candidate objects with role, artifact_type, value, evidence_ids",
                "deterministic opaque option shuffle asserted",
                "no singleton option rows",
                "no target semantic value visible before candidates",
                "no prompt-target leakage",
                "no same-root or same-lineage train/eval overlap",
                "candidate labels are presentation only; evaluation by semantic candidate identity",
                "all rows runnable through the frozen Stage12099 route",
            ],
        },
        "confirmation_metrics": {
            "primary": "frozen Stage12099 route accuracy on sealed slice",
            "minimum_to_treat_route_as_real": {
                "coverage": "100%",
                "option_permutation_stable": True,
                "accuracy": ">= Stage11924 selected standalone on same sealed slice",
                "protected_compact_gates": "unchanged",
            },
            "strong_confirmation": {
                "accuracy": "beats Gemma on same sealed slice",
                "transition_next_action": "improves relative to Stage11924 and Stage12083 single-runtime baselines",
                "transition_candidate_selection": "retains Stage12096 routed gain",
            },
            "failure_interpretation": {
                "route_below_stage11924": "routing gain was same-manifest brittle",
                "route_between_stage11924_and_gemma": "routing is useful but not enough; build task-specific heads/adapters from disjoint analogues",
                "route_above_gemma": "product routing deserves promotion candidate status; standalone consolidation remains separate",
            },
        },
        "next_data_build_request": data_plan["targeted_data_plan"],
        "source_artifacts": {
            "route_decision": rel(STAGE12100),
            "gap_targeted_data_plan": rel(STAGE12102),
            "option_permutation_audit": rel(STAGE12103),
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
        "permutation_passed": permutation_passed,
        "minimum_rows": summary["sealed_slice_contract"]["minimum_rows"],
        "preferred_rows": summary["sealed_slice_contract"]["preferred_rows"],
        "task_balance": summary["sealed_slice_contract"]["task_balance"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

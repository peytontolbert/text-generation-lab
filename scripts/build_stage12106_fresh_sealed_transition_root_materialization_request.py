#!/usr/bin/env python3
"""Request fresh root-disjoint rows for the Stage12104 sealed transition slice."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12106
NAME = "stage12106_fresh_sealed_transition_root_materialization_request"
OUT = ROOT / "runs/local/artifacts" / NAME
SUMMARY = OUT / "fresh_sealed_transition_root_materialization_request.json"
MIRROR = ROOT / "runs/summaries" / f"{NAME}.json"
REQUEST = ROOT / "runs/summaries/stage12104_sealed_transition_slice_request.json"
ATLAS = ROOT / "runs/summaries/stage12105_sealed_transition_candidate_atlas.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    request = read_json(REQUEST)
    atlas = read_json(ATLAS)

    contract = request["sealed_slice_contract"]
    admitted = atlas["admitted_counts"]
    remaining = atlas["remaining_to_minimum"]

    # The atlas has many row projections but only 25 roots. The materialization
    # request is root-first: one root can emit several projection rows, but only
    # independent roots count toward the sealed-slice credibility gate.
    target_new_roots = {
        "c_cpp": 25,
        "python": 20,
        "rust": 20,
        "web_js_ts_html": 20,
        "mixed_build_config_dependency": 15,
    }

    task_projection_targets = {
        "transition_next_action": 90,
        "transition_candidate_selection": 65,
        "transition_verifier_transition": 65,
        "transition_continue_or_stop": 40,
    }

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "fresh_sealed_root_materialization_required_before_route_claim",
        "do_not_train": True,
        "why": [
            "Stage12103 passed semantic option-permutation stability, so the routed policy is stable enough to test.",
            "Stage12105 found 2462 admitted row projections but only 25 unique roots.",
            "Existing admitted candidates have no C/C++ roots and no mixed build/config/dependency roots.",
            "The Stage12104 sealed contract requires at least 100 root-disjoint rows/roots before treating the route as confirmed.",
        ],
        "current_evidence": {
            "stage12103_route_permutation": request["stage12103_permutation_gate"],
            "stage12105_decision": atlas["decision"],
            "stage12105_admitted_rows": atlas["admitted_rows"],
            "stage12105_unique_admitted_roots": atlas["unique_admitted_roots"],
            "stage12105_admitted_counts": admitted,
            "stage12105_remaining_to_minimum": remaining,
        },
        "fresh_root_materialization_contract": {
            "target_new_unique_roots": sum(target_new_roots.values()),
            "new_roots_by_language_or_lane": target_new_roots,
            "repo_family_cap": "No repo family may contribute more than 10% of a task family or 15% of total sealed roots.",
            "split": "sealed_confirm_only; never train/support/adapt on these rows before confirmation scoring",
            "root_lineage_exclusions": [
                "Stage11897 transition projection roots",
                "Stage11943 Gemma-gap atlas roots",
                "All Stage120xx transition discovery, repair, and training roots",
                "Any root already admitted in Stage12105 unless explicitly marked diagnostic-only",
            ],
            "minimum_candidate_contract_per_root": [
                "task instruction",
                "visible source evidence",
                "visible verifier/test/build evidence",
                "semantic candidate objects with role/artifact_type/value/evidence_ids",
                "deterministic opaque option shuffle",
                "no singleton rows",
                "no target semantic value visible before options",
                "root_id, root_lineage_key, repo_family, snapshot_id, language_family",
            ],
            "preferred_projection_rows": task_projection_targets,
            "required_task_mix": contract["task_balance"],
            "required_language_floor_at_100": contract["language_floor_at_100_rows"],
        },
        "task_family_generation_guidance": {
            "transition_next_action": {
                "priority": "highest",
                "root_count_hint": 40,
                "hard_negatives": [
                    "PLAN_PATCH when SELECT_TEST is correct",
                    "PLAN_PATCH when RETRIEVE_EVIDENCE is correct",
                    "FINISH when VERIFY_RESULT is correct",
                    "RETRIEVE_EVIDENCE when localized enough and verifier selection is next",
                    "ABSTAIN when evidence is sufficient",
                ],
            },
            "transition_candidate_selection": {
                "root_count_hint": 30,
                "hard_negatives": [
                    "candidate_change_surface vs verifier_and_build_constraint",
                    "selected test anchor vs implementation-only candidate",
                    "symptom/call-path analogue vs decisive verifier evidence",
                ],
            },
            "transition_verifier_transition": {
                "root_count_hint": 30,
                "hard_negatives": [
                    "PASS_CURRENT_BUILD vs PASS_CURRENT_BUILD_AND_RUN",
                    "PASS_CURRENT_STATE vs PASS_TO_PASS",
                    "NOT_EXERCISED vs PASS_TO_PASS",
                    "VERIFIER_REMOVED vs INSUFFICIENT_EVIDENCE",
                    "FAIL_TO_PASS vs syntax-only compile recovery",
                ],
            },
            "transition_continue_or_stop": {
                "root_count_hint": 20,
                "hard_negatives": [
                    "premature DONE after focused test only when clean replay required",
                    "CONTINUE after verifier removed without enough evidence",
                    "STOP when unresolved regression remains",
                ],
            },
        },
        "next_stage_recommendation": {
            "stage": "stage12107_fresh_sealed_transition_root_materializer",
            "action": "Materialize fresh sealed roots to this contract, then run an admission audit before any route/Gemma scoring.",
            "minimum_to_score": {
                "unique_roots": 100,
                "c_cpp_roots": 20,
                "mixed_build_config_dependency_roots": 10,
                "all_task_minimums": True,
                "all_anti_cheat_gates": True,
            },
        },
        "source_artifacts": {
            "stage12104_request": rel(REQUEST),
            "stage12105_atlas": rel(ATLAS),
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
        "target_new_unique_roots": summary["fresh_root_materialization_contract"]["target_new_unique_roots"],
        "new_roots_by_language_or_lane": target_new_roots,
        "preferred_projection_rows": task_projection_targets,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

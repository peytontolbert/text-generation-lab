#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12226_level3_next_blocker_decision"
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
OUT = ROOT / "runs/local/artifacts" / STAGE


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    s12216 = load(ROOT / "runs/summaries/stage12216_normalized_verifier_observation_dataset.json")
    s12224 = load(ROOT / "runs/summaries/stage12224_patch_trace_training_rollup.json")
    s12225 = load(ROOT / "runs/summaries/stage12225_patch_trace_semantic_qc.json")
    s12223 = load(ROOT / "runs/summaries/stage12223_targeted_patch_replay_smoke.json")
    decision = {
        "stage": STAGE,
        "decision": "do_not_train_build_new_comparable_patch_trace_supply",
        "evidence": {
            "normalized_verifier_observation_rows": s12216.get("row_count"),
            "normalized_verifier_training_allowed": s12216.get("training_allowed"),
            "raw_patch_trace_rollup": {
                "admitted_count": s12224.get("admitted_count"),
                "patch_trace_floor_count": s12224.get("patch_trace_floor_count"),
                "fail_to_pass_floor_count": s12224.get("fail_to_pass_floor_count"),
                "language_counts": s12224.get("language_counts"),
            },
            "semantic_qc_patch_trace": {
                "admitted_count": s12225.get("admitted_count"),
                "downgraded_count": s12225.get("downgraded_count"),
                "patch_trace_floor_count": s12225.get("patch_trace_floor_count"),
                "fail_to_pass_floor_count": s12225.get("fail_to_pass_floor_count"),
                "transition_counts": s12225.get("transition_counts"),
                "repo_family_counts": s12225.get("repo_family_counts"),
            },
            "stage12223_invalid_repair_catch": {
                "raw_fail_to_pass_floor_count": s12223.get("fail_to_pass_floor_count"),
                "reason_removed": "mem0 before verifier failed because selected test file was absent; not comparable behavior failure",
            },
            "non_python_scout_result": "no accepted C/C++/Rust/Web Stage12201/12217 patch-trace candidates; current pool is blocked by missing node_modules, missing build dirs, CUDA dependency, weak anchors, or no Rust rows",
        },
        "blockers": [
            "patch_trace_train_support_after_semantic_qc_has_only_2_rows",
            "patch_trace_train_support_is_python_only",
            "valid_fail_to_pass_patch_repair_floor_is_0",
            "stage12201_stage12217_pool_exhausted_for_non_python_without_installs_or_gpu",
            "normalized_verifier_observation_rows_are_not_patch_trace_training_rows",
        ],
        "next_subagent_packets": [
            {
                "name": "comparable_fail_to_pass_patch_scout",
                "objective": "Find roots where the exact same selected verifier exists before and after, fails before for a behavior/source reason, passes after applying patch, and can run locally without installs/network/GPU.",
                "minimum_acceptance": "5 candidates, at least 2 non-Python, no test-added-before-missing failures, command output available or rehydratable.",
            },
            {
                "name": "non_python_hydratable_patch_scout",
                "objective": "Find C/C++/Rust/Web roots with existing local build/test artifacts or lightweight no-install commands tied to changed files.",
                "minimum_acceptance": "3 candidates per language family or explicit hard-blocker report with repo/source evidence.",
            },
            {
                "name": "patch_trace_schema_integrator",
                "objective": "Define how admitted patch-trace records become training projections without flattening multi-command ordered_events into verifier-only rows.",
                "minimum_acceptance": "No training request until semantic QC passes and patch_trace rows are projected as action/patch/verifier/stop records.",
            },
        ],
        "training_allowed": False,
        "claim_boundary": "Progress is dataset-hygiene and first patch replay plumbing. No model training should run from this patch-trace lane until comparable repair supply exists across languages.",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "level3_next_blocker_decision.json", decision)
    write_json(SUMMARY, decision)
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

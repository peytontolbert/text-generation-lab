#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12227_subagent_packet_control"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    common_hard_rejects = [
        "ENV_BLOCKED_or_dependency_install_required",
        "network_required",
        "gpu_required_or_uses_cuda_device",
        "test_added_before_patch_so_before_command_missing_test",
        "pytest_no_tests_ran_or_usage_error_counted_as_failure",
        "weak_anchor_tests_init_or_placeholder_test",
        "verifier_unrelated_to_changed_files",
        "build_only_result_counted_as_runnable_selected_verifier",
        "patch_diff_not_same_source_or_not_apply_checked",
        "strict_or_source_heldout_claim_without lineage audit",
    ]
    artifact = {
        "stage": STAGE,
        "source_stage": "stage12226_level3_next_blocker_decision",
        "decision": "subagent_packets_active_training_blocked",
        "active_subagents": {
            "019f6b5e-a93e-7d63-a359-1319ad1b57e2": "comparable_fail_to_pass_patch_scout",
            "019f6b5e-c362-7421-9e44-4606ca128de1": "non_python_hydratable_patch_scout",
            "019f6b5e-da5d-7bc3-babe-2cbf68244a73": "patch_trace_schema_integrator",
        },
        "common_hard_rejects": common_hard_rejects,
        "packets": [
            {
                "name": "comparable_fail_to_pass_patch_scout",
                "must_return_schema": [
                    "repo_family",
                    "language_family",
                    "episode_or_root_id",
                    "repo_commit_before_or_source_ref",
                    "repo_commit_after_or_source_ref",
                    "patch_diff_ref",
                    "verifier_command",
                    "verifier_cwd",
                    "verifier_env",
                    "why_before_failure_is_behavioral_and_comparable",
                    "why_patch_should_pass_same_verifier",
                    "risk_flags",
                ],
                "success_floor": {
                    "candidate_count": 5,
                    "non_python_count": 2,
                    "must_include_same_verifier_before_patch_after": True,
                    "must_exclude_test_added_before_missing": True,
                },
            },
            {
                "name": "non_python_hydratable_patch_scout",
                "must_return_schema": [
                    "repo_family",
                    "language_family",
                    "episode_or_root_id",
                    "repo_commit_before_or_source_ref",
                    "repo_commit_after_or_source_ref",
                    "patch_diff_ref",
                    "verifier_command",
                    "verifier_cwd",
                    "verifier_env",
                    "verifier_relation_to_changed_files",
                    "risk_or_blocker",
                ],
                "success_floor": {
                    "per_language_candidate_target": 3,
                    "languages": ["c_cpp", "rust", "web_js_ts_html"],
                    "allow_exhausted_pool_report": True,
                },
            },
            {
                "name": "patch_trace_schema_integrator",
                "must_return_schema": [
                    "projection_families",
                    "required_fields",
                    "hard_reject_rules",
                    "before_before_plus_patch_after_representation",
                    "trainer_or_dataset_scripts_to_change",
                    "known_schema_flaws",
                ],
                "success_floor": {
                    "must_prevent_flattening_to_stage12206_verifier_only": True,
                    "must_include_patch_apply_and_verifier_observation_fields": True,
                    "must_keep_training_blocked_until_semantic_qc": True,
                },
            },
        ],
        "training_allowed": False,
        "claim_boundary": "Control artifact only. Subagents can propose candidates/contracts; deterministic scripts must admit or reject rows.",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "subagent_packet_control.json", artifact)
    write_json(SUMMARY, artifact)
    print(json.dumps(artifact, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

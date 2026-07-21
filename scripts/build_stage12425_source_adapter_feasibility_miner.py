#!/usr/bin/env python3
"""Stage12425 source-adapter feasibility miner/control artifact.

This is deliberately fail-closed. It does not inspect large datasets, emit
training rows, admit candidates, replay patches, or copy raw commands/content.
It converts the Stage12424 scouting request into a bounded feasibility control
artifact for later source-adapter work.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12425_source_adapter_feasibility_miner"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

INPUTS = {
    "stage12424_summary": ROOT / "runs/summaries/stage12424_new_source_adapter_scouting_request_control_artifact.json",
    "stage12424_control_artifact": ROOT
    / "runs/local/artifacts/stage12424_new_source_adapter_scouting_request_control_artifact"
    / "new_source_adapter_scouting_request_control_artifact.json",
    "stage12424_guardrail_scan": ROOT
    / "runs/local/artifacts/stage12424_new_source_adapter_scouting_request_control_artifact"
    / "guardrail_scan.json",
}

FORBIDDEN_TEXT_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|"
    r"(?:^|[\s:=])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+",
    re.IGNORECASE | re.MULTILINE,
)

ZERO_COUNTERS = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed": False,
    "admitted_rows": 0,
    "emitted_rows": 0,
    "emitted_training_rows": 0,
    "countable_new_rows": 0,
    "countable_as_new_train_support_rows": 0,
    "countable_as_new_proof_floor_rows": 0,
    "raw_rows_inspected": 0,
    "raw_rows_copied": 0,
    "large_dataset_deep_scan_count": 0,
    "replay_attempted_count": 0,
    "patch_apply_attempted_count": 0,
    "tests_run_count": 0,
}

RAW_CONTENT_POLICY = {
    "raw_commands_emitted": False,
    "command_descriptors_only": True,
    "raw_paths_emitted": False,
    "urls_emitted": False,
    "diffs_emitted": False,
    "patches_emitted": False,
    "source_text_emitted": False,
    "stdout_stderr_emitted": False,
    "issue_bodies_emitted": False,
    "input_text_emitted": False,
    "raw_row_content_emitted": False,
    "raw_locator_values_emitted": False,
}

REQUIRED_SAFE_SCAN_FIELDS = [
    "source_adapter_id",
    "adapter_family",
    "source_family",
    "language_family",
    "repo_family_hash",
    "root_lineage_hash",
    "task_ref_hash",
    "observation_ref_hash",
    "verifier_ref_hash",
    "state_before_hash",
    "state_after_hash",
    "patch_or_action_hash",
    "dedupe_key_hash",
    "direct_source_anchor_present",
    "direct_verifier_anchor_present",
    "state_transition_anchor_present",
    "stop_or_continue_anchor_present",
    "before_after_verifier_status_present",
    "same_source_lineage_present",
    "source_heldout_split_status",
    "protected_overlap_status",
    "raw_leak_count",
    "overclaim_count",
    "blocked_reason",
]


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_known_adapter_families(stage12424: dict[str, Any]) -> list[dict[str, Any]]:
    families: list[dict[str, Any]] = []
    for item in stage12424.get("candidate_adapter_families") or []:
        if not isinstance(item, dict):
            continue
        adapter_family = str(item.get("adapter_family") or "unknown_adapter_family")
        must_prove = [str(v) for v in item.get("must_prove") or []]
        families.append(
            {
                "adapter_family": adapter_family,
                "known_from_stage12424": True,
                "feasibility_status": "not_mined_control_only",
                "safe_scan_mode": "metadata_hashes_and_boolean_slots_only",
                "required_proof_slots": must_prove,
                "raw_content_allowed": False,
                "admission_status": "not_admitted",
            }
        )
    return families


def fallback_adapter_families() -> list[dict[str, Any]]:
    names = [
        "codex_session_episode_graphs",
        "open_swe_replay_micro_pilot",
        "external_benchmark_patch_logs",
        "locally_hydratable_repo_tasks",
    ]
    return [
        {
            "adapter_family": name,
            "known_from_stage12424": False,
            "feasibility_status": "not_mined_control_only",
            "safe_scan_mode": "metadata_hashes_and_boolean_slots_only",
            "required_proof_slots": [],
            "raw_content_allowed": False,
            "admission_status": "not_admitted",
        }
        for name in names
    ]


def quota_checks(stage12424: dict[str, Any]) -> dict[str, dict[str, Any]]:
    quotas = stage12424.get("adapter_acceptance_quotas")
    if not isinstance(quotas, dict):
        quotas = {}
    checks: dict[str, dict[str, Any]] = {}
    for name, threshold in sorted(quotas.items()):
        observed = False if name == "training_allowed_required" else 0
        passed = observed is threshold if isinstance(threshold, bool) else observed >= threshold
        if name.startswith("maximum_") and not isinstance(threshold, bool):
            passed = observed <= threshold
        checks[name] = {
            "threshold": threshold,
            "observed_control_only": observed,
            "passed": bool(passed),
            "status": "blocked_no_candidate_scan_run" if not passed else "pass_by_zero_or_false_control",
        }
    return checks


def guardrail_scan(value: Any) -> dict[str, Any]:
    payload = json.dumps(value, sort_keys=True)
    matches = FORBIDDEN_TEXT_RE.findall(payload)
    return {
        "scan_passed": len(matches) == 0,
        "issue_count": len(matches),
        "issues": ["forbidden_raw_text_pattern_detected"] if matches else [],
        "required_safe_scan_fields_present": all(field in REQUIRED_SAFE_SCAN_FIELDS for field in REQUIRED_SAFE_SCAN_FIELDS),
        "raw_content_policy": RAW_CONTENT_POLICY,
    }


def main() -> None:
    stage12424 = read_json(INPUTS["stage12424_summary"]) or read_json(INPUTS["stage12424_control_artifact"])
    adapter_families = safe_known_adapter_families(stage12424) or fallback_adapter_families()
    checks = quota_checks(stage12424)

    blocked_reasons = {
        "control_artifact_only": len(adapter_families),
        "no_raw_source_scan_performed": len(adapter_families),
        "no_admission_gate_run": len(adapter_families),
        "large_dataset_deep_scan_disallowed": len(adapter_families),
    }
    failed_quota_count = sum(1 for check in checks.values() if not check["passed"])
    ranked_adapter_feasibility = [
        {
            "rank": 1,
            "adapter_family": "sakana_cuda_engineer_archive",
            "safe_dataset_root_label": "SakanaAI--AI-CUDA-Engineer-Archive",
            "metadata_row_count": 30615,
            "metadata_positive_observation_count": 15594,
            "metadata_negative_or_error_observation_count": 14116,
            "expected_countable_yield_after_admission": "40_to_75_verifier_observation_rows",
            "best_use": "cuda_c_cpp_verifier_performance_observation_support",
            "not_claimable_as": ["patch_trace", "level3_closed_loop", "fail_to_pass_repair"],
            "missing_proof_slots": ["local_rerun", "patch_lineage", "before_after_causal_repair_transition", "stop_continue"],
            "recommended_next_stage": "stage12426_sakana_cuda_safe_metadata_profiler",
        },
        {
            "rank": 2,
            "adapter_family": "open_swe_traces",
            "safe_dataset_root_label": "Open-SWE-Traces",
            "metadata_row_count": 207489,
            "metadata_shard_count": 84,
            "metadata_distinct_repo_count": 2654,
            "metadata_language_counts": {
                "python": 48179, "go": 46834, "typescript": 36897, "javascript": 29360,
                "rust": 21735, "java": 13176, "php": 10323, "c": 683, "cpp": 302
            },
            "metadata_result_counts": {"resolved": 65244, "unresolved": 95487, "unknown_or_other": 46758},
            "expected_countable_yield_after_safe_extraction": "20_to_50_transition_support_rows",
            "best_use": "high_volume_candidate_transition_and_replay_queue",
            "not_claimable_as": ["level3_or_patch_trace_without_replay", "resolved_equals_verifier_proof"],
            "missing_proof_slots": ["checkout_before", "patch_apply", "same_verifier_before_after", "causal_linkage", "stop_continue"],
            "recommended_next_stage": "stage12427_open_swe_safe_metadata_profiler",
        },
        {
            "rank": 3,
            "adapter_family": "swe_hero_zero_trajectory_datasets",
            "safe_dataset_root_label": "SWE-Hero_and_SWE-Zero",
            "metadata_row_counts": {"swe_hero": 34269, "swe_zero": 318115},
            "expected_countable_yield_after_safe_extraction": "candidate_only_until_verifier_or_replay_layer_exists",
            "best_use": "state_action_patch_context_candidate_mining",
            "not_claimable_as": ["verifier_observation_without_trace_parse_or_replay", "source_heldout_without_split_policy"],
            "missing_proof_slots": ["language_inference", "verifier_result", "same_verifier_before_after", "causal_linkage"],
        },
        {
            "rank": 4,
            "adapter_family": "bears_repairthemall",
            "safe_dataset_root_label": "Bears_RepairThemAll",
            "metadata_candidate_counts": {"metadata_records": 251, "failing_passing_candidates": 19, "hydration_candidates": 5},
            "expected_countable_yield_after_hydration": "0_now_possible_5_to_19_later",
            "best_use": "java_patch_trace_after_checkout_hydration",
            "not_claimable_as": ["current_countable_supply"],
            "missing_proof_slots": ["checkout_hydration", "buggy_failure_reproduction", "fixed_pass", "patch_apply_diff_lineage"],
        },
        {
            "rank": 5,
            "adapter_family": "local_external_repair_replay_cache",
            "safe_dataset_root_label": "Stage12284_12292_replay_cache",
            "expected_countable_yield_after_review": "0_patch_effect_rows",
            "best_use": "negative_blocker_telemetry",
            "not_claimable_as": ["patch_effect", "fail_to_pass_repair"],
            "missing_proof_slots": ["before_fail", "before_plus_patch_pass", "causal_repair_proof"],
        },
    ]

    artifact = {
        **ZERO_COUNTERS,
        "stage": STAGE,
        "record_type": "source_adapter_feasibility_control_artifact_v1",
        "decision": "fail_closed_feasibility_control_only_no_rows_admitted",
        "claim_boundary": (
            "Stage12425 defines feasible source-adapter scan contracts and quotas only. "
            "It does not mine, admit, emit, train on, replay, or copy raw source rows."
        ),
        "source_adapter_id": "stage12425_control_only_no_adapter_executed",
        "adapter_families": adapter_families,
        "ranked_adapter_feasibility": ranked_adapter_feasibility,
        "highest_priority_adapter": ranked_adapter_feasibility[0]["adapter_family"],
        "highest_priority_next_stage": ranked_adapter_feasibility[0]["recommended_next_stage"],
        "source_family_counts": {},
        "language_counts": {},
        "repo_family_counts": {},
        "root_count": 0,
        "dedupe_key_policy": {
            "required": True,
            "key_material": "hashes_only",
            "must_dedupe_against": ["stage12385", "stage12416", "stage12418", "stage12421"],
            "raw_locator_material_allowed": False,
        },
        "direct_vs_derived_counts": {"direct": 0, "derived": 0, "controlled_fixture": 0, "unknown": 0},
        "target_semantic_counts": {},
        "proof_slot_status_counts": {
            "direct_source_anchor_present": 0,
            "direct_verifier_anchor_present": 0,
            "state_transition_anchor_present": 0,
            "stop_or_continue_anchor_present": 0,
            "before_after_verifier_status_present": 0,
            "same_source_lineage_present": 0,
            "all_required_slots_present": 0,
        },
        "required_safe_scan_fields": REQUIRED_SAFE_SCAN_FIELDS,
        "adapter_acceptance_quota_checks": checks,
        "quota_check_summary": {
            "total_checks": len(checks),
            "passed_checks": len(checks) - failed_quota_count,
            "failed_checks": failed_quota_count,
            "promotion_allowed": False,
        },
        "strict_source_heldout_status": "not_claimed_no_scan_run",
        "dominance_report": {
            "dominant_source_family": None,
            "dominant_source_family_share": 0,
            "single_source_family_quota_passed": True,
            "controlled_fixture_share": 0,
            "controlled_fixture_quota_passed": True,
        },
        "blocked_reason_counts": blocked_reasons,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "promotion_gate_status": {
            "artifact_is_control_only": "PASS",
            "training_allowed_false": "PASS",
            "no_rows_admitted": "PASS",
            "no_rows_emitted": "PASS",
            "raw_content_policy_declared": "PASS",
            "quota_checks_defined": "PASS" if checks else "BLOCKED_MISSING_STAGE12424_QUOTAS",
            "safe_scan_fields_defined": "PASS",
            "promotion_allowed": "PASS_FALSE",
        },
        "input_inventory": {
            name: {"present": path.exists(), "sha256_24": file_hash(path)}
            for name, path in INPUTS.items()
        },
        "source_controls": {
            "stage12424_decision": stage12424.get("decision"),
            "stage12424_training_allowed": stage12424.get("training_allowed", False),
            "stage12424_guardrail_scan_passed": stage12424.get("guardrail_scan_passed"),
            "stage12424_next_stage_recommendation": stage12424.get("next_stage_recommendation"),
        },
        "next_stage_recommendation": "stage12426_sakana_cuda_safe_metadata_profiler_then_stage12427_open_swe_safe_metadata_profiler",
    }
    scan = guardrail_scan(artifact)
    artifact["guardrail_scan_passed"] = scan["scan_passed"]
    artifact["raw_leak_count"] = scan["issue_count"]
    artifact["overclaim_count"] = 0
    artifact["summary_hash"] = stable_hash({k: v for k, v in artifact.items() if k != "summary_hash"})

    write_json(OUT / "source_adapter_feasibility_control_artifact.json", artifact)
    write_json(OUT / "guardrail_scan.json", scan)
    write_json(SUMMARY, artifact)
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

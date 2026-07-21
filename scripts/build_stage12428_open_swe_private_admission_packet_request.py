#!/usr/bin/env python3
"""Stage12428 Open-SWE private admission packet request.

This is a fail-closed public control/sampler-request artifact. It does not
sample, read parquet rows, emit training rows, expose raw locators, or execute
replay. It packages the requirements a later private sampler must satisfy.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12428_open_swe_private_admission_packet_request"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

INPUTS = {
    "stage12427_summary": ROOT / "runs/summaries/stage12427_open_swe_safe_metadata_profiler.json",
    "unbounded_spine": ROOT / "docs/UNBOUNDED_SOFTWARE_TASK_COMPLETION_SPINE_STAGE12195.md",
}

ZERO_COUNTERS: dict[str, bool | int] = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed": False,
    "sampler_run": False,
    "admitted_rows": 0,
    "emitted_rows": 0,
    "emitted_training_rows": 0,
    "countable_rows": 0,
    "countable_new_rows": 0,
    "countable_as_new_train_support_rows": 0,
    "countable_as_new_proof_floor_rows": 0,
    "raw_rows_inspected": 0,
    "raw_rows_copied": 0,
    "raw_content_emitted": False,
    "replay_attempted_count": 0,
    "patch_apply_attempted_count": 0,
    "tests_run_count": 0,
}

RAW_CONTENT_POLICY = {
    "raw_trajectories_emitted": False,
    "raw_commands_emitted": False,
    "raw_outputs_emitted": False,
    "raw_diffs_emitted": False,
    "raw_patches_emitted": False,
    "raw_issue_bodies_emitted": False,
    "urls_emitted": False,
    "source_text_emitted": False,
    "raw_paths_emitted": False,
    "training_rows_emitted": False,
    "row_values_emitted": False,
    "locator_values_emitted": False,
    "schema_field_names_emitted": False,
    "private_only_fields_emitted": False,
}

FORBIDDEN_TEXT_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|stdout|stderr|pytest |npm |pip |git clone)\b",
    re.IGNORECASE | re.MULTILINE,
)

OVERCLAIM_RE = re.compile(
    r"\b(?:admitted|training rows|countable rows|level[_ -]?3|level[_ -]?4|closed[- ]loop|"
    r"fail[- ]to[- ]pass|verified repair|causal proof)\b",
    re.IGNORECASE,
)

ALLOWED_OVERCLAIM_CONTEXT_RE = re.compile(
    r"(not_|no_|zero|blocked|reject|required|minimum|candidate|not claimable|"
    r"not_claimable|training_allowed|admitted_rows|countable_rows|"
    r"countable_new_rows|countable_as_new|level3_candidate|level_3_diagnostic_floor)",
    re.IGNORECASE,
)


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


def safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def summarize_stage12427(stage12427: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_stage": stage12427.get("stage"),
        "source_decision": stage12427.get("decision"),
        "source_training_allowed": stage12427.get("training_allowed", False),
        "source_guardrail_scan_passed": stage12427.get("guardrail_scan_passed", False),
        "dataset_family": stage12427.get("dataset_family"),
        "safe_dataset_root_label": stage12427.get("safe_dataset_root_label"),
        "safe_metadata_available": bool(stage12427.get("safe_metadata_available")),
        "candidate_count": safe_int(stage12427.get("candidate_count")),
        "candidate_count_is_training_rows": bool(stage12427.get("candidate_count_is_training_rows")),
        "candidate_count_is_admission": bool(stage12427.get("candidate_count_is_admission")),
        "candidate_count_source": stage12427.get("candidate_count_source"),
        "trajectory_shard_count": safe_int(stage12427.get("trajectory_shard_count")),
        "shard_count": safe_int(stage12427.get("shard_count")),
        "metadata_file_count": safe_int(stage12427.get("metadata_file_count")),
        "schema_file_count": safe_int(stage12427.get("schema_file_count")),
        "config_counts": stage12427.get("config_counts") if isinstance(stage12427.get("config_counts"), dict) else {},
        "config_count_policy": stage12427.get("config_count_policy"),
        "extension_counts": stage12427.get("extension_counts") if isinstance(stage12427.get("extension_counts"), dict) else {},
        "metadata_status_counts": stage12427.get("metadata_status_counts")
        if isinstance(stage12427.get("metadata_status_counts"), dict)
        else {},
        "raw_rows_inspected": safe_int(stage12427.get("raw_rows_inspected")),
        "raw_rows_copied": safe_int(stage12427.get("raw_rows_copied")),
        "raw_content_emitted": bool(stage12427.get("raw_content_emitted")),
    }


def build_private_sampler_request(stage12427: dict[str, Any]) -> dict[str, Any]:
    source_summary = summarize_stage12427(stage12427)
    candidate_count = source_summary["candidate_count"]
    shard_count = source_summary["shard_count"]
    source_ok = (
        bool(stage12427)
        and source_summary["source_training_allowed"] is False
        and source_summary["source_guardrail_scan_passed"] is True
        and source_summary["raw_rows_inspected"] == 0
        and source_summary["raw_rows_copied"] == 0
        and source_summary["raw_content_emitted"] is False
    )

    request = {
        **ZERO_COUNTERS,
        "stage": STAGE,
        "record_type": "open_swe_private_admission_packet_request_v1",
        "decision": "fail_closed_public_request_only_no_sampling_no_rows_admitted",
        "claim_boundary": (
            "Stage12428 emits only a public-safe request/control packet for a later private Open-SWE sampler. "
            "It uses Stage12427 safe metadata counters, emits no raw fields, reads no parquet rows, admits no "
            "records, and cannot be counted as training data."
        ),
        "source_adapter_id": "stage12428_public_request_for_private_open_swe_sampler",
        "source_metadata": source_summary,
        "input_summary_hashes": {name: file_hash(path) for name, path in INPUTS.items()},
        "input_summary_presence": {name: path.exists() for name, path in INPUTS.items()},
        "source_preconditions": {
            "stage12427_present": bool(stage12427),
            "stage12427_fail_closed": stage12427.get("decision") == "fail_closed_safe_metadata_only_no_rows_admitted",
            "stage12427_training_allowed_false": source_summary["source_training_allowed"] is False,
            "stage12427_guardrail_scan_passed": source_summary["source_guardrail_scan_passed"] is True,
            "stage12427_raw_rows_inspected_zero": source_summary["raw_rows_inspected"] == 0,
            "stage12427_raw_rows_copied_zero": source_summary["raw_rows_copied"] == 0,
            "source_eligible_for_request_only": source_ok,
        },
        "private_sampler_quotas": {
            "candidate_supply_rows_from_metadata": candidate_count,
            "candidate_supply_rows_are_not_training_rows": True,
            "source_shard_count_from_metadata": shard_count,
            "max_private_candidates_to_sample_initial": min(candidate_count, 2000) if candidate_count else 0,
            "max_private_candidates_per_config_initial": 200,
            "max_private_candidates_per_repo_family": 50,
            "max_private_candidates_per_language_family": 500,
            "max_private_candidates_per_result_bucket": 500,
            "minimum_private_candidates_per_config_when_available": 25,
            "minimum_distinct_repo_families_before_admission": 10,
            "minimum_distinct_language_families_before_admission": 3,
            "minimum_level3_candidate_floor_before_any_training": 20,
            "minimum_patch_trace_candidate_floor_before_any_training": 8,
            "maximum_controlled_fixture_share": 0.0,
            "raw_leak_count_required": 0,
            "overclaim_count_required": 0,
        },
        "dedupe_collapse_policy": {
            "dedupe_required_before_private_review": True,
            "key_material_public_artifact": "hashes_only",
            "private_key_material_allowed_only_inside_private_sampler": [
                "raw_dataset_locator",
                "instance_id",
                "repo_identifier",
                "base_commit",
                "patch_hash",
                "verifier_command_fingerprint",
                "trajectory_event_window_hash",
            ],
            "collapse_equivalent_records_by": [
                "same_repo_family_hash",
                "same_issue_or_instance_hash",
                "same_patch_hash",
                "same_before_after_state_hash_pair",
                "same_verifier_identity_hash",
            ],
            "prefer_when_collapsing": [
                "complete same-source before/after verifier proof",
                "explicit patch application proof",
                "explicit stop-or-continue label",
                "shorter causal event window with all required proof slots",
                "rarer repo/language/config bucket under quota",
            ],
            "must_dedupe_against_existing_countable_ledgers": [
                "stage12385",
                "stage12416",
                "stage12418",
                "stage12421",
            ],
            "reject_if_duplicate_of_existing_countable_row": True,
        },
        "required_proof_slots": {
            "same_source_lineage": {
                "required": True,
                "public_return": "same_source_lineage_status",
                "private_evidence": ["raw_locator", "repo_identity", "commit_before", "state_after_ref"],
            },
            "checkout_before_anchor": {
                "required": True,
                "public_return": "checkout_before_anchor_status",
                "private_evidence": ["checkout_ref", "repo_root", "base_commit"],
            },
            "patch_application_proof": {
                "required": True,
                "public_return": "patch_application_status",
                "private_evidence": ["patch_text_or_delta", "apply_exit_status", "apply_observation"],
            },
            "same_verifier_before_after": {
                "required": True,
                "public_return": "same_verifier_before_after_status",
                "private_evidence": ["verifier_command", "pre_result", "post_result", "verifier_identity"],
            },
            "causal_transition_not_resolved_metadata": {
                "required": True,
                "public_return": "causal_transition_status",
                "private_evidence": ["ordered_events", "chosen_action", "observation", "state_update"],
            },
            "stop_or_continue_label": {
                "required": True,
                "public_return": "stop_or_continue_status",
                "private_evidence": ["terminal_decision", "remaining_blockers", "verifier_grounding"],
            },
            "protected_overlap_and_leak_audit": {
                "required": True,
                "public_return": "protected_overlap_status",
                "private_evidence": ["protected_split_refs", "overlap_hashes", "leak_scan_report"],
            },
        },
        "allowed_private_only_fields": [
            "raw_dataset_locator",
            "raw_trajectory",
            "raw_command",
            "raw_stdout",
            "raw_stderr",
            "raw_diff",
            "raw_patch",
            "raw_issue_body",
            "raw_repo_url",
            "raw_repo_path",
            "source_file_text",
            "checkout_ref",
            "instance_id",
            "repo_identifier",
            "verifier_command",
            "ordered_event_payloads",
        ],
        "public_safe_output_schema": {
            "stage": "string",
            "record_type": "private_open_swe_admission_packet_public_summary_v1",
            "training_allowed": "boolean_false_until_gate_passes",
            "admission_allowed": "boolean_false_until_gate_passes",
            "candidate_count_private_reviewed": "integer",
            "admitted_rows": "integer_zero_unless_separate_admission_gate_passes",
            "emitted_training_rows": "integer_zero_unless_separate_training_gate_passes",
            "bucket_counts": "hash_bucket_to_integer",
            "proof_slot_status_counts": "slot_name_to_status_count",
            "dedupe_status_counts": "status_to_integer",
            "reject_reason_counts": "reason_to_integer",
            "safe_row_hashes": "optional_hashes_only_for_admitted_rows_after_gate",
            "raw_content_policy": "all_false_public_policy_booleans",
            "raw_leak_count": "integer",
            "overclaim_count": "integer",
            "summary_hash": "hash",
        },
        "candidate_supply_rows": candidate_count,
        "trajectory_shard_count": shard_count,
        "first_private_sample_quota": {
            "sample_exactly": 100,
            "minimum_distinct_repositories": 10,
            "minimum_distinct_language_families": 3,
            "target_distinct_language_families": 8,
            "maximum_candidates_per_language_family": 25,
            "maximum_candidates_per_repository_family": 10,
            "maximum_candidates_per_source_config": 25,
            "maximum_resolved_label_candidates": 50,
            "maximum_unresolved_label_candidates": 35,
            "maximum_unknown_or_other_label_candidates": 25,
            "minimum_absent_from_existing_countable_ledgers": 40,
            "minimum_direct_verifier_anchor_present": 40,
            "minimum_state_transition_anchor_present": 30,
            "minimum_stop_or_continue_anchor_present": 20,
            "minimum_replayable_patch_trace_candidates": 12,
            "minimum_before_after_verifier_status_present": 8,
            "minimum_level3_candidates_after_private_replay": 20,
        },
        "public_safe_schema": {
            "record_type": "open_swe_private_admission_public_packet_v1",
            "required_fields": [
                "packet_id_hash", "candidate_id_hash", "source_adapter_id", "source_family",
                "language_family", "repo_family_hash", "root_lineage_hash", "task_ref_hash",
                "observation_ref_hash", "verifier_ref_hash", "state_before_hash", "state_after_hash",
                "patch_or_action_hash", "dedupe_key_hash", "collapse_key_hash", "metadata_result_label",
                "admission_level", "proof_readiness", "source_heldout_split_status",
                "protected_overlap_status", "raw_leak_count", "overclaim_count", "blocked_reason",
                "training_allowed", "admission_allowed"
            ],
            "public_material_policy": "hash_boolean_enum_count_only",
        },
        "private_only_fields": [
            "raw_locator_packet", "private_row_locator", "private_checkout_before_anchor",
            "private_state_after_anchor", "private_replay_workspace_locator",
            "private_verifier_invocation_descriptor", "before_status_payload", "after_status_payload",
            "patch_application_evidence", "ordered_event_payloads", "issue_task_payload",
            "observation_payload", "stop_continue_label_evidence", "same_source_lineage_material",
            "reviewer_audit_notes"
        ],
        "proof_slot_requirements": [
            "direct_source_anchor_present", "direct_verifier_anchor_present",
            "checkout_before_anchor_present", "patch_apply_evidence_present",
            "state_after_anchor_present", "before_after_verifier_status_present",
            "same_verifier_identity_present", "same_source_lineage_present",
            "causal_linkage_present", "state_transition_anchor_present",
            "stop_or_continue_anchor_present", "all_required_slots_present"
        ],
        "required_audit_metrics": {
            "resolved_label_shortcut_rate": "required_in_private_sampler_result",
            "resolved_only_blocked_count": "required_in_private_sampler_result",
            "resolved_to_repair_claim_count": "must_be_zero",
            "trajectory_duplicate_rate": "required_in_private_sampler_result",
            "near_duplicate_cluster_count": "required_in_private_sampler_result",
            "max_duplicate_cluster_size": "required_in_private_sampler_result",
            "model_family_counts": "required_in_private_sampler_result",
            "config_family_counts": "required_in_private_sampler_result",
            "max_model_family_share": "required_in_private_sampler_result",
            "unknown_provenance_count": "required_in_private_sampler_result",
            "repo_counts": "required_hashed_counts",
            "org_counts": "required_hashed_counts",
            "max_repo_share": "required_in_private_sampler_result",
            "max_org_share": "required_in_private_sampler_result",
            "repo_cap_blocked_count": "required_in_private_sampler_result",
            "benchmark_overlap_count": "required_in_private_sampler_result",
            "strict_eval_overlap_count": "must_be_zero",
            "raw_patch_leak_count": "must_be_zero",
            "raw_diff_leak_count": "must_be_zero",
            "raw_command_output_leak_count": "must_be_zero",
            "raw_path_url_issue_leak_count": "must_be_zero",
            "action_imitation_only_count": "required_in_private_sampler_result",
            "candidate_action_present_count": "required_in_private_sampler_result",
            "correct_policy_proven_count": "required_in_private_sampler_result",
            "same_verifier_before_after_count": "required_in_private_sampler_result",
            "patch_apply_proven_count": "required_in_private_sampler_result",
            "state_before_after_proven_count": "required_in_private_sampler_result",
            "verifier_causality_pass_count": "required_in_private_sampler_result",
            "level3_admitted_count": "must_remain_zero_until_separate_admission_gate",
            "patch_trace_admitted_count": "must_remain_zero_until_separate_admission_gate",
            "repo_floor_count": "required_in_private_sampler_result",
            "language_floor_count": "required_in_private_sampler_result"
        },
        "private_sampler_reject_conditions": [
            "any required proof slot missing",
            "any raw private-only field appears in public output",
            "resolved/status metadata is used as repair proof without verifier transition evidence",
            "patch and verifier co-presence is treated as causality without ordered transition",
            "dedupe against existing countable ledgers is absent",
            "repo, language, result, source-family, or config quota would be exceeded",
            "protected-overlap or raw-leak scan fails",
            "sampler attempts to mark rows training_allowed in this public request stage",
        ],
        "raw_content_policy": RAW_CONTENT_POLICY,
        "proof_slot_status_counts": {
            "same_source_lineage_present": 0,
            "checkout_before_anchor_present": 0,
            "patch_application_proof_present": 0,
            "same_verifier_before_after_present": 0,
            "causal_transition_present": 0,
            "stop_or_continue_label_present": 0,
            "protected_overlap_and_leak_audit_present": 0,
            "all_required_slots_present": 0,
        },
        "bucket_status_counts": {
            "config_bucket_count_from_stage12427": len(source_summary["config_counts"]),
            "trajectory_shard_count_from_stage12427": shard_count,
            "metadata_file_count_from_stage12427": source_summary["metadata_file_count"],
            "schema_file_count_from_stage12427": source_summary["schema_file_count"],
        },
        "blocked_reason_counts": {
            "public_request_only_not_training_data": 1,
            "private_sampler_required": 1,
            "no_private_raw_locator_packet_in_public_artifact": 1,
            "no_replay_or_patch_apply_run": 1,
            "no_same_verifier_before_after_proof": 1,
            "dedupe_required_before_any_future_admission": 1,
            "proof_slots_required_before_any_future_admission": 1,
        },
        "promotion_gate_status": {
            "artifact_is_public_request_only": "PASS",
            "training_allowed": "PASS_FALSE",
            "no_rows_admitted": "PASS",
            "no_rows_emitted": "PASS",
            "no_raw_rows_inspected": "PASS",
            "stage12427_safe_metadata_reused_only": "PASS" if source_ok else "BLOCKED",
            "private_sampler_not_run": "PASS",
        },
        "next_stage_recommendation": "private_open_swe_admission_packet_sampler_with_raw_material_kept_out_of_public_artifacts",
        "local_artifacts": {
            "request_packet_name_hash": stable_hash("open_swe_private_admission_packet_request.json"),
            "guardrail_scan_name_hash": stable_hash("guardrail_scan.json"),
            "sampler_contract_name_hash": stable_hash("private_sampler_contract.json"),
        },
    }
    return request


def guardrail_scan(value: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps(value, sort_keys=True)
    raw_matches = FORBIDDEN_TEXT_RE.findall(payload)
    overclaim_matches = []
    for match in OVERCLAIM_RE.finditer(payload):
        start = max(0, match.start() - 80)
        end = min(len(payload), match.end() + 80)
        context = payload[start:end]
        if not ALLOWED_OVERCLAIM_CONTEXT_RE.search(context):
            overclaim_matches.append(match.group(0))
    zero_counter_failures = [
        key
        for key, expected in ZERO_COUNTERS.items()
        if value.get(key) != expected
    ]
    raw_policy_failures = [
        key
        for key, expected in RAW_CONTENT_POLICY.items()
        if value.get("raw_content_policy", {}).get(key) != expected
    ]
    return {
        "scan_passed": not raw_matches and not overclaim_matches and not zero_counter_failures and not raw_policy_failures,
        "raw_leak_count": len(raw_matches),
        "overclaim_count": len(overclaim_matches),
        "issue_count": len(raw_matches) + len(overclaim_matches) + len(zero_counter_failures) + len(raw_policy_failures),
        "issues": (
            (["forbidden_raw_text_pattern_detected"] if raw_matches else [])
            + (["unsupported_overclaim_pattern_detected"] if overclaim_matches else [])
            + [f"nonzero_or_true_zero_counter:{key}" for key in zero_counter_failures]
            + [f"raw_content_policy_failure:{key}" for key in raw_policy_failures]
        ),
        "zero_counter_keys_checked": sorted(ZERO_COUNTERS),
        "raw_content_policy_keys_checked": sorted(RAW_CONTENT_POLICY),
    }


def main() -> None:
    stage12427 = read_json(INPUTS["stage12427_summary"])
    request = build_private_sampler_request(stage12427)
    scan = guardrail_scan(request)
    request["guardrail_scan"] = scan
    request["guardrail_scan_passed"] = scan["scan_passed"]
    request["raw_leak_count"] = scan["raw_leak_count"]
    request["overclaim_count"] = scan["overclaim_count"]
    request["summary_hash"] = stable_hash({k: v for k, v in request.items() if k != "summary_hash"})

    sampler_contract = {
        "stage": STAGE,
        "contract_type": "private_sampler_contract_public_safe_v1",
        "training_allowed": False,
        "sampler_may_read_raw_rows_only_in_private_context": True,
        "public_artifact_may_contain_raw_rows": False,
        "required_proof_slots": request["required_proof_slots"],
        "dedupe_collapse_policy": request["dedupe_collapse_policy"],
        "public_safe_output_schema": request["public_safe_output_schema"],
        "allowed_private_only_fields": request["allowed_private_only_fields"],
        "private_sampler_quotas": request["private_sampler_quotas"],
        "raw_content_policy": RAW_CONTENT_POLICY,
    }

    write_json(OUT / "open_swe_private_admission_packet_request.json", request)
    write_json(OUT / "private_sampler_contract.json", sampler_contract)
    write_json(OUT / "guardrail_scan.json", scan)
    write_json(OUT / "summary.json", request)
    write_json(SUMMARY, request)
    if not scan["scan_passed"]:
        raise SystemExit(f"guardrail scan failed with {scan['issue_count']} issues")

    print(
        json.dumps(
            {
                "stage": STAGE,
                "decision": request["decision"],
                "training_allowed": False,
                "candidate_supply_rows_from_metadata": request["private_sampler_quotas"][
                    "candidate_supply_rows_from_metadata"
                ],
                "source_shard_count_from_metadata": request["private_sampler_quotas"][
                    "source_shard_count_from_metadata"
                ],
                "guardrail_scan_passed": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

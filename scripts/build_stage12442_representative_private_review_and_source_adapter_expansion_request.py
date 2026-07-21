#!/usr/bin/env python3
"""Build Stage12442 representative review + source adapter expansion request.

This stage consumes Stage12441's public-safe embedding cluster representatives.
It does not admit rows. It creates a bounded request for private semantic review
and a separate source-adapter expansion plan because the current session-like
pool is too collapsed to scale the 100M maintainer dataset.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12442_representative_private_review_and_source_adapter_expansion_request"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12441_SUMMARY = ROOT / "runs/summaries/stage12441_embedding_transition_candidate_expansion_gate.json"
STAGE12441_REPRESENTATIVES = (
    ROOT
    / "runs/local/artifacts/stage12441_embedding_transition_candidate_expansion_gate/"
    "candidate_embedding_representative_priority_records.jsonl"
)
STAGE12441_PRIORITY = (
    ROOT
    / "runs/local/artifacts/stage12441_embedding_transition_candidate_expansion_gate/"
    "candidate_embedding_priority_records.jsonl"
)
STAGE12237 = ROOT / "runs/summaries/stage12237_current_training_control_board.json"
STAGE12248 = ROOT / "runs/summaries/stage12248_root_supply_discrepancy_audit.json"
SPINE = ROOT / "docs/UNBOUNDED_SOFTWARE_TASK_COMPLETION_SPINE_STAGE12195.md"
GOAL = ROOT / "goal.txt"

ZERO_COUNTERS: dict[str, bool | int] = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed": False,
    "emitted_training_rows": 0,
    "admitted_rows": 0,
    "level3_candidate_count": 0,
    "level4_candidate_count": 0,
    "patch_trace_candidate_count": 0,
    "sealed_eval_rows_emitted": 0,
    "countable_new_rows": 0,
}

RAW_CONTENT_POLICY = {
    "public_artifacts_raw_private_text_emitted": False,
    "public_artifacts_raw_command_values_emitted": False,
    "public_artifacts_raw_output_values_emitted": False,
    "public_artifacts_raw_diff_values_emitted": False,
    "public_artifacts_raw_patch_values_emitted": False,
    "public_artifacts_raw_source_values_emitted": False,
    "public_artifacts_raw_url_values_emitted": False,
    "public_artifacts_raw_path_values_emitted": False,
    "private_review_may_inspect_raw_refs": True,
    "private_review_must_not_mirror_raw_values_to_public_artifacts": True,
}

FORBIDDEN_PUBLIC_KEYS = {
    "path",
    "url",
    "uri",
    "command",
    "command_text",
    "stdout",
    "stderr",
    "output",
    "diff",
    "patch",
    "patch_body",
    "source",
    "source_text",
    "private_locator",
    "raw_text",
    "trace_text",
}

ALLOWED_FORBIDDEN_KEY_CONTEXT = re.compile(
    r"(policy|emitted|forbidden|required|ref|refs|hash|hashes|status|slot|slots|reason|schema|contract)",
    re.IGNORECASE,
)

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|stdout:|stderr:|stack trace|"
    r"terminal output:|command output:|git clone\s+\S|git apply\s+\S|"
    r"curl\s+\S|bash -|sh -|python -c)\b",
    re.IGNORECASE | re.MULTILINE,
)

OVERCLAIM_RE = re.compile(
    r"\b(?:admitted|training row|trainable|accepted row|verified repair|level-3 complete|"
    r"level3 complete|patch-trace complete|execution succeeded|tests passed)\b",
    re.IGNORECASE,
)

ALLOWED_OVERCLAIM_CONTEXT_RE = re.compile(
    r"(false|zero|none|blocked|request|required|future|must not|not |no |fail.closed|fail-closed|"
    r"counter|policy|guardrail|private review|source adapter|not admitted|not training)",
    re.IGNORECASE,
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def top_counts(values: list[Any], limit: int = 20) -> dict[str, int]:
    counts = Counter(str(value) for value in values)
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit])


def representative_review_packets(representatives: list[dict[str, Any]]) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for row in sorted(representatives, key=lambda item: int(item.get("representative_priority_rank") or 999999)):
        packets.append(
            {
                "review_packet_id_hash": stable_hash({"representative": row.get("candidate_id_hash")}),
                "source_stage": "stage12441_embedding_transition_candidate_expansion_gate",
                "representative_candidate_id_hash": row.get("candidate_id_hash"),
                "embedding_cluster_id_hash": row.get("embedding_cluster_id_hash"),
                "represented_candidate_count": int(row.get("represented_candidate_count") or 0),
                "representative_priority_rank": int(row.get("representative_priority_rank") or 0),
                "language_family": row.get("language_family"),
                "task_family": row.get("task_family"),
                "repo_family_hash": row.get("repo_family_hash"),
                "transition_function_key_hash": row.get("transition_function_key_hash"),
                "semantic_rule_id_hash": row.get("semantic_rule_id_hash"),
                "priority_bucket": row.get("priority_bucket"),
                "private_review_required": True,
                "public_safe_raw_refs_absent": True,
                "review_must_fill_slots": [
                    "authoritative_state_before",
                    "authoritative_state_after",
                    "observed_action_digest",
                    "policy_action_label",
                    "non_imitation_policy_action_label",
                    "candidate_action_set_semantics",
                    "counterfactual_action_set",
                    "policy_label_independence_proof",
                    "observation_status_class",
                    "verifier_relevance_proof",
                    "same_source_lineage_proof",
                    "patch_application_or_no_patch_reason",
                    "causal_verifier_linkage",
                    "state_delta_codes",
                    "stop_continue_label",
                    "protected_overlap_check",
                    "leakage_check",
                ],
                "hard_reject_if_missing": [
                    "same_source_lineage_proof",
                    "verifier_relevance_proof",
                    "non_imitation_policy_action_label",
                    "policy_label_independence_proof",
                    "counterfactual_action_set",
                    "state_delta_codes",
                    "stop_continue_label",
                ],
                "cluster_member_admission_policy": "review_representative_only_no_automatic_propagation_to_cluster_members",
                "training_allowed": False,
                "admission_allowed": False,
            }
        )
    return packets


def source_adapter_requests(stage12441: dict[str, Any]) -> list[dict[str, Any]]:
    common_slots = [
        "root_id_and_source_root_label",
        "repo_family_and_language_family",
        "ordered_events",
        "state_before_summary_codes",
        "candidate_action_set",
        "observed_action_digest",
        "policy_action_label",
        "counterfactual_action_set",
        "policy_label_independence_proof",
        "command_or_tool_observation_status",
        "patch_diff_or_explicit_no_patch_reason",
        "verifier_command_and_output_ref",
        "verifier_transition",
        "state_after_or_state_update",
        "stop_continue_label",
        "same_source_causality_proof",
        "anti_cheat_contract",
    ]
    return [
        {
            "adapter_request_id": "codex_session_private_trace_reviewer_representatives",
            "purpose": "complete private review packets for the 10 Stage12441 representative clusters before any row admission",
            "target_candidate_floor": 10,
            "target_distinct_repo_floor": 6,
            "target_language_floor": {"python": 3, "rust": 1, "c_cpp": 1, "web_js_ts_html": 1},
            "required_slots": common_slots,
            "acceptance_schema": "same_source_transition_candidate_request_v2",
            "split_policy": "derive_root_lineage_and_split_group_before_any_review_or_materialization",
            "verifier_oracle_requirement": "verifier refs must prove relevance to state/action, not broad co-presence",
            "anti_leak_policy": "public outputs emit only hashes/status/classes; raw/private values remain private",
            "blocked_until": "private_review_packets_exist_and_non_imitation_policy_labels_are_proven",
        },
        {
            "adapter_request_id": "external_repair_trace_fail_to_pass_adapter",
            "purpose": "find same-source comparable patch-effect records instead of patch/test co-presence",
            "target_candidate_floor": 75,
            "target_distinct_repo_floor": 40,
            "target_language_floor": {"python": 15, "rust": 10, "c_cpp": 10, "web_js_ts_html": 5},
            "required_status_floors": {"FAIL_TO_PASS": 25, "FAIL_TO_FAIL": 10, "NOT_EXERCISED": 10, "INSUFFICIENT_EVIDENCE": 10},
            "required_slots": common_slots,
            "acceptance_schema": "external_comparable_patch_effect_candidate_request_v2",
            "split_policy": "repo_family_lineage_time_disjoint_before_row_projection",
            "verifier_oracle_requirement": "same verifier before/after or authoritative equivalent with command/output refs",
            "anti_leak_policy": "public outputs emit only hashes/status/classes; raw/private values remain private",
            "blocked_until": "before_patch_after_patch_oracle_statuses_and_verifier_relevance_are_proven",
        },
        {
            "adapter_request_id": "selected_test_transition_root_batch_non_web_first",
            "purpose": "expand non-web selected-test/action/verifier roots without relying on tokenizers or a single benchmark family",
            "target_candidate_floor": 100,
            "target_distinct_repo_floor": 60,
            "target_language_floor": {"python": 20, "rust": 20, "c_cpp": 20, "web_js_ts_html": 0},
            "required_task_family_mix": {
                "transition_next_action": 35,
                "transition_candidate_selection": 25,
                "transition_verifier_transition": 25,
                "transition_continue_or_stop": 15,
            },
            "required_slots": common_slots,
            "acceptance_schema": "selected_test_transition_root_candidate_request_v2",
            "split_policy": "non_web_first_roots_must_be heldout_disjoint_or_dev_only_declared",
            "verifier_oracle_requirement": "selected verifier/test identity must be exact enough to distinguish exercised vs not_exercised",
            "anti_leak_policy": "public outputs emit only hashes/status/classes; raw/private values remain private",
            "blocked_until": "selected_verifier_identity_and_state_delta_are_proven",
        },
        {
            "adapter_request_id": "web_openhands_llama_private_execution_joiner",
            "purpose": "join existing executed web verifier material to canonical transition records without direct heldout leakage",
            "target_candidate_floor": 50,
            "target_distinct_repo_floor": 20,
            "target_language_floor": {"web_js_ts_html": 20},
            "required_task_family_mix": {
                "transition_next_action": 20,
                "transition_candidate_selection": 10,
                "transition_verifier_transition": 10,
                "transition_continue_or_stop": 10,
            },
            "required_slots": common_slots,
            "acceptance_schema": "web_execution_joiner_candidate_request_v2",
            "split_policy": "exclude heldout roots and benchmark identity leakage before projection",
            "verifier_oracle_requirement": "executed verifier evidence must be joined to canonical state/action records",
            "anti_leak_policy": "public outputs emit only hashes/status/classes; raw/private values remain private",
            "blocked_until": "heldout_root_overlap_and_static_pass_to_pass_shortcut_risks_are_cleared",
        },
    ]


def adapter_gap_targets(requests: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "target_stage_family": "transition_root_250_to_500_quality_supply",
        "minimum_before_training_probe": {
            "admitted_level3_roots": 150,
            "admitted_level3_rows": 500,
            "external_comparable_patch_trace_rows": 25,
            "external_fail_to_pass_rows": 15,
            "non_python_external_repair_rows": 10,
            "sealed_root_disjoint_transition_eval_rows": 100,
        },
        "adapter_request_count": len(requests),
        "adapter_candidate_floor_total": sum(int(req.get("target_candidate_floor") or 0) for req in requests),
        "quality_rule": "new volume must increase same-source proof slots, not metadata projections or observed-action imitation rows",
    }


def scan_payload(label: str, payload: Any) -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not ALLOWED_FORBIDDEN_KEY_CONTEXT.search(label):
        issues.append(f"{label}:forbidden_public_key:{stable_hash(leaf)}")
    if isinstance(payload, str):
        if RAW_LEAK_RE.search(payload):
            issues.append(f"{label}:raw_leak:{stable_hash(payload)}")
        for match in OVERCLAIM_RE.finditer(payload):
            start = max(0, match.start() - 80)
            end = min(len(payload), match.end() + 80)
            context = payload[start:end]
            if not ALLOWED_OVERCLAIM_CONTEXT_RE.search(context):
                issues.append(f"{label}:overclaim:{stable_hash(context)}")
    elif isinstance(payload, dict):
        for key, value in payload.items():
            issues.extend(scan_payload(f"{label}.{key}", value))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            issues.extend(scan_payload(f"{label}[{index}]", value))
    return issues


def build_artifact() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    stage12441 = read_json(STAGE12441_SUMMARY)
    representatives = read_jsonl(STAGE12441_REPRESENTATIVES)
    priority_records = read_jsonl(STAGE12441_PRIORITY)
    packets = representative_review_packets(representatives)
    adapter_requests = source_adapter_requests(stage12441)
    gaps = adapter_gap_targets(adapter_requests)

    represented_total = sum(int(row.get("represented_candidate_count") or 0) for row in representatives)
    language_counts = top_counts([row.get("language_family") for row in representatives])
    task_counts = top_counts([row.get("task_family") for row in representatives])
    priority_counts = top_counts([row.get("priority_bucket") for row in representatives])
    fail_closed_gate_status = {
        "stage12441_guardrail_required_and_present": stage12441.get("guardrail_scan_passed") is True,
        "representative_count_matches_stage12441": len(representatives) == int(stage12441.get("representative_priority_queue_count") or -1),
        "represented_total_matches_stage12441_vectors": represented_total == int(stage12441.get("candidate_vector_count") or -1),
        "expansion_queue_uses_collapsed_representatives": int(stage12441.get("expansion_priority_queue_count") or -1) == len(representatives),
        "training_blocked": True,
        "admission_blocked": True,
        "execution_blocked": True,
    }
    artifact = {
        "stage": STAGE,
        "record_type": "representative_private_review_and_source_adapter_expansion_request_public_safe_v1",
        "decision": "fail_closed_review_and_adapter_expansion_request_ready",
        **ZERO_COUNTERS,
        "source_context_hashes": {
            "goal_txt_sha256_24": file_hash(GOAL),
            "stage12195_spine_sha256_24": file_hash(SPINE),
            "stage12237_summary_sha256_24": file_hash(STAGE12237),
            "stage12248_summary_sha256_24": file_hash(STAGE12248),
            "stage12441_summary_sha256_24": file_hash(STAGE12441_SUMMARY),
        },
        "stage12441_inputs": {
            "candidate_vector_count": stage12441.get("candidate_vector_count"),
            "full_candidate_priority_queue_count": stage12441.get("full_candidate_priority_queue_count"),
            "representative_priority_queue_count": stage12441.get("representative_priority_queue_count"),
            "collapsed_duplicate_candidate_count": stage12441.get("collapsed_duplicate_candidate_count"),
            "near_duplicate_cluster_max_share": stage12441.get("near_duplicate_cluster_max_share"),
            "novelty_bucket_counts": stage12441.get("novelty_bucket_counts"),
            "embedding_use_policy": stage12441.get("embedding_use_policy"),
            "similarity_use_policy": stage12441.get("similarity_use_policy"),
        },
        "representative_priority_queue_count": len(representatives),
        "non_admissible_represented_candidate_metadata_count": represented_total,
        "represented_candidate_count_total": represented_total,
        "full_priority_record_count": len(priority_records),
        "non_admissible_collapsed_duplicate_candidate_count": max(0, len(priority_records) - len(representatives)),
        "collapsed_duplicate_candidate_count": max(0, len(priority_records) - len(representatives)),
        "countable_training_supply_delta": 0,
        "admissible_rows_from_this_stage": 0,
        "requested_not_materialized_count": len(packets) + len(adapter_requests),
        "private_review_packet_requested_count": len(packets),
        "private_review_packet_ready_count": 0,
        "review_accepted_representative_count": 0,
        "review_rejected_representative_count": 0,
        "review_deferred_representative_count": 0,
        "represented_candidates_unlocked_by_accepted_representatives": 0,
        "policy_label_valid_count": 0,
        "observed_action_imitation_rejected_count": 0,
        "state_delta_correct_count": 0,
        "stop_decision_correct_count": 0,
        "verifier_relevance_pass_count": 0,
        "same_source_lineage_pass_count": 0,
        "new_source_adapter_request_count": len(adapter_requests),
        "similarity_derived_review_queue_count": len(representatives),
        "similarity_derived_materialization_count": 0,
        "similarity_derived_admission_count": 0,
        "target_adapter_candidate_floor": gaps["adapter_candidate_floor_total"],
        "target_distinct_repo_floor": 120,
        "target_language_floor": {"python": 38, "rust": 31, "c_cpp": 31, "web_js_ts_html": 25},
        "representative_cluster_coverage_counts": {
            "language_family": language_counts,
            "task_family": task_counts,
            "priority_bucket": priority_counts,
            "represented_candidate_count_top": sorted([int(row.get("represented_candidate_count") or 0) for row in representatives], reverse=True)[:10],
        },
        "private_review_required_slots_path": "runs/local/artifacts/stage12442_representative_private_review_and_source_adapter_expansion_request/private_review_required_slots.json",
        "representative_private_review_packet_manifest_path": "runs/local/artifacts/stage12442_representative_private_review_and_source_adapter_expansion_request/representative_private_review_packet_manifest.jsonl",
        "source_adapter_expansion_request_path": "runs/local/artifacts/stage12442_representative_private_review_and_source_adapter_expansion_request/source_adapter_expansion_request.json",
        "adapter_gap_targets_path": "runs/local/artifacts/stage12442_representative_private_review_and_source_adapter_expansion_request/adapter_gap_targets.json",
        "fail_closed_gate_status": fail_closed_gate_status,
        "hard_gate_blockers": [
            "private_review_packet_ready_zero",
            "policy_label_valid_zero",
            "same_source_lineage_pass_zero",
            "verifier_relevance_pass_zero",
            "state_delta_correct_zero",
            "stop_decision_correct_zero",
            "level3_admission_blocked",
            "source_adapter_expansion_not_yet_materialized",
        ],
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": "public-safe request only; similarity creates a review queue, not materialization/admission/training supply; representative review and adapter expansion are requested but no rows are admitted or emitted for training",
        "summary_hash": "pending",
    }
    private_review_required_slots = {
        "review_packet_count": len(packets),
        "global_required_slots": packets[0]["review_must_fill_slots"] if packets else [],
        "global_hard_reject_if_missing": packets[0]["hard_reject_if_missing"] if packets else [],
        "policy_label_rule": "policy labels must describe the best maintainer action under state, not merely the observed next action family",
        "cluster_rule": "accepting a representative does not admit unreviewed cluster members",
    }
    guardrail_payload = {
        "main": artifact,
        "representative_private_review_packet_manifest": packets,
        "private_review_required_slots": private_review_required_slots,
        "source_adapter_expansion_request": adapter_requests,
        "adapter_gap_targets": gaps,
        "fail_closed_gate_status": fail_closed_gate_status,
    }
    issues: list[str] = []
    for name, payload in guardrail_payload.items():
        issues.extend(scan_payload(name, payload))
    for key, expected in ZERO_COUNTERS.items():
        if artifact.get(key) != expected:
            issues.append(f"zero_counter_mismatch:{key}")
    if not all(fail_closed_gate_status.values()):
        issues.append("fail_closed_gate_status_not_all_true")
    if artifact.get("similarity_derived_materialization_count") != 0:
        issues.append("similarity_materialization_authority_violation")
    if artifact.get("similarity_derived_admission_count") != 0:
        issues.append("similarity_admission_authority_violation")
    if artifact.get("countable_training_supply_delta") != 0 or artifact.get("admissible_rows_from_this_stage") != 0:
        issues.append("request_stage_countable_supply_violation")
    if len(representatives) != int(stage12441.get("representative_priority_queue_count") or -1):
        issues.append("stage12441_representative_count_mismatch")
    if represented_total != int(stage12441.get("candidate_vector_count") or -1):
        issues.append("stage12441_represented_total_mismatch")
    guardrail = {
        "scan_passed": not issues,
        "issue_count": len(set(issues)),
        "issues": sorted(set(issues)),
        "raw_leak_count": len({issue for issue in issues if ":raw_leak:" in issue}),
        "overclaim_count": len({issue for issue in issues if ":overclaim:" in issue}),
        "scan_scope": "stage12442_public_safe_request_artifacts",
    }
    artifact["guardrail_scan"] = guardrail
    artifact["guardrail_scan_passed"] = guardrail["scan_passed"]
    artifact["raw_leak_count"] = guardrail["raw_leak_count"]
    artifact["overclaim_count"] = guardrail["overclaim_count"]
    artifact["summary_hash"] = stable_hash({k: v for k, v in artifact.items() if k != "summary_hash"})
    return artifact, packets, private_review_required_slots, adapter_requests, gaps


def main() -> None:
    artifact, packets, private_review_required_slots, adapter_requests, gaps = build_artifact()
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / f"{STAGE}.json", artifact)
    write_json(OUT / "summary.json", artifact)
    write_json(SUMMARY, artifact)
    write_jsonl(OUT / "representative_private_review_packet_manifest.jsonl", packets)
    write_json(OUT / "representative_cluster_coverage_counts.json", artifact["representative_cluster_coverage_counts"])
    write_json(OUT / "private_review_required_slots.json", private_review_required_slots)
    write_json(OUT / "source_adapter_expansion_request.json", adapter_requests)
    write_json(OUT / "adapter_gap_targets.json", gaps)
    write_json(OUT / "fail_closed_gate_status.json", artifact["fail_closed_gate_status"])
    write_json(OUT / "guardrail_scan.json", artifact["guardrail_scan"])
    print(json.dumps({
        "stage": artifact["stage"],
        "decision": artifact["decision"],
        "representative_priority_queue_count": artifact["representative_priority_queue_count"],
        "represented_candidate_count_total": artifact["represented_candidate_count_total"],
        "private_review_packet_requested_count": artifact["private_review_packet_requested_count"],
        "new_source_adapter_request_count": artifact["new_source_adapter_request_count"],
        "target_adapter_candidate_floor": artifact["target_adapter_candidate_floor"],
        "training_allowed": artifact["training_allowed"],
        "admission_allowed": artifact["admission_allowed"],
        "guardrail_scan_passed": artifact["guardrail_scan_passed"],
        "raw_leak_count": artifact["raw_leak_count"],
        "overclaim_count": artifact["overclaim_count"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

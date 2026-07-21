#!/usr/bin/env python3
"""Spine-grounded control board for the causal-transition proof lane."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12477_causal_transition_next_action_control_board"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

INPUTS = {
    "goal": ROOT / "goal.txt",
    "spine_stage12195": ROOT / "docs/UNBOUNDED_SOFTWARE_TASK_COMPLETION_SPINE_STAGE12195.md",
    "stage12237": ROOT / "runs/summaries/stage12237_current_training_control_board.json",
    "stage12248": ROOT / "runs/summaries/stage12248_root_supply_discrepancy_audit.json",
    "stage12468": ROOT / "runs/summaries/stage12468_non_bears_patch_effect_private_return_validator.json",
    "stage12474": ROOT / "runs/summaries/stage12474_private_executor_request_contract.json",
    "stage12475": ROOT / "runs/summaries/stage12475_private_executor_return_status_audit.json",
    "stage12476": ROOT / "runs/summaries/stage12476_cpp_locator_gap_recovery_preflight.json",
    "stage12480": ROOT / "runs/summaries/stage12480_private_cpp_locator_sidecar_materializer_request.json",
    "stage12481": ROOT / "runs/summaries/stage12481_private_return_materialization_attempt.json",
    "stage12483": ROOT / "runs/summaries/stage12483_private_proof_bundle_acquisition_work_order.json",
}
LOCAL_SUMMARY_OUT = OUT_DIR / "summary.json"
ACTION_QUEUE_OUT = OUT_DIR / "causal_transition_action_queue.jsonl"
STOP_GATES_OUT = OUT_DIR / "training_stop_gates.json"
GUARDRAIL_OUT = OUT_DIR / "guardrail_scan.json"

EXPECTED_GAP = 15
FALSE_GUARDS = {
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "execution_performed_by_stage": False,
    "hydration_performed_by_stage": False,
    "replay_performed_by_stage": False,
    "network_performed_by_stage": False,
}
ZERO_GUARDS = {
    "emitted_training_rows": 0,
    "sealed_eval_rows": 0,
    "external_comparable_repair_credit_count": 0,
}
FORBIDDEN_PUBLIC_KEYS = {
    "body", "cmd", "command", "commands", "commit", "commit_sha", "content",
    "diff", "file_content", "file_path", "patch", "patch_body", "path",
    "paths", "raw", "raw_content", "raw_text", "repo", "repo_id",
    "repo_name", "repository", "sha", "source", "source_text", "stderr",
    "stdout", "text", "uri", "uris", "url", "urls",
}
PUBLIC_SAFE_KEY_RE = re.compile(
    r"(hash|hashes|ref|refs|id|ids|stage|schema|slot|slots|status|family|"
    r"lane|guardrail|issue|reason|count|policy|allowed|proof|return|artifact|"
    r"locator|candidate|context|label|input|excluded|request|contract|pending|file|"
    r"queue|gate|action|board|metric|credit|spine|goal|decision)",
    re.IGNORECASE,
)
RAW_LEAK_RE = re.compile(
    r"https?://|www\\.|diff --git|@@ |^\\+\\+\\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\\b(?:git clone|git apply|pytest\\s|python -c|bash -|sh -|curl\\s|"
    r"stdout|stderr|traceback|terminal output|command output)\\b|"
    r"\\b[0-9a-f]{40}\\b|"
    r"\\b(?:Open-SWE|RepairThemAll|SakanaAI|SWE-Hero|SWE-Zero)\\b",
    re.IGNORECASE | re.MULTILINE,
)


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"_missing": True}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"_invalid_json": True}
    return value if isinstance(value, dict) else {"_not_object": True}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def public_scan(label: str, value: Any) -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not PUBLIC_SAFE_KEY_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_content_pattern:{stable_hash(value)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(public_scan(f"{label}.{key}", child))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            issues.extend(public_scan(f"{label}[{idx}]", child))
    return issues


def main() -> int:
    summaries = {name: read_json(path) if path.suffix == ".json" else {} for name, path in INPUTS.items()}
    hashes = {name: file_hash(path) for name, path in INPUTS.items()}

    stage12468 = summaries["stage12468"]
    stage12474 = summaries["stage12474"]
    stage12475 = summaries["stage12475"]
    stage12476 = summaries["stage12476"]
    stage12480 = summaries.get("stage12480", {})
    stage12481 = summaries.get("stage12481", {})
    stage12483 = summaries.get("stage12483", {})

    pending_returns = int(stage12475.get("pending_private_executor_request_item_count", 0) or 0)
    return_file_exists = bool(stage12475.get("private_return_file_exists", False))
    cpp_gap = int(stage12476.get("c_cpp_locator_gaps_seen", stage12474.get("c_cpp_locator_gap", 0)) or 0)
    cpp_locator_refs = int(stage12476.get("locator_refs_emitted", 0) or 0)
    current_credit = int(stage12468.get("external_comparable_repair_credit_count", 0) or 0)
    materialization_blockers = int(stage12481.get("materialization_blocker_count", 0) or 0)
    validator_complete_candidates = int(stage12481.get("validator_complete_return_candidate_count", 0) or 0)
    proof_bundle_work_items = int(stage12483.get("proof_bundle_work_item_count", 0) or 0)

    action_queue = [
        {
            "priority": 1,
            "action_id": "acquire_full_stage12468_proof_bundles_for_stage12474_refs",
            "action_type": "private_proof_bundle_acquisition",
            "input_stage_ref": "stage12483_private_proof_bundle_acquisition_work_order",
            "request_ref_count": pending_returns,
            "success_gate": "stage12468_validator_complete_return_count_increases",
            "failure_mode_to_avoid": "locator_sidecar_or_fill_packet_treated_as_proof_bundle",
            "public_output_policy": "hash_status_only_no_raw_locator_or_command_material",
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        },
        {
            "priority": 2,
            "action_id": "rerun_stage12468_after_private_returns_exist",
            "action_type": "validator_revalidation",
            "input_stage_ref": "stage12468_non_bears_patch_effect_private_return_validator",
            "blocked_until_private_return_file_exists": not return_file_exists,
            "success_gate": "proof_complete_true_and_all_required_slots_present_with_valid_hashes",
            "failure_mode_to_avoid": "metadata_only_or_pass_to_pass_claim_counted_as_fail_to_pass",
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        },
        {
            "priority": 3,
            "action_id": "materialize_private_cpp_locator_sidecars_for_stage12480_requests",
            "action_type": "private_locator_sidecar_materialization",
            "input_stage_ref": "stage12480_private_cpp_locator_sidecar_materializer_request",
            "c_cpp_locator_gap_count": cpp_gap,
            "current_cpp_locator_refs_emitted": cpp_locator_refs,
            "success_gate": "public_safe_cpp_locator_refs_exist_then_rerun_stage12472_12473_path",
            "failure_mode_to_avoid": "metadata_profile_or_sidecar_template_count_treated_as_locator_or_proof",
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        },
        {
            "priority": 4,
            "action_id": "build_admitted_level3_transition_rows_only_after_stage12468_credit",
            "action_type": "training_data_admission_after_proof",
            "blocked_until_external_credit_positive": current_credit <= 0,
            "success_gate": "same_source_state_action_observation_verifier_state_delta_stop_continue_tuple_present",
            "failure_mode_to_avoid": "candidate_or_projection_rows_promoted_to_closed_loop_training",
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        },
    ]

    stop_gates = {
        "stage": STAGE,
        "record_type": "stage12477_training_stop_gates_v1",
        "training_must_remain_blocked": True,
        "reasons": [
            "stage12468_external_comparable_repair_credit_count_is_zero",
            "stage12475_private_proof_slot_return_file_missing",
            "stage12480_cpp_public_locator_refs_emitted_is_zero",
            "stage12481_validator_complete_return_candidate_count_is_zero",
            "stage12481_materialization_blockers_show_locator_sidecars_are_not_proof_bundles",
            "stage12483_proof_bundle_work_order_ready_but_not_executed",
            "level3_training_tuple_not_admitted_from_validator_complete_returns",
        ],
        "minimum_to_unblock_admission_planning": {
            "stage12468_validator_complete_return_count_min": 1,
            "stage12468_external_comparable_repair_credit_count_min": 1,
            "all_public_guardrails_raw_leak_count": 0,
            "state_action_observation_verifier_state_delta_stop_continue_tuple_required": True,
        },
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
    }

    summary = {
        "stage": STAGE,
        "record_type": "stage12477_causal_transition_next_action_control_board_summary_v1",
        "decision": "training_blocked_next_actions_are_private_returns_and_cpp_locators",
        "claim_boundary": "Control board only. It emits no training rows, executes nothing, and awards no proof credit.",
        "spine_alignment": {
            "goal_ref_hash": hashes["goal"],
            "unbounded_spine_ref_hash": hashes["spine_stage12195"],
            "training_control_board_ref_hash": hashes["stage12237"],
            "root_supply_audit_ref_hash": hashes["stage12248"],
            "current_blocker": "same_source_validator_complete_external_repair_returns_missing",
        },
        "current_counters": {
            "stage12468_external_comparable_repair_credit_count": current_credit,
            "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
            "stage12474_private_executor_request_item_count": stage12474.get("private_executor_request_item_count", 0),
            "stage12475_pending_private_executor_request_item_count": pending_returns,
            "stage12475_private_return_file_exists": return_file_exists,
            "stage12476_c_cpp_locator_gaps_seen": cpp_gap,
            "stage12476_cpp_locator_refs_emitted": cpp_locator_refs,
            "stage12476_cpp_recovery_request_refs_emitted": stage12476.get("request_refs_emitted", 0),
            "stage12480_cpp_sidecar_fill_request_count": stage12480.get("sidecar_fill_request_count", 0),
            "stage12481_validator_complete_return_candidate_count": validator_complete_candidates,
            "stage12481_materialization_blocker_count": materialization_blockers,
            "stage12483_proof_bundle_work_item_count": proof_bundle_work_items,
        },
        "next_stage_recommendations": [row["action_id"] for row in action_queue[:3]],
        "active_work_order_stage": "stage12483_private_proof_bundle_acquisition_work_order",
        "action_queue_count": len(action_queue),
        "training_allowed": False,
        "admission_allowed": False,
        "artifact_refs": {
            "causal_transition_action_queue": "stage12477_causal_transition_action_queue_jsonl",
            "training_stop_gates": "stage12477_training_stop_gates_json",
            "guardrail_scan": "stage12477_guardrail_scan_json",
            "local_summary": "stage12477_local_summary_json",
            "summary": "stage12477_summary_json",
        },
        "input_artifact_hashes": hashes,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
    }

    public_payload = {"summary": summary, "action_queue": action_queue, "stop_gates": stop_gates}
    scan_issues = public_scan("stage12477_public_artifacts", public_payload)
    guardrail = {
        "stage": STAGE,
        "record_type": "stage12477_guardrail_scan_v1",
        "scan_passed": not scan_issues,
        "raw_leak_count": len(scan_issues),
        "issue_hashes": [stable_hash(issue) for issue in scan_issues[:50]],
        "policy": "no_raw_paths_urls_commands_shas_repo_names_diffs_stdout_stderr_or_source",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
    }
    if scan_issues:
        summary["decision"] = "blocked_public_guardrail_scan_failed_zero_credit"
    summary["guardrail_scan_passed"] = guardrail["scan_passed"]
    summary["raw_leak_count"] = guardrail["raw_leak_count"]
    summary["schema_issue_count"] = 0 if guardrail["scan_passed"] else len(scan_issues)
    summary["summary_hash"] = stable_hash({
        "decision": summary["decision"],
        "current_counters": summary["current_counters"],
        "raw_leak_count": summary["raw_leak_count"],
    })

    write_jsonl(ACTION_QUEUE_OUT, action_queue)
    write_json(STOP_GATES_OUT, stop_gates)
    write_json(GUARDRAIL_OUT, guardrail)
    write_json(LOCAL_SUMMARY_OUT, summary)
    write_json(SUMMARY_OUT, summary)
    print(json.dumps({
        "stage": STAGE,
        "decision": summary["decision"],
        "stage12468_external_comparable_repair_credit_count": current_credit,
        "pending_private_executor_request_item_count": pending_returns,
        "private_return_file_exists": return_file_exists,
        "c_cpp_locator_gaps_seen": cpp_gap,
        "cpp_locator_refs_emitted": cpp_locator_refs,
        "training_allowed": False,
        "guardrail_scan_passed": summary["guardrail_scan_passed"],
        "raw_leak_count": summary["raw_leak_count"],
    }, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

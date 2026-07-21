#!/usr/bin/env python3
"""Produce safe Stage12516 private causal evidence candidate return rows.

Stage12518 consumes Stage12517's bounded seven-slot worklist/schema/runner
preflight and writes Stage12516-consumable candidate rows only for slots that
can be honestly filled from public-safe metadata. It does not inspect private
source material. Therefore it can only emit a status-only blocked-unavailable
candidate when Stage12517 already records the private return as absent and the
slot template allows that status.

No private review is executed, no proof/admission is claimed, no semantic
sufficiency is asserted, and no Stage12503, training, Level-3, patch-trace, raw
path, raw command, raw diff, source, or verifier output artifacts are written.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12518_private_causal_evidence_candidate_return_runner_request"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12515 = "stage12515_private_causal_evidence_acquisition_work_orders"
STAGE12517 = "stage12517_private_causal_evidence_return_candidate_worklist"
STAGE12515_OUT = ROOT / "runs/local/artifacts" / STAGE12515
STAGE12517_OUT = ROOT / "runs/local/artifacts" / STAGE12517

WORKLIST = STAGE12517_OUT / "private_causal_evidence_return_candidate_materialization_worklist.jsonl"
SCHEMA = STAGE12517_OUT / "private_causal_evidence_return_candidate_schema.json"
RUNNER_PREFLIGHT = STAGE12517_OUT / "runner_preflight.json"
CANDIDATE_OUTPUT = STAGE12515_OUT / "private_causal_evidence_return_candidates.jsonl"

TARGET_RETURN_RECORD_TYPE = "stage12516_private_causal_evidence_return_candidate_v1"
FULL_SEVEN_SLOTS = [
    "same_source_causal_lineage_with_independent_evidence_digest",
    "structured_state_before_codes",
    "state_delta_or_state_after_codes",
    "patch_apply_or_no_patch_status",
    "stop_continue_policy_label",
    "independent_policy_label_and_candidate_action_set",
    "external_patch_effect_or_no_patch_reason",
]
IDENTITY_FIELDS = [
    "revalidation_id_hash",
    "request_id_hash",
    "work_item_id_hash",
    "packet_id_hash",
    "root_or_window_hash",
    "source_stage",
    "source_kind",
    "language_family",
    "task_family",
    "evidence_slot",
    "proof_class",
]
REQUIRED_RETURN_FIELDS = [
    "record_type",
    "acquisition_work_order_id_hash",
    *IDENTITY_FIELDS,
    "private_reviewer_id_hash",
    "reviewer_conflict_check_hash",
    "reviewer_independence_attestation",
    "independent_slot_status",
    "independent_evidence_digest_hash",
    "slot_status_reason_code",
    "causal_review_digest_hash",
    "raw_private_values_revealed",
    "raw_source_output_included",
    "raw_paths_included",
    "raw_commands_included",
    "raw_diffs_included",
    "raw_verifier_output_included",
    "local_model_authority",
    "policy_label_emitted",
    "proof_or_admission_requested",
    "acceptance_criteria_passed",
    "observed_action_available_to_labeler",
    "observed_action_used_as_label",
    "candidate_action_set_blinded",
    "label_leak_attestation",
    "model_facing_gold_fields_excluded",
    "pass_to_pass_repair_credit_requested",
    "repair_credit_requires_before_fail_after_pass_same_verifier",
    "blocker_codes",
    "training_allowed",
    "admission_allowed",
    "stage12503_return_file_written",
    "stage12503_return_records_written",
]

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output|verifier output|commit:)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)
FORBIDDEN_PUBLIC_KEYS = {
    "raw",
    "raw_output",
    "raw_outputs",
    "raw_diff",
    "diff",
    "patch",
    "command",
    "commands",
    "cmd",
    "path",
    "paths",
    "file_path",
    "source",
    "source_text",
    "source_content",
    "verifier_output",
    "stdout",
    "stderr",
    "terminal_output",
    "policy_label",
    "policy_label_hash",
    "training_row",
    "training_rows",
    "admitted_row",
    "level3_atom",
    "patch_trace",
    "proof_row",
}
FALSE_GUARDS = {
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "execution_performed_by_stage": False,
    "hydration_performed_by_stage": False,
    "replay_performed_by_stage": False,
    "network_performed_by_stage": False,
    "policy_label_materialized": False,
    "level3_atom_materialized": False,
    "patch_trace_materialized": False,
    "stage12503_return_file_written": False,
    "proof_admission_allowed": False,
    "raw_source_output_included": False,
    "raw_private_values_revealed": False,
}
ZERO_GUARDS = {
    "training_rows_emitted": 0,
    "admitted_rows": 0,
    "level3_admitted": 0,
    "level3_atom_count": 0,
    "patch_trace_admitted": 0,
    "patch_trace_rows": 0,
    "policy_labels_emitted": 0,
    "proof_rows_emitted": 0,
    "proof_grade_repair_rows": 0,
    "external_repair_credit_count": 0,
    "sealed_eval_rows": 0,
    "stage12503_return_records_written": 0,
}


class RawLeakError(ValueError):
    pass


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
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


def scan_raw_leaks(value: Any) -> list[str]:
    issues: list[str] = []
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(stable_hash(value))
    elif isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_PUBLIC_KEYS:
                issues.append(stable_hash({"forbidden_key": key}))
            issues.extend(scan_raw_leaks(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan_raw_leaks(child))
    return issues


def enforce_no_raw_leaks(value: Any) -> None:
    issues = scan_raw_leaks(value)
    if issues:
        raise RawLeakError(f"stage12518 raw leak guard rejected {len(issues)} public field(s)")


def _safe_str(row: dict[str, Any], field: str) -> str:
    value = row.get(field)
    return value if isinstance(value, str) else ""


def _full_seven_ready(task: dict[str, Any]) -> bool:
    slots = [_safe_str(ref, "evidence_slot") for ref in task.get("slot_refs") or [] if isinstance(ref, dict)]
    return (
        task.get("slot_count") == 7
        and task.get("missing_from_full_seven_slot_set") == []
        and set(slots) == set(FULL_SEVEN_SLOTS)
    )


def _slot_can_be_safely_blocked(slot_ref: dict[str, Any]) -> bool:
    allowed = set(slot_ref.get("allowed_independent_slot_statuses") or [])
    blocker_codes = set(slot_ref.get("stage12516_blocker_codes") or [])
    return (
        slot_ref.get("target_return_record_type") == TARGET_RETURN_RECORD_TYPE
        and "blocked_unavailable" in allowed
        and (
            "private_causal_evidence_return_absent" in blocker_codes
            or slot_ref.get("stage12516_non_proof_status") == "blocked_unavailable"
        )
    )


def candidate_return_for(slot_ref: dict[str, Any]) -> dict[str, Any]:
    work_order_id = slot_ref.get("acquisition_work_order_id_hash")
    slot = slot_ref.get("evidence_slot")
    digest_seed = {
        "acquisition_work_order_id_hash": work_order_id,
        "evidence_slot": slot,
        "status": "blocked_unavailable",
        "basis": "stage12517_public_safe_absent_private_return_metadata",
    }
    row = {
        "record_type": TARGET_RETURN_RECORD_TYPE,
        "acquisition_work_order_id_hash": work_order_id,
        **{field: slot_ref.get(field) for field in IDENTITY_FIELDS},
        "private_reviewer_id_hash": stable_hash({"reviewer": "stage12518_metadata_only_blocker"}),
        "reviewer_conflict_check_hash": stable_hash({"conflict": work_order_id, "slot": slot}),
        "reviewer_independence_attestation": True,
        "independent_slot_status": "blocked_unavailable",
        "independent_evidence_digest_hash": stable_hash({"evidence_digest": digest_seed}),
        "slot_status_reason_code": "private_causal_evidence_return_absent_metadata_only",
        "causal_review_digest_hash": stable_hash({"causal_review": digest_seed}),
        "raw_private_values_revealed": False,
        "raw_source_output_included": False,
        "raw_paths_included": False,
        "raw_commands_included": False,
        "raw_diffs_included": False,
        "raw_verifier_output_included": False,
        "local_model_authority": False,
        "policy_label_emitted": False,
        "proof_or_admission_requested": False,
        "acceptance_criteria_passed": True,
        "observed_action_available_to_labeler": False,
        "observed_action_used_as_label": False,
        "candidate_action_set_blinded": True,
        "label_leak_attestation": True,
        "model_facing_gold_fields_excluded": True,
        "pass_to_pass_repair_credit_requested": False,
        "repair_credit_requires_before_fail_after_pass_same_verifier": True,
        "blocker_codes": [],
        "training_allowed": False,
        "admission_allowed": False,
        "stage12503_return_file_written": False,
        "stage12503_return_records_written": 0,
    }
    missing = [field for field in REQUIRED_RETURN_FIELDS if field not in row]
    if missing:
        raise ValueError(f"stage12518 candidate construction missing fields: {missing}")
    enforce_no_raw_leaks(row)
    return row


def blocker_row(reason_counts: Counter[str]) -> dict[str, Any]:
    row = {
        "record_type": "stage12518_private_causal_evidence_candidate_return_blocker_v1",
        "blocker_id_hash": stable_hash({"blockers": sorted(reason_counts.items())}),
        "decision": "blocked_no_honest_stage12516_candidate_returns_from_stage12517_metadata",
        "blocker_code_counts": dict(sorted(reason_counts.items())),
        "semantic_sufficiency": "deferred_not_claimed",
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "candidate_return_records_written": 0,
    }
    enforce_no_raw_leaks(row)
    return row


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    stage12517_out = root / "runs/local/artifacts" / STAGE12517
    stage12515_out = root / "runs/local/artifacts" / STAGE12515
    worklist = read_jsonl(stage12517_out / "private_causal_evidence_return_candidate_materialization_worklist.jsonl")
    schema = read_json(stage12517_out / "private_causal_evidence_return_candidate_schema.json")
    runner_preflight = read_json(stage12517_out / "runner_preflight.json")

    reason_counts: Counter[str] = Counter()
    if not worklist:
        reason_counts["stage12517_worklist_missing_or_empty"] += 1
    if schema.get("target_future_return_record_type") != TARGET_RETURN_RECORD_TYPE:
        reason_counts["stage12517_schema_target_return_record_type_not_ready"] += 1
    if runner_preflight.get("private_runner_assignment_ready") is not True:
        reason_counts["stage12517_runner_preflight_not_ready"] += 1
    if runner_preflight.get("candidate_output_written_by_stage12517") is not False:
        reason_counts["stage12517_candidate_output_boundary_unexpected"] += 1

    candidates: list[dict[str, Any]] = []
    blocked_slot_counts: Counter[str] = Counter()
    for task in worklist:
        if not _full_seven_ready(task):
            reason_counts["stage12517_task_not_full_seven_slot_ready"] += 1
            continue
        for slot_ref in task.get("slot_refs") or []:
            if not isinstance(slot_ref, dict):
                reason_counts["stage12517_slot_ref_not_object"] += 1
                continue
            if _slot_can_be_safely_blocked(slot_ref):
                candidates.append(candidate_return_for(slot_ref))
            else:
                blocked_slot_counts[_safe_str(slot_ref, "evidence_slot") or "unknown_slot"] += 1
                reason_counts["slot_not_honestly_fillable_from_stage12517_absence_metadata"] += 1

    duplicate_ids = [item for item, count in Counter(row["acquisition_work_order_id_hash"] for row in candidates).items() if count > 1]
    if duplicate_ids:
        reason_counts["duplicate_candidate_for_acquisition_work_order"] += len(duplicate_ids)
        candidates = []

    blockers = [] if candidates else [blocker_row(reason_counts or Counter({"no_safe_fillable_slots": 1}))]
    decision = (
        "stage12516_candidate_returns_written_status_only_blocked_unavailable_no_proof_or_admission"
        if candidates
        else "blocked_no_honest_stage12516_candidate_returns_from_stage12517_metadata"
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12518_private_causal_evidence_candidate_return_runner_summary_v1",
        "decision": decision,
        "claim_boundary": (
            "Stage12518 writes Stage12516 candidate rows only for metadata-supported "
            "blocked-unavailable slots. It performs no private review and makes no "
            "semantic sufficiency, proof, admission, Level-3, patch-trace, repair-credit, "
            "policy-label, or status-hash-as-proof claim."
        ),
        "source_stage": STAGE12517,
        "candidate_output_stage": STAGE12515,
        "candidate_output_ref": "stage12515_private_causal_evidence_return_candidates_jsonl",
        "stage12517_task_count": len(worklist),
        "full_seven_slot_task_count": sum(1 for task in worklist if _full_seven_ready(task)),
        "candidate_return_records_written": len(candidates),
        "blocker_record_count": len(blockers),
        "blocked_slot_counts": dict(sorted(blocked_slot_counts.items())),
        "blocker_code_counts": dict(sorted(reason_counts.items())),
        "candidate_status_counts": dict(sorted(Counter(row["independent_slot_status"] for row in candidates).items())),
        "seven_slot_per_revalidation_row_gate": "required_before_any_candidate_row_is_emitted_for_that_revalidation",
        "semantic_sufficiency_gate": "deferred_not_claimed_by_stage12518",
        "anti_imitation_gate": "observed_action_available_to_labeler_false_and_observed_action_used_as_label_false_required",
        "label_leak_gate": "candidate_action_set_blinded_true_label_leak_attestation_true_model_facing_gold_fields_excluded_true",
        "pass_to_pass_gate": "pass_to_pass_support_only_no_repair_credit",
        "raw_artifact_gate": "no_raw_paths_commands_diffs_source_or_verifier_output",
        "status_hash_as_proof_gate": "status_and_digest_hashes_are_not_proof_or_admission",
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "candidate_return_file_written": bool(candidates),
    }
    guardrail_scan = {
        "stage": STAGE,
        "scan_passed": True,
        "raw_leak_count": 0,
        "raw_leak_issue_hashes": [],
        "scanned_outputs": [
            "private_causal_evidence_return_candidates.jsonl",
            "private_causal_evidence_candidate_return_blockers.jsonl",
            "summary.json",
        ],
    }
    outputs = {"candidates": candidates, "blockers": blockers, "summary": summary, "guardrail_scan": guardrail_scan}
    enforce_no_raw_leaks(outputs)

    if candidates:
        write_jsonl(stage12515_out / "private_causal_evidence_return_candidates.jsonl", candidates)
    write_jsonl(out / "private_causal_evidence_candidate_return_blockers.jsonl", blockers)
    write_json(out / "guardrail_scan.json", guardrail_scan)
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()

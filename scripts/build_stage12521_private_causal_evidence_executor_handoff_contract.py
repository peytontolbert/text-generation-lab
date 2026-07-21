#!/usr/bin/env python3
"""Build private causal evidence executor handoff contracts from Stage12520.

Stage12521 consumes Stage12520 batch manifests, instructions, and expanded
slot rows. It emits public-safe executor handoff shards only: each shard tells
a future private executor which Stage12520 slot refs it must preserve and the
exact Stage12516 candidate-return schema it must satisfy if it later writes a
candidate return outside this stage.

This stage performs no execution and writes no candidate returns, Stage12503
returns, training rows, admission rows, Level-3 rows, patch traces, raw paths,
commands, diffs, source text, or verifier output.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12521_private_causal_evidence_executor_handoff_contract"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12520 = "stage12520_private_causal_evidence_acquisition_batch_planner"
STAGE12520_OUT = ROOT / "runs/local/artifacts" / STAGE12520

EXPANDED_SLOTS = STAGE12520_OUT / "expanded_missing_private_causal_evidence_slots.jsonl"
BATCH_MANIFESTS = STAGE12520_OUT / "private_causal_evidence_acquisition_batch_manifest.jsonl"
BATCH_INSTRUCTIONS = STAGE12520_OUT / "private_causal_evidence_acquisition_batch_instructions.jsonl"

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
REQUIRED_STAGE12516_RETURN_FIELDS = [
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
BATCH_GROUP_FIELDS = ["priority_rank", "language_family", "task_family", "source_stage", "evidence_slot"]

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
    "candidate_returns_written": False,
    "validated_returns_written": False,
    "stage12503_return_file_written": False,
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
    "proof_admission_allowed": False,
    "raw_source_output_included": False,
    "raw_private_values_revealed": False,
    "status_hash_as_proof_allowed": False,
    "digest_hash_as_proof_allowed": False,
    "observed_action_imitation_allowed": False,
    "pass_to_pass_repair_credit_allowed": False,
    "root_or_window_hash_unique_key_allowed": False,
    "dedupe_dropped_slots": False,
}
ZERO_GUARDS = {
    "candidate_return_records_written": 0,
    "validated_return_records_written": 0,
    "stage12503_return_records_written": 0,
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
}


class RawLeakError(ValueError):
    pass


class SlotAccountingError(ValueError):
    pass


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


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
        raise RawLeakError(f"stage12521 raw leak guard rejected {len(issues)} public field(s)")


def _safe_str(row: dict[str, Any], field: str) -> str:
    value = row.get(field)
    return value if isinstance(value, str) else ""


def _slot_identity(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _safe_str(row, "expanded_slot_id_hash"),
        _safe_str(row, "acquisition_work_order_id_hash"),
        _safe_str(row, "evidence_slot"),
    )


def _expected_output_schema(slot: str) -> dict[str, Any]:
    return {
        "target_return_record_type": TARGET_RETURN_RECORD_TYPE,
        "required_public_safe_return_fields_in_exact_stage12516_order": REQUIRED_STAGE12516_RETURN_FIELDS,
        "required_boolean_false_fields": [
            "raw_private_values_revealed",
            "raw_source_output_included",
            "raw_paths_included",
            "raw_commands_included",
            "raw_diffs_included",
            "raw_verifier_output_included",
            "local_model_authority",
            "policy_label_emitted",
            "proof_or_admission_requested",
            "observed_action_available_to_labeler",
            "observed_action_used_as_label",
            "pass_to_pass_repair_credit_requested",
            "training_allowed",
            "admission_allowed",
            "stage12503_return_file_written",
        ],
        "required_boolean_true_fields": [
            "reviewer_independence_attestation",
            "acceptance_criteria_passed",
            "candidate_action_set_blinded",
            "label_leak_attestation",
            "model_facing_gold_fields_excluded",
            "repair_credit_requires_before_fail_after_pass_same_verifier",
        ],
        "required_zero_fields": ["stage12503_return_records_written"],
        "required_digest_hash_fields": ["independent_evidence_digest_hash", "causal_review_digest_hash"],
        "required_reviewer_hash_fields": ["private_reviewer_id_hash", "reviewer_conflict_check_hash"],
        "allowed_independent_slot_statuses": ["blocked_unavailable", "not_applicable", "validated_absent", "validated_present"],
        "preferred_private_executor_status": "validated_present",
        "explicit_non_present_status_allowed_for_slot": slot
        in {
            "patch_apply_or_no_patch_status",
            "external_patch_effect_or_no_patch_reason",
            "stop_continue_policy_label",
        },
        "blocker_codes_on_success": [],
    }


def _slot_ref_for_handoff(slot_ref: dict[str, Any]) -> dict[str, Any]:
    row = {
        "expanded_slot_id_hash": slot_ref.get("expanded_slot_id_hash"),
        "revalidation_id_hash": slot_ref.get("revalidation_id_hash"),
        "request_id_hash": slot_ref.get("request_id_hash"),
        "work_item_id_hash": slot_ref.get("work_item_id_hash"),
        "packet_id_hash": slot_ref.get("packet_id_hash"),
        "root_or_window_hash": slot_ref.get("root_or_window_hash"),
        "missing_evidence_worklist_id_hash": slot_ref.get("missing_evidence_worklist_id_hash"),
        "semantic_sufficiency_blocker_id_hash": slot_ref.get("semantic_sufficiency_blocker_id_hash"),
        "semantic_matrix_row_id_hash": slot_ref.get("semantic_matrix_row_id_hash"),
        "acquisition_work_order_id_hash": slot_ref.get("acquisition_work_order_id_hash"),
        "source_stage": slot_ref.get("source_stage"),
        "source_kind": slot_ref.get("source_kind"),
        "language_family": slot_ref.get("language_family"),
        "task_family": slot_ref.get("task_family"),
        "evidence_slot": slot_ref.get("evidence_slot"),
        "proof_class": slot_ref.get("proof_class"),
        "current_independent_slot_status": slot_ref.get("current_independent_slot_status"),
        "blocker_codes": sorted(set(slot_ref.get("blocker_codes") or [])),
        "target_return_record_type": TARGET_RETURN_RECORD_TYPE,
        "stage12516_required_return_fields": REQUIRED_STAGE12516_RETURN_FIELDS,
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks(row)
    return row


def build_handoff_shards(manifests: list[dict[str, Any]], instructions: list[dict[str, Any]], expanded_slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expanded_by_id = {_safe_str(row, "expanded_slot_id_hash"): row for row in expanded_slots}
    instruction_by_batch = {_safe_str(row, "acquisition_batch_id_hash"): row for row in instructions}
    shards: list[dict[str, Any]] = []
    for manifest in sorted(manifests, key=lambda row: (row.get("priority_rank", 999999), _safe_str(row, "acquisition_batch_id_hash"))):
        batch_id = _safe_str(manifest, "acquisition_batch_id_hash")
        instruction = instruction_by_batch.get(batch_id, {})
        merged_slot_refs: list[dict[str, Any]] = []
        for slot_ref in manifest.get("slot_refs") or []:
            if not isinstance(slot_ref, dict):
                continue
            expanded = expanded_by_id.get(_safe_str(slot_ref, "expanded_slot_id_hash"), {})
            merged_slot_refs.append(_slot_ref_for_handoff({**expanded, **slot_ref}))
        slot = _safe_str(manifest, "evidence_slot")
        shard = {
            "record_type": "stage12521_private_causal_evidence_executor_handoff_shard_v1",
            "executor_handoff_shard_id_hash": stable_hash(
                {
                    "batch": batch_id,
                    "slot_refs": [_slot_identity(ref) for ref in merged_slot_refs],
                }
            ),
            "source_stage": STAGE12520,
            "acquisition_batch_id_hash": batch_id,
            "stage12520_instruction_id_hash": instruction.get("instruction_id_hash"),
            "priority_rank": manifest.get("priority_rank"),
            "shard_key": {
                "priority_rank": manifest.get("priority_rank"),
                "language_family": manifest.get("language_family"),
                "task_family": manifest.get("task_family"),
                "source_stage": manifest.get("source_stage"),
                "evidence_slot": slot,
            },
            "language_family": manifest.get("language_family"),
            "task_family": manifest.get("task_family"),
            "source_stage_name": manifest.get("source_stage"),
            "evidence_slot": slot,
            "slot_priority": manifest.get("slot_priority"),
            "slot_ref_count": len(merged_slot_refs),
            "slot_refs": sorted(merged_slot_refs, key=lambda row: _slot_identity(row)),
            "executor_action": "private_executor_may_inspect_private_material_later_and_return_stage12516_candidate_schema_only",
            "expected_output_contract": _expected_output_schema(slot),
            "downstream_validation_required": "stage12516_schema_validation_then_stage12519_semantic_sufficiency_required",
            "status_hash_as_proof_gate": "status_hashes_and_digest_hashes_are_never_proof",
            "observed_action_imitation_gate": "do_not_infer_or_copy_labels_from_observed_actions",
            "pass_to_pass_gate": "pass_to_pass_support_only_not_repair_credit",
            "root_or_window_hash_gate": "root_or_window_hash_context_only_not_unique_identity_or_dedupe_key",
            "dedupe_gate": "preserve_every_stage12520_slot_ref_no_dedupe_slot_drops",
            "semantic_sufficiency_gate": "downstream_stage12519_semantic_sufficiency_required_after_stage12516_validation",
            "output_boundary": "handoff_contract_only_no_execution_no_candidate_returns_written",
            "public_safe_status_only": True,
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        enforce_no_raw_leaks(shard)
        shards.append(shard)
    return shards


def validate_slot_accounting(expanded_slots: list[dict[str, Any]], manifests: list[dict[str, Any]], shards: list[dict[str, Any]]) -> None:
    expanded_keys = Counter(_slot_identity(row) for row in expanded_slots)
    manifest_keys = Counter(
        _slot_identity(slot_ref)
        for manifest in manifests
        for slot_ref in (manifest.get("slot_refs") or [])
        if isinstance(slot_ref, dict)
    )
    shard_keys = Counter(
        _slot_identity(slot_ref)
        for shard in shards
        for slot_ref in (shard.get("slot_refs") or [])
        if isinstance(slot_ref, dict)
    )
    if expanded_keys != manifest_keys:
        raise SlotAccountingError("stage12521 Stage12520 manifests do not preserve expanded slots")
    if expanded_keys != shard_keys:
        raise SlotAccountingError("stage12521 handoff shards dropped or duplicated slot refs")
    if set(row.get("evidence_slot") for row in expanded_slots) != set(FULL_SEVEN_SLOTS):
        raise SlotAccountingError("stage12521 did not preserve the full seven-slot set")


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    stage12520_out = root / "runs/local/artifacts" / STAGE12520
    expanded_slots = read_jsonl(stage12520_out / "expanded_missing_private_causal_evidence_slots.jsonl")
    manifests = read_jsonl(stage12520_out / "private_causal_evidence_acquisition_batch_manifest.jsonl")
    instructions = read_jsonl(stage12520_out / "private_causal_evidence_acquisition_batch_instructions.jsonl")

    enforce_no_raw_leaks({"expanded_slots": expanded_slots, "manifests": manifests, "instructions": instructions})
    expanded_slots = [row for row in expanded_slots if row.get("record_type") == "stage12520_expanded_missing_private_causal_evidence_slot_v1"]
    manifests = [row for row in manifests if row.get("record_type") == "stage12520_private_causal_evidence_acquisition_batch_manifest_v1"]
    instructions = [row for row in instructions if row.get("record_type") == "stage12520_private_causal_evidence_acquisition_batch_instruction_v1"]

    shards = build_handoff_shards(manifests, instructions, expanded_slots)
    validate_slot_accounting(expanded_slots, manifests, shards)

    slot_counts = Counter(_safe_str(row, "evidence_slot") for row in expanded_slots)
    shard_slot_counts = Counter(_safe_str(row, "evidence_slot") for row in shards)
    contract = {
        "record_type": "stage12521_private_causal_evidence_executor_handoff_contract_v1",
        "stage": STAGE,
        "source_stage": STAGE12520,
        "input_refs": [
            "stage12520_private_causal_evidence_acquisition_batch_manifest_jsonl",
            "stage12520_private_causal_evidence_acquisition_batch_instructions_jsonl",
            "stage12520_expanded_missing_private_causal_evidence_slots_jsonl",
        ],
        "output_scope": "executor_handoff_shards_and_schema_contract_only",
        "handoff_shard_group_fields": BATCH_GROUP_FIELDS,
        "target_future_return_record_type": TARGET_RETURN_RECORD_TYPE,
        "required_stage12516_candidate_return_fields": REQUIRED_STAGE12516_RETURN_FIELDS,
        "full_seven_slot_set": FULL_SEVEN_SLOTS,
        "status_hash_as_proof_gate": "status_hashes_and_digest_hashes_are_never_proof",
        "observed_action_imitation_gate": "observed_actions_must_not_be_used_as_labels",
        "pass_to_pass_gate": "pass_to_pass_support_only_not_repair_credit",
        "root_or_window_hash_gate": "root_or_window_hash_not_unique_and_never_used_for_dedupe",
        "no_dedupe_dropping_slots_gate": "handoff_slot_ref_count_must_equal_stage12520_expanded_slot_count",
        "semantic_sufficiency_gate": "downstream_stage12519_semantic_sufficiency_required_after_stage12516_validation",
        "candidate_return_boundary": "no_candidate_return_records_written_by_stage12521",
        "stage12503_boundary": "no_stage12503_records_written",
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    guardrail_scan = {
        "stage": STAGE,
        "scan_passed": True,
        "raw_leak_count": 0,
        "raw_leak_issue_hashes": [],
        "scanned_outputs": [
            "private_causal_evidence_executor_handoff_shards.jsonl",
            "private_causal_evidence_executor_handoff_contract.json",
            "summary.json",
        ],
    }
    summary = {
        "stage": STAGE,
        "record_type": "stage12521_private_causal_evidence_executor_handoff_summary_v1",
        "decision": "private_causal_evidence_executor_handoff_shards_written_no_execution_or_returns",
        "claim_boundary": (
            "Stage12521 hands off Stage12520 private acquisition batches to a future private "
            "executor contract. It preserves every slot ref and publishes the Stage12516 "
            "candidate-return schema, but writes no candidate returns, Stage12503 returns, "
            "training, admission, Level-3, patch-trace, raw, source, diff, command, or verifier material."
        ),
        "source_stage": STAGE12520,
        "input_expanded_slot_count": len(expanded_slots),
        "input_batch_manifest_count": len(manifests),
        "input_instruction_count": len(instructions),
        "handoff_shard_count": len(shards),
        "handoff_slot_ref_count": sum(row["slot_ref_count"] for row in shards),
        "dedupe_dropped_slot_count": 0,
        "full_seven_slot_set_seen": sorted(slot_counts) == sorted(FULL_SEVEN_SLOTS),
        "evidence_slot_counts": dict(sorted(slot_counts.items())),
        "handoff_shard_slot_counts": dict(sorted(shard_slot_counts.items())),
        "target_future_return_record_type": TARGET_RETURN_RECORD_TYPE,
        "required_stage12516_candidate_return_field_count": len(REQUIRED_STAGE12516_RETURN_FIELDS),
        "status_hash_as_proof_gate": "status_hashes_and_digest_hashes_are_never_proof",
        "observed_action_imitation_gate": "do_not_infer_or_copy_labels_from_observed_actions",
        "pass_to_pass_gate": "pass_to_pass_support_only_not_repair_credit",
        "root_or_window_hash_gate": "root_or_window_hash_context_only_not_unique_identity_or_dedupe_key",
        "no_dedupe_dropping_slots_gate": "handoff_slot_ref_count_equals_input_expanded_slot_count",
        "semantic_sufficiency_gate": "downstream_stage12519_semantic_sufficiency_required_after_stage12516_validation",
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        "next_stage": "future_private_executor_may_emit_stage12516_candidate_returns_for_stage12516_validation_only",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    outputs = {"shards": shards, "contract": contract, "guardrail_scan": guardrail_scan, "summary": summary}
    enforce_no_raw_leaks(outputs)

    write_jsonl(out / "private_causal_evidence_executor_handoff_shards.jsonl", shards)
    write_json(out / "private_causal_evidence_executor_handoff_contract.json", contract)
    write_json(out / "guardrail_scan.json", guardrail_scan)
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()

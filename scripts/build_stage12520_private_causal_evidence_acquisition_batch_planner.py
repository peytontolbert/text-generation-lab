#!/usr/bin/env python3
"""Plan private causal evidence acquisition batches from Stage12519 gaps.

Stage12520 consumes only public-safe Stage12519 missing worklist, blocker, and
semantic matrix records. It expands every missing seven-slot causal evidence
gap, groups slots into prioritized private extractor/reviewer batches, and
emits batch manifests plus instructions only.

The stage writes no candidate returns, Stage12503 returns, training rows,
admission rows, Level-3 rows, patch traces, raw paths, raw command material,
raw diffs, source text, or verifier output.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12520_private_causal_evidence_acquisition_batch_planner"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12519 = "stage12519_private_causal_evidence_semantic_sufficiency_gate"
STAGE12519_OUT = ROOT / "runs/local/artifacts" / STAGE12519

MISSING_WORKLIST = STAGE12519_OUT / "missing_private_causal_evidence_worklist.jsonl"
BLOCKERS = STAGE12519_OUT / "private_causal_evidence_semantic_sufficiency_blockers.jsonl"
MATRIX = STAGE12519_OUT / "private_causal_evidence_semantic_sufficiency_matrix.jsonl"

MISSING_WORKLIST_RECORD_TYPE = "stage12519_missing_private_causal_evidence_worklist_v1"
BLOCKER_RECORD_TYPE = "stage12519_private_causal_evidence_semantic_sufficiency_blocker_v1"
MATRIX_RECORD_TYPE = "stage12519_private_causal_evidence_slot_semantic_matrix_row_v1"

FULL_SEVEN_SLOTS = [
    "same_source_causal_lineage_with_independent_evidence_digest",
    "structured_state_before_codes",
    "state_delta_or_state_after_codes",
    "patch_apply_or_no_patch_status",
    "stop_continue_policy_label",
    "independent_policy_label_and_candidate_action_set",
    "external_patch_effect_or_no_patch_reason",
]
SLOT_PRIORITY = {slot: idx + 1 for idx, slot in enumerate(FULL_SEVEN_SLOTS)}
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
]
BATCH_GROUP_FIELDS = ["language_family", "task_family", "source_stage", "evidence_slot"]
ALLOWED_REPLACEMENT_STATUSES = {
    "validated_present",
    "validated_absent",
    "not_applicable",
}
EXPLICIT_ALLOWED_NON_PRESENT_STATUS_CODES = [
    "explicit_no_patch_reason_validated",
    "no_patch_semantics_validated",
    "not_applicable_no_patch_semantics_validated",
    "explicit_no_stop_reason_validated",
    "no_stop_semantics_validated",
    "not_applicable_no_stop_semantics_validated",
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
        raise RawLeakError(f"stage12520 raw leak guard rejected {len(issues)} public field(s)")


def _safe_str(row: dict[str, Any], field: str) -> str:
    value = row.get(field)
    return value if isinstance(value, str) else ""


def _copy_identity(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row.get(field) for field in IDENTITY_FIELDS}


def _matrix_key(row: dict[str, Any]) -> tuple[str, str]:
    return (_safe_str(row, "revalidation_id_hash"), _safe_str(row, "evidence_slot"))


def _slot_ref_key(slot_ref: dict[str, Any], worklist_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "revalidation_id_hash": _safe_str(worklist_row, "revalidation_id_hash"),
        "acquisition_work_order_id_hash": _safe_str(slot_ref, "acquisition_work_order_id_hash"),
        "evidence_slot": _safe_str(slot_ref, "evidence_slot"),
        "proof_class": _safe_str(slot_ref, "proof_class"),
    }


def _replacement_status_guidance(slot: str) -> dict[str, Any]:
    explicit_non_present_allowed = slot in {
        "patch_apply_or_no_patch_status",
        "external_patch_effect_or_no_patch_reason",
        "stop_continue_policy_label",
    }
    return {
        "preferred_replacement_status": "validated_present",
        "allowed_replacement_statuses": sorted(ALLOWED_REPLACEMENT_STATUSES),
        "explicit_non_present_status_allowed_for_slot": explicit_non_present_allowed,
        "explicit_non_present_reason_codes": EXPLICIT_ALLOWED_NON_PRESENT_STATUS_CODES if explicit_non_present_allowed else [],
        "blocked_unavailable_is_not_successful_replacement": True,
        "continued_blocker_status_if_private_acquisition_still_absent": "blocked_unavailable",
        "semantic_sufficiency_required": True,
    }


def expand_missing_slots(
    worklist_rows: list[dict[str, Any]],
    blocker_by_revalidation: dict[str, dict[str, Any]],
    matrix_by_key: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for worklist_row in worklist_rows:
        if worklist_row.get("record_type") != MISSING_WORKLIST_RECORD_TYPE:
            continue
        rid = _safe_str(worklist_row, "revalidation_id_hash")
        blocker = blocker_by_revalidation.get(rid, {})
        for slot_index, slot_ref in enumerate(worklist_row.get("slot_refs") or []):
            if not isinstance(slot_ref, dict):
                continue
            slot = _safe_str(slot_ref, "evidence_slot")
            matrix = matrix_by_key.get((rid, slot), {})
            slot_item = {
                "record_type": "stage12520_expanded_missing_private_causal_evidence_slot_v1",
                "expanded_slot_id_hash": stable_hash(
                    {
                        "missing_evidence_worklist_id_hash": worklist_row.get("missing_evidence_worklist_id_hash"),
                        "slot_index": slot_index,
                        "slot_ref": _slot_ref_key(slot_ref, worklist_row),
                    }
                ),
                **_copy_identity(worklist_row),
                "missing_evidence_worklist_id_hash": worklist_row.get("missing_evidence_worklist_id_hash"),
                "semantic_sufficiency_blocker_id_hash": blocker.get("semantic_sufficiency_blocker_id_hash"),
                "semantic_matrix_row_id_hash": matrix.get("semantic_matrix_row_id_hash"),
                "acquisition_work_order_id_hash": slot_ref.get("acquisition_work_order_id_hash"),
                "evidence_slot": slot,
                "slot_priority": SLOT_PRIORITY.get(slot, len(FULL_SEVEN_SLOTS) + 1),
                "proof_class": slot_ref.get("proof_class"),
                "current_independent_slot_status": slot_ref.get("current_independent_slot_status"),
                "blocker_codes": sorted(set(slot_ref.get("blocker_codes") or matrix.get("blocker_codes") or [])),
                "needed_evidence": slot_ref.get("needed_evidence"),
                "matrix_semantic_sufficient": matrix.get("semantic_sufficient"),
                "matrix_semantic_sufficiency_reason": matrix.get("semantic_sufficiency_reason"),
                "source_blocker_decision": blocker.get("decision"),
                "public_safe_status_only": True,
                **_replacement_status_guidance(slot),
                **FALSE_GUARDS,
                **ZERO_GUARDS,
            }
            enforce_no_raw_leaks(slot_item)
            expanded.append(slot_item)
    return expanded


def _group_key(slot_item: dict[str, Any]) -> tuple[str, str, str, str]:
    return tuple(_safe_str(slot_item, field) for field in BATCH_GROUP_FIELDS)  # type: ignore[return-value]


def build_batch_manifests(expanded_slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for slot_item in expanded_slots:
        grouped[_group_key(slot_item)].append(slot_item)

    ordered_groups = sorted(
        grouped.items(),
        key=lambda item: (
            min(slot["slot_priority"] for slot in item[1]),
            -len(item[1]),
            item[0],
        ),
    )
    manifests: list[dict[str, Any]] = []
    for priority_rank, (group_key, slots) in enumerate(ordered_groups, start=1):
        language_family, task_family, source_stage, evidence_slot = group_key
        root_hashes = sorted({_safe_str(slot, "root_or_window_hash") for slot in slots if _safe_str(slot, "root_or_window_hash")})
        revalidation_ids = sorted({_safe_str(slot, "revalidation_id_hash") for slot in slots if _safe_str(slot, "revalidation_id_hash")})
        blocker_counts = Counter(code for slot in slots for code in slot["blocker_codes"])
        manifest = {
            "record_type": "stage12520_private_causal_evidence_acquisition_batch_manifest_v1",
            "acquisition_batch_id_hash": stable_hash({"group": group_key, "slots": [slot["expanded_slot_id_hash"] for slot in slots]}),
            "priority_rank": priority_rank,
            "priority_basis": [
                "earlier_causal_slot_order_first",
                "larger_batch_before_smaller_within_same_slot",
                "stable_language_task_source_stage_tiebreak",
            ],
            "language_family": language_family,
            "task_family": task_family,
            "source_stage": source_stage,
            "evidence_slot": evidence_slot,
            "slot_priority": SLOT_PRIORITY.get(evidence_slot, len(FULL_SEVEN_SLOTS) + 1),
            "missing_slot_count": len(slots),
            "revalidation_record_count": len(revalidation_ids),
            "root_or_window_hash_count": len(root_hashes),
            "root_or_window_hashes_seen_for_context_only": root_hashes,
            "root_or_window_hash_unique_key_allowed": False,
            "dedupe_policy": "preserve_every_stage12519_missing_slot_ref_no_root_or_window_hash_dedupe",
            "dedupe_dropped_slots": False,
            "blocker_code_counts": dict(sorted(blocker_counts.items())),
            "slot_refs": [
                {
                    "expanded_slot_id_hash": slot["expanded_slot_id_hash"],
                    "revalidation_id_hash": slot["revalidation_id_hash"],
                    "request_id_hash": slot["request_id_hash"],
                    "work_item_id_hash": slot["work_item_id_hash"],
                    "packet_id_hash": slot["packet_id_hash"],
                    "root_or_window_hash": slot["root_or_window_hash"],
                    "missing_evidence_worklist_id_hash": slot["missing_evidence_worklist_id_hash"],
                    "semantic_sufficiency_blocker_id_hash": slot["semantic_sufficiency_blocker_id_hash"],
                    "semantic_matrix_row_id_hash": slot["semantic_matrix_row_id_hash"],
                    "acquisition_work_order_id_hash": slot["acquisition_work_order_id_hash"],
                    "evidence_slot": slot["evidence_slot"],
                    "proof_class": slot["proof_class"],
                    "current_independent_slot_status": slot["current_independent_slot_status"],
                    "blocker_codes": slot["blocker_codes"],
                }
                for slot in sorted(slots, key=lambda item: item["expanded_slot_id_hash"])
            ],
            "expected_private_reviewer_outcome": (
                "replace_blocked_unavailable_with_validated_present_or_explicit_allowed_no_patch_no_stop_status"
            ),
            "candidate_returns_written_by_stage12520": False,
            "stage12503_returns_written_by_stage12520": False,
            "public_safe_status_only": True,
            **_replacement_status_guidance(evidence_slot),
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        enforce_no_raw_leaks(manifest)
        manifests.append(manifest)
    return manifests


def instruction_record(manifest: dict[str, Any]) -> dict[str, Any]:
    slot = manifest["evidence_slot"]
    row = {
        "record_type": "stage12520_private_causal_evidence_acquisition_batch_instruction_v1",
        "instruction_id_hash": stable_hash({"batch": manifest["acquisition_batch_id_hash"], "slot": slot}),
        "acquisition_batch_id_hash": manifest["acquisition_batch_id_hash"],
        "priority_rank": manifest["priority_rank"],
        "language_family": manifest["language_family"],
        "task_family": manifest["task_family"],
        "source_stage": manifest["source_stage"],
        "evidence_slot": slot,
        "missing_slot_count": manifest["missing_slot_count"],
        "private_extractor_action": "inspect_private_material_for_this_slot_and_return_public_safe_status_metadata_only",
        "private_reviewer_action": "validate_independent_semantic_sufficiency_before_any_downstream_ingest",
        "required_evidence_slots_for_complete_record": FULL_SEVEN_SLOTS,
        "batch_slot_scope": "single_evidence_slot_grouped_by_language_task_and_source_stage",
        "replacement_status_rule": (
            "validated_present_required_unless_slot_has_explicit_allowed_no_patch_or_no_stop_semantics"
        ),
        "status_hash_as_proof_gate": "status_hashes_and_digest_hashes_are_never_proof",
        "observed_action_imitation_gate": "do_not_infer_labels_from_observed_actions",
        "pass_to_pass_gate": "pass_to_pass_support_is_not_repair_credit",
        "full_seven_slot_gate": "all_seven_slots_plus_semantic_sufficiency_required_before_proof_ready",
        "root_or_window_hash_gate": "root_or_window_hash_is_context_only_not_unique_identity",
        "dedupe_gate": "do_not_drop_any_stage12519_slot_ref_during_batching_or_review",
        "forbidden_public_material_gate": "no_raw_path_command_diff_source_or_verifier_material",
        "output_boundary": "planner_manifest_and_instruction_only_no_candidate_return_written",
        "public_safe_status_only": True,
        **_replacement_status_guidance(slot),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks(row)
    return row


def validate_slot_accounting(expanded_slots: list[dict[str, Any]], manifests: list[dict[str, Any]], matrix_rows: list[dict[str, Any]]) -> None:
    manifest_slot_count = sum(row["missing_slot_count"] for row in manifests)
    insufficient_matrix_count = sum(1 for row in matrix_rows if row.get("semantic_sufficient") is False)
    if manifest_slot_count != len(expanded_slots):
        raise SlotAccountingError("stage12520 batch manifests dropped expanded slots")
    if insufficient_matrix_count and insufficient_matrix_count != len(expanded_slots):
        raise SlotAccountingError("stage12520 expanded slot count does not match Stage12519 insufficient matrix slots")
    slot_counter = Counter(slot["evidence_slot"] for slot in expanded_slots)
    if set(slot_counter) != set(FULL_SEVEN_SLOTS):
        raise SlotAccountingError("stage12520 did not preserve the full seven-slot set")


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    stage12519_out = root / "runs/local/artifacts" / STAGE12519
    worklist_rows = read_jsonl(stage12519_out / "missing_private_causal_evidence_worklist.jsonl")
    blocker_rows = read_jsonl(stage12519_out / "private_causal_evidence_semantic_sufficiency_blockers.jsonl")
    matrix_rows = read_jsonl(stage12519_out / "private_causal_evidence_semantic_sufficiency_matrix.jsonl")

    enforce_no_raw_leaks({"worklist_rows": worklist_rows, "blocker_rows": blocker_rows, "matrix_rows": matrix_rows})

    worklist_rows = [row for row in worklist_rows if row.get("record_type") == MISSING_WORKLIST_RECORD_TYPE]
    blocker_rows = [row for row in blocker_rows if row.get("record_type") == BLOCKER_RECORD_TYPE]
    matrix_rows = [row for row in matrix_rows if row.get("record_type") == MATRIX_RECORD_TYPE]

    blocker_by_revalidation = {_safe_str(row, "revalidation_id_hash"): row for row in blocker_rows}
    matrix_by_key = {_matrix_key(row): row for row in matrix_rows}
    expanded_slots = expand_missing_slots(worklist_rows, blocker_by_revalidation, matrix_by_key)
    manifests = build_batch_manifests(expanded_slots)
    instructions = [instruction_record(manifest) for manifest in manifests]
    validate_slot_accounting(expanded_slots, manifests, matrix_rows)

    slot_counts = Counter(slot["evidence_slot"] for slot in expanded_slots)
    language_counts = Counter(slot["language_family"] for slot in expanded_slots)
    task_counts = Counter(slot["task_family"] for slot in expanded_slots)
    source_stage_counts = Counter(slot["source_stage"] for slot in expanded_slots)
    blocker_code_counts = Counter(code for slot in expanded_slots for code in slot["blocker_codes"])
    batch_sizes = [manifest["missing_slot_count"] for manifest in manifests]
    contract = {
        "record_type": "stage12520_private_causal_evidence_acquisition_batch_planner_contract_v1",
        "stage": STAGE,
        "source_stage": STAGE12519,
        "input_refs": [
            "stage12519_missing_private_causal_evidence_worklist_jsonl",
            "stage12519_private_causal_evidence_semantic_sufficiency_blockers_jsonl",
            "stage12519_private_causal_evidence_semantic_sufficiency_matrix_jsonl",
        ],
        "output_scope": "private_acquisition_batch_manifests_and_instructions_only",
        "batch_group_fields": BATCH_GROUP_FIELDS,
        "full_seven_slot_set": FULL_SEVEN_SLOTS,
        "status_hash_as_proof_gate": "status_hashes_and_digest_hashes_are_never_sufficient_proof",
        "observed_action_imitation_gate": "observed_actions_must_not_be_used_as_labels",
        "pass_to_pass_gate": "pass_to_pass_support_only_not_repair_credit",
        "full_seven_slot_gate": "all_seven_slots_plus_semantic_sufficiency_required",
        "root_or_window_hash_gate": "root_or_window_hash_not_unique_and_never_used_for_dedupe",
        "no_dedupe_dropping_slots_gate": "sum_of_batch_slot_refs_must_equal_stage12519_missing_slots",
        "candidate_return_boundary": "no_candidate_return_records_written",
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
            "expanded_missing_private_causal_evidence_slots.jsonl",
            "private_causal_evidence_acquisition_batch_manifest.jsonl",
            "private_causal_evidence_acquisition_batch_instructions.jsonl",
            "private_causal_evidence_acquisition_batch_planner_contract.json",
            "summary.json",
        ],
    }
    summary = {
        "stage": STAGE,
        "record_type": "stage12520_private_causal_evidence_acquisition_batch_planner_summary_v1",
        "decision": "private_causal_evidence_acquisition_batches_planned_no_returns_written",
        "claim_boundary": (
            "Stage12520 plans private acquisition batches from Stage12519 missing evidence only. "
            "It preserves every missing slot, emits instructions for private extraction/review, "
            "and writes no candidate returns, Stage12503 returns, training, admission, Level-3, "
            "patch-trace, raw, source, diff, or verifier material."
        ),
        "source_stage": STAGE12519,
        "input_missing_worklist_count": len(worklist_rows),
        "input_blocker_count": len(blocker_rows),
        "input_matrix_row_count": len(matrix_rows),
        "expanded_missing_slot_count": len(expanded_slots),
        "planned_batch_count": len(manifests),
        "instruction_count": len(instructions),
        "batch_slot_ref_count": sum(manifest["missing_slot_count"] for manifest in manifests),
        "dedupe_dropped_slot_count": 0,
        "full_seven_slot_set_seen": sorted(slot_counts) == sorted(FULL_SEVEN_SLOTS),
        "evidence_slot_counts": dict(sorted(slot_counts.items())),
        "language_family_slot_counts": dict(sorted(language_counts.items())),
        "task_family_slot_counts": dict(sorted(task_counts.items())),
        "source_stage_slot_counts": dict(sorted(source_stage_counts.items())),
        "blocker_code_counts": dict(sorted(blocker_code_counts.items())),
        "largest_batch_size": max(batch_sizes) if batch_sizes else 0,
        "smallest_batch_size": min(batch_sizes) if batch_sizes else 0,
        "status_hash_as_proof_gate": "status_hashes_and_digest_hashes_are_never_proof",
        "observed_action_imitation_gate": "do_not_infer_labels_from_observed_actions",
        "pass_to_pass_gate": "pass_to_pass_support_is_not_repair_credit",
        "full_seven_slot_gate": "all_seven_slots_plus_semantic_sufficiency_required",
        "root_or_window_hash_gate": "root_or_window_hash_not_unique_and_not_dedupe_key",
        "no_dedupe_dropping_slots_gate": "batch_slot_ref_count_equals_expanded_missing_slot_count",
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        "next_stage": "private_extractor_reviewer_may_supply_stage12516_compatible_status_metadata_after_private_validation",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    outputs = {
        "expanded_slots": expanded_slots,
        "manifests": manifests,
        "instructions": instructions,
        "contract": contract,
        "guardrail_scan": guardrail_scan,
        "summary": summary,
    }
    enforce_no_raw_leaks(outputs)

    write_jsonl(out / "expanded_missing_private_causal_evidence_slots.jsonl", expanded_slots)
    write_jsonl(out / "private_causal_evidence_acquisition_batch_manifest.jsonl", manifests)
    write_jsonl(out / "private_causal_evidence_acquisition_batch_instructions.jsonl", instructions)
    write_json(out / "private_causal_evidence_acquisition_batch_planner_contract.json", contract)
    write_json(out / "guardrail_scan.json", guardrail_scan)
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Adapt private executor returns from Stage12521 into Stage12516 candidates.

Stage12522 consumes Stage12521 executor handoff shards and, only when a private
executor return file is present under the Stage12521 artifact directory,
validates/converts public-safe executor rows into exact Stage12516 candidate
return rows at the Stage12515 candidate-return path.

It performs no private execution, fabricates no statuses, writes no Stage12503
returns, and emits no training, admission, Level-3, patch-trace, raw path,
command, diff, source, or verifier-output material.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12522_private_causal_evidence_executor_return_adapter"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12521 = "stage12521_private_causal_evidence_executor_handoff_contract"
STAGE12521_OUT = ROOT / "runs/local/artifacts" / STAGE12521
HANDOFF_SHARDS = STAGE12521_OUT / "private_causal_evidence_executor_handoff_shards.jsonl"
HANDOFF_CONTRACT = STAGE12521_OUT / "private_causal_evidence_executor_handoff_contract.json"

STAGE12515 = "stage12515_private_causal_evidence_acquisition_work_orders"
STAGE12515_OUT = ROOT / "runs/local/artifacts" / STAGE12515
STAGE12516_CANDIDATE_OUTPUT = STAGE12515_OUT / "private_causal_evidence_return_candidates.jsonl"

EXECUTOR_RETURN_FILENAMES = [
    "private_causal_evidence_executor_returns.jsonl",
    "private_causal_evidence_executor_return_candidates.jsonl",
    "executor_private_causal_evidence_returns.jsonl",
]

RETURN_RECORD_TYPE = "stage12516_private_causal_evidence_return_candidate_v1"
EXECUTOR_RECORD_TYPES = {
    RETURN_RECORD_TYPE,
    "stage12522_private_causal_evidence_executor_return_v1",
    "stage12521_private_causal_evidence_executor_return_v1",
}
ALLOWED_STATUSES = {"blocked_unavailable", "not_applicable", "validated_absent", "validated_present"}
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

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output|verifier output|commit:)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)
SAFE_HASH_RE = re.compile(r"^[0-9a-f]{12,64}$")
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
    "validated_present_fabricated": False,
    "blocked_unavailable_fabricated": False,
}
ZERO_GUARDS = {
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


def is_safe_hash(value: Any) -> bool:
    return isinstance(value, str) and SAFE_HASH_RE.fullmatch(value) is not None and len(set(value.lower())) > 1


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
        raise RawLeakError(f"stage12522 raw leak guard rejected {len(issues)} public field(s)")


def _safe_str(row: dict[str, Any], field: str) -> str:
    value = row.get(field)
    return value if isinstance(value, str) else ""


def _slot_identity(row: dict[str, Any]) -> tuple[str, str]:
    return (_safe_str(row, "acquisition_work_order_id_hash"), _safe_str(row, "evidence_slot"))


def _full_slot_identity(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(_safe_str(row, field) for field in ["acquisition_work_order_id_hash", *IDENTITY_FIELDS])


def find_executor_return_path(stage12521_out: Path) -> Path | None:
    for filename in EXECUTOR_RETURN_FILENAMES:
        path = stage12521_out / filename
        if path.exists():
            return path
    return None


def flatten_slot_refs(shards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slot_refs: list[dict[str, Any]] = []
    for shard in shards:
        for slot_ref in shard.get("slot_refs") or []:
            if isinstance(slot_ref, dict):
                slot_refs.append(slot_ref)
    return slot_refs


def validate_slot_accounting(slot_refs: list[dict[str, Any]]) -> None:
    if len(slot_refs) != len({_full_slot_identity(row) for row in slot_refs}):
        raise SlotAccountingError("stage12522 Stage12521 handoff contains duplicate full slot identities")
    if set(_safe_str(row, "evidence_slot") for row in slot_refs) != set(FULL_SEVEN_SLOTS):
        raise SlotAccountingError("stage12522 did not preserve the full seven-slot set")


def extract_candidate(row: dict[str, Any]) -> dict[str, Any]:
    nested = row.get("candidate_return")
    if isinstance(nested, dict):
        candidate = dict(nested)
    else:
        candidate = {field: row.get(field) for field in REQUIRED_STAGE12516_RETURN_FIELDS if field in row}
    candidate["record_type"] = RETURN_RECORD_TYPE
    return candidate


def validate_candidate(candidate: dict[str, Any], slot_ref: dict[str, Any] | None) -> list[str]:
    reasons: list[str] = []
    for field in REQUIRED_STAGE12516_RETURN_FIELDS:
        if field not in candidate:
            reasons.append(f"missing_{field}")
    if slot_ref is None:
        reasons.append("unknown_stage12521_slot_identity")
        return sorted(set(reasons))
    if candidate.get("record_type") != RETURN_RECORD_TYPE:
        reasons.append("schema_version_unsupported")
    for field in ["acquisition_work_order_id_hash", *IDENTITY_FIELDS]:
        if candidate.get(field) != slot_ref.get(field):
            reasons.append(f"{field}_mismatch")
    status = candidate.get("independent_slot_status")
    if status not in ALLOWED_STATUSES:
        reasons.append("unsupported_independent_slot_status")
    for field in [
        "private_reviewer_id_hash",
        "reviewer_conflict_check_hash",
        "independent_evidence_digest_hash",
        "causal_review_digest_hash",
    ]:
        if not is_safe_hash(candidate.get(field)):
            reasons.append(f"{field}_missing_or_unsafe")
    if candidate.get("reviewer_independence_attestation") is not True:
        reasons.append("reviewer_independence_attestation_missing")
    if not isinstance(candidate.get("slot_status_reason_code"), str) or not candidate.get("slot_status_reason_code"):
        reasons.append("slot_status_reason_code_missing")
    for field in [
        "raw_private_values_revealed",
        "raw_source_output_included",
        "raw_paths_included",
        "raw_commands_included",
        "raw_diffs_included",
        "raw_verifier_output_included",
        "local_model_authority",
        "policy_label_emitted",
        "proof_or_admission_requested",
        "training_allowed",
        "admission_allowed",
        "stage12503_return_file_written",
        "observed_action_available_to_labeler",
        "observed_action_used_as_label",
        "pass_to_pass_repair_credit_requested",
    ]:
        if candidate.get(field) is not False:
            reasons.append(f"{field}_not_false")
    for field in [
        "acceptance_criteria_passed",
        "candidate_action_set_blinded",
        "label_leak_attestation",
        "model_facing_gold_fields_excluded",
        "repair_credit_requires_before_fail_after_pass_same_verifier",
    ]:
        if candidate.get(field) is not True:
            reasons.append(f"{field}_not_true")
    if candidate.get("stage12503_return_records_written") != 0:
        reasons.append("stage12503_return_records_written_nonzero")
    if candidate.get("blocker_codes") not in ([], None):
        reasons.append("return_blocker_codes_not_empty")
    if set(candidate) - set(REQUIRED_STAGE12516_RETURN_FIELDS):
        reasons.append("extra_public_field_present")
    if set(candidate) & FORBIDDEN_PUBLIC_KEYS or scan_raw_leaks(candidate):
        reasons.append("raw_leakage_detected")
    return sorted(set(reasons))


def accepted_adapter_record(candidate: dict[str, Any]) -> dict[str, Any]:
    row = {
        "record_type": "stage12522_adapted_stage12516_candidate_return_v1",
        "adapted_candidate_id_hash": stable_hash({"candidate": _full_slot_identity(candidate)}),
        "target_record_type": RETURN_RECORD_TYPE,
        "target_stage12516_candidate_output_ref": (
            "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/"
            "private_causal_evidence_return_candidates.jsonl"
        ),
        **{field: candidate.get(field) for field in ["acquisition_work_order_id_hash", *IDENTITY_FIELDS]},
        "independent_slot_status": candidate.get("independent_slot_status"),
        "independent_evidence_digest_hash": candidate.get("independent_evidence_digest_hash"),
        "causal_review_digest_hash": candidate.get("causal_review_digest_hash"),
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "stage12516_candidate_rows_written": 1,
    }
    enforce_no_raw_leaks(row)
    return row


def rejected_adapter_record(row: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    rejected = {
        "record_type": "stage12522_rejected_private_executor_return_v1",
        "rejected_executor_return_id_hash": stable_hash(
            {"slot": _slot_identity(row), "record_type": row.get("record_type"), "reasons": reasons}
        ),
        "acquisition_work_order_id_hash": row.get("acquisition_work_order_id_hash"),
        "evidence_slot": row.get("evidence_slot"),
        "rejection_codes": reasons,
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks(rejected)
    return rejected


def blocker_records(slot_refs: list[dict[str, Any]], accepted_keys: set[tuple[str, str]], executor_file_present: bool) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for slot_ref in slot_refs:
        if _slot_identity(slot_ref) in accepted_keys:
            continue
        blocker_code = (
            "private_executor_return_absent"
            if not executor_file_present
            else "private_executor_return_missing_or_rejected_for_slot"
        )
        row = {
            "record_type": "stage12522_private_causal_evidence_executor_return_blocker_v1",
            "blocker_id_hash": stable_hash({"slot": _full_slot_identity(slot_ref), "present": executor_file_present}),
            **{field: slot_ref.get(field) for field in ["acquisition_work_order_id_hash", *IDENTITY_FIELDS]},
            "blocker_codes": [
                blocker_code,
                "stage12516_candidate_return_required_before_stage12516_validation",
                "downstream_stage12516_then_stage12519_required",
            ],
            "target_stage12516_candidate_output_ref": (
                "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/"
                "private_causal_evidence_return_candidates.jsonl"
            ),
            "public_safe_status_only": True,
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        enforce_no_raw_leaks(row)
        blockers.append(row)
    return blockers


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    stage12521_out = root / "runs/local/artifacts" / STAGE12521
    stage12515_out = root / "runs/local/artifacts" / STAGE12515
    target_output = stage12515_out / "private_causal_evidence_return_candidates.jsonl"

    shards = read_jsonl(stage12521_out / "private_causal_evidence_executor_handoff_shards.jsonl")
    contract = read_json(stage12521_out / "private_causal_evidence_executor_handoff_contract.json")
    slot_refs = flatten_slot_refs(shards)
    validate_slot_accounting(slot_refs)
    slot_ref_by_identity = {_slot_identity(row): row for row in slot_refs}
    executor_return_path = find_executor_return_path(stage12521_out)
    executor_returns = read_jsonl(executor_return_path) if executor_return_path else []

    accepted_candidates: list[dict[str, Any]] = []
    accepted_adapter_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    seen_return_keys = Counter(_slot_identity(extract_candidate(row)) for row in executor_returns)
    accepted_keys: set[tuple[str, str]] = set()
    for executor_row in executor_returns:
        if executor_row.get("record_type") not in EXECUTOR_RECORD_TYPES:
            candidate = extract_candidate(executor_row)
            reasons = ["unsupported_executor_return_record_type"]
        else:
            candidate = extract_candidate(executor_row)
            reasons = []
        if set(executor_row) & FORBIDDEN_PUBLIC_KEYS or scan_raw_leaks(executor_row):
            reasons.append("raw_leakage_detected")
        key = _slot_identity(candidate)
        reasons.extend(validate_candidate(candidate, slot_ref_by_identity.get(key)))
        if seen_return_keys[key] > 1:
            reasons.append("duplicate_executor_return_for_slot")
        if key in accepted_keys:
            reasons.append("duplicate_accepted_candidate_for_slot")
        reasons = sorted(set(reasons))
        if reasons:
            rejected_rows.append(rejected_adapter_record(candidate, reasons))
            continue
        accepted_candidates.append({field: candidate[field] for field in REQUIRED_STAGE12516_RETURN_FIELDS})
        accepted_adapter_rows.append(accepted_adapter_record(candidate))
        accepted_keys.add(key)

    if executor_return_path is not None:
        write_jsonl(target_output, accepted_candidates)

    blockers = blocker_records(slot_refs, accepted_keys, executor_return_path is not None)
    executed_count = len({key for key in seen_return_keys if key in slot_ref_by_identity})
    missing_count = len(slot_refs) - len(accepted_keys)
    slot_counts = Counter(_safe_str(row, "evidence_slot") for row in slot_refs)
    accepted_status_counts = Counter(str(row.get("independent_slot_status")) for row in accepted_candidates)
    rejected_code_counts: Counter[str] = Counter()
    blocker_code_counts: Counter[str] = Counter()
    for row in rejected_rows:
        rejected_code_counts.update(row["rejection_codes"])
    for row in blockers:
        blocker_code_counts.update(row["blocker_codes"])

    candidate_output_ref = (
        "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/"
        "private_causal_evidence_return_candidates.jsonl"
    )
    decision = (
        "private_executor_returns_adapted_to_stage12516_candidate_rows"
        if accepted_candidates
        else "blocked_no_stage12516_candidate_rows_from_private_executor_returns"
    )
    adapter_contract = {
        "record_type": "stage12522_private_causal_evidence_executor_return_adapter_contract_v1",
        "stage": STAGE,
        "source_stage": STAGE12521,
        "source_handoff_contract_record_type": contract.get("record_type"),
        "executor_return_input_filenames": EXECUTOR_RETURN_FILENAMES,
        "target_stage12516_candidate_output_ref": candidate_output_ref,
        "target_stage12516_candidate_record_type": RETURN_RECORD_TYPE,
        "required_stage12516_candidate_return_fields": REQUIRED_STAGE12516_RETURN_FIELDS,
        "output_scope": "executor_return_adapter_to_stage12516_candidates_or_hard_blocker_only",
        "status_hash_as_proof_gate": "status_hashes_and_digest_hashes_are_never_proof",
        "observed_action_imitation_gate": "observed_actions_must_not_be_available_or_used_as_labels",
        "pass_to_pass_gate": "pass_to_pass_support_only_not_repair_credit",
        "root_or_window_hash_gate": "root_or_window_hash_context_only_not_unique_identity_or_dedupe_key",
        "no_dedupe_dropping_slots_gate": "one_candidate_per_acquisition_work_order_id_hash_and_evidence_slot_no_root_hash_dedupe",
        "semantic_sufficiency_gate": "downstream_stage12516_validation_then_stage12519_semantic_sufficiency_required",
        "public_artifact_policy": "hash_enum_status_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    summary = {
        "stage": STAGE,
        "record_type": "stage12522_private_causal_evidence_executor_return_adapter_summary_v1",
        "decision": decision,
        "claim_boundary": (
            "Stage12522 adapts present private executor return rows into exact Stage12516 "
            "candidate-return rows. It does not execute, infer, fabricate statuses, validate "
            "proof, admit rows, write Stage12503 returns, or emit raw private material."
        ),
        "source_stage": STAGE12521,
        "input_handoff_shard_count": len(shards),
        "expected_slot_ref_count": len(slot_refs),
        "preserved_slot_identity_count": len({_full_slot_identity(row) for row in slot_refs}),
        "executor_return_file_present": executor_return_path is not None,
        "executor_return_record_count": len(executor_returns),
        "executed_slot_return_count": executed_count,
        "accepted_stage12516_candidate_count": len(accepted_candidates),
        "rejected_executor_return_count": len(rejected_rows),
        "missing_slot_return_count": missing_count,
        "blocked_slot_count": len(blockers),
        "candidate_output_written": executor_return_path is not None,
        "candidate_output_path": str(target_output.relative_to(root)),
        "target_stage12516_candidate_output_ref": candidate_output_ref,
        "target_stage12516_candidate_record_type": RETURN_RECORD_TYPE,
        "candidate_output_row_count": len(accepted_candidates),
        "validated_present_fabricated": False,
        "blocked_unavailable_fabricated": False,
        "dedupe_dropped_slot_count": 0,
        "full_seven_slot_set_seen": sorted(slot_counts) == sorted(FULL_SEVEN_SLOTS),
        "evidence_slot_counts": dict(sorted(slot_counts.items())),
        "accepted_status_counts": dict(sorted(accepted_status_counts.items())),
        "rejection_code_counts": dict(sorted(rejected_code_counts.items())),
        "blocker_code_counts": dict(sorted(blocker_code_counts.items())),
        "status_hash_as_proof_gate": "status_hashes_and_digest_hashes_are_never_proof",
        "observed_action_imitation_gate": "do_not_infer_or_copy_labels_from_observed_actions",
        "pass_to_pass_gate": "pass_to_pass_support_only_not_repair_credit",
        "root_or_window_hash_gate": "root_or_window_hash_context_only_not_unique_identity_or_dedupe_key",
        "no_dedupe_dropping_slots_gate": "preserve_one_slot_identity_per_acquisition_work_order_id_hash_and_evidence_slot",
        "semantic_sufficiency_gate": "downstream_stage12516_validation_then_stage12519_semantic_sufficiency_required",
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        "next_stage": "run_stage12516_private_causal_evidence_return_preflight_then_stage12519_semantic_sufficiency_gate",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    guardrail_scan = {
        "stage": STAGE,
        "scan_passed": True,
        "raw_leak_count": 0,
        "raw_leak_issue_hashes": [],
        "scanned_outputs": [
            "adapted_stage12516_candidate_return_audit.jsonl",
            "rejected_private_executor_returns.jsonl",
            "private_causal_evidence_executor_return_blockers.jsonl",
            "private_causal_evidence_executor_return_adapter_contract.json",
            "summary.json",
        ],
    }
    outputs = {
        "accepted_adapter_rows": accepted_adapter_rows,
        "rejected_rows": rejected_rows,
        "blockers": blockers,
        "adapter_contract": adapter_contract,
        "summary": summary,
        "guardrail_scan": guardrail_scan,
    }
    enforce_no_raw_leaks(outputs)

    write_jsonl(out / "adapted_stage12516_candidate_return_audit.jsonl", accepted_adapter_rows)
    write_jsonl(out / "rejected_private_executor_returns.jsonl", rejected_rows)
    write_jsonl(out / "private_causal_evidence_executor_return_blockers.jsonl", blockers)
    write_json(out / "private_causal_evidence_executor_return_adapter_contract.json", adapter_contract)
    write_json(out / "guardrail_scan.json", guardrail_scan)
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()

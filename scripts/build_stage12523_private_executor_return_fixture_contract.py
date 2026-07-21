#!/usr/bin/env python3
"""Build a public-safe private executor return fixture contract.

Stage12523 consumes Stage12522 blockers and Stage12521 handoff shards. It emits
the exact per-slot return contract a private executor must satisfy, plus a
runbook for acquiring those returns. It does not execute, infer proof, fabricate
statuses, write Stage12516 candidate rows, write Stage12503 rows, or expose raw
paths, commands, diffs, source, verifier output, training, admission, Level-3,
or patch-trace material.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12523_private_executor_return_fixture_contract"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12521 = "stage12521_private_causal_evidence_executor_handoff_contract"
STAGE12522 = "stage12522_private_causal_evidence_executor_return_adapter"
STAGE12515 = "stage12515_private_causal_evidence_acquisition_work_orders"

RETURN_RECORD_TYPE = "stage12516_private_causal_evidence_return_candidate_v1"
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
ALLOWED_EXECUTOR_STATUSES = ["blocked_unavailable", "not_applicable", "validated_absent", "validated_present"]

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
    "stage12516_candidate_rows_written": False,
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
    "blocked_unavailable_treated_as_proof": False,
}
ZERO_GUARDS = {
    "candidate_return_records_written": 0,
    "validated_return_records_written": 0,
    "stage12516_candidate_row_count": 0,
    "stage12503_return_records_written": 0,
    "training_rows_emitted": 0,
    "admitted_rows": 0,
    "level3_admitted": 0,
    "level3_atom_count": 0,
    "patch_trace_admitted": 0,
    "patch_trace_rows": 0,
    "policy_labels_emitted": 0,
    "proof_rows_emitted": 0,
}


class RawLeakError(ValueError):
    pass


class SlotAccountingError(ValueError):
    pass


class ProductionFixtureGenerationError(RuntimeError):
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
        raise RawLeakError(f"stage12523 raw leak guard rejected {len(issues)} public field(s)")


def _safe_str(row: dict[str, Any], field: str) -> str:
    value = row.get(field)
    return value if isinstance(value, str) else ""


def _slot_identity(row: dict[str, Any]) -> tuple[str, str]:
    return (_safe_str(row, "acquisition_work_order_id_hash"), _safe_str(row, "evidence_slot"))


def _full_slot_identity(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(_safe_str(row, field) for field in ["acquisition_work_order_id_hash", *IDENTITY_FIELDS])


def flatten_slot_refs(shards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        slot_ref
        for shard in shards
        for slot_ref in (shard.get("slot_refs") or [])
        if isinstance(slot_ref, dict)
    ]


def validate_slot_accounting(slot_refs: list[dict[str, Any]], blockers: list[dict[str, Any]]) -> None:
    if len(slot_refs) != len({_full_slot_identity(row) for row in slot_refs}):
        raise SlotAccountingError("stage12523 Stage12521 handoff contains duplicate full slot identities")
    if Counter(_slot_identity(row) for row in slot_refs) != Counter(_slot_identity(row) for row in blockers):
        raise SlotAccountingError("stage12523 Stage12522 blockers do not match Stage12521 slot identities")
    if set(_safe_str(row, "evidence_slot") for row in slot_refs) != set(FULL_SEVEN_SLOTS):
        raise SlotAccountingError("stage12523 did not preserve the full seven-slot set")


def _executor_field_contract(slot_ref: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_return_record_type": RETURN_RECORD_TYPE,
        "required_fields_in_exact_stage12516_order": REQUIRED_STAGE12516_RETURN_FIELDS,
        "identity_fields_must_equal_slot_ref": ["acquisition_work_order_id_hash", *IDENTITY_FIELDS],
        "allowed_independent_slot_statuses": ALLOWED_EXECUTOR_STATUSES,
        "preferred_private_executor_status_when_supported": "validated_present",
        "non_present_statuses_are_not_proof": True,
        "digest_hash_fields_required_but_not_proof": ["independent_evidence_digest_hash", "causal_review_digest_hash"],
        "reviewer_hash_fields_required": ["private_reviewer_id_hash", "reviewer_conflict_check_hash"],
        "required_false_fields": [
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
        "required_true_fields": [
            "reviewer_independence_attestation",
            "acceptance_criteria_passed",
            "candidate_action_set_blinded",
            "label_leak_attestation",
            "model_facing_gold_fields_excluded",
            "repair_credit_requires_before_fail_after_pass_same_verifier",
        ],
        "required_zero_fields": ["stage12503_return_records_written"],
        "blocker_codes_on_validated_present": [],
        "slot_evidence_kind": slot_ref.get("evidence_slot"),
    }


def contract_row(slot_ref: dict[str, Any], blocker: dict[str, Any] | None) -> dict[str, Any]:
    row = {
        "record_type": "stage12523_private_executor_return_fixture_contract_slot_v1",
        "fixture_contract_slot_id_hash": stable_hash({"slot": _full_slot_identity(slot_ref)}),
        **{field: slot_ref.get(field) for field in ["acquisition_work_order_id_hash", *IDENTITY_FIELDS]},
        "stage12521_expanded_slot_id_hash": slot_ref.get("expanded_slot_id_hash"),
        "stage12522_blocker_id_hash": blocker.get("blocker_id_hash") if blocker else None,
        "stage12522_blocker_codes": sorted(set(blocker.get("blocker_codes") or [])) if blocker else [],
        "executor_return_filename_contract": "private_causal_evidence_executor_returns.jsonl",
        "executor_must_return": _executor_field_contract(slot_ref),
        "stage12522_adapter_target_output_ref": (
            "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/"
            "private_causal_evidence_return_candidates.jsonl"
        ),
        "private_executor_return_required_before_stage12516_candidate_rows": True,
        "blocker_status_is_acquisition_reason_not_proof": True,
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks(row)
    return row


def build_contract_rows(slot_refs: list[dict[str, Any]], blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocker_by_identity = {_slot_identity(row): row for row in blockers}
    return [contract_row(slot_ref, blocker_by_identity.get(_slot_identity(slot_ref))) for slot_ref in slot_refs]


def generate_test_only_fixture_templates(root: Path) -> Path:
    """Write non-executable template rows under a non-production temp root only."""
    if root.resolve() == ROOT.resolve():
        raise ProductionFixtureGenerationError("stage12523 fixture templates are test-only and cannot be written at production root")
    out = root / "runs/local/artifacts" / STAGE
    rows = read_jsonl(out / "private_executor_return_fixture_contract_slots.jsonl")
    templates = []
    for row in rows:
        templates.append(
            {
                "record_type": "stage12523_test_only_private_executor_return_template_v1",
                "template_id_hash": stable_hash({"template": row["fixture_contract_slot_id_hash"]}),
                **{field: row.get(field) for field in ["acquisition_work_order_id_hash", *IDENTITY_FIELDS]},
                "target_return_record_type": RETURN_RECORD_TYPE,
                "required_fields_in_exact_stage12516_order": REQUIRED_STAGE12516_RETURN_FIELDS,
                "placeholder_status": "private_executor_must_choose_after_real_private_review",
                "not_a_stage12516_candidate_return": True,
                "not_adapter_consumable": True,
                "test_only_temp_root": True,
                "public_safe_status_only": True,
                **FALSE_GUARDS,
                **ZERO_GUARDS,
            }
        )
    enforce_no_raw_leaks(templates)
    path = out / "test_only_private_executor_return_templates.jsonl"
    write_jsonl(path, templates)
    return path


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    stage12521_out = root / "runs/local/artifacts" / STAGE12521
    stage12522_out = root / "runs/local/artifacts" / STAGE12522

    shards = read_jsonl(stage12521_out / "private_causal_evidence_executor_handoff_shards.jsonl")
    blockers = read_jsonl(stage12522_out / "private_causal_evidence_executor_return_blockers.jsonl")
    stage12522_summary = read_json(stage12522_out / "summary.json")
    slot_refs = flatten_slot_refs(shards)
    validate_slot_accounting(slot_refs, blockers)
    rows = build_contract_rows(slot_refs, blockers)

    slot_counts = Counter(_safe_str(row, "evidence_slot") for row in slot_refs)
    blocker_code_counts: Counter[str] = Counter()
    for row in blockers:
        blocker_code_counts.update(row.get("blocker_codes") or [])
    runbook = {
        "record_type": "stage12523_private_executor_return_acquisition_runbook_v1",
        "stage": STAGE,
        "source_stages": [STAGE12521, STAGE12522],
        "executor_return_file_must_be_placed_under_stage12521": "private_causal_evidence_executor_returns.jsonl",
        "executor_return_rows_must_match_contract_slots": len(rows),
        "target_return_record_type": RETURN_RECORD_TYPE,
        "required_stage12516_candidate_return_fields": REQUIRED_STAGE12516_RETURN_FIELDS,
        "adapter_to_run_after_real_returns": STAGE12522,
        "stage12516_candidate_output_ref_after_adapter_only": (
            "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/"
            "private_causal_evidence_return_candidates.jsonl"
        ),
        "status_hash_as_proof_gate": "status_hashes_and_digest_hashes_are_never_proof",
        "blocked_unavailable_gate": "blocked_unavailable_is_a_blocker_or_executor_status_not_proof",
        "validated_present_gate": "validated_present_requires_real_private_executor_return_row",
        "root_or_window_hash_gate": "root_or_window_hash_context_only_not_unique_identity_or_dedupe_key",
        "no_dedupe_dropping_slots_gate": "preserve_one_contract_row_per_stage12521_slot_ref",
        "public_artifact_policy": "hash_enum_status_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        "production_fixture_generator_allowed": False,
        "test_only_fixture_templates_available_by_explicit_temp_root_helper": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    summary = {
        "stage": STAGE,
        "record_type": "stage12523_private_executor_return_fixture_contract_summary_v1",
        "decision": "private_executor_return_fixture_contract_and_runbook_written_no_candidate_rows",
        "claim_boundary": (
            "Stage12523 converts Stage12522 blockers and Stage12521 slot refs into a public-safe "
            "executor-return acquisition contract. Blockers are not proof, validated_present is not "
            "fabricated, and Stage12516 candidate rows remain unwritten until real private executor "
            "returns exist under Stage12521."
        ),
        "source_stages": [STAGE12521, STAGE12522],
        "input_handoff_shard_count": len(shards),
        "input_stage12522_blocker_count": len(blockers),
        "contract_slot_count": len(rows),
        "preserved_slot_identity_count": len({_full_slot_identity(row) for row in slot_refs}),
        "dedupe_dropped_slot_count": 0,
        "full_seven_slot_set_seen": sorted(slot_counts) == sorted(FULL_SEVEN_SLOTS),
        "evidence_slot_counts": dict(sorted(slot_counts.items())),
        "blocker_code_counts": dict(sorted(blocker_code_counts.items())),
        "stage12522_executor_return_file_present": bool(stage12522_summary.get("executor_return_file_present")),
        "stage12522_candidate_output_written": bool(stage12522_summary.get("candidate_output_written")),
        "stage12522_candidate_output_row_count": int(stage12522_summary.get("candidate_output_row_count") or 0),
        "target_return_record_type": RETURN_RECORD_TYPE,
        "required_stage12516_candidate_return_field_count": len(REQUIRED_STAGE12516_RETURN_FIELDS),
        "candidate_output_written": False,
        "candidate_output_path": "",
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        "next_stage": "private_executor_writes_real_return_file_under_stage12521_then_stage12522_adapts_to_stage12516",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    guardrail_scan = {
        "stage": STAGE,
        "scan_passed": True,
        "raw_leak_count": 0,
        "raw_leak_issue_hashes": [],
        "scanned_outputs": [
            "private_executor_return_fixture_contract_slots.jsonl",
            "private_executor_return_acquisition_runbook.json",
            "summary.json",
        ],
    }
    outputs = {"rows": rows, "runbook": runbook, "summary": summary, "guardrail_scan": guardrail_scan}
    enforce_no_raw_leaks(outputs)

    write_jsonl(out / "private_executor_return_fixture_contract_slots.jsonl", rows)
    write_json(out / "private_executor_return_acquisition_runbook.json", runbook)
    write_json(out / "guardrail_scan.json", guardrail_scan)
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Audit whether the Stage12523 executor-return contract is executable.

Stage12524 consumes Stage12523 contract slots/runbook and Stage12521 handoff
shards. It checks for public-safe private resolver/executor readiness manifests
in the current artifact tree. If they are missing, it emits exact blocker codes
and zero returns. If present, it emits a public-safe invocation/readiness plan
that points to the expected Stage12521 return filename. It never executes the
private executor, fabricates return rows, writes Stage12516/Stage12503 rows, or
emits training/admission/Level-3/patch-trace material.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12524_private_executor_invocation_readiness_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12521 = "stage12521_private_causal_evidence_executor_handoff_contract"
STAGE12523 = "stage12523_private_executor_return_fixture_contract"

RETURN_FILENAME = "private_causal_evidence_executor_returns.jsonl"
RESOLVER_MANIFEST = "private_executor_resolver_readiness_manifest.json"
EXECUTOR_MANIFEST = "private_executor_runtime_readiness_manifest.json"

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
    "executor_return_rows_fabricated": False,
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
    "executor_return_records_written": 0,
}

REQUIRED_RESOLVER_FIELDS = {
    "record_type": "stage12524_private_executor_resolver_readiness_manifest_v1",
    "private_resolver_ready": True,
    "private_locator_inputs_available": True,
    "public_safe_status_only": True,
}
REQUIRED_EXECUTOR_FIELDS = {
    "record_type": "stage12524_private_executor_runtime_readiness_manifest_v1",
    "private_executor_ready": True,
    "supports_stage12516_return_schema": True,
    "public_safe_status_only": True,
}

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


class RawLeakError(ValueError):
    pass


class SlotAccountingError(ValueError):
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
        raise RawLeakError(f"stage12524 raw leak guard rejected {len(issues)} public field(s)")


def _safe_str(row: dict[str, Any], field: str) -> str:
    value = row.get(field)
    return value if isinstance(value, str) else ""


def _slot_identity(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(_safe_str(row, field) for field in ["acquisition_work_order_id_hash", *IDENTITY_FIELDS])


def flatten_slot_refs(shards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        slot_ref
        for shard in shards
        for slot_ref in (shard.get("slot_refs") or [])
        if isinstance(slot_ref, dict)
    ]


def validate_slot_accounting(contract_slots: list[dict[str, Any]], shard_slot_refs: list[dict[str, Any]]) -> None:
    contract_counter = Counter(_slot_identity(row) for row in contract_slots)
    shard_counter = Counter(_slot_identity(row) for row in shard_slot_refs)
    if contract_counter != shard_counter:
        raise SlotAccountingError("stage12524 Stage12523 contract slots do not match Stage12521 shard slot refs")
    if len(contract_slots) != len(contract_counter):
        raise SlotAccountingError("stage12524 duplicate contract slot identity detected")
    if set(_safe_str(row, "evidence_slot") for row in contract_slots) != set(FULL_SEVEN_SLOTS):
        raise SlotAccountingError("stage12524 did not preserve the full seven-slot set")


def _manifest_blockers(manifest: dict[str, Any], required: dict[str, Any], slot_count: int, count_field: str, prefix: str) -> list[str]:
    blockers: list[str] = []
    if not manifest:
        return [f"{prefix}_manifest_missing"]
    for field, expected in required.items():
        if manifest.get(field) != expected:
            blockers.append(f"{prefix}_{field}_missing_or_false")
    if int(manifest.get(count_field) or -1) != slot_count:
        blockers.append(f"{prefix}_{count_field}_mismatch")
    return blockers


def audit_private_inputs(root: Path, slot_count: int, expected_return_filename: str) -> tuple[bool, list[str], dict[str, Any]]:
    stage12521_out = root / "runs/local/artifacts" / STAGE12521
    resolver = read_json(stage12521_out / RESOLVER_MANIFEST)
    executor = read_json(stage12521_out / EXECUTOR_MANIFEST)
    blocker_codes = []
    blocker_codes.extend(_manifest_blockers(resolver, REQUIRED_RESOLVER_FIELDS, slot_count, "resolver_slot_count", "private_resolver"))
    blocker_codes.extend(_manifest_blockers(executor, REQUIRED_EXECUTOR_FIELDS, slot_count, "executor_slot_count", "private_executor"))
    if executor and executor.get("expected_executor_return_filename") != expected_return_filename:
        blocker_codes.append("private_executor_expected_return_filename_mismatch")
    inputs = {
        "private_resolver_manifest_present": bool(resolver),
        "private_executor_manifest_present": bool(executor),
        "private_resolver_manifest_id_hash": resolver.get("readiness_manifest_id_hash") if resolver else "",
        "private_executor_manifest_id_hash": executor.get("readiness_manifest_id_hash") if executor else "",
    }
    return not blocker_codes, sorted(set(blocker_codes)), inputs


def blocker_rows(contract_slots: list[dict[str, Any]], blocker_codes: list[str]) -> list[dict[str, Any]]:
    rows = []
    for slot in contract_slots:
        row = {
            "record_type": "stage12524_private_executor_invocation_readiness_blocker_v1",
            "readiness_blocker_id_hash": stable_hash({"blocker": _slot_identity(slot), "codes": blocker_codes}),
            **{field: slot.get(field) for field in ["acquisition_work_order_id_hash", *IDENTITY_FIELDS]},
            "stage12523_fixture_contract_slot_id_hash": slot.get("fixture_contract_slot_id_hash"),
            "blocker_codes": blocker_codes,
            "executor_return_filename_expected_under_stage12521": RETURN_FILENAME,
            "zero_executor_returns_emitted": True,
            "public_safe_status_only": True,
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        enforce_no_raw_leaks(row)
        rows.append(row)
    return rows


def invocation_plan(
    shards: list[dict[str, Any]],
    contract_slots: list[dict[str, Any]],
    inputs: dict[str, Any],
    runbook: dict[str, Any],
) -> dict[str, Any]:
    plan_shards = []
    for shard in shards:
        row = {
            "executor_handoff_shard_id_hash": shard.get("executor_handoff_shard_id_hash"),
            "priority_rank": shard.get("priority_rank"),
            "language_family": shard.get("language_family"),
            "task_family": shard.get("task_family"),
            "source_stage_name": shard.get("source_stage_name"),
            "evidence_slot": shard.get("evidence_slot"),
            "slot_ref_count": shard.get("slot_ref_count"),
        }
        enforce_no_raw_leaks(row)
        plan_shards.append(row)
    plan = {
        "record_type": "stage12524_private_executor_invocation_readiness_plan_v1",
        "stage": STAGE,
        "decision": "ready_public_safe_executor_invocation_plan_written_no_returns",
        "source_stages": [STAGE12521, STAGE12523],
        "private_resolver_manifest_id_hash": inputs["private_resolver_manifest_id_hash"],
        "private_executor_manifest_id_hash": inputs["private_executor_manifest_id_hash"],
        "executor_return_filename_expected_under_stage12521": RETURN_FILENAME,
        "executor_return_file_ref_for_future_stage12522_adapter": (
            f"runs/local/artifacts/{STAGE12521}/{RETURN_FILENAME}"
        ),
        "expected_stage12521_return_row_count": len(contract_slots),
        "executor_return_rows_must_match_stage12523_contract_slots": len(contract_slots),
        "stage12523_runbook_expected_row_count": runbook.get("executor_return_rows_must_match_contract_slots"),
        "invocation_boundary": "plan_only_private_executor_not_invoked_by_stage12524",
        "return_boundary": "no_executor_return_rows_written_or_fabricated",
        "adapter_after_real_returns": runbook.get("adapter_to_run_after_real_returns"),
        "stage12516_candidate_output_ref_after_stage12522_only": runbook.get("stage12516_candidate_output_ref_after_adapter_only"),
        "shard_plan_count": len(plan_shards),
        "slot_identity_count": len({_slot_identity(row) for row in contract_slots}),
        "shards": plan_shards,
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks(plan)
    return plan


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    stage12521_out = root / "runs/local/artifacts" / STAGE12521
    stage12523_out = root / "runs/local/artifacts" / STAGE12523

    shards = read_jsonl(stage12521_out / "private_causal_evidence_executor_handoff_shards.jsonl")
    contract_slots = read_jsonl(stage12523_out / "private_executor_return_fixture_contract_slots.jsonl")
    runbook = read_json(stage12523_out / "private_executor_return_acquisition_runbook.json")
    shard_slot_refs = flatten_slot_refs(shards)
    enforce_no_raw_leaks({"shards": shards, "contract_slots": contract_slots, "runbook": runbook})
    validate_slot_accounting(contract_slots, shard_slot_refs)

    expected_return_filename = str(runbook.get("executor_return_file_must_be_placed_under_stage12521") or RETURN_FILENAME)
    ready, blocker_codes, inputs = audit_private_inputs(root, len(contract_slots), expected_return_filename)
    rows = blocker_rows(contract_slots, blocker_codes) if not ready else []
    plan = invocation_plan(shards, contract_slots, inputs, runbook) if ready else {}

    slot_counts = Counter(_safe_str(row, "evidence_slot") for row in contract_slots)
    summary = {
        "stage": STAGE,
        "record_type": "stage12524_private_executor_invocation_readiness_summary_v1",
        "decision": (
            "ready_public_safe_executor_invocation_plan_written_no_returns"
            if ready
            else "blocked_missing_private_executor_inputs_zero_returns"
        ),
        "claim_boundary": (
            "Stage12524 audits executor readiness only. It checks public-safe resolver/executor "
            "readiness manifests, preserves every Stage12521/Stage12523 slot identity, and writes "
            "no private executor returns, Stage12516 candidates, Stage12503 rows, training, "
            "admission, Level-3, or patch-trace material."
        ),
        "source_stages": [STAGE12521, STAGE12523],
        "input_stage12521_handoff_shard_count": len(shards),
        "input_stage12521_slot_ref_count": len(shard_slot_refs),
        "input_stage12523_contract_slot_count": len(contract_slots),
        "preserved_slot_identity_count": len({_slot_identity(row) for row in contract_slots}),
        "dedupe_dropped_slot_count": 0,
        "full_seven_slot_set_seen": sorted(slot_counts) == sorted(FULL_SEVEN_SLOTS),
        "evidence_slot_counts": dict(sorted(slot_counts.items())),
        "readiness_blocker_codes": blocker_codes,
        "readiness_blocker_count": len(blocker_codes),
        "readiness_blocker_row_count": len(rows),
        "executor_invocation_ready": ready,
        "private_resolver_manifest_present": inputs["private_resolver_manifest_present"],
        "private_executor_manifest_present": inputs["private_executor_manifest_present"],
        "executor_return_filename_expected_under_stage12521": RETURN_FILENAME,
        "expected_stage12521_return_row_count": len(contract_slots) if ready else 0,
        "invocation_plan_written": ready,
        "executor_return_file_written": False,
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        "next_stage": (
            "private_executor_may_write_real_return_file_under_stage12521_then_stage12522_adapter_runs"
            if ready
            else "provide_public_safe_private_resolver_and_executor_readiness_manifests_then_rerun_stage12524"
        ),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    guardrail_scan = {
        "stage": STAGE,
        "scan_passed": True,
        "raw_leak_count": 0,
        "raw_leak_issue_hashes": [],
        "scanned_outputs": [
            "private_executor_invocation_readiness_blockers.jsonl",
            "private_executor_invocation_readiness_plan.json",
            "summary.json",
        ],
    }
    outputs = {"rows": rows, "plan": plan, "summary": summary, "guardrail_scan": guardrail_scan}
    enforce_no_raw_leaks(outputs)

    write_jsonl(out / "private_executor_invocation_readiness_blockers.jsonl", rows)
    write_json(out / "private_executor_invocation_readiness_plan.json", plan)
    write_json(out / "guardrail_scan.json", guardrail_scan)
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()

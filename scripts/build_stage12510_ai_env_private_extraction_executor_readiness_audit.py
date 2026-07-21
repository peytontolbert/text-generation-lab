#!/usr/bin/env python3
"""Audit whether Stage12509 has an authorized ai_env return executor.

Stage12510 is deliberately fail-closed. It consumes Stage12509 work orders and
classifies in-repo executor candidates. It does not inspect raw private
material, execute work orders, write Stage12503 returns, admit rows, emit
Level-3 atoms, or train.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12510_ai_env_private_extraction_executor_readiness_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12509 = "stage12509_ai_env_private_extraction_return_work_order"
WORK_ORDERS = ROOT / "runs/local/artifacts" / STAGE12509 / "ai_env_private_extraction_return_work_orders.jsonl"
STAGE12502 = "stage12502_authoritative_private_semantic_extraction_request_preflight"
STAGE12503_RETURN_FILE = ROOT / "runs/local/artifacts" / STAGE12502 / "private_semantic_extraction_returns.jsonl"

EXECUTOR_BINDING_ENV = "STAGE12510_AI_ENV_PRIVATE_EXTRACTOR"
RETURN_RECORD_TYPE = "stage12503_authoritative_private_semantic_extraction_return_v1"

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output|commit:)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)

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
    "stage12503_return_materialized": False,
    "stage12503_return_file_written": False,
    "raw_source_inspected": False,
    "extraction_run": False,
}

ZERO_GUARDS = {
    "training_rows_emitted": 0,
    "admitted_rows": 0,
    "level3_admitted": 0,
    "level3_atom_count": 0,
    "patch_trace_admitted": 0,
    "patch_trace_rows": 0,
    "stage12503_return_records_written": 0,
    "return_record_count": 0,
    "validated_private_semantic_extraction_return_count": 0,
    "rejected_private_semantic_extraction_return_count": 0,
    "policy_labels_emitted": 0,
    "proof_rows_emitted": 0,
    "proof_grade_repair_rows": 0,
    "external_repair_credit_count": 0,
    "sealed_eval_rows": 0,
}

REQUIRED_EXECUTOR_CAPABILITIES = [
    "consume_stage12509_work_orders",
    "run_inside_ai_env_not_trellis",
    "inspect_private_source_stage_locator_refs_without_public_raw_leakage",
    "emit_stage12503_authoritative_return_records_only",
    "emit_hash_status_enum_only_public_fields",
    "prove_extractor_authority_and_conflict_check",
    "prove_source_locator_and_causal_review_hashes",
    "fill_requested_private_extraction_slots_with_allowed_statuses",
    "set_raw_private_values_revealed_false",
    "set_raw_source_output_included_false",
    "set_local_model_authority_false",
    "set_policy_label_emitted_false",
    "set_training_and_admission_counters_zero",
    "write_private_semantic_extraction_returns_atomically",
]

SCRIPT_CANDIDATES = [
    {
        "stage_ref": "stage12485_private_proof_bundle_executor_v1",
        "script": "scripts/build_stage12485_private_proof_bundle_executor_v1.py",
        "classification": "stage12468_private_proof_executor_not_stage12503_semantic_extractor",
        "stage12509_compatible": False,
    },
    {
        "stage_ref": "stage12487_private_proof_bundle_fill_runner_skeleton",
        "script": "scripts/build_stage12487_private_proof_bundle_fill_runner_skeleton.py",
        "classification": "fill_runner_skeleton_not_authorized_stage12503_return_writer",
        "stage12509_compatible": False,
    },
    {
        "stage_ref": "stage12503_private_semantic_extraction_return_validator",
        "script": "scripts/build_stage12503_private_semantic_extraction_return_validator.py",
        "classification": "validator_not_executor",
        "stage12509_compatible": False,
    },
    {
        "stage_ref": "stage12509_ai_env_private_extraction_return_work_order",
        "script": "scripts/build_stage12509_ai_env_private_extraction_return_work_order.py",
        "classification": "work_order_template_builder_no_execution",
        "stage12509_compatible": False,
    },
]


class RawLeakError(ValueError):
    pass


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
        for child in value.values():
            issues.extend(scan_raw_leaks(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan_raw_leaks(child))
    return issues


def enforce_no_raw_leaks(value: Any) -> None:
    issues = scan_raw_leaks(value)
    if issues:
        raise RawLeakError(f"stage12510 raw leak guard rejected {len(issues)} public field(s)")


def classify_scripts(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in SCRIPT_CANDIDATES:
        script_path = root / candidate["script"]
        row = {
            "record_type": "stage12510_executor_candidate_classification_v1",
            "stage_ref": candidate["stage_ref"],
            "script_ref_hash": stable_hash(candidate["script"]),
            "script_present": script_path.exists(),
            "script_sha256_24": file_hash(script_path),
            "classification": candidate["classification"],
            "stage12509_compatible_executor": candidate["stage12509_compatible"],
            "raw_private_values_revealed": False,
            "raw_source_output_included": False,
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        enforce_no_raw_leaks(row)
        rows.append(row)
    return rows


def work_order_blockers(row: dict[str, Any], executor_ready: bool) -> list[str]:
    blockers: list[str] = []
    if row.get("record_type") != "stage12509_ai_env_private_extraction_return_work_order_v1":
        blockers.append("not_stage12509_work_order")
    if row.get("template_only") is not True or row.get("not_authoritative_return") is not True:
        blockers.append("work_order_not_marked_template_only")
    if row.get("materialization_environment") != "ai_env":
        blockers.append("materialization_environment_not_ai_env")
    if row.get("stage12503_return_record_type") != RETURN_RECORD_TYPE:
        blockers.append("stage12503_return_record_type_mismatch")
    if row.get("stage12503_return_records_written") != 0:
        blockers.append("work_order_claims_stage12503_returns_written")
    if row.get("training_rows_emitted") != 0 or row.get("admitted_rows") != 0:
        blockers.append("work_order_claims_training_or_admission")
    if not row.get("missing_private_proof_slots"):
        blockers.append("missing_private_proof_slots_absent")
    if not executor_ready:
        blockers.append("trusted_ai_env_private_extractor_binding_missing")
        blockers.append("no_authorized_stage12503_return_writer_configured")
    return sorted(set(blockers))


def binding_status(root: Path) -> dict[str, Any]:
    configured = os.environ.get(EXECUTOR_BINDING_ENV, "").strip()
    if not configured:
        return {
            "executor_binding_configured": False,
            "executor_binding_ref_hash": None,
            "executor_binding_script_present": False,
            "executor_binding_blocker_codes": [
                "trusted_ai_env_private_extractor_binding_missing",
                "no_authorized_stage12503_return_writer_configured",
            ],
        }
    binding_path = Path(configured)
    if not binding_path.is_absolute():
        binding_path = root / binding_path
    present = binding_path.exists() and binding_path.is_file()
    return {
        "executor_binding_configured": True,
        "executor_binding_ref_hash": stable_hash(str(binding_path)),
        "executor_binding_script_present": present,
        "executor_binding_blocker_codes": [] if present else ["configured_executor_binding_file_missing"],
    }


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    out.mkdir(parents=True, exist_ok=True)
    for stale_name in [
        "ai_env_private_extraction_executor_readiness_blockers.jsonl",
        "ai_env_private_extraction_executor_ready_work_orders.jsonl",
    ]:
        stale_path = out / stale_name
        if stale_path.exists() and stale_path.is_file():
            stale_path.unlink()
    work_orders = read_jsonl(root / "runs/local/artifacts" / STAGE12509 / "ai_env_private_extraction_return_work_orders.jsonl")
    binding = binding_status(root)
    script_rows = classify_scripts(root)
    compatible_script_count = sum(1 for row in script_rows if row["stage12509_compatible_executor"])
    authorized_executor_binding_count = int(
        bool(binding["executor_binding_configured"] and binding["executor_binding_script_present"])
    )
    executor_ready = bool(work_orders and authorized_executor_binding_count)

    blocked_rows: list[dict[str, Any]] = []
    blocker_counts: Counter[str] = Counter()
    for row in work_orders:
        enforce_no_raw_leaks(row)
        blockers = work_order_blockers(row, executor_ready)
        blocker_counts.update(blockers)
        blocked = {
            "record_type": "stage12510_ai_env_private_extraction_executor_blocker_v1",
            "executor_blocker_id_hash": stable_hash({"work_order": row.get("work_order_id_hash"), "blockers": blockers}),
            "work_order_id_hash": row.get("work_order_id_hash"),
            "request_id_hash": row.get("request_id_hash"),
            "audit_item_id_hash": row.get("audit_item_id_hash"),
            "packet_id_hash": row.get("packet_id_hash"),
            "root_or_window_hash": row.get("root_or_window_hash"),
            "source_stage": row.get("source_stage"),
            "source_kind": row.get("source_kind"),
            "task_family": row.get("task_family"),
            "language_family": row.get("language_family"),
            "blocker_codes": blockers,
            "executor_ready": executor_ready,
            "materialization_environment": "ai_env",
            "forbidden_materialization_environments": ["trellis"],
            "raw_private_values_revealed": False,
            "raw_source_output_included": False,
            "public_safe_status_only": True,
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        enforce_no_raw_leaks(blocked)
        blocked_rows.append(blocked)

    if not work_orders:
        blocker_counts.update(["stage12509_work_orders_missing"])
        blocked = {
            "record_type": "stage12510_ai_env_private_extraction_executor_blocker_v1",
            "executor_blocker_id_hash": stable_hash({"missing": "stage12509_work_orders"}),
            "blocker_codes": ["stage12509_work_orders_missing"],
            "executor_ready": False,
            "materialization_environment": "ai_env",
            "forbidden_materialization_environments": ["trellis"],
            "raw_private_values_revealed": False,
            "raw_source_output_included": False,
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        enforce_no_raw_leaks(blocked)
        blocked_rows.append(blocked)

    language_counts = Counter(row.get("language_family") for row in blocked_rows)
    task_counts = Counter(row.get("task_family") for row in blocked_rows)
    source_counts = Counter(row.get("source_stage") for row in blocked_rows)
    decision = (
        "ai_env_private_extraction_executor_binding_ready_manual_execution_still_required_no_returns_written"
        if executor_ready and not blocker_counts
        else "blocked_ai_env_private_extraction_executor_binding_missing_no_returns_written"
    )

    contract = {
        "record_type": "stage12510_ai_env_private_extraction_executor_readiness_contract_v1",
        "stage": STAGE,
        "input_stage": STAGE12509,
        "input_work_order_file_role": "ai_env_private_extraction_return_work_orders.jsonl",
        "materialization_environment": "ai_env",
        "forbidden_materialization_environments": ["trellis"],
        "executor_binding_env": EXECUTOR_BINDING_ENV,
        "required_executor_capabilities": REQUIRED_EXECUTOR_CAPABILITIES,
        "public_artifact_policy": "hashes_enums_status_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        "stage12510_does_not_execute_work_orders": True,
        "stage12510_does_not_write_stage12503_returns": True,
        "stage12503_return_file_role": "private_semantic_extraction_returns.jsonl",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    guardrail = {"stage": STAGE, "scan_passed": True, "raw_leak_count": 0, "raw_leak_issue_hashes": []}
    summary = {
        "stage": STAGE,
        "record_type": "stage12510_ai_env_private_extraction_executor_readiness_summary_v1",
        "decision": decision,
        "claim_boundary": "Executor readiness only. No ai_env execution, no Stage12503 returns, no proof validation, no row admission, no training.",
        "input_work_order_count": len(work_orders),
        "executor_ready_count": len(work_orders) if executor_ready and not blocker_counts else 0,
        "executor_blocker_count": len(blocked_rows) if not executor_ready or blocker_counts else 0,
        "stage12509_compatible_executor_count": compatible_script_count,
        "authorized_executor_binding_count": authorized_executor_binding_count,
        "executor_binding_configured": binding["executor_binding_configured"],
        "executor_binding_script_present": binding["executor_binding_script_present"],
        "executor_binding_blocker_codes": binding["executor_binding_blocker_codes"],
        "stage12503_return_file_present_before": (root / "runs/local/artifacts" / STAGE12502 / "private_semantic_extraction_returns.jsonl").exists(),
        "stage12503_return_file_written": False,
        "stage12503_return_records_written": 0,
        "blocker_code_counts": dict(sorted(blocker_counts.items())),
        "language_counts": dict(sorted((str(k), v) for k, v in language_counts.items())),
        "task_family_counts": dict(sorted((str(k), v) for k, v in task_counts.items())),
        "source_stage_counts": dict(sorted((str(k), v) for k, v in source_counts.items())),
        "materialization_environment": "ai_env",
        "forbidden_materialization_environments": ["trellis"],
        "next_stage": "configure_or_implement_trusted_ai_env_stage12503_return_writer_then_rerun_stage12510" if not executor_ready else "run_authorized_ai_env_private_extractor_to_write_stage12503_returns_then_rerun_stage12503",
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks({"contract": contract, "guardrail": guardrail, "summary": summary, "blocked": blocked_rows, "scripts": script_rows})
    write_jsonl(out / "ai_env_private_extraction_executor_blockers.jsonl", blocked_rows)
    write_jsonl(out / "executor_candidate_classifications.jsonl", script_rows)
    write_json(out / "ai_env_private_extraction_executor_readiness_contract.json", contract)
    write_json(out / "guardrail_scan.json", guardrail)
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()

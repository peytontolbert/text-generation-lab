#!/usr/bin/env python3
"""Build ai_env private extraction return work orders.

Stage12509 consumes Stage12508 handoff jobs and emits hash-only work orders plus
Stage12503 return templates. It does not inspect raw material, execute ai_env,
write Stage12503 returns, admit rows, produce Level-3 atoms, or train.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12509_ai_env_private_extraction_return_work_order"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12508 = "stage12508_ai_env_handoff_from_recovered_locator_worklist"
HANDOFF_JOBS = ROOT / "runs/local/artifacts" / STAGE12508 / "ai_env_private_extraction_handoff_jobs.jsonl"
STAGE12502 = "stage12502_authoritative_private_semantic_extraction_request_preflight"
RETURN_FILE_ROLE = "private_semantic_extraction_returns.jsonl"
RETURN_RECORD_TYPE = "stage12503_authoritative_private_semantic_extraction_return_v1"

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output|commit:)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)
ALLOWED_SLOT_STATUSES = ["validated_present", "validated_absent", "blocked_unavailable", "not_applicable"]
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
    "stage12496_return_records_written": 0,
    "stage12503_return_records_written": 0,
    "policy_labels_emitted": 0,
    "proof_rows_emitted": 0,
    "proof_grade_repair_rows": 0,
    "external_repair_credit_count": 0,
    "sealed_eval_rows": 0,
    "return_record_count": 0,
    "validated_private_semantic_extraction_return_count": 0,
    "rejected_private_semantic_extraction_return_count": 0,
}

class RawLeakError(ValueError):
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
        for child in value.values():
            issues.extend(scan_raw_leaks(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan_raw_leaks(child))
    return issues


def enforce_no_raw_leaks(value: Any) -> None:
    issues = scan_raw_leaks(value)
    if issues:
        raise RawLeakError(f"stage12509 raw leak guard rejected {len(issues)} public field(s)")


def requested_slots(job: dict[str, Any]) -> list[str]:
    contract = job.get("stage12503_return_contract") or {}
    slots = contract.get("requested_private_extraction_slots") or []
    return sorted(slot for slot in slots if isinstance(slot, str))


def build_template(job: dict[str, Any]) -> dict[str, Any]:
    slots = requested_slots(job)
    return {
        "record_type": RETURN_RECORD_TYPE,
        "template_only": True,
        "not_authoritative_return": True,
        "request_id_hash": job.get("request_id_hash"),
        "audit_item_id_hash": job.get("audit_item_id_hash"),
        "work_item_id_hash": job.get("work_item_id_hash"),
        "packet_id_hash": job.get("packet_id_hash"),
        "root_or_window_hash": job.get("root_or_window_hash"),
        "source_stage": job.get("source_stage"),
        "source_kind": job.get("source_kind"),
        "task_family": job.get("task_family"),
        "language_family": job.get("language_family"),
        "extractor_id_hash": "TO_BE_FILLED_SAFE_HASH",
        "extractor_authority_attestation": "TO_BE_FILLED_TRUE",
        "extractor_conflict_check_hash": "TO_BE_FILLED_SAFE_HASH",
        "requested_private_extraction_slots": slots,
        "extracted_slot_statuses": {slot: "TO_BE_FILLED_STATUS" for slot in slots},
        "extracted_slot_proof_hashes": {slot: "TO_BE_FILLED_SAFE_HASH_OR_NULL" for slot in slots},
        "source_locator_hash": "TO_BE_FILLED_SAFE_HASH",
        "causal_review_hash": "TO_BE_FILLED_SAFE_HASH",
        "patch_apply_status_enum": "TO_BE_FILLED_ENUM",
        "stop_continue_status_enum": "TO_BE_FILLED_ENUM",
        "raw_private_values_revealed": False,
        "raw_source_output_included": False,
        "local_model_authority": False,
        "policy_label_emitted": False,
        "acceptance_criteria_passed": "TO_BE_FILLED_TRUE",
        "blocker_codes": [],
        "training_allowed": False,
        "admission_allowed": False,
        "training_rows_emitted": 0,
        "admitted_rows": 0,
    }


def job_blockers(job: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if job.get("record_type") != "stage12508_ai_env_private_extraction_handoff_job_v1":
        blockers.append("not_stage12508_handoff_job")
    if job.get("materialization_environment") != "ai_env":
        blockers.append("handoff_job_materialization_environment_not_ai_env")
    if not requested_slots(job):
        blockers.append("requested_private_extraction_slots_missing")
    if job.get("source_stage_locator_ref_count", 0) <= 0:
        blockers.append("source_stage_locator_refs_missing")
    if job.get("context_locator_ref_count", 0) <= 0:
        blockers.append("context_locator_refs_missing")
    if job.get("stage12503_return_records_written") != 0:
        blockers.append("handoff_job_claims_stage12503_returns_written")
    if job.get("training_rows_emitted") != 0 or job.get("admitted_rows") != 0:
        blockers.append("handoff_job_claims_training_or_admission")
    return sorted(set(blockers))


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    out.mkdir(parents=True, exist_ok=True)
    jobs = read_jsonl(root / "runs/local/artifacts" / STAGE12508 / "ai_env_private_extraction_handoff_jobs.jsonl")
    work_orders: list[dict[str, Any]] = []
    templates: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    if not jobs:
        missing = {
            "record_type": "stage12509_ai_env_private_extraction_work_order_blocker_v1",
            "work_order_blocker_id_hash": stable_hash({"missing": "stage12508_handoff_jobs"}),
            "blocker_codes": [
                "no_private_extraction_return_work_order_templates_emitted",
                "stage12508_handoff_jobs_missing",
            ],
            "materialization_environment": "ai_env",
            "forbidden_materialization_environments": ["trellis"],
            "raw_private_values_revealed": False,
            "raw_source_output_included": False,
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        enforce_no_raw_leaks(missing)
        blockers.append(missing)

    for job in jobs:
        enforce_no_raw_leaks(job)
        blockers_for_job = job_blockers(job)
        common = {
            "request_id_hash": job.get("request_id_hash"),
            "audit_item_id_hash": job.get("audit_item_id_hash"),
            "work_item_id_hash": job.get("work_item_id_hash"),
            "packet_id_hash": job.get("packet_id_hash"),
            "root_or_window_hash": job.get("root_or_window_hash"),
            "source_stage": job.get("source_stage"),
            "source_kind": job.get("source_kind"),
            "task_family": job.get("task_family"),
            "language_family": job.get("language_family"),
            "materialization_environment": "ai_env",
            "forbidden_materialization_environments": ["trellis"],
            "raw_private_values_revealed": False,
            "raw_source_output_included": False,
            "public_safe_status_only": True,
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        if blockers_for_job:
            row = {
                "record_type": "stage12509_ai_env_private_extraction_work_order_blocker_v1",
                "work_order_blocker_id_hash": stable_hash({"job": job.get("handoff_job_id_hash"), "blockers": blockers_for_job}),
                "blocker_codes": blockers_for_job,
                **common,
            }
            enforce_no_raw_leaks(row)
            blockers.append(row)
            continue
        template = build_template(job)
        template_hash = stable_hash(template)
        work_order = {
            "record_type": "stage12509_ai_env_private_extraction_return_work_order_v1",
            "template_only": True,
            "not_authoritative_return": True,
            "work_order_id_hash": stable_hash({"job": job.get("handoff_job_id_hash"), "template": template_hash}),
            "handoff_job_id_hash": job.get("handoff_job_id_hash"),
            "return_template_hash": template_hash,
            "return_file_stage": STAGE12502,
            "return_file_role": RETURN_FILE_ROLE,
            "stage12503_return_record_type": RETURN_RECORD_TYPE,
            "stage12503_return_file_role": RETURN_FILE_ROLE,
            "required_return_fields": [
                "record_type", "request_id_hash", "audit_item_id_hash", "work_item_id_hash", "packet_id_hash",
                "root_or_window_hash", "source_stage", "source_kind", "task_family", "language_family",
                "extractor_id_hash", "extractor_authority_attestation", "extractor_conflict_check_hash",
                "requested_private_extraction_slots", "extracted_slot_statuses", "extracted_slot_proof_hashes",
                "source_locator_hash", "causal_review_hash", "raw_private_values_revealed",
                "raw_source_output_included", "local_model_authority", "policy_label_emitted",
                "acceptance_criteria_passed", "blocker_codes", "training_allowed", "admission_allowed",
                "training_rows_emitted", "admitted_rows",
            ],
            "allowed_slot_statuses": ALLOWED_SLOT_STATUSES,
            "missing_private_proof_slots": requested_slots(job),
            "source_stage_locator_ref_count": job.get("source_stage_locator_ref_count", 0),
            "context_locator_ref_count": job.get("context_locator_ref_count", 0),
            "executor_requirements": job.get("ai_env_executor_requirements") or [],
            "claim_boundary": "Work order/template only. Not a Stage12503 return, not semantic proof, not training/admission.",
            **common,
        }
        enforce_no_raw_leaks(work_order)
        enforce_no_raw_leaks(template)
        work_orders.append(work_order)
        templates.append({
            "record_type": "stage12509_stage12503_return_schema_template_v1",
            "template_only": True,
            "not_authoritative_return": True,
            "placeholder_only": True,
            "return_template_hash": template_hash,
            "stage12503_return_record_type": RETURN_RECORD_TYPE,
            "missing_private_proof_slots": requested_slots(job),
            "stage12503_return_record_template": template,
            **common,
        })

    leak_issues = scan_raw_leaks({"work_orders": work_orders, "templates": templates, "blockers": blockers})
    if leak_issues:
        raise RawLeakError("stage12509 raw leak guard rejected public outputs")
    language_counts = Counter(row.get("language_family") for row in [*work_orders, *blockers])
    task_counts = Counter(row.get("task_family") for row in [*work_orders, *blockers])
    source_counts = Counter(row.get("source_stage") for row in [*work_orders, *blockers])
    blocker_counts = Counter()
    for row in blockers:
        blocker_counts.update(row.get("blocker_codes") or [])
    contract = {
        "record_type": "stage12509_ai_env_private_extraction_return_work_order_contract_v1",
        "stage": STAGE,
        "input_stage": STAGE12508,
        "materialization_environment": "ai_env",
        "forbidden_materialization_environments": ["trellis"],
        "public_artifact_policy": "hashes_enums_templates_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        "return_file_stage": STAGE12502,
        "return_file_role": RETURN_FILE_ROLE,
        "stage12503_return_record_type": RETURN_RECORD_TYPE,
        "required_return_fields": [
            "record_type", "request_id_hash", "audit_item_id_hash", "work_item_id_hash",
            "packet_id_hash", "root_or_window_hash", "source_stage", "source_kind",
            "task_family", "language_family", "extractor_id_hash",
            "extractor_authority_attestation", "extractor_conflict_check_hash",
            "requested_private_extraction_slots", "extracted_slot_statuses",
            "extracted_slot_proof_hashes", "source_locator_hash", "causal_review_hash",
            "patch_apply_status_enum", "stop_continue_status_enum",
            "raw_private_values_revealed", "raw_source_output_included",
            "local_model_authority", "policy_label_emitted",
            "acceptance_criteria_passed", "blocker_codes", "training_allowed",
            "admission_allowed", "training_rows_emitted", "admitted_rows",
        ],
        "stage12509_does_not_write_return_file": True,
        "template_only": True,
        "not_authoritative_return": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    guardrail = {"stage": STAGE, "scan_passed": True, "raw_leak_count": 0, "raw_leak_issue_hashes": []}
    summary = {
        "stage": STAGE,
        "record_type": "stage12509_ai_env_private_extraction_return_work_order_summary_v1",
        "decision": "ai_env_private_extraction_return_work_orders_ready_stage12503_templates_only_training_and_admission_blocked" if work_orders and not blockers else "partial_ai_env_private_extraction_return_work_orders_remaining_blocked" if work_orders else "blocked_stage12508_handoff_jobs_missing_no_work_orders_or_templates",
        "claim_boundary": "Stage12509 emits work orders and templates only. It does not execute ai_env, write Stage12503 returns, validate proof, admit rows, or train.",
        "input_handoff_job_count": len(jobs),
        "work_order_count": len(work_orders),
        "stage12503_return_schema_template_count": len(templates),
        "return_template_count": len(templates),
        "blocked_work_order_count": len(blockers),
        "work_order_blocker_count": len(blockers),
        "blocker_code_counts": dict(sorted(blocker_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "task_family_counts": dict(sorted(task_counts.items())),
        "source_stage_counts": dict(sorted(source_counts.items())),
        "materialization_environment": "ai_env",
        "forbidden_materialization_environments": ["trellis"],
        "stage12503_return_records_written": 0,
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        "next_stage": "execute_stage12509_work_orders_in_ai_env_to_write_stage12503_return_file_then_rerun_stage12503" if work_orders and not blockers else "repair_stage12508_handoff_jobs_then_rerun_stage12509",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks({"contract": contract, "guardrail": guardrail, "summary": summary})
    write_jsonl(out / "ai_env_private_extraction_return_work_orders.jsonl", work_orders)
    write_jsonl(out / "stage12503_return_schema_templates.jsonl", templates)
    write_jsonl(out / "ai_env_private_extraction_return_work_order_blockers.jsonl", blockers)
    write_json(out / "ai_env_private_extraction_return_work_order_contract.json", contract)
    write_json(out / "guardrail_scan.json", guardrail)
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()

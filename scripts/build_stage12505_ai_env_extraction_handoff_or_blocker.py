#!/usr/bin/env python3
"""Build or block the ai_env private extraction handoff.

Stage12505 consumes Stage12504 hash-only locator work items. It only emits an
ai_env execution handoff when a request has locator coverage for its original
source stage. Context-only locators are blocked because they cannot support
trusted extraction of same-source state/action/verifier proof.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12505_ai_env_extraction_handoff_or_blocker"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12504 = "stage12504_private_extractor_source_locator_worklist"
STAGE12504_OUT = ROOT / "runs/local/artifacts" / STAGE12504
STAGE12504_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12504}.json"
WORKLIST = STAGE12504_OUT / "private_extractor_source_locator_worklist.jsonl"

STAGE12502 = "stage12502_authoritative_private_semantic_extraction_request_preflight"
STAGE12503_RETURN_FILE_ROLE = "private_semantic_extraction_returns.jsonl"
STAGE12503_RETURN_RECORD_TYPE = "stage12503_authoritative_private_semantic_extraction_return_v1"

CONTEXT_ONLY_STAGES = {
    "stage12500_closed_loop_candidate_packet_router",
    "stage12502_authoritative_private_semantic_extraction_request_preflight",
    "stage12503_private_semantic_extraction_return_validator",
    STAGE12504,
}

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
}


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
            if not line.strip():
                continue
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


def locator_stage_counts(row: dict[str, Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for locator in row.get("hash_locator_records") or []:
        stage = locator.get("artifact_stage")
        if isinstance(stage, str):
            counts[stage] += 1
    return counts


def source_stage_locator_refs(row: dict[str, Any]) -> list[dict[str, Any]]:
    source_stage = row.get("source_stage")
    refs: list[dict[str, Any]] = []
    for locator in row.get("hash_locator_records") or []:
        if locator.get("artifact_stage") != source_stage:
            continue
        refs.append(
            {
                "locator_id_hash": locator.get("locator_id_hash"),
                "artifact_locator_hash": locator.get("artifact_locator_hash"),
                "artifact_file_role_hash": locator.get("artifact_file_role_hash"),
                "artifact_content_hash": locator.get("artifact_content_hash"),
                "matched_lookup_key_names": locator.get("matched_lookup_key_names") or [],
                "public_safe_hash_locator_only": True,
            }
        )
    return refs


def context_locator_refs(row: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for locator in row.get("hash_locator_records") or []:
        stage = locator.get("artifact_stage")
        if stage not in CONTEXT_ONLY_STAGES:
            continue
        refs.append(
            {
                "locator_id_hash": locator.get("locator_id_hash"),
                "artifact_stage": stage,
                "artifact_locator_hash": locator.get("artifact_locator_hash"),
                "artifact_file_role_hash": locator.get("artifact_file_role_hash"),
                "matched_lookup_key_count": locator.get("matched_lookup_key_count", 0),
                "public_safe_hash_locator_only": True,
            }
        )
    return refs


def required_return_contract(row: dict[str, Any]) -> dict[str, Any]:
    slots = sorted(row.get("requested_private_extraction_slots") or [])
    return {
        "return_file_stage": STAGE12502,
        "return_file_role": STAGE12503_RETURN_FILE_ROLE,
        "return_file_role_hash": row.get("stage12503_return_file_role_hash"),
        "return_record_type": STAGE12503_RETURN_RECORD_TYPE,
        "required_identity_hash_fields": [
            "request_id_hash",
            "audit_item_id_hash",
            "work_item_id_hash",
            "packet_id_hash",
            "root_or_window_hash",
        ],
        "required_private_proof_fields": [
            "extractor_id_hash",
            "extractor_conflict_check_hash",
            "source_locator_hash",
            "causal_review_hash",
            "extracted_slot_statuses",
            "extracted_slot_proof_hashes",
            "patch_apply_status_enum",
            "stop_continue_status_enum",
        ],
        "requested_private_extraction_slots": slots,
        "must_keep_false": [
            "raw_private_values_revealed",
            "raw_source_output_included",
            "local_model_authority",
            "policy_label_emitted",
            "training_allowed",
            "admission_allowed",
        ],
        "must_keep_zero": [
            "training_rows_emitted",
            "admitted_rows",
        ],
    }


def build_record(row: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    source_refs = source_stage_locator_refs(row)
    context_refs = context_locator_refs(row)
    counts = locator_stage_counts(row)
    blockers: list[str] = []

    if row.get("materialization_environment") != "ai_env":
        blockers.append("stage12504_materialization_environment_not_ai_env")
    if row.get("source_stage") in CONTEXT_ONLY_STAGES or not row.get("source_stage"):
        blockers.append("source_stage_missing_or_context_only")
    if not source_refs:
        blockers.append("original_source_stage_locator_refs_missing")
    if not context_refs:
        blockers.append("context_locator_refs_missing")
    if row.get("source_locator_worklist_ready") is not True:
        blockers.append("stage12504_source_locator_not_ready")
    if row.get("stage12503_expected_return_record_type") != STAGE12503_RETURN_RECORD_TYPE:
        blockers.append("stage12503_return_record_type_mismatch")

    common = {
        "request_id_hash": row.get("request_id_hash"),
        "audit_item_id_hash": row.get("audit_item_id_hash"),
        "work_item_id_hash": row.get("work_item_id_hash"),
        "packet_id_hash": row.get("packet_id_hash"),
        "root_or_window_hash": row.get("root_or_window_hash"),
        "source_stage": row.get("source_stage"),
        "source_kind": row.get("source_kind"),
        "task_family": row.get("task_family"),
        "language_family": row.get("language_family"),
        "materialization_environment": "ai_env",
        "forbidden_materialization_environments": ["trellis"],
        "stage12503_return_contract": required_return_contract(row),
        "source_stage_locator_ref_count": len(source_refs),
        "context_locator_ref_count": len(context_refs),
        "locator_artifact_stage_counts": dict(sorted(counts.items())),
        "raw_private_values_revealed": False,
        "raw_locator_values_emitted": False,
        "public_safe_hash_locator_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }

    if blockers:
        return None, {
            "record_type": "stage12505_ai_env_extraction_handoff_blocker_v1",
            "handoff_blocker_id_hash": stable_hash(
                {"request": row.get("request_id_hash"), "blockers": sorted(set(blockers))}
            ),
            "blocker_codes": sorted(set(blockers)),
            "blocking_decision": "blocked_do_not_execute_ai_env_extractor_until_original_source_stage_locators_exist",
            "safe_next_action": (
                "rebuild Stage12504 source locator discovery so each request includes hash-only locator "
                "refs into the original source_stage artifact, then rerun Stage12505"
            ),
            "context_locator_refs": context_refs,
            "source_stage_locator_refs": [],
            **common,
        }

    return {
        "record_type": "stage12505_ai_env_private_extraction_handoff_job_v1",
        "handoff_job_id_hash": stable_hash({"request": row.get("request_id_hash"), "kind": "ai_env_handoff"}),
        "execution_decision": "ready_for_ai_env_private_extractor_return_production",
        "source_stage_locator_refs": source_refs,
        "context_locator_refs": context_refs,
        "ai_env_executor_requirements": [
            "execute_inside_ai_env_not_trellis",
            "resolve_source_stage_locator_refs_privately",
            "inspect_raw_source_command_patch_verifier_material_privately",
            "emit_only_stage12503_authoritative_private_semantic_extraction_return_v1",
            "emit_hashes_enums_statuses_only_to_public_return_file",
            "do_not_emit_training_rows_level3_atoms_patch_traces_or_policy_labels",
        ],
        **common,
    }, None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12504_summary = read_json(STAGE12504_SUMMARY)
    work_items = read_jsonl(WORKLIST)

    jobs: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for row in work_items:
        job, blocker = build_record(row)
        if job is not None:
            jobs.append(job)
        if blocker is not None:
            blockers.append(blocker)

    language_counts = Counter(row.get("language_family") for row in work_items)
    task_counts = Counter(row.get("task_family") for row in work_items)
    source_stage_counts = Counter(row.get("source_stage") for row in work_items)
    blocker_counts = Counter()
    locator_stage_counts_total = Counter()
    for row in work_items:
        locator_stage_counts_total.update(locator_stage_counts(row))
    for row in blockers:
        blocker_counts.update(row.get("blocker_codes") or [])

    handoff_contract = {
        "record_type": "stage12505_ai_env_private_extraction_handoff_contract_v1",
        "stage": STAGE,
        "input_stage": STAGE12504,
        "materialization_environment": "ai_env",
        "forbidden_materialization_environments": ["trellis"],
        "stage12503_return_file_stage": STAGE12502,
        "stage12503_return_file_role": STAGE12503_RETURN_FILE_ROLE,
        "stage12503_return_record_type_required": STAGE12503_RETURN_RECORD_TYPE,
        "public_artifact_policy": "hashes_stage_ids_enums_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        "execution_gate": "requires_nonzero_original_source_stage_locator_refs_per_request",
        "training_gate": "blocked_until_stage12503_validates_authoritative_private_returns_then_downstream_admission_passes",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }

    outputs = {
        "jobs": jobs,
        "blockers": blockers,
        "handoff_contract": handoff_contract,
    }
    leak_issues = scan_raw_leaks(outputs)
    guardrail = {
        "stage": STAGE,
        "scan_passed": not leak_issues,
        "raw_leak_count": len(leak_issues),
        "raw_leak_issue_hashes": leak_issues[:40],
        "scanned_outputs": [
            "ai_env_private_extraction_handoff_jobs.jsonl",
            "ai_env_private_extraction_handoff_blockers.jsonl",
            "ai_env_private_extraction_handoff_contract.json",
        ],
    }

    summary = {
        "stage": STAGE,
        "record_type": "stage12505_ai_env_extraction_handoff_or_blocker_summary_v1",
        "decision": (
            "ai_env_private_extraction_handoff_ready_training_and_admission_blocked"
            if jobs
            else "blocked_stage12504_locators_are_context_only_no_ai_env_extraction_handoff"
        ),
        "claim_boundary": (
            "Stage12505 only builds an ai_env private extractor handoff when Stage12504 provides "
            "original source-stage hash locator refs. Context-only refs are blocked. It does not "
            "write Stage12503 returns, inspect raw source, admit atoms, or train."
        ),
        "source_stage": STAGE12504,
        "stage12504_decision": stage12504_summary.get("decision"),
        "input_work_item_count": len(work_items),
        "handoff_job_count": len(jobs),
        "blocked_handoff_count": len(blockers),
        "context_only_blocked_count": sum(
            1 for row in blockers if "original_source_stage_locator_refs_missing" in row.get("blocker_codes", [])
        ),
        "source_stage_locator_ready_count": len(jobs),
        "context_locator_only_count": len(blockers),
        "language_counts": dict(sorted(language_counts.items())),
        "task_family_counts": dict(sorted(task_counts.items())),
        "source_stage_counts": dict(sorted(source_stage_counts.items())),
        "locator_artifact_stage_counts": dict(sorted(locator_stage_counts_total.items())),
        "blocker_code_counts": dict(sorted(blocker_counts.items())),
        "materialization_environment": "ai_env",
        "forbidden_materialization_environments": ["trellis"],
        "stage12503_return_record_type_required": STAGE12503_RETURN_RECORD_TYPE,
        "stage12503_return_file_role": STAGE12503_RETURN_FILE_ROLE,
        "stage12503_return_records_written": 0,
        "guardrail_scan_passed": guardrail["scan_passed"],
        "raw_leak_count": guardrail["raw_leak_count"],
        "public_artifact_policy": handoff_contract["public_artifact_policy"],
        "next_stage": (
            "rebuild_source_stage_locator_recovery_then_rerun_stage12505"
            if not jobs
            else "execute_ai_env_private_extractor_jobs_then_rerun_stage12503"
        ),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }

    write_jsonl(OUT / "ai_env_private_extraction_handoff_jobs.jsonl", jobs)
    write_jsonl(OUT / "ai_env_private_extraction_handoff_blockers.jsonl", blockers)
    write_json(OUT / "ai_env_private_extraction_handoff_contract.json", handoff_contract)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()

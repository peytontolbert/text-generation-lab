#!/usr/bin/env python3
"""Build an ai_env handoff from the Stage12507 recovered locator worklist.

Stage12508 is a Stage12505-equivalent gate over the patched Stage12507
worklist. It may emit hash-only ai_env handoff job records, but it does not
execute extraction, write Stage12503 returns, admit rows, train, or materialize
Level-3/patch-trace proof.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12508_ai_env_handoff_from_recovered_locator_worklist"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12507 = "stage12507_recovered_source_locator_integration_preflight"
STAGE12507_WORKLIST = (
    ROOT
    / "runs/local/artifacts"
    / STAGE12507
    / "patched_private_extractor_source_locator_worklist.jsonl"
)
STAGE12507_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12507}.json"

STAGE12502 = "stage12502_authoritative_private_semantic_extraction_request_preflight"
STAGE12503_RETURN_FILE_ROLE = "private_semantic_extraction_returns.jsonl"
STAGE12503_RETURN_RECORD_TYPE = "stage12503_authoritative_private_semantic_extraction_return_v1"

CONTEXT_ONLY_STAGES = {
    "stage12500_closed_loop_candidate_packet_router",
    STAGE12502,
    "stage12503_private_semantic_extraction_return_validator",
    "stage12504_private_extractor_source_locator_worklist",
    "stage12505_ai_env_extraction_handoff_or_blocker",
    "stage12506_source_stage_locator_recovery_preflight",
    STAGE12507,
    STAGE,
}
HASH_FIELD_NAMES = {
    "locator_id_hash",
    "artifact_locator_hash",
    "artifact_file_role_hash",
    "artifact_content_hash",
    "row_locator_hash",
}
HASH_VALUE_RE = re.compile(r"^[0-9a-f]{16,64}$")
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


def enforce_no_raw_leaks(value: Any) -> None:
    issues = scan_raw_leaks(value)
    if issues:
        raise RawLeakError(f"{STAGE} raw leak guard rejected {len(issues)} public field(s)")


def path_for(root: Path, absolute_path: Path) -> Path:
    return root / absolute_path.relative_to(ROOT)


def hash_value_ok(value: Any) -> bool:
    return isinstance(value, str) and bool(HASH_VALUE_RE.fullmatch(value))


def locator_is_public_safe(locator: dict[str, Any]) -> bool:
    if locator.get("public_safe_hash_locator_only") is not True:
        return False
    if locator.get("raw_locator_values_emitted") is not False:
        return False
    for field in HASH_FIELD_NAMES:
        if field in locator and locator.get(field) is not None and not hash_value_ok(locator.get(field)):
            return False
    return True


def locator_stage_counts(row: dict[str, Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for locator in row.get("hash_locator_records") or []:
        stage = locator.get("artifact_stage")
        if isinstance(stage, str):
            counts[stage] += 1
    return counts


def source_stage_locator_refs(row: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    source_stage = row.get("source_stage")
    refs: list[dict[str, Any]] = []
    invalid_count = 0
    for locator in row.get("hash_locator_records") or []:
        if locator.get("artifact_stage") != source_stage:
            continue
        if not locator_is_public_safe(locator):
            invalid_count += 1
            continue
        refs.append(
            {
                "locator_id_hash": locator.get("locator_id_hash"),
                "artifact_stage": locator.get("artifact_stage"),
                "artifact_locator_hash": locator.get("artifact_locator_hash"),
                "artifact_file_role_hash": locator.get("artifact_file_role_hash"),
                "artifact_content_hash": locator.get("artifact_content_hash"),
                "row_locator_hash": locator.get("row_locator_hash"),
                "matched_lookup_key_names": locator.get("matched_lookup_key_names") or [],
                "public_safe_hash_locator_only": True,
                "raw_locator_values_emitted": False,
            }
        )
    return refs, invalid_count


def context_locator_refs(row: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    refs: list[dict[str, Any]] = []
    invalid_count = 0
    for locator in row.get("hash_locator_records") or []:
        stage = locator.get("artifact_stage")
        if stage not in CONTEXT_ONLY_STAGES:
            continue
        if not locator_is_public_safe(locator):
            invalid_count += 1
            continue
        refs.append(
            {
                "locator_id_hash": locator.get("locator_id_hash"),
                "artifact_stage": stage,
                "artifact_locator_hash": locator.get("artifact_locator_hash"),
                "artifact_file_role_hash": locator.get("artifact_file_role_hash"),
                "artifact_content_hash": locator.get("artifact_content_hash"),
                "matched_lookup_key_count": locator.get("matched_lookup_key_count", 0),
                "matched_lookup_key_names": locator.get("matched_lookup_key_names") or [],
                "public_safe_hash_locator_only": True,
                "raw_locator_values_emitted": False,
            }
        )
    return refs, invalid_count


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
            "level3_admitted",
            "patch_trace_admitted",
        ],
    }


def common_record(row: dict[str, Any], source_refs: list[dict[str, Any]], context_refs: list[dict[str, Any]]) -> dict[str, Any]:
    counts = locator_stage_counts(row)
    return {
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
        "forbidden_public_outputs": [
            "raw_paths",
            "raw_commands",
            "raw_diffs",
            "raw_source_text",
            "raw_verifier_output",
            "private_values",
            "policy_labels",
            "training_rows",
            "level3_atoms",
            "patch_traces",
            "stage12503_returns",
        ],
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def build_record(row: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    source_refs, invalid_source_ref_count = source_stage_locator_refs(row)
    context_refs, invalid_context_ref_count = context_locator_refs(row)
    blockers: list[str] = []

    if row.get("materialization_environment") != "ai_env":
        blockers.append("stage12507_materialization_environment_not_ai_env")
    if row.get("source_stage") in CONTEXT_ONLY_STAGES or not row.get("source_stage"):
        blockers.append("source_stage_missing_or_context_only")
    if row.get("stage12505_rerun_ready") is not True:
        blockers.append("stage12505_rerun_ready_not_true")
    if row.get("source_locator_worklist_ready") is not True:
        blockers.append("source_locator_worklist_ready_not_true")
    if not source_refs:
        blockers.append("source_stage_locator_refs_missing")
    if not context_refs:
        blockers.append("context_locator_refs_missing")
    if invalid_source_ref_count:
        blockers.append("source_stage_locator_refs_not_public_safe_hash_only")
    if invalid_context_ref_count:
        blockers.append("context_locator_refs_not_public_safe_hash_only")
    if row.get("stage12503_expected_return_record_type") != STAGE12503_RETURN_RECORD_TYPE:
        blockers.append("stage12503_return_record_type_mismatch")
    if row.get("raw_private_values_revealed") is not False:
        blockers.append("raw_private_values_revealed_not_false")
    if row.get("raw_locator_values_emitted") is not False:
        blockers.append("raw_locator_values_emitted_not_false")
    if row.get("public_safe_hash_locator_only") is not True:
        blockers.append("work_item_not_public_safe_hash_only")

    common = common_record(row, source_refs, context_refs)
    if blockers:
        blocker = {
            "record_type": "stage12508_ai_env_handoff_from_recovered_locator_blocker_v1",
            "handoff_blocker_id_hash": stable_hash(
                {"request": row.get("request_id_hash"), "blockers": sorted(set(blockers))}
            ),
            "blocker_codes": sorted(set(blockers)),
            "blocking_decision": "blocked_do_not_execute_ai_env_extractor_until_stage12507_patched_worklist_is_safe",
            "safe_next_action": (
                "repair Stage12507 patched hash-only worklist so each item has non-context source_stage, "
                "source-stage locator refs, context refs, stage12505_rerun_ready true, and no raw values"
            ),
            "source_stage_locator_refs": source_refs,
            "context_locator_refs": context_refs,
            **common,
        }
        enforce_no_raw_leaks(blocker)
        return None, blocker

    job = {
        "record_type": "stage12508_ai_env_private_extraction_handoff_job_v1",
        "handoff_job_id_hash": stable_hash({"request": row.get("request_id_hash"), "kind": "ai_env_handoff"}),
        "execution_decision": "ready_for_ai_env_private_extractor_return_production_from_stage12507_patched_worklist",
        "source_stage_locator_refs": source_refs,
        "context_locator_refs": context_refs,
        "ai_env_executor_requirements": [
            "execute_inside_ai_env_not_trellis",
            "resolve_source_stage_locator_refs_privately",
            "preserve_context_locator_refs_for_request_identity",
            "emit_only_stage12503_authoritative_private_semantic_extraction_return_v1",
            "emit_hashes_enums_statuses_only_to_public_return_file",
            "do_not_emit_training_rows_level3_atoms_patch_traces_or_policy_labels",
        ],
        **common,
    }
    enforce_no_raw_leaks(job)
    return job, None


def missing_worklist_blocker() -> dict[str, Any]:
    return {
        "record_type": "stage12508_ai_env_handoff_from_recovered_locator_blocker_v1",
        "handoff_blocker_id_hash": stable_hash({"missing": "stage12507_patched_worklist"}),
        "blocker_codes": ["stage12507_patched_worklist_missing"],
        "blocking_decision": "blocked_missing_stage12507_patched_worklist_no_ai_env_handoff",
        "safe_next_action": "run Stage12507 to produce patched_private_extractor_source_locator_worklist.jsonl, then rerun Stage12508",
        "materialization_environment": "ai_env",
        "forbidden_materialization_environments": ["trellis"],
        "source_stage_locator_ref_count": 0,
        "context_locator_ref_count": 0,
        "source_stage_locator_refs": [],
        "context_locator_refs": [],
        "raw_private_values_revealed": False,
        "raw_locator_values_emitted": False,
        "public_safe_hash_locator_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / OUT.relative_to(ROOT)
    out.mkdir(parents=True, exist_ok=True)
    summary_path = root / SUMMARY.relative_to(ROOT)
    worklist_path = path_for(root, STAGE12507_WORKLIST)
    stage12507_summary = read_json(path_for(root, STAGE12507_SUMMARY))

    jobs: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    work_items: list[dict[str, Any]] = []

    if not worklist_path.exists():
        blockers.append(missing_worklist_blocker())
    else:
        work_items = read_jsonl(worklist_path)
        enforce_no_raw_leaks(work_items)
        for row in work_items:
            job, blocker = build_record(row)
            if job is not None:
                jobs.append(job)
            if blocker is not None:
                blockers.append(blocker)

    blocker_counts = Counter()
    locator_stage_counts_total = Counter()
    for row in blockers:
        blocker_counts.update(row.get("blocker_codes") or [])
    for row in work_items:
        locator_stage_counts_total.update(locator_stage_counts(row))

    language_counts = Counter(row.get("language_family") for row in work_items)
    task_counts = Counter(row.get("task_family") for row in work_items)
    source_stage_counts = Counter(row.get("source_stage") for row in work_items)
    source_stage_ref_total = sum(row.get("source_stage_locator_ref_count", 0) for row in jobs)
    context_ref_total = sum(row.get("context_locator_ref_count", 0) for row in jobs)

    handoff_contract = {
        "record_type": "stage12508_ai_env_private_extraction_handoff_contract_v1",
        "stage": STAGE,
        "input_stage": STAGE12507,
        "input_file_role": "patched_private_extractor_source_locator_worklist.jsonl",
        "materialization_environment": "ai_env",
        "forbidden_materialization_environments": ["trellis"],
        "stage12503_return_file_stage": STAGE12502,
        "stage12503_return_file_role": STAGE12503_RETURN_FILE_ROLE,
        "stage12503_return_record_type_required": STAGE12503_RETURN_RECORD_TYPE,
        "public_artifact_policy": "hashes_stage_ids_enums_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        "execution_gate": (
            "requires_stage12505_rerun_ready_true_non_context_source_stage_nonzero_source_stage_locator_refs_"
            "context_locator_refs_and_public_safe_hash_only_refs"
        ),
        "training_gate": "blocked_until_stage12503_validates_authoritative_private_returns_then_downstream_admission_passes",
        "forbidden_stage_actions": [
            "execute_extraction",
            "write_stage12503_returns",
            "admit_rows",
            "train",
            "emit_level3_atoms",
            "emit_patch_traces",
        ],
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    outputs = {
        "jobs": jobs,
        "blockers": blockers,
        "handoff_contract": handoff_contract,
    }
    leak_issues = scan_raw_leaks(outputs)
    if leak_issues:
        raise RawLeakError(f"{STAGE} raw leak guard rejected generated outputs")

    decision = (
        "ai_env_private_extraction_handoff_ready_from_stage12507_patched_worklist_training_and_admission_blocked"
        if jobs and not blockers
        else "blocked_stage12507_patched_worklist_missing_no_ai_env_handoff"
        if not worklist_path.exists()
        else "blocked_stage12507_patched_worklist_not_safe_no_ai_env_handoff"
    )
    guardrail = {
        "stage": STAGE,
        "scan_passed": True,
        "raw_leak_count": 0,
        "raw_leak_issue_hashes": [],
        "scanned_outputs": [
            "ai_env_private_extraction_handoff_jobs.jsonl",
            "ai_env_private_extraction_handoff_blockers.jsonl",
            "ai_env_private_extraction_handoff_contract.json",
        ],
    }
    summary = {
        "stage": STAGE,
        "record_type": "stage12508_ai_env_handoff_from_recovered_locator_worklist_summary_v1",
        "decision": decision,
        "claim_boundary": (
            "Stage12508 only builds hash-only ai_env handoff jobs from the Stage12507 patched worklist. "
            "It does not execute extraction, write Stage12503 returns, admit rows, train, emit Level-3 atoms, "
            "or emit patch traces."
        ),
        "source_stage": STAGE12507,
        "stage12507_decision": stage12507_summary.get("decision"),
        "input_work_item_count": len(work_items),
        "handoff_job_count": len(jobs),
        "blocked_handoff_count": len(blockers),
        "context_only_blocked_count": sum(
            1 for row in blockers if "original_source_stage_locator_refs_missing" in row.get("blocker_codes", [])
        ),
        "source_stage_locator_ready_count": len(jobs),
        "context_locator_only_count": len(blockers),
        "source_stage_locator_ref_total": source_stage_ref_total,
        "context_locator_ref_total": context_ref_total,
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
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        "public_artifact_policy": handoff_contract["public_artifact_policy"],
        "next_stage": (
            "execute_ai_env_private_extractor_jobs_then_rerun_stage12503"
            if jobs and not blockers
            else "repair_stage12507_patched_worklist_then_rerun_stage12508"
        ),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks({"contract": handoff_contract, "guardrail": guardrail, "summary": summary})

    write_jsonl(out / "ai_env_private_extraction_handoff_jobs.jsonl", jobs)
    write_jsonl(out / "ai_env_private_extraction_handoff_blockers.jsonl", blockers)
    write_json(out / "ai_env_private_extraction_handoff_contract.json", handoff_contract)
    write_json(out / "guardrail_scan.json", guardrail)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()

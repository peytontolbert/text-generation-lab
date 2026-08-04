#!/usr/bin/env python3
# Build Stage12636 independent review of candidate-ledger dry-run artifacts.
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12636_candidate_ledger_dry_run_independent_review_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12635 = ROOT / "runs/local/artifacts/stage12635_authoritative_ledger_update_dry_run_materialization_only"
S12635_SUMMARY = ROOT / "runs/summaries/stage12635_authoritative_ledger_update_dry_run_materialization_only.json"

EXPECTED_HASHES = {
    "stage12635_summary": "cdbf11e630c65f2e36ede98084950537c720323a8c57a8de26eddf981e643e05",
    "stage12635_contract": "65252405099e49ae238a4fbf0e86061d4f47614ec2382c963cacf0f088dbb4d8",
    "stage12635_pointer": "9daca9e4ecab5ec38f059e4be16fbcc3cf41860298df0d5417a9e2fb79f131f4",
    "stage12635_public_diff": "960f3584876ad4cfa25888f83aa1250bf52afbcbe72c738087745c0f2fd5e5ec",
    "stage12635_private": "01ceff2a27bc3fb951f2c501d6a6296454bcb35248a251726ea41073dad90b3c",
    "stage12635_materialization": "0fc08665b6b592b8fd966cb5733f2bae581a2aa8ec6ec244e7e2d2c4e134b59b",
    "stage12635_private_manifest": "7e8c62d60c22c5996573b40e6d9ccf592f3825dd848ec4a7e4ae02dcb1f83347",
    "stage12635_rows_bytes": "065923de4ef183501b5f528d82065814826bd257a9b1814d54850680fe6cbce5",
    "stage12634_authorization": "5736cc592b79db588df019a0b498a0abf1fbec8486ae1411ac5ee6457aafdcf4",
}

FALSE_FIELDS = (
    "implementation_ready", "dataset_admission_allowed", "dataset_rows_admitted", "new_rows_admitted",
    "frontier_100m_training_dataset_ready", "source_packet_implementation_allowed", "source_packet_executable",
    "stage12629_allowed", "stage12630_allowed", "stage12631_allowed", "stage12632_allowed", "stage12633_allowed",
    "stage12634_allowed", "stage12636_allowed", "stage12637_allowed",
    "stage12631_authoritative_ledger_dry_run_authority_source_packet_allowed",
    "stage12632_authoritative_ledger_dry_run_authority_source_packet_allowed",
    "stage12632_authoritative_ledger_update_dry_run_only_allowed",
    "stage12633_authoritative_ledger_update_dry_run_only_allowed",
    "stage12634_authoritative_ledger_update_dry_run_only_allowed",
    "stage12636_authoritative_ledger_update_allowed",
    "stage12637_authoritative_ledger_update_allowed",
    "vm_branch_active", "vm_runner_execution_allowed", "execution_performed", "storage_write_performed", "replay_trustworthy",
    "causal_transition_atoms_present", "causal_transition_atoms_allowed", "level3_preflight_allowed", "level_3_materialized",
    "level_3_materialization_allowed", "gpu_allocation_requested", "cuda2_training_allowed",
    "training_admission_allowed", "training_admission_preflight_allowed", "training_admitted", "training_allowed", "training_run_allowed",
    "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
    "admission_allowed", "ranking_allowed", "positive_stop", "authoritative_ledger_updated",
    "authoritative_ledger_update_allowed", "row_artifacts_written", "summary_artifact_written",
    "ledger_update_materialized", "dry_run_ready",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream", "stdout.raw", "stderr.raw",
    "before_commit_oid", "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
    "slot_1.patch", "slot_2.patch", "repository_root", "patch_path", "slot_1/", "slot_2/", "combined_selected_test_rows",
    "combined_train_support_rows", "direct_verifier_log_train_support_manifest", "direct_verifier_log_train_support_rows",
    "guardrail_scan.json", "combined_train_support_ledger", "jsonl", "row_id", "stable_lineage_key",
)


class CandidateDryRunReviewError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CandidateDryRunReviewError("json_object_required:" + path.name)
    return value


def read_jsonl_bytes(data: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise CandidateDryRunReviewError(f"candidate_row_object_required:{line_number}")
        rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def no_claim_fields() -> dict[str, Any]:
    return {field: False for field in FALSE_FIELDS}


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise CandidateDryRunReviewError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise CandidateDryRunReviewError(f"{label}_public_leak:{needle}")


def load_stage12635() -> dict[str, Any]:
    summary = read_json(S12635 / "summary.json")
    external = read_json(S12635_SUMMARY)
    contract = read_json(S12635 / "contract.json")
    pointer = read_json(S12635 / "digest_pointer.json")
    public_diff = read_json(S12635 / "candidate_summary_diff.json")
    private = read_json(S12635 / "private/authoritative_ledger_update_dry_run_materialization_only.json")
    private_manifest = read_json(S12635 / "private/candidate_ledger_dry_run_manifest.json")
    rows_bytes = (S12635 / "private/candidate_train_support_rows_dry_run.jsonl").read_bytes()
    if summary != external:
        raise CandidateDryRunReviewError("stage12635_external_summary_mismatch")
    for label, value in (
        ("stage12635_summary", summary),
        ("stage12635_contract", contract),
        ("stage12635_pointer", pointer),
        ("stage12635_public_diff", public_diff),
        ("stage12635_private", private),
        ("stage12635_private_manifest", private_manifest),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise CandidateDryRunReviewError("stage12635_pin_drift:" + label)
    materialization = private.get("dry_run_materialization") or {}
    if stable_hash(materialization) != EXPECTED_HASHES["stage12635_materialization"]:
        raise CandidateDryRunReviewError("stage12635_materialization_hash_drift")
    if sha256_bytes(rows_bytes) != EXPECTED_HASHES["stage12635_rows_bytes"]:
        raise CandidateDryRunReviewError("stage12635_rows_hash_drift")
    rows = read_jsonl_bytes(rows_bytes)
    if len(rows) != 99:
        raise CandidateDryRunReviewError("stage12635_projection_row_count_drift")
    row_ids = [row.get("row_id") for row in rows]
    if len(set(row_ids)) != len(row_ids):
        raise CandidateDryRunReviewError("stage12635_duplicate_projection_row_id_drift")
    return {
        "summary": summary,
        "contract": contract,
        "pointer": pointer,
        "public_diff": public_diff,
        "private": private,
        "private_manifest": private_manifest,
        "materialization": materialization,
        "projection_rows": rows,
    }


def validate_stage12635(stage12635: Mapping[str, Any]) -> None:
    summary = stage12635["summary"]
    public_diff = stage12635["public_diff"]
    private_manifest = stage12635["private_manifest"]
    materialization = stage12635["materialization"]
    required_true = (
        "dry_run_authorization_granted",
        "dry_run_authorized",
        "authoritative_ledger_dry_run_allowed",
        "stage12635_authoritative_ledger_update_dry_run_only_allowed",
        "authoritative_ledger_dry_run_performed",
        "authoritative_ledger_update_dry_run_materialized",
        "candidate_ledger_materialized",
        "candidate_rows_materialized",
        "candidate_projection_rows_materialized",
        "dry_run_candidate_artifacts_written",
        "vm_branch_remains_paused",
    )
    for record, label in ((summary, "summary"), (stage12635["contract"], "contract"), (stage12635["pointer"], "pointer")):
        for field in required_true:
            if record.get(field) is not True:
                raise CandidateDryRunReviewError(f"stage12635_{label}_true_marker_missing:{field}")
    for field in ("authoritative_ledger_update_allowed", "authoritative_ledger_updated", "dataset_admission_allowed", "dataset_rows_admitted", "new_rows_admitted", "training_allowed", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted", "level_3_materialized", "replay_trustworthy", "vm_runner_execution_allowed"):
        if summary.get(field) is not False:
            raise CandidateDryRunReviewError("stage12635_forbidden_gate_drift:" + field)
    if summary.get("authoritative_admitted_train_support_tasks_after_dry_run") != 158:
        raise CandidateDryRunReviewError("stage12635_authoritative_count_drift")
    if summary.get("candidate_train_support_tasks_after_dry_run") != 190:
        raise CandidateDryRunReviewError("stage12635_candidate_count_drift")
    if summary.get("materialized_projection_rows") != 99 or summary.get("event_local_base_rows_referenced") != 91:
        raise CandidateDryRunReviewError("stage12635_projection_base_split_drift")
    if public_diff.get("candidate_count_after_dry_run") != 190 or public_diff.get("materialized_projection_rows") != 99:
        raise CandidateDryRunReviewError("stage12635_public_diff_count_drift")
    requirements = private_manifest.get("materialized_private_manifest_requirements") or {}
    required_sections = {"merged_row_manifest", "supersession_manifest", "direct_log_merge_manifest", "duplicate_policy_manifest", "guardrail_manifest"}
    if set(requirements) != required_sections:
        raise CandidateDryRunReviewError("stage12635_private_manifest_sections_drift")
    if requirements["supersession_manifest"].get("net_delta") != 14:
        raise CandidateDryRunReviewError("stage12635_supersession_delta_drift")
    if requirements["direct_log_merge_manifest"].get("direct_log_projection_rows") != 18:
        raise CandidateDryRunReviewError("stage12635_direct_log_delta_drift")
    if requirements["duplicate_policy_manifest"].get("post_update_duplicate_extra_rows_required") != 0:
        raise CandidateDryRunReviewError("stage12635_duplicate_policy_drift")
    if requirements["guardrail_manifest"].get("scan_passed") is not True:
        raise CandidateDryRunReviewError("stage12635_guardrail_manifest_drift")
    if materialization.get("authoritative_ledger_update_performed") is not False or materialization.get("new_admission_performed") is not False:
        raise CandidateDryRunReviewError("stage12635_materialization_overclaim")
    for label, record in (("summary", summary), ("contract", stage12635["contract"]), ("pointer", stage12635["pointer"]), ("public_diff", public_diff)):
        assert_public_sanitized(record, "stage12635_" + label)


def build_review(stage12635: Mapping[str, Any]) -> dict[str, Any]:
    validate_stage12635(stage12635)
    checks = [
        {"check_id": "stage12635_public_and_private_hashes_pinned", "status": "passed"},
        {"check_id": "stage12635_dry_run_authorization_preserved", "status": "passed"},
        {"check_id": "candidate_projection_rows_are_99_unique_rows", "status": "passed"},
        {"check_id": "candidate_total_count_is_190_with_91_base_rows", "status": "passed"},
        {"check_id": "private_manifest_requirements_materialized", "status": "passed", "manifest_section_count": 5},
        {"check_id": "public_artifacts_have_no_private_leaks", "status": "passed"},
        {"check_id": "authoritative_update_admission_training_eval_replay_level3_vm_forbidden", "status": "passed"},
    ]
    return {
        "record_type": "stage12636_candidate_ledger_dry_run_independent_review_v1",
        "review_scope": "candidate_ledger_dry_run_independent_review_only",
        "reviewed_stage": "stage12635_authoritative_ledger_update_dry_run_materialization_only",
        "reviewed_hashes": EXPECTED_HASHES,
        "review_checks": checks,
        "review_check_count": len(checks),
        "review_status": "candidate_ledger_dry_run_review_passed_no_authoritative_update_or_admission",
        "authoritative_count_after_review": 158,
        "authoritative_gap_after_review": 342,
        "candidate_count_after_review": 190,
        "candidate_gap_after_review": 310,
        "materialized_projection_rows": 99,
        "event_local_base_rows_referenced": 91,
        "candidate_delta_total": 32,
        "candidate_dry_run_artifacts_reviewed": 3,
        "candidate_dry_run_independent_review_only": True,
        "dry_run_authorization_granted": True,
        "dry_run_authorized": True,
        "authoritative_ledger_dry_run_allowed": True,
        "stage12635_authoritative_ledger_update_dry_run_only_allowed": True,
        "authoritative_ledger_dry_run_performed": True,
        "authoritative_ledger_update_dry_run_materialized": True,
        "candidate_ledger_materialized": True,
        "candidate_rows_materialized": True,
        "candidate_projection_rows_materialized": True,
        "dry_run_candidate_artifacts_written": True,
        "authoritative_ledger_update_performed": False,
        "new_admission_performed": False,
        "training_allowed_after_review": False,
    }


def build_packet(stage12635: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    review = build_review(stage12635)
    true_fields = {
        "candidate_dry_run_independent_review_only": True,
        "dry_run_authorization_granted": True,
        "dry_run_authorized": True,
        "authoritative_ledger_dry_run_allowed": True,
        "stage12635_authoritative_ledger_update_dry_run_only_allowed": True,
        "authoritative_ledger_dry_run_performed": True,
        "authoritative_ledger_update_dry_run_materialized": True,
        "candidate_ledger_materialized": True,
        "candidate_rows_materialized": True,
        "candidate_projection_rows_materialized": True,
        "dry_run_candidate_artifacts_written": True,
        "vm_branch_remains_paused": True,
    }
    private = {
        "record_type": "stage12636_private_candidate_ledger_dry_run_independent_review_only_v1",
        **no_claim_fields(),
        **true_fields,
        "source_hashes": EXPECTED_HASHES,
        "candidate_dry_run_independent_review": review,
        "decision": "CANDIDATE_LEDGER_DRY_RUN_INDEPENDENT_REVIEW_PASSED_NO_AUTHORITATIVE_UPDATE_OR_ADMISSION",
    }
    contract = {
        "record_type": "stage12636_public_candidate_ledger_dry_run_independent_review_only_contract_v1",
        **no_claim_fields(),
        **true_fields,
        "stage12635_summary_sha256": EXPECTED_HASHES["stage12635_summary"],
        "stage12635_materialization_sha256": EXPECTED_HASHES["stage12635_materialization"],
        "candidate_dry_run_independent_review_sha256": stable_hash(review),
        "private_candidate_dry_run_independent_review_sha256": stable_hash(private),
        "claim_boundary": {"review": "candidate_dry_run_artifact_review_only", "authoritative_ledger_update": "not_authorized_or_performed", "new_admission": "not_authorized", "training": "not_authorized", "eval": "not_authorized", "vm": "paused_not_used_for_review", "replay": "not_executed", "level3": "not_materialized"},
    }
    summary = {
        "record_type": "stage12636_public_candidate_ledger_dry_run_independent_review_only_summary_v1",
        **no_claim_fields(),
        **true_fields,
        "stage": STAGE,
        "decision": "CANDIDATE_LEDGER_DRY_RUN_INDEPENDENT_REVIEW_PASSED_NO_AUTHORITATIVE_UPDATE_OR_ADMISSION",
        "stage12635_summary_sha256": EXPECTED_HASHES["stage12635_summary"],
        "stage12635_materialization_sha256": EXPECTED_HASHES["stage12635_materialization"],
        "candidate_dry_run_independent_review_sha256": stable_hash(review),
        "private_candidate_dry_run_independent_review_sha256": stable_hash(private),
        "review_status": "candidate_ledger_dry_run_review_passed_no_authoritative_update_or_admission",
        "authoritative_admitted_train_support_tasks_after_review": 158,
        "authoritative_gap_to_500_after_review": 342,
        "candidate_train_support_tasks_after_review": 190,
        "candidate_gap_to_500_after_review": 310,
        "materialized_projection_rows": 99,
        "event_local_base_rows_referenced": 91,
        "candidate_delta_total": 32,
        "frontier_100m_training_dataset_ready": False,
        "downstream_blockers": ["authoritative_ledger_update_not_authorized", "new_train_support_rows_not_admitted", "authoritative_gap_still_342", "training_admission_forbidden"],
        "next_required_action": "separate_authoritative_ledger_update_authorization_decision",
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12636_" + label)
        assert_public_sanitized(record, "stage12636_" + label)
    check_false(private, "stage12636_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12635 = load_stage12635()
    summary, contract, private = build_packet(stage12635)
    pointer = {
        "record_type": "stage12636_public_private_candidate_ledger_dry_run_independent_review_pointer_v1",
        **no_claim_fields(),
        "stage12635_summary_sha256": EXPECTED_HASHES["stage12635_summary"],
        "contract_sha256": stable_hash(contract),
        "private_candidate_dry_run_independent_review_sha256": stable_hash(private),
        "candidate_dry_run_independent_review_sha256": stable_hash(private["candidate_dry_run_independent_review"]),
        "candidate_dry_run_independent_review_only": True,
        "dry_run_authorization_granted": True,
        "dry_run_authorized": True,
        "authoritative_ledger_dry_run_allowed": True,
        "stage12635_authoritative_ledger_update_dry_run_only_allowed": True,
        "authoritative_ledger_dry_run_performed": True,
        "authoritative_ledger_update_dry_run_materialized": True,
        "candidate_ledger_materialized": True,
        "candidate_rows_materialized": True,
        "candidate_projection_rows_materialized": True,
        "dry_run_candidate_artifacts_written": True,
        "vm_branch_remains_paused": True,
    }
    check_false(pointer, "stage12636_pointer")
    assert_public_sanitized(pointer, "stage12636_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/candidate_ledger_dry_run_independent_review_only.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))

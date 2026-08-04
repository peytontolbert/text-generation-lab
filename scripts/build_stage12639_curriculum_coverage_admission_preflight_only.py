#!/usr/bin/env python3
# Build Stage12639 curriculum coverage/admission preflight only.
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12639_curriculum_coverage_admission_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12638 = ROOT / "runs/local/artifacts/stage12638_authoritative_ledger_update_materialization_only"
S12638_SUMMARY = ROOT / "runs/summaries/stage12638_authoritative_ledger_update_materialization_only.json"
ROWS = S12638 / "private/authoritative_update_evidence_rows.jsonl"
LOSS_SCHEMA = ROOT / "configs/schema/loss_mask.schema.json"
MANIFEST_ROW_SCHEMA = ROOT / "configs/schema/manifest_row.schema.json"

EXPECTED_HASHES = {
    "stage12638_summary": "b770e77b349fe71b71fda9c4bcb948a9636540aff29d491fd5aee1638a8c6a0e",
    "stage12638_contract": "83242b89d59304772a0e6369e7e909966ae49c4c7d15e95bd7ebe7430b88f1ea",
    "stage12638_pointer": "cd17f8db75087528aa802820166a0a6f7173d8c85c0da155c15118a15756f9d7",
    "stage12638_private": "46fe6f42259244710ebb6d5d9eb244e012298ae368e33c316a527341836ff1cd",
    "stage12638_coverage": "e096bc839e6e7664d3f1b59725b1cc0437f89e3a0ce98bea07d968051c38fc66",
    "stage12638_rows_bytes": "065923de4ef183501b5f528d82065814826bd257a9b1814d54850680fe6cbce5",
}

FALSE_FIELDS = (
    "implementation_ready", "dataset_admission_allowed", "dataset_rows_admitted", "new_rows_admitted",
    "frontier_100m_training_dataset_ready", "source_packet_implementation_allowed", "source_packet_executable",
    "stage12629_allowed", "stage12630_allowed", "stage12631_allowed", "stage12632_allowed", "stage12633_allowed",
    "stage12634_allowed", "stage12636_allowed", "stage12637_allowed", "stage12639_allowed",
    "stage12631_authoritative_ledger_dry_run_authority_source_packet_allowed",
    "stage12632_authoritative_ledger_dry_run_authority_source_packet_allowed",
    "stage12632_authoritative_ledger_update_dry_run_only_allowed",
    "stage12633_authoritative_ledger_update_dry_run_only_allowed",
    "stage12634_authoritative_ledger_update_dry_run_only_allowed",
    "stage12639_training_admission_allowed",
    "vm_branch_active", "vm_runner_execution_allowed", "execution_performed", "replay_trustworthy",
    "causal_transition_atoms_present", "causal_transition_atoms_allowed", "level3_preflight_allowed", "level_3_materialized",
    "level_3_materialization_allowed", "gpu_allocation_requested", "cuda2_training_allowed",
    "training_admission_allowed", "training_admission_preflight_allowed", "training_admitted", "training_allowed", "training_run_allowed",
    "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
    "admission_allowed", "ranking_allowed", "positive_stop", "dry_run_ready",
)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream", "stdout.raw", "stderr.raw",
    "before_commit_oid", "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
    "slot_1.patch", "slot_2.patch", "repository_root", "patch_path", "slot_1/", "slot_2/", "combined_selected_test_rows",
    "combined_train_support_rows", "direct_verifier_log_train_support_manifest", "direct_verifier_log_train_support_rows",
    "guardrail_scan.json", "combined_train_support_ledger", "jsonl", "row_id", "stable_lineage_key",
)

CANONICAL_REQUIRED_FIELDS = (
    "row_id", "split", "language_family", "input_state", "target", "loss_mask", "authority", "source_provenance", "anti_cheat_contract"
)

CURRICULUM_SIGNAL_RULES = {
    "structured_repo_state_partial": lambda row: isinstance(row.get("input_text"), str) or isinstance(row.get("opaque_options"), list),
    "maintainer_action_policy": lambda row: row.get("task_family") == "transition_next_action" or row.get("task_projection") == "transition_next_action",
    "continue_stop_policy": lambda row: row.get("task_family") == "transition_continue_or_stop" or row.get("task_projection") == "transition_continue_or_stop",
    "candidate_selection": lambda row: row.get("task_family") == "transition_candidate_selection" or row.get("task_projection") == "transition_candidate_selection",
    "verifier_transition_classification_partial": lambda row: row.get("task_family") == "transition_verifier_transition" or row.get("task_projection") == "transition_verifier_transition",
    "evidence_citation_partial": lambda row: row.get("task_family") == "transition_evidence_citation",
    "direct_verifier_observation_partial": lambda row: row.get("record_type") == "direct_real_verifier_log_train_support_projection",
}

MISSING_CURRICULUM_SIGNALS = (
    "canonical_state_t_state_t_plus_1",
    "canonical_action_t_observation_t_plus_1",
    "repo_graph_candidates",
    "symbol_binding_candidates",
    "file_span_localization_candidates",
    "root_cause_failure_category",
    "patch_operator_arguments",
    "verifier_repair_actions",
    "replay_retention_sets",
)


class CurriculumCoveragePreflightError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CurriculumCoveragePreflightError("json_object_required:" + path.name)
    return value


def read_rows(data: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise CurriculumCoveragePreflightError(f"row_object_required:{line_number}")
        rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def no_claim_fields() -> dict[str, Any]:
    return {field: False for field in FALSE_FIELDS}


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise CurriculumCoveragePreflightError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise CurriculumCoveragePreflightError(f"{label}_public_leak:{needle}")


def load_stage12638() -> dict[str, Any]:
    summary = read_json(S12638 / "summary.json")
    external = read_json(S12638_SUMMARY)
    contract = read_json(S12638 / "contract.json")
    pointer = read_json(S12638 / "digest_pointer.json")
    private = read_json(S12638 / "private/authoritative_ledger_update_materialization_only.json")
    coverage = read_json(S12638 / "curriculum_coverage_preview.json")
    rows_bytes = ROWS.read_bytes()
    if summary != external:
        raise CurriculumCoveragePreflightError("stage12638_external_summary_mismatch")
    for label, value in (
        ("stage12638_summary", summary),
        ("stage12638_contract", contract),
        ("stage12638_pointer", pointer),
        ("stage12638_private", private),
        ("stage12638_coverage", coverage),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise CurriculumCoveragePreflightError("stage12638_pin_drift:" + label)
    if sha256_bytes(rows_bytes) != EXPECTED_HASHES["stage12638_rows_bytes"]:
        raise CurriculumCoveragePreflightError("stage12638_rows_hash_drift")
    rows = read_rows(rows_bytes)
    if len(rows) != 99:
        raise CurriculumCoveragePreflightError("stage12638_rows_count_drift")
    if summary.get("authoritative_admitted_train_support_tasks_after_update") != 190:
        raise CurriculumCoveragePreflightError("stage12638_authoritative_count_drift")
    if summary.get("stage12639_curriculum_coverage_preflight_allowed") is not True:
        raise CurriculumCoveragePreflightError("stage12639_preflight_not_allowed")
    for field in ("dataset_rows_admitted", "new_rows_admitted", "training_allowed", "level_3_materialized", "replay_trustworthy"):
        if summary.get(field) is not False:
            raise CurriculumCoveragePreflightError("stage12638_forbidden_gate_drift:" + field)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private, "coverage": coverage, "rows": rows}


def load_schema() -> dict[str, Any]:
    loss_schema = read_json(LOSS_SCHEMA)
    row_schema = read_json(MANIFEST_ROW_SCHEMA)
    allowed_loss_keys = set((loss_schema.get("properties") or {}).keys())
    required_fields = tuple(row_schema.get("required") or CANONICAL_REQUIRED_FIELDS)
    if set(required_fields) != set(CANONICAL_REQUIRED_FIELDS):
        raise CurriculumCoveragePreflightError("manifest_schema_required_field_drift")
    return {"allowed_loss_keys": allowed_loss_keys, "required_fields": required_fields}


def row_audit(rows: list[dict[str, Any]], schema: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    allowed_loss_keys = set(schema["allowed_loss_keys"])
    required_fields = set(schema["required_fields"])
    missing_required_counts: Counter[str] = Counter()
    unsupported_loss_counts: Counter[str] = Counter()
    loss_key_counts: Counter[str] = Counter()
    task_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    signal_counts: Counter[str] = Counter()
    row_local_training_allowed = 0
    private_rows: list[dict[str, Any]] = []
    canonical_ready = 0
    for index, row in enumerate(rows):
        row_id = str(row.get("row_id") or f"row_{index}")
        task = str(row.get("task_family") or row.get("task_projection") or row.get("record_type") or "unknown")
        language = str(row.get("language_family") or "unknown")
        task_counts[task] += 1
        language_counts[language] += 1
        missing = sorted(required_fields - set(row))
        missing_required_counts.update(missing)
        loss_mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        enabled_loss_keys = sorted(key for key, value in loss_mask.items() if value)
        loss_key_counts.update(enabled_loss_keys)
        unsupported = sorted(key for key in enabled_loss_keys if key not in allowed_loss_keys)
        unsupported_loss_counts.update(unsupported)
        signals = sorted(name for name, predicate in CURRICULUM_SIGNAL_RULES.items() if predicate(row))
        signal_counts.update(signals)
        admission = row.get("admission") if isinstance(row.get("admission"), dict) else {}
        local_training_allowed = admission.get("training_allowed") is True
        row_local_training_allowed += int(local_training_allowed)
        if not missing and not unsupported and enabled_loss_keys:
            canonical_ready += 1
        private_rows.append({
            "row_index": index,
            "row_id": row_id,
            "task_family_or_projection": task,
            "language_family": language,
            "missing_required_fields": missing,
            "enabled_loss_keys": enabled_loss_keys,
            "unsupported_loss_keys": unsupported,
            "curriculum_signals": signals,
            "row_local_training_allowed_normalized_to_train_support_only": local_training_allowed,
            "canonical_trainer_ready": (not missing and not unsupported and bool(enabled_loss_keys)),
        })
    matrix = {
        "record_type": "stage12639_public_curriculum_coverage_matrix_v1",
        "coverage_scope": "authoritative_update_evidence_rows_preflight_only",
        "row_count": len(rows),
        "canonical_trainer_ready_rows": canonical_ready,
        "canonical_trainer_blocked_rows": len(rows) - canonical_ready,
        "row_local_training_allowed_metadata_count": row_local_training_allowed,
        "row_local_training_allowed_normalization": "treat_as_train_support_allowed_not_project_training_authority",
        "task_family_or_projection_counts": dict(sorted(task_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "loss_key_counts": dict(sorted(loss_key_counts.items())),
        "unsupported_loss_key_counts": dict(sorted(unsupported_loss_counts.items())),
        "missing_required_field_counts": dict(sorted(missing_required_counts.items())),
        "curriculum_signal_counts": dict(sorted(signal_counts.items())),
        "supported_curriculum_signals": sorted(signal_counts),
        "missing_curriculum_signals": list(MISSING_CURRICULUM_SIGNALS),
        "recommended_next_renderer": "stage12640_canonical_curriculum_renderer_preflight_only",
        "training_allowed_after_preflight": False,
    }
    return matrix, private_rows


def build_preflight(stage12638: Mapping[str, Any], matrix: Mapping[str, Any]) -> dict[str, Any]:
    checks = [
        {"check_id": "stage12638_materialization_pinned", "status": "passed"},
        {"check_id": "authoritative_count_190_gap_310_confirmed", "status": "passed"},
        {"check_id": "row_evidence_hash_pinned", "status": "passed", "row_count": 99},
        {"check_id": "canonical_schema_gap_measured", "status": "passed", "canonical_ready_rows": matrix["canonical_trainer_ready_rows"]},
        {"check_id": "row_local_training_allowed_normalized", "status": "passed", "metadata_rows": matrix["row_local_training_allowed_metadata_count"]},
        {"check_id": "curriculum_missing_signals_recorded", "status": "passed", "missing_signal_count": len(matrix["missing_curriculum_signals"])},
        {"check_id": "admission_training_eval_replay_level3_gpu_forbidden", "status": "passed"},
    ]
    return {
        "record_type": "stage12639_curriculum_coverage_admission_preflight_v1",
        "preflight_scope": "curriculum_coverage_admission_preflight_only",
        "source_stage12638_summary_sha256": EXPECTED_HASHES["stage12638_summary"],
        "source_stage12638_rows_sha256": EXPECTED_HASHES["stage12638_rows_bytes"],
        "curriculum_coverage_matrix_sha256": stable_hash(matrix),
        "preflight_checks": checks,
        "preflight_check_count": len(checks),
        "preflight_status": "curriculum_coverage_recorded_no_admission_or_training",
        "authoritative_train_support_tasks_after_update": 190,
        "authoritative_gap_to_500_after_update": 310,
        "row_evidence_count": matrix["row_count"],
        "canonical_trainer_ready_rows": matrix["canonical_trainer_ready_rows"],
        "canonical_trainer_blocked_rows": matrix["canonical_trainer_blocked_rows"],
        "unsupported_loss_key_counts": matrix["unsupported_loss_key_counts"],
        "missing_required_field_counts": matrix["missing_required_field_counts"],
        "missing_curriculum_signal_count": len(matrix["missing_curriculum_signals"]),
        "recommended_next_stage": "stage12640_canonical_curriculum_renderer_preflight_only",
        "dataset_rows_admitted_after_preflight": False,
        "training_allowed_after_preflight": False,
    }


def build_packet(stage12638: Mapping[str, Any], schema: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    matrix, private_rows = row_audit(stage12638["rows"], schema)
    preflight = build_preflight(stage12638, matrix)
    true_fields = {
        "authoritative_ledger_update_allowed": True,
        "authoritative_ledger_updated": True,
        "ledger_update_materialized": True,
        "stage12638_authoritative_ledger_update_materialization_only_allowed": True,
        "stage12639_curriculum_coverage_preflight_allowed": True,
        "stage12639_curriculum_coverage_preflight_only": True,
        "stage12639_curriculum_coverage_preflight_performed": True,
        "stage12640_canonical_curriculum_renderer_preflight_allowed": True,
        "vm_branch_remains_paused": True,
    }
    private = {
        "record_type": "stage12639_private_curriculum_coverage_admission_preflight_only_v1",
        **no_claim_fields(),
        **true_fields,
        "source_hashes": EXPECTED_HASHES,
        "curriculum_coverage_admission_preflight": preflight,
        "curriculum_coverage_matrix": matrix,
        "private_row_audit_sha256_pending_external_file": True,
        "decision": "CURRICULUM_COVERAGE_PREFLIGHT_RECORDED_NO_ADMISSION_OR_TRAINING",
    }
    contract = {
        "record_type": "stage12639_public_curriculum_coverage_admission_preflight_only_contract_v1",
        **no_claim_fields(),
        **true_fields,
        "stage12638_summary_sha256": EXPECTED_HASHES["stage12638_summary"],
        "stage12638_rows_sha256": EXPECTED_HASHES["stage12638_rows_bytes"],
        "curriculum_coverage_matrix_sha256": stable_hash(matrix),
        "curriculum_coverage_preflight_sha256": stable_hash(preflight),
        "private_curriculum_coverage_preflight_sha256": stable_hash(private),
        "claim_boundary": {
            "preflight": "curriculum_coverage_only",
            "authoritative_train_support_count": "190_preserved_from_stage12638",
            "canonical_trainer_rows": "not_materialized",
            "dataset_row_admission": "not_performed",
            "training": "not_authorized",
            "eval": "not_authorized",
            "replay": "not_executed",
            "level3": "not_materialized",
            "gpu": "not_authorized",
        },
    }
    summary = {
        "record_type": "stage12639_public_curriculum_coverage_admission_preflight_only_summary_v1",
        **no_claim_fields(),
        **true_fields,
        "stage": STAGE,
        "decision": "CURRICULUM_COVERAGE_PREFLIGHT_RECORDED_NO_ADMISSION_OR_TRAINING",
        "stage12638_summary_sha256": EXPECTED_HASHES["stage12638_summary"],
        "stage12638_rows_sha256": EXPECTED_HASHES["stage12638_rows_bytes"],
        "curriculum_coverage_matrix_sha256": stable_hash(matrix),
        "curriculum_coverage_preflight_sha256": stable_hash(preflight),
        "private_curriculum_coverage_preflight_sha256": stable_hash(private),
        "preflight_status": "curriculum_coverage_recorded_no_admission_or_training",
        "authoritative_admitted_train_support_tasks_after_update": 190,
        "authoritative_gap_to_500_after_update": 310,
        "row_evidence_count": matrix["row_count"],
        "canonical_trainer_ready_rows": matrix["canonical_trainer_ready_rows"],
        "canonical_trainer_blocked_rows": matrix["canonical_trainer_blocked_rows"],
        "row_local_training_allowed_metadata_count": matrix["row_local_training_allowed_metadata_count"],
        "unsupported_loss_key_count": sum(matrix["unsupported_loss_key_counts"].values()),
        "missing_required_field_count": sum(matrix["missing_required_field_counts"].values()),
        "curriculum_supported_signal_count": len(matrix["supported_curriculum_signals"]),
        "curriculum_missing_signal_count": len(matrix["missing_curriculum_signals"]),
        "frontier_100m_training_dataset_ready": False,
        "downstream_blockers": [
            "canonical_curriculum_renderer_not_materialized",
            "canonical_trainer_ready_rows_zero",
            "repo_graph_symbol_localization_patch_repair_signals_missing",
            "training_admission_forbidden",
        ],
        "next_required_action": "stage12640_canonical_curriculum_renderer_preflight_only",
    }
    for label, record in (("summary", summary), ("contract", contract), ("matrix", matrix)):
        check_false(record, "stage12639_" + label)
        assert_public_sanitized(record, "stage12639_" + label)
    check_false(private, "stage12639_private")
    return summary, contract, private, matrix, private_rows


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12638 = load_stage12638()
    schema = load_schema()
    summary, contract, private, matrix, private_rows = build_packet(stage12638, schema)
    row_audit_sha = stable_hash(private_rows)
    private["private_row_audit_sha256"] = row_audit_sha
    private["private_row_audit_sha256_pending_external_file"] = False
    contract["private_curriculum_coverage_preflight_sha256"] = stable_hash(private)
    summary["private_curriculum_coverage_preflight_sha256"] = stable_hash(private)
    pointer = {
        "record_type": "stage12639_public_private_curriculum_coverage_admission_preflight_pointer_v1",
        **no_claim_fields(),
        "stage12638_summary_sha256": EXPECTED_HASHES["stage12638_summary"],
        "contract_sha256": stable_hash(contract),
        "private_curriculum_coverage_preflight_sha256": stable_hash(private),
        "curriculum_coverage_preflight_sha256": stable_hash(private["curriculum_coverage_admission_preflight"]),
        "curriculum_coverage_matrix_sha256": stable_hash(matrix),
        "private_row_audit_sha256": row_audit_sha,
        "authoritative_ledger_update_allowed": True,
        "authoritative_ledger_updated": True,
        "ledger_update_materialized": True,
        "stage12638_authoritative_ledger_update_materialization_only_allowed": True,
        "stage12639_curriculum_coverage_preflight_allowed": True,
        "stage12639_curriculum_coverage_preflight_only": True,
        "stage12639_curriculum_coverage_preflight_performed": True,
        "stage12640_canonical_curriculum_renderer_preflight_allowed": True,
        "vm_branch_remains_paused": True,
    }
    check_false(pointer, "stage12639_pointer")
    assert_public_sanitized(pointer, "stage12639_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "curriculum_coverage_matrix.json", matrix)
    write_jsonl(out / "private/row_curriculum_audit.jsonl", private_rows)
    write_json(out / "private/curriculum_coverage_admission_preflight_only.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    fsync_dir(out / "private")
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))

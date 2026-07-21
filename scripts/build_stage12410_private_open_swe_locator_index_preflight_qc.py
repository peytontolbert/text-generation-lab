#!/usr/bin/env python3
"""Build Stage12410 private Open-SWE locator-index preflight QC.

This is a fail-closed control stage. It does not read raw parquet rows, emit
raw locator values, execute replay, or admit training/eval rows. Its purpose is
to make the current blocker explicit: Stage12408/12409 requests are hash-safe
but do not carry enough raw-record locator proof to replay.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12410_private_open_swe_locator_index_preflight_qc"
OUT = ROOT / "runs/local/artifacts" / STAGE
PRIVATE_OUT = ROOT / "runs/local/private" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12409_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12409_open_swe_replay_executor_preflight/"
    "open_swe_replay_executor_preflight.jsonl"
)
STAGE12409_SUMMARY = ROOT / "runs/summaries/stage12409_open_swe_replay_executor_preflight.json"
STAGE12408_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12408_replay_calibration_execution_request/"
    "replay_calibration_execution_requests.jsonl"
)
STAGE12327_OPEN_SWE = (
    ROOT
    / "runs/local/artifacts/stage12327_external_adapter_preflight/"
    "open_swe_trace_support_candidates.jsonl"
)
STAGE12402_DIGESTS = (
    ROOT
    / "runs/local/artifacts/stage12402_open_swe_private_event_digest_extractor/"
    "open_swe_private_event_digests.jsonl"
)
STAGE12404_REQUESTS = (
    ROOT
    / "runs/local/artifacts/stage12404_open_swe_replay_state_reconstruction_request/"
    "open_swe_replay_state_reconstruction_request_items.jsonl"
)

ROWS_NAME = "private_open_swe_locator_index_preflight_qc.jsonl"
MANIFEST_NAME = "private_open_swe_locator_index_preflight_manifest.json"
GUARDRAIL_NAME = "guardrail_scan.json"
PRIVATE_INDEX_NAME = "open_swe_raw_locator_index.private.jsonl"

SAFE_RESULT_SCHEMA_VERSION = "stage12410_private_locator_index_preflight_qc_v1"
DATASET_REF_HASH = hashlib.sha256(b"nvidia--Open-SWE-Traces").hexdigest()[:24]

MISSING_MAPPING_FIELDS = [
    "repo_id",
    "commit_sha",
    "verifier_command",
    "patch_ref",
    "raw_record_locator",
    "state_before_locator",
    "state_after_locator",
]

PROOF_SLOT_NAMES = [
    "state_before",
    "action",
    "observation",
    "verifier_identity",
    "verifier_output_class",
    "patch_application",
    "causal_linkage",
    "state_after",
    "stop_continue",
    "root_split_no_leak",
    "option_permutation",
]

RAW_CONTENT_POLICY: dict[str, bool] = {
    "raw_parquet_rows_read": False,
    "raw_trajectory_text_emitted": False,
    "raw_commands_emitted": False,
    "raw_outputs_emitted": False,
    "raw_patches_emitted": False,
    "source_text_emitted": False,
    "absolute_paths_emitted": False,
    "raw_dataset_paths_emitted": False,
    "urls_emitted": False,
    "issue_bodies_emitted": False,
    "line_contents_emitted": False,
    "patch_diffs_emitted": False,
}

CLAIM_BOUNDARY: dict[str, bool | str] = {
    "boundary": "private_locator_index_preflight_only",
    "raw_locator_emitted": False,
    "mapping_proven": False,
    "replay_executed": False,
    "training_claim": False,
    "admission_claim": False,
    "level3_claim": False,
    "repair_claim": False,
    "fail_to_pass_claim": False,
    "patch_trace_claim": False,
}

ZERO_ADMISSION_FLAGS: dict[str, bool | int] = {
    "admission": False,
    "training_allowed": False,
    "training_row_count": 0,
    "eval_row_count": 0,
    "admitted_rows": 0,
    "mapping_proven_count": 0,
    "replay_attempted_count": 0,
    "replay_succeeded_safe_status_count": 0,
    "level3_admitted": 0,
    "patch_trace_admitted": 0,
    "repair_claim_admitted": 0,
    "fail_to_pass_claim_admitted": 0,
    "strict_eval_eligible": 0,
    "source_heldout_admissible": 0,
}

ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
DIFF_RE = re.compile(r"diff --git|@@ |^\+\+\+ |^--- |<<<<<<<", re.MULTILINE)
RAW_KEY_RE = re.compile(r"^(trajectory|command|output|patch|diff|content|stdout|stderr|issue_body)$", re.IGNORECASE)


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    if not path.exists():
        return rows, [f"missing_input_{path.name}"]
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                issues.append(f"{path.name}_line_{line_number}_invalid_json")
                continue
            if not isinstance(value, dict):
                issues.append(f"{path.name}_line_{line_number}_not_object")
                continue
            rows.append(value)
    return rows, issues


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def build_private_locator_index(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create a private, non-model-facing raw locator index.

    This file lives under runs/local/private and is not a public/model-facing
    artifact. It contains raw locator fields already present in Stage12327, but
    no trajectory text, command output, patches, diffs, source text, issue
    bodies, or parquet row contents.
    """
    private_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows, 1):
        source_ref = row.get("source_record_ref") if isinstance(row.get("source_record_ref"), dict) else {}
        if not source_ref:
            continue
        basis = {
            "candidate_id": row.get("candidate_id"),
            "source_record_ref": source_ref,
            "index": index,
        }
        private_rows.append(
            {
                "private_locator_id": f"{STAGE}::private::{stable_hash(basis, 20)}",
                "source_stage": "stage12327_external_adapter_preflight",
                "source_candidate_hash": stable_hash(row.get("candidate_id") or f"row_{index}", 24),
                "source_record_ref": source_ref,
                "source_record_ref_hash": stable_hash(source_ref, 24),
                "instance_ref_hash": stable_hash(source_ref.get("instance_id") or "missing", 24),
                "trajectory_ref_hash": stable_hash(source_ref.get("trajectory_id") or "missing", 24),
                "trajectory_family_hash": stable_hash(source_ref.get("trajectory_family") or "missing", 24),
                "dataset_file_hash": stable_hash(source_ref.get("dataset_file") or "missing", 24),
                "language_family": row.get("language_family") or "unknown",
                "repo_family_hash": stable_hash(row.get("repo_family") or "unknown", 24),
                "selected_test_count": int(row.get("selected_test_count") or 0),
                "seed_path_count": int(row.get("seed_path_count") or 0),
                "private_raw_locator_index_only": True,
                "not_model_facing": True,
                "raw_parquet_row_content_read": False,
                "raw_trajectory_text_included": False,
                "raw_command_output_included": False,
                "raw_patch_or_diff_included": False,
            }
        )
    return private_rows


def local_open_swe_inventory() -> dict[str, Any]:
    dataset_dir = Path("/arxiv/datasets/nvidia--Open-SWE-Traces")
    try:
        parquet_count = sum(1 for child in dataset_dir.rglob("*.parquet") if child.is_file())
    except (OSError, PermissionError):
        return {
            "local_open_swe_dataset_presence_status": "unavailable",
            "local_open_swe_parquet_file_count": 0,
        }
    return {
        "local_open_swe_dataset_presence_status": "present_count_only" if parquet_count else "unavailable",
        "local_open_swe_parquet_file_count": parquet_count,
    }


def index_stage12408(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("request_id") or ""): row for row in rows if row.get("request_id")}


def proof_slot_statuses() -> dict[str, dict[str, Any]]:
    return {
        name: {
            "proof_status": "blocked",
            "proof_proven": False,
            "evidence_class": "private_locator_index_preflight_not_replay_proof",
            "proof_ref_hash": "missing",
            "status_code": f"blocked_{name}_proof_not_materialized",
        }
        for name in PROOF_SLOT_NAMES
    }


def build_open_swe_row(row: dict[str, Any], stage12408_by_id: dict[str, dict[str, Any]], rank: int) -> dict[str, Any]:
    request_id = str(row.get("stage12408_request_id") or "")
    request = stage12408_by_id.get(request_id, {})
    request_hashes = request.get("input_artifact_hashes") if isinstance(request.get("input_artifact_hashes"), dict) else {}
    safe_identifier_basis = {
        "stage12408_request_id": request_id,
        "source_request_id": row.get("source_request_id"),
        "source_adapter_ref_hash": request.get("source_adapter_ref_hash"),
        "stage12407_work_item_ref_hash": request_hashes.get("stage12407_work_item_ref_hash"),
    }
    missing_mapping_fields = list(row.get("missing_mapping_fields") or MISSING_MAPPING_FIELDS)
    blockers = [
        "blocked_private_locator_values_not_available_in_stage12408_or_stage12409",
        "blocked_raw_record_locator_missing",
        "blocked_repo_commit_verifier_patch_and_state_locators_missing",
        "blocked_no_raw_parquet_row_read_in_qc_stage",
        "blocked_no_replay_attempted",
        "fail_closed_if_uncertain",
    ]
    if len(missing_mapping_fields) != len(MISSING_MAPPING_FIELDS):
        blockers.append("blocked_mapping_field_set_not_complete")
    return {
        "locator_qc_id": f"{STAGE}::{stable_hash({'request': request_id, 'rank': rank}, 20)}",
        "source_stage": "stage12409_open_swe_replay_executor_preflight",
        "source_preflight_id": row.get("preflight_id"),
        "stage12408_request_id": request_id,
        "source_request_id": row.get("source_request_id"),
        "source_family": "open_swe",
        "executor_kind": row.get("executor_kind") or "open_swe_replay_calibration",
        "safe_result_schema_version": SAFE_RESULT_SCHEMA_VERSION,
        "dataset_ref_hash": DATASET_REF_HASH,
        "local_dataset_presence_status": row.get("local_dataset_presence_status") or "unknown",
        "local_parquet_file_count": int(row.get("local_parquet_file_count") or 0),
        "metadata_inspection_status": "count_only_no_parquet_metadata_read",
        "safe_row_identifier_status": "request_hash_only_not_raw_locator",
        "safe_row_identifier_hash": stable_hash(safe_identifier_basis, 24),
        "locator_index_ref_hash": stable_hash({"safe_identifier": safe_identifier_basis, "missing": missing_mapping_fields}, 24),
        "locator_index_status": "blocked",
        "locator_index_candidate_count": 1,
        "locator_index_proven": False,
        "mapping_proven": False,
        "missing_mapping_fields": missing_mapping_fields,
        "proof_slot_statuses": proof_slot_statuses(),
        "request_readiness_status": "raw_unavailable",
        "execution_attempt_status": "skipped_blocked",
        "replay_outcome_status": "not_run",
        "level3_status": "level3_still_blocked",
        "blockers": sorted(set(blockers)),
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
    }


def scan_value(value: Any, artifact: str, issues: list[dict[str, Any]], key_path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{key_path}.{key}" if key_path else str(key)
            if RAW_KEY_RE.search(str(key)) and isinstance(child, str) and child not in {"missing", "blocked", "not_applicable"}:
                # Hash/status fields are allowed; raw-looking values are not.
                if not str(key).endswith(("_hash", "_count", "_status", "_class", "_policy")):
                    issues.append({"artifact": artifact, "issue": "raw_like_key_with_string_value", "key_hash": stable_hash(child_path, 16)})
            scan_value(child, artifact, issues, child_path)
        return
    if isinstance(value, list):
        for list_index, child in enumerate(value):
            scan_value(child, artifact, issues, f"{key_path}[{list_index}]")
        return
    if not isinstance(value, str):
        return
    if ABS_PATH_RE.search(value):
        issues.append({"artifact": artifact, "issue": "absolute_path_string", "key_hash": stable_hash(key_path, 16)})
    if URL_RE.search(value):
        issues.append({"artifact": artifact, "issue": "url_string", "key_hash": stable_hash(key_path, 16)})
    if DIFF_RE.search(value):
        issues.append({"artifact": artifact, "issue": "diff_like_string", "key_hash": stable_hash(key_path, 16)})


def guardrail_scan(paths: list[Path]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    scanned_json_values = 0
    scanned_jsonl_rows = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if ABS_PATH_RE.search(text):
            issues.append({"artifact": path.name, "issue": "absolute_path_pattern"})
        if URL_RE.search(text):
            issues.append({"artifact": path.name, "issue": "url_pattern"})
        if DIFF_RE.search(text):
            issues.append({"artifact": path.name, "issue": "diff_like_pattern"})
        if path.suffix == ".jsonl":
            for line_number, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                scanned_jsonl_rows += 1
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    issues.append({"artifact": path.name, "issue": "invalid_jsonl", "line": line_number})
                    continue
                scan_value(value, path.name, issues, f"line[{line_number}]")
            continue
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            issues.append({"artifact": path.name, "issue": "invalid_json"})
            continue
        scanned_json_values += 1
        scan_value(value, path.name, issues)
    return {
        "scan_passed": not issues,
        "issues": issues,
        "scanned_artifact_count": len(paths),
        "scanned_json_values": scanned_json_values,
        "scanned_jsonl_rows": scanned_jsonl_rows,
    }


def validate_rows(rows: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    required = [
        "locator_qc_id",
        "source_stage",
        "source_preflight_id",
        "stage12408_request_id",
        "source_request_id",
        "source_family",
        "executor_kind",
        "safe_result_schema_version",
        "dataset_ref_hash",
        "local_dataset_presence_status",
        "local_parquet_file_count",
        "metadata_inspection_status",
        "safe_row_identifier_status",
        "safe_row_identifier_hash",
        "locator_index_ref_hash",
        "locator_index_status",
        "missing_mapping_fields",
        "proof_slot_statuses",
        "request_readiness_status",
        "execution_attempt_status",
        "replay_outcome_status",
        "level3_status",
        "blockers",
        "raw_content_policy",
        "claim_boundary",
        "zero_admission_flags",
    ]
    for index, row in enumerate(rows, 1):
        for key in required:
            if key not in row:
                issues.append(f"row_{index}_missing_{key}")
        if row.get("source_family") != "open_swe":
            issues.append(f"row_{index}_not_open_swe")
        if row.get("locator_index_status") != "blocked":
            issues.append(f"row_{index}_locator_index_status_not_blocked")
        if row.get("locator_index_proven") is not False:
            issues.append(f"row_{index}_locator_index_proven")
        if row.get("mapping_proven") is not False:
            issues.append(f"row_{index}_mapping_proven")
        if row.get("replay_outcome_status") != "not_run":
            issues.append(f"row_{index}_replay_outcome_not_not_run")
        if row.get("level3_status") != "level3_still_blocked":
            issues.append(f"row_{index}_level3_not_blocked")
        for key, expected in RAW_CONTENT_POLICY.items():
            if row.get("raw_content_policy", {}).get(key) is not expected:
                issues.append(f"row_{index}_raw_content_policy_{key}_mismatch")
        for key, expected in CLAIM_BOUNDARY.items():
            if row.get("claim_boundary", {}).get(key) != expected:
                issues.append(f"row_{index}_claim_boundary_{key}_mismatch")
        for key, expected in ZERO_ADMISSION_FLAGS.items():
            if row.get("zero_admission_flags", {}).get(key) != expected:
                issues.append(f"row_{index}_zero_admission_flags_{key}_mismatch")
        for slot_name, slot in row.get("proof_slot_statuses", {}).items():
            if slot_name not in PROOF_SLOT_NAMES:
                issues.append(f"row_{index}_unexpected_proof_slot_{slot_name}")
            if not isinstance(slot, dict) or slot.get("proof_proven") is not False:
                issues.append(f"row_{index}_proof_slot_{slot_name}_not_blocked")
    return issues


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    PRIVATE_OUT.mkdir(parents=True, exist_ok=True)
    stage12409_rows, input_issues = read_jsonl(STAGE12409_ROWS)
    stage12408_rows, stage12408_issues = read_jsonl(STAGE12408_ROWS)
    stage12327_rows, stage12327_issues = read_jsonl(STAGE12327_OPEN_SWE)
    stage12402_rows, stage12402_issues = read_jsonl(STAGE12402_DIGESTS)
    stage12404_rows, stage12404_issues = read_jsonl(STAGE12404_REQUESTS)
    stage12408_by_id = index_stage12408(stage12408_rows)
    stage12409_summary = read_json(STAGE12409_SUMMARY)
    inventory = local_open_swe_inventory()

    open_swe_rows = [row for row in stage12409_rows if row.get("source_family") == "open_swe"]
    bears_rows = [row for row in stage12409_rows if row.get("source_family") == "bears"]
    output_rows = [build_open_swe_row(row, stage12408_by_id, rank) for rank, row in enumerate(open_swe_rows, 1)]
    private_locator_rows = build_private_locator_index(stage12327_rows)

    schema_issues = list(input_issues)
    schema_issues.extend(stage12408_issues)
    schema_issues.extend(stage12327_issues)
    schema_issues.extend(stage12402_issues)
    schema_issues.extend(stage12404_issues)
    schema_issues.extend(validate_rows(output_rows))
    if not private_locator_rows:
        schema_issues.append("private_locator_index_empty")

    manifest = {
        "stage": STAGE,
        "record_type": "private_open_swe_locator_index_preflight_manifest",
        "input_stage12409_bundle_hash": file_hash(STAGE12409_ROWS),
        "input_stage12409_summary_hash": file_hash(STAGE12409_SUMMARY),
        "input_stage12408_bundle_hash": file_hash(STAGE12408_ROWS),
        "input_stage12327_open_swe_bundle_hash": file_hash(STAGE12327_OPEN_SWE),
        "input_stage12402_digest_bundle_hash": file_hash(STAGE12402_DIGESTS),
        "input_stage12404_request_bundle_hash": file_hash(STAGE12404_REQUESTS),
        "output_bundle_hash": stable_hash(output_rows),
        "private_locator_index_bundle_hash": stable_hash(private_locator_rows),
        "private_locator_index_path_emitted_publicly": False,
        "safe_result_schema_version": SAFE_RESULT_SCHEMA_VERSION,
        "inspection_policy": {
            "private_locator_index_preflight_only": True,
            "raw_parquet_rows_read": False,
            "raw_parquet_metadata_read": False,
            "raw_content_allowed": False,
            "replay_executed": False,
            "fail_closed_if_uncertain": True,
        },
        "local_open_swe_dataset_inventory": {
            "dataset_ref_hash": DATASET_REF_HASH,
            **inventory,
        },
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
    }

    rows_path = OUT / ROWS_NAME
    manifest_path = OUT / MANIFEST_NAME
    private_index_path = PRIVATE_OUT / PRIVATE_INDEX_NAME
    write_jsonl(rows_path, output_rows)
    write_json(manifest_path, manifest)
    write_jsonl(private_index_path, private_locator_rows)
    guardrail = guardrail_scan([rows_path, manifest_path])
    write_json(OUT / GUARDRAIL_NAME, guardrail)

    guardrail_issues = list(guardrail.get("issues") or [])
    raw_leak_count = len(guardrail_issues)
    hard_reject_count = len(schema_issues) + len(guardrail_issues)
    readiness_counts = Counter(str(row.get("request_readiness_status") or "unknown") for row in output_rows)
    locator_counts = Counter(str(row.get("locator_index_status") or "unknown") for row in output_rows)
    stage12327_private_ref_hashes = {stable_hash(row.get("source_record_ref") or {}, 24) for row in stage12327_rows if row.get("source_record_ref")}
    stage12402_raw_ref_hashes = {
        str((row.get("raw_row_ref_hashes") or {}).get("source_record_ref_hash") or "missing")
        for row in stage12402_rows
        if isinstance(row.get("raw_row_ref_hashes"), dict)
    }
    stage12404_raw_ref_hashes = {
        str((row.get("source_digest_refs") or {}).get("source_record_ref_hash") or "missing")
        for row in stage12404_rows
        if isinstance(row.get("source_digest_refs"), dict)
    }

    decision = (
        "fail_closed_private_locator_index_preflight_blocked_by_qc_issue"
        if hard_reject_count
        else "fail_closed_private_locator_index_preflight_no_training_no_replay"
    )
    summary = {
        "stage": STAGE,
        "record_type": "private_open_swe_locator_index_preflight_summary",
        "decision": decision,
        "input_stage12409_row_count": len(stage12409_rows),
        "input_open_swe_row_count": len(open_swe_rows),
        "input_bears_ignored_count": len(bears_rows),
        "stage12409_decision": stage12409_summary.get("decision"),
        "local_open_swe_dataset_presence_status": inventory["local_open_swe_dataset_presence_status"],
        "local_open_swe_parquet_file_count": inventory["local_open_swe_parquet_file_count"],
        "stage12327_private_ref_rows": len(stage12327_rows),
        "stage12327_unique_private_ref_hashes": len(stage12327_private_ref_hashes),
        "stage12402_digest_rows_with_raw_hash_lineage": len(stage12402_rows),
        "stage12402_unique_source_record_ref_hashes": len(stage12402_raw_ref_hashes - {"missing"}),
        "stage12404_request_rows_with_raw_hash_lineage": len(stage12404_rows),
        "stage12404_unique_source_record_ref_hashes": len(stage12404_raw_ref_hashes - {"missing"}),
        "private_locator_index_rows": len(private_locator_rows),
        "private_locator_index_hash": stable_hash(private_locator_rows, 24),
        "private_locator_index_path_emitted_publicly": False,
        "stage12408_open_swe_rows_with_direct_raw_record_locator": 0,
        "stage12408_open_swe_rows_with_direct_stage12404_request_id": 0,
        "stage12408_open_swe_rows_artifact_level_only": len(open_swe_rows),
        "raw_parquet_rows_read_count": 0,
        "raw_content_emitted_count": 0,
        "raw_dataset_paths_emitted_count": 0,
        "locator_index_candidate_count": len(output_rows),
        "locator_index_status_counts": dict(sorted(locator_counts.items())),
        "locator_index_proven_count": 0,
        "mapping_proven_count": 0,
        "request_readiness_status_counts": dict(sorted(readiness_counts.items())),
        "replay_attempted_count": 0,
        "replay_succeeded_safe_status_count": 0,
        "admitted_rows": 0,
        "training_allowed": False,
        "training_row_count": 0,
        "eval_row_count": 0,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "repair_claim_admitted": 0,
        "fail_to_pass_claim_admitted": 0,
        "strict_eval_eligible": 0,
        "source_heldout_admissible": 0,
        "schema_issue_count": len(schema_issues),
        "schema_issues": schema_issues,
        "guardrail_issue_count": len(guardrail_issues),
        "guardrail_issues": guardrail_issues,
        "raw_leak_count": raw_leak_count,
        "hard_reject_count": hard_reject_count,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
    }
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()

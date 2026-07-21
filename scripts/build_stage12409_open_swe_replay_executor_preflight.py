#!/usr/bin/env python3
"""Build Stage12409 fail-closed Open-SWE replay executor preflight.

This stage classifies Stage12408 replay calibration execution requests. It is
not an executor: it does not run replay, read raw parquet rows, hydrate repos,
apply patches, or emit raw paths/content.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12409_open_swe_replay_executor_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

INPUT_REQUESTS = (
    ROOT
    / "runs/local/artifacts/stage12408_replay_calibration_execution_request/"
    "replay_calibration_execution_requests.jsonl"
)
INPUT_SUMMARY = ROOT / "runs/summaries/stage12408_replay_calibration_execution_request.json"

RESULTS_NAME = "open_swe_replay_executor_preflight.jsonl"
MANIFEST_NAME = "open_swe_replay_executor_preflight_manifest.json"
GUARDRAIL_NAME = "guardrail_scan.json"

SAFE_RESULT_SCHEMA_VERSION = "stage12409_safe_replay_result_v1"
OPEN_SWE_DATASET_REF_HASH = hashlib.sha256(b"nvidia--Open-SWE-Traces").hexdigest()[:24]

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
    "raw_trajectory_text_emitted": False,
    "raw_commands_emitted": False,
    "raw_outputs_emitted": False,
    "raw_patches_emitted": False,
    "source_text_emitted": False,
    "absolute_paths_emitted": False,
    "urls_emitted": False,
    "issue_bodies_emitted": False,
    "line_contents_emitted": False,
    "patch_diffs_emitted": False,
    "raw_parquet_rows_read": False,
    "raw_dataset_paths_emitted": False,
}

CLAIM_BOUNDARY: dict[str, bool | str] = {
    "boundary": "preflight_only_no_executor",
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
MULTILINE_RE = re.compile(r"[\r\n]")


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


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


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
        return rows, ["missing_stage12408_requests"]
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                issues.append(f"input_line_{line_number}_invalid_json")
                continue
            if not isinstance(value, dict):
                issues.append(f"input_line_{line_number}_not_object")
                continue
            rows.append(value)
    return rows, issues


def requested_schema_hash(row: dict[str, Any]) -> str:
    return stable_hash(row.get("requested_safe_return_schema") or [], 24)


def find_mapping_proof(row: dict[str, Any]) -> tuple[bool, list[str]]:
    """Fail closed unless all required mapping fields are hash-safe and present.

    Stage12408 currently carries no raw locator mapping proof. This function
    permits future hash-safe mapping proofs without treating raw-like fields as
    evidence.
    """
    proof = row.get("mapping_proof")
    if not isinstance(proof, dict):
        return False, list(MISSING_MAPPING_FIELDS)
    missing = [field for field in MISSING_MAPPING_FIELDS if not proof.get(f"{field}_hash")]
    return not missing, missing


def local_open_swe_inventory() -> dict[str, Any]:
    dataset_dir = Path("/arxiv/datasets/nvidia--Open-SWE-Traces")
    try:
        parquet_count = sum(1 for child in dataset_dir.rglob("*.parquet") if child.is_file())
    except (OSError, PermissionError):
        return {
            "local_dataset_presence_status": "unavailable",
            "local_dataset_ref_hash": OPEN_SWE_DATASET_REF_HASH,
            "local_parquet_file_count": 0,
        }
    if parquet_count > 0:
        return {
            "local_dataset_presence_status": "present_count_only",
            "local_dataset_ref_hash": OPEN_SWE_DATASET_REF_HASH,
            "local_parquet_file_count": parquet_count,
        }
    return {
        "local_dataset_presence_status": "unavailable",
        "local_dataset_ref_hash": OPEN_SWE_DATASET_REF_HASH,
        "local_parquet_file_count": 0,
    }


def proof_slot_statuses(status: str) -> dict[str, dict[str, Any]]:
    slot_status = "unavailable" if status == "raw_unavailable" else "blocked"
    return {
        name: {
            "proof_status": slot_status,
            "proof_proven": False,
            "evidence_class": "mapping_unavailable" if slot_status == "unavailable" else "environment_blocked",
            "proof_ref_hash": "missing",
            "status_code": f"{slot_status}_{name}_proof_not_proven",
        }
        for name in PROOF_SLOT_NAMES
    }


def build_row(row: dict[str, Any], index: int, inventory: dict[str, Any]) -> dict[str, Any]:
    source_family = str(row.get("source_family") or "unknown")
    mapping_proven, missing_mapping_fields = find_mapping_proof(row)

    if source_family == "bears":
        readiness_status = "environment_blocked"
        execution_attempt_status = "skipped_blocked"
        local_status = {
            "local_dataset_presence_status": "not_applicable",
            "local_dataset_ref_hash": None,
            "local_parquet_file_count": 0,
        }
        blockers = [
            "blocked_bears_local_hydration_unresolved",
            "blocked_environment_not_replay_ready",
            "blocked_no_replay_attempted",
            "fail_closed_if_uncertain",
        ]
    elif source_family == "open_swe" and mapping_proven:
        readiness_status = "executable"
        execution_attempt_status = "not_attempted"
        local_status = dict(inventory)
        blockers = [
            "blocked_preflight_only_executor_not_run",
            "blocked_level3_still_blocked_until_safe_replay_evidence",
            "fail_closed_no_admission_from_preflight",
        ]
    else:
        readiness_status = "raw_unavailable"
        execution_attempt_status = "skipped_blocked"
        local_status = dict(inventory) if source_family == "open_swe" else {
            "local_dataset_presence_status": "not_applicable",
            "local_dataset_ref_hash": None,
            "local_parquet_file_count": 0,
        }
        blockers = [
            "blocked_raw_mapping_unavailable_from_hash_safe_artifacts",
            "blocked_missing_repo_commit_verifier_patch_and_state_locators",
            "blocked_no_replay_attempted",
            "fail_closed_if_uncertain",
        ]

    basis = {
        "stage": STAGE,
        "stage12408_request_id": row.get("request_id"),
        "source_request_id": row.get("source_request_id"),
        "index": index,
    }
    return {
        "preflight_id": f"{STAGE}::{stable_hash(basis, 20)}",
        "source_request_id": row.get("source_request_id"),
        "stage12408_request_id": row.get("request_id"),
        "source_family": source_family,
        "executor_kind": row.get("executor_kind"),
        "request_readiness_status": readiness_status,
        "execution_attempt_status": execution_attempt_status,
        "replay_outcome_status": "not_run",
        "level3_status": "level3_still_blocked",
        "safe_result_schema_version": SAFE_RESULT_SCHEMA_VERSION,
        "requested_safe_return_schema_hash": requested_schema_hash(row),
        **local_status,
        "missing_mapping_fields": missing_mapping_fields,
        "proof_slot_statuses": proof_slot_statuses(readiness_status),
        "blockers": sorted(set(blockers)),
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
    }


def scan_value(value: Any, artifact: str, issues: list[dict[str, Any]], key_path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{key_path}.{key}" if key_path else str(key)
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
    if MULTILINE_RE.search(value):
        issues.append({"artifact": artifact, "issue": "multiline_string", "key_hash": stable_hash(key_path, 16)})


def guardrail_scan(paths: list[Path]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    parsed_json_values = 0
    scanned_jsonl_rows = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if ABS_PATH_RE.search(text):
            issues.append({"artifact": path.name, "issue": "absolute_path_pattern"})
        if URL_RE.search(text):
            issues.append({"artifact": path.name, "issue": "url_pattern"})
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
        parsed_json_values += 1
        scan_value(value, path.name, issues)
    return {
        "scan_passed": not issues,
        "issues": issues,
        "scanned_artifact_count": len(paths),
        "parsed_json_values": parsed_json_values,
        "scanned_jsonl_rows": scanned_jsonl_rows,
    }


def validate_rows(rows: list[dict[str, Any]], input_rows: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    if len(rows) != len(input_rows):
        issues.append("output_row_count_mismatch")
    required = [
        "preflight_id",
        "source_request_id",
        "stage12408_request_id",
        "source_family",
        "executor_kind",
        "request_readiness_status",
        "execution_attempt_status",
        "replay_outcome_status",
        "level3_status",
        "safe_result_schema_version",
        "requested_safe_return_schema_hash",
        "local_dataset_presence_status",
        "local_dataset_ref_hash",
        "local_parquet_file_count",
        "missing_mapping_fields",
        "proof_slot_statuses",
        "blockers",
        "raw_content_policy",
        "claim_boundary",
        "zero_admission_flags",
    ]
    for index, row in enumerate(rows, 1):
        for key in required:
            if key not in row:
                issues.append(f"row_{index}_missing_{key}")
        if row.get("safe_result_schema_version") != SAFE_RESULT_SCHEMA_VERSION:
            issues.append(f"row_{index}_safe_schema_version_mismatch")
        if row.get("replay_outcome_status") != "not_run":
            issues.append(f"row_{index}_replay_outcome_not_not_run")
        if row.get("level3_status") != "level3_still_blocked":
            issues.append(f"row_{index}_level3_status_not_blocked")
        if (
            row.get("source_family") == "open_swe"
            and row.get("missing_mapping_fields")
            and row.get("request_readiness_status") != "raw_unavailable"
        ):
            issues.append(f"row_{index}_open_swe_missing_mapping_not_raw_unavailable")
        if row.get("source_family") == "bears" and row.get("request_readiness_status") != "environment_blocked":
            issues.append(f"row_{index}_bears_not_environment_blocked")
        for key, expected in RAW_CONTENT_POLICY.items():
            if row.get("raw_content_policy", {}).get(key) is not expected:
                issues.append(f"row_{index}_raw_content_policy_{key}_mismatch")
        for key, expected in CLAIM_BOUNDARY.items():
            if row.get("claim_boundary", {}).get(key) != expected:
                issues.append(f"row_{index}_claim_boundary_{key}_mismatch")
        for key, expected in ZERO_ADMISSION_FLAGS.items():
            if row.get("zero_admission_flags", {}).get(key) != expected:
                issues.append(f"row_{index}_zero_admission_flags_{key}_mismatch")
        slots = row.get("proof_slot_statuses")
        if not isinstance(slots, dict):
            issues.append(f"row_{index}_proof_slot_statuses_not_object")
        else:
            for slot_name in PROOF_SLOT_NAMES:
                slot = slots.get(slot_name)
                if not isinstance(slot, dict):
                    issues.append(f"row_{index}_proof_slot_{slot_name}_missing")
                    continue
                if slot.get("proof_proven") is not False:
                    issues.append(f"row_{index}_proof_slot_{slot_name}_proven")
                if slot.get("proof_status") not in {"blocked", "unavailable", "indeterminate"}:
                    issues.append(f"row_{index}_proof_slot_{slot_name}_invalid_status")
    return issues


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    input_rows, input_issues = read_jsonl(INPUT_REQUESTS)
    input_summary = read_json(INPUT_SUMMARY)
    inventory = local_open_swe_inventory()

    rows = [build_row(row, index, inventory) for index, row in enumerate(input_rows, 1)]
    schema_issues = list(input_issues)
    schema_issues.extend(validate_rows(rows, input_rows))

    counts_by_family = Counter(str(row.get("source_family") or "unknown") for row in rows)
    readiness_counts = Counter(str(row.get("request_readiness_status") or "unknown") for row in rows)
    execution_attempted_count = sum(1 for row in rows if row.get("execution_attempt_status") not in {"not_attempted", "skipped_blocked"})

    manifest = {
        "stage": STAGE,
        "record_type": "open_swe_replay_executor_preflight_manifest",
        "input_request_bundle_hash": file_hash(INPUT_REQUESTS),
        "input_summary_hash": file_hash(INPUT_SUMMARY),
        "result_bundle_hash": stable_hash(rows),
        "safe_result_schema_version": SAFE_RESULT_SCHEMA_VERSION,
        "execution_policy": {
            "preflight_only": True,
            "executor_implemented": False,
            "replay_executed": False,
            "raw_parquet_rows_read": False,
            "raw_content_allowed": False,
            "fail_closed_if_uncertain": True,
        },
        "local_open_swe_dataset_inventory": inventory,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
    }

    result_path = OUT / RESULTS_NAME
    manifest_path = OUT / MANIFEST_NAME
    write_jsonl(result_path, rows)
    write_json(manifest_path, manifest)
    guardrail = guardrail_scan([result_path, manifest_path])
    write_json(OUT / GUARDRAIL_NAME, guardrail)

    guardrail_issues = list(guardrail["issues"])
    raw_leak_count = len(guardrail_issues)
    decision = (
        "fail_closed_open_swe_replay_executor_preflight_blocked"
        if schema_issues or guardrail_issues
        else "fail_closed_no_executable_replay_without_raw_mapping_or_environment_repair"
    )

    summary = {
        "stage": STAGE,
        "record_type": "open_swe_replay_executor_preflight_summary",
        "input_request_count": len(input_rows),
        "open_swe_request_count": counts_by_family.get("open_swe", 0),
        "bears_blocked_request_count": counts_by_family.get("bears", 0),
        "ready_request_count": int(input_summary.get("ready_to_execute_count") or 0),
        "execution_attempted_count": execution_attempted_count,
        "environment_blocked_count": readiness_counts.get("environment_blocked", 0),
        "raw_unavailable_count": readiness_counts.get("raw_unavailable", 0),
        "replay_succeeded_safe_status_count": 0,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "repair_claim_admitted": 0,
        "fail_to_pass_claim_admitted": 0,
        "training_allowed": False,
        "training_row_count": 0,
        "strict_eval_eligible": 0,
        "source_heldout_admissible": 0,
        "schema_issue_count": len(schema_issues),
        "schema_issues": schema_issues,
        "guardrail_issue_count": len(guardrail_issues),
        "guardrail_issues": guardrail_issues,
        "raw_leak_count": raw_leak_count,
        "decision": decision,
        "local_open_swe_dataset_inventory": inventory,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
    }
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()

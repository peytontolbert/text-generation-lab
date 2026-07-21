#!/usr/bin/env python3
"""Build Stage12408 replay calibration execution request bundle.

This stage selects the Stage12407 execute_replay_request work items and emits a
safe executor request manifest. It never executes replay and never emits raw
commands, outputs, paths, URLs, patches, source text, issue bodies, or line
contents.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12408_replay_calibration_execution_request"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

WORKLIST = (
    ROOT
    / "runs/local/artifacts/stage12407_prioritized_adapter_materialization_worklist/"
    "prioritized_adapter_materialization_worklist.jsonl"
)
WORKLIST_SUMMARY = ROOT / "runs/summaries/stage12407_prioritized_adapter_materialization_worklist.json"
OPEN_SWE_ITEMS = (
    ROOT
    / "runs/local/artifacts/stage12404_open_swe_replay_state_reconstruction_request/"
    "open_swe_replay_state_reconstruction_request_items.jsonl"
)
BEARS_REQUESTS = (
    ROOT
    / "runs/local/artifacts/stage12333_bears_hydration_request/bears_priority_hydration_requests.jsonl"
)
BEARS_BLOCKER_SUMMARY = ROOT / "runs/summaries/stage12336_bears_local_hydration_blocker_audit.json"

REQUESTS_NAME = "replay_calibration_execution_requests.jsonl"
MANIFEST_NAME = "replay_calibration_execution_request_manifest.json"
GUARDRAIL_NAME = "guardrail_scan.json"

TARGET_TIER = "replay_calibrated_supervision"
EXPECTED_REPLAY_REQUEST_COUNT = 7

SAFE_RETURN_FIELDS = [
    "executor_provenance_hash",
    "replay_attempt_status",
    "language_family",
    "repo_family_hash",
    "root_lineage_key_hash",
    "state_before_ref_hash",
    "chosen_action_ref_hash",
    "observation_ref_hash",
    "verifier_identity_hash",
    "verifier_output_class",
    "patch_application_status",
    "patch_ref_hash",
    "state_after_ref_hash",
    "stop_continue_status",
    "causal_linkage_status",
    "raw_content_policy",
    "replay_artifact_hashes",
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
}

CLAIM_BOUNDARY: dict[str, bool | str] = {
    "boundary": "request_only",
    "request_only": True,
    "replay_executed": False,
    "training_rows_created": False,
    "level3_claim": False,
}

ZERO_ADMISSION_FLAGS: dict[str, bool | int] = {
    "admission": False,
    "training_allowed": False,
    "training_row_count": 0,
    "eval_row_count": 0,
    "admitted_rows": 0,
    "replay_calibrated_rows": 0,
    "level3_admitted": 0,
    "patch_trace_admitted": 0,
    "strict_eval_eligible": 0,
    "source_heldout_admissible": 0,
}

BASE_BLOCKERS = [
    "blocked_request_only_no_replay_executed",
    "blocked_executor_must_return_safe_hash_class_status_only",
    "blocked_no_training_rows_created",
    "blocked_no_eval_rows_created",
    "blocked_no_level3_claim",
    "blocked_no_patch_trace_admission",
    "blocked_raw_content_not_emitted",
    "fail_closed_if_uncertain",
]

REQUIRED_EVIDENCE_TO_UPGRADE = [
    "executor_provenance_hash",
    "replay_attempt_status",
    "language_family",
    "repo_family_hash",
    "root_lineage_key_hash",
    "state_before_ref_hash",
    "chosen_action_ref_hash",
    "observation_ref_hash",
    "verifier_identity_hash",
    "verifier_output_class",
    "patch_application_status",
    "patch_ref_hash",
    "state_after_ref_hash",
    "stop_continue_status",
    "causal_linkage_status",
    "raw_content_policy_all_false",
    "replay_artifact_hashes",
]

ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
MULTILINE_RE = re.compile(r"[\r\n]")
HEX_RE = re.compile(r"^[0-9a-f]{12,64}$")


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
        return rows, [f"missing_input_{stable_hash(path.name, 12)}"]
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                issues.append(f"jsonl_line_{line_number}_invalid")
                continue
            if not isinstance(value, dict):
                issues.append(f"jsonl_line_{line_number}_not_object")
                continue
            rows.append(value)
    return rows, issues


def source_inventory() -> dict[str, Any]:
    open_swe_rows, open_swe_issues = read_jsonl(OPEN_SWE_ITEMS) if OPEN_SWE_ITEMS.exists() else ([], [])
    bears_rows, bears_issues = read_jsonl(BEARS_REQUESTS) if BEARS_REQUESTS.exists() else ([], [])
    return {
        "stage12404_open_swe": {
            "present": OPEN_SWE_ITEMS.exists(),
            "source_hash": file_hash(OPEN_SWE_ITEMS),
            "record_count": len(open_swe_rows),
            "schema_issue_count": len(open_swe_issues),
        },
        "stage12333_bears": {
            "present": BEARS_REQUESTS.exists(),
            "source_hash": file_hash(BEARS_REQUESTS),
            "record_count": len(bears_rows),
            "schema_issue_count": len(bears_issues),
        },
    }


def proof_slots() -> dict[str, dict[str, str]]:
    return {
        name: {
            "proof_status": "blocked",
            "evidence_class": "executor_evidence_required_not_available",
            "proof_ref_hash": "missing",
            "status_code": f"blocked_missing_{name}_proof",
        }
        for name in PROOF_SLOT_NAMES
    }


def executor_kind(source_family: str) -> str:
    if source_family == "open_swe":
        return "open_swe_replay_calibration"
    if source_family == "bears":
        return "bears_replay_hydration"
    return "unknown_replay_executor"


def bears_hydration_blocked(summary: dict[str, Any]) -> bool:
    decision = str(summary.get("decision") or "")
    blocked_reasons = summary.get("blocked_reasons")
    return "blocked" in decision or bool(blocked_reasons)


def build_request(row: dict[str, Any], index: int, bears_blocked: bool) -> dict[str, Any]:
    source_family = str(row.get("source_family") or "unknown")
    source_stage = str(row.get("source_stage") or "unknown")
    source_work_item_id = str(row.get("work_item_id") or f"missing_work_item_id_{index}")
    source_adapter_ref_hash = str(row.get("source_adapter_ref_hash") or "")
    status = "request_not_executed"
    request_status = "ready_to_execute"
    blockers = list(BASE_BLOCKERS)
    if source_family == "bears" and bears_blocked:
        request_status = "blocked_request_pending_hydration_repair"
        blockers.append("blocked_bears_submodule_or_local_hydration_unresolved")
    request_basis = {
        "stage": STAGE,
        "source_work_item_id": source_work_item_id,
        "source_adapter_ref_hash": source_adapter_ref_hash,
        "source_family": source_family,
    }
    return {
        "stage": STAGE,
        "record_type": "replay_calibration_execution_request",
        "request_id": f"{STAGE}::{stable_hash(request_basis, 20)}",
        "source_work_item_id": source_work_item_id,
        "source_family": source_family,
        "source_stage": source_stage,
        "source_adapter_ref_hash": source_adapter_ref_hash,
        "source_request_id": stable_hash({"source_work_item_id": source_work_item_id, "source_adapter_ref_hash": source_adapter_ref_hash}, 24),
        "request_rank": index,
        "current_proof_tier": str(row.get("current_proof_tier") or "unknown"),
        "target_next_proof_tier": TARGET_TIER,
        "execution_status": status,
        "executor_request_status": request_status,
        "executor_kind": executor_kind(source_family),
        "allowed_executor_action": "execute_replay_in_separate_stage",
        "required_executor_return_schema_version": "stage12408_safe_replay_return_v1",
        "requested_safe_return_schema": SAFE_RETURN_FIELDS,
        "input_artifact_hashes": {
            "stage12407_work_item_ref_hash": stable_hash(source_work_item_id, 24),
            "source_adapter_ref_hash": source_adapter_ref_hash,
        },
        "proof_slots": proof_slots(),
        "required_evidence_to_upgrade": REQUIRED_EVIDENCE_TO_UPGRADE,
        "blockers": sorted(set(blockers)),
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
        **ZERO_ADMISSION_FLAGS,
    }


def validate_request(row: dict[str, Any], index: int) -> list[str]:
    issues: list[str] = []
    required = [
        "request_id",
        "source_work_item_id",
        "source_family",
        "source_stage",
        "source_adapter_ref_hash",
        "source_request_id",
        "request_rank",
        "current_proof_tier",
        "target_next_proof_tier",
        "execution_status",
        "executor_kind",
        "allowed_executor_action",
        "required_executor_return_schema_version",
        "requested_safe_return_schema",
        "input_artifact_hashes",
        "proof_slots",
        "required_evidence_to_upgrade",
        "blockers",
        "raw_content_policy",
        "claim_boundary",
        "zero_admission_flags",
    ]
    for key in required:
        if key not in row:
            issues.append(f"request_{index}_missing_{key}")
    if row.get("target_next_proof_tier") != TARGET_TIER:
        issues.append(f"request_{index}_target_tier_mismatch")
    if row.get("execution_status") != "request_not_executed":
        issues.append(f"request_{index}_execution_status_not_request_not_executed")
    if row.get("executor_kind") not in {"open_swe_replay_calibration", "bears_replay_hydration"}:
        issues.append(f"request_{index}_executor_kind_invalid")
    if row.get("allowed_executor_action") != "execute_replay_in_separate_stage":
        issues.append(f"request_{index}_allowed_executor_action_mismatch")
    if row.get("required_executor_return_schema_version") != "stage12408_safe_replay_return_v1":
        issues.append(f"request_{index}_schema_version_mismatch")
    if row.get("requested_safe_return_schema") != SAFE_RETURN_FIELDS:
        issues.append(f"request_{index}_safe_return_schema_mismatch")
    if not isinstance(row.get("input_artifact_hashes"), dict):
        issues.append(f"request_{index}_input_artifact_hashes_missing")
    if not isinstance(row.get("source_adapter_ref_hash"), str) or not HEX_RE.match(row["source_adapter_ref_hash"]):
        issues.append(f"request_{index}_source_adapter_ref_hash_not_hash")
    slots = row.get("proof_slots")
    if not isinstance(slots, dict):
        issues.append(f"request_{index}_proof_slots_not_object")
    else:
        for slot_name in PROOF_SLOT_NAMES:
            slot = slots.get(slot_name)
            if not isinstance(slot, dict):
                issues.append(f"request_{index}_proof_slot_{slot_name}_missing")
                continue
            if slot.get("proof_status") != "blocked":
                issues.append(f"request_{index}_proof_slot_{slot_name}_not_blocked")
    for key, expected in RAW_CONTENT_POLICY.items():
        if row.get("raw_content_policy", {}).get(key) is not expected:
            issues.append(f"request_{index}_raw_content_policy_{key}_mismatch")
    for key, expected in CLAIM_BOUNDARY.items():
        if row.get("claim_boundary", {}).get(key) != expected:
            issues.append(f"request_{index}_claim_boundary_{key}_mismatch")
    for key, expected in ZERO_ADMISSION_FLAGS.items():
        if row.get("zero_admission_flags", {}).get(key) != expected:
            issues.append(f"request_{index}_zero_admission_flags_{key}_mismatch")
        if row.get(key) != expected:
            issues.append(f"request_{index}_{key}_not_false_or_zero")
    if row.get("source_family") == "bears" and row.get("executor_request_status") == "ready_to_execute":
        issues.append(f"request_{index}_bears_ready_despite_hydration_blocker")
    return issues


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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    work_items, input_issues = read_jsonl(WORKLIST)
    source_summary = read_json(WORKLIST_SUMMARY)
    bears_summary = read_json(BEARS_BLOCKER_SUMMARY)
    bears_blocked = bears_hydration_blocked(bears_summary)

    selected_source_items = [
        row
        for row in work_items
        if row.get("recommended_next_action") == "execute_replay_request"
        and row.get("target_next_proof_tier") == TARGET_TIER
    ]
    selected_source_items = sorted(
        selected_source_items,
        key=lambda row: (
            str(row.get("source_family") or ""),
            str(row.get("work_item_id") or ""),
        ),
    )
    requests = [build_request(row, index, bears_blocked) for index, row in enumerate(selected_source_items, 1)]

    schema_issues = list(input_issues)
    if len(requests) != EXPECTED_REPLAY_REQUEST_COUNT:
        schema_issues.append("selected_replay_request_count_not_7")
    if source_summary.get("counts_by_recommended_next_action", {}).get("execute_replay_request") not in {
        None,
        EXPECTED_REPLAY_REQUEST_COUNT,
    }:
        schema_issues.append("stage12407_summary_execute_replay_count_mismatch")
    for index, request in enumerate(requests, 1):
        schema_issues.extend(validate_request(request, index))

    counts_by_source_family = Counter(str(row["source_family"]) for row in requests)
    counts_by_executor_kind = Counter(str(row["executor_kind"]) for row in requests)
    target_counts = Counter(str(row["target_next_proof_tier"]) for row in requests)
    ready_to_execute_count = sum(1 for row in requests if row.get("executor_request_status") == "ready_to_execute")
    blocked_request_count = sum(
        1 for row in requests if row.get("executor_request_status") != "ready_to_execute"
    )

    manifest = {
        "stage": STAGE,
        "record_type": "replay_calibration_execution_request_manifest",
        "request_bundle_hash": stable_hash(requests),
        "selected_replay_request_count": len(requests),
        "execution_policy": {
            "request_only": True,
            "replay_executed": False,
            "training_allowed": False,
            "raw_content_allowed": False,
            "executor_return_must_match_safe_schema": True,
            "fail_closed_if_uncertain": True,
        },
        "source_inventory": source_inventory(),
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
        **ZERO_ADMISSION_FLAGS,
    }

    request_path = OUT / REQUESTS_NAME
    manifest_path = OUT / MANIFEST_NAME
    write_jsonl(request_path, requests)
    write_json(manifest_path, manifest)
    guardrail = guardrail_scan([request_path, manifest_path])
    write_json(OUT / GUARDRAIL_NAME, guardrail)

    guardrail_issues = list(guardrail["issues"])
    raw_leak_findings = guardrail_issues
    decision = (
        "fail_closed_replay_calibration_execution_request_ready_with_blocked_bears"
        if not schema_issues and not guardrail_issues and blocked_request_count
        else "fail_closed_replay_calibration_execution_request_ready"
        if not schema_issues and not guardrail_issues
        else "fail_closed_replay_calibration_execution_request_blocked"
    )

    summary = {
        "stage": STAGE,
        "decision": decision,
        "input_work_items": len(work_items),
        "selected_replay_request_count": len(requests),
        "counts_by_source_family": dict(sorted(counts_by_source_family.items())),
        "counts_by_executor_kind": dict(sorted(counts_by_executor_kind.items())),
        "ready_to_execute_count": ready_to_execute_count,
        "blocked_request_count": blocked_request_count,
        "target_next_proof_tier_counts": dict(sorted(target_counts.items())),
        "training_allowed": False,
        "training_row_count": 0,
        "admitted_rows": 0,
        "replay_calibrated_rows": 0,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "strict_eval_eligible": 0,
        "source_heldout_admissible": 0,
        "schema_issue_count": len(schema_issues),
        "schema_issues": schema_issues,
        "guardrail_issue_count": len(guardrail_issues),
        "guardrail_issues": guardrail_issues,
        "raw_leak_findings": raw_leak_findings,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
        "bears_hydration_blocked": bears_blocked,
        "source_inventory": manifest["source_inventory"],
        **ZERO_ADMISSION_FLAGS,
    }
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()

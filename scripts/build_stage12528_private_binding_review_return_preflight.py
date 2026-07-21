#!/usr/bin/env python3
"""Preflight private binding-review returns from Stage12527 queue items.

Stage12528 defines the exact public-safe private-review return schema for the
Stage12527 candidate binding-source queue. If a return file is absent, it emits
blockers/checklist rows and zero ready candidates. If a return file is present
under the Stage12527 artifact directory, it strictly validates hash/enum/status
returns and emits accepted/rejected public-safe status rows only.

It does not read raw candidate contents, write Stage12521 readiness manifests,
write executor returns, write Stage12516 candidates, write Stage12503 rows, or
emit training/admission/Level-3/patch-trace material.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12528_private_binding_review_return_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12527 = "stage12527_private_binding_review_queue"
RETURN_FILENAMES = [
    "private_binding_review_returns.jsonl",
    "private_review_returns.jsonl",
    "stage12528_private_binding_review_returns.jsonl",
]
RETURN_RECORD_TYPE = "stage12528_private_binding_review_return_v1"
ALLOWED_REVIEW_ACTIONS = {"trusted_binding", "authorized_return_writer", "reject", "blocked"}
READY_ACTIONS = {"trusted_binding", "authorized_return_writer"}
SLOT_COUNT = 343

REQUIRED_RETURN_FIELDS = [
    "record_type",
    "private_review_packet_id_hash",
    "candidate_binding_source_id_hash",
    "review_action",
    "private_reviewer_id_hash",
    "reviewer_conflict_check_hash",
    "reviewer_independence_attestation",
    "review_decision_reason_code",
    "acceptance_criteria_passed",
    "trusted_binding_confirmed",
    "authorized_return_writer_confirmed",
    "binding_authority_current",
    "scope_limited_to_stage12521_stage12516_stage12503_flow",
    "return_writer_destination_authorized",
    "maps_to_343_slot_context",
    "slot_context_gap_code",
    "no_training_admission_level3_patch_trace_requested",
    "raw_private_values_revealed",
    "raw_source_output_included",
    "raw_paths_included",
    "raw_commands_included",
    "raw_diffs_included",
    "raw_verifier_output_included",
    "candidate_file_contents_read_publicly",
    "stage12521_readiness_manifest_written",
    "stage12516_candidate_row_written",
    "stage12503_return_file_written",
    "training_allowed",
    "admission_allowed",
    "level3_atom_materialized",
    "patch_trace_materialized",
    "blocker_codes",
]

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output|verifier output|commit:)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)
SAFE_HASH_RE = re.compile(r"^[0-9a-f]{12,64}$")
SAFE_CODE_RE = re.compile(r"^[a-z0-9][a-z0-9_]{2,96}$")
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
    "candidate_name",
    "candidate_ref_hash",
    "source",
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
FALSE_GUARDS = {
    "readiness_fabricated": False,
    "stage12521_readiness_manifests_written": False,
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
    "raw_source_output_included": False,
    "raw_private_values_revealed": False,
    "candidate_file_contents_read": False,
    "candidate_raw_paths_emitted": False,
    "readiness_claimed": False,
}
ZERO_GUARDS = {
    "stage12521_readiness_manifest_count": 0,
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


class RawLeakError(ValueError):
    pass


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def is_safe_hash(value: Any) -> bool:
    return isinstance(value, str) and SAFE_HASH_RE.fullmatch(value) is not None and len(set(value.lower())) > 1


def is_safe_code(value: Any) -> bool:
    return isinstance(value, str) and SAFE_CODE_RE.fullmatch(value) is not None


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
        raise RawLeakError(f"stage12528 raw leak guard rejected {len(issues)} public field(s)")


def stage12527_dir(root: Path) -> Path:
    return root / "runs/local/artifacts" / STAGE12527


def prior_stage12527(root: Path) -> dict[str, Any]:
    artifacts = stage12527_dir(root)
    summaries = root / "runs/summaries"
    return {
        "summary": read_json(artifacts / "summary.json") or read_json(summaries / f"{STAGE12527}.json"),
        "queue": read_jsonl(artifacts / "private_review_queue.jsonl"),
        "criteria": read_json(artifacts / "review_criteria.json"),
    }


def preserved_slot_context(stage12527: dict[str, Any]) -> int:
    value = stage12527["summary"].get("preserved_slot_count_context")
    return value if isinstance(value, int) and value > 0 else SLOT_COUNT


def find_return_path(stage12527_out: Path) -> Path | None:
    for filename in RETURN_FILENAMES:
        path = stage12527_out / filename
        if path.exists():
            return path
    return None


def queue_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("private_review_packet_id_hash") or ""),
        str(row.get("candidate_binding_source_id_hash") or ""),
    )


def validate_return(row: dict[str, Any], queue_by_key: dict[tuple[str, str], dict[str, Any]], seen: Counter[tuple[str, str]]) -> list[str]:
    reasons: list[str] = []
    missing = [field for field in REQUIRED_RETURN_FIELDS if field not in row]
    reasons.extend(f"missing_{field}" for field in missing)
    extra = sorted(set(row) - set(REQUIRED_RETURN_FIELDS))
    if extra:
        reasons.append("extra_public_field_present")
    if row.get("record_type") != RETURN_RECORD_TYPE:
        reasons.append("schema_version_unsupported")

    key = queue_key(row)
    queue_row = queue_by_key.get(key)
    if queue_row is None:
        reasons.append("unknown_stage12527_queue_identity")
    elif row.get("candidate_binding_source_id_hash") != queue_row.get("candidate_binding_source_id_hash"):
        reasons.append("candidate_binding_source_id_hash_mismatch")
    if seen[key] > 1:
        reasons.append("duplicate_private_review_return_for_queue_item")

    action = row.get("review_action")
    if action not in ALLOWED_REVIEW_ACTIONS:
        reasons.append("unsupported_review_action")
    for field in ["private_review_packet_id_hash", "candidate_binding_source_id_hash", "private_reviewer_id_hash", "reviewer_conflict_check_hash"]:
        if not is_safe_hash(row.get(field)):
            reasons.append(f"{field}_missing_or_unsafe")
    if row.get("reviewer_independence_attestation") is not True:
        reasons.append("reviewer_independence_attestation_missing")
    if not is_safe_code(row.get("review_decision_reason_code")):
        reasons.append("review_decision_reason_code_missing_or_unsafe")
    if row.get("slot_context_gap_code") is not None and not is_safe_code(row.get("slot_context_gap_code")):
        reasons.append("slot_context_gap_code_unsafe")
    if not isinstance(row.get("blocker_codes"), list) or not all(is_safe_code(code) for code in row.get("blocker_codes", [])):
        reasons.append("blocker_codes_missing_or_unsafe")

    true_required = ["no_training_admission_level3_patch_trace_requested"]
    false_required = [
        "raw_private_values_revealed",
        "raw_source_output_included",
        "raw_paths_included",
        "raw_commands_included",
        "raw_diffs_included",
        "raw_verifier_output_included",
        "candidate_file_contents_read_publicly",
        "stage12521_readiness_manifest_written",
        "stage12516_candidate_row_written",
        "stage12503_return_file_written",
        "training_allowed",
        "admission_allowed",
        "level3_atom_materialized",
        "patch_trace_materialized",
    ]
    for field in true_required:
        if row.get(field) is not True:
            reasons.append(f"{field}_not_true")
    for field in false_required:
        if row.get(field) is not False:
            reasons.append(f"{field}_not_false")

    if action in READY_ACTIONS:
        if row.get("acceptance_criteria_passed") is not True:
            reasons.append("acceptance_criteria_passed_not_true_for_ready_review")
        if row.get("binding_authority_current") is not True:
            reasons.append("binding_authority_current_not_true_for_ready_review")
        if row.get("scope_limited_to_stage12521_stage12516_stage12503_flow") is not True:
            reasons.append("scope_limited_not_true_for_ready_review")
        if row.get("maps_to_343_slot_context") is not True:
            reasons.append("maps_to_343_slot_context_not_true_for_ready_review")
        if row.get("slot_context_gap_code") is not None:
            reasons.append("slot_context_gap_code_present_for_ready_review")
        if row.get("blocker_codes") != []:
            reasons.append("blocker_codes_present_for_ready_review")
        if action == "trusted_binding" and row.get("trusted_binding_confirmed") is not True:
            reasons.append("trusted_binding_confirmed_not_true")
        if action == "trusted_binding" and row.get("authorized_return_writer_confirmed") is not False:
            reasons.append("authorized_return_writer_confirmed_not_false_for_trusted_binding")
        if action == "authorized_return_writer" and row.get("authorized_return_writer_confirmed") is not True:
            reasons.append("authorized_return_writer_confirmed_not_true")
        if action == "authorized_return_writer" and row.get("trusted_binding_confirmed") is not False:
            reasons.append("trusted_binding_confirmed_not_false_for_authorized_return_writer")
        if action == "authorized_return_writer" and row.get("return_writer_destination_authorized") is not True:
            reasons.append("return_writer_destination_authorized_not_true")
    else:
        if row.get("acceptance_criteria_passed") is not False:
            reasons.append("acceptance_criteria_passed_not_false_for_non_ready_review")
        if row.get("trusted_binding_confirmed") is not False:
            reasons.append("trusted_binding_confirmed_not_false_for_non_ready_review")
        if row.get("authorized_return_writer_confirmed") is not False:
            reasons.append("authorized_return_writer_confirmed_not_false_for_non_ready_review")
        if row.get("blocker_codes") == [] and action == "blocked":
            reasons.append("blocker_codes_empty_for_blocked_review")

    if set(row) & FORBIDDEN_PUBLIC_KEYS or scan_raw_leaks(row):
        reasons.append("raw_leakage_detected")
    return sorted(set(reasons))


def return_schema_document() -> dict[str, Any]:
    schema = {
        "record_type": "stage12528_private_binding_review_return_schema_v1",
        "source_stage": STAGE12527,
        "return_input_filenames": RETURN_FILENAMES,
        "return_record_type": RETURN_RECORD_TYPE,
        "required_public_safe_return_fields": REQUIRED_RETURN_FIELDS,
        "allowed_review_actions": sorted(ALLOWED_REVIEW_ACTIONS),
        "ready_review_actions": sorted(READY_ACTIONS),
        "action_requirements": {
            "trusted_binding": [
                "acceptance_criteria_passed_true",
                "trusted_binding_confirmed_true",
                "authorized_return_writer_confirmed_false",
                "binding_authority_current_true",
                "scope_limited_to_stage12521_stage12516_stage12503_flow_true",
                "maps_to_343_slot_context_true",
                "slot_context_gap_code_null",
                "blocker_codes_empty",
            ],
            "authorized_return_writer": [
                "acceptance_criteria_passed_true",
                "trusted_binding_confirmed_false",
                "authorized_return_writer_confirmed_true",
                "binding_authority_current_true",
                "return_writer_destination_authorized_true",
                "scope_limited_to_stage12521_stage12516_stage12503_flow_true",
                "maps_to_343_slot_context_true",
                "slot_context_gap_code_null",
                "blocker_codes_empty",
            ],
            "reject": [
                "acceptance_criteria_passed_false",
                "trusted_binding_confirmed_false",
                "authorized_return_writer_confirmed_false",
                "review_decision_reason_code_safe_enum_required",
            ],
            "blocked": [
                "acceptance_criteria_passed_false",
                "trusted_binding_confirmed_false",
                "authorized_return_writer_confirmed_false",
                "blocker_codes_non_empty_safe_enums_required",
                "slot_context_gap_code_required_when_maps_to_343_slot_context_false",
            ],
        },
        "global_must_be_true_fields": ["reviewer_independence_attestation", "no_training_admission_level3_patch_trace_requested"],
        "global_must_be_false_fields": [
            "raw_private_values_revealed",
            "raw_source_output_included",
            "raw_paths_included",
            "raw_commands_included",
            "raw_diffs_included",
            "raw_verifier_output_included",
            "candidate_file_contents_read_publicly",
            "stage12521_readiness_manifest_written",
            "stage12516_candidate_row_written",
            "stage12503_return_file_written",
            "training_allowed",
            "admission_allowed",
            "level3_atom_materialized",
            "patch_trace_materialized",
        ],
        "public_artifact_policy": "hash_enum_boolean_status_only_no_raw_candidate_contents_paths_commands_diffs_outputs_or_credentials",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "public_safe_metadata_only": True,
    }
    enforce_no_raw_leaks(schema)
    return schema


def accepted_status(row: dict[str, Any]) -> dict[str, Any]:
    status = {
        "record_type": "stage12528_accepted_private_binding_review_status_v1",
        "accepted_private_review_status_id_hash": stable_hash(
            {
                "private_review_packet_id_hash": row.get("private_review_packet_id_hash"),
                "candidate_binding_source_id_hash": row.get("candidate_binding_source_id_hash"),
                "review_action": row.get("review_action"),
            }
        ),
        "private_review_packet_id_hash": row.get("private_review_packet_id_hash"),
        "candidate_binding_source_id_hash": row.get("candidate_binding_source_id_hash"),
        "review_action": row.get("review_action"),
        "public_safe_status": "ready_review" if row.get("review_action") in READY_ACTIONS else row.get("review_action"),
        "review_decision_reason_code": row.get("review_decision_reason_code"),
        "trusted_binding_confirmed": row.get("trusted_binding_confirmed"),
        "authorized_return_writer_confirmed": row.get("authorized_return_writer_confirmed"),
        "maps_to_343_slot_context": row.get("maps_to_343_slot_context"),
        "slot_context_gap_code": row.get("slot_context_gap_code"),
        "blocker_codes": row.get("blocker_codes"),
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks(status)
    return status


def rejected_status(row: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    rejected = {
        "record_type": "stage12528_rejected_private_binding_review_return_v1",
        "rejected_private_review_return_id_hash": stable_hash(
            {
                "private_review_packet_id_hash": row.get("private_review_packet_id_hash"),
                "candidate_binding_source_id_hash": row.get("candidate_binding_source_id_hash"),
                "record_type": row.get("record_type"),
                "reasons": reasons,
            }
        ),
        "private_review_packet_id_hash": row.get("private_review_packet_id_hash"),
        "candidate_binding_source_id_hash": row.get("candidate_binding_source_id_hash"),
        "review_action": row.get("review_action"),
        "rejection_codes": reasons,
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks(rejected)
    return rejected


def blocker_rows(queue: list[dict[str, Any]], accepted_keys: set[tuple[str, str]], return_file_present: bool) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for queue_row in queue:
        key = queue_key(queue_row)
        if key in accepted_keys:
            continue
        code = "private_binding_review_return_absent" if not return_file_present else "private_binding_review_return_missing_or_rejected"
        row = {
            "record_type": "stage12528_private_binding_review_return_blocker_v1",
            "blocker_id_hash": stable_hash({"queue": key, "return_file_present": return_file_present}),
            "private_review_packet_id_hash": queue_row.get("private_review_packet_id_hash"),
            "candidate_binding_source_id_hash": queue_row.get("candidate_binding_source_id_hash"),
            "candidate_class": queue_row.get("candidate_class"),
            "review_band": queue_row.get("review_band"),
            "preserved_slot_count_context": queue_row.get("preserved_slot_count_context", SLOT_COUNT),
            "blocker_codes": [
                code,
                "private_reviewer_return_required_before_stage12521_readiness",
                "stage12528_writes_status_only_no_stage12521_manifest",
            ],
            "required_return_schema_ref": "private_binding_review_return_schema.json",
            "public_safe_status_only": True,
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        enforce_no_raw_leaks(row)
        blockers.append(row)
    return blockers


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    stage12527 = prior_stage12527(root)
    queue = stage12527["queue"]
    queue_by_key = {queue_key(row): row for row in queue}
    return_path = find_return_path(stage12527_dir(root))
    returns = read_jsonl(return_path) if return_path else []
    seen = Counter(queue_key(row) for row in returns)

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    accepted_keys: set[tuple[str, str]] = set()
    for row in returns:
        reasons = validate_return(row, queue_by_key, seen)
        key = queue_key(row)
        if key in accepted_keys:
            reasons.append("duplicate_accepted_private_review_return_for_queue_item")
            reasons = sorted(set(reasons))
        if reasons:
            rejected.append(rejected_status(row, reasons))
            continue
        accepted.append(accepted_status(row))
        accepted_keys.add(key)

    blockers = blocker_rows(queue, accepted_keys, return_path is not None)
    schema = return_schema_document()
    action_counts = Counter(row["review_action"] for row in accepted)
    rejected_code_counts: Counter[str] = Counter()
    blocker_code_counts: Counter[str] = Counter()
    for row in rejected:
        rejected_code_counts.update(row["rejection_codes"])
    for row in blockers:
        blocker_code_counts.update(row["blocker_codes"])

    ready_review_count = sum(1 for row in accepted if row["review_action"] in READY_ACTIONS)
    decision = (
        "blocked_no_private_binding_review_return_file"
        if return_path is None
        else "private_binding_review_returns_validated_status_only_no_manifests"
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12528_private_binding_review_return_preflight_summary_v1",
        "decision": decision,
        "claim_boundary": (
            "Stage12528 validates public-safe private-review return statuses for Stage12527 "
            "queue items. Ready-review statuses are review outcomes only and do not write or "
            "authorize Stage12521 manifests, executor returns, Stage12516 candidates, Stage12503 "
            "rows, training/admission material, Level-3 atoms, or patch-trace material."
        ),
        "source_stage": STAGE12527,
        "stage12527_private_review_queue_count": len(queue),
        "preserved_slot_count_context": preserved_slot_context(stage12527),
        "return_file_present": return_path is not None,
        "return_input_filenames": RETURN_FILENAMES,
        "return_record_count": len(returns),
        "accepted_private_review_status_count": len(accepted),
        "rejected_private_review_return_count": len(rejected),
        "blocked_private_review_queue_item_count": len(blockers),
        "ready_review_status_count": ready_review_count,
        "ready_candidate_count": 0,
        "accepted_review_action_counts": dict(sorted(action_counts.items())),
        "rejection_code_counts": dict(sorted(rejected_code_counts.items())),
        "blocker_code_counts": dict(sorted(blocker_code_counts.items())),
        "return_schema_ref": "private_binding_review_return_schema.json",
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        "next_stage": (
            "private_reviewer_must_supply_stage12528_return_file"
            if return_path is None
            else "manual_status_review_only_no_stage12521_readiness_yet"
        ),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    guardrail = {
        "stage": STAGE,
        "scan_passed": True,
        "raw_leak_count": 0,
        "raw_leak_issue_hashes": [],
        "scanned_outputs": [
            "accepted_private_binding_review_statuses.jsonl",
            "rejected_private_binding_review_returns.jsonl",
            "private_binding_review_return_blockers.jsonl",
            "private_binding_review_return_schema.json",
            "summary.json",
        ],
    }
    outputs = {"accepted": accepted, "rejected": rejected, "blockers": blockers, "schema": schema, "summary": summary, "guardrail": guardrail}
    enforce_no_raw_leaks(outputs)

    write_jsonl(out / "accepted_private_binding_review_statuses.jsonl", accepted)
    write_jsonl(out / "rejected_private_binding_review_returns.jsonl", rejected)
    write_jsonl(out / "private_binding_review_return_blockers.jsonl", blockers)
    write_json(out / "private_binding_review_return_schema.json", schema)
    write_json(out / "guardrail_scan.json", guardrail)
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()

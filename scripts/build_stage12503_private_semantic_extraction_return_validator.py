#!/usr/bin/env python3
"""Validate authoritative private semantic extraction returns.

Stage12503 consumes Stage12502 private semantic extraction requests and an
optional externally produced return file. It is fail-closed: absent or invalid
returns produce blockers only. Accepted returns are sanitized extraction-status
records, not policy labels, Level-3 atoms, patch traces, or training rows.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12503_private_semantic_extraction_return_validator"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12502 = "stage12502_authoritative_private_semantic_extraction_request_preflight"
STAGE12502_OUT = ROOT / "runs/local/artifacts" / STAGE12502
STAGE12502_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12502}.json"
REQUESTS = STAGE12502_OUT / "private_semantic_extraction_requests.jsonl"
RETURN_FILE = STAGE12502_OUT / "private_semantic_extraction_returns.jsonl"

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
}
ZERO_GUARDS = {
    "training_rows_emitted": 0,
    "admitted_rows": 0,
    "level3_admitted": 0,
    "level3_atom_count": 0,
    "patch_trace_admitted": 0,
    "patch_trace_rows": 0,
    "stage12496_return_records_written": 0,
    "policy_labels_emitted": 0,
    "proof_rows_emitted": 0,
    "proof_grade_repair_rows": 0,
    "external_repair_credit_count": 0,
    "sealed_eval_rows": 0,
}

REQUIRED_RETURN_FIELDS = [
    "record_type",
    "request_id_hash",
    "audit_item_id_hash",
    "work_item_id_hash",
    "packet_id_hash",
    "root_or_window_hash",
    "source_stage",
    "source_kind",
    "task_family",
    "language_family",
    "extractor_id_hash",
    "extractor_authority_attestation",
    "extractor_conflict_check_hash",
    "requested_private_extraction_slots",
    "extracted_slot_statuses",
    "extracted_slot_proof_hashes",
    "source_locator_hash",
    "causal_review_hash",
    "raw_private_values_revealed",
    "raw_source_output_included",
    "local_model_authority",
    "policy_label_emitted",
    "acceptance_criteria_passed",
    "blocker_codes",
    "training_allowed",
    "admission_allowed",
    "training_rows_emitted",
    "admitted_rows",
]
IDENTITY_FIELDS = [
    "audit_item_id_hash",
    "work_item_id_hash",
    "packet_id_hash",
    "root_or_window_hash",
    "source_stage",
    "source_kind",
    "task_family",
    "language_family",
]
FORBIDDEN_RETURN_FIELDS = {
    "raw_output",
    "raw_outputs",
    "raw_diff",
    "diff",
    "command",
    "commands",
    "path",
    "paths",
    "source_text",
    "verifier_output",
    "stdout",
    "stderr",
    "policy_label",
    "policy_label_hash",
    "independent_policy_label_hash",
    "training_row",
    "training_rows",
    "admitted_row",
    "level3_atom",
    "patch_trace",
}
ALLOWED_SLOT_STATUSES = {
    "validated_present",
    "validated_absent",
    "blocked_unavailable",
    "not_applicable",
}
ALLOWED_PATCH_APPLY_STATUS = {
    "applies",
    "does_not_apply",
    "not_applicable",
    "unknown",
}
ALLOWED_STOP_CONTINUE_STATUS = {
    "continue",
    "stop",
    "not_applicable",
    "unknown",
}
SAFE_HASH_RE = re.compile(r"^[0-9a-f]{12,64}$")


def is_safe_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(SAFE_HASH_RE.fullmatch(value))


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


def validate_return(row: dict[str, Any], request: dict[str, Any] | None) -> list[str]:
    reasons: list[str] = []
    if not row.get("request_id_hash"):
        reasons.append("missing_request_id_hash")
    if request is None:
        reasons.append("unknown_request_id_hash")
        return sorted(set(reasons))
    for field in REQUIRED_RETURN_FIELDS:
        if field not in row:
            reasons.append(f"missing_{field}")
    if row.get("record_type") != "stage12503_authoritative_private_semantic_extraction_return_v1":
        reasons.append("schema_version_unsupported")
    for field in IDENTITY_FIELDS:
        if row.get(field) != request.get(field):
            reasons.append(f"{field}_mismatch")
    if set(row.keys()) & FORBIDDEN_RETURN_FIELDS:
        reasons.append("forbidden_raw_or_label_field_present")
    requested_slots = sorted(request.get("requested_private_extraction_slots") or [])
    if sorted(row.get("requested_private_extraction_slots") or []) != requested_slots:
        reasons.append("requested_private_extraction_slots_mismatch")
    statuses = row.get("extracted_slot_statuses")
    if not isinstance(statuses, dict):
        reasons.append("extracted_slot_statuses_not_object")
        statuses = {}
    if sorted(statuses) != requested_slots:
        reasons.append("extracted_slot_status_keys_mismatch")
    for slot, status in statuses.items():
        if status not in ALLOWED_SLOT_STATUSES:
            reasons.append(f"unsupported_slot_status_{slot}")
    proof_hashes = row.get("extracted_slot_proof_hashes")
    if not isinstance(proof_hashes, dict):
        reasons.append("extracted_slot_proof_hashes_not_object")
        proof_hashes = {}
    if sorted(proof_hashes) != requested_slots:
        reasons.append("extracted_slot_proof_hash_keys_mismatch")
    for slot, status in statuses.items():
        proof_hash = proof_hashes.get(slot)
        if status == "validated_present" and not is_safe_hash(proof_hash):
            reasons.append(f"missing_validated_present_proof_hash_{slot}")
    if not is_safe_hash(row.get("source_locator_hash")):
        reasons.append("source_locator_hash_missing")
    if not is_safe_hash(row.get("causal_review_hash")):
        reasons.append("causal_review_hash_missing")
    if row.get("patch_apply_status_enum", "not_applicable") not in ALLOWED_PATCH_APPLY_STATUS:
        reasons.append("unsupported_patch_apply_status_enum")
    if row.get("stop_continue_status_enum", "not_applicable") not in ALLOWED_STOP_CONTINUE_STATUS:
        reasons.append("unsupported_stop_continue_status_enum")
    if row.get("extractor_authority_attestation") is not True:
        reasons.append("extractor_authority_attestation_missing")
    if not row.get("extractor_id_hash"):
        reasons.append("extractor_id_hash_missing")
    if not row.get("extractor_conflict_check_hash"):
        reasons.append("extractor_conflict_check_hash_missing")
    if row.get("raw_private_values_revealed") is not False:
        reasons.append("raw_private_values_revealed")
    if row.get("raw_source_output_included") is not False:
        reasons.append("raw_source_output_included")
    if row.get("local_model_authority") is not False:
        reasons.append("local_model_authority_claimed")
    if row.get("policy_label_emitted") is not False:
        reasons.append("policy_label_emitted")
    if row.get("acceptance_criteria_passed") is not True:
        reasons.append("acceptance_criteria_failed")
    if row.get("blocker_codes") not in ([], None):
        reasons.append("return_blocker_codes_not_empty")
    if row.get("training_allowed") is not False or row.get("admission_allowed") is not False:
        reasons.append("training_or_admission_requested")
    if row.get("training_rows_emitted") != 0 or row.get("admitted_rows") != 0:
        reasons.append("nonzero_training_or_admission_rows_requested")
    if scan_raw_leaks(row):
        reasons.append("raw_leakage_detected")
    return sorted(set(reasons))


def accepted_record(row: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "stage12503_validated_private_semantic_extraction_status_v1",
        "validated_extraction_id_hash": stable_hash({"request": request.get("request_id_hash"), "return": row}),
        "request_id_hash": request.get("request_id_hash"),
        "audit_item_id_hash": request.get("audit_item_id_hash"),
        "work_item_id_hash": request.get("work_item_id_hash"),
        "packet_id_hash": request.get("packet_id_hash"),
        "root_or_window_hash": request.get("root_or_window_hash"),
        "source_stage": request.get("source_stage"),
        "source_kind": request.get("source_kind"),
        "task_family": request.get("task_family"),
        "language_family": request.get("language_family"),
        "requested_private_extraction_slots": request.get("requested_private_extraction_slots"),
        "extracted_slot_statuses": row.get("extracted_slot_statuses"),
        "extracted_slot_proof_hashes": row.get("extracted_slot_proof_hashes"),
        "source_locator_hash": row.get("source_locator_hash"),
        "causal_review_hash": row.get("causal_review_hash"),
        "patch_apply_status_enum": row.get("patch_apply_status_enum", "not_applicable"),
        "stop_continue_status_enum": row.get("stop_continue_status_enum", "not_applicable"),
        "authoritative_extraction_return_validated": True,
        "raw_private_values_revealed": False,
        "public_safe_status_only": True,
        "claim_boundary": (
            "Validated private semantic extraction status only. This is not a policy label, "
            "Level-3 admission, patch trace, proof-grade repair row, or training authorization."
        ),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "validated_private_semantic_extraction_returns": 1,
    }


def rejected_record(row: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    return {
        "record_type": "stage12503_rejected_private_semantic_extraction_return_v1",
        "rejected_return_id_hash": stable_hash({"request": row.get("request_id_hash"), "reasons": reasons}),
        "request_id_hash": row.get("request_id_hash"),
        "audit_item_id_hash": row.get("audit_item_id_hash"),
        "work_item_id_hash": row.get("work_item_id_hash"),
        "packet_id_hash": row.get("packet_id_hash"),
        "root_or_window_hash": row.get("root_or_window_hash"),
        "source_stage": row.get("source_stage"),
        "source_kind": row.get("source_kind"),
        "task_family": row.get("task_family"),
        "language_family": row.get("language_family"),
        "rejection_codes": reasons,
        "public_safe_status_only": True,
        "raw_private_values_revealed": False,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def blocker_record(request: dict[str, Any], return_seen: bool) -> dict[str, Any]:
    blockers = [
        "authoritative_private_semantic_extraction_return_absent"
        if not return_seen
        else "authoritative_private_semantic_extraction_return_not_validated",
        "honest_ingest_requires_valid_authoritative_return_record",
        "do_not_materialize_labels_or_proofs_from_stage12502_request",
    ]
    return {
        "record_type": "stage12503_private_semantic_extraction_ingest_blocker_v1",
        "blocker_id_hash": stable_hash({"request": request.get("request_id_hash"), "return_seen": return_seen}),
        "request_id_hash": request.get("request_id_hash"),
        "audit_item_id_hash": request.get("audit_item_id_hash"),
        "work_item_id_hash": request.get("work_item_id_hash"),
        "packet_id_hash": request.get("packet_id_hash"),
        "root_or_window_hash": request.get("root_or_window_hash"),
        "source_stage": request.get("source_stage"),
        "source_kind": request.get("source_kind"),
        "task_family": request.get("task_family"),
        "language_family": request.get("language_family"),
        "requested_private_extraction_slots": request.get("requested_private_extraction_slots"),
        "ingest_decision": "blocked",
        "blocker_codes": blockers,
        "public_safe_status_only": True,
        "raw_private_values_revealed": False,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12502_summary = read_json(STAGE12502_SUMMARY)
    requests = read_jsonl(REQUESTS)
    returns = read_jsonl(RETURN_FILE)
    request_by_id = {row.get("request_id_hash"): row for row in requests}

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    rejected_request_ids: set[str] = set()
    for row in returns:
        request = request_by_id.get(row.get("request_id_hash"))
        reasons = validate_return(row, request)
        if reasons:
            rejected.append(rejected_record(row, reasons))
            if row.get("request_id_hash") in request_by_id:
                rejected_request_ids.add(str(row.get("request_id_hash")))
            continue
        accepted.append(accepted_record(row, request_by_id[str(row["request_id_hash"])]))

    accepted_request_ids = {str(row["request_id_hash"]) for row in accepted}
    blocked = [
        blocker_record(request, str(request.get("request_id_hash")) in rejected_request_ids)
        for request in requests
        if str(request.get("request_id_hash")) not in accepted_request_ids
    ]

    blocker_counts: Counter[str] = Counter()
    rejected_counts: Counter[str] = Counter()
    language_counts = Counter(row.get("language_family") for row in requests)
    task_counts = Counter(row.get("task_family") for row in requests)
    for row in blocked:
        blocker_counts.update(row["blocker_codes"])
    for row in rejected:
        rejected_counts.update(row["rejection_codes"])

    outputs = {
        "accepted": accepted,
        "rejected": rejected,
        "blocked": blocked,
    }
    leak_issues = scan_raw_leaks(outputs)
    guardrail = {
        "stage": STAGE,
        "scan_passed": not leak_issues,
        "raw_leak_count": len(leak_issues),
        "raw_leak_issue_hashes": leak_issues[:40],
        "scanned_outputs": [
            "validated_private_semantic_extraction_status.jsonl",
            "rejected_private_semantic_extraction_returns.jsonl",
            "private_semantic_extraction_ingest_blockers.jsonl",
        ],
    }

    decision = (
        "validated_private_semantic_extraction_returns_ingested_training_and_admission_blocked"
        if accepted
        else "blocked_no_valid_authoritative_private_semantic_extraction_returns"
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12503_private_semantic_extraction_return_validator_summary_v1",
        "decision": decision,
        "claim_boundary": (
            "Stage12503 validates authoritative private semantic extraction returns for Stage12502 "
            "requests. It never fabricates proof hashes, raw outputs, diffs, commands, paths, labels, "
            "Level-3 atoms, patch traces, or training rows."
        ),
        "source_stage": STAGE12502,
        "stage12502_decision": stage12502_summary.get("decision"),
        "input_request_count": len(requests),
        "return_file_present": RETURN_FILE.exists(),
        "return_record_count": len(returns),
        "validated_private_semantic_extraction_return_count": len(accepted),
        "rejected_private_semantic_extraction_return_count": len(rejected),
        "blocked_request_count": len(blocked),
        "language_counts": dict(sorted(language_counts.items())),
        "task_family_counts": dict(sorted(task_counts.items())),
        "blocker_code_counts": dict(sorted(blocker_counts.items())),
        "rejection_code_counts": dict(sorted(rejected_counts.items())),
        "raw_leak_count": guardrail["raw_leak_count"],
        "guardrail_scan_passed": guardrail["scan_passed"],
        "public_artifact_policy": "hash_enum_status_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        "next_stage": (
            "closed_loop_slot_update_from_validated_private_extraction_status"
            if accepted
            else "authoritative_private_semantic_extraction_return_acquisition"
        ),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }

    write_jsonl(OUT / "validated_private_semantic_extraction_status.jsonl", accepted)
    write_jsonl(OUT / "rejected_private_semantic_extraction_returns.jsonl", rejected)
    write_jsonl(OUT / "private_semantic_extraction_ingest_blockers.jsonl", blocked)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()

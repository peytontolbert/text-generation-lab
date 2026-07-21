#!/usr/bin/env python3
"""Apply validated private semantic extraction status to closed-loop proof slots.

Stage12504 consumes Stage12503's already validated, public-safe extraction
status records. It updates only hash-backed proof-slot status. It does not
create policy labels, Level-3 atoms, patch traces, proof-grade repair rows, or
training/admission rows.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12504_closed_loop_slot_update_from_validated_private_extraction_status"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12500_OUT = ROOT / "runs/local/artifacts/stage12500_closed_loop_candidate_packet_router"
PACKETS = STAGE12500_OUT / "closed_loop_candidate_packets.jsonl"
WORKLIST = STAGE12500_OUT / "closed_loop_materialization_worklist.jsonl"

STAGE12503 = "stage12503_private_semantic_extraction_return_validator"
STAGE12503_OUT = ROOT / "runs/local/artifacts" / STAGE12503
STAGE12503_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12503}.json"
VALIDATED = STAGE12503_OUT / "validated_private_semantic_extraction_status.jsonl"
INGEST_BLOCKERS = STAGE12503_OUT / "private_semantic_extraction_ingest_blockers.jsonl"

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
    "event_local_promoted": False,
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

SLOT_TO_PROOF = {
    "state_before_summary_codes_present": "authoritative_state_before",
    "state_delta_codes_present": "state_delta_or_state_after",
    "same_source_lineage_proof_present": "same_source_causal_lineage",
    "patch_apply_status_present": "patch_apply_status",
    "stop_continue_label_present": "stop_continue",
}
NON_REQUESTABLE_LEVEL3_BLOCKERS = {
    "chosen_action_policy_label_present": "independent_policy_label_missing",
    "external_patch_effect_proof_present": "external_patch_effect_proof_missing",
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


def slot_updates(status: dict[str, Any]) -> dict[str, dict[str, Any]]:
    statuses = status.get("extracted_slot_statuses") or {}
    proof_hashes = status.get("extracted_slot_proof_hashes") or {}
    updates: dict[str, dict[str, Any]] = {}
    for slot, extracted_status in sorted(statuses.items()):
        proof_slot = SLOT_TO_PROOF.get(slot)
        if proof_slot is None:
            continue
        updates[proof_slot] = {
            "source_private_extraction_slot": slot,
            "validated_present": extracted_status == "validated_present",
            "extraction_status": extracted_status,
            "proof_hash": proof_hashes.get(slot) if extracted_status == "validated_present" else None,
        }
    return updates


def residual_blockers(work: dict[str, Any], updates: dict[str, dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    proven_source_slots = {
        update["source_private_extraction_slot"]
        for update in updates.values()
        if update["validated_present"]
    }
    for slot in sorted(set(work.get("required_materialization") or [])):
        if slot in proven_source_slots:
            continue
        if slot in NON_REQUESTABLE_LEVEL3_BLOCKERS:
            blockers.append(NON_REQUESTABLE_LEVEL3_BLOCKERS[slot])
        elif slot.endswith("_required"):
            blockers.append(slot)
        else:
            blockers.append(f"{slot}_unproven")
    blockers.extend(
        [
            "stage12504_does_not_materialize_policy_labels",
            "stage12504_does_not_admit_level3_or_patch_trace",
        ]
    )
    return sorted(set(blockers))


def update_record(
    status: dict[str, Any],
    work: dict[str, Any] | None,
    packet: dict[str, Any] | None,
) -> dict[str, Any]:
    updates = slot_updates(status)
    blockers = residual_blockers(work or {}, updates)
    return {
        "record_type": "stage12504_closed_loop_proof_slot_update_v1",
        "slot_update_id_hash": stable_hash(
            {"validated": status.get("validated_extraction_id_hash"), "updates": updates}
        ),
        "validated_extraction_id_hash": status.get("validated_extraction_id_hash"),
        "request_id_hash": status.get("request_id_hash"),
        "audit_item_id_hash": status.get("audit_item_id_hash"),
        "work_item_id_hash": status.get("work_item_id_hash"),
        "packet_id_hash": status.get("packet_id_hash"),
        "root_or_window_hash": status.get("root_or_window_hash"),
        "source_stage": status.get("source_stage"),
        "source_kind": status.get("source_kind"),
        "task_family": status.get("task_family"),
        "language_family": status.get("language_family"),
        "slot_update_decision": "authoritative_status_applied" if updates else "no_supported_slot_update",
        "authoritative_extraction_return_validated": True,
        "source_locator_hash": status.get("source_locator_hash"),
        "causal_review_hash": status.get("causal_review_hash"),
        "proof_slot_updates": updates,
        "updated_proof_slot_count": sum(1 for update in updates.values() if update["validated_present"]),
        "original_missing_proof_slots": sorted(set((work or {}).get("required_materialization") or [])),
        "packet_closed_loop_slot_status_seen": (packet or {}).get("closed_loop_slot_status") or {},
        "level3_complete_after_update": False,
        "patch_trace_candidate_after_update": False,
        "residual_blocker_codes": blockers,
        "claim_boundary": (
            "Hash-backed private semantic status applied to proof-slot coverage only. "
            "No policy label, Level-3 atom, patch trace, proof-grade repair row, or training row is emitted."
        ),
        "raw_private_values_revealed": False,
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def blocker_from_stage12503(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "stage12504_authoritative_proof_slot_update_blocker_v1",
        "blocker_id_hash": stable_hash({"request": row.get("request_id_hash"), "stage12503": row.get("blocker_codes")}),
        "request_id_hash": row.get("request_id_hash"),
        "audit_item_id_hash": row.get("audit_item_id_hash"),
        "work_item_id_hash": row.get("work_item_id_hash"),
        "packet_id_hash": row.get("packet_id_hash"),
        "root_or_window_hash": row.get("root_or_window_hash"),
        "source_stage": row.get("source_stage"),
        "source_kind": row.get("source_kind"),
        "task_family": row.get("task_family"),
        "language_family": row.get("language_family"),
        "slot_update_decision": "blocked_no_validated_private_extraction_status",
        "blocker_codes": sorted(
            set(row.get("blocker_codes") or [])
            | {
                "stage12504_requires_stage12503_validated_private_semantic_extraction_status",
                "no_slot_update_without_authoritative_proof_hash",
            }
        ),
        "public_safe_status_only": True,
        "raw_private_values_revealed": False,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12503_summary = read_json(STAGE12503_SUMMARY)
    packets = {row.get("packet_id_hash"): row for row in read_jsonl(PACKETS)}
    worklist = {row.get("work_item_id_hash"): row for row in read_jsonl(WORKLIST)}
    validated = read_jsonl(VALIDATED)
    upstream_blockers = read_jsonl(INGEST_BLOCKERS)

    updates = [
        update_record(
            status,
            worklist.get(status.get("work_item_id_hash")),
            packets.get(status.get("packet_id_hash")),
        )
        for status in validated
    ]
    blockers = [blocker_from_stage12503(row) for row in upstream_blockers]

    slot_counts: Counter[str] = Counter()
    residual_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    task_counts: Counter[str] = Counter()
    for row in updates:
        language_counts[row["language_family"]] += 1
        task_counts[row["task_family"]] += 1
        for proof_slot, update in row["proof_slot_updates"].items():
            if update["validated_present"]:
                slot_counts[proof_slot] += 1
        residual_counts.update(row["residual_blocker_codes"])
    for row in blockers:
        residual_counts.update(row["blocker_codes"])

    outputs = {"updates": updates, "blockers": blockers}
    leak_issues = scan_raw_leaks(outputs)
    guardrail = {
        "stage": STAGE,
        "scan_passed": not leak_issues,
        "raw_leak_count": len(leak_issues),
        "raw_leak_issue_hashes": leak_issues[:40],
        "scanned_outputs": [
            "closed_loop_proof_slot_update_ledger.jsonl",
            "authoritative_proof_slot_update_blockers.jsonl",
        ],
    }

    decision = (
        "authoritative_private_semantic_slot_updates_ingested_level3_admission_blocked"
        if updates
        else "blocked_no_validated_private_semantic_extraction_status_to_apply"
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12504_closed_loop_slot_update_summary_v1",
        "decision": decision,
        "claim_boundary": (
            "Stage12504 applies Stage12503-validated private semantic extraction status to proof-slot "
            "coverage only. It emits no raw/private data, fabricated labels, event-local promotion, "
            "Level-3 atoms, patch traces, or training/admission rows."
        ),
        "source_stage": STAGE12503,
        "stage12503_decision": stage12503_summary.get("decision"),
        "validated_private_semantic_extraction_status_count": len(validated),
        "proof_slot_update_record_count": len(updates),
        "proof_slots_updated_counts": dict(sorted(slot_counts.items())),
        "blocked_request_count_carried_forward": len(blockers),
        "language_counts": dict(sorted(language_counts.items())),
        "task_family_counts": dict(sorted(task_counts.items())),
        "residual_blocker_code_counts": dict(sorted(residual_counts.items())),
        "event_local_promoted_count": 0,
        "guardrail_scan_passed": guardrail["scan_passed"],
        "raw_leak_count": guardrail["raw_leak_count"],
        "next_stage": (
            "independent_policy_label_or_same_source_lineage_proof_acquisition"
            if updates
            else "authoritative_private_semantic_extraction_return_acquisition"
        ),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }

    write_jsonl(OUT / "closed_loop_proof_slot_update_ledger.jsonl", updates)
    write_jsonl(OUT / "authoritative_proof_slot_update_blockers.jsonl", blockers)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()

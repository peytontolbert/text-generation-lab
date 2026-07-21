#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12501_closed_loop_slot_materialization_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12500_OUT = ROOT / "runs/local/artifacts/stage12500_closed_loop_candidate_packet_router"
STAGE12500_SUMMARY = ROOT / "runs/summaries/stage12500_closed_loop_candidate_packet_router.json"
WORKLIST = STAGE12500_OUT / "closed_loop_materialization_worklist.jsonl"
PACKETS = STAGE12500_OUT / "closed_loop_candidate_packets.jsonl"

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
    "private_review_performed_by_stage": False,
    "local_model_label_authority_used": False,
}
ZERO_GUARDS = {
    "training_rows_emitted": 0,
    "admitted_rows": 0,
    "level3_admitted": 0,
    "level3_atom_count": 0,
    "patch_trace_admitted": 0,
    "patch_trace_rows": 0,
    "proof_grade_repair_rows": 0,
    "external_repair_credit_count": 0,
    "sealed_eval_rows": 0,
}

REQUIRED_FOR_LEVEL3 = {
    "state_before_summary_codes_present": "authoritative_state_before_missing",
    "candidate_action_set_materialized": "candidate_action_set_missing",
    "chosen_action_policy_label_present": "chosen_action_or_no_policy_label_reason_missing",
    "observation_or_verifier_status_present": "observation_or_verifier_semantic_status_missing",
    "state_delta_codes_present": "state_delta_or_state_after_missing",
    "stop_continue_label_present": "stop_continue_proof_missing",
    "same_source_lineage_proof_present": "same_source_causal_lineage_missing",
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


def level3_blockers(work: dict[str, Any], packet: dict[str, Any] | None) -> list[str]:
    blockers: list[str] = []
    if packet is None:
        return ["source_packet_missing"]

    if packet.get("source_kind") == "event_local_observation_status_support":
        blockers.append("event_local_recovery_only_independent_review_missing")
    if packet.get("language_family") == "session_unknown_language":
        blockers.append("language_family_unrecovered")

    slot_status = packet.get("closed_loop_slot_status") or {}
    for slot, blocker in REQUIRED_FOR_LEVEL3.items():
        if not slot_status.get(slot):
            blockers.append(blocker)

    required_materialization = set(work.get("required_materialization") or [])
    if "same_source_lineage_proof_required" in required_materialization:
        blockers.append("same_source_lineage_required_by_upstream")
    if "structured_state_before_codes_required" in required_materialization:
        blockers.append("structured_state_before_required_by_upstream")
    if "state_delta_codes_required" in required_materialization:
        blockers.append("state_delta_required_by_upstream")
    if "external_patch_effect_proof_present" in required_materialization:
        blockers.append("external_patch_effect_proof_missing")
    if "patch_apply_status_present" in required_materialization:
        blockers.append("patch_apply_status_missing")

    blockers.append("candidate_action_set_policy_validity_not_authoritatively_reviewed")
    blockers.append("observed_action_imitation_not_ruled_out")
    blockers.append("raw_private_semantic_review_not_performed")
    return sorted(set(blockers))


def make_audit(work: dict[str, Any], packet: dict[str, Any] | None) -> dict[str, Any]:
    blockers = level3_blockers(work, packet)
    materialized = not blockers
    return {
        "record_type": "stage12501_closed_loop_slot_materialization_audit_v1",
        "audit_id_hash": stable_hash(
            {
                "work_item_id_hash": work.get("work_item_id_hash"),
                "packet_id_hash": work.get("packet_id_hash"),
                "blockers": blockers,
            }
        ),
        "work_item_id_hash": work.get("work_item_id_hash"),
        "packet_id_hash": work.get("packet_id_hash"),
        "root_or_window_hash": work.get("root_or_window_hash"),
        "source_stage": work.get("source_stage"),
        "source_kind": work.get("source_kind"),
        "task_family": work.get("task_family"),
        "language_family": work.get("language_family"),
        "materialization_decision": "materialized" if materialized else "blocked",
        "materialized_closed_loop_record": materialized,
        "level3_candidate": materialized,
        "patch_trace_candidate": False,
        "blocker_codes": blockers,
        "proved_slots": {
            "authoritative_state_before": False,
            "policy_valid_candidate_action_set": False,
            "chosen_action_or_no_policy_label_reason": False,
            "observation_or_verifier_semantic_status": False,
            "state_delta_or_state_after": False,
            "stop_continue": False,
            "same_source_causal_lineage": False,
            "patch_apply_status": False,
            "external_patch_effect": False,
        },
        "event_local_promotion_status": (
            "blocked_recovery_only"
            if work.get("source_kind") == "event_local_observation_status_support"
            else "not_event_local"
        ),
        "unknown_language_status": (
            "blocked_language_recovery_required"
            if work.get("language_family") == "session_unknown_language"
            else "language_present"
        ),
        "claim_boundary": (
            "Per-work-item materialization audit only. This stage does not inspect raw private "
            "logs, execute verifiers, fabricate policy labels, or admit training rows."
        ),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12500 = read_json(STAGE12500_SUMMARY)
    worklist = read_jsonl(WORKLIST)
    packets = {packet.get("packet_id_hash"): packet for packet in read_jsonl(PACKETS)}

    audits = [make_audit(work, packets.get(work.get("packet_id_hash"))) for work in worklist]
    blocked = [row for row in audits if row["materialization_decision"] == "blocked"]
    materialized = [row for row in audits if row["materialization_decision"] == "materialized"]

    blocker_counts = Counter()
    for row in audits:
        blocker_counts.update(row["blocker_codes"])
    task_counts = Counter(row["task_family"] for row in audits)
    language_counts = Counter(row["language_family"] for row in audits)
    source_kind_counts = Counter(row["source_kind"] for row in audits)

    outputs = {
        "audits": audits,
        "blocked": blocked,
        "materialized": materialized,
    }
    write_jsonl(OUT / "closed_loop_slot_materialization_audit.jsonl", audits)
    write_jsonl(OUT / "blocked_closed_loop_slot_materialization.jsonl", blocked)
    write_jsonl(OUT / "materialized_closed_loop_slot_records.jsonl", materialized)

    leak_issues = scan_raw_leaks(outputs)
    guardrail = {
        "scan_passed": not leak_issues,
        "raw_leak_count": len(leak_issues),
        "raw_leak_issue_hashes": leak_issues[:20],
        "scanned_outputs": [
            "closed_loop_slot_materialization_audit.jsonl",
            "blocked_closed_loop_slot_materialization.jsonl",
            "materialized_closed_loop_slot_records.jsonl",
        ],
    }
    write_json(OUT / "guardrail_scan.json", guardrail)

    summary = {
        "stage": STAGE,
        "decision": (
            "closed_loop_slot_materialization_blocked_no_authoritative_private_or_same_source_proofs"
            if not materialized
            else "closed_loop_slot_materialization_partial_requires_downstream_admission"
        ),
        "claim_boundary": (
            "Stage12501 audits Stage12500 materialization work items for authoritative closed-loop "
            "slot completion. It blocks items whose current public-safe artifacts cannot prove "
            "state, action-policy validity, verifier semantics, state delta, stop/continue, and "
            "same-source causal lineage."
        ),
        "input_stage12500_decision": stage12500.get("decision"),
        "input_work_item_count": len(worklist),
        "audit_record_count": len(audits),
        "blocked_work_item_count": len(blocked),
        "materialized_record_count": len(materialized),
        "task_family_counts": dict(sorted(task_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "source_kind_counts": dict(sorted(source_kind_counts.items())),
        "blocker_code_counts": dict(sorted(blocker_counts.items())),
        "event_local_blocked_count": sum(
            1 for row in audits if row["event_local_promotion_status"] == "blocked_recovery_only"
        ),
        "unknown_language_blocked_count": sum(
            1 for row in audits if row["unknown_language_status"] == "blocked_language_recovery_required"
        ),
        "raw_leak_count": guardrail["raw_leak_count"],
        "guardrail_scan_passed": guardrail["scan_passed"],
        "next_stage": "stage12502_authoritative_private_semantic_or_same_source_trace_extraction",
        "next_stage_acceptance": [
            "inspect_raw_private_sources_in_trusted_process_then_emit_safe_semantic_enums_only",
            "prove_same_source_patch_action_verifier_ordering_and_relevance",
            "recover_language_for_session_unknown_language_before_policy_or_eval_use",
            "keep_event_local_rows_recovery_only_until_independent_policy_review_exists",
            "emit_nonzero_level3_atoms_only_after_all_required_slots_are_proven",
        ],
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    write_json(OUT / "summary.json", summary)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()

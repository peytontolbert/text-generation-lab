#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12502_authoritative_private_semantic_extraction_request_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12500 = "stage12500_closed_loop_candidate_packet_router"
STAGE12500_OUT = ROOT / "runs/local/artifacts" / STAGE12500
STAGE12500_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12500}.json"
WORKLIST = STAGE12500_OUT / "closed_loop_materialization_worklist.jsonl"
PACKETS = STAGE12500_OUT / "closed_loop_candidate_packets.jsonl"
STAGE12499_SUMMARY = ROOT / "runs/summaries/stage12499_private_semantic_return_materializer_or_blocker.json"

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
}
ZERO_GUARDS = {
    "training_rows_emitted": 0,
    "admitted_rows": 0,
    "level3_admitted": 0,
    "patch_trace_admitted": 0,
    "stage12496_return_records_written": 0,
    "policy_labels_emitted": 0,
    "proof_rows_emitted": 0,
    "proof_grade_repair_rows": 0,
    "external_repair_credit_count": 0,
    "sealed_eval_rows": 0,
}

STATE_EXTRACTION_SLOTS = {
    "state_before_summary_codes_present",
    "state_delta_codes_present",
    "state_delta_codes_required",
    "structured_state_before_codes_required",
    "same_source_lineage_proof_present",
    "same_source_lineage_proof_required",
    "patch_apply_status_present",
    "stop_continue_label_present",
}
POLICY_LABEL_SLOTS = {"chosen_action_policy_label_present"}
REPAIR_EFFECT_SLOTS = {"external_patch_effect_proof_present"}
EVENT_LOCAL_SLOTS = {
    "event_local_not_policy_label_without_independent_review",
    "private_or_authoritative_state_update_review_required",
}
LANGUAGE_SLOTS = {"language_family_recovery_required"}
UNDERREPRESENTED_LANES = [
    "transition_candidate_selection",
    "transition_evidence_citation",
]


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


def group_slots(slots: list[str]) -> dict[str, list[str]]:
    groups = {
        "private_state_semantic_extraction": [],
        "causal_same_source_lineage": [],
        "independent_policy_label_review": [],
        "external_patch_effect_repair_proof": [],
        "event_local_independent_review": [],
        "language_recovery": [],
        "other": [],
    }
    for slot in sorted(set(slots)):
        if slot in {"same_source_lineage_proof_present", "same_source_lineage_proof_required"}:
            groups["causal_same_source_lineage"].append(slot)
        elif slot in STATE_EXTRACTION_SLOTS:
            groups["private_state_semantic_extraction"].append(slot)
        elif slot in POLICY_LABEL_SLOTS:
            groups["independent_policy_label_review"].append(slot)
        elif slot in REPAIR_EFFECT_SLOTS:
            groups["external_patch_effect_repair_proof"].append(slot)
        elif slot in EVENT_LOCAL_SLOTS:
            groups["event_local_independent_review"].append(slot)
        elif slot in LANGUAGE_SLOTS:
            groups["language_recovery"].append(slot)
        else:
            groups["other"].append(slot)
    return {key: value for key, value in groups.items() if value}


def risk_codes(work: dict[str, Any], packet: dict[str, Any] | None) -> list[str]:
    risks: list[str] = []
    source_kind = work.get("source_kind")
    language = work.get("language_family")
    task_family = work.get("task_family")
    slots = set(work.get("required_materialization") or [])
    if source_kind == "event_local_observation_status_support":
        risks.append("event_local_rows_recovery_only_not_policy_labels")
    if language == "session_unknown_language":
        risks.append("unknown_language_requires_language_recovery")
    if task_family == "transition_next_action":
        risks.append("observed_action_imitation_guard_required")
    if "external_patch_effect_proof_present" in slots:
        risks.append("selected_test_or_verifier_only_cannot_count_as_external_repair")
    if "patch_apply_status_present" in slots:
        risks.append("pass_to_pass_as_repair_guard_required")
    if packet and (packet.get("closed_loop_slot_status") or {}).get("observation_or_verifier_status_present"):
        risks.append("verifier_only_as_repair_guard_required")
    return sorted(set(risks))


def requestable_slots(work: dict[str, Any]) -> list[str]:
    slots = set(work.get("required_materialization") or [])
    allowed = slots & STATE_EXTRACTION_SLOTS
    return sorted(allowed - {"state_delta_codes_required", "structured_state_before_codes_required", "same_source_lineage_proof_required"})


def has_private_extraction_preflight_evidence(work: dict[str, Any], packet: dict[str, Any] | None) -> bool:
    if packet is None:
        return False
    if work.get("source_kind") == "event_local_observation_status_support":
        return False
    if work.get("language_family") == "session_unknown_language":
        return False
    if not (packet.get("candidate_action_set_status") or {}).get("candidate_action_set_materialized"):
        return False
    if not (packet.get("closed_loop_slot_status") or {}).get("observation_or_verifier_status_present"):
        return False
    return bool(requestable_slots(work))


def item_audit(work: dict[str, Any], packet: dict[str, Any] | None) -> dict[str, Any]:
    risks = risk_codes(work, packet)
    can_request = has_private_extraction_preflight_evidence(work, packet)
    blockers: list[str] = []
    if packet is None:
        blockers.append("stage12500_candidate_packet_missing")
    if work.get("source_kind") == "event_local_observation_status_support":
        blockers.append("event_local_row_requires_independent_private_review_before_policy_use")
    if work.get("language_family") == "session_unknown_language":
        blockers.append("language_family_recovery_required_before_extraction")
    if not can_request:
        blockers.append("not_enough_public_safe_locator_evidence_for_private_extraction_request")
    return {
        "record_type": "stage12502_materialization_preflight_item_audit_v1",
        "audit_item_id_hash": stable_hash({"work_item": work.get("work_item_id_hash"), "packet": work.get("packet_id_hash")}),
        "work_item_id_hash": work.get("work_item_id_hash"),
        "packet_id_hash": work.get("packet_id_hash"),
        "root_or_window_hash": work.get("root_or_window_hash"),
        "source_stage": work.get("source_stage"),
        "source_kind": work.get("source_kind"),
        "task_family": work.get("task_family"),
        "language_family": work.get("language_family"),
        "materialization_focus": work.get("materialization_focus"),
        "missing_proof_slots": sorted(set(work.get("required_materialization") or [])),
        "missing_proof_slot_groups": group_slots(work.get("required_materialization") or []),
        "risk_codes": risks,
        "public_safe_evidence_sufficient_for_private_extraction_request": can_request,
        "private_extraction_request_emitted": can_request,
        "requestable_private_extraction_slots": requestable_slots(work) if can_request else [],
        "blocked_proof_slots": sorted(set(work.get("required_materialization") or []) - set(requestable_slots(work))),
        "blocker_codes": sorted(set(blockers)),
        "raw_private_values_revealed": False,
        "policy_label_materialized": False,
        "level3_atom_materialized": False,
        "stage12496_return_materialized": False,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def extraction_request(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "stage12502_private_semantic_extraction_request_v1",
        "request_id_hash": stable_hash({"audit": audit["audit_item_id_hash"], "kind": "private_semantic_extraction"}),
        "audit_item_id_hash": audit["audit_item_id_hash"],
        "work_item_id_hash": audit["work_item_id_hash"],
        "packet_id_hash": audit["packet_id_hash"],
        "root_or_window_hash": audit["root_or_window_hash"],
        "source_stage": audit["source_stage"],
        "source_kind": audit["source_kind"],
        "task_family": audit["task_family"],
        "language_family": audit["language_family"],
        "requested_private_extraction_slots": audit["requestable_private_extraction_slots"],
        "required_private_review_guards": [
            "hash_locator_only_no_raw_public_artifact",
            "do_not_derive_policy_label_from_observed_action",
            "do_not_treat_pass_to_pass_as_repair",
            "do_not_treat_verifier_only_status_as_repair",
            "same_source_causal_lineage_must_be_independently_proven",
            "no_raw_paths_commands_diffs_source_text_or_verifier_output",
        ],
        "forbidden_outputs": [
            "training_rows",
            "admitted_rows",
            "level3_atoms",
            "patch_traces",
            "stage12496_returns",
            "policy_labels",
            "raw_private_values",
        ],
        "request_status": "ready_for_private_or_authoritative_extractor",
        "raw_private_values_revealed": False,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def blocker_record(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "stage12502_materialization_preflight_blocker_v1",
        "blocker_id_hash": stable_hash({"audit": audit["audit_item_id_hash"], "kind": "blocker"}),
        "audit_item_id_hash": audit["audit_item_id_hash"],
        "work_item_id_hash": audit["work_item_id_hash"],
        "packet_id_hash": audit["packet_id_hash"],
        "root_or_window_hash": audit["root_or_window_hash"],
        "source_stage": audit["source_stage"],
        "source_kind": audit["source_kind"],
        "task_family": audit["task_family"],
        "language_family": audit["language_family"],
        "missing_proof_slot_groups": audit["missing_proof_slot_groups"],
        "risk_codes": audit["risk_codes"],
        "blocker_codes": audit["blocker_codes"],
        "public_safe_status_only": True,
        "raw_private_values_revealed": False,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def grouped_records(audits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for audit in audits:
        primary = audit["blocker_codes"][0] if audit["blocker_codes"] else "private_extraction_requestable"
        grouped[(primary, audit["task_family"])].append(audit)
    rows = []
    for (primary, task_family), items in sorted(grouped.items()):
        slot_counter: Counter[str] = Counter()
        risk_counter: Counter[str] = Counter()
        language_counter: Counter[str] = Counter()
        for item in items:
            slot_counter.update(item["missing_proof_slots"])
            risk_counter.update(item["risk_codes"])
            language_counter[item["language_family"]] += 1
        rows.append(
            {
                "record_type": "stage12502_missing_proof_risk_group_v1",
                "group_id_hash": stable_hash({"primary": primary, "task": task_family}),
                "primary_group": primary,
                "task_family": task_family,
                "item_count": len(items),
                "language_counts": dict(sorted(language_counter.items())),
                "missing_proof_slot_counts": dict(sorted(slot_counter.items())),
                "risk_counts": dict(sorted(risk_counter.items())),
                "requestable_item_count": sum(1 for item in items if item["private_extraction_request_emitted"]),
                "blocked_item_count": sum(1 for item in items if not item["private_extraction_request_emitted"]),
                **FALSE_GUARDS,
                **ZERO_GUARDS,
            }
        )
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12500_summary = read_json(STAGE12500_SUMMARY)
    stage12499_summary = read_json(STAGE12499_SUMMARY)
    worklist = read_jsonl(WORKLIST)
    packets = {row.get("packet_id_hash"): row for row in read_jsonl(PACKETS)}

    audits = [item_audit(work, packets.get(work.get("packet_id_hash"))) for work in worklist]
    requests = [extraction_request(audit) for audit in audits if audit["private_extraction_request_emitted"]]
    blockers = [blocker_record(audit) for audit in audits if not audit["private_extraction_request_emitted"]]
    groups = grouped_records(audits)

    language_counts = Counter(row["language_family"] for row in audits)
    task_counts = Counter(row["task_family"] for row in audits)
    focus_counts = Counter(row["materialization_focus"] for row in audits)
    source_kind_counts = Counter(row["source_kind"] for row in audits)
    underrepresented_counts = {lane: task_counts.get(lane, 0) for lane in UNDERREPRESENTED_LANES}
    risk_counts: Counter[str] = Counter()
    missing_counts: Counter[str] = Counter()
    blocked_slot_counts: Counter[str] = Counter()
    request_slot_counts: Counter[str] = Counter()
    for row in audits:
        risk_counts.update(row["risk_codes"])
        missing_counts.update(row["missing_proof_slots"])
        blocked_slot_counts.update(row["blocked_proof_slots"])
        request_slot_counts.update(row["requestable_private_extraction_slots"])

    outputs = {
        "audits": audits,
        "requests": requests,
        "blockers": blockers,
        "groups": groups,
    }
    leak_issues = scan_raw_leaks(outputs)
    guardrail = {
        "stage": STAGE,
        "scan_passed": not leak_issues,
        "raw_leak_count": len(leak_issues),
        "raw_leak_issue_hashes": leak_issues[:40],
        "scanned_outputs": [
            "materialization_preflight_item_audit.jsonl",
            "private_semantic_extraction_requests.jsonl",
            "materialization_preflight_blockers.jsonl",
            "missing_proof_risk_groups.jsonl",
        ],
    }

    summary = {
        "stage": STAGE,
        "record_type": "stage12502_authoritative_private_semantic_extraction_request_preflight_summary_v1",
        "decision": "private_extraction_requests_ready_training_and_admission_blocked",
        "claim_boundary": (
            "Stage12502 classifies Stage12500 materialization work items for private/raw semantic "
            "extraction readiness using public-safe hashes and enums only. It emits no training rows, "
            "admitted rows, Level-3 atoms, patch traces, Stage12496 returns, proof rows, or policy labels."
        ),
        "source_stage": STAGE12500,
        "stage12500_decision": stage12500_summary.get("decision"),
        "input_work_item_count": len(worklist),
        "candidate_packet_count_seen": len(packets),
        "preflight_item_count": len(audits),
        "private_semantic_extraction_request_count": len(requests),
        "per_item_blocker_count": len(blockers),
        "missing_proof_risk_group_count": len(groups),
        "language_counts": dict(sorted(language_counts.items())),
        "task_family_counts": dict(sorted(task_counts.items())),
        "materialization_focus_counts": dict(sorted(focus_counts.items())),
        "source_kind_counts": dict(sorted(source_kind_counts.items())),
        "underrepresented_lane_counts": underrepresented_counts,
        "missing_proof_slot_counts": dict(sorted(missing_counts.items())),
        "requestable_private_extraction_slot_counts": dict(sorted(request_slot_counts.items())),
        "blocked_proof_slot_counts": dict(sorted(blocked_slot_counts.items())),
        "risk_counts": dict(sorted(risk_counts.items())),
        "stage12499_blocked_slot_count_carried_forward": stage12499_summary.get("blocked_slot_count", 0),
        "stage12499_event_local_excluded_count_carried_forward": stage12499_summary.get("event_local_excluded_count", 0),
        "stage12499_carryforward_blockers_preserved": True,
        "stage12499_event_local_exclusions_preserved": True,
        "event_local_promoted_count": 0,
        "unknown_language_extraction_request_count": sum(
            1 for row in requests if row.get("language_family") == "session_unknown_language"
        ),
        "guardrail_scan_passed": guardrail["scan_passed"],
        "raw_leak_count": guardrail["raw_leak_count"],
        "required_guards": [
            "event_local_rows_blocked_from_policy_label_use",
            "unknown_language_rows_require_language_recovery",
            "observed_action_imitation_guard",
            "pass_to_pass_as_repair_guard",
            "verifier_only_as_repair_guard",
            "raw_leakage_guard",
        ],
        "next_stage": "private_or_authoritative_semantic_extraction_runner_or_blocker",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }

    write_jsonl(OUT / "materialization_preflight_item_audit.jsonl", audits)
    write_jsonl(OUT / "private_semantic_extraction_requests.jsonl", requests)
    write_jsonl(OUT / "materialization_preflight_blockers.jsonl", blockers)
    write_jsonl(OUT / "missing_proof_risk_groups.jsonl", groups)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()

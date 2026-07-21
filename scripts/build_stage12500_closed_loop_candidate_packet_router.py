#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12500_closed_loop_candidate_packet_router"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

SELECTED_TEST_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12385_combined_train_support_ledger_v15_dedup"
    / "combined_selected_test_rows_v15_dedup.jsonl"
)
EVENT_LOCAL_SOURCES = {
    "stage12320_event_local_observation": (
        ROOT
        / "runs/local/artifacts/stage12320_event_local_semantic_review_admission"
        / "event_local_observation_train_support_admitted_rows.jsonl"
    ),
    "stage12323_v4_event_local": (
        ROOT
        / "runs/local/artifacts/stage12323_v4_event_local_review_admission"
        / "v4_event_local_train_support_admitted_rows.jsonl"
    ),
}
STAGE12499_SUMMARY = ROOT / "runs/summaries/stage12499_private_semantic_return_materializer_or_blocker.json"
STAGE12477_QUEUE = (
    ROOT
    / "runs/local/artifacts/stage12477_causal_transition_next_action_control_board"
    / "causal_transition_action_queue.jsonl"
)

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
    "proof_grade_repair_rows": 0,
    "external_repair_credit_count": 0,
    "sealed_eval_rows": 0,
}

TASK_PRIORITY = {
    "transition_next_action": 0,
    "transition_verifier_transition": 1,
    "transition_continue_or_stop": 2,
    "transition_candidate_selection": 3,
    "transition_evidence_citation": 4,
    "event_local_transition_observation": 5,
}
MATERIALIZATION_TARGET = 64
MAX_PER_ROOT = 3
MAX_PER_SOURCE_STAGE = 16


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


def load_source_rows() -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    for row in read_jsonl(SELECTED_TEST_ROWS):
        rows.append(("selected_test_transition_support", row))
    for source_name, path in EVENT_LOCAL_SOURCES.items():
        for row in read_jsonl(path):
            rows.append((source_name, row))
    return rows


def candidate_roles(row: dict[str, Any]) -> list[str]:
    if row.get("opaque_options"):
        roles = []
        for option in row.get("opaque_options") or []:
            semantic = option.get("semantic_candidate") or {}
            role = semantic.get("role") or option.get("value") or option.get("semantic_id")
            if role:
                roles.append(str(role))
        return sorted(set(roles))
    actions = (((row.get("model_input_view") or {}).get("candidate_action_set") or {}).get("actions") or [])
    return sorted({str(action.get("action_type")) for action in actions if action.get("action_type")})


def source_kind(source_name: str, row: dict[str, Any]) -> str:
    if row.get("record_type") == "target_hidden_event_local_observation_status_train_support":
        return "event_local_observation_status_support"
    if source_name == "selected_test_transition_support":
        return "selected_test_bounded_transition_support"
    return source_name


def proof_slots(row: dict[str, Any], kind: str) -> tuple[dict[str, bool], list[str]]:
    selected = kind == "selected_test_bounded_transition_support"
    event_local = kind == "event_local_observation_status_support"
    target = row.get("target_only") or {}
    state_codes = (row.get("model_input_view") or {}).get("state_before_summary_codes") or []
    slots = {
        "state_before_summary_codes_present": bool(state_codes),
        "candidate_action_set_materialized": bool(candidate_roles(row)),
        "chosen_action_policy_label_present": False,
        "observation_or_verifier_status_present": bool(target.get("verifier_status_class")) or selected,
        "state_delta_codes_present": bool(target.get("state_delta_codes")),
        "stop_continue_label_present": bool(target.get("stop_continue_label")) or row.get("task_family") == "transition_continue_or_stop",
        "same_source_lineage_proof_present": False,
        "patch_apply_status_present": bool(target.get("patch_apply_status")),
        "external_patch_effect_proof_present": False,
        "level3_complete": False,
    }
    missing = [
        name
        for name, present in slots.items()
        if not present and name not in {"level3_complete"}
    ]
    if selected:
        missing.extend(
            [
                "structured_state_before_codes_required",
                "state_delta_codes_required",
                "same_source_lineage_proof_required",
            ]
        )
    if event_local:
        missing.extend(
            [
                "language_family_recovery_required" if not row.get("language_family") else "language_family_present",
                "private_or_authoritative_state_update_review_required",
                "event_local_not_policy_label_without_independent_review",
            ]
        )
    return slots, sorted(set(missing))


def row_identity(row: dict[str, Any]) -> dict[str, Any]:
    root_id = row.get("root_id") or (row.get("source_refs") or {}).get("task_window_id") or row.get("source_row_id")
    return {
        "row_id_hash": stable_hash(row.get("row_id") or row.get("source_row_id")),
        "source_row_id_hash": stable_hash(row.get("source_row_id") or row.get("row_id")),
        "root_or_window_hash": stable_hash(root_id),
        "source_ref_hash": stable_hash(row.get("source_refs") or {}),
    }


def make_packet(source_name: str, row: dict[str, Any]) -> dict[str, Any]:
    kind = source_kind(source_name, row)
    slots, missing = proof_slots(row, kind)
    roles = candidate_roles(row)
    task_family = row.get("task_family") or row.get("record_type") or "unknown"
    language = row.get("language_family") or "session_unknown_language"
    return {
        "record_type": "stage12500_closed_loop_candidate_packet_v1",
        "packet_id_hash": stable_hash({"source": source_name, "row": row.get("row_id") or row.get("source_row_id")}),
        **row_identity(row),
        "source_stage": row.get("stage") or row.get("source_stage") or source_name,
        "source_kind": kind,
        "task_family": task_family,
        "language_family": language,
        "candidate_action_set_status": {
            "candidate_action_set_materialized": bool(roles),
            "candidate_action_or_role_count": len(roles),
            "candidate_action_or_role_hashes": [stable_hash(role) for role in roles],
            "raw_candidate_text_emitted": False,
        },
        "closed_loop_slot_status": slots,
        "missing_proof_slots": missing,
        "materialization_focus": materialization_focus(task_family, kind, missing),
        "claim_boundary": (
            "Candidate packet only. May support next materialization/review work, "
            "but is not a Level-3 atom, repair proof, strict eval row, or training authorization."
        ),
        "source_refs_public_policy": "hashes_and_enums_only_no_paths_commands_diffs_source_or_verifier_output",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def materialization_focus(task_family: str, kind: str, missing: list[str]) -> str:
    if "same_source_lineage_proof_present" in missing:
        return "same_source_lineage_and_state_delta_recovery"
    if task_family == "transition_next_action":
        return "independent_next_action_policy_label_review"
    if task_family == "transition_verifier_transition":
        return "verifier_transition_semantic_extraction"
    if kind == "event_local_observation_status_support":
        return "state_update_and_stop_continue_review"
    return "closed_loop_slot_completion"


def select_worklist(packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        packets,
        key=lambda row: (
            TASK_PRIORITY.get(row.get("task_family"), 99),
            row.get("language_family") or "",
            row.get("root_or_window_hash") or "",
            row.get("packet_id_hash") or "",
        ),
    )
    selected: list[dict[str, Any]] = []
    per_root: Counter[str] = Counter()
    per_source: Counter[str] = Counter()
    per_task: Counter[str] = Counter()
    per_language: Counter[str] = Counter()
    for packet in ordered:
        root = packet["root_or_window_hash"]
        source = packet["source_stage"]
        if per_root[root] >= MAX_PER_ROOT:
            continue
        if per_source[source] >= MAX_PER_SOURCE_STAGE:
            continue
        work = {
            "record_type": "stage12500_materialization_work_item_v1",
            "work_item_id_hash": stable_hash({"packet": packet["packet_id_hash"], "work": "materialize_closed_loop_slots"}),
            "packet_id_hash": packet["packet_id_hash"],
            "root_or_window_hash": root,
            "source_stage": source,
            "source_kind": packet["source_kind"],
            "task_family": packet["task_family"],
            "language_family": packet["language_family"],
            "required_materialization": packet["missing_proof_slots"],
            "materialization_focus": packet["materialization_focus"],
            "acceptance_gate": [
                "state_before_codes_are_authoritative",
                "candidate_action_set_is_policy_valid_not_observed_action_imitation",
                "observation_or_verifier_status_has_safe_semantic_extraction",
                "state_delta_or_stop_continue_proof_is_not_inferred_from_target_label",
                "same_source_lineage_proof_is_hash_only_and_causal",
                "no_raw_paths_commands_diffs_source_text_or_verifier_output",
            ],
            "training_allowed": False,
            "admission_allowed": False,
            "training_rows_emitted": 0,
            "admitted_rows": 0,
        }
        selected.append(work)
        per_root[root] += 1
        per_source[source] += 1
        per_task[packet["task_family"]] += 1
        per_language[packet["language_family"]] += 1
        if len(selected) >= MATERIALIZATION_TARGET:
            break
    return selected


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_rows = load_source_rows()
    packets = [make_packet(source_name, row) for source_name, row in source_rows]
    worklist = select_worklist(packets)
    stage12499 = read_json(STAGE12499_SUMMARY)
    action_queue = read_jsonl(STAGE12477_QUEUE)

    language_counts = Counter(packet["language_family"] for packet in packets)
    task_counts = Counter(packet["task_family"] for packet in packets)
    source_kind_counts = Counter(packet["source_kind"] for packet in packets)
    worklist_language_counts = Counter(row["language_family"] for row in worklist)
    worklist_task_counts = Counter(row["task_family"] for row in worklist)
    worklist_focus_counts = Counter(row["materialization_focus"] for row in worklist)
    slot_counts = Counter()
    missing_counts = Counter()
    for packet in packets:
        for slot, present in packet["closed_loop_slot_status"].items():
            if present:
                slot_counts[slot] += 1
        for missing in packet["missing_proof_slots"]:
            missing_counts[missing] += 1

    outputs = {
        "packets": packets,
        "worklist": worklist,
        "stage12477_action_queue_carryforward": [
            {
                "record_type": "stage12500_stage12477_action_queue_carryforward_v1",
                "action_id": item.get("action_id"),
                "action_type": item.get("action_type"),
                "priority": item.get("priority"),
                "input_stage_ref": item.get("input_stage_ref"),
                "success_gate": item.get("success_gate"),
                "training_allowed": False,
                "admission_allowed": False,
                "emitted_training_rows": 0,
            }
            for item in action_queue
        ],
    }
    write_jsonl(OUT / "closed_loop_candidate_packets.jsonl", packets)
    write_jsonl(OUT / "closed_loop_materialization_worklist.jsonl", worklist)
    write_jsonl(OUT / "stage12477_action_queue_carryforward.jsonl", outputs["stage12477_action_queue_carryforward"])

    leak_issues: list[str] = []
    leak_issues.extend(scan_raw_leaks(outputs))
    guardrail = {
        "scan_passed": not leak_issues,
        "raw_leak_count": len(leak_issues),
        "raw_leak_issue_hashes": leak_issues[:20],
        "scanned_outputs": [
            "closed_loop_candidate_packets.jsonl",
            "closed_loop_materialization_worklist.jsonl",
            "stage12477_action_queue_carryforward.jsonl",
        ],
    }
    write_json(OUT / "guardrail_scan.json", guardrail)

    summary = {
        "stage": STAGE,
        "decision": "closed_loop_candidate_packets_ready_training_blocked",
        "claim_boundary": (
            "Stage12500 normalizes current support supply into public-safe closed-loop candidate packets "
            "and a capped materialization worklist. It emits no train rows and admits no Level-3 atoms."
        ),
        "input_source_row_count": len(source_rows),
        "candidate_packet_count": len(packets),
        "materialization_work_item_count": len(worklist),
        "materialization_target": MATERIALIZATION_TARGET,
        "language_counts": dict(sorted(language_counts.items())),
        "task_family_counts": dict(sorted(task_counts.items())),
        "source_kind_counts": dict(sorted(source_kind_counts.items())),
        "worklist_language_counts": dict(sorted(worklist_language_counts.items())),
        "worklist_task_family_counts": dict(sorted(worklist_task_counts.items())),
        "worklist_materialization_focus_counts": dict(sorted(worklist_focus_counts.items())),
        "stage12501_claim_limits": [
            "stage12501_must_not_claim_broad_transition_coverage_from_stage12500_worklist",
            "event_local_rows_are_recovery_only_not_policy_labels_without_independent_review",
            "session_unknown_language_rows_require_language_recovery_before_training_or_eval",
            "candidate_selection_and_evidence_citation_lanes_are_underrepresented_and_need_separate_followup",
        ],
        "closed_loop_slot_present_counts": dict(sorted(slot_counts.items())),
        "missing_proof_slot_counts": dict(sorted(missing_counts.items())),
        "stage12499_blocked_slot_count_carried_forward": stage12499.get("blocked_slot_count", 0),
        "stage12499_event_local_excluded_count_carried_forward": stage12499.get("event_local_excluded_count", 0),
        "stage12477_action_queue_count_carried_forward": len(action_queue),
        "next_stage": "stage12501_private_or_authoritative_closed_loop_slot_materializer",
        "next_stage_acceptance": [
            "fill_state_before_state_after_or_state_delta_semantics_for_stage12500_worklist",
            "prove_same_source_causal_linkage_or_keep_candidate_blocked",
            "do_not_promote_event_local_observation_rows_to_next_action_policy_without_independent_review",
            "do_not_count_selected_test_support_as_external_patch_effect_repair",
        ],
        "raw_leak_count": guardrail["raw_leak_count"],
        "guardrail_scan_passed": guardrail["scan_passed"],
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    write_json(OUT / "summary.json", summary)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()

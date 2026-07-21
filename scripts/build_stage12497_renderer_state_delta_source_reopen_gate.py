#!/usr/bin/env python3
"""Renderer, state-delta, and source-reopen gate.

Stage12497 is the next gate after policy-label review validation. It only
creates downstream work packets when Stage12496 has validated independent
policy labels. With zero validated labels, it fails closed and emits no
training, admission, renderer, or source-reopen packets.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12497_renderer_state_delta_source_reopen_gate"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12496 = "stage12496_policy_label_review_return_validator"
VALIDATED = ROOT / "runs/local/artifacts" / STAGE12496 / "validated_policy_label_review_results.jsonl"
STAGE12496_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12496}.json"

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output)\b|"
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
    "reviewed_train_support_rows": 0,
    "proof_grade_repair_rows": 0,
    "external_repair_credit_count": 0,
    "sealed_eval_rows": 0,
}

REQUIRED_DOWNSTREAM_GATES = [
    "renderer_contract_hash",
    "state_delta_review_hash",
    "source_reopen_or_trace_join_hash",
    "stop_continue_label_hash",
    "anti_shortcut_final_audit_hash",
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


def scan(value: Any) -> list[str]:
    issues: list[str] = []
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(stable_hash(value))
    elif isinstance(value, dict):
        for child in value.values():
            issues.extend(scan(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan(child))
    return issues


def downstream_packet(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "stage12497_renderer_state_delta_source_reopen_work_item_v1",
        "work_item_id_hash": stable_hash({"validated": row.get("validated_result_id_hash")}),
        "validated_result_id_hash": row.get("validated_result_id_hash"),
        "review_item_id_hash": row.get("review_item_id_hash"),
        "packet_id_hash": row.get("packet_id_hash"),
        "source_candidate_id_hash": row.get("source_candidate_id_hash"),
        "language_family": row.get("language_family"),
        "task_family": row.get("task_family"),
        "candidate_action_set_rewritten_hash": row.get("candidate_action_set_rewritten_hash"),
        "independent_policy_label_hash": row.get("independent_policy_label_hash"),
        "required_downstream_gates": REQUIRED_DOWNSTREAM_GATES,
        "remaining_blocker_codes": [
            "renderer_contract_missing",
            "state_delta_review_missing",
            "source_reopen_or_trace_join_required",
            "stop_continue_label_missing",
            "anti_shortcut_final_audit_missing",
        ],
        "claim_boundary": {
            "renderer_state_delta_source_reopen_work_item": True,
            "reviewed_train_support": False,
            "level3_closed_loop_episode": False,
            "proof_grade_repair": False,
        },
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12496_summary = read_json(STAGE12496_SUMMARY)
    validated = read_jsonl(VALIDATED)
    packets = [downstream_packet(row) for row in validated]
    blocked = []
    if not validated:
        blocked.append(
            {
                "record_type": "stage12497_blocked_gate_ref_v1",
                "reason_codes": [
                    "stage12496_zero_accepted_returns",
                    "stage12496_missing_review_returns",
                    "policy_label_review_not_validated",
                    "renderer_contract_missing",
                    "state_delta_review_missing",
                    "source_reopen_or_trace_join_missing",
                    "training_packaging_premature",
                ],
                "stage12496_expected_work_items": stage12496_summary.get("input_work_item_count", 0),
                "stage12496_missing_return_count": stage12496_summary.get("missing_return_count", 0),
                "stage12496_accepted_policy_label_count": stage12496_summary.get("accepted_policy_label_count", 0),
                **FALSE_GUARDS,
                **ZERO_GUARDS,
            }
        )

    language_counts = Counter(row["language_family"] for row in packets)
    task_counts = Counter(row["task_family"] for row in packets)
    issue_hashes = scan({"packets": packets, "blocked": blocked})
    guardrail = {
        "stage": STAGE,
        "scan_passed": not issue_hashes,
        "raw_leak_count": len(issue_hashes),
        "issue_hashes": issue_hashes[:80],
    }
    summary = {
        "stage": STAGE,
        "record_type": "stage12497_renderer_state_delta_source_reopen_gate_summary_v1",
        "decision": "blocked_stage12496_zero_accepted_returns"
        if not packets
        else "renderer_state_delta_source_reopen_work_items_ready_training_blocked",
        "source_stage_refs": [STAGE12496],
        "stage12496_decision": stage12496_summary.get("decision"),
        "stage12496_input_work_item_count": stage12496_summary.get("input_work_item_count"),
        "stage12496_accepted_return_count": stage12496_summary.get("accepted_policy_label_count"),
        "stage12496_missing_return_count": stage12496_summary.get("missing_return_count"),
        "stage12496_accepted_policy_label_count": stage12496_summary.get("accepted_policy_label_count"),
        "input_validated_policy_label_count": len(validated),
        "validated_policy_label_input_count": len(validated),
        "renderer_contract_input_count": 0,
        "renderer_contract_valid_count": 0,
        "renderer_contract_missing_count": len(validated) if validated else int(stage12496_summary.get("input_work_item_count") or 0),
        "renderer_leak_blocked_count": 0,
        "state_delta_review_input_count": 0,
        "state_delta_review_valid_count": 0,
        "state_delta_review_missing_count": len(validated) if validated else int(stage12496_summary.get("input_work_item_count") or 0),
        "state_delta_fabrication_blocked_count": 0,
        "source_reopen_input_count": 0,
        "source_reopen_valid_count": 0,
        "source_reopen_missing_count": len(validated) if validated else int(stage12496_summary.get("input_work_item_count") or 0),
        "source_reopen_overclaim_blocked_count": 0,
        "event_local_input_count": stage12496_summary.get("event_local_input_count", 0),
        "event_local_promoted_count": stage12496_summary.get("event_local_promoted_count", 0),
        "event_local_blocked_count": stage12496_summary.get("event_local_input_count", 0),
        "validated_stage12497_row_count": len(packets),
        "blocked_stage12497_row_count": len(blocked),
        "work_item_count": len(packets),
        "blocked_gate_count": len(blocked),
        "language_counts": dict(sorted(language_counts.items())),
        "task_family_counts": dict(sorted(task_counts.items())),
        "required_downstream_gates": REQUIRED_DOWNSTREAM_GATES,
        "raw_leak_count": guardrail["raw_leak_count"],
        "next_stage": "stage12498_reviewed_transition_train_support_admission",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "summary_hash": stable_hash(
            {
                "validated": len(validated),
                "packets": len(packets),
                "blocked": len(blocked),
            }
        ),
    }

    write_jsonl(OUT / "renderer_state_delta_source_reopen_work_items.jsonl", packets)
    write_jsonl(OUT / "blocked_gate_refs.jsonl", blocked)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()

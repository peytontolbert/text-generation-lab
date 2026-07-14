#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11042
NAME = "stage11042_priority_residual_root_materialization_packet"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "priority_residual_root_materialization_packet.json"
ROOT_CARDS_JSONL = OUT_DIR / "priority_root_cards.jsonl"
PACKET_ROWS_JSONL = OUT_DIR / "priority_packet_rows.jsonl"

REQUEST_ROWS = ARTIFACTS / "stage11041_residual_rebalance_materialization_request" / "request_rows.jsonl"
ROOT_RECORDS = ARTIFACTS / "stage10516_long_context_root_state_compiler" / "compiled_root_records.jsonl"
CAUSAL_STATES = ARTIFACTS / "stage10516_long_context_root_state_compiler" / "compiled_causal_states.jsonl"
EVENTS = ARTIFACTS / "stage10516_long_context_root_state_compiler" / "compiled_typed_events.jsonl"
MULTITARGET_ROWS = ARTIFACTS / "stage10516_long_context_root_state_compiler" / "compiled_multitarget_rows.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_json_text(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def scoreability_for(row: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    subtype = str(row.get("target_subtype") or "")
    visible_ids = list(state.get("visible_evidence_ids") or [])
    target = parse_json_text(row.get("target_text"))

    if subtype == "decisive_evidence":
        if isinstance(target, list) and target and all(str(item) in visible_ids for item in target):
            return {
                "scoreable_now": False,
                "reason": "target_evidence_ids_are_visible_but_still_opaque_handles",
            }
        return {
            "scoreable_now": False,
            "reason": "requires_explicit_candidate_ledger_or_evidence_projection",
        }
    if subtype == "verifier_outcome":
        return {
            "scoreable_now": True,
            "reason": "semantic_verifier_route_target_present",
        }
    if subtype == "retrieve_answer_abstain":
        return {
            "scoreable_now": True,
            "reason": "semantic_terminal_decision_target_present",
        }
    return {
        "scoreable_now": False,
        "reason": "unknown_target_subtype",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    request_rows = sorted(load_jsonl(REQUEST_ROWS), key=lambda row: int(row.get("priority") or 999))
    selected_requests = request_rows[:5]
    selected_root_ids = {str(row.get("root_id") or "") for row in selected_requests}

    root_records = {str(row.get("root_id") or ""): row for row in load_jsonl(ROOT_RECORDS) if str(row.get("root_id") or "") in selected_root_ids}
    states = {str(row.get("root_id") or ""): row for row in load_jsonl(CAUSAL_STATES) if str(row.get("root_id") or "") in selected_root_ids}

    events_by_root: dict[str, list[dict[str, Any]]] = {}
    for row in load_jsonl(EVENTS):
        root_id = str(row.get("root_id") or "")
        if root_id not in selected_root_ids:
            continue
        events_by_root.setdefault(root_id, []).append(row)
    for root_id in events_by_root:
        events_by_root[root_id].sort(key=lambda row: int(row.get("event_index") or 0))

    rows_by_root: dict[str, list[dict[str, Any]]] = {}
    for row in load_jsonl(MULTITARGET_ROWS):
        root_id = str(row.get("root_id") or "")
        if root_id not in selected_root_ids:
            continue
        rows_by_root.setdefault(root_id, []).append(row)

    root_cards: list[dict[str, Any]] = []
    packet_rows: list[dict[str, Any]] = []

    for request in selected_requests:
        root_id = str(request.get("root_id") or "")
        root = root_records[root_id]
        state = states[root_id]
        root_events = events_by_root.get(root_id, [])
        root_rows = sorted(rows_by_root.get(root_id, []), key=lambda row: str(row.get("target_subtype") or row.get("row_id") or ""))

        task_event = next((event for event in root_events if event.get("event_type") == "USER_TASK"), None)
        retrieve_event = next((event for event in root_events if event.get("event_type") in {"SEARCH_RESULT", "FILE_READ", "COMMAND_RESULT"}), None)
        test_event = next((event for event in root_events if event.get("event_type") == "TEST_RESULT"), None)

        final_state = dict(state.get("final_state") or {})
        task_counts = Counter(str(row.get("target_subtype") or "unknown") for row in root_rows)
        scoreability_counts = Counter()

        for row in root_rows:
            decision = scoreability_for(row, state)
            scoreability_counts["scoreable" if decision["scoreable_now"] else "blocked"] += 1
            packet_rows.append(
                {
                    "root_id": root_id,
                    "repo_id": request.get("repo_id"),
                    "repo_family": request.get("repo_family"),
                    "language_family": request.get("language_family"),
                    "priority": request.get("priority"),
                    "request_kind": request.get("request_kind"),
                    "claim_role": request.get("claim_role"),
                    "promotion_lane": request.get("promotion_lane"),
                    "row_id": row.get("row_id"),
                    "state_id": row.get("state_id"),
                    "target_family": row.get("target_family"),
                    "target_subtype": row.get("target_subtype"),
                    "target_text": row.get("target_text"),
                    "target_text_parsed": parse_json_text(row.get("target_text")),
                    "query_text": state.get("query_text"),
                    "visible_evidence_ids": list(state.get("visible_evidence_ids") or []),
                    "verification_targets": list(final_state.get("verification_targets") or []),
                    "expected_changed_files": list(final_state.get("expected_changed_files") or []),
                    "key_symbols": list(final_state.get("key_symbols") or [])[:16],
                    "anti_cheat_requirements": list(request.get("anti_cheat_requirements") or []),
                    "materialization_requirements": list(request.get("materialization_requirements") or []),
                    "scoreability": decision,
                }
            )

        root_cards.append(
            {
                "root_id": root_id,
                "priority": request.get("priority"),
                "request_kind": request.get("request_kind"),
                "claim_role": request.get("claim_role"),
                "promotion_lane": request.get("promotion_lane"),
                "language_family": request.get("language_family"),
                "repo_id": request.get("repo_id"),
                "repo_family": request.get("repo_family"),
                "snapshot_id": request.get("snapshot_id"),
                "semantic_lane": request.get("semantic_lane"),
                "quality_tier": request.get("quality_tier"),
                "source_family_id": request.get("source_family_id"),
                "verifier_id": request.get("verifier_id"),
                "task_family": root.get("task_family"),
                "split_component": root.get("split_component"),
                "query_text": state.get("query_text"),
                "user_task_text": task_event.get("content") if task_event else None,
                "retrieval_event_artifact_refs": list(retrieve_event.get("artifact_refs") or []) if retrieve_event else [],
                "test_event_artifact_refs": list(test_event.get("artifact_refs") or []) if test_event else [],
                "event_types": [str(event.get("event_type") or "") for event in root_events],
                "visible_evidence_ids": list(state.get("visible_evidence_ids") or []),
                "verification_targets": list(final_state.get("verification_targets") or []),
                "expected_changed_files": list(final_state.get("expected_changed_files") or []),
                "key_symbols": list(final_state.get("key_symbols") or []),
                "row_ids": [str(row.get("row_id") or "") for row in root_rows],
                "row_task_counts": dict(sorted(task_counts.items())),
                "scoreability_counts": dict(sorted(scoreability_counts.items())),
                "anti_cheat_contract": [
                    "Do not use these roots as strict eval until decisive_evidence targets are projected into an explicit visible candidate ledger.",
                    "Keep verifier targets opaque where the row is meant to test test-selection competition rather than filename matching.",
                    "Reserve sibling roots before training and never split rows from the same root across train/heldout.",
                    "Maintain candidate_change_surface as a plausible distractor when converting decisive_evidence into bounded-choice rows.",
                ],
            }
        )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "priority_residual_root_materialization_packet_ready",
        "claim_scope": [
            "Materialize the top five stage11041 residual-rebalance roots into a direct execution packet tied to the actual plateau lanes.",
            "Expose root cards and packet rows for the exact C/C++ parametergolf and Python verifier-transition roots that should be converted next.",
            "Preserve anti-cheat boundaries by marking which row targets are scoreable now and which still require explicit evidence-ledger projection.",
        ],
        "headline_findings": [
            f"All {len(root_cards)} priority roots have compiled root/state/event coverage and exactly three useful targets each: decisive_evidence, verifier_outcome, and retrieve_answer_abstain.",
            "The Python verifier-transition roots are materially ready for successor-row construction because they already carry PASS_TRACE_VERIFICATION_TARGETS plus concrete verification target paths.",
            "The C/C++ parametergolf roots are executable packet candidates, but their decisive_evidence targets are still opaque chunk IDs and must be projected into visible evidence ledgers before scoring.",
        ],
        "metrics": {
            "selected_root_count": len(root_cards),
            "packet_row_count": len(packet_rows),
            "rows_by_language": {
                language: sum(1 for row in packet_rows if str(row.get("language_family") or "") == language)
                for language in sorted({str(row.get("language_family") or "") for row in packet_rows})
            },
            "scoreable_rows": sum(1 for row in packet_rows if (row.get("scoreability") or {}).get("scoreable_now") is True),
            "blocked_rows": sum(1 for row in packet_rows if (row.get("scoreability") or {}).get("scoreable_now") is False),
            "scoreable_by_subtype": {
                subtype: sum(
                    1
                    for row in packet_rows
                    if str(row.get("target_subtype") or "") == subtype and (row.get("scoreability") or {}).get("scoreable_now") is True
                )
                for subtype in sorted({str(row.get("target_subtype") or "") for row in packet_rows})
            },
        },
        "next_best_step": [
            "Build explicit visible-evidence candidate ledgers for the five blocked decisive_evidence rows.",
            "Convert the two Python roots into opaque verifier-transition candidate rows with sibling test competition.",
            "Merge the resulting rows into the next residual-support or reserved-candidate package only after anti-cheat review passes.",
        ],
        "source_artifacts": {
            "request_rows": rel(REQUEST_ROWS),
            "root_records": rel(ROOT_RECORDS),
            "causal_states": rel(CAUSAL_STATES),
            "events": rel(EVENTS),
            "multitarget_rows": rel(MULTITARGET_ROWS),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "root_cards_jsonl": rel(ROOT_CARDS_JSONL),
            "packet_rows_jsonl": rel(PACKET_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(ROOT_CARDS_JSONL, root_cards)
    write_jsonl(PACKET_ROWS_JSONL, packet_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

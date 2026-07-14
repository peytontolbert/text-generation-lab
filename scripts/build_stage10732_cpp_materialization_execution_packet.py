#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACT_DIR = ROOT / "runs/local/artifacts/stage10732_cpp_materialization_execution_packet"

SELECTED_ROOTS = ROOT / "runs/local/artifacts/stage10731_cpp_materialization_candidate_packet/cpp_materialization_selected_roots.jsonl"
CAUSAL_STATES = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_causal_states.jsonl"
EVENTS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_typed_events.jsonl"
MULTITARGET_ROWS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_multitarget_rows.jsonl"
STAGE10731 = ROOT / "runs/local/artifacts/stage10731_cpp_materialization_candidate_packet/cpp_materialization_candidate_packet.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


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


def parse_json_content(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    selected_roots = load_jsonl(SELECTED_ROOTS)
    states = load_jsonl(CAUSAL_STATES)
    events = load_jsonl(EVENTS)
    multitarget_rows = load_jsonl(MULTITARGET_ROWS)
    stage10731 = load_json(STAGE10731)

    state_by_root = {
        row["root_id"]: row
        for row in states
        if row.get("root_id") in {item["root_id"] for item in selected_roots}
    }

    events_by_root: dict[str, list[dict[str, Any]]] = {}
    for row in events:
        root_id = row.get("root_id")
        if root_id not in state_by_root:
            continue
        events_by_root.setdefault(root_id, []).append(row)
    for root_id in events_by_root:
        events_by_root[root_id].sort(key=lambda row: row.get("event_index") or 0)

    rows_by_root: dict[str, list[dict[str, Any]]] = {}
    for row in multitarget_rows:
        root_id = row.get("root_id")
        if root_id not in state_by_root:
            continue
        rows_by_root.setdefault(root_id, []).append(row)

    packet_rows: list[dict[str, Any]] = []
    root_cards: list[dict[str, Any]] = []

    for root in selected_roots:
        root_id = root["root_id"]
        state = state_by_root[root_id]
        final_state = state.get("final_state") or {}
        root_events = events_by_root.get(root_id, [])
        root_rows = rows_by_root.get(root_id, [])

        task_event = next((event for event in root_events if event.get("event_type") == "USER_TASK"), None)
        patch_event = next((event for event in root_events if event.get("event_type") == "PATCH"), None)
        test_event = next((event for event in root_events if event.get("event_type") == "TEST_RESULT"), None)

        root_card = {
            "root_id": root_id,
            "repo_id": root.get("repo_id"),
            "repo_family": root.get("repo_family"),
            "snapshot_id": root.get("snapshot_id"),
            "execution_route": final_state.get("execution_route"),
            "test_selection_route": final_state.get("test_selection_route"),
            "expected_changed_files": final_state.get("expected_changed_files") or [],
            "verification_targets": final_state.get("verification_targets") or [],
            "key_symbols": final_state.get("key_symbols") or [],
            "query_text": state.get("query_text"),
            "user_task_text": task_event.get("content") if task_event else None,
            "patch_artifact_refs": patch_event.get("artifact_refs") if patch_event else [],
            "test_artifact_refs": test_event.get("artifact_refs") if test_event else [],
            "row_ids": [row["row_id"] for row in root_rows],
            "materialization_ready_signals": {
                "has_query_text": bool(state.get("query_text")),
                "has_user_task_event": bool(task_event),
                "has_patch_event": bool(patch_event),
                "has_test_result_event": bool(test_event),
                "has_verifier_outcome_row": any(row.get("target_subtype") == "verifier_outcome" for row in root_rows),
                "has_patch_sketch_row": any(row.get("target_subtype") == "patch_sketch" for row in root_rows),
                "has_repair_intent_row": any(row.get("target_subtype") == "repair_intent" for row in root_rows),
            },
            "anti_cheat_contract": [
                "Do not expose verification target paths as direct answer strings before the candidate set.",
                "Derive candidate paths from changed files, verification targets, and source context rather than copying gold targets into prompts.",
                "Keep these roots root-disjoint from the current reviewed v2.7/v2.8 C/C++ frontier.",
                "Require a maintainer-visible evidence view before any row becomes promotable strict eval.",
            ],
            "next_materialization_actions": [
                "Construct maintainer-visible prompt views from query_text and event evidence.",
                "Generate candidate path competition from changed files, verification targets, and nearby implementation/test surfaces.",
                "Attach rubric, anti-cheat, and gold adjudication before any scoring use.",
            ],
        }
        root_cards.append(root_card)

        for row in root_rows:
            packet_rows.append(
                {
                    "root_id": root_id,
                    "repo_family": root.get("repo_family"),
                    "row_id": row["row_id"],
                    "state_id": row.get("state_id"),
                    "target_family": row.get("target_family"),
                    "target_subtype": row.get("target_subtype"),
                    "target_text": row.get("target_text"),
                    "target_text_parsed": parse_json_content(row.get("target_text")),
                    "materialization_view": {
                        "query_text": state.get("query_text"),
                        "expected_changed_files": final_state.get("expected_changed_files") or [],
                        "verification_targets": final_state.get("verification_targets") or [],
                        "key_symbols": final_state.get("key_symbols") or [],
                    },
                }
            )

    summary = {
        "stage": 10732,
        "stage_name": "stage10732_cpp_materialization_execution_packet",
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "cpp_materialization_execution_packet_ready",
        "claim_scope": [
            "Convert the clean C/C++ root candidates into a direct execution/materialization packet.",
            "Expose the exact state, event, and row artifacts needed for reviewed maintainer-bundle construction.",
            "Keep anti-cheat and promotion boundaries explicit before any of these roots are turned into new strict eval rows.",
        ],
        "headline_findings": [
            f"All {len(root_cards)} selected C/C++ roots have reconstructable query_text plus patch and test event evidence.",
            "The clean roots are not yet promotable maintainer bundles, but they now have a direct execution packet for the next materialization step.",
            "The packet preserves structured targets like verifier_outcome, repair_intent, and patch_sketch while keeping candidate-set construction for the next stage.",
        ],
        "source_packet_metrics": {
            "selected_root_count": len(root_cards),
            "packet_row_count": len(packet_rows),
            "roots_with_query_text": sum(1 for card in root_cards if card["materialization_ready_signals"]["has_query_text"]),
            "roots_with_patch_event": sum(1 for card in root_cards if card["materialization_ready_signals"]["has_patch_event"]),
            "roots_with_test_result_event": sum(1 for card in root_cards if card["materialization_ready_signals"]["has_test_result_event"]),
        },
        "next_best_steps": [
            "Build reviewed maintainer bundles from these packet roots by constructing candidate path competition and maintainer-visible evidence cards.",
            "Use this packet as the first execution-backed C/C++ materialization lane before attempting broader multilingual root-scale promotion.",
            "Keep the quarantined C/C++ roots out of this path until prompt-target leakage is removed.",
        ],
        "sources": {
            "selected_roots": rel(SELECTED_ROOTS),
            "causal_states": rel(CAUSAL_STATES),
            "events": rel(EVENTS),
            "multitarget_rows": rel(MULTITARGET_ROWS),
            "stage10731_packet": rel(STAGE10731),
        },
        "output_files": {
            "summary_json": rel(ARTIFACT_DIR / "cpp_materialization_execution_packet.json"),
            "root_cards_jsonl": rel(ARTIFACT_DIR / "cpp_materialization_root_cards.jsonl"),
            "packet_rows_jsonl": rel(ARTIFACT_DIR / "cpp_materialization_packet_rows.jsonl"),
        },
    }

    write_json(ARTIFACT_DIR / "cpp_materialization_execution_packet.json", summary)
    write_jsonl(ARTIFACT_DIR / "cpp_materialization_root_cards.jsonl", root_cards)
    write_jsonl(ARTIFACT_DIR / "cpp_materialization_packet_rows.jsonl", packet_rows)
    print(ARTIFACT_DIR / "cpp_materialization_execution_packet.json")


if __name__ == "__main__":
    main()

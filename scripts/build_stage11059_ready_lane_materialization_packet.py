#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11059
NAME = "stage11059_ready_lane_materialization_packet"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "ready_lane_materialization_packet.json"
LANE_CARDS_JSONL = OUT_DIR / "ready_lane_cards.jsonl"
ROOT_CARDS_JSONL = OUT_DIR / "ready_root_cards.jsonl"
PACKET_ROWS_JSONL = OUT_DIR / "ready_packet_rows.jsonl"

READY_ROWS = ARTIFACTS / "stage11058_explicit_ledger_conflict_materialization_request" / "ready_request_rows.jsonl"
ROOT_RECORDS = ARTIFACTS / "stage10516_long_context_root_state_compiler" / "compiled_root_records.jsonl"
CAUSAL_STATES = ARTIFACTS / "stage10516_long_context_root_state_compiler" / "compiled_causal_states.jsonl"
EVENTS = ARTIFACTS / "stage10516_long_context_root_state_compiler" / "compiled_typed_events.jsonl"
MULTITARGET_ROWS = ARTIFACTS / "stage10516_long_context_root_state_compiler" / "compiled_multitarget_rows.jsonl"

READY_TARGET_FAMILIES = {
    "python_repository_library_reviewed_next",
    "rust_non_tokenizers_non_alias",
    "parametergolf_verifier_transition",
}


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
            return {"scoreable_now": False, "reason": "visible_target_still_opaque_handle"}
        return {"scoreable_now": False, "reason": "needs_explicit_visible_candidate_ledger"}
    if subtype == "verifier_outcome":
        return {"scoreable_now": True, "reason": "verifier_target_present"}
    if subtype == "retrieve_answer_abstain":
        return {"scoreable_now": True, "reason": "terminal_action_target_present"}
    return {"scoreable_now": False, "reason": "unsupported_target_subtype"}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ready_rows = [
        row
        for row in load_jsonl(READY_ROWS)
        if str(row.get("target_family") or "") in READY_TARGET_FAMILIES
    ]
    ready_rows.sort(key=lambda row: int(row.get("priority") or 999))

    root_records = {str(row.get("root_id") or ""): row for row in load_jsonl(ROOT_RECORDS)}
    states = {str(row.get("root_id") or ""): row for row in load_jsonl(CAUSAL_STATES)}

    root_ids = {
        str(ref.get("root_id") or "")
        for lane in ready_rows
        for ref in list(lane.get("packet_refs") or [])
        if str(ref.get("source_kind") or "") == "seed_queue_root"
    }

    events_by_root: dict[str, list[dict[str, Any]]] = {}
    for row in load_jsonl(EVENTS):
        root_id = str(row.get("root_id") or "")
        if root_id not in root_ids:
            continue
        events_by_root.setdefault(root_id, []).append(row)
    for root_id in events_by_root:
        events_by_root[root_id].sort(key=lambda row: int(row.get("event_index") or 0))

    rows_by_root: dict[str, list[dict[str, Any]]] = {}
    for row in load_jsonl(MULTITARGET_ROWS):
        root_id = str(row.get("root_id") or "")
        if root_id not in root_ids:
            continue
        rows_by_root.setdefault(root_id, []).append(row)

    lane_cards: list[dict[str, Any]] = []
    root_cards: list[dict[str, Any]] = []
    packet_rows: list[dict[str, Any]] = []

    for lane in ready_rows:
        lane_refs = list(lane.get("packet_refs") or [])
        seed_refs = [ref for ref in lane_refs if str(ref.get("source_kind") or "") == "seed_queue_root"]
        reviewed_refs = [ref for ref in lane_refs if str(ref.get("source_kind") or "") == "reviewed_bundle"]
        candidate_refs = list(lane.get("candidate_refs") or [])

        lane_cards.append(
            {
                "priority": lane.get("priority"),
                "lane": lane.get("lane"),
                "target_family": lane.get("target_family"),
                "status": lane.get("status"),
                "objective": lane.get("objective"),
                "why_now": lane.get("why_now"),
                "root_gap_remaining": lane.get("root_gap_remaining"),
                "row_gap_remaining": lane.get("row_gap_remaining"),
                "resolved_root_count": lane.get("resolved_root_count"),
                "resolved_row_count": lane.get("resolved_row_count"),
                "reviewed_bundle_refs": reviewed_refs,
                "seed_root_refs": seed_refs,
                "candidate_refs": candidate_refs,
                "notes": list(lane.get("notes") or []),
                "materialization_contract": [
                    "Use reviewed bundles as semantic anchors, not as same-surface row replay.",
                    "Project seed roots into fresh explicit-ledger or verifier-transition rows before any training use.",
                    "Keep all new rows root-disjoint from strict promoted surfaces until anti-cheat review passes.",
                ],
            }
        )

        for ref in seed_refs:
            root_id = str(ref.get("root_id") or "")
            root = root_records.get(root_id)
            state = states.get(root_id)
            if root is None or state is None:
                root_cards.append(
                    {
                        "lane": lane.get("lane"),
                        "target_family": lane.get("target_family"),
                        "root_id": root_id,
                        "repo_family": ref.get("repo_family"),
                        "language_family": ref.get("language_family"),
                        "compiled_state_present": False,
                        "reason": "missing_compiled_root_or_state",
                    }
                )
                continue

            lane_root_rows = sorted(
                rows_by_root.get(root_id, []),
                key=lambda row: str(row.get("target_subtype") or row.get("row_id") or ""),
            )
            final_state = dict(state.get("final_state") or {})
            task_counts = Counter(str(row.get("target_subtype") or "unknown") for row in lane_root_rows)
            scoreability_counts = Counter()

            task_event = next((event for event in events_by_root.get(root_id, []) if event.get("event_type") == "USER_TASK"), None)
            test_event = next((event for event in events_by_root.get(root_id, []) if event.get("event_type") == "TEST_RESULT"), None)
            retrieve_event = next(
                (
                    event
                    for event in events_by_root.get(root_id, [])
                    if event.get("event_type") in {"SEARCH_RESULT", "FILE_READ", "COMMAND_RESULT"}
                ),
                None,
            )

            for row in lane_root_rows:
                decision = scoreability_for(row, state)
                scoreability_counts["scoreable" if decision["scoreable_now"] else "blocked"] += 1
                packet_rows.append(
                    {
                        "lane": lane.get("lane"),
                        "target_family": lane.get("target_family"),
                        "priority": lane.get("priority"),
                        "root_id": root_id,
                        "repo_family": ref.get("repo_family"),
                        "repo_id": ref.get("repo_id"),
                        "language_family": ref.get("language_family"),
                        "row_id": row.get("row_id"),
                        "state_id": row.get("state_id"),
                        "target_subtype": row.get("target_subtype"),
                        "target_family_row": row.get("target_family"),
                        "target_text": row.get("target_text"),
                        "target_text_parsed": parse_json_text(row.get("target_text")),
                        "query_text": state.get("query_text"),
                        "visible_evidence_ids": list(state.get("visible_evidence_ids") or []),
                        "verification_targets": list(final_state.get("verification_targets") or []),
                        "expected_changed_files": list(final_state.get("expected_changed_files") or []),
                        "key_symbols": list(final_state.get("key_symbols") or [])[:16],
                        "scoreability": decision,
                        "source_ref": ref,
                    }
                )

            root_cards.append(
                {
                    "lane": lane.get("lane"),
                    "target_family": lane.get("target_family"),
                    "priority": lane.get("priority"),
                    "root_id": root_id,
                    "repo_family": ref.get("repo_family"),
                    "repo_id": ref.get("repo_id"),
                    "language_family": ref.get("language_family"),
                    "quality_tier": ref.get("quality_tier"),
                    "source_family_id": ref.get("source_family_id"),
                    "verifier_id": ref.get("verifier_id"),
                    "compiled_state_present": True,
                    "task_family": root.get("task_family"),
                    "split_component": root.get("split_component"),
                    "query_text": state.get("query_text"),
                    "user_task_text": task_event.get("content") if task_event else None,
                    "retrieval_event_artifact_refs": list(retrieve_event.get("artifact_refs") or []) if retrieve_event else [],
                    "test_event_artifact_refs": list(test_event.get("artifact_refs") or []) if test_event else [],
                    "visible_evidence_ids": list(state.get("visible_evidence_ids") or []),
                    "verification_targets": list(final_state.get("verification_targets") or []),
                    "expected_changed_files": list(final_state.get("expected_changed_files") or []),
                    "key_symbols": list(final_state.get("key_symbols") or []),
                    "row_ids": [str(row.get("row_id") or "") for row in lane_root_rows],
                    "row_task_counts": dict(sorted(task_counts.items())),
                    "scoreability_counts": dict(sorted(scoreability_counts.items())),
                    "anti_cheat_contract": [
                        "Do not reuse these compiled root siblings in strict eval until fresh explicit-ledger or verifier-transition rows are reviewed.",
                        "Treat decisive_evidence targets as blocked until packet-visible candidate ledgers exist.",
                        "Preserve verifier anchors and selected-test semantics when projecting new rows.",
                    ],
                }
            )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "ready_lane_materialization_packet_prepared",
        "claim_scope": [
            "Turn the stage11058 ready lanes into a concrete materialization packet with compiled root/state coverage where available.",
            "Separate reviewed semantic anchors from seed-root causal states so new row construction can proceed without same-surface replay.",
            "Make scoreability explicit for each compact target type before the next row-construction stage.",
        ],
        "headline_findings": [
            f"{len(lane_cards)} ready lanes now have direct packet definitions for fresh materialization work.",
            f"{sum(1 for row in root_cards if row.get('compiled_state_present') is True)} seed roots already have compiled root/state/event coverage and can be projected immediately.",
            "Across the ready lanes, verifier_outcome and retrieve_answer_abstain remain directly scoreable, while decisive_evidence still requires explicit visible candidate ledgers.",
        ],
        "metrics": {
            "ready_lane_count": len(lane_cards),
            "compiled_root_count": sum(1 for row in root_cards if row.get("compiled_state_present") is True),
            "missing_compiled_root_count": sum(1 for row in root_cards if row.get("compiled_state_present") is not True),
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
            "Project fresh explicit-ledger decisive-evidence rows for repository_library and Rust seed roots.",
            "Project fresh verifier-transition rows for parametergolf seed roots using the reviewed bundle as the semantic anchor.",
            "Keep code_assist and agentkernel on the discovery queue until they have more independent roots.",
        ],
        "source_artifacts": {
            "ready_request_rows": rel(READY_ROWS),
            "root_records": rel(ROOT_RECORDS),
            "causal_states": rel(CAUSAL_STATES),
            "events": rel(EVENTS),
            "multitarget_rows": rel(MULTITARGET_ROWS),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "lane_cards_jsonl": rel(LANE_CARDS_JSONL),
            "root_cards_jsonl": rel(ROOT_CARDS_JSONL),
            "packet_rows_jsonl": rel(PACKET_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(LANE_CARDS_JSONL, lane_cards)
    write_jsonl(ROOT_CARDS_JSONL, root_cards)
    write_jsonl(PACKET_ROWS_JSONL, packet_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

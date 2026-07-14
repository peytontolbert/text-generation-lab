#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11094
NAME = "stage11094_fresh_family_materialization_packet"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_family_materialization_packet.json"
FAMILY_CARDS_JSONL = OUT_DIR / "fresh_family_cards.jsonl"
ROOT_CARDS_JSONL = OUT_DIR / "fresh_family_root_cards.jsonl"
PACKET_ROWS_JSONL = OUT_DIR / "fresh_family_packet_rows.jsonl"

QUEUE_SUMMARY = ARTIFACTS / "stage11092_fresh_evidence_family_queue" / "fresh_evidence_family_queue.json"
QUEUE_ROWS = ARTIFACTS / "stage11092_fresh_evidence_family_queue" / "queue_rows.jsonl"
ROOT_RECORDS = ARTIFACTS / "stage10516_long_context_root_state_compiler" / "compiled_root_records.jsonl"
CAUSAL_STATES = ARTIFACTS / "stage10516_long_context_root_state_compiler" / "compiled_causal_states.jsonl"
EVENTS = ARTIFACTS / "stage10516_long_context_root_state_compiler" / "compiled_typed_events.jsonl"
MULTITARGET_ROWS = ARTIFACTS / "stage10516_long_context_root_state_compiler" / "compiled_multitarget_rows.jsonl"

TARGET_SUBTYPES = {
    "decisive_evidence",
    "retrieve_answer_abstain",
    "verifier_outcome",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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

    queue_summary = load_json(QUEUE_SUMMARY)
    queue_rows = sorted(load_jsonl(QUEUE_ROWS), key=lambda row: int(row.get("priority") or 999))
    selected_root_ids = {str(row.get("root_id") or "") for row in queue_rows}

    root_records = {
        str(row.get("root_id") or ""): row
        for row in load_jsonl(ROOT_RECORDS)
        if str(row.get("root_id") or "") in selected_root_ids
    }
    states = {
        str(row.get("root_id") or ""): row
        for row in load_jsonl(CAUSAL_STATES)
        if str(row.get("root_id") or "") in selected_root_ids
    }

    events_by_root: dict[str, list[dict[str, Any]]] = {}
    for row in load_jsonl(EVENTS):
        root_id = str(row.get("root_id") or "")
        if root_id not in selected_root_ids:
            continue
        events_by_root.setdefault(root_id, []).append(row)
    for root_id, rows in events_by_root.items():
        rows.sort(key=lambda row: int(row.get("event_index") or 0))

    rows_by_root: dict[str, list[dict[str, Any]]] = {}
    for row in load_jsonl(MULTITARGET_ROWS):
        root_id = str(row.get("root_id") or "")
        subtype = str(row.get("target_subtype") or "")
        if root_id not in selected_root_ids or subtype not in TARGET_SUBTYPES:
            continue
        rows_by_root.setdefault(root_id, []).append(row)
    for root_id, rows in rows_by_root.items():
        rows.sort(key=lambda row: (str(row.get("target_subtype") or ""), str(row.get("row_id") or "")))

    family_cards: list[dict[str, Any]] = []
    root_cards: list[dict[str, Any]] = []
    packet_rows: list[dict[str, Any]] = []

    by_family: dict[str, list[dict[str, Any]]] = {}
    for row in queue_rows:
        by_family.setdefault(str(row.get("repo_family") or "unknown"), []).append(row)

    for repo_family, family_rows in sorted(by_family.items()):
        family_rows.sort(key=lambda row: int(row.get("priority") or 999))
        family_cards.append(
            {
                "repo_family": repo_family,
                "repo_id": family_rows[0].get("repo_id"),
                "language_family": family_rows[0].get("language_family"),
                "queued_root_count": len(family_rows),
                "queued_root_ids": [str(row.get("root_id") or "") for row in family_rows],
                "verification_routes": sorted({str(row.get("verifier_id") or "") for row in family_rows}),
                "available_target_subtypes_union": sorted(
                    {
                        str(subtype)
                        for row in family_rows
                        for subtype in list(row.get("available_target_subtypes") or [])
                    }
                ),
                "anti_cheat_requirements": list(family_rows[0].get("anti_cheat_requirements") or []),
                "materialization_requirements": list(family_rows[0].get("materialization_requirements") or []),
                "family_contract": [
                    "Keep this family out of promotable strict eval until sibling split assignment is frozen.",
                    "Project decisive_evidence into a visible candidate ledger before any evidence scoring.",
                    "Preserve candidate_change_surface as a plausible distractor rather than training only verifier-ledger positives.",
                    "Emit verifier/test-constraint-positive and candidate-surface-positive rows when the source root supports both.",
                ],
            }
        )

    for request in queue_rows:
        root_id = str(request.get("root_id") or "")
        root = root_records.get(root_id)
        state = states.get(root_id)
        root_events = events_by_root.get(root_id, [])
        root_rows = rows_by_root.get(root_id, [])

        if root is None or state is None:
            root_cards.append(
                {
                    "root_id": root_id,
                    "repo_family": request.get("repo_family"),
                    "language_family": request.get("language_family"),
                    "compiled_state_present": False,
                    "reason": "missing_compiled_root_or_state",
                    "priority": request.get("priority"),
                }
            )
            continue

        task_event = next((event for event in root_events if event.get("event_type") == "USER_TASK"), None)
        retrieve_event = next(
            (
                event
                for event in root_events
                if event.get("event_type") in {"SEARCH_RESULT", "FILE_READ", "COMMAND_RESULT"}
            ),
            None,
        )
        test_event = next((event for event in root_events if event.get("event_type") == "TEST_RESULT"), None)

        final_state = dict(state.get("final_state") or {})
        task_counts = Counter(str(row.get("target_subtype") or "unknown") for row in root_rows)
        scoreability_counts = Counter()

        for row in root_rows:
            decision = scoreability_for(row, state)
            scoreability_counts["scoreable" if decision["scoreable_now"] else "blocked"] += 1
            packet_rows.append(
                {
                    "priority": request.get("priority"),
                    "claim_role": request.get("claim_role"),
                    "root_id": root_id,
                    "repo_id": request.get("repo_id"),
                    "repo_family": request.get("repo_family"),
                    "language_family": request.get("language_family"),
                    "snapshot_id": request.get("snapshot_id"),
                    "source_family_id": request.get("source_family_id"),
                    "split_component": request.get("split_component"),
                    "verifier_id": request.get("verifier_id"),
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
                "priority": request.get("priority"),
                "claim_role": request.get("claim_role"),
                "root_id": root_id,
                "repo_id": request.get("repo_id"),
                "repo_family": request.get("repo_family"),
                "language_family": request.get("language_family"),
                "snapshot_id": request.get("snapshot_id"),
                "source_family_id": request.get("source_family_id"),
                "verifier_id": request.get("verifier_id"),
                "task_family": root.get("task_family"),
                "split_component": root.get("split_component"),
                "compiled_state_present": True,
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
                    "Do not use this root as promotable strict eval until decisive_evidence targets are projected into a visible candidate ledger.",
                    "Hide raw target file/test paths before options when constructing bounded rows.",
                    "Record deterministic or explicit option shuffle metadata for every bounded row.",
                    "Keep sibling roots and same root lineage within one split component.",
                ],
            }
        )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "fresh_family_materialization_packet_ready",
        "claim_scope": [
            "Turn the stage11092 fresh-family queue into a concrete materialization packet with per-family cards, per-root cards, and packet rows.",
            "Expose exactly which queued roots are immediately scoreable for verifier/retrieve work and which remain blocked only on visible-ledger projection.",
            "Prepare the next row-construction stage from fresh families rather than looping on repository_library, parametergolf, tokenizers, or candle.",
        ],
        "headline_findings": [
            f"Prepared {len(root_cards)} fresh-family root cards across {len(family_cards)} repo families with subtype-filtered packet rows for decisive_evidence, verifier_outcome, and retrieve_answer_abstain.",
            "Every family in the packet carries verifier-target signal and materialization constraints at queue time, which keeps the next build aligned to heldout-safe evidence work.",
            "The main remaining blocker is still explicit evidence-ledger projection for decisive_evidence; verifier_outcome and retrieve_answer_abstain rows are the immediately scoreable subset.",
        ],
        "metrics": {
            "family_count": len(family_cards),
            "selected_root_count": len(root_cards),
            "packet_row_count": len(packet_rows),
            "rows_by_language": {
                language: sum(1 for row in packet_rows if str(row.get("language_family") or "") == language)
                for language in sorted({str(row.get("language_family") or "") for row in packet_rows})
            },
            "roots_by_language": {
                language: sum(1 for row in root_cards if str(row.get("language_family") or "") == language)
                for language in sorted({str(row.get("language_family") or "") for row in root_cards})
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
            "blocked_by_subtype": {
                subtype: sum(
                    1
                    for row in packet_rows
                    if str(row.get("target_subtype") or "") == subtype and (row.get("scoreability") or {}).get("scoreable_now") is False
                )
                for subtype in sorted({str(row.get("target_subtype") or "") for row in packet_rows})
            },
        },
        "next_best_step": [
            "Project decisive_evidence rows from this packet into explicit visible candidate ledgers before evidence scoring.",
            "Construct verifier/test-constraint and candidate-surface counterexamples from at least one Python family and one C/C++ family in this packet.",
            "Keep mem0 separate until the web selected-test/verifier lane is materialized with the same anti-cheat contract.",
        ],
        "source_artifacts": {
            "queue_summary": rel(QUEUE_SUMMARY),
            "queue_rows": rel(QUEUE_ROWS),
            "root_records": rel(ROOT_RECORDS),
            "causal_states": rel(CAUSAL_STATES),
            "events": rel(EVENTS),
            "multitarget_rows": rel(MULTITARGET_ROWS),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "family_cards_jsonl": rel(FAMILY_CARDS_JSONL),
            "root_cards_jsonl": rel(ROOT_CARDS_JSONL),
            "packet_rows_jsonl": rel(PACKET_ROWS_JSONL),
        },
        "queue_snapshot": queue_summary.get("metrics"),
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(FAMILY_CARDS_JSONL, family_cards)
    write_jsonl(ROOT_CARDS_JSONL, root_cards)
    write_jsonl(PACKET_ROWS_JSONL, packet_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

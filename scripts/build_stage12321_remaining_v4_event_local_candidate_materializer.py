#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12321_remaining_v4_event_local_candidate_materializer"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12271 = ROOT / "runs/local/artifacts/stage12271_horizon_slice_miner_pilot/horizon_slice_candidates.jsonl"
STAGE12316 = ROOT / "runs/local/artifacts/stage12316_transition_local_event_joiner/transition_local_event_join_records.jsonl"
STAGE12317 = ROOT / "runs/local/artifacts/stage12317_event_local_observation_train_support_500/event_local_observation_train_support_tasks.jsonl"
STAGE12318 = ROOT / "runs/local/artifacts/stage12318_event_local_observation_package_qc/event_local_observation_qc_records.jsonl"

MAX_PARENT_WINDOWS = 98
MAX_PARENT_WINDOWS_PER_CHAT = 20


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    used_windows = {row.get("task_window_id") for row in read_jsonl(STAGE12316)}
    qc_by_window = defaultdict(list)
    for row in read_jsonl(STAGE12317):
        task_window_id = (row.get("source_refs") or {}).get("task_window_id")
        if task_window_id:
            qc_by_window[task_window_id].append(row.get("row_id"))
    stage12318_status_by_source = {
        row.get("source_row_id"): row.get("review_status")
        for row in read_jsonl(STAGE12318)
    }

    v4_by_window: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in read_jsonl(STAGE12271):
        if row.get("horizon_label") != "H10_patch_verifier_loop":
            continue
        if (row.get("admission") or {}).get("validation_level") != "V4_patch_verifier_candidate":
            continue
        task_window_id = (row.get("source_refs") or {}).get("task_window_id")
        if task_window_id:
            v4_by_window[task_window_id].append(row)

    candidates = []
    for task_window_id, rows in v4_by_window.items():
        if task_window_id in used_windows:
            continue
        rows.sort(key=lambda row: ((row.get("lineage") or {}).get("child_loop_index") or 0, row.get("horizon_slice_id") or ""))
        primary = rows[0]
        refs = primary.get("source_refs") or {}
        linked = []
        for row_id in qc_by_window.get(task_window_id, []):
            linked.append({"stage12317_row_id": row_id, "stage12318_review_status": stage12318_status_by_source.get(row_id)})
        candidates.append(
            {
                "stage": STAGE,
                "record_type": "remaining_v4_parent_event_local_candidate",
                "task_window_id": task_window_id,
                "primary_horizon_slice_id": primary.get("horizon_slice_id"),
                "child_loop_slice_ids": [row.get("horizon_slice_id") for row in rows],
                "v4_slice_count": len(rows),
                "source_refs": {
                    "chat_id_hash_source": refs.get("chat_id"),
                    "session_id_hint_hash_source": refs.get("session_id_hint"),
                    "source_file_hash_compat": refs.get("source_file_hash_compat"),
                    "snapshot_id": refs.get("snapshot_id"),
                    "raw_text_emitted": False,
                    "raw_command_text_emitted": False,
                    "raw_tool_output_emitted": False,
                    "raw_patch_body_emitted": False,
                },
                "lineage": {
                    "root_lineage_key": (primary.get("lineage") or {}).get("root_lineage_key"),
                    "split_group_id": (primary.get("lineage") or {}).get("split_group_id"),
                    "source_lineage_key": (primary.get("lineage") or {}).get("source_lineage_key"),
                },
                "linked_event_local_qc_refs": linked,
                "admission": {
                    "training_allowed": False,
                    "train_support_allowed": False,
                    "strict_eval_eligible": False,
                    "source_heldout_admissible": False,
                    "level3_admitted": False,
                    "patch_trace_admitted": False,
                },
                "blocked_reasons": [
                    "requires_stage12316_style_event_local_extraction_or_qc_link",
                    "repo_family_not_semantically_recovered",
                    "state_delta_needs_semantic_review",
                    "policy_label_not_reviewed",
                    "not_level3_repair_causality",
                ],
            }
        )

    candidates.sort(key=lambda row: (row["source_refs"].get("chat_id_hash_source") or "", row.get("task_window_id") or ""))
    selected = []
    per_chat: Counter[str] = Counter()
    for row in candidates:
        chat = row["source_refs"].get("chat_id_hash_source") or "unknown"
        if per_chat[chat] >= MAX_PARENT_WINDOWS_PER_CHAT:
            continue
        selected.append(row)
        per_chat[chat] += 1
        if len(selected) >= MAX_PARENT_WINDOWS:
            break

    write_jsonl(OUT / "remaining_v4_event_local_parent_candidates.jsonl", selected)

    linked_counts = Counter()
    slice_counts = Counter()
    for row in selected:
        slice_counts[str(row.get("v4_slice_count"))] += 1
        if row.get("linked_event_local_qc_refs"):
            linked_counts["has_stage12317_or_12318_link"] += 1
        else:
            linked_counts["needs_stage12316_extraction"] += 1
    summary = {
        "stage": STAGE,
        "decision": "remaining_v4_parent_candidates_materialized_training_blocked",
        "claim_boundary": "Parent-normalized V4 candidate materialization only. No train/eval/Level-3 admission.",
        "training_allowed": False,
        "records_emitted": len(selected),
        "target_records": MAX_PARENT_WINDOWS,
        "admitted_training_tasks": 0,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "v4_total_parent_windows": len(v4_by_window),
        "v4_used_by_stage12316": len(used_windows & set(v4_by_window)),
        "v4_remaining_parent_windows": len(set(v4_by_window) - used_windows),
        "v4_slice_count_distribution": dict(slice_counts),
        "linked_qc_counts": dict(linked_counts),
        "per_chat_selected_top": dict(per_chat.most_common(20)),
        "caps": {
            "MAX_PARENT_WINDOWS": MAX_PARENT_WINDOWS,
            "MAX_PARENT_WINDOWS_PER_CHAT": MAX_PARENT_WINDOWS_PER_CHAT,
            "max_records_per_task_window": 1,
        },
        "next_stage": {
            "stage": "stage12323_v4_event_local_extraction_and_review",
            "purpose": "Run Stage12316-style extraction or link existing Stage12317/12318 review records, then feed Stage12320 admission.",
            "training_allowed": False,
        },
    }
    (OUT / "remaining_v4_event_local_candidate_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "REMAINING_V4_EVENT_LOCAL_CANDIDATE_MATERIALIZER_STAGE12321.md").write_text(
        "# Stage12321 Remaining V4 Event-Local Candidate Materializer\n\n"
        "This stage emits one parent-normalized candidate per unused V4 task window. It does not admit training rows.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

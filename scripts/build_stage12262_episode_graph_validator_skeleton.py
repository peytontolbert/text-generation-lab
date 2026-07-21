#!/usr/bin/env python3
"""Build Stage12262 fail-closed episode graph validator skeleton/preflight.

This validates the current Stage12260 task-window supply against the
Stage12261 episode-graph admission principles. It does not generate
episode_graph_candidate records and does not admit roots.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12262_episode_graph_validator_skeleton"
WINDOWS = ROOT / "runs/local/artifacts/stage12260_codex_chat_task_boundary_miner/codex_task_windows.jsonl"


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            yield line_no, json.loads(line)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def main() -> int:
    windows = [row for _, row in iter_jsonl(WINDOWS) or []]
    blocked_rows: list[dict[str, Any]] = []
    warning_rows: list[dict[str, Any]] = []
    blocked_counts: Counter[str] = Counter()
    dominance_all: Counter[str] = Counter()
    dominance_l2: Counter[str] = Counter()
    overlaps = 0
    prev_end_by_chat: dict[str, int] = {}

    for row in windows:
        chat_id = str(row.get("chat_id") or "")
        dominance_all[chat_id] += 1
        if row.get("training_potential") == "level_2_patch_and_verifier_refs_needs_state_join":
            dominance_l2[chat_id] += 1
        start = int(row.get("start_line") or 0)
        end = int(row.get("end_line") or 0)
        if chat_id in prev_end_by_chat and start <= prev_end_by_chat[chat_id]:
            overlaps += 1
            blocked_counts["overlapping_task_window_without_parent_child_relation"] += 1
        prev_end_by_chat[chat_id] = max(prev_end_by_chat.get(chat_id, 0), end)

        reasons: list[str] = []
        warnings: list[str] = []
        if not row.get("source_root_label"):
            reasons.append("source_root_label_missing")
        if not row.get("snapshot_id"):
            reasons.append("snapshot_id_missing")
        if not row.get("source_file_hash_compat"):
            reasons.append("source_file_hash_compat_missing")
        if row.get("training_potential") == "level_2_patch_and_verifier_refs_needs_state_join":
            reasons.append("level2_only_patch_and_verifier_copresent_state_join_missing")
            reasons.append("patch_verifier_causality_not_proven")
        if row.get("has_verifier_like_ref") and not row.get("has_command_observation"):
            reasons.append("verifier_like_ref_without_paired_observation")
        command_families = row.get("command_family_counts") or {}
        if row.get("has_verifier_like_ref") and command_families.get("verifier_or_execution", 0) == 0 and command_families.get("python_execution", 0) > 0:
            warnings.append("verifier_signal_may_be_generic_python_execution")
        if row.get("terminal_status") == "no_terminal_event":
            reasons.append("terminal_event_missing")
        if row.get("boundary_confidence") != "lifecycle_exact":
            reasons.append("non_lifecycle_boundary")

        for reason in reasons:
            blocked_counts[reason] += 1
        if reasons:
            blocked_rows.append(
                {
                    "task_window_id": row.get("task_window_id"),
                    "chat_id": chat_id,
                    "training_potential": row.get("training_potential"),
                    "blocked_reason_codes": reasons,
                    "start_line": row.get("start_line"),
                    "end_line": row.get("end_line"),
                    "training_allowed": False,
                }
            )
        elif warnings:
            warning_rows.append(
                {
                    "task_window_id": row.get("task_window_id"),
                    "chat_id": chat_id,
                    "warning_codes": warnings,
                    "training_allowed": False,
                }
            )

    l2_total = sum(dominance_l2.values())
    top_l2 = dominance_l2.most_common(10)
    top2_l2 = sum(count for _, count in top_l2[:2])
    top2_l2_share = (top2_l2 / l2_total) if l2_total else 0.0
    dominance_blocked = top2_l2_share > 0.50
    if dominance_blocked:
        blocked_counts["level2_pool_session_dominance_top2_gt_50pct"] += 1

    validation_levels = {
        "V0_source_envelope": {
            "status": "fail",
            "reason": "source_root_label_missing_on_current_stage12260_windows",
        },
        "V1_ordering_pairing": {
            "status": "pass_with_warnings" if overlaps == 0 else "fail",
            "overlap_count": overlaps,
        },
        "V2_task_boundary": {
            "status": "pass_as_boundary_candidates_only",
            "note": "Lifecycle boundaries exist, but they are not admitted episode graphs.",
        },
        "V3_causal_tuple": {
            "status": "fail",
            "reason": "state_before/candidate_actions/chosen_action/state_update/stop_continue not materialized.",
        },
        "V4_patch_verifier": {
            "status": "fail",
            "reason": "patch and verifier refs are co-present only; causal ordering and same-source verifier relevance are not proven.",
        },
        "V5_admission_qc": {
            "status": "fail",
            "reason": "dominance, dedupe, source-root repair, leak/protected-overlap, and repo/language caps not complete.",
        },
    }

    summary = {
        "stage": STAGE,
        "artifact_type": "episode_graph_validator_skeleton_preflight",
        "decision": "validator_ready_stage12260_not_admissible_training_blocked",
        "training_allowed": False,
        "claim_boundary": (
            "Validator/preflight artifact only. It validates task-window readiness against episode-graph levels. "
            "It emits no episode_graph_candidate records, no root admissions, and no training rows."
        ),
        "input": {
            "task_windows_path": str(WINDOWS.relative_to(ROOT)),
            "task_windows": len(windows),
        },
        "counts": {
            "blocked_window_rows": len(blocked_rows),
            "warning_window_rows": len(warning_rows),
            "blocked_reason_counts": dict(blocked_counts),
            "task_window_overlap_count": overlaps,
            "all_window_top_chats": dominance_all.most_common(10),
            "level2_patch_verifier_total": l2_total,
            "level2_top_chats": top_l2,
            "level2_top2_share": top2_l2_share,
            "dominance_blocked": dominance_blocked,
        },
        "validation_levels": validation_levels,
        "must_fix_before_candidate_projection": [
            "Repair Stage12260 or Stage12261 projection to carry source_root_label/source adapter fields.",
            "Do not promote patch+verifier co-presence to causality.",
            "Add candidate state_before/chosen_action/observation/state_update/stop_continue materialization.",
            "Apply max-per-chat/session caps before GPT review or admission.",
            "Separate broad build/generic python execution from selected verifier evidence.",
        ],
        "recommended_next_stage": {
            "stage": "stage12263_high_value_window_profiler",
            "scope": "profile/cap the 2059 patch+verifier-ref windows, no admission",
            "constraints": {
                "max_per_chat_for_audit": 3,
                "require_source_root_repair": True,
                "training_allowed": False,
            },
        },
    }

    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", summary)
    write_json(out_dir / "episode_graph_validator_skeleton_preflight.json", summary)
    write_jsonl(out_dir / "blocked_task_windows.jsonl", blocked_rows)
    if warning_rows:
        write_jsonl(out_dir / "warning_task_windows.jsonl", warning_rows)
    md = f"""# Stage12262 Episode Graph Validator Skeleton

## Decision

`{summary["decision"]}`

No training is allowed.

## Critical Findings

- Stage12260 windows: `{len(windows)}`
- Missing `source_root_label`: `{blocked_counts.get('source_root_label_missing', 0)}`
- Level-2 patch+verifier-ref windows: `{l2_total}`
- Top-2 chat share of level-2 pool: `{top2_l2_share:.3f}`
- Dominance blocked: `{dominance_blocked}`

Stage12260 is useful source segmentation, but not admissible episode-graph data yet.
"""
    write_text(out_dir / "EPISODE_GRAPH_VALIDATOR_SKELETON_STAGE12262.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "blocked_task_windows.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

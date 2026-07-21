#!/usr/bin/env python3
"""Build Stage12271 horizon slice miner pilot.

Mines capped horizon-slice candidates from Codex task windows using metadata and
paired tool observations only. No root admission or training rows are emitted.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12271_horizon_slice_miner_pilot"
WINDOWS = ROOT / "runs/local/artifacts/stage12260_codex_chat_task_boundary_miner/codex_task_windows.jsonl"
PAIRS = ROOT / "runs/local/artifacts/stage12259_codex_tool_call_observation_pairer/tool_call_observation_pairs.jsonl"
OUT_DIR = ROOT / f"runs/local/artifacts/{STAGE}"
SUMMARY_PATH = ROOT / f"runs/summaries/{STAGE}.json"

VERIFIER_HEADS = {
    "pytest", "ctest", "cargo", "npm", "pnpm", "yarn", "node", "npx", "make", "cmake", "python", "python3",
}
INSPECT_HEADS = {"rg", "grep", "find", "sed", "cat", "ls", "jq", "tail", "head", "nl", "git", "pwd"}
MAX_PARENT_WINDOWS = 200
MAX_PARENT_WINDOWS_PER_CHAT = 20
MAX_SLICES_PER_PARENT = 4


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if line:
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


def action_type(tool: str | None, head: str | None) -> str:
    head = head or ""
    if tool == "apply_patch":
        return "patch"
    if head in INSPECT_HEADS:
        return "inspect"
    if head in VERIFIER_HEADS or "test" in head or "pytest" in head:
        return "verify"
    return "run"


def build_pair_index() -> dict[str, list[dict[str, Any]]]:
    by_chat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for _, row in iter_jsonl(PAIRS):
        chat_id = row.get("chat_id")
        if not chat_id:
            continue
        call_line = int(row.get("call_line_number") or 0)
        output_line = int(row.get("output_line_number") or 0)
        tool = row.get("tool_name")
        head = row.get("command_head")
        rec = {
            "tool_pair_ref": stable_id("tool_pair_ref", chat_id, row.get("call_id"), call_line, output_line),
            "chat_id": chat_id,
            "tool_name": tool,
            "command_head": head,
            "action_type": action_type(tool, head),
            "call_event_id": row.get("call_event_id"),
            "output_event_id": row.get("output_event_id"),
            "call_line_number": call_line,
            "output_line_number": output_line,
            "arguments_digest": row.get("arguments_digest"),
            "output_digest": row.get("output_digest"),
            "raw_arguments_emitted": False,
            "raw_output_emitted": False,
        }
        by_chat[chat_id].append(rec)
    for rows in by_chat.values():
        rows.sort(key=lambda r: (r["call_line_number"], r["output_line_number"], r["tool_pair_ref"]))
    return by_chat


def candidate_action_set(actions: list[dict[str, Any]], idx: int, radius: int = 2, *, include_future: bool = False) -> list[dict[str, Any]]:
    lo = max(0, idx - radius)
    hi = min(len(actions), idx + radius + 1) if include_future else idx + 1
    out = []
    for j, act in enumerate(actions[lo:hi], lo):
        out.append({
            "action_id": stable_id("action_ref", act["chat_id"], act["tool_pair_ref"]),
            "action_type": act["action_type"],
            "tool_pair_ref": act["tool_pair_ref"],
            "command_head": act.get("command_head"),
            "position_role": "chosen" if j == idx else "nearby_candidate",
        })
    return out


def allowed_projection_families(horizon: str) -> list[str]:
    if horizon == "H1_next_action":
        return ["next_action", "candidate_action_rank", "state_update"]
    if horizon == "H3_micro_loop":
        return ["verifier_interpretation", "continue_or_stop", "evidence_role"]
    if horizon == "H10_patch_verifier_loop":
        return ["patch_selection", "verifier_transition", "repair_vs_continue"]
    return []


def make_slice(
    window: dict[str, Any],
    actions: list[dict[str, Any]],
    idx: int,
    horizon: str,
    reason: str,
    child_loop_index: int = 0,
    verifier_idx: int | None = None,
) -> dict[str, Any]:
    chosen = actions[idx]
    prev_action = actions[idx - 1] if idx > 0 else None
    next_action = actions[idx + 1] if idx + 1 < len(actions) else None
    split_group_id = stable_id(
        "split_group",
        window.get("chat_id"),
        window.get("session_id_hint"),
        window.get("source_file_hash_compat"),
        window.get("source_root_label"),
    )
    parent_key = stable_id("root_lineage", split_group_id, window.get("task_window_id"))
    transition_id = stable_id("transition", parent_key, horizon, idx, chosen.get("tool_pair_ref"), chosen.get("output_digest"))
    validation_level = "V4_patch_verifier_candidate" if horizon == "H10_patch_verifier_loop" else "V3_horizon_slice_candidate"
    return {
        "schema_version": "horizon_slice_candidate_v1",
        "stage": STAGE,
        "horizon_slice_id": stable_id("horizon_slice", transition_id),
        "horizon_label": horizon,
        "selection_reason": reason,
        "source_refs": {
            "snapshot_id": window.get("snapshot_id"),
            "chat_id": window.get("chat_id"),
            "session_id_hint": window.get("session_id_hint"),
            "task_window_id": window.get("task_window_id"),
            "source_file_hash_compat": window.get("source_file_hash_compat"),
            "source_root_label": window.get("source_root_label"),
            "event_span_refs": {
                "line_start": window.get("start_line"),
                "line_end": window.get("end_line"),
                "start_event_id": window.get("start_event_id"),
                "terminal_event_id": window.get("terminal_event_id"),
            },
        },
        "lineage": {
            "source_lineage_key": stable_id("source_lineage", window.get("snapshot_id"), window.get("source_file_hash_compat")),
            "root_lineage_key": parent_key,
            "split_group_id": split_group_id,
            "episode_id": stable_id("episode", parent_key, child_loop_index),
            "child_loop_index": child_loop_index,
            "transition_id": transition_id,
            "dedupe_cluster_id": stable_id("dedupe", parent_key, chosen.get("action_type"), chosen.get("command_head")),
            "sibling_loss_group": transition_id,
            "projection_loss_weight_cap": 1.0,
        },
        "state_before": {
            "state_before_ref": stable_id("state_before", transition_id, prev_action.get("tool_pair_ref") if prev_action else "window_start"),
            "previous_action_ref": prev_action.get("tool_pair_ref") if prev_action else None,
            "raw_content_emitted": False,
        },
        "candidate_action_set": {
            "status": "materialized_from_prefix_actions",
            "actions": candidate_action_set(actions, idx, include_future=False),
            "future_actions_masked": True,
        },
        "chosen_action": {
            "action_id": stable_id("action_ref", chosen["chat_id"], chosen["tool_pair_ref"]),
            "action_type": chosen["action_type"],
            "tool_pair_ref": chosen["tool_pair_ref"],
            "command_head": chosen.get("command_head"),
        },
        "observation": {
            "observation_ref": stable_id("observation", chosen.get("tool_pair_ref"), chosen.get("output_digest")),
            "tool_pair_ref": chosen.get("tool_pair_ref"),
            "output_digest": chosen.get("output_digest"),
            "raw_output_emitted": False,
            "model_visible_for_pre_action_projection": False,
        },
        "state_update": {
            "state_update_ref": stable_id("state_update", transition_id, chosen.get("output_digest")),
            "next_action_ref": next_action.get("tool_pair_ref") if next_action else None,
            "safe_update_label": "needs_semantic_review",
            "model_visible_for_pre_action_projection": False,
        },
        "verifier_linkage": {
            "status": "temporal_only_needs_causal_review" if verifier_idx is not None else "not_applicable",
            "verifier_action_ref": actions[verifier_idx]["tool_pair_ref"] if verifier_idx is not None else None,
            "verifier_command_head": actions[verifier_idx].get("command_head") if verifier_idx is not None else None,
            "same_source_relation_proven": False,
            "no_intervening_patch_proven": False,
            "pre_status_observed": False,
            "post_status_observed": False,
        },
        "stop_continue": {
            "label": "STOP" if next_action is None and window.get("terminal_status") == "task_complete" else "CONTINUE",
            "terminal_status": window.get("terminal_status"),
            "weak_lifecycle_only": True,
        },
        "allowed_projection_families": allowed_projection_families(horizon),
        "admission": {
            "validation_level": validation_level,
            "train_support_allowed": False,
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
            "admission_allowed": False,
            "blocked_reason": "candidate_only_requires_source_root_repair_and_causal_review",
        },
        "visibility_masks": {
            "pre_action_input_fields": ["source_refs", "lineage", "state_before", "candidate_action_set"],
            "target_or_post_action_fields": ["chosen_action", "observation", "state_update", "stop_continue", "verifier_linkage"],
            "future_actions_visible_to_model": False,
        },
        "guardrails": {
            "raw_message_text_emitted": False,
            "raw_patch_body_emitted": False,
            "raw_tool_arguments_emitted": False,
            "raw_tool_output_emitted": False,
        },
    }


def select_windows() -> tuple[list[dict[str, Any]], Counter[str]]:
    all_windows = [row for _, row in iter_jsonl(WINDOWS) if row.get("has_command_observation")]
    all_windows.sort(key=lambda r: (
        0 if r.get("training_potential") == "level_2_patch_and_verifier_refs_needs_state_join" else 1,
        -int(r.get("paired_tool_call_count") or 0),
        str(r.get("chat_id")),
        int(r.get("start_line") or 0),
    ))
    selected: list[dict[str, Any]] = []
    per_chat: Counter[str] = Counter()
    for row in all_windows:
        if len(selected) >= MAX_PARENT_WINDOWS:
            break
        chat_id = str(row.get("chat_id"))
        if per_chat[chat_id] >= MAX_PARENT_WINDOWS_PER_CHAT:
            continue
        selected.append(row)
        per_chat[chat_id] += 1
    return selected, per_chat


def mine_slices(windows: list[dict[str, Any]], pairs_by_chat: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    slices: list[dict[str, Any]] = []
    for window in windows:
        chat_id = window.get("chat_id")
        start = int(window.get("start_line") or 0)
        end = int(window.get("end_line") or 0)
        actions = [p for p in pairs_by_chat.get(chat_id, []) if start <= int(p["call_line_number"]) <= end]
        if not actions:
            continue
        parent = window.get("task_window_id")
        parent_slices = 0

        h1_idx = next((i for i, a in enumerate(actions) if a["action_type"] != "inspect"), 0)
        slices.append(make_slice(window, actions, h1_idx, "H1_next_action", "first_non_inspect_or_first_action", 0))
        parent_slices += 1

        h3_idx = next((i for i, a in enumerate(actions) if a["action_type"] == "verify"), None)
        if h3_idx is not None and parent_slices < MAX_SLICES_PER_PARENT:
            slices.append(make_slice(window, actions, h3_idx, "H3_micro_loop", "first_verifier_micro_loop", 0))
            parent_slices += 1

        loop_count = 0
        for pi, act in enumerate(actions):
            if act["action_type"] != "patch":
                continue
            vi = next((j for j in range(pi + 1, len(actions)) if actions[j]["action_type"] == "verify"), None)
            if vi is None:
                continue
            if parent_slices >= MAX_SLICES_PER_PARENT:
                break
            slices.append(make_slice(window, actions, pi, "H10_patch_verifier_loop", "patch_followed_by_later_verifier", loop_count, verifier_idx=vi))
            parent_slices += 1
            loop_count += 1
    return slices


def main() -> int:
    pairs_by_chat = build_pair_index()
    selected_windows, selected_per_chat = select_windows()
    slices = mine_slices(selected_windows, pairs_by_chat)

    horizon_counts = Counter(s["horizon_label"] for s in slices)
    validation_counts = Counter(s["admission"]["validation_level"] for s in slices)
    parent_counts = Counter(s["source_refs"]["task_window_id"] for s in slices)
    chat_slice_counts = Counter(s["source_refs"]["chat_id"] for s in slices)
    action_counts = Counter(s["chosen_action"]["action_type"] for s in slices)
    raw_guardrail_violations = [
        s["horizon_slice_id"] for s in slices
        if s["guardrails"]["raw_message_text_emitted"]
        or s["guardrails"]["raw_patch_body_emitted"]
        or s["guardrails"]["raw_tool_arguments_emitted"]
        or s["guardrails"]["raw_tool_output_emitted"]
    ]

    write_jsonl(OUT_DIR / "horizon_slice_candidates.jsonl", slices)
    summary = {
        "stage": STAGE,
        "decision": "horizon_slice_candidates_mined_training_blocked",
        "inputs": {
            "task_windows": str(WINDOWS.relative_to(ROOT)),
            "tool_pairs": str(PAIRS.relative_to(ROOT)),
        },
        "selection_policy": {
            "max_parent_windows": MAX_PARENT_WINDOWS,
            "max_parent_windows_per_chat": MAX_PARENT_WINDOWS_PER_CHAT,
            "max_slices_per_parent": MAX_SLICES_PER_PARENT,
            "priority": ["level_2_patch_and_verifier_refs_needs_state_join", "paired_tool_call_count_desc"],
        },
        "counts": {
            "selected_parent_windows": len(selected_windows),
            "horizon_slice_candidates": len(slices),
            "unique_parent_task_windows": len(parent_counts),
            "max_slices_per_parent": max(parent_counts.values()) if parent_counts else 0,
            "max_parent_windows_per_chat_in_selection": max(selected_per_chat.values()) if selected_per_chat else 0,
            "raw_guardrail_violations": len(raw_guardrail_violations),
            "training_rows_emitted": 0,
            "admitted_rows": 0,
        },
        "horizon_counts": dict(horizon_counts),
        "validation_level_counts": dict(validation_counts),
        "chosen_action_type_counts": dict(action_counts),
        "top_chat_slice_counts": chat_slice_counts.most_common(10),
        "visibility_masks": {
            "pre_action_input_fields": ["source_refs", "lineage", "state_before", "candidate_action_set"],
            "target_or_post_action_fields": ["chosen_action", "observation", "state_update", "stop_continue", "verifier_linkage"],
            "future_actions_visible_to_model": False,
        },
        "guardrails": {
            "raw_message_text_emitted": False,
            "raw_patch_body_emitted": False,
            "raw_tool_arguments_emitted": False,
            "raw_tool_output_emitted": False,
            "candidate_only": True,
            "training_allowed": False,
        },
        "known_limitations": [
            "source_root_label remains missing for inherited stage12260 windows until source-root repair runs",
            "state_update labels are safe placeholders pending semantic review",
            "stop_continue labels are weak lifecycle labels, not gold completion labels",
            "patch-followed-by-verifier is temporal evidence only, not sufficient repair causality",
            "future actions are masked from candidate_action_set; observation/state_update are target-only for pre-action projections",
        ],
        "next_stage": "stage12272_horizon_slice_qc_and_projection_plan",
    }
    write_json(SUMMARY_PATH, summary)
    write_json(OUT_DIR / "horizon_slice_miner_summary.json", summary)
    write_text(
        OUT_DIR / "HORIZON_SLICE_MINER_PILOT_STAGE12271.md",
        "# Stage12271 Horizon Slice Miner Pilot\n\n"
        "This stage expands from whole task windows into capped H1/H3/H10 horizon-slice candidates. "
        "It emits references and digests only, not raw chat text, raw tool arguments, raw outputs, or patch bodies.\n\n"
        f"Selected parent windows: {len(selected_windows)}\n\n"
        f"Horizon slice candidates: {len(slices)}\n\n"
        f"Horizon counts: {dict(horizon_counts)}\n\n"
        "Admission status: blocked. These candidates require source-root repair, causal state review, and projection QC before any training use.\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

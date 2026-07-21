#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12317_event_local_observation_train_support_500"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

WINDOWS = ROOT / "runs/local/artifacts/stage12260_codex_chat_task_boundary_miner/codex_task_windows.jsonl"
STAGE12316_SCRIPT = ROOT / "scripts/build_stage12316_transition_local_event_joiner.py"

TARGET_TRAIN_SUPPORT_TASKS = 500
MAX_PER_CHAT = 50
WINDOW_PRIORITY = {
    "level_2_patch_and_verifier_refs_needs_state_join": 0,
    "level_1_action_observation_index": 1,
}


def load_stage12316():
    spec = importlib.util.spec_from_file_location("stage12316_mod", STAGE12316_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load stage12316 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
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


def choose_windows(windows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Counter[str]]:
    eligible = [
        row
        for row in windows
        if row.get("training_potential") in WINDOW_PRIORITY
        and row.get("has_command_observation")
    ]
    by_chat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        by_chat[row.get("chat_id") or "unknown_chat"].append(row)
    for rows in by_chat.values():
        rows.sort(
            key=lambda row: (
                WINDOW_PRIORITY.get(row.get("training_potential"), 99),
                -(row.get("patch_pair_count") or 0),
                -(row.get("verifier_like_pair_count") or 0),
                -(row.get("paired_tool_call_count") or 0),
                row.get("start_line") or 0,
            )
        )
        del rows[MAX_PER_CHAT:]

    selected: list[dict[str, Any]] = []
    per_chat = Counter()
    round_index = 0
    chat_ids = sorted(by_chat, key=lambda chat: (-len(by_chat[chat]), chat))
    while len(selected) < TARGET_TRAIN_SUPPORT_TASKS:
        progressed = False
        for chat_id in chat_ids:
            rows = by_chat[chat_id]
            if round_index < len(rows):
                selected.append(rows[round_index])
                per_chat[chat_id] += 1
                progressed = True
                if len(selected) >= TARGET_TRAIN_SUPPORT_TASKS:
                    break
        if not progressed:
            break
        round_index += 1
    return selected, per_chat


def is_train_support_observation_task(semantic: dict[str, Any]) -> tuple[bool, list[str]]:
    blockers: list[str] = [
        "stage12318_semantic_review_required_before_train_support",
        "event_local_status_is_not_policy_or_level3_repair_label",
    ]
    if not semantic.get("semantic_rule_id") or not semantic.get("transition_function_key"):
        blockers.append("missing_semantic_rule_or_transition_key")
    if semantic.get("verifier_status_class") in {"NO_VERIFIER_OBSERVED", "VERIFIER_STATUS_UNKNOWN", None}:
        blockers.append("verifier_status_not_observed")
    if semantic.get("patch_apply_status") in {"PATCH_STATUS_UNKNOWN", None}:
        blockers.append("patch_status_unknown")
    if semantic.get("raw_text_emitted") or semantic.get("raw_tool_output_emitted") or semantic.get("raw_patch_body_emitted"):
        blockers.append("raw_leak_guardrail_violation")
    return False, blockers


def make_record(mod, window: dict[str, Any], raw_path: Path, source_rank: int) -> dict[str, Any]:
    semantic = mod.summarize_window(raw_path, window)
    allowed, blockers = is_train_support_observation_task(semantic)
    source_hash = window.get("source_file_hash_compat")
    task_window_id = window.get("task_window_id")
    row_id = mod.stable_id("stage12317_task", task_window_id, semantic.get("transition_function_key"), source_rank)
    action_counts = semantic.get("action_family_counts") or {}
    return {
        "stage": STAGE,
        "record_type": "event_local_transition_observation_train_support_task",
        "row_id": row_id,
        "task_family": "event_local_transition_observation",
        "training_objective_scope": [
            "patch_apply_status_prediction",
            "verifier_status_class_prediction",
            "stop_continue_observation_prediction",
            "semantic_rule_classification",
        ],
        "not_training_objective_scope": [
            "next_action_policy",
            "patch_generation",
            "Level3 repair causality",
            "source-heldout claim",
        ],
        "source_refs": {
            "task_window_id": task_window_id,
            "source_file_hash_compat": source_hash,
            "chat_id_hash": mod.stable_hash(window.get("chat_id")),
            "raw_source_reopened_internally": True,
            "raw_text_emitted": False,
            "raw_command_text_emitted": False,
            "raw_tool_output_emitted": False,
            "raw_patch_body_emitted": False,
        },
        "input_view": {
            "state_before_summary_codes": semantic.get("state_before_summary_codes") or [],
            "candidate_action_set": {
                "actions": mod.candidate_actions_from_counts(action_counts),
                "neutral_candidates_only": True,
            },
            "observed_action_family_counts_audit_only": action_counts,
        },
        "target_view": {
            "patch_apply_status": semantic.get("patch_apply_status"),
            "verifier_status_class": semantic.get("verifier_status_class"),
            "state_delta_codes": semantic.get("state_delta_codes") or [],
            "stop_continue_label": semantic.get("stop_continue_label"),
            "semantic_rule_id": semantic.get("semantic_rule_id"),
            "transition_function_key": semantic.get("transition_function_key"),
        },
        "admission": {
            "training_allowed": allowed,
            "train_support_allowed": allowed,
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
            "level3_admitted": False,
            "patch_trace_admitted": False,
            "reason": "event-local observation supervision only; not next-action policy or repair proof",
        },
        "blocked_reasons": sorted(set(blockers)),
        "dominance_controls": {
            "max_per_chat": MAX_PER_CHAT,
            "selection_rank": source_rank,
        },
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    mod = load_stage12316()
    source_map = mod.source_file_map()
    windows = read_jsonl(WINDOWS)
    selected, per_chat = choose_windows(windows)

    rows: list[dict[str, Any]] = []
    blocked_source_rows: list[dict[str, Any]] = []
    for rank, window in enumerate(selected, 1):
        raw_path = source_map.get(str(window.get("source_file_hash_compat")))
        if not raw_path:
            blocked_source_rows.append(
                {
                    "task_window_id": window.get("task_window_id"),
                    "blocked_reason": "raw_source_session_unavailable",
                    "source_file_hash_compat": window.get("source_file_hash_compat"),
                }
            )
            continue
        rows.append(make_record(mod, window, raw_path, rank))

    write_jsonl(OUT / "event_local_observation_train_support_tasks.jsonl", rows)
    if blocked_source_rows:
        write_jsonl(OUT / "blocked_source_rows.jsonl", blocked_source_rows)

    language_counts: Counter[str] = Counter()
    train_counts: Counter[str] = Counter()
    blocker_counts: Counter[str] = Counter()
    verifier_counts: Counter[str] = Counter()
    patch_counts: Counter[str] = Counter()
    rule_counts: Counter[str] = Counter()
    risky_action_fields: Counter[str] = Counter()
    for row in rows:
        language_counts["session_unknown_language"] += 1
        if (row.get("admission") or {}).get("train_support_allowed"):
            train_counts[row.get("task_family") or "unknown"] += 1
        blocker_counts.update(row.get("blocked_reasons") or [])
        target = row.get("target_view") or {}
        verifier_counts[target.get("verifier_status_class") or "MISSING"] += 1
        patch_counts[target.get("patch_apply_status") or "MISSING"] += 1
        rule_counts[target.get("semantic_rule_id") or "MISSING"] += 1
        for action in (((row.get("input_view") or {}).get("candidate_action_set") or {}).get("actions") or []):
            for key in action:
                if key in {"role", "chosen", "gold", "correct", "target", "observed", "observed_in_window", "count_bucket"} or key.endswith("_ref"):
                    risky_action_fields[key] += 1

    summary = {
        "stage": STAGE,
        "decision": "event_local_observation_review_candidates_ready_training_blocked",
        "claim_boundary": "Review candidates only for event-local observation/status heads. Not train-support until Stage12318 semantic review; not Level-3 repair, not next-action policy, not strict/source-heldout.",
        "target_train_support_tasks": TARGET_TRAIN_SUPPORT_TASKS,
        "records_emitted": len(rows),
        "train_support_tasks": 0,
        "review_candidate_records": len(rows),
        "training_allowed": False,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "strict_eval_rows": 0,
        "source_heldout_rows": 0,
        "blocked_source_rows": len(blocked_source_rows),
        "language_counts": dict(language_counts),
        "task_family_train_counts": dict(train_counts),
        "verifier_status_counts": dict(verifier_counts),
        "patch_apply_status_counts": dict(patch_counts),
        "semantic_rule_counts": dict(rule_counts),
        "blocked_reason_counts": dict(blocker_counts),
        "per_chat_selected_top": dict(per_chat.most_common(20)),
        "dominance_controls": {
            "max_per_chat": MAX_PER_CHAT,
            "unique_chats_selected": len(per_chat),
            "top_chat_fraction": (per_chat.most_common(1)[0][1] / max(1, sum(per_chat.values()))) if per_chat else 0,
        },
        "risky_candidate_action_field_counts": dict(risky_action_fields),
        "next_stage": {
            "stage": "stage12318_event_local_observation_package_qc",
            "purpose": "Audit narrow train-support package for dominance, label balance, shortcut fields, and train objective routing.",
            "training_allowed": False,
        },
    }
    (OUT / "event_local_observation_train_support_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "EVENT_LOCAL_OBSERVATION_TRAIN_SUPPORT_500_STAGE12317.md").write_text(
        "# Stage12317 Event-Local Observation Train-Support 500\n\n"
        "This stage targets 500 narrow train-support tasks for observation/status heads only.\n\n"
        "It does not claim Level-3 repair, patch-trace repair, next-action policy, strict eval, or source-heldout readiness.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

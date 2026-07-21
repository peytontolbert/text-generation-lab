#!/usr/bin/env python3
"""Build Stage12306 session episode graph candidate materialization.

This materializer emits candidate-only episode graph records from raw Codex
session task-window metadata. It deliberately fails closed: no training rows,
raw tool output, raw tool arguments, patch bodies, command text, or source paths
are emitted.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12306_session_episode_graph_candidate_materializer"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_PATH = ROOT / "runs/summaries" / f"{STAGE}.json"

LIVE_SOURCE_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12256_live_physical_session_inventory_refresh/live_physical_source_records.jsonl"
)
TASK_WINDOWS = (
    ROOT / "runs/local/artifacts/stage12260_codex_chat_task_boundary_miner/codex_task_windows.jsonl"
)
BLOCKED_WINDOWS = (
    ROOT / "runs/local/artifacts/stage12262_episode_graph_validator_skeleton/blocked_task_windows.jsonl"
)
HORIZON_CANDIDATES = (
    ROOT / "runs/local/artifacts/stage12271_horizon_slice_miner_pilot/horizon_slice_candidates.jsonl"
)

MAX_CANDIDATES = 25
MAX_PER_CHAT_OR_SESSION = 3
SOURCE_POOL_ID = "session_like_source_inventory_real"


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(json.dumps(part, sort_keys=True, default=str) for part in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            yield line_no, json.loads(line)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def read_physical_sources() -> dict[str, dict[str, Any]]:
    by_hash: dict[str, dict[str, Any]] = {}
    for _, row in iter_jsonl(LIVE_SOURCE_RECORDS) or []:
        source_hash = row.get("source_file_hash_compat")
        if not source_hash:
            continue
        by_hash[source_hash] = {
            "physical_source_id": row.get("physical_source_id"),
            "source_root_label": row.get("source_root_label"),
            "source_kind": row.get("source_kind"),
            "source_root_exists": row.get("source_root_exists"),
            "path_policy": row.get("path_policy"),
            "source_path_emitted": False,
            "raw_content_read": False,
        }
    return by_hash


def read_windows() -> dict[str, dict[str, Any]]:
    windows: dict[str, dict[str, Any]] = {}
    for _, row in iter_jsonl(TASK_WINDOWS) or []:
        task_window_id = row.get("task_window_id")
        if task_window_id:
            windows[task_window_id] = row
    return windows


def read_blocked_window_reasons() -> dict[str, list[str]]:
    blocked: dict[str, list[str]] = defaultdict(list)
    for _, row in iter_jsonl(BLOCKED_WINDOWS) or []:
        task_window_id = row.get("task_window_id")
        if not task_window_id:
            continue
        reasons = row.get("blocked_reasons") or row.get("blocker_codes") or []
        if isinstance(reasons, str):
            reasons = [reasons]
        for reason in reasons:
            if reason not in blocked[task_window_id]:
                blocked[task_window_id].append(reason)
    return blocked


def infer_language_family(window: dict[str, Any], horizon: dict[str, Any] | None = None) -> str:
    if horizon:
        allowed = horizon.get("allowed_projection_families") or []
        if any("python" in str(item).lower() for item in allowed):
            return "python"
    heads = window.get("command_head_counts_top") or {}
    families = window.get("command_family_counts") or {}
    if any(str(head).startswith("python") for head in heads):
        return "python"
    if any(str(head) in {"cargo", "rustc"} for head in heads):
        return "rust"
    if any(str(head) in {"gcc", "g++", "clang", "clang++", "cmake", "ctest"} for head in heads):
        return "c_cpp"
    if any(str(head) in {"node", "npm", "pnpm", "yarn", "npx"} for head in heads):
        return "javascript_typescript"
    if families.get("python_execution"):
        return "python"
    return "unknown_from_metadata"


def root_fields(
    window: dict[str, Any],
    physical: dict[str, Any] | None,
    horizon: dict[str, Any] | None,
) -> dict[str, Any]:
    source_root_label = (
        window.get("source_root_label")
        or (horizon or {}).get("source_refs", {}).get("source_root_label")
        or (physical or {}).get("source_root_label")
    )
    source_hash = window.get("source_file_hash_compat") or (horizon or {}).get("source_refs", {}).get(
        "source_file_hash_compat"
    )
    split_group_id = stable_id(
        "split_group",
        source_root_label,
        window.get("chat_id"),
        window.get("session_id_hint"),
        source_hash,
    )
    root_lineage_key = stable_id("root_lineage", split_group_id, window.get("task_window_id"))
    return {
        "canonical_root_id": stable_id("canonical_root", SOURCE_POOL_ID, root_lineage_key),
        "repo_family": "unknown_until_cwd_or_repo_join",
        "language_family": infer_language_family(window, horizon),
        "source_root_label": source_root_label,
        "root_lineage_key": root_lineage_key,
        "split_group_id": split_group_id,
        "source_pool_id": SOURCE_POOL_ID,
    }


def source_refs(window: dict[str, Any], physical: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "source_adapter": "codex_sessions",
        "snapshot_id": window.get("snapshot_id"),
        "chat_or_session_ids": [item for item in [window.get("chat_id"), window.get("session_id_hint")] if item],
        "task_window_id": window.get("task_window_id"),
        "physical_source_ids": [physical["physical_source_id"]] if physical and physical.get("physical_source_id") else [],
        "source_file_hash_compat": window.get("source_file_hash_compat"),
        "event_span_refs": {
            "line_start": window.get("start_line"),
            "line_end": window.get("end_line"),
            "start_event_id": window.get("start_event_id"),
            "terminal_event_id": window.get("terminal_event_id"),
            "event_count": window.get("event_count"),
        },
        "raw_payloads_emitted": False,
        "raw_message_text_emitted": False,
        "raw_tool_arguments_emitted": False,
        "raw_tool_output_emitted": False,
        "raw_patch_body_emitted": False,
        "source_path_emitted": False,
    }


def ordered_events(window: dict[str, Any]) -> dict[str, Any]:
    if window.get("start_event_id") and window.get("terminal_event_id") and window.get("line_count"):
        return {
            "ordered_events_ref": stable_id(
                "ordered_events",
                window.get("chat_id"),
                window.get("task_window_id"),
                window.get("start_event_id"),
                window.get("terminal_event_id"),
            ),
            "ordered_events_missing_reason": None,
            "monotonic_line_order": True,
            "event_count": window.get("event_count"),
            "paired_tool_call_count": window.get("paired_tool_call_count"),
            "patch_pair_count": window.get("patch_pair_count"),
            "verifier_like_pair_count": window.get("verifier_like_pair_count"),
        }
    return {
        "ordered_events_ref": None,
        "ordered_events_missing_reason": "missing_task_window_event_span",
        "monotonic_line_order": None,
        "event_count": window.get("event_count"),
        "paired_tool_call_count": window.get("paired_tool_call_count"),
        "patch_pair_count": window.get("patch_pair_count"),
        "verifier_like_pair_count": window.get("verifier_like_pair_count"),
    }


def scrub_action(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "action_type": action.get("action_type"),
        "action_ref_hidden": True,
        "tool_pair_ref_hidden": True,
        "position_role_hidden": True,
        "raw_tool_arguments_emitted": False,
        "raw_tool_output_emitted": False,
        "command_text_emitted": False,
    }


def candidate_action_set(horizon: dict[str, Any] | None, window: dict[str, Any]) -> dict[str, Any]:
    if horizon and isinstance(horizon.get("candidate_action_set"), dict):
        action_set = horizon["candidate_action_set"]
        actions = [scrub_action(action) for action in action_set.get("actions", [])]
        if actions:
            return {
                "status": "materialized_target_refs_only",
                "actions": actions,
                "candidate_count": len(actions),
                "future_actions_masked": bool(action_set.get("future_actions_masked", True)),
                "raw_tool_arguments_emitted": False,
                "raw_tool_output_emitted": False,
                "raw_patch_body_emitted": False,
                "command_text_emitted": False,
            }
    if window.get("paired_tool_call_count"):
        return {
            "status": "blocked_missing_bounded_action_refs",
            "actions": [],
            "candidate_count": 0,
            "missing_reason": "task_window_has_tool_pairs_but_no_stage12271_candidate_action_set",
            "raw_tool_arguments_emitted": False,
            "raw_tool_output_emitted": False,
            "raw_patch_body_emitted": False,
            "command_text_emitted": False,
        }
    return {
        "status": "missing_no_action_pairs_in_task_window",
        "actions": [],
        "candidate_count": 0,
        "missing_reason": "no_paired_tool_calls",
        "contains_chosen_or_gold_role_markers": False,
        "contains_raw_action_refs": False,
        "raw_tool_arguments_emitted": False,
        "raw_tool_output_emitted": False,
        "raw_patch_body_emitted": False,
        "command_text_emitted": False,
    }


def chosen_action(horizon: dict[str, Any] | None) -> dict[str, Any]:
    chosen = (horizon or {}).get("chosen_action")
    if isinstance(chosen, dict) and (chosen.get("action_id") or chosen.get("tool_pair_ref")):
        return {
            "status": "target_only_ref_materialized",
            "action_ref": chosen.get("action_id") or chosen.get("tool_pair_ref"),
            "action_type": chosen.get("action_type"),
            "tool_pair_ref": chosen.get("tool_pair_ref"),
            "target_fields_only": True,
            "raw_tool_arguments_emitted": False,
            "raw_tool_output_emitted": False,
            "raw_patch_body_emitted": False,
            "command_text_emitted": False,
        }
    return {
        "status": "missing",
        "missing_reason": "no_stage12271_chosen_action_ref",
        "target_fields_only": True,
        "raw_tool_arguments_emitted": False,
        "raw_tool_output_emitted": False,
        "raw_patch_body_emitted": False,
        "command_text_emitted": False,
    }


def state_before(horizon: dict[str, Any] | None, transition_id: str) -> dict[str, Any]:
    state = (horizon or {}).get("state_before")
    if isinstance(state, dict) and state.get("state_before_ref"):
        return {
            "state_before_ref": state.get("state_before_ref"),
            "state_before_missing_reason": None,
            "raw_content_emitted": False,
        }
    return {
        "state_before_ref": None,
        "state_before_missing_reason": "state_before_not_materialized_from_raw_session_events",
        "fallback_state_before_ref": stable_id("state_before_missing", transition_id),
        "raw_content_emitted": False,
    }


def target_ref_block(
    horizon: dict[str, Any] | None,
    source_key: str,
    target_key: str,
    missing_reason: str,
) -> dict[str, Any]:
    source = (horizon or {}).get(source_key)
    if isinstance(source, dict) and source.get(target_key):
        out = {
            "status": "target_only_ref_materialized",
            target_key: source.get(target_key),
            "target_fields_only": True,
            "model_visible_for_pre_action_projection": False,
            "raw_content_emitted": False,
            "raw_tool_output_emitted": False,
            "raw_patch_body_emitted": False,
        }
        for optional_key in ("tool_pair_ref", "output_digest", "safe_update_label", "next_action_ref"):
            if optional_key in source:
                out[optional_key] = source.get(optional_key)
        return out
    return {
        "status": "missing",
        "missing_reason": missing_reason,
        "target_fields_only": True,
        "model_visible_for_pre_action_projection": False,
        "raw_content_emitted": False,
        "raw_tool_output_emitted": False,
        "raw_patch_body_emitted": False,
    }


def verifier_result(horizon: dict[str, Any] | None, window: dict[str, Any]) -> dict[str, Any]:
    linkage = (horizon or {}).get("verifier_linkage")
    if isinstance(linkage, dict) and linkage.get("status"):
        return {
            "status": linkage.get("status"),
            "verifier_action_ref": linkage.get("verifier_action_ref"),
            "same_source_relation_proven": bool(linkage.get("same_source_relation_proven")),
            "no_intervening_patch_proven": bool(linkage.get("no_intervening_patch_proven")),
            "pre_status_observed": bool(linkage.get("pre_status_observed")),
            "post_status_observed": bool(linkage.get("post_status_observed")),
            "target_fields_only": True,
            "raw_verifier_output_emitted": False,
            "command_text_emitted": False,
        }
    if window.get("has_verifier_like_ref"):
        return {
            "status": "missing_verifier_relevance_not_materialized",
            "missing_reason": "task_window_has_verifier_like_refs_but_no_causal_verifier_linkage",
            "target_fields_only": True,
            "raw_verifier_output_emitted": False,
            "command_text_emitted": False,
        }
    return {
        "status": "missing",
        "missing_reason": "no_verifier_like_ref_in_task_window",
        "target_fields_only": True,
        "raw_verifier_output_emitted": False,
        "command_text_emitted": False,
    }


def stop_continue(horizon: dict[str, Any] | None, window: dict[str, Any]) -> dict[str, Any]:
    stop = (horizon or {}).get("stop_continue")
    if isinstance(stop, dict) and stop.get("label"):
        return {
            "status": "target_only_ref_materialized",
            "label": stop.get("label"),
            "terminal_status": stop.get("terminal_status") or window.get("terminal_status"),
            "weak_lifecycle_only": bool(stop.get("weak_lifecycle_only", True)),
            "target_fields_only": True,
        }
    if window.get("terminal_status"):
        return {
            "status": "weak_lifecycle_only",
            "label": "STOP" if window.get("terminal_status") == "task_complete" else "UNKNOWN",
            "terminal_status": window.get("terminal_status"),
            "weak_lifecycle_only": True,
            "target_fields_only": True,
        }
    return {
        "status": "missing",
        "missing_reason": "terminal_status_missing",
        "target_fields_only": True,
    }


def blocked_reasons(
    root: dict[str, Any],
    action_set: dict[str, Any],
    chosen: dict[str, Any],
    ordered: dict[str, Any],
    state: dict[str, Any],
    verifier: dict[str, Any],
    extra_reasons: list[str],
) -> list[str]:
    reasons = [
        "candidate_only_fail_closed",
        "training_allowed_false",
        "raw_session_event_root_requires_causal_review",
        "repo_family_unknown_until_cwd_or_repo_join",
    ]
    if not root.get("source_root_label"):
        reasons.append("missing_source_root_label")
    if ordered.get("ordered_events_missing_reason"):
        reasons.append(ordered["ordered_events_missing_reason"])
    if state.get("state_before_missing_reason"):
        reasons.append(state["state_before_missing_reason"])
    if action_set.get("candidate_count", 0) == 0:
        reasons.append("no_candidate_action_set")
    if chosen.get("status") == "missing":
        reasons.append("chosen_action_missing")
    if verifier.get("status", "").startswith("missing"):
        reasons.append(verifier.get("missing_reason") or "verifier_result_missing")
    for reason in extra_reasons:
        if reason not in reasons:
            reasons.append(reason)
    return reasons


def make_candidate(
    window: dict[str, Any],
    physical: dict[str, Any] | None,
    blocked: list[str],
    horizon: dict[str, Any] | None,
    source_rank: int,
) -> dict[str, Any]:
    root = root_fields(window, physical, horizon)
    lineage = (horizon or {}).get("lineage") if isinstance((horizon or {}).get("lineage"), dict) else {}
    episode_id = lineage.get("episode_id") or stable_id("episode", root["root_lineage_key"], window.get("task_window_id"))
    transition_id = lineage.get("transition_id") or stable_id("transition", episode_id, "metadata_only")
    ordered = ordered_events(window)
    state = state_before(horizon, transition_id)
    action_set = candidate_action_set(horizon, window)
    chosen = chosen_action(horizon)
    observation = target_ref_block(
        horizon,
        "observation",
        "observation_ref",
        "observation_not_materialized_from_raw_session_events",
    )
    verifier = verifier_result(horizon, window)
    state_update = target_ref_block(
        horizon,
        "state_update",
        "state_update_ref",
        "state_update_not_materialized_from_raw_session_events",
    )
    stop = stop_continue(horizon, window)
    reasons = blocked_reasons(root, action_set, chosen, ordered, state, verifier, blocked)
    validation_level = (horizon or {}).get("admission", {}).get("validation_level") or "V2_task_boundary"
    admission_level = "candidate_only_blocked"
    if validation_level.startswith("V4"):
        admission_level = "candidate_only_v4_unadmitted"
    elif validation_level.startswith("V3"):
        admission_level = "candidate_only_v3_unadmitted"

    return {
        "schema_version": "episode_graph_candidate_v2",
        "stage": STAGE,
        "record_type": "episode_graph_candidate",
        "candidate_id": stable_id("episode_graph_candidate", STAGE, window.get("task_window_id"), transition_id),
        "candidate_only": True,
        "training_allowed": False,
        "admission_allowed": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        **root,
        "task_window_id": window.get("task_window_id"),
        "episode_id": episode_id,
        "transition_id": transition_id,
        "root_lineage": {
            "root_lineage_key": root["root_lineage_key"],
            "split_group_id": root["split_group_id"],
            "episode_id": episode_id,
            "transition_id": transition_id,
            "source_lineage_key": lineage.get("source_lineage_key")
            or stable_id("source_lineage", window.get("snapshot_id"), window.get("source_file_hash_compat")),
        },
        "source_refs": source_refs(window, physical),
        "ordered_events": ordered,
        "state_before": state,
        "candidate_action_set": action_set,
        "chosen_action_target_only": chosen,
        "observation_target_only": observation,
        "verifier_result_target_only": verifier,
        "state_after_or_update_target_only": state_update,
        "stop_continue_target_only": stop,
        "admission_level": admission_level,
        "blocked_reasons": reasons,
        "guardrails": {
            "candidate_only": True,
            "training_allowed": False,
            "raw_source_paths_emitted": False,
            "raw_message_text_emitted": False,
            "raw_tool_arguments_emitted": False,
            "raw_tool_output_emitted": False,
            "raw_patch_body_emitted": False,
            "command_text_emitted": False,
        },
        "selection": {
            "source_rank": source_rank,
            "selection_source": "stage12271_horizon_slice" if horizon else "stage12260_task_window_metadata",
            "max_candidates": MAX_CANDIDATES,
            "max_per_chat_or_session": MAX_PER_CHAT_OR_SESSION,
        },
    }


def candidate_sort_key(window: dict[str, Any], horizon: dict[str, Any] | None) -> tuple[int, int, int, str]:
    patch_count = int(window.get("patch_pair_count") or 0)
    verifier_count = int(window.get("verifier_like_pair_count") or 0)
    paired_count = int(window.get("paired_tool_call_count") or 0)
    horizon_bonus = 1 if horizon else 0
    return (-horizon_bonus, -patch_count, -verifier_count, -paired_count, window.get("task_window_id") or "")


def load_horizon_by_window() -> dict[str, list[dict[str, Any]]]:
    by_window: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for _, row in iter_jsonl(HORIZON_CANDIDATES) or []:
        refs = row.get("source_refs") or {}
        task_window_id = refs.get("task_window_id")
        if task_window_id:
            by_window[task_window_id].append(row)
    return by_window


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    physical_by_hash = read_physical_sources()
    windows = read_windows()
    blocked_by_window = read_blocked_window_reasons()
    horizon_by_window = load_horizon_by_window()

    materialization_inputs: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
    for task_window_id, window in windows.items():
        horizons = horizon_by_window.get(task_window_id)
        if horizons:
            for horizon in horizons:
                materialization_inputs.append((window, horizon))
        else:
            materialization_inputs.append((window, None))
    materialization_inputs.sort(key=lambda pair: candidate_sort_key(pair[0], pair[1]))

    candidates: list[dict[str, Any]] = []
    per_group: Counter[str] = Counter()
    skipped_by_cap = 0
    source_rank = 0
    seen_candidates: set[str] = set()
    for window, horizon in materialization_inputs:
        if len(candidates) >= MAX_CANDIDATES:
            break
        group = window.get("chat_id") or window.get("session_id_hint") or "unknown_session"
        if per_group[group] >= MAX_PER_CHAT_OR_SESSION:
            skipped_by_cap += 1
            continue
        source_rank += 1
        source_hash = window.get("source_file_hash_compat")
        physical = physical_by_hash.get(source_hash or "")
        candidate = make_candidate(
            window,
            physical,
            blocked_by_window.get(window.get("task_window_id"), []),
            horizon,
            source_rank,
        )
        if candidate["candidate_id"] in seen_candidates:
            continue
        seen_candidates.add(candidate["candidate_id"])
        candidates.append(candidate)
        per_group[group] += 1

    artifact_rel = f"stage12306_session_episode_graph_candidate_materializer/{STAGE}.jsonl"
    write_jsonl(OUT_DIR / f"{STAGE}.jsonl", candidates)

    admission_counts = Counter(candidate["admission_level"] for candidate in candidates)
    source_counts = Counter(candidate["selection"]["selection_source"] for candidate in candidates)
    blocked_counts: Counter[str] = Counter()
    for candidate in candidates:
        blocked_counts.update(candidate["blocked_reasons"])

    summary = {
        "stage": STAGE,
        "record_type": "stage_summary",
        "candidate_only": True,
        "training_allowed": False,
        "admission_allowed": False,
        "decision": "candidate_materialization_complete_fail_closed",
        "output_artifacts": [
            {
                "artifact_id": "stage12306_episode_graph_candidates_jsonl",
                "artifact_rel": artifact_rel,
                "record_type": "episode_graph_candidate",
                "record_count": len(candidates),
                "candidate_only": True,
                "training_allowed": False,
            }
        ],
        "input_artifact_status": {
            "stage12256_live_physical_source_records": {
                "exists": LIVE_SOURCE_RECORDS.exists(),
                "records_indexed_by_hash": len(physical_by_hash),
                "source_paths_emitted": False,
            },
            "stage12260_codex_task_windows": {
                "exists": TASK_WINDOWS.exists(),
                "records_indexed_by_task_window": len(windows),
            },
            "stage12262_blocked_task_windows": {
                "exists": BLOCKED_WINDOWS.exists(),
                "records_indexed_by_task_window": len(blocked_by_window),
            },
            "stage12271_horizon_slice_candidates": {
                "exists": HORIZON_CANDIDATES.exists(),
                "task_windows_with_candidates": len(horizon_by_window),
            },
        },
        "caps": {
            "max_candidates": MAX_CANDIDATES,
            "max_per_chat_or_session": MAX_PER_CHAT_OR_SESSION,
            "emitted_candidates": len(candidates),
            "skipped_by_per_chat_or_session_cap": skipped_by_cap,
        },
        "admission_level_counts": dict(sorted(admission_counts.items())),
        "selection_source_counts": dict(sorted(source_counts.items())),
        "blocked_reason_counts": dict(sorted(blocked_counts.items())),
        "guardrails": {
            "candidate_only": True,
            "training_allowed": False,
            "raw_source_paths_emitted": False,
            "raw_message_text_emitted": False,
            "raw_tool_arguments_emitted": False,
            "raw_tool_output_emitted": False,
            "raw_patch_body_emitted": False,
            "command_text_emitted": False,
        },
    }
    write_json(SUMMARY_PATH, summary)
    write_json(OUT_DIR / f"{STAGE}.json", summary)


if __name__ == "__main__":
    main()

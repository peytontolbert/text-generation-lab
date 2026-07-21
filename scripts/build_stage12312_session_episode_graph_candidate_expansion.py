#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12312_session_episode_graph_candidate_expansion"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
STAGE12306_SCRIPT = ROOT / "scripts/build_stage12306_session_episode_graph_candidate_materializer.py"

MAX_CANDIDATES = 100
MAX_PER_CHAT_OR_SESSION = 4


def load_stage12306_module():
    spec = importlib.util.spec_from_file_location("stage12306_mod", STAGE12306_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load stage12306 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_jsonl(path: Path, rows: list[dict]) -> int:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)


def make_candidates(mod) -> tuple[list[dict], int]:
    physical_by_hash = mod.read_physical_sources()
    windows = mod.read_windows()
    blocked_by_window = mod.read_blocked_window_reasons()
    horizon_by_window = mod.load_horizon_by_window()

    materialization_inputs = []
    for task_window_id, window in windows.items():
        horizons = horizon_by_window.get(task_window_id)
        if horizons:
            for horizon in horizons:
                materialization_inputs.append((window, horizon))
        else:
            materialization_inputs.append((window, None))
    materialization_inputs.sort(key=lambda pair: mod.candidate_sort_key(pair[0], pair[1]))

    candidates = []
    per_group: Counter[str] = Counter()
    skipped_by_cap = 0
    source_rank = 0
    seen = set()
    for window, horizon in materialization_inputs:
        if len(candidates) >= MAX_CANDIDATES:
            break
        group = window.get("chat_id") or window.get("session_id_hint") or "unknown_session"
        if per_group[group] >= MAX_PER_CHAT_OR_SESSION:
            skipped_by_cap += 1
            continue
        source_rank += 1
        physical = physical_by_hash.get(window.get("source_file_hash_compat") or "")
        candidate = mod.make_candidate(
            window,
            physical,
            blocked_by_window.get(window.get("task_window_id"), []),
            horizon,
            source_rank,
        )
        candidate["stage"] = STAGE
        candidate["candidate_id"] = candidate["candidate_id"].replace("episode_graph_candidate_", "episode_graph_candidate_expanded_")
        candidate["selection"]["max_candidates"] = MAX_CANDIDATES
        candidate["selection"]["max_per_chat_or_session"] = MAX_PER_CHAT_OR_SESSION
        candidate["training_allowed"] = False
        candidate["admission_allowed"] = False
        candidate["candidate_only"] = True
        # Keep Stage12306's strict candidate-action fix: no target role or refs in model-visible candidates.
        for action in (candidate.get("candidate_action_set") or {}).get("actions", []):
            for key in ["position_role", "action_ref", "tool_pair_ref"]:
                action.pop(key, None)
            action["position_role_hidden"] = True
            action["action_ref_hidden"] = True
            action["tool_pair_ref_hidden"] = True
        key = (candidate.get("task_window_id"), candidate.get("transition_id"))
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
        per_group[group] += 1
    return candidates, skipped_by_cap


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    mod = load_stage12306_module()
    candidates, skipped_by_cap = make_candidates(mod)
    write_jsonl(OUT / "expanded_episode_graph_candidates.jsonl", candidates)

    blocked_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    selection_counts: Counter[str] = Counter()
    shortcut_fields: Counter[str] = Counter()
    for candidate in candidates:
        blocked_counts.update(candidate.get("blocked_reasons") or [])
        language_counts[candidate.get("language_family") or "unknown"] += 1
        selection_counts[(candidate.get("selection") or {}).get("selection_source") or "unknown"] += 1
        for action in (candidate.get("candidate_action_set") or {}).get("actions", []):
            for key in ["position_role", "action_ref", "tool_pair_ref", "chosen", "gold", "correct", "target"]:
                if key in action:
                    shortcut_fields[key] += 1
    summary = {
        "stage": STAGE,
        "decision": "expanded_session_episode_graph_candidates_ready_training_blocked",
        "claim_boundary": "Expanded candidate-only session episode graph records. No training rows, Level-3 claims, or eval claims emitted.",
        "candidate_count": len(candidates),
        "training_rows_emitted": 0,
        "training_allowed": False,
        "admission_allowed": False,
        "language_counts": dict(language_counts),
        "selection_source_counts": dict(selection_counts),
        "blocked_reason_counts": dict(blocked_counts),
        "shortcut_field_counts": dict(shortcut_fields),
        "caps": {
            "MAX_CANDIDATES": MAX_CANDIDATES,
            "MAX_PER_CHAT_OR_SESSION": MAX_PER_CHAT_OR_SESSION,
            "skipped_by_per_chat_or_session_cap": skipped_by_cap,
        },
        "next_stage": "stage12313_expanded_state_code_hydration_or_repo_join",
    }
    (OUT / "expanded_episode_graph_candidate_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build Stage12263 high-value task-window profiler.

Profiles the Stage12260 patch+verifier-ref windows, repairs source adapter
metadata from Stage12258 chat manifests, enforces max-3-per-chat audit caps, and
selects a 25-window deterministic audit set. No root admission or training.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12263_high_value_window_profiler"
WINDOWS = ROOT / "runs/local/artifacts/stage12260_codex_chat_task_boundary_miner/codex_task_windows.jsonl"
CHATS = ROOT / "runs/local/artifacts/stage12258_live_codex_chat_reconstruction_index/per_chat_manifest.jsonl"

ENV_NOISE_HEADS = {"conda", "pip", "apt", "brew", "df", "du", "nvidia-smi", "ps", "kill", "pkill", "ollama"}
DESTRUCTIVE_HEADS = {"rm", "pkill", "kill", "mv"}


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


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


def rate(count: float, denom: float) -> float:
    return float(count) / float(denom if denom else 1.0)


def infer_language(heads: dict[str, int]) -> str:
    keys = set(heads)
    if keys & {"pytest", "python", "python3"} or any("python" in k for k in keys):
        return "python"
    if keys & {"cargo"}:
        return "rust"
    if keys & {"cmake", "ctest", "make"}:
        return "c_cpp"
    if keys & {"npm", "npx", "pnpm", "node", "./node_modules/.bin/vitest", "./node_modules/.bin/tsc"}:
        return "web_js_ts_html"
    return "unknown"


def score_window(row: dict[str, Any], chat: dict[str, Any]) -> tuple[float, dict[str, Any], dict[str, Any]]:
    event_count = int(row.get("event_count") or 0)
    paired = int(row.get("paired_tool_call_count") or 0)
    exec_count = int(row.get("exec_command_pair_count") or 0)
    patch_count = int(row.get("patch_pair_count") or 0)
    verifier_count = int(row.get("verifier_like_pair_count") or 0)
    loop_count = min(patch_count, verifier_count)
    command_heads = {str(k): int(v) for k, v in (row.get("command_head_counts_top") or {}).items()}
    env_noise = sum(v for k, v in command_heads.items() if k in ENV_NOISE_HEADS)
    destructive = sum(v for k, v in command_heads.items() if k in DESTRUCTIVE_HEADS)
    parse_errors = int(chat.get("parse_error_count") or 0)
    chat_events = int(chat.get("event_count") or 1)
    density = {
        "tool_density": rate(paired, event_count),
        "patch_density": rate(patch_count, event_count),
        "verifier_density": rate(verifier_count, exec_count),
        "loop_density": rate(loop_count, event_count),
        "pair_quality": 1.0 if paired > 0 else 0.0,
        "user_task_density": 1.0 if row.get("has_user_signal") else 0.0,
    }
    risk = {
        "parse_error_rate": rate(parse_errors, chat_events),
        "env_install_noise_rate": rate(env_noise, max(exec_count, 1)),
        "destructive_command_rate": rate(destructive, max(exec_count, 1)),
        "privacy_risk_flag": False,
        "unpaired_tool_rate": 0.0,
    }
    noise_penalty = (
        0.20 * risk["env_install_noise_rate"]
        + 0.15 * risk["destructive_command_rate"]
        + 0.15 * risk["parse_error_rate"]
        + 0.10 * risk["unpaired_tool_rate"]
        + (0.20 if risk["privacy_risk_flag"] else 0.0)
    )
    score = 100.0 * (
        0.20 * math.log1p(exec_count)
        + 0.22 * math.log1p(patch_count)
        + 0.24 * math.log1p(verifier_count)
        + 0.14 * math.log1p(loop_count)
        + 0.07 * density["pair_quality"]
        + 0.05 * density["user_task_density"]
    ) - 100.0 * noise_penalty
    return score, density, risk


def main() -> int:
    chats = {row["chat_id"]: row for _, row in iter_jsonl(CHATS) or []}
    profiles: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for _, row in iter_jsonl(WINDOWS) or []:
        if row.get("training_potential") != "level_2_patch_and_verifier_refs_needs_state_join":
            continue
        chat = chats.get(row["chat_id"], {})
        command_heads = {str(k): int(v) for k, v in (row.get("command_head_counts_top") or {}).items()}
        exclusions: list[str] = []
        if not chat:
            exclusions.append("missing_chat_manifest")
        if row.get("raw_content_emitted"):
            exclusions.append("raw_content_emitted")
        if int(row.get("event_count") or 0) < 3:
            exclusions.append("event_count_lt_3")
        if not row.get("has_command_observation"):
            exclusions.append("missing_paired_command_observation")
        if not row.get("has_patch_ref"):
            exclusions.append("missing_patch_ref")
        if not row.get("has_verifier_like_ref"):
            exclusions.append("missing_verifier_ref")
        if row.get("boundary_confidence") != "lifecycle_exact":
            exclusions.append("non_lifecycle_boundary")
        score, density, risk = score_window(row, chat)
        language = infer_language(command_heads)
        profile = {
            "shard_id": stable_id("source_shard", row.get("task_window_id"), row.get("chat_id")),
            "task_window_id": row.get("task_window_id"),
            "chat_id": row.get("chat_id"),
            "source_adapter": "codex_sessions",
            "source_root_label": chat.get("source_root_label") or "codex_sessions",
            "source_kind": chat.get("source_kind") or "codex_session_jsonl",
            "session_id_hint": row.get("session_id_hint"),
            "snapshot_id": row.get("snapshot_id"),
            "source_file_hash_compat": row.get("source_file_hash_compat"),
            "file_content_sha256": chat.get("file_content_sha256"),
            "line_start": row.get("start_line"),
            "line_end": row.get("end_line"),
            "event_start_id": row.get("start_event_id"),
            "event_end_id": row.get("terminal_event_id"),
            "event_count": row.get("event_count"),
            "paired_tool_calls": row.get("paired_tool_call_count"),
            "exec_command_count": row.get("exec_command_pair_count"),
            "patch_signal_count": row.get("patch_pair_count"),
            "verifier_command_count": row.get("verifier_like_pair_count"),
            "loop_count": min(int(row.get("patch_pair_count") or 0), int(row.get("verifier_like_pair_count") or 0)),
            "top_command_heads": command_heads,
            "likely_language_family": language,
            "density_features": density,
            "risk_features": risk,
            "score": score,
            "rank": None,
            "recommended_parser_mode": "line_window",
            "exclusion_codes": exclusions,
            "audit_bucket": "patch_verify_loop",
            "source_root_repaired_from_chat_manifest": bool(chat),
            "training_allowed": False,
        }
        if exclusions:
            excluded.append(profile)
        else:
            profiles.append(profile)

    profiles.sort(
        key=lambda r: (
            -float(r["score"]),
            -int(r["loop_count"]),
            -int(r["verifier_command_count"]),
            -int(r["patch_signal_count"]),
            int(r["event_count"]),
            str(r["chat_id"]),
            int(r["line_start"] or 0),
        )
    )
    for idx, row in enumerate(profiles, 1):
        row["rank"] = idx

    selected: list[dict[str, Any]] = []
    per_chat: Counter[str] = Counter()
    per_lang: Counter[str] = Counter()
    for row in profiles:
        if len(selected) >= 25:
            break
        if per_chat[row["chat_id"]] >= 3:
            continue
        selected_row = dict(row)
        selected_row["selection_reason"] = "top_ranked_patch_verify_loop_under_max3_per_chat_cap"
        selected.append(selected_row)
        per_chat[row["chat_id"]] += 1
        per_lang[row["likely_language_family"]] += 1

    summary = {
        "stage": STAGE,
        "artifact_type": "high_value_window_profiler",
        "decision": "capped_audit_set_ready_no_admission",
        "training_allowed": False,
        "claim_boundary": "Metadata/digest profiler only. No raw content, no episode admission, no root admission, no training rows.",
        "input": {
            "stage12260_windows": str(WINDOWS.relative_to(ROOT)),
            "stage12258_chats": str(CHATS.relative_to(ROOT)),
        },
        "counts": {
            "input_level2_patch_verifier_windows": len(profiles) + len(excluded),
            "eligible_profiles": len(profiles),
            "excluded_profiles": len(excluded),
            "selected_audit_windows": len(selected),
            "max_per_chat": 3,
            "selected_per_chat": dict(per_chat),
            "selected_language_family_counts": dict(per_lang),
            "eligible_top_chats": Counter(r["chat_id"] for r in profiles).most_common(10),
        },
        "guardrails": {
            "raw_message_text_emitted": False,
            "raw_tool_output_emitted": False,
            "raw_tool_arguments_emitted": False,
            "raw_patch_body_emitted": False,
            "root_admission_emitted": False,
            "training_rows_emitted_now": False,
        },
        "next_stage": {
            "stage": "stage12264_small_episode_graph_candidate_projection_audit",
            "scope": "convert only capped audit windows into candidate skeletons and validate, no admission",
            "training_allowed": False,
        },
    }

    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_jsonl(out_dir / "source_shard_profiles.jsonl", profiles)
    write_jsonl(out_dir / "top25_audit_set.jsonl", selected)
    if excluded:
        write_jsonl(out_dir / "excluded_profiles.jsonl", excluded)
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", summary)
    write_json(out_dir / "high_value_window_profiler_summary.json", summary)
    md = f"""# Stage12263 High-Value Window Profiler

## Decision

`{summary["decision"]}`

No training is allowed.

## Counts

- input patch+verifier windows: `{summary["counts"]["input_level2_patch_verifier_windows"]}`
- eligible profiles: `{len(profiles)}`
- selected audit windows: `{len(selected)}`
- max per chat: `3`

The selected set is capped before any GPT review.
"""
    write_text(out_dir / "HIGH_VALUE_WINDOW_PROFILER_STAGE12263.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "top25_audit_set.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build Stage12260 Codex chat task boundary miner.

Uses Stage12258 per-chat event refs and Stage12259 tool-call/observation pairs
to segment live Codex chats into task windows. This is boundary/source mining
only: no raw chat content, no raw tool output, no root admission, no training.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12260_codex_chat_task_boundary_miner"
STAGE12258 = ROOT / "runs/local/artifacts/stage12258_live_codex_chat_reconstruction_index"
STAGE12259 = ROOT / "runs/local/artifacts/stage12259_codex_tool_call_observation_pairer"


VERIFY_HEADS = {
    "pytest",
    "ctest",
    "cargo",
    "npm",
    "npx",
    "pnpm",
    "node",
    "python",
    "python3",
    "cmake",
    "make",
    "bash",
    "./node_modules/.bin/vitest",
    "./node_modules/.bin/tsc",
}
READ_HEADS = {"sed", "cat", "head", "tail", "nl", "rg", "find", "ls", "jq", "grep"}
VCS_HEADS = {"git"}


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


def in_range(line: int | None, start: int, end: int) -> bool:
    if line is None:
        return False
    return start <= int(line) <= end


def command_family(head: str | None) -> str:
    if not head:
        return "other_or_non_command"
    if head in READ_HEADS:
        return "read_or_search"
    if head in VCS_HEADS:
        return "version_control"
    if head in VERIFY_HEADS or "pytest" in head or "vitest" in head or "tsc" in head:
        return "verifier_or_execution"
    if head in {"python", "python3"} or head.endswith("/python"):
        return "python_execution"
    return "other_command"


def build_windows_for_chat(chat: dict[str, Any], events: list[dict[str, Any]], pairs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    windows: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    if not events:
        blocked.append({"chat_id": chat["chat_id"], "reason": "no_events"})
        return windows, blocked
    events = sorted(events, key=lambda e: int(e.get("line_number") or 0))
    pairs = sorted(pairs, key=lambda p: int(p.get("call_line_number") or 0))

    starts = [e for e in events if e.get("event_type") == "event_msg" and e.get("payload_type") == "task_started"]
    terminals = [
        e
        for e in events
        if e.get("event_type") == "event_msg" and e.get("payload_type") in {"task_complete", "turn_aborted"}
    ]
    if not starts:
        # Fallback: user message to end, but mark lower confidence.
        user_events = [e for e in events if e.get("role") == "user" or e.get("payload_type") == "user_message"]
        starts = user_events[:1]
    if not starts:
        blocked.append({"chat_id": chat["chat_id"], "reason": "no_task_start_or_user_boundary"})
        return windows, blocked

    event_lines = [int(e["line_number"]) for e in events if e.get("line_number") is not None]
    chat_end = max(event_lines) if event_lines else int(chat.get("event_count") or 0)
    terminals_sorted = sorted(terminals, key=lambda e: int(e.get("line_number") or 0))
    starts_sorted = sorted(starts, key=lambda e: int(e.get("line_number") or 0))

    boundary_specs: list[dict[str, Any]] = []
    for idx, start in enumerate(starts_sorted):
        start_line = int(start.get("line_number") or 1)
        next_start_line = int(starts_sorted[idx + 1].get("line_number") or (chat_end + 1)) if idx + 1 < len(starts_sorted) else chat_end + 1
        terminal = next((t for t in terminals_sorted if start_line <= int(t.get("line_number") or 0) < next_start_line), None)
        end_line = int(terminal.get("line_number")) if terminal else next_start_line - 1
        if end_line < start_line:
            continue
        boundary_specs.append({"start": start, "terminal": terminal, "start_line": start_line, "end_line": end_line})

    event_idx = 0
    pair_idx = 0
    for spec in boundary_specs:
        start = spec["start"]
        terminal = spec["terminal"]
        start_line = spec["start_line"]
        end_line = spec["end_line"]
        while event_idx < len(events) and int(events[event_idx].get("line_number") or 0) < start_line:
            event_idx += 1
        event_scan = event_idx
        window_events: list[dict[str, Any]] = []
        while event_scan < len(events) and int(events[event_scan].get("line_number") or 0) <= end_line:
            window_events.append(events[event_scan])
            event_scan += 1
        event_idx = event_scan

        while pair_idx < len(pairs) and int(pairs[pair_idx].get("call_line_number") or 0) < start_line:
            pair_idx += 1
        pair_scan = pair_idx
        window_pairs: list[dict[str, Any]] = []
        while pair_scan < len(pairs) and int(pairs[pair_scan].get("call_line_number") or 0) <= end_line:
            window_pairs.append(pairs[pair_scan])
            pair_scan += 1
        pair_idx = pair_scan

        et_counts = Counter(str(e.get("payload_type") or e.get("event_type") or "") for e in window_events)
        tool_counts = Counter(str(p.get("tool_name") or "") for p in window_pairs)
        cmd_families = Counter(command_family(p.get("command_head")) for p in window_pairs)
        command_heads = Counter(str(p.get("command_head") or "") for p in window_pairs if p.get("command_head"))
        verifier_pairs = [p for p in window_pairs if command_family(p.get("command_head")) in {"verifier_or_execution", "python_execution"}]
        patch_pairs = [p for p in window_pairs if p.get("tool_name") == "apply_patch"]
        exec_pairs = [p for p in window_pairs if p.get("tool_name") == "exec_command"]
        terminal_status = str(terminal.get("payload_type")) if terminal else "no_terminal_event"
        boundary_confidence = "lifecycle_exact" if terminal and start.get("payload_type") == "task_started" else "fallback_or_partial"
        training_potential = "level_0_boundary_only"
        if window_pairs:
            training_potential = "level_1_action_observation_index"
        if patch_pairs and verifier_pairs:
            training_potential = "level_2_patch_and_verifier_refs_needs_state_join"
        windows.append(
            {
                "task_window_id": stable_id("codex_task_window", chat["chat_id"], start_line, end_line),
                "chat_id": chat["chat_id"],
                "session_id_hint": chat.get("session_id_hint"),
                "snapshot_id": chat.get("snapshot_id"),
                "source_file_hash_compat": chat.get("source_file_hash_compat"),
                "start_line": start_line,
                "end_line": end_line,
                "line_count": end_line - start_line + 1,
                "start_event_id": start.get("event_id"),
                "terminal_event_id": terminal.get("event_id") if terminal else None,
                "terminal_status": terminal_status,
                "boundary_confidence": boundary_confidence,
                "event_count": len(window_events),
                "paired_tool_call_count": len(window_pairs),
                "exec_command_pair_count": len(exec_pairs),
                "patch_pair_count": len(patch_pairs),
                "verifier_like_pair_count": len(verifier_pairs),
                "event_payload_type_counts": dict(et_counts),
                "tool_name_counts": dict(tool_counts),
                "command_family_counts": dict(cmd_families),
                "command_head_counts_top": dict(command_heads.most_common(20)),
                "has_user_signal": any(e.get("role") == "user" or e.get("payload_type") == "user_message" for e in window_events),
                "has_assistant_signal": any(e.get("role") == "assistant" or e.get("payload_type") == "agent_message" for e in window_events),
                "has_command_observation": bool(window_pairs),
                "has_patch_ref": bool(patch_pairs),
                "has_verifier_like_ref": bool(verifier_pairs),
                "training_potential": training_potential,
                "raw_content_emitted": False,
                "training_allowed": False,
            }
        )
    return windows, blocked


def main() -> int:
    chats = [row for _, row in iter_jsonl(STAGE12258 / "per_chat_manifest.jsonl") or []]
    events_by_chat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pairs_by_chat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for _, row in iter_jsonl(STAGE12258 / "chat_event_index.jsonl") or []:
        events_by_chat[row["chat_id"]].append(row)
    for _, row in iter_jsonl(STAGE12259 / "tool_call_observation_pairs.jsonl") or []:
        pairs_by_chat[row["chat_id"]].append(row)

    all_windows: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for chat in chats:
        windows, blocked_rows = build_windows_for_chat(chat, events_by_chat.get(chat["chat_id"], []), pairs_by_chat.get(chat["chat_id"], []))
        all_windows.extend(windows)
        blocked.extend(blocked_rows)

    by_potential = Counter(w["training_potential"] for w in all_windows)
    by_terminal = Counter(w["terminal_status"] for w in all_windows)
    by_confidence = Counter(w["boundary_confidence"] for w in all_windows)
    candidate_windows = [w for w in all_windows if w["has_command_observation"] and w["boundary_confidence"] == "lifecycle_exact"]
    patch_verifier_windows = [w for w in all_windows if w["has_patch_ref"] and w["has_verifier_like_ref"]]
    complete_windows = [w for w in all_windows if w["terminal_status"] == "task_complete"]

    summary = {
        "stage": STAGE,
        "artifact_type": "codex_chat_task_boundary_miner",
        "decision": "task_boundaries_ready_for_candidate_root_projection_training_blocked",
        "training_allowed": False,
        "claim_boundary": (
            "Task boundary/source-window artifact only. No raw chat content, no raw tool output, no patch bodies, "
            "no root admission, and no training rows."
        ),
        "counts": {
            "source_chats": len(chats),
            "task_windows": len(all_windows),
            "blocked_chats": len(blocked),
            "complete_task_windows": len(complete_windows),
            "candidate_windows_with_command_observation": len(candidate_windows),
            "patch_and_verifier_ref_windows": len(patch_verifier_windows),
            "training_potential_counts": dict(by_potential),
            "terminal_status_counts": dict(by_terminal),
            "boundary_confidence_counts": dict(by_confidence),
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
            "stage": "stage12261_codex_task_window_root_candidate_projector",
            "purpose": "Project root candidates from task windows, grouped by repo/workdir/evidence availability, still without admission.",
            "training_allowed": False,
        },
    }

    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_jsonl(out_dir / "codex_task_windows.jsonl", all_windows)
    if blocked:
        write_jsonl(out_dir / "blocked_chats.jsonl", blocked)
    write_json(out_dir / "codex_task_boundary_summary.json", summary)
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", summary)
    md = f"""# Stage12260 Codex Chat Task Boundary Miner

## Decision

`{summary["decision"]}`

No training is allowed.

## Counts

- source chats: `{len(chats)}`
- task windows: `{len(all_windows)}`
- candidate windows with command observations: `{len(candidate_windows)}`
- patch + verifier-ref windows: `{len(patch_verifier_windows)}`

The next stage may project candidate roots from these task windows, but must still keep root admission separate.
"""
    write_text(out_dir / "CODEX_CHAT_TASK_BOUNDARY_MINER_STAGE12260.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "codex_task_windows.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

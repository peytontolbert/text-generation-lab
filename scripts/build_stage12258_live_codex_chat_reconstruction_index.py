#!/usr/bin/env python3
"""Build Stage12258 live Codex chat reconstruction index.

This indexes individual live Codex session JSONLs as first-class source chats.
It does not emit raw user/assistant text, tool output, or patch bodies. It emits
line-level refs, digests, and completeness counters so later miners can rehydrate
specific records from the raw source under the same snapshot.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12258_live_codex_chat_reconstruction_index"
CODEX_SESSIONS = Path("/home/peyton/.codex/sessions")


def sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    return f"{prefix}_{sha256_json(parts)[:20]}"


def iso_utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def command_head(cmd: str) -> str:
    parts = str(cmd or "").strip().split()
    return parts[0] if parts else ""


def safe_json(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                return json.loads(text)
            except Exception:
                return value
    return value


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


def payload_digest(payload: dict[str, Any]) -> str:
    scrubbed = dict(payload)
    for key in ("content", "output", "arguments", "message", "encrypted_content", "summary"):
        if key in scrubbed:
            scrubbed[key] = f"<{key}:redacted:{sha256_json(scrubbed[key])[:16]}>"
    return sha256_json(scrubbed)


def parse_tool_args(payload: dict[str, Any]) -> dict[str, Any]:
    args = safe_json(payload.get("arguments"))
    return args if isinstance(args, dict) else {}


def iter_session_files() -> list[Path]:
    if not CODEX_SESSIONS.exists():
        return []
    return sorted(p for p in CODEX_SESSIONS.rglob("*.jsonl") if p.is_file())


def main() -> int:
    snapshot_id = f"live_codex_sessions_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    chat_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    tool_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []
    aggregate_event_types: Counter[str] = Counter()
    aggregate_tools: Counter[str] = Counter()
    aggregate_roles: Counter[str] = Counter()
    aggregate_command_heads: Counter[str] = Counter()

    for path in iter_session_files():
        try:
            stat = path.stat()
            rel = str(path.relative_to(CODEX_SESSIONS))
            raw_bytes = path.read_bytes()
        except Exception as exc:
            blocked_rows.append({"path_hash": sha1_text(str(path)), "reason": "read_failed", "error": str(exc)})
            continue
        source_file_hash_compat = sha1_text(str(path))
        chat_id = stable_id("codex_chat", source_file_hash_compat, stat.st_size, stat.st_mtime_ns)
        rel_hash = sha1_text(rel)
        content_sha256 = sha256_bytes(raw_bytes)
        event_type_counts: Counter[str] = Counter()
        payload_type_counts: Counter[str] = Counter()
        role_counts: Counter[str] = Counter()
        tool_counts: Counter[str] = Counter()
        command_head_counts: Counter[str] = Counter()
        parse_error_count = 0
        event_count = 0
        tool_call_count = 0
        tool_output_count = 0
        exec_command_count = 0
        apply_patch_count = 0
        write_stdin_count = 0
        first_timestamp = None
        last_timestamp = None
        session_meta_seen = False
        turn_context_count = 0
        cwd_hints: Counter[str] = Counter()
        workspace_root_hints: Counter[str] = Counter()

        for line_no, raw_line in enumerate(raw_bytes.splitlines(), 1):
            try:
                obj = json.loads(raw_line.decode("utf-8", errors="ignore"))
            except Exception as exc:
                parse_error_count += 1
                event_rows.append(
                    {
                        "chat_id": chat_id,
                        "event_id": stable_id("chat_event", chat_id, line_no),
                        "line_number": line_no,
                        "parse_status": "json_error",
                        "error_digest": sha256_json(str(exc)),
                        "raw_content_emitted": False,
                    }
                )
                continue
            if not isinstance(obj, dict):
                parse_error_count += 1
                continue
            event_count += 1
            event_type = str(obj.get("type") or "")
            payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
            payload_type = str(payload.get("type") or "")
            role = str(payload.get("role") or "")
            tool_name = str(payload.get("name") or "")
            call_id = str(payload.get("call_id") or payload.get("id") or "")
            ts = str(obj.get("timestamp") or payload.get("timestamp") or "")
            if ts:
                first_timestamp = first_timestamp or ts
                last_timestamp = ts
            if event_type == "session_meta":
                session_meta_seen = True
            if event_type == "turn_context":
                turn_context_count += 1
            if isinstance(payload.get("cwd"), str):
                cwd_hints[payload["cwd"]] += 1
            for wr in payload.get("workspace_roots") or []:
                if isinstance(wr, str):
                    workspace_root_hints[wr] += 1

            args = parse_tool_args(payload)
            cmd_head = command_head(str(args.get("cmd") or ""))
            has_output = "output" in payload
            has_arguments = "arguments" in payload
            event_type_counts[event_type] += 1
            payload_type_counts[payload_type] += 1
            role_counts[role] += 1
            if tool_name:
                tool_counts[tool_name] += 1
            if cmd_head:
                command_head_counts[cmd_head] += 1

            event_id = stable_id("chat_event", chat_id, line_no)
            event_rows.append(
                {
                    "chat_id": chat_id,
                    "event_id": event_id,
                    "line_number": line_no,
                    "timestamp": ts,
                    "event_type": event_type,
                    "payload_type": payload_type,
                    "role": role,
                    "tool_name": tool_name,
                    "call_id": call_id or None,
                    "command_head": cmd_head or None,
                    "has_arguments": has_arguments,
                    "has_output": has_output,
                    "has_content": "content" in payload or "message" in payload,
                    "payload_digest_redacted": payload_digest(payload),
                    "raw_content_emitted": False,
                }
            )
            if tool_name:
                tool_call_count += 1
                if has_output:
                    tool_output_count += 1
                if tool_name == "exec_command":
                    exec_command_count += 1
                if tool_name == "apply_patch":
                    apply_patch_count += 1
                if tool_name == "write_stdin":
                    write_stdin_count += 1
                tool_rows.append(
                    {
                        "chat_id": chat_id,
                        "tool_record_id": stable_id("chat_tool", chat_id, line_no, call_id, tool_name),
                        "event_id": event_id,
                        "line_number": line_no,
                        "tool_name": tool_name,
                        "call_id": call_id or None,
                        "command_head": cmd_head or None,
                        "arguments_digest": sha256_json(args) if args else None,
                        "output_digest": sha256_json(payload.get("output")) if has_output else None,
                        "has_arguments": has_arguments,
                        "has_output": has_output,
                        "raw_arguments_emitted": False,
                        "raw_output_emitted": False,
                    }
                )

        aggregate_event_types.update(event_type_counts)
        aggregate_tools.update(tool_counts)
        aggregate_roles.update(role_counts)
        aggregate_command_heads.update(command_head_counts)
        chat_rows.append(
            {
                "chat_id": chat_id,
                "snapshot_id": snapshot_id,
                "source_root_label": "codex_sessions",
                "source_kind": "codex_session_jsonl",
                "source_file_hash_compat": source_file_hash_compat,
                "relative_path_hash": rel_hash,
                "file_content_sha256": content_sha256,
                "file_size_bytes": stat.st_size,
                "mtime_utc": iso_utc(stat.st_mtime),
                "session_id_hint": path.stem,
                "raw_source_available": True,
                "raw_source_path_emitted": False,
                "raw_content_emitted": False,
                "event_count": event_count,
                "parse_error_count": parse_error_count,
                "event_type_counts": dict(event_type_counts),
                "payload_type_counts": dict(payload_type_counts),
                "role_counts": dict(role_counts),
                "tool_name_counts": dict(tool_counts),
                "command_head_counts": dict(command_head_counts),
                "tool_call_count": tool_call_count,
                "tool_output_count": tool_output_count,
                "exec_command_count": exec_command_count,
                "apply_patch_count": apply_patch_count,
                "write_stdin_count": write_stdin_count,
                "session_meta_seen": session_meta_seen,
                "turn_context_count": turn_context_count,
                "first_timestamp": first_timestamp,
                "last_timestamp": last_timestamp,
                "cwd_hints_top": cwd_hints.most_common(10),
                "workspace_root_hints_top": workspace_root_hints.most_common(10),
                "completeness_flags": {
                    "json_parse_clean": parse_error_count == 0,
                    "has_session_meta": session_meta_seen,
                    "has_any_user_message": role_counts.get("user", 0) > 0,
                    "has_any_assistant_message": role_counts.get("assistant", 0) > 0,
                    "has_tool_calls": tool_call_count > 0,
                    "has_tool_outputs": tool_output_count > 0,
                    "has_exec_commands": exec_command_count > 0,
                    "has_patches": apply_patch_count > 0,
                },
                "admission_status": "source_chat_index_only",
                "training_allowed": False,
            }
        )

    complete_source_chats = sum(1 for row in chat_rows if row["completeness_flags"]["json_parse_clean"] and row["event_count"] > 0)
    summary = {
        "stage": STAGE,
        "artifact_type": "live_codex_chat_reconstruction_index",
        "decision": "live_codex_chat_source_index_ready_training_blocked",
        "training_allowed": False,
        "claim_boundary": (
            "Per-chat source index only. Raw chat text, raw tool outputs, raw arguments, and patch bodies are not emitted. "
            "No root admission or training is authorized."
        ),
        "snapshot_id": snapshot_id,
        "counts": {
            "live_codex_chat_files": len(chat_rows),
            "complete_source_chats": complete_source_chats,
            "event_index_rows": len(event_rows),
            "tool_call_index_rows": len(tool_rows),
            "blocked_files": len(blocked_rows),
            "aggregate_event_type_counts": dict(aggregate_event_types),
            "aggregate_tool_name_counts": dict(aggregate_tools),
            "aggregate_role_counts": dict(aggregate_roles),
            "aggregate_command_head_counts_top": dict(aggregate_command_heads.most_common(40)),
        },
        "guardrails": {
            "raw_message_text_emitted": False,
            "raw_tool_output_emitted": False,
            "raw_tool_arguments_emitted": False,
            "raw_patch_body_emitted": False,
            "training_rows_emitted_now": False,
        },
        "output_artifacts": {
            "per_chat_manifest": f"runs/local/artifacts/{STAGE}/per_chat_manifest.jsonl",
            "chat_event_index": f"runs/local/artifacts/{STAGE}/chat_event_index.jsonl",
            "chat_tool_call_index": f"runs/local/artifacts/{STAGE}/chat_tool_call_index.jsonl",
            "blocked_files": f"runs/local/artifacts/{STAGE}/blocked_files.jsonl",
        },
        "next_stage": {
            "stage": "stage12259_codex_chat_task_boundary_miner",
            "purpose": "Use per-chat event/tool refs to mine task boundaries and candidate roots without reparsing partial subsets.",
            "training_allowed": False,
        },
    }

    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_jsonl(out_dir / "per_chat_manifest.jsonl", chat_rows)
    write_jsonl(out_dir / "chat_event_index.jsonl", event_rows)
    write_jsonl(out_dir / "chat_tool_call_index.jsonl", tool_rows)
    if blocked_rows:
        write_jsonl(out_dir / "blocked_files.jsonl", blocked_rows)
    write_json(out_dir / "live_codex_chat_reconstruction_summary.json", summary)
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", summary)
    md = f"""# Stage12258 Live Codex Chat Reconstruction Index

## Decision

`{summary["decision"]}`

No training is allowed.

## Output

- per-chat manifests: `{len(chat_rows)}`
- event index rows: `{len(event_rows)}`
- tool call index rows: `{len(tool_rows)}`
- blocked files: `{len(blocked_rows)}`

This is the first correct unit for Codex chat mining: one source chat first, then task boundaries, then roots.
"""
    write_text(out_dir / "LIVE_CODEX_CHAT_RECONSTRUCTION_INDEX_STAGE12258.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "per_chat_manifest.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from long_context_common import write_json, write_jsonl


FILE_HEADER_RE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$")
PATH_RE = re.compile(r"(?:^|[\s'\"`])((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.[A-Za-z0-9_]+)")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _path_hash(path: str) -> str:
    return hashlib.sha1(path.encode("utf-8")).hexdigest()


def _safe_json_loads(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text.startswith("{"):
        return None
    try:
        decoded = json.loads(text)
    except Exception:
        return None
    return decoded if isinstance(decoded, dict) else None


def _command_head(cmd: str) -> str:
    parts = str(cmd or "").strip().split()
    return parts[0] if parts else ""


def _tool_file_refs(tool_name: str, tool_args: dict[str, Any] | None, payload: dict[str, Any]) -> list[str]:
    refs: set[str] = set()
    tool_args = tool_args or {}
    for key in ("workdir", "path", "input", "output", "manifest", "file", "files", "trainer_rows", "episodes", "output_dir"):
        value = tool_args.get(key)
        if isinstance(value, str):
            for match in PATH_RE.findall(value):
                refs.add(match)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    for match in PATH_RE.findall(item):
                        refs.add(match)
    if tool_name == "apply_patch":
        patch_text = str(tool_args.get("patch") or tool_args.get("input") or payload.get("input") or "")
        for line in patch_text.splitlines():
            matched = FILE_HEADER_RE.match(line.strip())
            if matched:
                refs.add(matched.group(1).strip())
    return sorted(refs)[:16]


def _normalized_event_type(*, root_label: str, raw_type: str, role: str, tool_name: str, command_head: str, success: bool | None) -> str:
    if root_label.startswith("cursor_"):
        if role == "user":
            return "user_message"
        if role == "assistant":
            return "assistant_message"
        return "cursor_event"
    if raw_type == "session_meta":
        return "session_meta"
    if raw_type == "turn_context":
        return "turn_context"
    if raw_type == "event_msg":
        if tool_name == "exec_command":
            if command_head in {"pytest", "python"}:
                return "verification_command"
            return "tool_call_exec_command"
        if tool_name == "apply_patch":
            return "patch_applied"
        if tool_name:
            return "tool_call_other"
        return "commentary_update"
    if raw_type == "response_item":
        if tool_name == "exec_command":
            return "tool_call_exec_command"
        if tool_name == "apply_patch":
            return "patch_applied"
        if tool_name:
            return "tool_call_other"
        if role == "assistant":
            return "assistant_message"
        if role == "user":
            return "user_message"
        return "response_item"
    if raw_type == "user_message":
        return "user_message"
    if raw_type == "agent_message":
        return "assistant_message"
    if raw_type == "task_complete":
        return "final_verified_summary" if success else "task_complete"
    return raw_type or "unknown_event"


def _iter_planned_files(parse_plan: list[dict[str, Any]]) -> Iterable[tuple[str, Path]]:
    for root_plan in parse_plan:
        root_label = str(root_plan.get("source_root_label") or "")
        root_path = Path(str(root_plan.get("root_path") or "")).expanduser()
        explicit_relative_paths = list(root_plan.get("explicit_relative_paths") or [])
        require_explicit_paths = bool(root_plan.get("require_explicit_paths") is True)
        if explicit_relative_paths:
            seen: set[Path] = set()
            for relative_path in explicit_relative_paths:
                candidate = (root_path / str(relative_path)).resolve()
                if candidate in seen:
                    continue
                seen.add(candidate)
                if not candidate.is_file():
                    if require_explicit_paths:
                        raise FileNotFoundError(f"missing_explicit_session_file:{candidate}")
                    continue
                yield root_label, candidate
            continue
        file_sort_mode = str(root_plan.get("file_sort_mode") or "path_asc")
        for ext_plan in root_plan.get("extension_plan", []):
            if str(ext_plan.get("parse_mode") or "") != "content_parser_candidate":
                continue
            extension = str(ext_plan.get("extension") or "")
            cap = int(ext_plan.get("file_cap") or 0)
            if cap <= 0 or not root_path.exists():
                continue
            matches = [path for path in root_path.rglob(f"*{extension}") if path.is_file()]
            if file_sort_mode == "mtime_desc":
                matches.sort(key=lambda path: (-path.stat().st_mtime_ns, str(path)))
            else:
                matches.sort()
            matches = matches[:cap]
            for path in matches:
                yield root_label, path


def _parse_codex_line(root_label: str, path: Path, line_number: int, obj: dict[str, Any], fallback_cwd: str = "") -> dict[str, Any]:
    raw_type = str(obj.get("type") or "")
    payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
    tool_name = str(payload.get("name") or "")
    tool_args = _safe_json_loads(payload.get("arguments"))
    command_head = _command_head(str((tool_args or {}).get("cmd") or ""))
    role = str(payload.get("role") or "")
    status = str(payload.get("status") or "")
    success_value = payload.get("success")
    success = bool(success_value) if isinstance(success_value, bool) else None
    cwd = str(payload.get("cwd") or fallback_cwd or "")
    repo_hint = Path(cwd).name if cwd else ""
    file_refs = _tool_file_refs(tool_name, tool_args, payload)
    if cwd and repo_hint:
        file_refs = sorted(set(file_refs + [cwd]))
    return {
        "source_root_label": root_label,
        "source_file_hash": _path_hash(str(path)),
        "session_id_hint": path.stem,
        "line_number": int(line_number),
        "raw_event_type": raw_type,
        "normalized_event_type": _normalized_event_type(
            root_label=root_label,
            raw_type=raw_type,
            role=role,
            tool_name=tool_name,
            command_head=command_head,
            success=success,
        ),
        "role": role,
        "tool_name": tool_name,
        "command_head": command_head,
        "status": status,
        "success": success,
        "repo_hint": repo_hint,
        "file_path_refs": file_refs[:16],
        "timestamp": str(obj.get("timestamp") or ""),
    }


def _parse_cursor_line(root_label: str, path: Path, line_number: int, obj: dict[str, Any]) -> dict[str, Any]:
    role = str(obj.get("role") or "")
    message = obj.get("message") if isinstance(obj.get("message"), dict) else {}
    content = message.get("content") if isinstance(message.get("content"), list) else []
    content_types = sorted({str(item.get("type") or "") for item in content if isinstance(item, dict)})
    repo_hint = ""
    for part in path.parts[::-1]:
        if part not in {"agent-transcripts", path.name} and not part.endswith(".jsonl"):
            repo_hint = part
            break
    return {
        "source_root_label": root_label,
        "source_file_hash": _path_hash(str(path)),
        "session_id_hint": path.stem,
        "line_number": int(line_number),
        "raw_event_type": role,
        "normalized_event_type": _normalized_event_type(
            root_label=root_label,
            raw_type="",
            role=role,
            tool_name="",
            command_head="",
            success=None,
        ),
        "role": role,
        "tool_name": "",
        "command_head": "",
        "status": "",
        "success": None,
        "repo_hint": repo_hint,
        "file_path_refs": [],
        "timestamp": "",
        "content_types": content_types,
    }


def parse_bounded_session_jsonl_metadata(
    *,
    parser_ticket_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    ticket = _read_json(parser_ticket_path)
    event_rows: list[dict[str, Any]] = []
    session_stats: dict[tuple[str, str], dict[str, Any]] = {}
    root_counter: Counter[str] = Counter()

    for root_label, path in _iter_planned_files(list(ticket.get("parse_plan") or [])):
        session_key = (root_label, path.stem)
        session_cwd = ""
        stats = session_stats.setdefault(
            session_key,
            {
                "source_root_label": root_label,
                "source_file_hash": _path_hash(str(path)),
                "session_id_hint": path.stem,
                "event_count": 0,
                "normalized_event_type_counts": Counter(),
                "tool_name_counts": Counter(),
                "repo_hints": Counter(),
                "file_path_refs": set(),
            },
        )
        parser = _parse_codex_line if root_label == "codex_sessions" else _parse_cursor_line
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line_number, line in enumerate(handle, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    obj = json.loads(text)
                except Exception:
                    continue
                if not isinstance(obj, dict):
                    continue
                if root_label == "codex_sessions":
                    payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
                    if str(obj.get("type") or "") in {"session_meta", "turn_context"}:
                        session_cwd = str(payload.get("cwd") or session_cwd or "")
                    event = parser(root_label, path, line_number, obj, session_cwd)
                    session_cwd = str(event.get("repo_hint") or session_cwd or "") if session_cwd else session_cwd
                else:
                    event = parser(root_label, path, line_number, obj)
                event_rows.append(event)
                stats["event_count"] += 1
                stats["normalized_event_type_counts"][str(event.get("normalized_event_type") or "")] += 1
                if str(event.get("tool_name") or ""):
                    stats["tool_name_counts"][str(event["tool_name"])] += 1
                if str(event.get("repo_hint") or ""):
                    stats["repo_hints"][str(event["repo_hint"])] += 1
                for ref in event.get("file_path_refs") or []:
                    stats["file_path_refs"].add(str(ref))
                root_counter[root_label] += 1

    session_rows: list[dict[str, Any]] = []
    for stats in session_stats.values():
        session_rows.append(
            {
                "source_root_label": str(stats["source_root_label"]),
                "source_file_hash": str(stats["source_file_hash"]),
                "session_id_hint": str(stats["session_id_hint"]),
                "event_count": int(stats["event_count"]),
                "normalized_event_type_counts": dict(sorted(stats["normalized_event_type_counts"].items())),
                "tool_name_counts": dict(sorted(stats["tool_name_counts"].items())),
                "repo_hints": dict(sorted(stats["repo_hints"].items())),
                "file_path_refs": sorted(stats["file_path_refs"])[:32],
            }
        )
    session_rows.sort(key=lambda row: (row["source_root_label"], -row["event_count"], row["session_id_hint"]))

    summary = {
        "parsed_event_rows": len(event_rows),
        "parsed_sessions": len(session_rows),
        "roots_observed": dict(sorted(root_counter.items())),
        "guardrails": {
            "raw_message_text_emitted": False,
            "raw_tool_output_emitted": False,
            "raw_patch_body_emitted": False,
            "training_rows_emitted_now": False,
        },
    }
    return event_rows, session_rows, summary


def materialize_bounded_session_jsonl_metadata(
    *,
    parser_ticket_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    event_rows, session_rows, summary = parse_bounded_session_jsonl_metadata(parser_ticket_path=parser_ticket_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "normalized_session_events.jsonl", event_rows)
    write_jsonl(output_dir / "session_event_summaries.jsonl", session_rows)
    write_json(output_dir / "session_parse_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse bounded session-like JSONL files into normalized metadata-only event rows.")
    parser.add_argument("--parser-ticket", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    materialize_bounded_session_jsonl_metadata(
        parser_ticket_path=args.parser_ticket,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()

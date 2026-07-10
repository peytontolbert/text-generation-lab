from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

from long_context_common import stable_id, write_json, write_jsonl
from parse_bounded_session_jsonl_metadata import PATH_RE, _safe_json_loads, _iter_planned_files
from runtime_trace_normalizer import normalize_runtime_trace


EXIT_RE = re.compile(r"Process exited with code (?P<code>-?\d+)")
RUNNING_RE = re.compile(r"Process running with session ID (?P<session_id>\d+)")
OUTPUT_RE = re.compile(r"\nOutput:\n(?P<body>[\s\S]*)\Z")
TRACE_PATH_HINTS = ("traceback", "error", "stderr", "stdout", "pytest", "assert", "exception", "failure", "test")
INFRA_FAILURE_TERMS = (
    "bwrap: loopback",
    "operation not permitted",
    "sandbox wrapper is failing",
    "failed rtm_newaddr",
)


def _command_head(cmd: str) -> str:
    parts = str(cmd or "").strip().split()
    return parts[0] if parts else ""


def _repo_hint(workdir: str) -> str:
    normalized = str(workdir or "").rstrip("/")
    return Path(normalized).name if normalized else ""


def _command_file_refs(tool_args: dict[str, Any] | None) -> list[str]:
    refs: set[str] = set()
    tool_args = tool_args or {}
    for key in ("cmd", "workdir", "file", "files", "path", "input", "output"):
        value = tool_args.get(key)
        if isinstance(value, str):
            refs.update(PATH_RE.findall(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    refs.update(PATH_RE.findall(item))
    return sorted(refs)[:32]


def _output_body(text: str) -> str:
    match = OUTPUT_RE.search(str(text or ""))
    if not match:
        return ""
    return str(match.group("body") or "").strip()


def _output_exit_code(text: str) -> int | None:
    match = EXIT_RE.search(str(text or ""))
    return int(match.group("code")) if match else None


def _signal_kind(*, command_head: str, cmd: str, exit_code: int | None, output_body: str) -> str:
    cmd_lower = str(cmd or "").lower()
    body_lower = str(output_body or "").lower()
    if command_head in {"pytest", "python"} or "pytest" in cmd_lower:
        return "verification"
    if exit_code not in (None, 0):
        return "runtime_failure"
    if any(term in body_lower for term in TRACE_PATH_HINTS):
        return "runtime_signal"
    return "command_output"


def _is_verification_command(command_head: str, cmd: str, path_refs: list[str]) -> bool:
    cmd_lower = str(cmd or "").lower()
    if command_head in {"pytest", "python"}:
        return True
    if "pytest" in cmd_lower or any("test" in ref.lower() for ref in path_refs):
        return True
    return False


def _is_infra_failure(output_body: str) -> bool:
    lower = str(output_body or "").lower()
    return any(term in lower for term in INFRA_FAILURE_TERMS)


def _keep_trace_row(*, exit_code: int | None, signal_kind: str, packet: dict[str, Any], path_refs: list[str], output_body: str, command_head: str, cmd: str) -> bool:
    if _is_infra_failure(output_body):
        return False
    if _is_verification_command(command_head, cmd, path_refs):
        return True
    if packet.get("frames") or packet.get("exception_type"):
        return True
    if exit_code not in (None, 0) and path_refs and command_head in {"python", "bash", "sh", "make", "cmake", "node", "npm"}:
        return True
    return False


def _summary_text(*, command_head: str, cmd: str, repo_hint: str, path_refs: list[str], exit_code: int | None, packet: dict[str, Any], output_body: str) -> str:
    frames = list(packet.get("frames") or [])[:4]
    frame_text = "; ".join(
        f'{Path(str(frame.get("path") or "")).name}:{frame.get("line") or 0}:{frame.get("function") or "<unknown>"}'
        for frame in frames
    )
    path_text = ", ".join(path_refs[:8]) if path_refs else "<none>"
    lines = [
        f"Session repo: {repo_hint or '<unknown>'}",
        f"Command head: {command_head or '<unknown>'}",
        f"Command: {cmd.strip()[:240]}",
        f"Exit code: {exit_code if exit_code is not None else '<unknown>'}",
        f"Failure type: {packet.get('failure_type') or 'unknown_runtime_failure'}",
        f"Exception type: {packet.get('exception_type') or '<none>'}",
        f"Exception message: {packet.get('exception_message') or '<none>'}",
        f"Referenced paths: {path_text}",
    ]
    if frame_text:
        lines.append(f"Trace frames: {frame_text}")
    elif output_body:
        lines.append("Trace frames: <none>")
    return "\n".join(lines)


def _iter_codex_files(parser_ticket_path: Path) -> Iterable[Path]:
    ticket = json.loads(parser_ticket_path.read_text(encoding="utf-8"))
    for root_label, path in _iter_planned_files(list(ticket.get("parse_plan") or [])):
        if root_label == "codex_sessions":
            yield path


def extract_codex_session_execution_traces(*, parser_ticket_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    trace_rows: list[dict[str, Any]] = []
    session_counts: dict[str, int] = {}

    for path in _iter_codex_files(parser_ticket_path):
        session_id_hint = path.stem
        call_args: dict[str, dict[str, Any]] = {}
        workdir_hint = ""
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
            raw_type = str(obj.get("type") or "")
            payload_type = str(payload.get("type") or "")
            if raw_type == "session_meta":
                workdir_hint = str(payload.get("cwd") or workdir_hint or "")
            elif raw_type == "turn_context":
                workdir_hint = str(payload.get("cwd") or workdir_hint or "")
            if payload_type == "function_call" and str(payload.get("name") or "") == "exec_command":
                args = _safe_json_loads(payload.get("arguments")) or {}
                call_args[str(payload.get("call_id") or "")] = args
                continue
            if payload_type != "function_call_output":
                continue
            call_id = str(payload.get("call_id") or "")
            args = call_args.get(call_id)
            if not args:
                continue
            cmd = str(args.get("cmd") or "")
            command_head = _command_head(cmd)
            workdir = str(args.get("workdir") or workdir_hint or "")
            repo_hint = _repo_hint(workdir)
            output_text = str(payload.get("output") or "")
            exit_code = _output_exit_code(output_text)
            output_body = _output_body(output_text)
            if not output_body and exit_code in (None, 0):
                continue
            packet = normalize_runtime_trace(output_body, row_id=f"{session_id_hint}:{call_id}")
            path_refs = sorted(set(_command_file_refs(args) + PATH_RE.findall(output_body)))[:32]
            signal_kind = _signal_kind(command_head=command_head, cmd=cmd, exit_code=exit_code, output_body=output_body)
            if not _keep_trace_row(
                exit_code=exit_code,
                signal_kind=signal_kind,
                packet=packet,
                path_refs=path_refs,
                output_body=output_body,
                command_head=command_head,
                cmd=cmd,
            ):
                continue
            trace_id = stable_id("sess_trace", session_id_hint, call_id, str(exit_code), packet.get("trace_id") or "")
            row = {
                "trace_id": trace_id,
                "source_root_label": "codex_sessions",
                "session_id_hint": session_id_hint,
                "repo_hint": repo_hint,
                "call_id": call_id,
                "command_head": command_head,
                "command": cmd,
                "workdir": workdir,
                "exit_code": exit_code,
                "signal_kind": signal_kind,
                "file_path_refs": path_refs,
                "runtime_trace": packet,
                "summary_text": _summary_text(
                    command_head=command_head,
                    cmd=cmd,
                    repo_hint=repo_hint,
                    path_refs=path_refs,
                    exit_code=exit_code,
                    packet=packet,
                    output_body=output_body,
                ),
            }
            trace_rows.append(row)
            session_counts[session_id_hint] = session_counts.get(session_id_hint, 0) + 1

    summary = {
        "trace_count": len(trace_rows),
        "session_count": len(session_counts),
        "sessions_with_traces": sum(1 for count in session_counts.values() if count > 0),
    }
    return trace_rows, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract normalized execution-trace packets from bounded raw Codex sessions.")
    parser.add_argument("--parser-ticket", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path)
    args = parser.parse_args()
    rows, summary = extract_codex_session_execution_traces(parser_ticket_path=args.parser_ticket)
    write_jsonl(args.output, rows)
    write_json(args.summary_output or args.output.with_name("session_execution_trace_summary.json"), summary)


if __name__ == "__main__":
    main()

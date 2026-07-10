from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from extract_codex_session_execution_traces import extract_codex_session_execution_traces  # noqa: E402


def test_extract_codex_session_execution_traces_normalizes_exec_failure(tmp_path: Path) -> None:
    codex_root = tmp_path / "codex"
    codex_root.mkdir()
    session_file = codex_root / "rollout-2026-07-09T00-00-00-abc.jsonl"
    session_file.write_text(
        "\n".join(
            [
                json.dumps({"type": "session_meta", "payload": {"cwd": "/repo_a", "id": "abc"}}),
                json.dumps({"type": "response_item", "payload": {"type": "function_call", "name": "exec_command", "arguments": json.dumps({"cmd": "pytest -q tests/test_app.py", "workdir": "/repo_a"}), "call_id": "c1"}}),
                json.dumps({"type": "response_item", "payload": {"type": "function_call_output", "call_id": "c1", "output": "Chunk ID: x\nWall time: 0.0\nProcess exited with code 1\nOriginal token count: 20\nOutput:\nTraceback (most recent call last):\n  File \"src/app.py\", line 12, in run\n    raise ValueError('bad shape')\nValueError: bad shape\n"}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ticket = tmp_path / "ticket.json"
    ticket.write_text(
        json.dumps(
            {
                "parse_plan": [
                    {
                        "source_root_label": "codex_sessions",
                        "root_path": str(codex_root),
                        "extension_plan": [{"extension": ".jsonl", "file_cap": 10, "parse_mode": "content_parser_candidate"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    rows, summary = extract_codex_session_execution_traces(parser_ticket_path=ticket)

    assert summary["trace_count"] == 1
    row = rows[0]
    assert row["session_id_hint"] == session_file.stem
    assert row["repo_hint"] == "repo_a"
    assert row["command_head"] == "pytest"
    assert row["exit_code"] == 1
    assert row["signal_kind"] == "verification"
    assert row["runtime_trace"]["failure_type"] == "runtime_contract_failure"
    assert "src/app.py" in row["summary_text"]
    assert "ValueError" in row["summary_text"]


def test_extract_codex_session_execution_traces_skips_infra_noise(tmp_path: Path) -> None:
    codex_root = tmp_path / "codex"
    codex_root.mkdir()
    session_file = codex_root / "rollout-2026-07-09T00-00-00-noise.jsonl"
    session_file.write_text(
        "\n".join(
            [
                json.dumps({"type": "session_meta", "payload": {"cwd": "/repo_a", "id": "noise"}}),
                json.dumps({"type": "response_item", "payload": {"type": "function_call", "name": "exec_command", "arguments": json.dumps({"cmd": "pwd", "workdir": "/repo_a"}), "call_id": "c1"}}),
                json.dumps({"type": "response_item", "payload": {"type": "function_call_output", "call_id": "c1", "output": "Chunk ID: x\nWall time: 0.0\nProcess exited with code 1\nOriginal token count: 16\nOutput:\nbwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\n"}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ticket = tmp_path / "ticket.json"
    ticket.write_text(
        json.dumps(
            {
                "parse_plan": [
                    {
                        "source_root_label": "codex_sessions",
                        "root_path": str(codex_root),
                        "extension_plan": [{"extension": ".jsonl", "file_cap": 10, "parse_mode": "content_parser_candidate"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    rows, summary = extract_codex_session_execution_traces(parser_ticket_path=ticket)

    assert summary["trace_count"] == 0
    assert rows == []

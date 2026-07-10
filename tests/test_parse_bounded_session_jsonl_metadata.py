from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from parse_bounded_session_jsonl_metadata import parse_bounded_session_jsonl_metadata  # noqa: E402


def test_parse_bounded_session_jsonl_metadata_normalizes_codex_and_cursor(tmp_path: Path) -> None:
    codex_root = tmp_path / "codex"
    cursor_root = tmp_path / "cursor"
    codex_root.mkdir()
    (cursor_root / "project-a").mkdir(parents=True)
    codex_file = codex_root / "s1.jsonl"
    codex_file.write_text(
        "\n".join(
            [
                json.dumps({"timestamp": "t0", "type": "session_meta", "payload": {"cwd": "/repo/a", "id": "s1"}}),
                json.dumps({"timestamp": "t1", "type": "event_msg", "payload": {"name": "exec_command", "arguments": json.dumps({"cmd": "pytest -q", "workdir": "/repo/a"}), "status": "completed"}}),
                json.dumps({"timestamp": "t2", "type": "response_item", "payload": {"name": "apply_patch", "arguments": {"patch": "*** Begin Patch\n*** Update File: src/app.py\n*** End Patch\n"}}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    cursor_file = cursor_root / "project-a" / "t1.jsonl"
    cursor_file.write_text(
        "\n".join(
            [
                json.dumps({"role": "user", "message": {"content": [{"type": "text", "text": "hello"}]}}),
                json.dumps({"role": "assistant", "message": {"content": [{"type": "text", "text": "done"}]}}),
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
                    },
                    {
                        "source_root_label": "cursor_projects",
                        "root_path": str(cursor_root),
                        "extension_plan": [{"extension": ".jsonl", "file_cap": 10, "parse_mode": "content_parser_candidate"}],
                    },
                ]
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    event_rows, session_rows, summary = parse_bounded_session_jsonl_metadata(parser_ticket_path=ticket)

    assert summary["parsed_event_rows"] == 5
    assert summary["parsed_sessions"] == 2
    normalized = [row["normalized_event_type"] for row in event_rows]
    assert "session_meta" in normalized
    assert "verification_command" in normalized
    assert "patch_applied" in normalized
    assert "user_message" in normalized
    patch_row = next(row for row in event_rows if row["normalized_event_type"] == "patch_applied")
    assert "src/app.py" in patch_row["file_path_refs"]
    codex_summary = next(row for row in session_rows if row["source_root_label"] == "codex_sessions")
    assert codex_summary["tool_name_counts"]["exec_command"] == 1
    assert codex_summary["tool_name_counts"]["apply_patch"] == 1


def test_parse_bounded_session_jsonl_metadata_honors_explicit_relative_paths(tmp_path: Path) -> None:
    codex_root = tmp_path / "codex"
    nested = codex_root / "2026" / "07"
    nested.mkdir(parents=True)
    selected_file = nested / "s-selected.jsonl"
    skipped_file = nested / "s-skipped.jsonl"
    selected_file.write_text(
        json.dumps({"timestamp": "t0", "type": "session_meta", "payload": {"cwd": "/repo/selected", "id": "s-selected"}}) + "\n",
        encoding="utf-8",
    )
    skipped_file.write_text(
        json.dumps({"timestamp": "t0", "type": "session_meta", "payload": {"cwd": "/repo/skipped", "id": "s-skipped"}}) + "\n",
        encoding="utf-8",
    )
    ticket = tmp_path / "ticket_explicit.json"
    ticket.write_text(
        json.dumps(
            {
                "parse_plan": [
                    {
                        "source_root_label": "codex_sessions",
                        "root_path": str(codex_root),
                        "explicit_relative_paths": ["2026/07/s-selected.jsonl"],
                        "require_explicit_paths": True,
                        "extension_plan": [{"extension": ".jsonl", "file_cap": 10, "parse_mode": "content_parser_candidate"}],
                    }
                ]
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    event_rows, session_rows, summary = parse_bounded_session_jsonl_metadata(parser_ticket_path=ticket)

    assert summary["parsed_event_rows"] == 1
    assert summary["parsed_sessions"] == 1
    assert event_rows[0]["session_id_hint"] == "s-selected"
    assert session_rows[0]["session_id_hint"] == "s-selected"

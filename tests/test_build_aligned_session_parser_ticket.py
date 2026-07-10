from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_aligned_session_parser_ticket import build_aligned_session_parser_ticket  # noqa: E402


def test_build_aligned_session_parser_ticket_prefers_recent_files(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    older = root / "older.jsonl"
    newer = root / "newer.jsonl"
    root.mkdir()
    older.write_text("{}", encoding="utf-8")
    newer.write_text("{}", encoding="utf-8")
    older.touch()
    newer.touch()

    ticket = build_aligned_session_parser_ticket(
        source_root_label="codex_sessions",
        root_path=root,
        max_files=1,
    )

    parse_plan = ticket["parse_plan"][0]
    assert parse_plan["require_explicit_paths"] is True
    assert parse_plan["explicit_relative_paths"] == ["newer.jsonl"]


def test_build_aligned_session_parser_ticket_can_require_session_ids(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    root.mkdir()
    (root / "s1.jsonl").write_text("{}", encoding="utf-8")
    (root / "s2.jsonl").write_text("{}", encoding="utf-8")
    traces = tmp_path / "traces.jsonl"
    traces.write_text(json.dumps({"session_id_hint": "s2"}) + "\n", encoding="utf-8")

    ticket = build_aligned_session_parser_ticket(
        source_root_label="codex_sessions",
        root_path=root,
        max_files=4,
        session_ids_jsonl_path=traces,
        require_session_ids=True,
    )

    assert ticket["selection_summary"]["selected_session_ids"] == ["s2"]


def test_build_aligned_session_parser_ticket_can_filter_by_repo_hint(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    root.mkdir()
    (root / "s1.jsonl").write_text("{}", encoding="utf-8")
    (root / "s2.jsonl").write_text("{}", encoding="utf-8")
    summaries = tmp_path / "session_summaries.jsonl"
    summaries.write_text(
        "\n".join(
            [
                json.dumps({"session_id_hint": "s1", "repo_hints": {"repo_a": 10}, "event_count": 10}),
                json.dumps({"session_id_hint": "s2", "repo_hints": {"repo_b": 12}, "event_count": 12}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    ticket = build_aligned_session_parser_ticket(
        source_root_label="codex_sessions",
        root_path=root,
        max_files=4,
        session_summaries_path=summaries,
        allowed_repo_hints={"repo_b"},
        require_repo_hint_match=True,
    )

    assert ticket["selection_summary"]["selected_session_ids"] == ["s2"]

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_session_parser_ticket import build_session_parser_ticket  # noqa: E402


def test_build_session_parser_ticket_prioritizes_codex_jsonl_first(tmp_path: Path) -> None:
    counts = tmp_path / "counts.json"
    counts.write_text(
        json.dumps(
            {
                "codex_sessions": {
                    "root_path": "/home/x/.codex/sessions",
                    "file_count": 500,
                    "total_bytes": 5_000_000_000,
                    "extension_counts": {".jsonl": 500},
                    "total_bytes_by_extension": {".jsonl": 5_000_000_000},
                },
                "cursor_projects": {
                    "root_path": "/home/x/.cursor/projects",
                    "file_count": 200,
                    "total_bytes": 50_000_000,
                    "extension_counts": {".jsonl": 40, ".txt": 100},
                    "total_bytes_by_extension": {".jsonl": 10_000_000, ".txt": 20_000_000},
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    parser_input = tmp_path / "parser_input.json"
    parser_input.write_text(
        json.dumps(
            {
                "candidate_roots_present": ["codex_sessions", "cursor_projects"],
                "metadata_only_inventory_complete": True,
                "raw_content_access_performed": False,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    ticket = build_session_parser_ticket(
        counts_by_root_path=counts,
        parser_input_path=parser_input,
        max_initial_files=128,
    )

    assert ticket["metadata_only_inventory_complete"] is True
    assert ticket["raw_content_access_performed"] is False
    assert ticket["root_priorities"][0]["source_root_label"] == "codex_sessions"
    assert ticket["parse_plan"][0]["source_root_label"] == "codex_sessions"
    assert ticket["parse_plan"][0]["extension_plan"][0]["extension"] == ".jsonl"
    assert ticket["guardrails"]["parse_content_now"] is False

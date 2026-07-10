from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from inventory_session_like_sources import inventory_session_like_sources, materialize_session_like_inventory  # noqa: E402


def test_inventory_session_like_sources_counts_files_without_content_reads(tmp_path: Path) -> None:
    codex_root = tmp_path / "codex"
    cursor_root = tmp_path / "cursor"
    (codex_root / "2026" / "07" / "08").mkdir(parents=True)
    (cursor_root / "chats").mkdir(parents=True)
    (codex_root / "2026" / "07" / "08" / "rollout.jsonl").write_text("ignored-content", encoding="utf-8")
    (cursor_root / "chats" / "chat1.json").write_text("ignored-content", encoding="utf-8")

    rows, counts_by_root, extension_counts, root_card, auxiliary = inventory_session_like_sources(
        root_specs=[("codex_sessions", codex_root), ("cursor_chats", cursor_root)],
    )

    assert len(rows) == 2
    assert counts_by_root["codex_sessions"]["file_count"] == 1
    assert counts_by_root["cursor_chats"]["file_count"] == 1
    assert extension_counts["extension_counts"][".jsonl"] == 1
    assert extension_counts["extension_counts"][".json"] == 1
    assert root_card["roots_present"] == 2
    assert auxiliary["no_content_read_proof"]["file_content_read_now"] is False
    assert all("relative_path_hash" in row and "source_root_label" in row for row in rows)


def test_materialize_session_like_inventory_writes_contract_outputs(tmp_path: Path) -> None:
    codex_root = tmp_path / "codex"
    (codex_root / "2026").mkdir(parents=True)
    (codex_root / "2026" / "a.jsonl").write_text("ignored-content", encoding="utf-8")
    out = tmp_path / "out"

    result = materialize_session_like_inventory(
        output_dir=out,
        root_specs=[("codex_sessions", codex_root), ("missing_cursor", tmp_path / "missing")],
    )

    expected = [
        "session_inventory_root_card.json",
        "session_inventory_counts_by_root.json",
        "session_inventory_extension_counts.json",
        "session_inventory_relative_path_hashes.jsonl",
        "no_content_read_proof.json",
        "next_session_parser_ticket_input.json",
    ]
    for name in expected:
        assert (out / name).exists(), name

    root_card = json.loads((out / "session_inventory_root_card.json").read_text(encoding="utf-8"))
    assert root_card["roots_present"] == 1
    assert result["next_parser_ticket_input"]["raw_content_access_performed"] is False

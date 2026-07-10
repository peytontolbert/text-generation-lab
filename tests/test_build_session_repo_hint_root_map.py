from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_session_repo_hint_root_map import build_session_repo_hint_root_map  # noqa: E402


def test_build_session_repo_hint_root_map_merges_observed_hints(tmp_path: Path) -> None:
    seeds = tmp_path / "seeds.jsonl"
    seeds.write_text(
        "\n".join(
            [
                json.dumps({"repo_hint": "agentkernel"}),
                json.dumps({"repo_hint": "custom_repo"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    payload = build_session_repo_hint_root_map(hints_path=seeds)
    hints = {row["repo_hint"] for row in payload["rows"]}
    assert "agentkernel" in hints
    assert "custom_repo" in hints
    mapped = {row["repo_hint"]: row["local_repo_root"] for row in payload["rows"]}
    assert mapped["agentkernel"] == "/data/agentkernel"

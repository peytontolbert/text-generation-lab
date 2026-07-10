from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from resolve_session_episode_seeds_to_local_roots import resolve_session_episode_seeds_to_local_roots  # noqa: E402


def test_resolve_session_episode_seeds_to_local_roots_matches_repo_hint_and_relative_paths(tmp_path: Path) -> None:
    repo_root = tmp_path / "bddy_website"
    (repo_root / "src").mkdir(parents=True)
    (repo_root / "src" / "main.js").write_text("x", encoding="utf-8")
    seeds = tmp_path / "session_seeds.jsonl"
    seeds.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "seed_id": "s1",
                        "repo_hint": "bddy_website",
                        "goal": "repair_or_edit",
                        "changes": [{"path": "src/main.js"}],
                        "metadata": {"original_changes": [{"path": "src/main.js"}]},
                    },
                    sort_keys=True,
                )
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    root_map = tmp_path / "root_map.json"
    root_map.write_text(
        json.dumps(
            {"rows": [{"repo_hint": "bddy_website", "local_repo_root": str(repo_root), "root_exists": True}]},
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    rows, summary = resolve_session_episode_seeds_to_local_roots(
        session_seed_candidates_path=seeds,
        root_map_path=root_map,
    )

    assert summary["resolved_local_root_count"] == 1
    assert summary["resolved_local_change_count"] == 1
    assert rows[0]["local_repo_root"] == str(repo_root)
    assert rows[0]["changes"] == [{"path": str(repo_root / "src" / "main.js")}]

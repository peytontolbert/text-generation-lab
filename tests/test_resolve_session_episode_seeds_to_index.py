from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from long_context_parquet import write_parquet_shard  # noqa: E402
from resolve_session_episode_seeds_to_index import resolve_session_episode_seeds_to_index  # noqa: E402


def test_resolve_session_episode_seeds_to_index_maps_repo_hint_and_absolute_paths(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        pytest.skip("pyarrow not installed")

    index_dir = tmp_path / "index"
    chunks_dir = index_dir / "chunks"
    chunks_dir.mkdir(parents=True)
    write_parquet_shard(
        chunks_dir / "chunks-000000.parquet",
        [
            {
                "source_id": "agentkernel",
                "source_type": "repo",
                "metadata_json": "{\"path\":\"agentkernel/src/app.py\"}",
            },
            {
                "source_id": "agentkernel",
                "source_type": "repo",
                "metadata_json": "{\"path\":\"agentkernel/tests/test_app.py\"}",
            },
        ],
    )
    seeds = tmp_path / "session_seeds.jsonl"
    seeds.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "seed_id": "s1",
                        "repo_hint": "agentkernel",
                        "goal": "repair_or_edit",
                        "changes": [{"path": "/data/agentkernel/src/app.py"}],
                    },
                    sort_keys=True,
                )
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows, summary = resolve_session_episode_seeds_to_index(
        session_seed_candidates_path=seeds,
        index_dir=index_dir,
    )

    assert summary["resolved_seed_count"] == 1
    assert rows[0]["repo_id"] == "agentkernel"
    assert rows[0]["changes"] == [{"path": "agentkernel/src/app.py"}]

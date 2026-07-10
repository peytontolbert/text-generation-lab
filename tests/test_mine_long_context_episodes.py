from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from long_context_parquet import write_parquet_shard  # noqa: E402
from mine_long_context_episodes import build_long_context_episodes  # noqa: E402


def test_build_long_context_episodes_mines_repo_local_transition_closure(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        pytest.skip("pyarrow not installed")

    index_dir = tmp_path / "index"
    chunks_dir = index_dir / "chunks"
    chunks_dir.mkdir(parents=True)
    write_parquet_shard(
        chunks_dir / "chunks-000000.parquet",
        [
            {
                "chunk_id": "c1",
                "source_type": "repo",
                "source_id": "repo_alpha",
                "doc_id": "src/engine.py",
                "chunk_index": 0,
                "token_count": 40,
                "text": "from src.helpers import compute_total\n\ndef run_order(x):\n    return compute_total(x)\n",
                "metadata_json": "{\"path\":\"src/engine.py\"}",
            },
            {
                "chunk_id": "c2",
                "source_type": "repo",
                "source_id": "repo_alpha",
                "doc_id": "src/helpers.py",
                "chunk_index": 0,
                "token_count": 35,
                "text": "def compute_total(x):\n    return x + 1\n",
                "metadata_json": "{\"path\":\"src/helpers.py\"}",
            },
            {
                "chunk_id": "c3",
                "source_type": "repo",
                "source_id": "repo_alpha",
                "doc_id": "tests/test_engine.py",
                "chunk_index": 0,
                "token_count": 30,
                "text": "from src.engine import run_order\n\ndef test_run_order():\n    assert run_order(1) == 2\n",
                "metadata_json": "{\"path\":\"tests/test_engine.py\"}",
            },
            {
                "chunk_id": "c4",
                "source_type": "repo",
                "source_id": "repo_beta",
                "doc_id": "lib/engine.py",
                "chunk_index": 0,
                "token_count": 45,
                "text": "def run_order(items):\n    return compute_total(items)\n",
                "metadata_json": "{\"path\":\"lib/engine.py\"}",
            },
            {
                "chunk_id": "p1",
                "source_type": "paper",
                "source_id": "paper_attention_ops",
                "doc_id": "methods",
                "chunk_index": 0,
                "token_count": 50,
                "text": "The run_order procedure preserves compute_total semantics when aggregating sequence items in the execution engine.",
                "metadata_json": "{\"path\":\"paper/methods.txt\"}",
            },
        ],
    )

    seeds = tmp_path / "seeds.jsonl"
    seeds.write_text(
        "\n".join(
            [
                "{\"seed_id\":\"s1\",\"seed_type\":\"commit\",\"repo_id\":\"repo_alpha\",\"goal\":\"Fix run_order behavior\",\"changes\":[{\"path\":\"src/engine.py\",\"symbol\":\"run_order\"}],\"target\":{\"expected_patch_summary\":\"Update run_order to preserve compute_total semantics\",\"expected_outcome\":\"tests pass\"}}"
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    episodes, summary = build_long_context_episodes(index_dir=index_dir, seeds_path=seeds)

    assert summary["episode_count"] == 1
    episode = episodes[0]
    assert episode["seed_type"] == "commit"
    assert episode["seed_paths"] == ["src/engine.py"]
    assert "tests/test_engine.py" in episode["selected_tests"]
    paths_by_role = {(row["path"], row["role"]) for row in episode["context_rows"]}
    assert ("src/engine.py", "seed_change") in paths_by_role
    assert ("src/helpers.py", "repo_graph_neighbor") in paths_by_role
    assert ("tests/test_engine.py", "verification_constraint") in paths_by_role
    assert ("lib/engine.py", "cross_repo_analogue") in paths_by_role
    assert ("paper/methods.txt", "algorithm_grounding") in paths_by_role
    assert episode["transition_record"]["retrieval_context_refs"]


def test_build_long_context_episodes_skips_unknown_repo_or_path(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        pytest.skip("pyarrow not installed")

    index_dir = tmp_path / "index"
    chunks_dir = index_dir / "chunks"
    chunks_dir.mkdir(parents=True)
    write_parquet_shard(
        chunks_dir / "chunks-000000.parquet",
        [
            {
                "chunk_id": "c1",
                "source_type": "repo",
                "source_id": "repo_alpha",
                "doc_id": "src/engine.py",
                "chunk_index": 0,
                "token_count": 10,
                "text": "def run_order(x):\n    return x\n",
                "metadata_json": "{\"path\":\"src/engine.py\"}",
            }
        ],
    )
    seeds = tmp_path / "seeds.jsonl"
    seeds.write_text(
        "\n".join(
            [
                "{\"seed_id\":\"bad_repo\",\"repo_id\":\"missing_repo\",\"changes\":[{\"path\":\"src/engine.py\"}]}",
                "{\"seed_id\":\"bad_path\",\"repo_id\":\"repo_alpha\",\"changes\":[{\"path\":\"src/missing.py\"}]}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    episodes, summary = build_long_context_episodes(index_dir=index_dir, seeds_path=seeds)

    assert episodes == []
    assert summary["episode_count"] == 0

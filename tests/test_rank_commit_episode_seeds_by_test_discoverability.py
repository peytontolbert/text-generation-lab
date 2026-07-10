from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from long_context_parquet import write_parquet_shard  # noqa: E402
from rank_commit_episode_seeds_by_test_discoverability import (  # noqa: E402
    rank_commit_episode_seeds_by_test_discoverability,
)


def test_rank_commit_episode_seeds_by_test_discoverability_prioritizes_targeted_tests(tmp_path: Path) -> None:
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
                "doc_id": "repo_alpha/src/engine.py",
                "chunk_index": 0,
                "token_count": 40,
                "text": "from src.helpers import compute_total\n\ndef run_order(x):\n    return compute_total(x)\n",
                "metadata_json": '{"path":"repo_alpha/src/engine.py"}',
            },
            {
                "chunk_id": "c2",
                "source_type": "repo",
                "source_id": "repo_alpha",
                "doc_id": "repo_alpha/tests/test_engine.py",
                "chunk_index": 0,
                "token_count": 30,
                "text": "from src.engine import run_order\n\ndef test_run_order():\n    assert run_order(1) == 2\n",
                "metadata_json": '{"path":"repo_alpha/tests/test_engine.py"}',
            },
            {
                "chunk_id": "c3",
                "source_type": "repo",
                "source_id": "repo_beta",
                "doc_id": "repo_beta/src/reader.py",
                "chunk_index": 0,
                "token_count": 25,
                "text": "def load_data(x):\n    return x\n",
                "metadata_json": '{"path":"repo_beta/src/reader.py"}',
            },
        ],
    )
    seeds = tmp_path / "seeds.jsonl"
    seeds.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "seed_id": "s1",
                        "seed_type": "external_repo_commit",
                        "repo_id": "repo_alpha",
                        "goal": "Fix run_order behavior",
                        "changes": [{"path": "repo_alpha/src/engine.py", "symbol": "run_order"}],
                    }
                ),
                json.dumps(
                    {
                        "seed_id": "s2",
                        "seed_type": "external_repo_commit",
                        "repo_id": "repo_beta",
                        "goal": "Touch loader",
                        "changes": [{"path": "repo_beta/src/reader.py", "symbol": "load_data"}],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows, summary = rank_commit_episode_seeds_by_test_discoverability(index_dir=index_dir, seeds_path=seeds)

    assert summary["ranked_seed_count"] == 2
    assert rows[0]["seed_id"] == "s1"
    assert rows[0]["rank_metadata"]["discoverability_route"] == "PASS_TARGETED_TEST_SELECTION"
    assert rows[0]["rank_metadata"]["selected_tests"] == ["tests/test_engine.py"]
    assert rows[1]["rank_metadata"]["discoverability_route"] == "NEEDS_BROAD_TEST_DISCOVERY"
    assert rows[0]["rank_metadata"]["discoverability_score"] > rows[1]["rank_metadata"]["discoverability_score"]


def test_rank_commit_episode_seeds_by_test_discoverability_resolves_unique_suffix_paths(tmp_path: Path) -> None:
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
                "doc_id": "repo_alpha/pkg/src/engine.py",
                "chunk_index": 0,
                "token_count": 40,
                "text": "def run_order(x):\n    return x + 1\n",
                "metadata_json": '{\"path\":\"pkg/src/engine.py\"}',
            },
            {
                "chunk_id": "c2",
                "source_type": "repo",
                "source_id": "repo_alpha",
                "doc_id": "repo_alpha/tests/test_engine.py",
                "chunk_index": 0,
                "token_count": 30,
                "text": "from pkg.src.engine import run_order\n\ndef test_run_order():\n    assert run_order(1) == 2\n",
                "metadata_json": '{\"path\":\"tests/test_engine.py\"}',
            },
        ],
    )
    seeds = tmp_path / "seeds.jsonl"
    seeds.write_text(
        json.dumps(
            {
                "seed_id": "s1",
                "seed_type": "external_repo_commit",
                "repo_id": "repo_alpha",
                "goal": "Fix run_order behavior",
                "changes": [{"path": "repo_alpha/src/engine.py", "symbol": "run_order"}],
            }
        ) + "\n",
        encoding="utf-8",
    )

    rows, summary = rank_commit_episode_seeds_by_test_discoverability(index_dir=index_dir, seeds_path=seeds)

    assert summary["ranked_seed_count"] == 1
    assert rows[0]["rank_metadata"]["discoverability_route"] == "PASS_TARGETED_TEST_SELECTION"
    assert rows[0]["rank_metadata"]["selected_tests"] == ["tests/test_engine.py"]


def test_rank_commit_episode_seeds_by_test_discoverability_records_broad_grounded_signal(tmp_path: Path) -> None:
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
                "source_id": "repo_gamma",
                "doc_id": "repo_gamma/src/trainer.py",
                "chunk_index": 0,
                "token_count": 40,
                "text": "def train_epoch(model):\n    return model.step()\n",
                "metadata_json": '{"path":"src/trainer.py"}',
            },
            {
                "chunk_id": "c2",
                "source_type": "repo",
                "source_id": "repo_gamma",
                "doc_id": "repo_gamma/full_eval.py",
                "chunk_index": 0,
                "token_count": 45,
                "text": "from src.trainer import train_epoch\n\n\ndef run_full_eval(model):\n    return train_epoch(model)\n",
                "metadata_json": '{"path":"full_eval.py"}',
            },
        ],
    )
    seeds = tmp_path / "seeds.jsonl"
    seeds.write_text(
        json.dumps(
            {
                "seed_id": "s1",
                "seed_type": "external_repo_commit",
                "repo_id": "repo_gamma",
                "goal": "Repair training evaluation behavior for train_epoch",
                "changes": [{"path": "src/trainer.py"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rows, summary = rank_commit_episode_seeds_by_test_discoverability(index_dir=index_dir, seeds_path=seeds)

    assert summary["ranked_seed_count"] == 1
    meta = rows[0]["rank_metadata"]
    assert meta["discoverability_route"] == "NEEDS_BROAD_TEST_DISCOVERY"
    assert meta["broad_verification_candidate_count"] == 1
    assert meta["top_broad_verification_score"] > 0.0
    assert meta["broad_verification_candidates_preview"][0]["test_path"] == "full_eval.py"


def test_rank_commit_episode_seeds_by_test_discoverability_fails_when_index_has_no_matching_repo(tmp_path: Path) -> None:
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
                "doc_id": "repo_alpha/src/engine.py",
                "chunk_index": 0,
                "token_count": 40,
                "text": "def run_order(x):\n    return x + 1\n",
                "metadata_json": '{"path":"src/engine.py"}',
            },
        ],
    )
    seeds = tmp_path / "seeds.jsonl"
    seeds.write_text(
        json.dumps(
            {
                "seed_id": "s1",
                "seed_type": "external_repo_commit",
                "repo_id": "repo_missing",
                "goal": "Fix missing repo mapping",
                "changes": [{"path": "src/engine.py"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="all_seeds_missing_repo_analysis"):
        rank_commit_episode_seeds_by_test_discoverability(index_dir=index_dir, seeds_path=seeds)


def test_rank_commit_episode_seeds_by_test_discoverability_supports_explicit_local_repo_mode(tmp_path: Path) -> None:
    repo_root = tmp_path / "repos"
    repo = repo_root / "repo_alpha"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "src" / "engine.py").write_text("from src.helpers import compute_total\n\ndef run_order(x):\n    return compute_total(x)\n", encoding="utf-8")
    (repo / "src" / "helpers.py").write_text("def compute_total(x):\n    return x + 1\n", encoding="utf-8")
    (repo / "tests" / "test_engine.py").write_text("from src.engine import run_order\n\ndef test_run_order():\n    assert run_order(1) == 2\n", encoding="utf-8")

    seeds = tmp_path / "seeds_local.jsonl"
    seeds.write_text(
        json.dumps(
            {
                "seed_id": "s1",
                "seed_type": "external_repo_commit",
                "repo_id": "repo_alpha",
                "goal": "Fix run_order behavior",
                "changes": [{"path": "repo_alpha/src/engine.py", "symbol": "run_order"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rows, summary = rank_commit_episode_seeds_by_test_discoverability(
        repositories_root=repo_root,
        seeds_path=seeds,
        root_file_limit=20,
        neighbor_dir_file_limit=20,
        max_total_candidates=50,
    )

    assert summary["source_mode"] == "repositories_root"
    assert summary["ranked_seed_count"] == 1
    assert rows[0]["rank_metadata"]["discoverability_route"] == "PASS_TARGETED_TEST_SELECTION"
    assert rows[0]["rank_metadata"]["selected_tests"] == ["tests/test_engine.py"]


def test_rank_commit_episode_seeds_by_test_discoverability_fails_when_local_repo_root_missing(tmp_path: Path) -> None:
    repo_root = tmp_path / "repos"
    repo_root.mkdir(parents=True)
    seeds = tmp_path / "seeds_missing_local.jsonl"
    seeds.write_text(
        json.dumps(
            {
                "seed_id": "s1",
                "seed_type": "external_repo_commit",
                "repo_id": "repo_missing",
                "goal": "Fix missing repo mapping",
                "changes": [{"path": "repo_missing/src/engine.py"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="all_seeds_missing_local_repo_root"):
        rank_commit_episode_seeds_by_test_discoverability(repositories_root=repo_root, seeds_path=seeds)

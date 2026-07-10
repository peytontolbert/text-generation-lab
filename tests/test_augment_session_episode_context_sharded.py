from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import augment_session_episode_context_sharded as module  # noqa: E402


def test_augment_session_episode_context_sharded_merges_shards(tmp_path: Path, monkeypatch) -> None:
    episodes = tmp_path / "episodes.jsonl"
    rows = [
        {"episode_id": "e1", "context_token_count": 10},
        {"episode_id": "e2", "context_token_count": 20},
        {"episode_id": "e3", "context_token_count": 30},
    ]
    episodes.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def fake_augment_session_episode_context(**kwargs):
        input_rows = [json.loads(line) for line in Path(kwargs["episodes_path"]).read_text().splitlines() if line.strip()]
        out_rows = []
        for row in input_rows:
            out_rows.append(
                {
                    **row,
                    "context_token_count": int(row.get("context_token_count") or 0) + 5,
                }
            )
        return out_rows, {
            "augmented_role_counts": {"cross_repo_analogue": len(out_rows)},
            "augmented_source_type_counts": {"repo": len(out_rows)},
        }

    monkeypatch.setattr(module, "augment_session_episode_context", fake_augment_session_episode_context)

    merged_rows, summary = module.augment_session_episode_context_sharded(
        episodes_path=episodes,
        index_dir=tmp_path / "index",
        output_dir=tmp_path / "out",
        shard_size=2,
    )

    assert len(merged_rows) == 3
    assert summary["shard_count"] == 2
    assert summary["augmented_episode_count"] == 3
    assert summary["avg_uplift_tokens"] == 5.0
    assert summary["augmented_role_counts"] == {"cross_repo_analogue": 3}
    assert summary["augmented_source_type_counts"] == {"repo": 3}
    assert (tmp_path / "out" / "shards" / "augmented_0000.jsonl").exists()
    assert (tmp_path / "out" / "shards" / "augmented_0001.jsonl").exists()


def test_augment_session_episode_context_sharded_reuses_completed_shards(tmp_path: Path, monkeypatch) -> None:
    episodes = tmp_path / "episodes.jsonl"
    rows = [
        {"episode_id": "e1", "context_token_count": 10},
        {"episode_id": "e2", "context_token_count": 20},
    ]
    episodes.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    calls = {"count": 0}

    def fake_augment_session_episode_context(**kwargs):
        calls["count"] += 1
        input_rows = [json.loads(line) for line in Path(kwargs["episodes_path"]).read_text().splitlines() if line.strip()]
        out_rows = [{**row, "context_token_count": int(row.get("context_token_count") or 0) + 5} for row in input_rows]
        return out_rows, {
            "augmented_role_counts": {"cross_repo_analogue": len(out_rows)},
            "augmented_source_type_counts": {"repo": len(out_rows)},
        }

    monkeypatch.setattr(module, "augment_session_episode_context", fake_augment_session_episode_context)

    module.augment_session_episode_context_sharded(
        episodes_path=episodes,
        index_dir=tmp_path / "index",
        output_dir=tmp_path / "out",
        shard_size=1,
    )
    module.augment_session_episode_context_sharded(
        episodes_path=episodes,
        index_dir=tmp_path / "index",
        output_dir=tmp_path / "out",
        shard_size=1,
    )

    assert calls["count"] == 2

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from compile_long_context_episode_rows import compile_long_context_episode_rows  # noqa: E402


def test_compile_long_context_episode_rows_emits_four_training_views(tmp_path: Path) -> None:
    episodes = tmp_path / "episodes.jsonl"
    episodes.write_text(
        "\n".join(
            [
                '{"episode_id":"e1","seed_type":"commit","repo_id":"repo_alpha","goal":"Fix run_order behavior","seed_paths":["src/engine.py"],"seed_symbols":["run_order","compute_total"],"selected_tests":["tests/test_engine.py"],"context_token_count":120,"context_role_counts":{"seed_change":1,"verification_constraint":1},"context_rows":[{"chunk_id":"c1","path":"src/engine.py","role":"seed_change","text":"def run_order(x): return compute_total(x)"},{"chunk_id":"c2","path":"tests/test_engine.py","role":"verification_constraint","text":"assert run_order(1) == 2"}],"target":{"expected_patch_summary":"Update run_order to preserve compute_total semantics","expected_outcome":"tests pass","state_after":{"tests":"pass"}}}'
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    buckets, summary = compile_long_context_episode_rows(
        episodes_path=episodes,
        max_positive_chunks=4,
    )

    assert summary["episode_rows"] == 1
    assert summary["full_context_rows"] == 1
    assert summary["retrieval_rows"] == 1
    assert summary["action_rows"] == 1
    assert summary["memory_rows"] == 1
    assert buckets["full_context_rows"][0]["task_type"] == "full_context_transition_prediction"
    assert buckets["retrieval_rows"][0]["positive_chunk_ids"] == ["c1", "c2"]
    assert buckets["action_rows"][0]["target_text"] == "Update run_order to preserve compute_total semantics"
    assert buckets["memory_rows"][0]["task_type"] == "state_summary_compression"

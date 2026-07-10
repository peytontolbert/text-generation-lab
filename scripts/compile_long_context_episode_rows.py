from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from long_context_common import write_json
from materialize_trainer_setup import read_jsonl


POSITIVE_ROLES = {
    "seed_change",
    "repo_graph_neighbor",
    "verification_constraint",
    "cross_repo_analogue",
    "algorithm_grounding",
}


def _full_context_prompt(row: dict[str, Any]) -> str:
    goal = str(row.get("goal") or "")
    return "\n".join(
        [
            "You are given a long transition episode assembled from repository state, retrieved analogues, and grounding evidence.",
            f"Goal: {goal}",
            "Produce the best next transition summary using only the supplied evidence.",
        ]
    )


def _target_text(row: dict[str, Any]) -> str:
    target = dict(row.get("target") or {})
    return json.dumps(
        {
            "expected_patch_summary": str(target.get("expected_patch_summary") or ""),
            "expected_outcome": str(target.get("expected_outcome") or ""),
            "state_after": target.get("state_after") if isinstance(target.get("state_after"), dict) else {},
        },
        sort_keys=True,
    )


def _retrieval_query_text(row: dict[str, Any]) -> str:
    symbols = ", ".join(str(symbol) for symbol in list(row.get("seed_symbols") or [])[:8])
    goal = str(row.get("goal") or "")
    return f"Retrieve the most useful evidence for goal `{goal}` using symbols [{symbols}]."


def _positive_chunk_ids(context_rows: list[dict[str, Any]], *, max_positive_chunks: int) -> list[str]:
    selected = [
        str(context_row.get("chunk_id") or "")
        for context_row in context_rows
        if str(context_row.get("role") or "") in POSITIVE_ROLES
    ]
    if not selected:
        selected = [str(context_row.get("chunk_id") or "") for context_row in context_rows[: max(1, min(3, max_positive_chunks))]]
    return selected[:max_positive_chunks]


def _memory_target(row: dict[str, Any], context_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "episode_id": str(row.get("episode_id") or ""),
        "repo_id": str(row.get("repo_id") or ""),
        "goal": str(row.get("goal") or ""),
        "seed_paths": list(row.get("seed_paths") or []),
        "seed_symbols": list(row.get("seed_symbols") or []),
        "selected_tests": list(row.get("selected_tests") or []),
        "context_roles": sorted({str(context_row.get("role") or "") for context_row in context_rows}),
    }


def compile_long_context_episode_rows(
    *,
    episodes_path: Path,
    max_positive_chunks: int = 8,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    episodes = read_jsonl(episodes_path)
    full_context_rows: list[dict[str, Any]] = []
    retrieval_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    memory_rows: list[dict[str, Any]] = []
    seed_type_counts: Counter[str] = Counter()

    for row in episodes:
        episode_id = str(row.get("episode_id") or "")
        seed_type = str(row.get("seed_type") or "transition_seed")
        context_rows = list(row.get("context_rows") or [])
        seed_type_counts[seed_type] += 1

        full_context_rows.append(
            {
                "row_id": f"full::{episode_id}",
                "episode_id": episode_id,
                "task_type": "full_context_transition_prediction",
                "seed_type": seed_type,
                "prompt_text": _full_context_prompt(row),
                "context_rows": context_rows,
                "target_text": _target_text(row),
                "metadata": {
                    "repo_id": str(row.get("repo_id") or ""),
                    "context_token_count": int(row.get("context_token_count") or 0),
                    "context_role_counts": dict(row.get("context_role_counts") or {}),
                },
            }
        )

        retrieval_rows.append(
            {
                "row_id": f"retrieval::{episode_id}",
                "episode_id": episode_id,
                "task_type": "retrieval_supervision",
                "seed_type": seed_type,
                "query_text": _retrieval_query_text(row),
                "positive_chunk_ids": _positive_chunk_ids(context_rows, max_positive_chunks=max_positive_chunks),
                "target_text": _target_text(row),
                "metadata": {
                    "repo_id": str(row.get("repo_id") or ""),
                    "goal": str(row.get("goal") or ""),
                },
            }
        )

        action_rows.append(
            {
                "row_id": f"action::{episode_id}",
                "episode_id": episode_id,
                "task_type": "next_action_prediction",
                "seed_type": seed_type,
                "input_text": f"Given the episode goal `{str(row.get('goal') or '')}`, predict the best next action summary.",
                "target_text": str((row.get("target") or {}).get("expected_patch_summary") or (row.get("target") or {}).get("expected_outcome") or ""),
                "metadata": {
                    "repo_id": str(row.get("repo_id") or ""),
                    "seed_paths": list(row.get("seed_paths") or []),
                },
            }
        )

        memory_rows.append(
            {
                "row_id": f"memory::{episode_id}",
                "episode_id": episode_id,
                "task_type": "state_summary_compression",
                "seed_type": seed_type,
                "input_text": f"Summarize the persistent working memory for episode {episode_id}.",
                "target_text": json.dumps(_memory_target(row, context_rows), sort_keys=True),
                "metadata": {
                    "repo_id": str(row.get("repo_id") or ""),
                    "context_token_count": int(row.get("context_token_count") or 0),
                },
            }
        )

    buckets = {
        "full_context_rows": full_context_rows,
        "retrieval_rows": retrieval_rows,
        "action_rows": action_rows,
        "memory_rows": memory_rows,
    }
    summary = {
        "episode_rows": len(episodes),
        "full_context_rows": len(full_context_rows),
        "retrieval_rows": len(retrieval_rows),
        "action_rows": len(action_rows),
        "memory_rows": len(memory_rows),
        "seed_type_counts": dict(sorted(seed_type_counts.items())),
        "max_positive_chunks": int(max_positive_chunks),
        "full_context_format": "structured_prompt_plus_context_rows",
    }
    return buckets, summary


def stream_compile_long_context_episode_rows(
    *,
    episodes_path: Path,
    output_dir: Path,
    max_positive_chunks: int = 8,
) -> dict[str, Any]:
    buckets, summary = compile_long_context_episode_rows(
        episodes_path=episodes_path,
        max_positive_chunks=max_positive_chunks,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    for bucket_name, rows in buckets.items():
        path = output_dir / f"{bucket_name}.jsonl"
        if path.exists():
            path.unlink()
        with path.open("a", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
    write_json(output_dir / "compile_card.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile long-context episode rows into model-consumable training shards.")
    parser.add_argument("--episodes", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-positive-chunks", type=int, default=8)
    args = parser.parse_args()
    stream_compile_long_context_episode_rows(
        episodes_path=args.episodes,
        output_dir=args.output_dir,
        max_positive_chunks=args.max_positive_chunks,
    )


if __name__ == "__main__":
    main()

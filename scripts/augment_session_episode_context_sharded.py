from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from augment_session_episode_context import augment_session_episode_context
from long_context_common import write_json, write_jsonl


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def augment_session_episode_context_sharded(
    *,
    episodes_path: Path,
    index_dir: Path,
    output_dir: Path,
    shard_size: int,
    external_token_budget: int = 250_000,
    max_query_terms: int = 24,
    max_term_docfreq: int = 2500,
    max_augmented_chunks: int = 320,
    max_chunks_per_source_type: int = 128,
    max_chunks_per_source_id: int = 16,
    max_chunks_per_path: int = 4,
    neighbor_window: int = 2,
    max_neighbor_chunks_per_anchor: int = 4,
    min_external_chunks: int = 12,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    episodes = _read_jsonl(episodes_path)
    if not episodes:
        raise ValueError("no_episode_rows")
    if shard_size <= 0:
        raise ValueError("shard_size_must_be_positive")

    output_dir.mkdir(parents=True, exist_ok=True)
    shard_dir = output_dir / "shards"
    shard_dir.mkdir(parents=True, exist_ok=True)

    merged_rows: list[dict[str, Any]] = []
    uplift_tokens: list[int] = []
    augmented_role_counts: Counter[str] = Counter()
    augmented_source_type_counts: Counter[str] = Counter()
    shard_summaries: list[dict[str, Any]] = []

    for shard_index, start in enumerate(range(0, len(episodes), shard_size)):
        stop = min(start + shard_size, len(episodes))
        shard_rows = episodes[start:stop]
        shard_input = shard_dir / f"episodes_{shard_index:04d}.jsonl"
        shard_output = shard_dir / f"augmented_{shard_index:04d}.jsonl"
        shard_summary_path = shard_dir / f"augmented_{shard_index:04d}_summary.json"
        write_jsonl(shard_input, shard_rows)
        if shard_output.exists() and shard_summary_path.exists():
            rows = _read_jsonl(shard_output)
            summary = json.loads(shard_summary_path.read_text(encoding="utf-8"))
        else:
            rows, summary = augment_session_episode_context(
                episodes_path=shard_input,
                index_dir=index_dir,
                external_token_budget=external_token_budget,
                max_query_terms=max_query_terms,
                max_term_docfreq=max_term_docfreq,
                max_augmented_chunks=max_augmented_chunks,
                max_chunks_per_source_type=max_chunks_per_source_type,
                max_chunks_per_source_id=max_chunks_per_source_id,
                max_chunks_per_path=max_chunks_per_path,
                neighbor_window=neighbor_window,
                max_neighbor_chunks_per_anchor=max_neighbor_chunks_per_anchor,
                min_external_chunks=min_external_chunks,
            )
            if len(rows) != len(shard_rows):
                raise ValueError(f"shard_row_count_mismatch:{shard_index}:{len(rows)}!={len(shard_rows)}")
            write_jsonl(shard_output, rows)
            write_json(shard_summary_path, summary)
        merged_rows.extend(rows)
        for row, source_row in zip(rows, shard_rows):
            uplift = int(row.get("context_token_count") or 0) - int(source_row.get("context_token_count") or 0)
            if uplift <= 0:
                raise ValueError(f"non_positive_shard_uplift:{shard_index}:{row.get('episode_id')}:{uplift}")
            uplift_tokens.append(uplift)
        for key, value in dict(summary.get("augmented_role_counts") or {}).items():
            augmented_role_counts[str(key)] += int(value)
        for key, value in dict(summary.get("augmented_source_type_counts") or {}).items():
            augmented_source_type_counts[str(key)] += int(value)
        shard_summaries.append(
            {
                "shard_index": shard_index,
                "start": start,
                "stop": stop,
                "episode_count": len(shard_rows),
                "summary_path": str(shard_summary_path),
            }
        )

    merged_summary = {
        "episode_count": len(episodes),
        "augmented_episode_count": len(merged_rows),
        "shard_count": len(shard_summaries),
        "shard_size": int(shard_size),
        "external_token_budget": int(external_token_budget),
        "neighbor_window": int(neighbor_window),
        "max_neighbor_chunks_per_anchor": int(max_neighbor_chunks_per_anchor),
        "max_chunks_per_path": int(max_chunks_per_path),
        "avg_uplift_tokens": (sum(uplift_tokens) / len(uplift_tokens)) if uplift_tokens else 0.0,
        "max_uplift_tokens": max(uplift_tokens) if uplift_tokens else 0,
        "min_uplift_tokens": min(uplift_tokens) if uplift_tokens else 0,
        "augmented_role_counts": dict(sorted(augmented_role_counts.items())),
        "augmented_source_type_counts": dict(sorted(augmented_source_type_counts.items())),
        "shards": shard_summaries,
    }
    return merged_rows, merged_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run strict long-context augmentation in bounded shards and merge the results.")
    parser.add_argument("--episodes", type=Path, required=True)
    parser.add_argument("--index-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--shard-size", type=int, default=8)
    parser.add_argument("--external-token-budget", type=int, default=250000)
    parser.add_argument("--max-query-terms", type=int, default=24)
    parser.add_argument("--max-term-docfreq", type=int, default=2500)
    parser.add_argument("--max-augmented-chunks", type=int, default=320)
    parser.add_argument("--max-chunks-per-source-type", type=int, default=128)
    parser.add_argument("--max-chunks-per-source-id", type=int, default=16)
    parser.add_argument("--max-chunks-per-path", type=int, default=4)
    parser.add_argument("--neighbor-window", type=int, default=2)
    parser.add_argument("--max-neighbor-chunks-per-anchor", type=int, default=4)
    parser.add_argument("--min-external-chunks", type=int, default=12)
    args = parser.parse_args()
    rows, summary = augment_session_episode_context_sharded(
        episodes_path=args.episodes,
        index_dir=args.index_dir,
        output_dir=args.output_dir,
        shard_size=args.shard_size,
        external_token_budget=args.external_token_budget,
        max_query_terms=args.max_query_terms,
        max_term_docfreq=args.max_term_docfreq,
        max_augmented_chunks=args.max_augmented_chunks,
        max_chunks_per_source_type=args.max_chunks_per_source_type,
        max_chunks_per_source_id=args.max_chunks_per_source_id,
        max_chunks_per_path=args.max_chunks_per_path,
        neighbor_window=args.neighbor_window,
        max_neighbor_chunks_per_anchor=args.max_neighbor_chunks_per_anchor,
        min_external_chunks=args.min_external_chunks,
    )
    write_jsonl(args.output_dir / "augmented_session_episodes.jsonl", rows)
    write_json(args.output_dir / "augmented_session_episodes_summary.json", summary)


if __name__ == "__main__":
    main()

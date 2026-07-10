from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from long_context_common import read_jsonl, write_json, write_jsonl
from rank_commit_episode_seeds_by_test_discoverability import rank_commit_episode_seeds_by_test_discoverability


def rank_commit_episode_seeds_by_test_discoverability_sharded(
    *,
    seeds_path: Path,
    output_dir: Path,
    shard_size: int,
    index_dir: Path | None = None,
    repositories_root: Path | None = None,
    max_selected_tests: int = 8,
    root_file_limit: int = 400,
    neighbor_dir_file_limit: int = 250,
    max_total_candidates: int = 1600,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seeds = read_jsonl(seeds_path)
    if not seeds:
        raise ValueError("no_seed_rows")
    if shard_size <= 0:
        raise ValueError("shard_size_must_be_positive")

    output_dir.mkdir(parents=True, exist_ok=True)
    shard_dir = output_dir / "shards"
    shard_dir.mkdir(parents=True, exist_ok=True)

    merged_rows: list[dict[str, Any]] = []
    route_counts: Counter[str] = Counter()
    shard_summaries: list[dict[str, Any]] = []
    discoverability_scores: list[float] = []
    source_mode: str | None = None

    for shard_index, start in enumerate(range(0, len(seeds), shard_size)):
        stop = min(start + shard_size, len(seeds))
        shard_rows = seeds[start:stop]
        shard_input = shard_dir / f"seeds_{shard_index:04d}.jsonl"
        shard_output = shard_dir / f"ranked_{shard_index:04d}.jsonl"
        shard_summary_path = shard_dir / f"ranked_{shard_index:04d}_summary.json"
        write_jsonl(shard_input, shard_rows)
        if shard_output.exists() and shard_summary_path.exists():
            rows = read_jsonl(shard_output)
            summary = json.loads(shard_summary_path.read_text(encoding="utf-8"))
        else:
            rows, summary = rank_commit_episode_seeds_by_test_discoverability(
                seeds_path=shard_input,
                index_dir=index_dir,
                repositories_root=repositories_root,
                max_selected_tests=max_selected_tests,
                root_file_limit=root_file_limit,
                neighbor_dir_file_limit=neighbor_dir_file_limit,
                max_total_candidates=max_total_candidates,
            )
            write_jsonl(shard_output, rows)
            write_json(shard_summary_path, summary)
        merged_rows.extend(rows)
        for key, value in dict(summary.get("route_counts") or {}).items():
            route_counts[str(key)] += int(value)
        for row in rows:
            discoverability_scores.append(float((row.get("rank_metadata") or {}).get("discoverability_score") or 0.0))
        if source_mode is None:
            source_mode = str(summary.get("source_mode") or "") or None
        shard_summaries.append(
            {
                "shard_index": shard_index,
                "start": start,
                "stop": stop,
                "seed_count": len(shard_rows),
                "ranked_seed_count": len(rows),
                "summary_path": str(shard_summary_path),
            }
        )

    merged_rows.sort(
        key=lambda row: (
            -float((row.get("rank_metadata") or {}).get("discoverability_score") or 0.0),
            -int((row.get("rank_metadata") or {}).get("selected_test_count") or 0),
            str(row.get("repo_id") or ""),
            str(row.get("seed_id") or ""),
        )
    )
    merged_summary = {
        "seed_count": len(seeds),
        "ranked_seed_count": len(merged_rows),
        "shard_count": len(shard_summaries),
        "shard_size": int(shard_size),
        "route_counts": dict(sorted(route_counts.items())),
        "avg_discoverability_score": (sum(discoverability_scores) / len(discoverability_scores)) if discoverability_scores else 0.0,
        "source_mode": source_mode,
        "shards": shard_summaries,
    }
    return merged_rows, merged_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run commit-seed discoverability ranking in bounded shards and merge the results.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--index-dir", type=Path)
    source_group.add_argument("--repositories-root", type=Path)
    parser.add_argument("--seeds", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--shard-size", type=int, default=64)
    parser.add_argument("--max-selected-tests", type=int, default=8)
    parser.add_argument("--root-file-limit", type=int, default=400)
    parser.add_argument("--neighbor-dir-file-limit", type=int, default=250)
    parser.add_argument("--max-total-candidates", type=int, default=1600)
    args = parser.parse_args()
    rows, summary = rank_commit_episode_seeds_by_test_discoverability_sharded(
        seeds_path=args.seeds,
        output_dir=args.output_dir,
        shard_size=args.shard_size,
        index_dir=args.index_dir,
        repositories_root=args.repositories_root,
        max_selected_tests=args.max_selected_tests,
        root_file_limit=args.root_file_limit,
        neighbor_dir_file_limit=args.neighbor_dir_file_limit,
        max_total_candidates=args.max_total_candidates,
    )
    write_jsonl(args.output_dir / "ranked_commit_episode_seeds.jsonl", rows)
    write_json(args.output_dir / "ranked_commit_episode_seed_summary.json", summary)


if __name__ == "__main__":
    main()

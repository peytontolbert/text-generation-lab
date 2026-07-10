from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from long_context_common import read_jsonl, write_json, write_jsonl


def _normalize_paths(paths: list[Any]) -> list[str]:
    out: list[str] = []
    for path in paths:
        value = str(path or '').strip().replace('\\', '/')
        if value:
            out.append(value)
    return out


def _suffixes(path: str) -> set[str]:
    parts = [part for part in str(path or '').split('/') if part]
    suffixes: set[str] = set()
    for index in range(len(parts)):
        suffixes.add('/'.join(parts[index:]))
    return suffixes or ({str(path)} if path else set())


def _seed_paths_from_example(example: dict[str, Any]) -> list[str]:
    query = dict(example.get('query') or {})
    return _normalize_paths(list(query.get('seed_paths') or []))


def _changed_paths_from_seed(seed: dict[str, Any]) -> list[str]:
    changes = list(seed.get('changes') or [])
    out: list[str] = []
    for change in changes:
        if not isinstance(change, dict):
            continue
        path = str(change.get('path') or '').strip()
        if path:
            out.append(path.replace('\\', '/'))
    return out


def _build_existing_repo_path_index(examples: list[dict[str, Any]]) -> tuple[dict[str, set[str]], dict[str, int]]:
    suffixes_by_repo: dict[str, set[str]] = defaultdict(set)
    counts_by_repo: dict[str, int] = defaultdict(int)
    for example in examples:
        repo_id = str(example.get('repo_id') or example.get('program_id') or '')
        if not repo_id:
            continue
        counts_by_repo[repo_id] += 1
        for path in _seed_paths_from_example(example):
            suffixes_by_repo[repo_id].update(_suffixes(path))
    return dict(suffixes_by_repo), dict(counts_by_repo)


def _corpus_novelty_score(*, repo_id: str, changed_paths: list[str], existing_suffixes: dict[str, set[str]], existing_counts: dict[str, int]) -> tuple[float, dict[str, Any]]:
    seen_count = int(existing_counts.get(repo_id, 0))
    changed = _normalize_paths(changed_paths)
    if not changed:
        metadata = {
            'repo_seen_count': seen_count,
            'changed_path_count': 0,
            'novel_path_count': 0,
            'novel_path_ratio': 0.0,
            'repo_seen_before': bool(seen_count),
        }
        return (200.0 if seen_count == 0 else -25.0), metadata

    seen_suffixes = existing_suffixes.get(repo_id, set())
    novel_path_count = 0
    overlapping_path_count = 0
    for path in changed:
        suffixes = _suffixes(path)
        if suffixes & seen_suffixes:
            overlapping_path_count += 1
        else:
            novel_path_count += 1
    novel_ratio = novel_path_count / len(changed)
    score = 0.0
    if seen_count == 0:
        score += 200.0
    else:
        score -= min(seen_count, 8) * 20.0
    score += novel_path_count * 15.0
    score += novel_ratio * 60.0
    score -= overlapping_path_count * 5.0
    metadata = {
        'repo_seen_count': seen_count,
        'changed_path_count': len(changed),
        'novel_path_count': novel_path_count,
        'overlapping_path_count': overlapping_path_count,
        'novel_path_ratio': round(novel_ratio, 6),
        'repo_seen_before': bool(seen_count),
    }
    return score, metadata


def rerank_commit_seeds_by_corpus_novelty(
    *,
    ranked_seeds_path: Path,
    existing_examples_path: Path,
    discoverability_weight: float = 1.0,
    corpus_novelty_weight: float = 1.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ranked_seeds = read_jsonl(ranked_seeds_path)
    existing_examples = read_jsonl(existing_examples_path)
    existing_suffixes, existing_counts = _build_existing_repo_path_index(existing_examples)

    reranked: list[dict[str, Any]] = []
    route_counts: Counter[str] = Counter()
    repo_seen_histogram: Counter[int] = Counter()

    for seed in ranked_seeds:
        repo_id = str(seed.get('repo_id') or '')
        rank_metadata = dict(seed.get('rank_metadata') or {})
        discoverability_score = float(rank_metadata.get('discoverability_score') or 0.0)
        changed_paths = _changed_paths_from_seed(seed)
        novelty_score, novelty_metadata = _corpus_novelty_score(
            repo_id=repo_id,
            changed_paths=changed_paths,
            existing_suffixes=existing_suffixes,
            existing_counts=existing_counts,
        )
        combined_score = (discoverability_weight * discoverability_score) + (corpus_novelty_weight * novelty_score)
        route = str(rank_metadata.get('discoverability_route') or '')
        route_counts[route] += 1
        repo_seen_histogram[int(novelty_metadata['repo_seen_count'])] += 1
        reranked.append(
            {
                **seed,
                'rank_metadata': {
                    **rank_metadata,
                    'corpus_novelty_score': novelty_score,
                    'combined_selection_score': combined_score,
                    'corpus_novelty': novelty_metadata,
                },
            }
        )

    reranked.sort(
        key=lambda row: (
            -float((row.get('rank_metadata') or {}).get('combined_selection_score') or 0.0),
            -float((row.get('rank_metadata') or {}).get('discoverability_score') or 0.0),
            -float((row.get('rank_metadata') or {}).get('corpus_novelty_score') or 0.0),
            str(row.get('repo_id') or ''),
            str(row.get('seed_id') or ''),
        )
    )
    summary = {
        'input_seed_count': len(ranked_seeds),
        'existing_example_count': len(existing_examples),
        'avg_discoverability_score': (
            sum(float((row.get('rank_metadata') or {}).get('discoverability_score') or 0.0) for row in reranked) / len(reranked)
            if reranked else 0.0
        ),
        'avg_corpus_novelty_score': (
            sum(float((row.get('rank_metadata') or {}).get('corpus_novelty_score') or 0.0) for row in reranked) / len(reranked)
            if reranked else 0.0
        ),
        'avg_combined_selection_score': (
            sum(float((row.get('rank_metadata') or {}).get('combined_selection_score') or 0.0) for row in reranked) / len(reranked)
            if reranked else 0.0
        ),
        'discoverability_weight': float(discoverability_weight),
        'corpus_novelty_weight': float(corpus_novelty_weight),
        'route_counts': dict(sorted(route_counts.items())),
        'repo_seen_histogram': {str(key): int(value) for key, value in sorted(repo_seen_histogram.items())},
        'top_rows': [
            {
                'seed_id': str(row.get('seed_id') or ''),
                'repo_id': str(row.get('repo_id') or ''),
                'combined_selection_score': float((row.get('rank_metadata') or {}).get('combined_selection_score') or 0.0),
                'discoverability_score': float((row.get('rank_metadata') or {}).get('discoverability_score') or 0.0),
                'corpus_novelty_score': float((row.get('rank_metadata') or {}).get('corpus_novelty_score') or 0.0),
                'corpus_novelty': dict((row.get('rank_metadata') or {}).get('corpus_novelty') or {}),
            }
            for row in reranked[: min(20, len(reranked))]
        ],
    }
    return reranked, summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Rerank commit seeds by discoverability plus novelty against an existing corpus.')
    parser.add_argument('--ranked-seeds', type=Path, required=True)
    parser.add_argument('--existing-examples', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path)
    parser.add_argument('--discoverability-weight', type=float, default=1.0)
    parser.add_argument('--corpus-novelty-weight', type=float, default=1.0)
    args = parser.parse_args()
    rows, summary = rerank_commit_seeds_by_corpus_novelty(
        ranked_seeds_path=args.ranked_seeds,
        existing_examples_path=args.existing_examples,
        discoverability_weight=args.discoverability_weight,
        corpus_novelty_weight=args.corpus_novelty_weight,
    )
    write_jsonl(args.output, rows)
    write_json(args.summary_output or args.output.with_name('reranked_commit_episode_seed_summary.json'), summary)


if __name__ == '__main__':
    main()

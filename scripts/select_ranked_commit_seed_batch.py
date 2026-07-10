from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from long_context_common import read_jsonl, write_json, write_jsonl


def select_ranked_commit_seed_batch(
    *,
    ranked_seeds_path: Path,
    max_seeds: int,
    one_per_repo: bool = True,
    require_targeted_tests: bool = True,
    require_direct_test_touch: bool = False,
    allow_broad_discovery_for_unseen: bool = False,
    min_broad_discovery_score: float | None = None,
    max_seen_repos: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = read_jsonl(ranked_seeds_path)
    selected: list[dict[str, Any]] = []
    seen_repos: set[str] = set()
    route_counts: Counter[str] = Counter()
    selected_seen_repo_count = 0

    for row in rows:
        rank_metadata = row.get("rank_metadata") if isinstance(row.get("rank_metadata"), dict) else {}
        route = str(rank_metadata.get("discoverability_route") or "")
        corpus_novelty = dict(rank_metadata.get("corpus_novelty") or {})
        repo_seen_before = bool(corpus_novelty.get("repo_seen_before"))
        allow_broad_for_row = bool(allow_broad_discovery_for_unseen and not repo_seen_before)
        broad_signal = max(
            float(rank_metadata.get("top_broad_test_score") or 0.0),
            float(rank_metadata.get("top_broad_verification_score") or 0.0),
        )
        if require_targeted_tests and route != "PASS_TARGETED_TEST_SELECTION" and not allow_broad_for_row:
            route_counts[f"SKIP_ROUTE_{route or 'UNKNOWN'}"] += 1
            continue
        if route != "PASS_TARGETED_TEST_SELECTION" and allow_broad_for_row and min_broad_discovery_score is not None and broad_signal < float(min_broad_discovery_score):
            route_counts["SKIP_BROAD_DISCOVERY_BELOW_MIN_SCORE"] += 1
            continue
        if require_direct_test_touch and not bool(rank_metadata.get("has_direct_test_touch")):
            route_counts["SKIP_NO_DIRECT_TEST_TOUCH"] += 1
            continue
        if max_seen_repos is not None and repo_seen_before and selected_seen_repo_count >= int(max_seen_repos):
            route_counts["SKIP_MAX_SEEN_REPOS"] += 1
            continue
        repo_id = str(row.get("repo_id") or "")
        if one_per_repo and repo_id in seen_repos:
            route_counts["SKIP_DUPLICATE_REPO"] += 1
            continue
        selected.append(row)
        if repo_seen_before:
            selected_seen_repo_count += 1
        if repo_id:
            seen_repos.add(repo_id)
        route_counts["SELECTED"] += 1
        if len(selected) >= max_seeds:
            break

    summary = {
        "input_ranked_seed_count": len(rows),
        "selected_seed_count": len(selected),
        "unique_repo_count": len({str(row.get("repo_id") or "") for row in selected if str(row.get("repo_id") or "")}),
        "route_counts": dict(sorted(route_counts.items())),
        "constraints": {
            "max_seeds": int(max_seeds),
            "one_per_repo": bool(one_per_repo),
            "require_targeted_tests": bool(require_targeted_tests),
            "require_direct_test_touch": bool(require_direct_test_touch),
            "allow_broad_discovery_for_unseen": bool(allow_broad_discovery_for_unseen),
            "min_broad_discovery_score": float(min_broad_discovery_score) if min_broad_discovery_score is not None else None,
            "max_seen_repos": int(max_seen_repos) if max_seen_repos is not None else None,
        },
    }
    if rows and not selected:
        raise ValueError("no_ranked_commit_seeds_selected")
    return selected, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Select a bounded high-yield batch from ranked commit seeds.")
    parser.add_argument("--ranked-seeds", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--max-seeds", type=int, default=40)
    parser.add_argument("--allow-multi-per-repo", action="store_true")
    parser.add_argument("--allow-broad-discovery", action="store_true")
    parser.add_argument("--require-direct-test-touch", action="store_true")
    parser.add_argument("--allow-broad-discovery-for-unseen", action="store_true")
    parser.add_argument("--min-broad-discovery-score", type=float)
    parser.add_argument("--max-seen-repos", type=int)
    args = parser.parse_args()
    rows, summary = select_ranked_commit_seed_batch(
        ranked_seeds_path=args.ranked_seeds,
        max_seeds=args.max_seeds,
        one_per_repo=not args.allow_multi_per_repo,
        require_targeted_tests=not args.allow_broad_discovery,
        require_direct_test_touch=args.require_direct_test_touch,
        allow_broad_discovery_for_unseen=args.allow_broad_discovery_for_unseen,
        min_broad_discovery_score=args.min_broad_discovery_score,
        max_seen_repos=args.max_seen_repos,
    )
    write_jsonl(args.output, rows)
    write_json(args.summary_output or args.output.with_name("selected_ranked_commit_seed_batch_summary.json"), summary)


if __name__ == "__main__":
    main()

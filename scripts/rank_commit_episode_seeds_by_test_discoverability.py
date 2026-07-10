from __future__ import annotations

import argparse
import warnings
from collections import Counter
from pathlib import Path
from typing import Any

from coverage_test_selection import candidate_tests_for_change, select_tests
from long_context_common import read_jsonl, write_json, write_jsonl
from mine_local_root_session_episodes import _collect_candidate_paths, _repo_index_from_paths
warnings.filterwarnings("ignore", category=SyntaxWarning)


from mine_selected_repo_commit_episodes import (
    _build_repo_analysis,
    _build_repo_file_index,
    _build_test_to_symbols,
    _broad_discovery_test_candidates,
    _broad_discovery_verification_candidates,
    _candidate_neighbor_paths,
    _is_python_path,
    _is_test_path,
    _read_filtered_chunk_rows,
    _seed_symbol_names,
    _resolve_changed_paths,
)


VERIFICATION_PATH_MARKERS = ("eval", "evaluate", "benchmark", "bench", "check", "verify", "smoke", "integration", "example")


def _discoverability_score(
    *,
    selected_count: int,
    candidate_count: int,
    top_candidate_score: float,
    broad_test_candidate_count: int,
    top_broad_test_score: float,
    broad_verification_candidate_count: int,
    top_broad_verification_score: float,
    has_direct_test_touch: bool,
    has_symbol_link: bool,
    has_stem_match: bool,
    repo_test_file_count: int,
    repo_verification_file_count: int,
    neighbor_count: int,
    changed_python_count: int,
) -> float:
    score = 0.0
    score += min(selected_count, 8) * 8.0
    score += min(candidate_count, 12) * 1.5
    score += float(top_candidate_score) * 4.0
    score += min(broad_test_candidate_count, 8) * 1.25
    score += min(top_broad_test_score, 12.0) * 1.5
    score += min(broad_verification_candidate_count, 8) * 0.75
    score += min(top_broad_verification_score, 12.0) * 1.0
    score += min(repo_test_file_count, 32) * 0.25
    score += min(repo_verification_file_count, 24) * 0.2
    score += min(neighbor_count, 12) * 0.5
    score += min(changed_python_count, 8) * 0.75
    if has_direct_test_touch:
        score += 10.0
    if has_symbol_link:
        score += 8.0
    if has_stem_match:
        score += 4.0
    if selected_count == 0 and broad_test_candidate_count > 0:
        score += 6.0
    if selected_count == 0 and broad_verification_candidate_count > 0:
        score += 3.0
    return score


def _changed_rel_paths_for_local_repo(repo_id: str, changes: list[dict[str, Any]]) -> list[str]:
    rel_paths: list[str] = []
    prefix = f"{repo_id}/"
    for change in changes:
        if not isinstance(change, dict):
            continue
        raw = str(change.get("path") or change.get("file") or "").strip().replace("\\", "/").lstrip("./")
        if not raw:
            continue
        rel = raw[len(prefix):] if raw.startswith(prefix) else raw
        rel_paths.append(rel)
    return rel_paths


def _repo_analysis_from_local_root(
    *,
    repo_root: Path,
    repo_id: str,
    changes: list[dict[str, Any]],
    root_file_limit: int,
    neighbor_dir_file_limit: int,
    max_total_candidates: int,
    walk_cache: dict[str, list[Path]],
    file_info_cache: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    changed_rel_paths = _changed_rel_paths_for_local_repo(repo_id, changes)
    candidate_paths = _collect_candidate_paths(
        repo_root,
        changed_rel_paths,
        root_file_limit=root_file_limit,
        neighbor_dir_file_limit=neighbor_dir_file_limit,
        max_total_candidates=max_total_candidates,
        walk_cache=walk_cache,
    )
    repo_files = _repo_index_from_paths(repo_root, candidate_paths, file_info_cache=file_info_cache)
    repo_analysis: dict[str, dict[str, Any]] = {}
    for rel_path, info in repo_files.items():
        repo_analysis[rel_path] = {
            "path": rel_path,
            "repo_id": repo_id,
            "chunk_rows": [],
            "text": str(info.get("text") or ""),
            "defined_symbols": list(info.get("defined_symbols") or []),
            "imported_symbols": list(info.get("imported_symbols") or []),
            "called_symbols": list(info.get("called_symbols") or []),
        }
    return repo_analysis


def _resolve_local_repo_root(seed: dict[str, Any], repositories_root: Path) -> Path:
    metadata = dict(seed.get("metadata") or {})
    explicit = str(metadata.get("repo_root") or "").strip()
    if explicit:
        return Path(explicit)
    repo_id = str(seed.get("repo_id") or "").strip()
    if not repo_id:
        return Path()
    return repositories_root / repo_id


def rank_commit_episode_seeds_by_test_discoverability(
    *,
    seeds_path: Path,
    index_dir: Path | None = None,
    repositories_root: Path | None = None,
    max_selected_tests: int = 8,
    root_file_limit: int = 400,
    neighbor_dir_file_limit: int = 250,
    max_total_candidates: int = 1600,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if (index_dir is None) == (repositories_root is None):
        raise ValueError("exactly_one_source_mode_required")

    seeds = read_jsonl(seeds_path)
    source_mode = "index_dir" if index_dir is not None else "repositories_root"
    repo_analysis_by_id: dict[str, dict[str, dict[str, Any]]] = {}
    local_repo_roots: dict[str, Path] = {}
    walk_cache_by_repo: dict[str, dict[str, list[Path]]] = {}
    file_info_cache_by_repo: dict[str, dict[str, dict[str, Any]]] = {}

    if index_dir is not None:
        selected_repo_ids = {str(row.get("repo_id") or "") for row in seeds if str(row.get("repo_id") or "")}
        chunks = _read_filtered_chunk_rows(index_dir, selected_repo_ids, include_papers=False)
        repo_files = _build_repo_file_index(chunks)
        repo_analysis_by_id = _build_repo_analysis(repo_files)

    ranked_rows: list[dict[str, Any]] = []
    route_counts: Counter[str] = Counter()

    for seed in seeds:
        repo_id = str(seed.get("repo_id") or "")
        changes = list(seed.get("changes") or [])

        if repositories_root is not None:
            repo_root = _resolve_local_repo_root(seed, repositories_root)
            if not repo_root.exists() or not repo_root.is_dir():
                route_counts["SKIP_NO_LOCAL_REPO_ROOT"] += 1
                continue
            local_repo_roots[repo_id] = repo_root
            repo_analysis = _repo_analysis_from_local_root(
                repo_root=repo_root,
                repo_id=repo_id,
                changes=changes,
                root_file_limit=root_file_limit,
                neighbor_dir_file_limit=neighbor_dir_file_limit,
                max_total_candidates=max_total_candidates,
                walk_cache=walk_cache_by_repo.setdefault(repo_id, {}),
                file_info_cache=file_info_cache_by_repo.setdefault(repo_id, {}),
            )
        else:
            repo_analysis = repo_analysis_by_id.get(repo_id)

        if not repo_analysis:
            route_counts["SKIP_NO_REPO_ANALYSIS"] += 1
            continue

        changed_lookup_paths, changed_display_paths = _resolve_changed_paths(repo_id, changes, repo_analysis)
        if not changed_lookup_paths:
            route_counts["SKIP_NO_MATCHED_PATHS"] += 1
            continue

        changed_infos = [repo_analysis[path] for path in changed_lookup_paths]
        seed_symbols = _seed_symbol_names(changes, changed_infos)
        repo_parse_failure_count = sum(1 for info in repo_analysis.values() if str(info.get("analysis_status") or "") == "parse_failed")
        repo_index = {
            "files": sorted(repo_analysis),
            "coverage_map": {},
            "test_to_symbols": _build_test_to_symbols(repo_analysis),
        }
        normalized_changes = [{"path": path, "symbol": ""} for path in changed_display_paths]
        candidate_tests: dict[str, dict[str, Any]] = {}
        has_symbol_link = False
        has_stem_match = False
        for change in normalized_changes:
            for candidate in candidate_tests_for_change(change, repo_index):
                reasons = set(str(item) for item in candidate.get("reasons", []))
                if "symbol_match" in reasons:
                    has_symbol_link = True
                if "path_stem_match" in reasons:
                    has_stem_match = True
                current = candidate_tests.get(candidate["test_path"])
                if current is None or float(candidate["score"]) > float(current["score"]):
                    candidate_tests[candidate["test_path"]] = candidate
        test_selection = select_tests(
            {
                "row_id": str(seed.get("seed_id") or ""),
                "repo_index": repo_index,
                "changes": normalized_changes,
            },
            max_tests=max_selected_tests,
        )
        route = str(test_selection.get("test_selection_route") or "")
        route_counts[route] += 1
        candidate_ranked = sorted(candidate_tests.values(), key=lambda item: (-float(item["score"]), item["test_path"]))
        selected_tests = list(test_selection.get("selected_tests") or [])
        repo_test_file_count = sum(1 for path in repo_analysis if _is_test_path(path))
        repo_verification_file_count = sum(
            1
            for path in repo_analysis
            if path.endswith(".py") and not _is_test_path(path) and any(marker in path.lower() for marker in VERIFICATION_PATH_MARKERS)
        )
        changed_python_count = sum(1 for path in changed_lookup_paths if _is_python_path(path))
        has_direct_test_touch = any(_is_test_path(path) for path in changed_display_paths)
        neighbor_count = len(
            _candidate_neighbor_paths(
                repo_analysis=repo_analysis,
                changed_paths=changed_lookup_paths,
                seed_symbols=seed_symbols,
            )
        )
        broad_test_candidates = _broad_discovery_test_candidates(
            repo_analysis=repo_analysis,
            changed_paths=changed_display_paths,
            changed_infos=changed_infos,
            seed_symbols=seed_symbols,
            goal=str(seed.get("goal") or ""),
            max_results=max_selected_tests,
        )
        broad_verification_candidates = _broad_discovery_verification_candidates(
            repo_analysis=repo_analysis,
            changed_paths=changed_display_paths,
            changed_infos=changed_infos,
            seed_symbols=seed_symbols,
            goal=str(seed.get("goal") or ""),
            max_results=max_selected_tests,
        )
        top_candidate_score = float(candidate_ranked[0]["score"]) if candidate_ranked else 0.0
        top_broad_test_score = float(broad_test_candidates[0]["score"]) if broad_test_candidates else 0.0
        top_broad_verification_score = float(broad_verification_candidates[0]["score"]) if broad_verification_candidates else 0.0
        score = _discoverability_score(
            selected_count=len(selected_tests),
            candidate_count=len(candidate_ranked),
            top_candidate_score=top_candidate_score,
            broad_test_candidate_count=len(broad_test_candidates),
            top_broad_test_score=top_broad_test_score,
            broad_verification_candidate_count=len(broad_verification_candidates),
            top_broad_verification_score=top_broad_verification_score,
            has_direct_test_touch=has_direct_test_touch,
            has_symbol_link=has_symbol_link,
            has_stem_match=has_stem_match,
            repo_test_file_count=repo_test_file_count,
            repo_verification_file_count=repo_verification_file_count,
            neighbor_count=neighbor_count,
            changed_python_count=changed_python_count,
        )
        rank_metadata = {
            "discoverability_route": route,
            "discoverability_score": score,
            "selected_tests": selected_tests,
            "selected_test_count": len(selected_tests),
            "candidate_test_count": len(candidate_ranked),
            "top_candidate_score": top_candidate_score,
            "broad_test_candidate_count": len(broad_test_candidates),
            "top_broad_test_score": top_broad_test_score,
            "broad_verification_candidate_count": len(broad_verification_candidates),
            "top_broad_verification_score": top_broad_verification_score,
            "repo_test_file_count": repo_test_file_count,
            "repo_verification_file_count": repo_verification_file_count,
            "repo_parse_failure_count": repo_parse_failure_count,
            "neighbor_count": neighbor_count,
            "changed_python_count": changed_python_count,
            "changed_path_count": len(changed_display_paths),
            "has_direct_test_touch": has_direct_test_touch,
            "has_symbol_link": has_symbol_link,
            "has_stem_match": has_stem_match,
            "seed_symbols": sorted(seed_symbols)[:32],
            "candidate_tests_preview": candidate_ranked[:8],
            "broad_test_candidates_preview": broad_test_candidates[:8],
            "broad_verification_candidates_preview": broad_verification_candidates[:8],
            "source_mode": source_mode,
        }
        ranked_rows.append({**seed, "rank_metadata": rank_metadata})

    ranked_rows.sort(
        key=lambda row: (
            -float((row.get("rank_metadata") or {}).get("discoverability_score") or 0.0),
            -int((row.get("rank_metadata") or {}).get("selected_test_count") or 0),
            str(row.get("repo_id") or ""),
            str(row.get("seed_id") or ""),
        )
    )
    summary = {
        "seed_count": len(seeds),
        "ranked_seed_count": len(ranked_rows),
        "route_counts": dict(sorted(route_counts.items())),
        "avg_discoverability_score": (
            sum(float((row.get("rank_metadata") or {}).get("discoverability_score") or 0.0) for row in ranked_rows) / len(ranked_rows)
            if ranked_rows
            else 0.0
        ),
        "source_mode": source_mode,
    }
    if seeds and not ranked_rows:
        if route_counts.get("SKIP_NO_LOCAL_REPO_ROOT") == len(seeds):
            raise ValueError("all_seeds_missing_local_repo_root")
        if route_counts.get("SKIP_NO_REPO_ANALYSIS") == len(seeds):
            raise ValueError("all_seeds_missing_repo_analysis")
        raise ValueError("no_ranked_commit_seeds_built")
    return ranked_rows, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank commit episode seeds by strict test discoverability before expensive mining.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--index-dir", type=Path)
    source_group.add_argument("--repositories-root", type=Path)
    parser.add_argument("--seeds", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--max-selected-tests", type=int, default=8)
    parser.add_argument("--root-file-limit", type=int, default=400)
    parser.add_argument("--neighbor-dir-file-limit", type=int, default=250)
    parser.add_argument("--max-total-candidates", type=int, default=1600)
    args = parser.parse_args()
    rows, summary = rank_commit_episode_seeds_by_test_discoverability(
        index_dir=args.index_dir,
        repositories_root=args.repositories_root,
        seeds_path=args.seeds,
        max_selected_tests=args.max_selected_tests,
        root_file_limit=args.root_file_limit,
        neighbor_dir_file_limit=args.neighbor_dir_file_limit,
        max_total_candidates=args.max_total_candidates,
    )
    write_jsonl(args.output, rows)
    write_json(args.summary_output or args.output.with_name("ranked_commit_episode_seed_summary.json"), summary)


if __name__ == "__main__":
    main()

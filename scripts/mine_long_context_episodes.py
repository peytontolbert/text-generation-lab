from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from coverage_test_selection import select_tests
from long_context_common import extract_terms, lexical_overlap_score, read_jsonl, stable_id, write_json, write_jsonl
from program_state_call_graph_extractor import extract_python_call_graph
from program_state_symbol_table_extractor import extract_python_symbols


def _read_chunk_rows(index_dir: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    rows: list[dict[str, Any]] = []
    for shard in sorted((index_dir / "chunks").glob("*.parquet")):
        rows.extend(pq.read_table(shard).to_pylist())
    return rows


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("metadata_json") or "{}"
    if isinstance(value, dict):
        return value
    return json.loads(str(value))


def _norm_path(path: str) -> str:
    return str(path or "").replace("\\", "/").lstrip("./")


def _is_python_path(path: str) -> bool:
    return _norm_path(path).endswith(".py")


def _is_test_path(path: str) -> bool:
    normalized = _norm_path(path)
    name = normalized.rsplit("/", 1)[-1]
    return normalized.startswith("tests/") or "/tests/" in normalized or name.startswith("test_") or name.endswith("_test.py")


def _repo_file_text(chunk_rows: list[dict[str, Any]]) -> str:
    ordered = sorted(chunk_rows, key=lambda row: (int(row.get("chunk_index") or 0), str(row.get("chunk_id") or "")))
    return "\n".join(str(row.get("text") or "") for row in ordered if str(row.get("text") or "").strip())


def _build_repo_file_index(chunks: list[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    repo_files: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in chunks:
        if str(row.get("source_type") or "") != "repo":
            continue
        metadata = _metadata(row)
        path = _norm_path(str(metadata.get("path") or ""))
        if not path:
            continue
        repo_id = str(row.get("source_id") or "")
        repo_files[repo_id][path].append(row)
    return {repo_id: dict(path_map) for repo_id, path_map in repo_files.items()}


def _build_paper_chunk_rows(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in chunks if str(row.get("source_type") or "") == "paper"]


def _python_file_analysis(repo_id: str, path: str, chunk_rows: list[dict[str, Any]]) -> dict[str, Any]:
    text = _repo_file_text(chunk_rows)
    symbol_packet = extract_python_symbols(text, row_id=f"{repo_id}:{path}", path=path).to_dict()
    call_packet = extract_python_call_graph(text, row_id=f"{repo_id}:{path}", path=path).to_dict()
    defined_symbols = {
        str(symbol.get("name") or "")
        for symbol in symbol_packet.get("symbols", [])
        if str(symbol.get("symbol_kind") or "") in {"function", "async_function", "method", "class"}
    }
    imported_symbols = {
        str(symbol.get("name") or "")
        for symbol in symbol_packet.get("symbols", [])
        if str(symbol.get("symbol_kind") or "") == "import"
    }
    called_symbols = {
        str(node.get("name") or "")
        for node in call_packet.get("call_nodes", [])
        if str(node.get("node_kind") or "") in {"callee_reference", "callsite"}
    }
    return {
        "path": path,
        "repo_id": repo_id,
        "chunk_rows": sorted(chunk_rows, key=lambda row: (int(row.get("chunk_index") or 0), str(row.get("chunk_id") or ""))),
        "text": text,
        "defined_symbols": sorted(symbol for symbol in defined_symbols if symbol),
        "imported_symbols": sorted(symbol for symbol in imported_symbols if symbol),
        "called_symbols": sorted(symbol for symbol in called_symbols if symbol and symbol != "<unknown>"),
        "symbol_failures": list(symbol_packet.get("failures") or []),
        "call_failures": list(call_packet.get("failures") or []),
    }


def _build_repo_analysis(repo_files: dict[str, dict[str, list[dict[str, Any]]]]) -> dict[str, dict[str, dict[str, Any]]]:
    analysis: dict[str, dict[str, dict[str, Any]]] = {}
    for repo_id, path_map in repo_files.items():
        repo_analysis: dict[str, dict[str, Any]] = {}
        for path, chunk_rows in path_map.items():
            if _is_python_path(path):
                repo_analysis[path] = _python_file_analysis(repo_id, path, chunk_rows)
            else:
                repo_analysis[path] = {
                    "path": path,
                    "repo_id": repo_id,
                    "chunk_rows": sorted(chunk_rows, key=lambda row: (int(row.get("chunk_index") or 0), str(row.get("chunk_id") or ""))),
                    "text": _repo_file_text(chunk_rows),
                    "defined_symbols": [],
                    "imported_symbols": [],
                    "called_symbols": [],
                    "symbol_failures": [],
                    "call_failures": [],
                }
        analysis[repo_id] = repo_analysis
    return analysis


def _build_test_to_symbols(repo_analysis: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for path, info in repo_analysis.items():
        if not _is_test_path(path):
            continue
        symbols = sorted(set(info.get("defined_symbols", [])) | set(info.get("called_symbols", [])))
        mapping[path] = symbols
    return mapping


def _seed_symbol_names(changes: list[dict[str, Any]], changed_infos: list[dict[str, Any]]) -> set[str]:
    names = {
        str(change.get("symbol") or change.get("function") or change.get("class") or "")
        for change in changes
        if isinstance(change, dict)
    }
    for info in changed_infos:
        names.update(info.get("defined_symbols", []))
        names.update(info.get("called_symbols", []))
        names.update(info.get("imported_symbols", []))
    return {name for name in names if name}


def _changed_paths(changes: list[dict[str, Any]]) -> list[str]:
    out = []
    for change in changes:
        if not isinstance(change, dict):
            continue
        path = _norm_path(str(change.get("path") or change.get("file") or ""))
        if path:
            out.append(path)
    return out


def _candidate_neighbor_paths(
    *,
    repo_analysis: dict[str, dict[str, Any]],
    changed_paths: list[str],
    seed_symbols: set[str],
) -> list[dict[str, Any]]:
    changed_set = set(changed_paths)
    neighbors: list[dict[str, Any]] = []
    for path, info in repo_analysis.items():
        if path in changed_set:
            continue
        reasons: list[str] = []
        score = 0.0
        defined = set(info.get("defined_symbols", []))
        imported = set(info.get("imported_symbols", []))
        called = set(info.get("called_symbols", []))
        if defined & seed_symbols:
            reasons.append("defines_seed_symbol")
            score += 3.0
        if imported & seed_symbols:
            reasons.append("imports_seed_symbol")
            score += 2.0
        if called & seed_symbols:
            reasons.append("calls_seed_symbol")
            score += 2.0
        if any(symbol in defined for symbol in seed_symbols if "." in symbol and symbol.rsplit(".", 1)[-1] in defined):
            reasons.append("defines_called_suffix")
            score += 1.0
        if not reasons:
            continue
        if _is_test_path(path):
            score -= 0.5
        neighbors.append({"path": path, "reasons": sorted(set(reasons)), "score": score})
    return sorted(neighbors, key=lambda row: (-float(row["score"]), row["path"]))


def _cross_repo_analogues(
    *,
    repo_analysis_by_id: dict[str, dict[str, dict[str, Any]]],
    repo_id: str,
    seed_symbols: set[str],
    max_results: int,
) -> list[dict[str, Any]]:
    analogues: list[dict[str, Any]] = []
    for other_repo_id, repo_analysis in repo_analysis_by_id.items():
        if other_repo_id == repo_id:
            continue
        for path, info in repo_analysis.items():
            defined = set(info.get("defined_symbols", []))
            called = set(info.get("called_symbols", []))
            imported = set(info.get("imported_symbols", []))
            symbol_overlap = (defined | called | imported) & seed_symbols
            if not symbol_overlap:
                continue
            score = float(len(symbol_overlap))
            reasons = []
            if defined & seed_symbols:
                reasons.append("defines_seed_symbol")
                score += 1.5
            if called & seed_symbols:
                reasons.append("calls_seed_symbol")
                score += 1.0
            if imported & seed_symbols:
                reasons.append("imports_seed_symbol")
                score += 0.5
            analogues.append(
                {
                    "repo_id": other_repo_id,
                    "path": path,
                    "score": score,
                    "reasons": sorted(set(reasons)),
                    "symbol_overlap": sorted(symbol_overlap),
                }
            )
    return sorted(analogues, key=lambda row: (-float(row["score"]), str(row["repo_id"]), str(row["path"])))[:max_results]


def _paper_grounding_candidates(
    *,
    paper_rows: list[dict[str, Any]],
    seed_symbols: set[str],
    goal: str,
    max_results: int,
) -> list[dict[str, Any]]:
    query_text = " ".join(sorted(seed_symbols)) + "\n" + str(goal or "")
    if not query_text.strip():
        return []
    seed_terms = set(extract_terms(query_text, max_terms=48))
    candidates: list[dict[str, Any]] = []
    for row in paper_rows:
        text = str(row.get("text") or "")
        if not text.strip():
            continue
        overlap = lexical_overlap_score(query_text, text)
        if overlap <= 0.0:
            continue
        chunk_terms = set(extract_terms(text, max_terms=48))
        shared_terms = sorted(seed_terms & chunk_terms)[:12]
        score = overlap + 0.05 * len(shared_terms)
        candidates.append({"row": row, "score": score, "shared_terms": shared_terms})
    return sorted(candidates, key=lambda item: (-float(item["score"]), str(item["row"].get("source_id") or ""), str(item["row"].get("chunk_id") or "")))[:max_results]


def _chunk_context_rows(
    chunk_rows: list[dict[str, Any]],
    *,
    role: str,
    retrieval_reason: str,
    distance_from_seed: int,
    retrieval_score: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chunk in sorted(chunk_rows, key=lambda row: (int(row.get("chunk_index") or 0), str(row.get("chunk_id") or ""))):
        metadata = _metadata(chunk)
        rows.append(
            {
                "chunk_id": str(chunk.get("chunk_id") or ""),
                "source_type": str(chunk.get("source_type") or ""),
                "source_id": str(chunk.get("source_id") or ""),
                "doc_id": str(chunk.get("doc_id") or ""),
                "path": _norm_path(str(metadata.get("path") or "")),
                "chunk_index": int(chunk.get("chunk_index") or 0),
                "token_count": int(chunk.get("token_count") or 0),
                "text": str(chunk.get("text") or ""),
                "role": role,
                "retrieval_reason": retrieval_reason,
                "distance_from_seed": int(distance_from_seed),
                "retrieval_score": float(retrieval_score),
            }
        )
    return rows


def _dedupe_context_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_chunk_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        chunk_id = str(row.get("chunk_id") or "")
        current = by_chunk_id.get(chunk_id)
        if current is None:
            by_chunk_id[chunk_id] = row
            continue
        current_score = (int(current.get("distance_from_seed") or 0), -float(current.get("retrieval_score") or 0.0))
        new_score = (int(row.get("distance_from_seed") or 0), -float(row.get("retrieval_score") or 0.0))
        if new_score < current_score:
            by_chunk_id[chunk_id] = row
    return sorted(
        by_chunk_id.values(),
        key=lambda row: (
            int(row.get("distance_from_seed") or 0),
            str(row.get("role") or ""),
            str(row.get("path") or ""),
            int(row.get("chunk_index") or 0),
            str(row.get("chunk_id") or ""),
        ),
    )


def _repo_index_for_seed(repo_analysis: dict[str, dict[str, Any]], coverage_map: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "files": sorted(repo_analysis),
        "coverage_map": dict(coverage_map or {}),
        "test_to_symbols": _build_test_to_symbols(repo_analysis),
    }


def _episode_targets(seed: dict[str, Any]) -> dict[str, Any]:
    if isinstance(seed.get("target"), dict):
        return dict(seed["target"])
    return {
        "expected_patch_summary": str(seed.get("expected_patch_summary") or ""),
        "expected_outcome": str(seed.get("expected_outcome") or ""),
        "state_after": dict(seed.get("state_after") or {}),
    }


def build_long_context_episodes(
    *,
    index_dir: Path,
    seeds_path: Path,
    max_neighbor_files: int = 12,
    max_selected_tests: int = 8,
    max_cross_repo_files: int = 8,
    max_paper_chunks: int = 12,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    chunks = _read_chunk_rows(index_dir)
    repo_files = _build_repo_file_index(chunks)
    repo_analysis_by_id = _build_repo_analysis(repo_files)
    paper_rows = _build_paper_chunk_rows(chunks)
    seeds = read_jsonl(seeds_path)

    episodes: list[dict[str, Any]] = []
    route_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()

    for seed in seeds:
        repo_id = str(seed.get("repo_id") or seed.get("source_id") or "")
        repo_analysis = repo_analysis_by_id.get(repo_id)
        if not repo_analysis:
            continue
        changes = list(seed.get("changes") or [])
        changed_paths = [path for path in _changed_paths(changes) if path in repo_analysis]
        if not changed_paths:
            continue
        changed_infos = [repo_analysis[path] for path in changed_paths]
        seed_symbols = _seed_symbol_names(changes, changed_infos)
        repo_index = _repo_index_for_seed(repo_analysis, coverage_map=seed.get("coverage_map") if isinstance(seed.get("coverage_map"), dict) else None)
        test_selection = select_tests(
            {
                "row_id": str(seed.get("seed_id") or seed.get("row_id") or ""),
                "repo_index": repo_index,
                "changes": changes,
            },
            max_tests=max_selected_tests,
        )
        route_counts[str(test_selection.get("test_selection_route") or "")] += 1

        context_rows: list[dict[str, Any]] = []
        for path in changed_paths:
            context_rows.extend(
                _chunk_context_rows(
                    repo_analysis[path]["chunk_rows"],
                    role="seed_change",
                    retrieval_reason="changed_path",
                    distance_from_seed=0,
                    retrieval_score=1.0,
                )
            )

        neighbor_paths = _candidate_neighbor_paths(
            repo_analysis=repo_analysis,
            changed_paths=changed_paths,
            seed_symbols=seed_symbols,
        )[:max_neighbor_files]
        for neighbor in neighbor_paths:
            path = str(neighbor["path"])
            context_rows.extend(
                _chunk_context_rows(
                    repo_analysis[path]["chunk_rows"],
                    role="repo_graph_neighbor" if not _is_test_path(path) else "test_neighbor",
                    retrieval_reason="|".join(neighbor["reasons"]),
                    distance_from_seed=1,
                    retrieval_score=float(neighbor["score"]),
                )
            )

        cross_repo_paths = _cross_repo_analogues(
            repo_analysis_by_id=repo_analysis_by_id,
            repo_id=repo_id,
            seed_symbols=seed_symbols,
            max_results=max_cross_repo_files,
        )
        for analogue in cross_repo_paths:
            other_repo_id = str(analogue["repo_id"])
            path = str(analogue["path"])
            context_rows.extend(
                _chunk_context_rows(
                    repo_analysis_by_id[other_repo_id][path]["chunk_rows"],
                    role="cross_repo_analogue",
                    retrieval_reason="|".join(list(analogue["reasons"]) + list(analogue["symbol_overlap"][:4])),
                    distance_from_seed=2,
                    retrieval_score=float(analogue["score"]),
                )
            )

        for rank, test_path in enumerate(test_selection.get("selected_tests", []), start=1):
            if test_path not in repo_analysis:
                continue
            context_rows.extend(
                _chunk_context_rows(
                    repo_analysis[test_path]["chunk_rows"],
                    role="verification_constraint",
                    retrieval_reason="targeted_test_selection",
                    distance_from_seed=1,
                    retrieval_score=max(0.0, 2.0 - rank * 0.1),
                )
            )

        for paper_hit in _paper_grounding_candidates(
            paper_rows=paper_rows,
            seed_symbols=seed_symbols,
            goal=str(seed.get("goal") or ""),
            max_results=max_paper_chunks,
        ):
            paper_row = paper_hit["row"]
            metadata = _metadata(paper_row)
            context_rows.append(
                {
                    "chunk_id": str(paper_row.get("chunk_id") or ""),
                    "source_type": str(paper_row.get("source_type") or ""),
                    "source_id": str(paper_row.get("source_id") or ""),
                    "doc_id": str(paper_row.get("doc_id") or ""),
                    "path": _norm_path(str(metadata.get("path") or "")),
                    "chunk_index": int(paper_row.get("chunk_index") or 0),
                    "token_count": int(paper_row.get("token_count") or 0),
                    "text": str(paper_row.get("text") or ""),
                    "role": "algorithm_grounding",
                    "retrieval_reason": "|".join(list(paper_hit["shared_terms"])[:6]) or "lexical_overlap",
                    "distance_from_seed": 3,
                    "retrieval_score": float(paper_hit["score"]),
                }
            )

        context_rows = _dedupe_context_rows(context_rows)
        for row in context_rows:
            role_counts[str(row.get("role") or "")] += 1

        episode_id = stable_id(
            "lce",
            str(seed.get("seed_type") or "episode"),
            repo_id,
            str(seed.get("seed_id") or seed.get("row_id") or ""),
            "|".join(changed_paths),
        )
        target = _episode_targets(seed)
        episodes.append(
            {
                "episode_id": episode_id,
                "seed_id": str(seed.get("seed_id") or seed.get("row_id") or ""),
                "seed_type": str(seed.get("seed_type") or "transition_seed"),
                "repo_id": repo_id,
                "goal": str(seed.get("goal") or ""),
                "changes": changes,
                "seed_paths": changed_paths,
                "seed_symbols": sorted(seed_symbols),
                "selected_tests": list(test_selection.get("selected_tests") or []),
                "test_selection_route": str(test_selection.get("test_selection_route") or ""),
                "context_rows": context_rows,
                "context_token_count": sum(int(row.get("token_count") or 0) for row in context_rows),
                "context_role_counts": dict(sorted(Counter(str(row.get("role") or "") for row in context_rows).items())),
                "target": target,
                "transition_record": {
                    "task_intent": {
                        "intent_type": "software_maintenance_transition",
                        "intent_ref": episode_id,
                    },
                    "state_before_ref": {
                        "repo_id": repo_id,
                        "changed_paths": changed_paths,
                    },
                    "retrieval_context_refs": [
                        {
                            "chunk_id": str(row.get("chunk_id") or ""),
                            "role": str(row.get("role") or ""),
                            "path": str(row.get("path") or ""),
                            "distance_from_seed": int(row.get("distance_from_seed") or 0),
                        }
                        for row in context_rows
                    ],
                    "chosen_action": str(target.get("expected_patch_summary") or target.get("expected_outcome") or "UNSPECIFIED_ACTION"),
                },
            }
        )

    summary = {
        "episode_count": len(episodes),
        "seed_count": len(seeds),
        "test_selection_route_counts": dict(sorted(route_counts.items())),
        "context_role_counts": dict(sorted(role_counts.items())),
        "avg_context_token_count": (
            sum(int(row.get("context_token_count") or 0) for row in episodes) / len(episodes)
            if episodes
            else 0.0
        ),
    }
    return episodes, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Mine repo-local long-context transition episodes from seed changes and a chunk index.")
    parser.add_argument("--index-dir", type=Path, required=True)
    parser.add_argument("--seeds", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--max-neighbor-files", type=int, default=12)
    parser.add_argument("--max-selected-tests", type=int, default=8)
    parser.add_argument("--max-cross-repo-files", type=int, default=8)
    parser.add_argument("--max-paper-chunks", type=int, default=12)
    args = parser.parse_args()

    episodes, summary = build_long_context_episodes(
        index_dir=args.index_dir,
        seeds_path=args.seeds,
        max_neighbor_files=args.max_neighbor_files,
        max_selected_tests=args.max_selected_tests,
        max_cross_repo_files=args.max_cross_repo_files,
        max_paper_chunks=args.max_paper_chunks,
    )
    write_jsonl(args.output, episodes)
    write_json(args.summary_output or args.output.with_name("long_context_episode_summary.json"), summary)


if __name__ == "__main__":
    main()

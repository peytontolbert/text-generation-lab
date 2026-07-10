from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from long_context_common import slugify, write_json, write_jsonl


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("metadata_json") or "{}"
    if isinstance(value, dict):
        return value
    return json.loads(str(value))


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())


def _read_repo_index(index_dir: Path) -> dict[str, Any]:
    import pyarrow.parquet as pq

    source_paths: dict[str, set[str]] = defaultdict(set)
    source_roots: dict[str, set[str]] = defaultdict(set)
    for shard in sorted((index_dir / "chunks").glob("*.parquet")):
        rows = pq.read_table(shard, columns=["source_id", "source_type", "metadata_json"]).to_pylist()
        for row in rows:
            if str(row.get("source_type") or "") != "repo":
                continue
            source_id = str(row.get("source_id") or "")
            path = str((_metadata(row).get("path") or "")).replace("\\", "/")
            if not source_id or not path:
                continue
            source_paths[source_id].add(path)
            source_roots[source_id].add(path.split("/", 1)[0])
    return {"source_paths": source_paths, "source_roots": source_roots}


def _candidate_source_ids(repo_hint: str, source_roots: dict[str, set[str]]) -> list[str]:
    hint_norm = _normalize(repo_hint)
    if not hint_norm:
        return []
    scored: list[tuple[int, str]] = []
    for source_id, roots in source_roots.items():
        score = 0
        source_norm = _normalize(source_id)
        if source_norm == hint_norm:
            score += 100
        elif hint_norm in source_norm or source_norm in hint_norm:
            score += 50
        for root in roots:
            root_norm = _normalize(root)
            if root_norm == hint_norm:
                score += 90
            elif hint_norm in root_norm or root_norm in hint_norm:
                score += 40
        if score > 0:
            scored.append((score, source_id))
    return [source_id for _, source_id in sorted(scored, key=lambda item: (-item[0], item[1]))[:8]]


def _resolve_change_path(path: str, source_id: str, source_paths: dict[str, set[str]], source_roots: dict[str, set[str]]) -> str | None:
    normalized = str(path or "").replace("\\", "/").strip()
    if not normalized:
        return None
    candidates = source_paths.get(source_id) or set()
    if normalized in candidates:
        return normalized
    basename = normalized.rstrip("/").split("/")[-1]
    roots = source_roots.get(source_id) or set()
    for root in roots:
        suffix = f"/{root}/"
        if suffix in normalized:
            tail = normalized.split(suffix, 1)[1]
            candidate = f"{root}/{tail}"
            if candidate in candidates:
                return candidate
    direct_tail = None
    if basename and basename != normalized:
        parts = normalized.split("/")
        for i in range(len(parts)):
            tail = "/".join(parts[i:])
            if tail in candidates:
                return tail
            direct_tail = tail
    if basename:
        matches = sorted(candidate for candidate in candidates if candidate.endswith("/" + basename) or candidate == basename)
        if len(matches) == 1:
            return matches[0]
    return direct_tail if direct_tail in candidates else None


def resolve_session_episode_seeds_to_index(
    *,
    session_seed_candidates_path: Path,
    index_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seeds = _read_jsonl(session_seed_candidates_path)
    repo_index = _read_repo_index(index_dir)
    source_paths = repo_index["source_paths"]
    source_roots = repo_index["source_roots"]

    resolved_rows: list[dict[str, Any]] = []
    route_counts: Counter[str] = Counter()
    for row in seeds:
        repo_hint = str(row.get("repo_hint") or "")
        candidate_source_ids = _candidate_source_ids(repo_hint, source_roots)
        resolved_source_id = ""
        resolved_changes: list[dict[str, Any]] = []
        route = "UNRESOLVED"
        for source_id in candidate_source_ids:
            attempted_changes = []
            all_resolved = True
            for change in row.get("changes") or []:
                if not isinstance(change, dict):
                    continue
                original_path = str(change.get("path") or "")
                resolved_path = _resolve_change_path(original_path, source_id, source_paths, source_roots)
                if resolved_path is None:
                    all_resolved = False
                    break
                attempted_changes.append({"path": resolved_path})
            if all_resolved and attempted_changes:
                resolved_source_id = source_id
                resolved_changes = attempted_changes
                route = "RESOLVED_FULL"
                break
        if not resolved_source_id and candidate_source_ids:
            route = "CANDIDATE_SOURCE_ONLY"
        route_counts[route] += 1
        resolved_rows.append(
            {
                "seed_id": str(row.get("seed_id") or ""),
                "seed_type": "session_episode",
                "repo_hint": repo_hint,
                "repo_id": resolved_source_id,
                "candidate_repo_ids": candidate_source_ids,
                "goal": str(row.get("goal") or ""),
                "changes": resolved_changes,
                "metadata": {
                    **dict(row.get("metadata") or {}),
                    "resolution_route": route,
                    "original_changes": list(row.get("changes") or []),
                },
            }
        )

    summary = {
        "input_seed_count": len(seeds),
        "resolved_seed_count": sum(1 for row in resolved_rows if str(row.get("repo_id") or "") and list(row.get("changes") or [])),
        "candidate_only_seed_count": sum(1 for row in resolved_rows if not row.get("repo_id") and list((row.get("candidate_repo_ids") or []))),
        "route_counts": dict(sorted(route_counts.items())),
    }
    return resolved_rows, summary


def materialize_resolved_session_episode_seeds(
    *,
    session_seed_candidates_path: Path,
    index_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    rows, summary = resolve_session_episode_seeds_to_index(
        session_seed_candidates_path=session_seed_candidates_path,
        index_dir=index_dir,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "resolved_session_episode_seeds.jsonl", rows)
    write_json(output_dir / "resolved_session_episode_seed_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve session-derived episode seed candidates against the indexed repo corpus.")
    parser.add_argument("--session-seeds", type=Path, required=True)
    parser.add_argument("--index-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    materialize_resolved_session_episode_seeds(
        session_seed_candidates_path=args.session_seeds,
        index_dir=args.index_dir,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()

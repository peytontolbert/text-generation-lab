from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from long_context_common import write_json, write_jsonl


DEFAULT_ROOT_MAP_PATH = Path("runs/local/artifacts/session_like_source_inventory_real/session_repo_hint_root_map.json")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_root_map(path: Path) -> dict[str, Path]:
    payload = _read_json(path)
    mapping: dict[str, Path] = {}
    for row in payload.get("rows", []):
        hint = str(row.get("repo_hint") or "")
        root = str(row.get("local_repo_root") or "")
        if hint and root:
            mapping[hint] = Path(root)
    return mapping


def _resolve_change_paths(root: Path, original_changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    seen: set[str] = set()
    for change in original_changes:
        if not isinstance(change, dict):
            continue
        raw_path = str(change.get("path") or "")
        if not raw_path:
            continue
        path = Path(raw_path)
        candidates: list[Path] = []
        if path.is_absolute():
            candidates.append(path)
        else:
            candidates.append(root / raw_path)
            if len(path.parts) >= 2 and path.parts[0] == root.name:
                candidates.append(root / Path(*path.parts[1:]))
        for candidate in candidates:
            if candidate.exists():
                candidate_str = str(candidate)
                if candidate_str not in seen:
                    seen.add(candidate_str)
                    resolved.append({"path": candidate_str})
                break
    return resolved


def resolve_session_episode_seeds_to_local_roots(
    *,
    session_seed_candidates_path: Path,
    root_map_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _read_jsonl(session_seed_candidates_path)
    root_map = _load_root_map(root_map_path)
    resolved_rows: list[dict[str, Any]] = []
    route_counts: Counter[str] = Counter()

    for row in rows:
        repo_hint = str(row.get("repo_hint") or "")
        metadata = dict(row.get("metadata") or {})
        original_changes = list(metadata.get("original_changes") or row.get("changes") or [])
        root = root_map.get(repo_hint)
        if root is None or not root.exists():
            route = "NO_LOCAL_ROOT_MATCH"
            resolved_changes: list[dict[str, Any]] = []
        else:
            resolved_changes = _resolve_change_paths(root, original_changes)
            route = "LOCAL_ROOT_AND_PATHS" if resolved_changes else "LOCAL_ROOT_ONLY"
        route_counts[route] += 1
        resolved_rows.append(
            {
                "seed_id": str(row.get("seed_id") or ""),
                "seed_type": "session_episode_local_root",
                "source_root_label": str(row.get("source_root_label") or ""),
                "session_id_hint": str(row.get("session_id_hint") or ""),
                "repo_hint": repo_hint,
                "local_repo_root": str(root) if root else "",
                "goal": str(row.get("goal") or ""),
                "changes": resolved_changes,
                "metadata": {
                    **metadata,
                    "local_resolution_route": route,
                },
            }
        )

    summary = {
        "input_seed_count": len(rows),
        "resolved_local_root_count": sum(1 for row in resolved_rows if row.get("local_repo_root")),
        "resolved_local_change_count": sum(1 for row in resolved_rows if row.get("changes")),
        "route_counts": dict(sorted(route_counts.items())),
    }
    return resolved_rows, summary


def materialize_resolved_session_episode_seeds_to_local_roots(
    *,
    session_seed_candidates_path: Path,
    output_dir: Path,
    root_map_path: Path,
) -> dict[str, Any]:
    rows, summary = resolve_session_episode_seeds_to_local_roots(
        session_seed_candidates_path=session_seed_candidates_path,
        root_map_path=root_map_path,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "resolved_session_episode_seeds_local_roots.jsonl", rows)
    write_json(output_dir / "resolved_session_episode_seeds_local_roots_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve session-derived episode seeds to explicit local repo roots.")
    parser.add_argument("--session-seeds", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--root-map", type=Path, default=DEFAULT_ROOT_MAP_PATH)
    args = parser.parse_args()
    materialize_resolved_session_episode_seeds_to_local_roots(
        session_seed_candidates_path=args.session_seeds,
        output_dir=args.output_dir,
        root_map_path=args.root_map,
    )


if __name__ == "__main__":
    main()

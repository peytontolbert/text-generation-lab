from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from long_context_common import write_json


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_session_id_set(path: Path | None, field: str) -> set[str]:
    if path is None or not path.exists():
        return set()
    rows = _read_jsonl(path)
    session_ids: set[str] = set()
    for row in rows:
        value = str(row.get(field) or "")
        if value:
            session_ids.add(value)
    return session_ids


def _load_summary_by_session(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    rows = _read_jsonl(path)
    summary_by_session: dict[str, dict[str, Any]] = {}
    for row in rows:
        session_id = str(row.get("session_id_hint") or "")
        if session_id:
            summary_by_session[session_id] = row
    return summary_by_session


def _repo_hint_matches(summary: dict[str, Any], allowed_repo_hints: set[str]) -> bool:
    if not allowed_repo_hints:
        return True
    repo_hints = {str(key) for key in dict(summary.get("repo_hints") or {}).keys() if str(key)}
    return bool(repo_hints & allowed_repo_hints)


def build_aligned_session_parser_ticket(
    *,
    source_root_label: str,
    root_path: Path,
    counts_by_root_path: Path | None = None,
    extension: str = ".jsonl",
    max_files: int = 64,
    session_ids_jsonl_path: Path | None = None,
    session_id_field: str = "session_id_hint",
    require_session_ids: bool = False,
    session_summaries_path: Path | None = None,
    allowed_repo_hints: set[str] | None = None,
    require_repo_hint_match: bool = False,
) -> dict[str, Any]:
    if max_files <= 0:
        raise ValueError("max_files_must_be_positive")
    if not root_path.exists():
        raise FileNotFoundError(f"missing_root_path:{root_path}")

    counts_by_root = _read_json(counts_by_root_path) if counts_by_root_path and counts_by_root_path.exists() else {}
    root_counts = dict(counts_by_root.get(source_root_label) or {})
    preferred_session_ids = _load_session_id_set(session_ids_jsonl_path, session_id_field)
    summary_by_session = _load_summary_by_session(session_summaries_path)
    allowed_repo_hints = set(allowed_repo_hints or set())

    candidates: list[dict[str, Any]] = []
    for path in root_path.rglob(f"*{extension}"):
        if not path.is_file():
            continue
        relative_path = str(path.relative_to(root_path))
        session_id_hint = path.stem
        summary = summary_by_session.get(session_id_hint, {})
        preferred = session_id_hint in preferred_session_ids if preferred_session_ids else False
        repo_hint_match = _repo_hint_matches(summary, allowed_repo_hints)
        if require_session_ids and preferred_session_ids and not preferred:
            continue
        if require_repo_hint_match and not repo_hint_match:
            continue
        candidates.append(
            {
                "path": path,
                "relative_path": relative_path,
                "session_id_hint": session_id_hint,
                "mtime_ns": path.stat().st_mtime_ns,
                "preferred": preferred,
                "repo_hint_match": repo_hint_match,
                "event_count": int(summary.get("event_count") or 0),
                "repo_hints": sorted(str(key) for key in dict(summary.get("repo_hints") or {}).keys() if str(key)),
            }
        )

    if require_session_ids and preferred_session_ids and not candidates:
        raise ValueError("no_candidates_for_required_session_ids")

    candidates.sort(
        key=lambda row: (
            0 if row["preferred"] else 1,
            0 if row["repo_hint_match"] else 1,
            -int(row["mtime_ns"]),
            -int(row["event_count"]),
            str(row["relative_path"]),
        )
    )

    selected = candidates[:max_files]
    if not selected:
        raise ValueError("no_session_files_selected")

    selected_session_ids = [str(row["session_id_hint"]) for row in selected]
    selected_repo_hints = Counter(hint for row in selected for hint in row["repo_hints"])
    preferred_selected_count = sum(1 for row in selected if row["preferred"])
    repo_hint_selected_count = sum(1 for row in selected if row["repo_hint_match"])

    return {
        "metadata_only_inventory_complete": True,
        "raw_content_access_performed": False,
        "selection_strategy": "explicit_relative_paths_mtime_desc",
        "selection_summary": {
            "source_root_label": source_root_label,
            "root_path": str(root_path),
            "extension": extension,
            "candidate_count": len(candidates),
            "selected_count": len(selected),
            "preferred_session_id_count": len(preferred_session_ids),
            "preferred_selected_count": preferred_selected_count,
            "allowed_repo_hint_count": len(allowed_repo_hints),
            "repo_hint_selected_count": repo_hint_selected_count,
            "selected_repo_hints": dict(sorted(selected_repo_hints.items())),
            "selected_session_ids": selected_session_ids,
        },
        "parse_plan": [
            {
                "source_root_label": source_root_label,
                "root_path": str(root_path),
                "initial_file_cap": len(selected),
                "recommended_parse_mode": "jsonl_stream",
                "file_sort_mode": "mtime_desc",
                "explicit_relative_paths": [str(row["relative_path"]) for row in selected],
                "require_explicit_paths": True,
                "extension_plan": [
                    {
                        "extension": extension,
                        "file_cap": len(selected),
                        "parse_mode": "content_parser_candidate",
                        "priority_score": 1.0,
                    }
                ],
                "root_priority_score": float(root_counts.get("file_count") or 0),
            }
        ],
        "guardrails": {
            "parse_content_now": False,
            "emit_training_rows_now": False,
            "write_to_arxiv_now": False,
            "raw_session_payload_materialized_now": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an explicit-file aligned parser ticket for session JSONL parsing.")
    parser.add_argument("--source-root-label", default="codex_sessions")
    parser.add_argument("--root-path", type=Path, required=True)
    parser.add_argument("--counts-by-root", type=Path)
    parser.add_argument("--extension", default=".jsonl")
    parser.add_argument("--max-files", type=int, default=64)
    parser.add_argument("--session-ids-jsonl", type=Path)
    parser.add_argument("--session-id-field", default="session_id_hint")
    parser.add_argument("--require-session-ids", action="store_true")
    parser.add_argument("--session-summaries", type=Path)
    parser.add_argument("--repo-hint", action="append")
    parser.add_argument("--require-repo-hint-match", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_aligned_session_parser_ticket(
        source_root_label=args.source_root_label,
        root_path=args.root_path.expanduser(),
        counts_by_root_path=args.counts_by_root,
        extension=args.extension,
        max_files=args.max_files,
        session_ids_jsonl_path=args.session_ids_jsonl,
        session_id_field=args.session_id_field,
        require_session_ids=args.require_session_ids,
        session_summaries_path=args.session_summaries,
        allowed_repo_hints=set(args.repo_hint or []),
        require_repo_hint_match=args.require_repo_hint_match,
    )
    write_json(args.output, payload)


if __name__ == "__main__":
    main()

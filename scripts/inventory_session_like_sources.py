from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from long_context_common import write_json, write_jsonl


DEFAULT_ROOT_SPECS = [
    ("codex_sessions", "~/.codex/sessions"),
    ("cursor_chats", "~/.cursor/chats"),
    ("cursor_projects", "~/.cursor/projects"),
]


def _hash_relative_path(relative_path: str) -> str:
    return hashlib.sha1(relative_path.encode("utf-8")).hexdigest()


def _mtime_utc(stat_result: os.stat_result) -> str:
    return datetime.fromtimestamp(stat_result.st_mtime, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_root_specs(values: list[str] | None) -> list[tuple[str, Path]]:
    specs = values or [f"{label}={path}" for label, path in DEFAULT_ROOT_SPECS]
    roots: list[tuple[str, Path]] = []
    for spec in specs:
        if "=" not in spec:
            raise ValueError(f"invalid_root_spec:{spec}")
        label, raw_path = spec.split("=", 1)
        normalized_label = str(label).strip()
        if not normalized_label:
            raise ValueError(f"invalid_root_label:{spec}")
        roots.append((normalized_label, Path(raw_path).expanduser()))
    return roots


def inventory_session_like_sources(
    *,
    root_specs: list[tuple[str, Path]],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    relative_path_rows: list[dict[str, Any]] = []
    counts_by_root: dict[str, Any] = {}
    extension_counts: Counter[str] = Counter()
    total_files = 0
    total_bytes = 0

    for label, root in root_specs:
        exists = root.exists()
        root_counts: Counter[str] = Counter()
        root_bytes: Counter[str] = Counter()
        earliest_mtime: str | None = None
        latest_mtime: str | None = None
        files_seen = 0

        if exists:
            for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
                dirnames[:] = [name for name in dirnames if not Path(dirpath, name).is_symlink()]
                for filename in sorted(filenames):
                    path = Path(dirpath) / filename
                    if path.is_symlink():
                        continue
                    stat_result = path.stat()
                    relative_path = str(path.relative_to(root))
                    extension = path.suffix.lower() or "<no_ext>"
                    mtime = _mtime_utc(stat_result)
                    depth = len(Path(relative_path).parts)
                    relative_path_rows.append(
                        {
                            "source_root_label": label,
                            "source_root_exists": True,
                            "relative_path_hash": _hash_relative_path(relative_path),
                            "extension": extension,
                            "file_size_bytes": int(stat_result.st_size),
                            "mtime_utc": mtime,
                            "depth": depth,
                        }
                    )
                    root_counts[extension] += 1
                    root_bytes[extension] += int(stat_result.st_size)
                    extension_counts[extension] += 1
                    files_seen += 1
                    total_files += 1
                    total_bytes += int(stat_result.st_size)
                    earliest_mtime = mtime if earliest_mtime is None or mtime < earliest_mtime else earliest_mtime
                    latest_mtime = mtime if latest_mtime is None or mtime > latest_mtime else latest_mtime

        counts_by_root[label] = {
            "root_path": str(root),
            "root_exists": exists,
            "file_count": files_seen,
            "total_bytes": int(sum(root_bytes.values())),
            "extension_counts": dict(sorted(root_counts.items())),
            "total_bytes_by_extension": dict(sorted(root_bytes.items())),
            "mtime_range_utc": {"min": earliest_mtime, "max": latest_mtime},
        }

    root_card = {
        "root_count": len(root_specs),
        "roots_present": sum(int(counts_by_root[label]["root_exists"]) for label, _ in root_specs),
        "roots_missing": sum(int(not counts_by_root[label]["root_exists"]) for label, _ in root_specs),
        "total_files": total_files,
        "total_bytes": total_bytes,
        "source_root_labels": [label for label, _ in root_specs],
    }
    no_content_read_proof = {
        "file_content_read_now": False,
        "session_json_parsed_now": False,
        "message_body_hashed_now": False,
        "tool_output_content_read_now": False,
        "operations_used": ["path_exists", "os_walk_no_followlinks", "stat_only", "relative_path_hash_only"],
    }
    next_parser_ticket_input = {
        "source_root_labels": [label for label, _ in root_specs],
        "candidate_roots_present": [label for label, _ in root_specs if counts_by_root[label]["root_exists"]],
        "candidate_file_counts_by_root": {label: counts_by_root[label]["file_count"] for label, _ in root_specs},
        "largest_extensions": dict(extension_counts.most_common(16)),
        "metadata_only_inventory_complete": True,
        "raw_content_access_performed": False,
    }
    return (
        relative_path_rows,
        counts_by_root,
        {"extension_counts": dict(sorted(extension_counts.items()))},
        root_card,
        {"no_content_read_proof": no_content_read_proof, "next_parser_ticket_input": next_parser_ticket_input},
    )


def materialize_session_like_inventory(
    *,
    output_dir: Path,
    root_specs: list[tuple[str, Path]],
) -> dict[str, Any]:
    (
        relative_path_rows,
        counts_by_root,
        extension_counts,
        root_card,
        auxiliary,
    ) = inventory_session_like_sources(root_specs=root_specs)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "session_inventory_root_card.json", root_card)
    write_json(output_dir / "session_inventory_counts_by_root.json", counts_by_root)
    write_json(output_dir / "session_inventory_extension_counts.json", extension_counts)
    write_jsonl(output_dir / "session_inventory_relative_path_hashes.jsonl", relative_path_rows)
    write_json(output_dir / "no_content_read_proof.json", auxiliary["no_content_read_proof"])
    write_json(output_dir / "next_session_parser_ticket_input.json", auxiliary["next_parser_ticket_input"])
    return {
        "output_dir": str(output_dir),
        "root_card": root_card,
        "counts_by_root": counts_by_root,
        "extension_counts": extension_counts,
        **auxiliary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a metadata-only inventory for Codex/Cursor session-like sources without reading file contents.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--root",
        action="append",
        help="Root spec in the form label=/path/to/root. Can be repeated. Defaults to Codex and Cursor roots.",
    )
    args = parser.parse_args()
    materialize_session_like_inventory(
        output_dir=args.output_dir,
        root_specs=_parse_root_specs(args.root),
    )


if __name__ == "__main__":
    main()

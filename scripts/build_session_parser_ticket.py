from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from long_context_common import write_json


ROOT_TYPE_PRIORITIES = {
    "codex_sessions": 100.0,
    "cursor_projects": 80.0,
    "cursor_chats": 60.0,
}

EXTENSION_PRIORITIES = {
    ".jsonl": 100.0,
    ".json": 70.0,
    ".txt": 55.0,
    ".md": 35.0,
    ".log": 30.0,
    ".db": 20.0,
    ".ts": 10.0,
    ".tsx": 10.0,
    ".map": 1.0,
    ".png": 0.0,
    "<no_ext>": 0.0,
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _root_priority(label: str, counts: dict[str, Any]) -> float:
    base = ROOT_TYPE_PRIORITIES.get(label, 10.0)
    file_count = int(counts.get("file_count") or 0)
    total_bytes = int(counts.get("total_bytes") or 0)
    jsonl_files = int((counts.get("extension_counts") or {}).get(".jsonl", 0))
    return base + min(file_count / 100.0, 20.0) + min(total_bytes / 1_000_000_000.0, 10.0) + min(jsonl_files / 100.0, 10.0)


def _extension_priority(extension: str, file_count: int, total_bytes: int) -> float:
    base = EXTENSION_PRIORITIES.get(extension, 5.0)
    return base + min(file_count / 100.0, 10.0) + min(total_bytes / 100_000_000.0, 10.0)


def build_session_parser_ticket(
    *,
    counts_by_root_path: Path,
    parser_input_path: Path,
    max_initial_files: int = 256,
) -> dict[str, Any]:
    counts_by_root = _read_json(counts_by_root_path)
    parser_input = _read_json(parser_input_path)

    root_priority_rows: list[dict[str, Any]] = []
    extension_rows: list[dict[str, Any]] = []
    parse_plan: list[dict[str, Any]] = []

    for label in parser_input.get("candidate_roots_present", []):
        counts = counts_by_root.get(label) or {}
        root_priority_rows.append(
            {
                "source_root_label": label,
                "root_path": str(counts.get("root_path") or ""),
                "file_count": int(counts.get("file_count") or 0),
                "total_bytes": int(counts.get("total_bytes") or 0),
                "priority_score": round(_root_priority(label, counts), 3),
                "recommended_parse_mode": "jsonl_stream" if int((counts.get("extension_counts") or {}).get(".jsonl", 0)) > 0 else "schema_probe_only",
            }
        )
        for extension, file_count in sorted((counts.get("extension_counts") or {}).items()):
            total_bytes = int((counts.get("total_bytes_by_extension") or {}).get(extension, 0))
            extension_rows.append(
                {
                    "source_root_label": label,
                    "extension": extension,
                    "file_count": int(file_count),
                    "total_bytes": total_bytes,
                    "priority_score": round(_extension_priority(extension, int(file_count), total_bytes), 3),
                }
            )

    root_priority_rows.sort(key=lambda row: (-float(row["priority_score"]), row["source_root_label"]))
    extension_rows.sort(key=lambda row: (-float(row["priority_score"]), row["source_root_label"], row["extension"]))

    files_remaining = int(max_initial_files)
    for root_row in root_priority_rows:
        label = str(root_row["source_root_label"])
        root_extensions = [row for row in extension_rows if str(row["source_root_label"]) == label and float(row["priority_score"]) > 0.0]
        root_file_budget = min(files_remaining, max(16, min(int(root_row["file_count"]), max_initial_files // max(1, len(root_priority_rows)))))
        ext_plan: list[dict[str, Any]] = []
        ext_remaining = root_file_budget
        for ext_row in root_extensions:
            if ext_remaining <= 0:
                break
            ext_budget = min(ext_remaining, max(1, min(int(ext_row["file_count"]), root_file_budget // max(1, len(root_extensions)))))
            ext_plan.append(
                {
                    "extension": str(ext_row["extension"]),
                    "file_cap": int(ext_budget),
                    "priority_score": float(ext_row["priority_score"]),
                    "parse_mode": "content_parser_candidate" if str(ext_row["extension"]) in {".jsonl", ".json", ".txt", ".md"} else "schema_probe_only",
                }
            )
            ext_remaining -= ext_budget
        files_remaining -= min(root_file_budget, files_remaining)
        parse_plan.append(
            {
                "source_root_label": label,
                "root_path": str(root_row["root_path"]),
                "root_priority_score": float(root_row["priority_score"]),
                "initial_file_cap": int(root_file_budget),
                "recommended_parse_mode": str(root_row["recommended_parse_mode"]),
                "extension_plan": ext_plan,
            }
        )

    return {
        "metadata_only_inventory_complete": bool(parser_input.get("metadata_only_inventory_complete") is True),
        "raw_content_access_performed": bool(parser_input.get("raw_content_access_performed") is True),
        "max_initial_files": int(max_initial_files),
        "root_priorities": root_priority_rows,
        "extension_priorities": extension_rows,
        "parse_plan": parse_plan,
        "guardrails": {
            "parse_content_now": False,
            "emit_training_rows_now": False,
            "write_to_arxiv_now": False,
            "raw_session_payload_materialized_now": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a metadata-only parser ticket from a session-like source inventory.")
    parser.add_argument("--counts-by-root", type=Path, required=True)
    parser.add_argument("--parser-input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-initial-files", type=int, default=256)
    args = parser.parse_args()
    ticket = build_session_parser_ticket(
        counts_by_root_path=args.counts_by_root,
        parser_input_path=args.parser_input,
        max_initial_files=args.max_initial_files,
    )
    write_json(args.output, ticket)


if __name__ == "__main__":
    main()

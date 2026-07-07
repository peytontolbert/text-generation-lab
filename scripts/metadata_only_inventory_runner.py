#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
RUNS_LOCAL_ARTIFACTS = (ROOT / "runs/local/artifacts").resolve()
ARXIV_DATASETS = Path("/arxiv/datasets")
ARXIV_REPOSITORIES = Path("/arxiv/repositories")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Metadata-only /arxiv inventory runner.")
    parser.add_argument("--datasets-root", required=True)
    parser.add_argument("--repositories-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-depth", required=True, type=int)
    parser.add_argument("--metadata-only", action="store_true", required=True)
    parser.add_argument("--no-row-reads", action="store_true", required=True)
    parser.add_argument("--no-source-body-reads", action="store_true", required=True)
    parser.add_argument("--no-arxiv-writes", action="store_true", required=True)
    parser.add_argument("--no-follow-symlinks", action="store_true", required=True)
    parser.add_argument("--require-ticket-audit", required=True)
    return parser


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_args(args: argparse.Namespace) -> list[str]:
    failures: list[str] = []
    datasets_root = Path(args.datasets_root)
    repositories_root = Path(args.repositories_root)
    output_dir = Path(args.output_dir).resolve()
    ticket_audit = Path(args.require_ticket_audit)

    if datasets_root != ARXIV_DATASETS:
        failures.append("datasets_root_is_not_arxiv_datasets")
    if repositories_root != ARXIV_REPOSITORIES:
        failures.append("repositories_root_is_not_arxiv_repositories")
    if not is_relative_to(output_dir, RUNS_LOCAL_ARTIFACTS):
        failures.append("output_dir_not_under_runs_local_artifacts")
    if args.max_depth < 0 or args.max_depth > 4:
        failures.append("max_depth_out_of_bounds")
    for attr, failure in [
        ("metadata_only", "metadata_only_flag_required"),
        ("no_row_reads", "row_reads_not_disabled"),
        ("no_source_body_reads", "source_body_reads_not_disabled"),
        ("no_arxiv_writes", "arxiv_writes_not_disabled"),
        ("no_follow_symlinks", "symlink_follow_not_disabled"),
    ]:
        if getattr(args, attr) is not True:
            failures.append(failure)
    if not ticket_audit.exists():
        failures.append("ticket_audit_missing")
    else:
        try:
            audit = json.loads(ticket_audit.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            failures.append("ticket_audit_not_json")
        else:
            if audit.get("passed") is not True:
                failures.append("ticket_audit_not_passed")
    return failures


def iter_metadata(root: Path, max_depth: int) -> Iterable[dict[str, object]]:
    stack = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        if depth > max_depth:
            continue
        with os.scandir(current) as entries:
            for entry in entries:
                stat_result = entry.stat(follow_symlinks=False)
                path = Path(entry.path)
                kind = "symlink" if entry.is_symlink() else "dir" if entry.is_dir(follow_symlinks=False) else "file"
                yield {
                    "path": str(path),
                    "entry_name": entry.name,
                    "entry_kind": kind,
                    "extension": path.suffix,
                    "size_bytes": stat_result.st_size,
                    "mtime_epoch": stat_result.st_mtime,
                    "depth": depth,
                    "parent": str(path.parent),
                }
                if kind == "dir" and depth < max_depth:
                    stack.append((path, depth + 1))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    failures = validate_args(args)
    if failures:
        raise SystemExit("metadata_only_inventory_runner refused: " + ",".join(failures))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_out = output_dir / "dataset_file_inventory_metadata_only.jsonl"
    repo_out = output_dir / "repository_root_inventory_metadata_only.jsonl"
    with dataset_out.open("w", encoding="utf-8") as handle:
        for row in iter_metadata(Path(args.datasets_root), args.max_depth):
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    with repo_out.open("w", encoding="utf-8") as handle:
        for row in iter_metadata(Path(args.repositories_root), args.max_depth):
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps({"passed": True, "dataset_inventory": str(dataset_out), "repository_inventory": str(repo_out)}, sort_keys=True))


if __name__ == "__main__":
    main()

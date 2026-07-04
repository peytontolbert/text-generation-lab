#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any


def list_files(root: Path, *, exclude_manifests: bool = False) -> list[str]:
    files: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if exclude_manifests and path.name.startswith("_backup_manifest_"):
            continue
        files.append(path.relative_to(root).as_posix())
    return sorted(files)


def build_manifest(source: Path, destination: Path, *, method: str) -> dict[str, Any]:
    source_files = list_files(source)
    destination_files = list_files(destination, exclude_manifests=True)
    source_set = set(source_files)
    destination_set = set(destination_files)
    missing = sorted(source_set - destination_set)
    extra = sorted(destination_set - source_set)
    size_mismatches: list[dict[str, Any]] = []
    for rel in source_files:
        src_path = source / rel
        dst_path = destination / rel
        if not dst_path.exists():
            continue
        src_size = src_path.stat().st_size
        dst_size = dst_path.stat().st_size
        if src_size != dst_size:
            size_mismatches.append(
                {
                    "path": rel,
                    "source_bytes": src_size,
                    "destination_bytes": dst_size,
                    "delta": src_size - dst_size,
                }
            )
    return {
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": str(source),
        "destination": str(destination),
        "source_file_count": len(source_files),
        "destination_file_count": len(destination_files),
        "source_bytes": sum((source / rel).stat().st_size for rel in source_files),
        "destination_bytes": sum((destination / rel).stat().st_size for rel in destination_files),
        "missing_count": len(missing),
        "extra_count": len(extra),
        "size_mismatch_count": len(size_mismatches),
        "missing_sample": missing[:20],
        "extra_sample": extra[:20],
        "size_mismatch_sample": size_mismatches[:20],
        "method": method,
        "note": "Size mismatches can occur when Codex is actively appending to session logs during backup.",
    }


def write_manifest(destination: Path, manifest: dict[str, Any]) -> Path:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = destination / f"_backup_manifest_{stamp}.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Back up Codex session logs to /arxiv/code/sessions.")
    parser.add_argument("--source", type=Path, default=Path("/home/peyton/.codex/sessions"))
    parser.add_argument("--destination", type=Path, default=Path("/arxiv/code/sessions"))
    parser.add_argument("--append-verify", action="store_true", help="Use rsync --append-verify for growing logs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.source.is_dir():
        raise SystemExit(f"source does not exist or is not a directory: {args.source}")
    args.destination.mkdir(parents=True, exist_ok=True)
    command = ["rsync", "-a"]
    method = "rsync -a source/ destination/ without delete"
    if args.append_verify:
        command.append("--append-verify")
        method = "rsync -a --append-verify source/ destination/ without delete"
    command.extend([str(args.source) + "/", str(args.destination) + "/"])
    subprocess.run(command, check=True)
    manifest = build_manifest(args.source, args.destination, method=method)
    manifest_path = write_manifest(args.destination, manifest)
    print(json.dumps({**manifest, "manifest": str(manifest_path)}, indent=2, sort_keys=True))
    return 0 if manifest["missing_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())


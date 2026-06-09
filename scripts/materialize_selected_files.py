#!/usr/bin/env python3
"""Copy selected source files from an inventory into this lab repo.

Defaults are conservative: text/config/code files only, with a 50 MB per-file
limit, and no checkpoint/artifact directory copying. Use --execute to copy.
"""
from __future__ import annotations
import argparse, json, shutil
from pathlib import Path
DEFAULT_GROUPS = {"scripts", "docs", "tests", "data_files", "tmp_files", "examples", "model_stack", "wasm"}
DEFAULT_EXTS = {".py", ".sh", ".js", ".mjs", ".json", ".jsonl", ".txt", ".csv", ".md", ".yaml", ".yml", ".toml", ".rs", ".wgsl"}
def parse_csv(value: str | None, default: set[str]) -> set[str]:
    if not value: return set(default)
    return {item.strip() for item in value.split(",") if item.strip()}
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", default="manifests/current_environment.json")
    parser.add_argument("--source-root", default=None)
    parser.add_argument("--dest-root", default="legacy_src")
    parser.add_argument("--groups", default=None, help="Comma-separated inventory groups to copy")
    parser.add_argument("--include-ext", default=None, help="Comma-separated file extensions to include")
    parser.add_argument("--exclude-ext", default=".pyc,.pt,.safetensors,.bin,.onnx,.png,.jpg,.jpeg,.wav,.mp3,.npz,.f32,.i32,.wasm")
    parser.add_argument("--max-size-mb", type=float, default=50.0)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(Path(args.inventory).read_text())
    source_root = Path(args.source_root or manifest["source_root"]).resolve()
    dest_root = Path(args.dest_root)
    groups = parse_csv(args.groups, DEFAULT_GROUPS)
    include_ext = {e if e.startswith(".") else "." + e for e in parse_csv(args.include_ext, DEFAULT_EXTS)}
    exclude_ext = {e if e.startswith(".") else "." + e for e in parse_csv(args.exclude_ext, set())}
    max_bytes = int(args.max_size_mb * 1024 * 1024)
    copied = 0; skipped = 0; bytes_copied = 0
    for group, paths in manifest["selected_paths"].items():
        if group not in groups: continue
        for rel in paths:
            src = source_root / rel
            if not src.is_file(): skipped += 1; continue
            suffix = src.suffix.lower()
            if suffix in exclude_ext or suffix not in include_ext: skipped += 1; continue
            size = src.stat().st_size
            if size > max_bytes: skipped += 1; continue
            dst = dest_root / rel
            print(f"{'COPY' if args.execute else 'DRY'} {src} -> {dst}")
            if args.execute:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied += 1; bytes_copied += size
    print(json.dumps({"copied": copied, "skipped": skipped, "bytes_copied": bytes_copied, "mb_copied": round(bytes_copied/1024/1024, 3)}, indent=2))
if __name__ == "__main__": main()

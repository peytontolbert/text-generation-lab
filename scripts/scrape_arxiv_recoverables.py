#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Iterable


TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".jsonl",
    ".py",
    ".yaml",
    ".yml",
    ".toml",
    ".csv",
    ".rst",
}

KEYWORDS = [
    "agentkernel",
    "seq2seq",
    "100m",
    "software maintainer",
    "software-maintainer",
    "repo_state_graph",
    "bounded_decoder",
    "model_stack",
    "model_family_stack",
    "research_spine",
    "central_research_spine",
    "symbol_binding",
    "edit_localization",
    "patch_operator",
    "verifier_repair",
    "curriculum compiler",
    "dataset judge",
    "agentkernel_lite",
    "codegraph",
    "repo_graph",
    "program_graph",
]

SKIP_PARTS = {
    "sessions",
    "docker",
    "lost+found",
    "__pycache__",
    ".git",
}

DATASET_HINTS = [
    "swe",
    "code_x_glue",
    "codexglue",
    "opencode",
    "open-swe",
    "python",
    "repo",
    "trace",
    "instruct",
    "atlas",
]

ARCH_HINTS = [
    "tolbert_brain",
    "codegraph",
    "repo_graph",
    "program_graph",
    "train_tolbert",
    "joint_code",
    "spans",
    "nodes",
]


def sha256_file(path: Path, limit_bytes: int | None = None) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        if limit_bytes is None:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        else:
            remaining = limit_bytes
            while remaining > 0:
                chunk = f.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                h.update(chunk)
    return h.hexdigest()


def iter_files(roots: Iterable[Path], max_depth: int) -> Iterable[Path]:
    for root in roots:
        if not root.exists():
            continue
        root = root.resolve()
        for dirpath, dirnames, filenames in os.walk(root):
            current = Path(dirpath)
            parts_lower = {p.lower() for p in current.parts}
            if parts_lower & SKIP_PARTS:
                dirnames[:] = []
                continue
            depth = len(current.relative_to(root).parts)
            if depth >= max_depth:
                dirnames[:] = []
            dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_PARTS]
            for name in filenames:
                path = current / name
                if path.suffix.lower() in TEXT_SUFFIXES:
                    yield path


def read_probe(path: Path, max_bytes: int) -> str:
    try:
        with path.open("rb") as f:
            data = f.read(max_bytes)
    except OSError:
        return ""
    return data.decode("utf-8", errors="ignore")


def classify(path: Path, text: str) -> tuple[str, list[str]]:
    path_l = str(path).lower()
    text_l = text.lower()
    hits = [kw for kw in KEYWORDS if kw in path_l or kw in text_l]
    if any(x in path_l for x in ["agentkernel-seq2seq-text-lab", "agentkernel_lite", "bounded_decoder", "repo_state_graph"]):
        return "likely_direct_recovery", hits
    if any(h in path_l for h in ARCH_HINTS) or any(h in text_l for h in ARCH_HINTS):
        return "architecture_related", hits
    if "/datasets/" in path_l or any(h in path_l for h in DATASET_HINTS):
        return "dataset_source", hits
    if hits:
        return "keyword_related", hits
    return "unclassified", hits


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-depth", type=int, default=7)
    parser.add_argument("--probe-bytes", type=int, default=131072)
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        help="Root to scan. Can be repeated.",
    )
    args = parser.parse_args()

    roots = [Path(p) for p in args.root] or [
        Path("/arxiv/preserved_checkpoints_20260609"),
        Path("/arxiv/TOLBERT_BRAIN"),
        Path("/arxiv/datasets"),
        Path("/arxiv/repositories"),
        Path("/arxiv/models"),
        Path("/arxiv/code"),
    ]
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    counts: dict[str, int] = {}
    keyword_counts: dict[str, int] = {}
    root_counts: dict[str, int] = {}

    for path in iter_files(roots, args.max_depth):
        text = read_probe(path, args.probe_bytes)
        category, hits = classify(path, text)
        if category == "unclassified":
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        root_name = next((str(r) for r in roots if str(path).startswith(str(r))), "unknown")
        row = {
            "path": str(path),
            "category": category,
            "size_bytes": stat.st_size,
            "sha256_prefix_probe": sha256_file(path, args.probe_bytes),
            "keyword_hits": hits,
            "root": root_name,
        }
        rows.append(row)
        counts[category] = counts.get(category, 0) + 1
        root_counts[root_name] = root_counts.get(root_name, 0) + 1
        for hit in hits:
            keyword_counts[hit] = keyword_counts.get(hit, 0) + 1

    rows.sort(key=lambda r: (r["category"], r["path"]))

    candidates_path = out / "recoverable_candidates.jsonl"
    with candidates_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    summary = {
        "roots": [str(r) for r in roots],
        "max_depth": args.max_depth,
        "probe_bytes": args.probe_bytes,
        "candidate_rows": len(rows),
        "category_counts": dict(sorted(counts.items())),
        "root_counts": dict(sorted(root_counts.items())),
        "keyword_counts": dict(sorted(keyword_counts.items())),
        "top_candidates": rows[:50],
        "notes": [
            "This is a recovery index only; it does not authorize training, execution, scoring, or promotion.",
            "The Codex session backup is intentionally skipped as a scanned corpus because it is already backed up separately.",
        ],
    }
    (out / "recoverable_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

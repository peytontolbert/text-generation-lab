from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from long_context_common import (
    approx_token_count,
    chunk_text,
    extract_terms,
    iter_text_files,
    language_from_suffix,
    modality_from_suffix,
    safe_read_text,
    source_id_from_path,
    source_mix,
    source_type_from_path,
    stable_id,
    write_json,
    write_jsonl,
)


def chunk_row(
    *,
    source_root: Path,
    path: Path,
    chunk_index: int,
    text: str,
) -> dict[str, Any]:
    source_type = source_type_from_path(path, source_root=source_root)
    source_id = source_id_from_path(path, source_root=source_root)
    rel = str(path.relative_to(source_root))
    metadata = {
        "path": rel,
        "language": language_from_suffix(path),
        "section_name": None,
        "title": path.stem if source_type == "paper" else None,
        "symbol_names": [],
        "imports": [],
        "method_terms": extract_terms(text, max_terms=8),
        "benchmark_terms": [],
        "error_terms": [term for term in extract_terms(text, max_terms=12) if "error" in term or "fail" in term],
    }
    return {
        "chunk_id": stable_id(source_type, source_id, rel, str(chunk_index)),
        "source_type": source_type,
        "source_id": source_id,
        "doc_id": rel,
        "modality": modality_from_suffix(path),
        "token_count": approx_token_count(text),
        "text": text,
        "metadata": metadata,
    }


def build_chunk_catalog(
    *,
    paper_roots: list[Path],
    repo_roots: list[Path],
    dataset_roots: list[Path],
    paper_chunk_tokens: int = 1024,
    repo_chunk_tokens: int = 512,
    trace_chunk_tokens: int = 384,
    max_files_per_root: int = 1000,
    max_chars_per_file: int = 120_000,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    all_roots = [(root, "paper") for root in paper_roots] + [(root, "repo") for root in repo_roots] + [(root, "dataset") for root in dataset_roots]
    source_counts: Counter[str] = Counter()
    for root, declared_type in all_roots:
        if not root.exists():
            inventory.append({"root": str(root), "declared_type": declared_type, "exists": False, "files_scanned": 0})
            continue
        files = []
        for index, path in enumerate(iter_text_files(root)):
            if index >= max_files_per_root:
                break
            files.append(path)
        inventory.append({"root": str(root), "declared_type": declared_type, "exists": True, "files_scanned": len(files)})
        for path in files:
            raw = safe_read_text(path, max_chars=max_chars_per_file)
            if not raw.strip():
                continue
            budget = paper_chunk_tokens if declared_type == "paper" else repo_chunk_tokens if declared_type == "repo" else trace_chunk_tokens
            for chunk_index, text in enumerate(chunk_text(raw, max_tokens=budget), start=1):
                row = chunk_row(source_root=root, path=path, chunk_index=chunk_index, text=text)
                chunks.append(row)
                source_counts[row["source_type"]] += 1
    summary = {
        "chunk_count": len(chunks),
        "source_type_counts": dict(sorted(source_counts.items())),
        "source_mix": source_mix(chunks),
        "inventory": inventory,
    }
    return chunks, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build normalized long-context chunks from local paper/repo/dataset roots.")
    parser.add_argument("--papers-root", action="append", type=Path, default=[])
    parser.add_argument("--repos-root", action="append", type=Path, default=[])
    parser.add_argument("--datasets-root", action="append", type=Path, default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inventory-output", type=Path)
    parser.add_argument("--paper-chunk-tokens", type=int, default=1024)
    parser.add_argument("--repo-chunk-tokens", type=int, default=512)
    parser.add_argument("--trace-chunk-tokens", type=int, default=384)
    parser.add_argument("--max-files-per-root", type=int, default=1000)
    parser.add_argument("--max-chars-per-file", type=int, default=120000)
    args = parser.parse_args()
    rows, summary = build_chunk_catalog(
        paper_roots=args.papers_root,
        repo_roots=args.repos_root,
        dataset_roots=args.datasets_root,
        paper_chunk_tokens=args.paper_chunk_tokens,
        repo_chunk_tokens=args.repo_chunk_tokens,
        trace_chunk_tokens=args.trace_chunk_tokens,
        max_files_per_root=args.max_files_per_root,
        max_chars_per_file=args.max_chars_per_file,
    )
    write_jsonl(args.output, rows)
    write_json(args.inventory_output or args.output.with_name("source_inventory.json"), summary)


if __name__ == "__main__":
    main()

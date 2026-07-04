#!/usr/bin/env python3
"""Recover compact training/mining details from local Codex session logs.

This is read-only over ~/.codex/sessions. It writes compact recovery artifacts
inside the repo and never rewrites session files.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


TERM_GROUPS = {
    "semantic_presentation": [
        "semantic presentation",
        "semantic label",
        "semantic factorization",
        "SAFE",
        "UNSAFE",
        "RETRIEVE",
        "surface presentation",
        "target_shape",
        "surface_role",
        "repair_surface",
    ],
    "user_intent": [
        "user intent",
        "intent-to-build",
        "intent_to_build",
        "build strategy",
        "USE_WHITELIST_IMPORT",
        "BUILD_ON_TOP",
        "BUILD_FROM_SCRATCH",
        "allowed_import",
        "blocked_import",
        "file_plan",
    ],
    "mining": [
        "mine",
        "mining",
        "candidate miner",
        "residual miner",
        "external analog",
        "patch queue",
        "residual queue",
        "gap candidates",
        "neighbor miner",
    ],
    "curriculum_compiler": [
        "curriculum compiler",
        "canonical graph",
        "obligation graph",
        "mixed replay",
        "counterfactual sibling",
        "loss mask",
        "route rows",
        "compile manifest",
    ],
    "dataset_judge": [
        "dataset judge",
        "junk ranker",
        "quality gate",
        "shortcut audit",
        "baseline audit",
        "leak rows",
        "authority rows",
        "duplicate semantic",
    ],
    "training_telemetry": [
        "row_field_logits",
        "row_field_losses",
        "field_exact_by_split",
        "confusion_matrix",
        "gradient norm",
        "module_delta",
        "high-confidence wrong",
        "token loss",
        "eval_loss",
    ],
    "software_maintenance": [
        "repo_state_graph",
        "symbol binding",
        "edit localization",
        "patch operator",
        "verifier repair",
        "failure log",
        "test graph",
        "call graph",
        "import graph",
    ],
}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def extract_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(extract_text(item) for item in value)
    if isinstance(value, dict):
        parts = []
        for key in ("text", "content", "message", "output", "cmd"):
            if key in value:
                parts.append(extract_text(value[key]))
        if not parts:
            for item in value.values():
                text = extract_text(item)
                if text:
                    parts.append(text)
        return "\n".join(parts)
    return ""


def clean_snippet(text: str, needle: str, radius: int = 420) -> str:
    lower = text.lower()
    idx = lower.find(needle.lower())
    if idx < 0:
        idx = 0
    start = max(0, idx - radius)
    end = min(len(text), idx + len(needle) + radius)
    snippet = text[start:end]
    snippet = re.sub(r"\s+", " ", snippet).strip()
    return snippet[:1200]


def scan_file(path: Path, compiled: dict[str, list[tuple[str, re.Pattern[str]]]], max_snippets_per_group_file: int, max_bytes_per_file: int) -> tuple[Counter[str], list[dict[str, Any]]]:
    counts: Counter[str] = Counter()
    snippets: list[dict[str, Any]] = []
    per_group_snippets: Counter[str] = Counter()
    try:
        with path.open("rb") as f:
            raw = f.read(max_bytes_per_file)
        lines = raw.decode("utf-8", errors="ignore").splitlines()
    except OSError:
        return counts, snippets
    for line_no, line in enumerate(lines, start=1):
        if not line:
            continue
        lower = line.lower()
        for group, terms in compiled.items():
            matched_terms = []
            for term, pattern in terms:
                if pattern.search(lower):
                    counts[group] += 1
                    matched_terms.append(term)
            if matched_terms and per_group_snippets[group] < max_snippets_per_group_file:
                per_group_snippets[group] += 1
                snippets.append(
                    {
                        "session_file": str(path),
                        "line": line_no,
                        "group": group,
                        "matched_terms": sorted(set(matched_terms)),
                        "snippet": clean_snippet(line, matched_terms[0]),
                    }
                )
    return counts, snippets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-root", default="/home/peyton/.codex/sessions")
    parser.add_argument("--output-dir", default="runs/local/artifacts/stage8613_codex_session_training_detail_recovery")
    parser.add_argument("--max-files", type=int, default=1200)
    parser.add_argument("--max-snippets-per-group-file", type=int, default=2)
    parser.add_argument("--max-bytes-per-file", type=int, default=2000000)
    args = parser.parse_args()

    root = Path(args.sessions_root)
    out = Path(args.output_dir)
    compiled = {
        group: [(term, re.compile(re.escape(term.lower()))) for term in terms]
        for group, terms in TERM_GROUPS.items()
    }
    files = sorted(root.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[: args.max_files]
    total_counts: Counter[str] = Counter()
    file_counts = []
    snippets: list[dict[str, Any]] = []
    for path in files:
        counts, file_snips = scan_file(path, compiled, args.max_snippets_per_group_file, args.max_bytes_per_file)
        if counts:
            total_counts.update(counts)
            file_counts.append({"path": str(path), "counts": dict(counts), "size_bytes": path.stat().st_size})
            snippets.extend(file_snips)

    # Keep the most useful snippets: latest files first, capped per group globally.
    capped_snippets = []
    group_seen: Counter[str] = Counter()
    for item in snippets:
        if group_seen[item["group"]] < 80:
            capped_snippets.append(item)
            group_seen[item["group"]] += 1

    summary = {
        "sessions_root": str(root),
        "files_scanned": len(files),
        "files_with_hits": len(file_counts),
        "term_group_counts": dict(total_counts),
        "snippet_counts": dict(group_seen),
        "top_files_by_hits": sorted(
            file_counts,
            key=lambda row: sum(row["counts"].values()),
            reverse=True,
        )[:50],
        "recovered_groups": sorted([group for group, count in total_counts.items() if count > 0]),
    }
    write_json(out / "session_recovery_summary.json", summary)
    write_jsonl(out / "session_recovery_snippets.jsonl", capped_snippets)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

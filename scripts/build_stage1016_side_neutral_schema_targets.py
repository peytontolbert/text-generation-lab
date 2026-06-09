#!/usr/bin/env python3
"""Build a no-pair-anchor surface with side-neutral entity_/slot_ schema markers."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REPLACEMENTS = [
    (re.compile(r"\bqent_([A-Za-z0-9]+)\b"), r"entity_\1"),
    (re.compile(r"\bdent_([A-Za-z0-9]+)\b"), r"entity_\1"),
    (re.compile(r"\bqslot_([A-Za-z0-9]+)\b"), r"slot_\1"),
    (re.compile(r"\bdslot_([A-Za-z0-9]+)\b"), r"slot_\1"),
]


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _rewrite(text: str) -> tuple[str, int]:
    total = 0
    text = str(text)
    for pattern, repl in REPLACEMENTS:
        text, count = pattern.subn(repl, text)
        total += count
    return text, total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-jsonl", type=Path, default=Path("runs/local/artifacts/stage1013_no_anchor_targets.jsonl"))
    parser.add_argument("--output-jsonl", type=Path, default=Path("runs/local/artifacts/stage1016_side_neutral_schema_targets.jsonl"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage1016_side_neutral_schema_targets_summary.json"))
    args = parser.parse_args()

    rows = candidates = query_replacements = doc_replacements = 0
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as out:
        for row in _iter_jsonl(args.input_jsonl):
            row["query_text"], count = _rewrite(row.get("query_text", ""))
            query_replacements += count
            row["stage1016_surface"] = {
                "side_neutral_schema_markers": ["entity_", "slot_"],
                "removed_side_specific_schema_markers": ["qent_", "dent_", "qslot_", "dslot_"],
            }
            for candidate in list(row.get("candidates", []) or []):
                candidate["doc_text"], count = _rewrite(candidate.get("doc_text", ""))
                doc_replacements += count
                candidates += 1
            out.write(json.dumps(row, sort_keys=True) + "\n")
            rows += 1

    summary = {
        "artifact_kind": "stage1016_side_neutral_schema_targets",
        "status": "completed_side_neutral_schema_target_export",
        "input_jsonl": str(args.input_jsonl),
        "output_jsonl": str(args.output_jsonl),
        "rows": rows,
        "candidates": candidates,
        "query_marker_replacements": query_replacements,
        "doc_marker_replacements": doc_replacements,
        "decision": "Pair anchors remain removed; side-specific entity/slot markers are replaced with side-neutral schema markers.",
    }
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

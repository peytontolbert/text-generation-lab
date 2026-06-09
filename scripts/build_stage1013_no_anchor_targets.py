#!/usr/bin/env python3
"""Build a rendered-text target file with explicit pair anchor tokens removed."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ANCHOR_TOKEN = re.compile(r"\banchor_[A-Za-z0-9]+\b")
ANCHOR_FIELD = re.compile(r"\s*latent_shared_anchors=(?:\s*anchor_[A-Za-z0-9]+)*")
SPACES = re.compile(r"\s+")


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _remove_anchors(text: str) -> tuple[str, int]:
    text = str(text)
    count = len(ANCHOR_TOKEN.findall(text))
    text = ANCHOR_FIELD.sub("", text)
    text = ANCHOR_TOKEN.sub("", text)
    text = SPACES.sub(" ", text).strip()
    return text, count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-jsonl", type=Path, default=Path("runs/local/artifacts/stage1008_naturalized_pair_anchor_targets.jsonl"))
    parser.add_argument("--output-jsonl", type=Path, default=Path("runs/local/artifacts/stage1013_no_anchor_targets.jsonl"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage1013_no_anchor_targets_summary.json"))
    args = parser.parse_args()

    rows = 0
    candidates = 0
    query_anchors_removed = 0
    doc_anchors_removed = 0
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as out:
        for row in _iter_jsonl(args.input_jsonl):
            row["query_text"], removed = _remove_anchors(row.get("query_text", ""))
            query_anchors_removed += removed
            row["stage1013_surface"] = {
                "removed_rendered_pair_anchor_tokens": True,
                "structured_bridge_fields_retained_for_audit_only": True,
            }
            for candidate in list(row.get("candidates", []) or []):
                candidate["doc_text"], removed = _remove_anchors(candidate.get("doc_text", ""))
                doc_anchors_removed += removed
                candidates += 1
            out.write(json.dumps(row, sort_keys=True) + "\n")
            rows += 1

    summary = {
        "artifact_kind": "stage1013_no_anchor_targets",
        "status": "completed_no_anchor_target_export",
        "input_jsonl": str(args.input_jsonl),
        "output_jsonl": str(args.output_jsonl),
        "rows": rows,
        "candidates": candidates,
        "query_anchors_removed": query_anchors_removed,
        "doc_anchors_removed": doc_anchors_removed,
        "decision": "Explicit rendered pair anchor tokens are removed from query/doc text. Structured bridge fields remain only for audit compatibility and should not be used by no-anchor eval.",
    }
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

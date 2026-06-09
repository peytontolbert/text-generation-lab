#!/usr/bin/env python3
"""Build a text-only naturalized pair-anchor target file.

The transformation removes side-specific qpair_/dpair_ rendered markers from
query/doc text and replaces both with side-neutral anchor_ markers. Structured
bridge fields are left in the JSON for audit compatibility, but downstream
naturalized runs use rendered-text regex extraction only.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


QPAIR = re.compile(r"\bqpair_([A-Za-z0-9]+)\b")
DPAIR = re.compile(r"\bdpair_([A-Za-z0-9]+)\b")


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _naturalize_text(text: str) -> str:
    text = QPAIR.sub(r"anchor_\1", str(text))
    text = DPAIR.sub(r"anchor_\1", text)
    text = text.replace("latent_query_bridge=", "latent_shared_anchors=")
    text = text.replace("latent_doc_bridge=", "latent_shared_anchors=")
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-jsonl", type=Path, default=Path("runs/local/artifacts/stage975_pair_overlap_teacher_targets.jsonl"))
    parser.add_argument("--output-jsonl", type=Path, default=Path("runs/local/artifacts/stage1008_naturalized_pair_anchor_targets.jsonl"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage1008_naturalized_pair_anchor_targets_summary.json"))
    args = parser.parse_args()

    rows = 0
    candidates = 0
    query_replacements = 0
    doc_replacements = 0
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as out:
        for row in _iter_jsonl(args.input_jsonl):
            old_query = str(row.get("query_text", "") or "")
            query_replacements += len(QPAIR.findall(old_query))
            row["query_text"] = _naturalize_text(old_query)
            row["stage1008_surface"] = {
                "pair_marker": "anchor_",
                "removed_rendered_markers": ["qpair_", "dpair_"],
                "structured_bridge_fields_retained_for_audit_only": True,
            }
            for candidate in list(row.get("candidates", []) or []):
                old_doc = str(candidate.get("doc_text", "") or "")
                doc_replacements += len(DPAIR.findall(old_doc))
                candidate["doc_text"] = _naturalize_text(old_doc)
                candidates += 1
            out.write(json.dumps(row, sort_keys=True) + "\n")
            rows += 1

    summary = {
        "artifact_kind": "stage1008_naturalized_pair_anchor_targets",
        "status": "completed_naturalized_target_export",
        "input_jsonl": str(args.input_jsonl),
        "output_jsonl": str(args.output_jsonl),
        "rows": rows,
        "candidates": candidates,
        "query_pair_marker_replacements": query_replacements,
        "doc_pair_marker_replacements": doc_replacements,
        "decision": "Rendered qpair_/dpair_ markers are replaced by side-neutral anchor_ markers. This naturalizes side-specific marker text but still retains explicit anchor tokens.",
    }
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

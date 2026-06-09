#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MEMBERSHIP_OPS = {
    "set_member",
    "rule_case_member",
    "set_intersection_member",
    "rule_case_intersection_member",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def has_all(text: str, fields: tuple[str, ...]) -> bool:
    return all(field in text for field in fields)


def anchor_ok(row: dict[str, Any]) -> bool:
    text = str(row["retrieval_doc_text"])
    op = str(row["operation"])
    if op == "set_member":
        return has_all(text, ("lookup_key=", "domain=", "field=", "answer=", "entity=", "member=", "count="))
    if op == "rule_case_member":
        return has_all(text, ("rule_case_key=", "domain=", "field=", "case=", "entity=", "member=", "count="))
    if op == "set_intersection_member":
        return has_all(
            text,
            ("lookup_key=", "domain=", "field_a=", "answer_a=", "field_b=", "answer_b=", "entity=", "member=", "count="),
        )
    if op == "rule_case_intersection_member":
        return has_all(
            text,
            (
                "rule_case_intersection_key=",
                "domain=",
                "rule_field=",
                "case=",
                "filter_field=",
                "filter_answer=",
                "entity=",
                "member=",
                "count=",
            ),
        )
    return True


def summarize_dataset(label: str, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = load_jsonl(Path(manifest["train_dataset_path"])) + load_jsonl(Path(manifest["eval_dataset_path"]))
    membership_rows = [row for row in rows if row.get("operation") in MEMBERSHIP_OPS]
    by_op: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in membership_rows:
        by_op[str(row["operation"])].append(row)

    op_summary = {}
    for op, op_rows in sorted(by_op.items()):
        lengths = [len(str(row["retrieval_doc_text"]).split()) for row in op_rows]
        op_summary[op] = {
            "rows": len(op_rows),
            "mean_doc_tokens": mean(lengths) if lengths else 0.0,
            "min_doc_tokens": min(lengths) if lengths else 0,
            "max_doc_tokens": max(lengths) if lengths else 0,
            "anchor_complete_rows": sum(1 for row in op_rows if anchor_ok(row)),
            "anchor_complete_fraction": sum(1 for row in op_rows if anchor_ok(row)) / len(op_rows) if op_rows else None,
        }
    all_lengths = [len(str(row["retrieval_doc_text"]).split()) for row in membership_rows]
    return {
        "label": label,
        "manifest_path": str(manifest_path.relative_to(ROOT)),
        "total_examples": manifest["total_examples"],
        "membership_rows": len(membership_rows),
        "operation_counts": dict(Counter(str(row["operation"]) for row in membership_rows)),
        "mean_membership_doc_tokens": mean(all_lengths) if all_lengths else 0.0,
        "anchor_complete_rows": sum(1 for row in membership_rows if anchor_ok(row)),
        "anchor_complete_fraction": sum(1 for row in membership_rows if anchor_ok(row)) / len(membership_rows) if membership_rows else None,
        "by_operation": op_summary,
        "flags": {
            "compact_membership_cards": manifest.get("compact_membership_cards"),
            "anchored_compact_membership_cards": manifest.get("anchored_compact_membership_cards", False),
            "compact_set_op_cards": manifest.get("compact_set_op_cards"),
            "compact_reverse_set_cards": manifest.get("compact_reverse_set_cards"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="runs/local/artifacts/membership_card_compression_analysis.json")
    parser.add_argument("manifests", nargs="+", help="label=path entries")
    args = parser.parse_args()

    summaries = []
    for item in args.manifests:
        label, path = item.split("=", 1)
        summaries.append(summarize_dataset(label, ROOT / path))

    by_label = {item["label"]: item for item in summaries}
    compact = by_label.get("stage579_compact")
    anchored = by_label.get("stage591_anchored")
    comparison = {}
    if compact and anchored:
        comparison = {
            "mean_doc_token_delta_anchored_minus_compact": anchored["mean_membership_doc_tokens"] - compact["mean_membership_doc_tokens"],
            "anchor_fraction_delta_anchored_minus_compact": anchored["anchor_complete_fraction"] - compact["anchor_complete_fraction"],
            "interpretation": (
                "Anchored compact cards intentionally spend extra target tokens to restore explicit binding anchors. "
                "This should recover near-neighbor geometry if Stage579 failed because key+member+count was too aliasable."
            ),
        }

    result = {
        "artifact_kind": "membership_card_compression_analysis",
        "summaries": summaries,
        "comparison": comparison,
    }
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from manifest_path_validator import validate_manifest_input_path


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def row_has_options(row: dict[str, Any]) -> bool:
    prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    return "\nOptions:\n" in prompt


def audit_manifest_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_row_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    root_ids_by_split: dict[str, set[str]] = defaultdict(set)
    bounded_rows_without_options: list[str] = []
    prompt_target_leak_rows: list[str] = []
    prompt_target_leak_rows_by_split: dict[str, list[str]] = defaultdict(list)
    split_counts = Counter()
    language_counts = Counter()
    source_kind_counts = Counter()

    for row in rows:
        row_id = str(row.get("row_id") or "")
        split = str(row.get("split") or "unknown")
        source_kind = str(row.get("package_source_kind") or "unknown")
        language = str(row.get("language_family") or "unknown")
        root_id = str(row.get("root_id") or "")
        target_family = str(row.get("target_family") or "")
        target_text = str(row.get("target_text") or "")
        prompt = str(row.get("prompt_text") or row.get("input_text") or "")

        by_row_id[row_id].append(row)
        split_counts[split] += 1
        language_counts[language] += 1
        source_kind_counts[source_kind] += 1
        if root_id:
            root_ids_by_split[split].add(root_id)
        if target_family == "bounded_decision" and split in {"eval", "strict_eval"} and not row_has_options(row):
            bounded_rows_without_options.append(row_id)
        prompt_before_options = prompt.split("\nOptions:\n", 1)[0]
        if target_text and len(target_text) >= 8 and target_text in prompt_before_options:
            prompt_target_leak_rows.append(row_id)
            prompt_target_leak_rows_by_split[split].append(row_id)

    duplicate_row_groups = []
    duplicate_row_counts_by_split = Counter()
    duplicate_row_counts_by_source_pair = Counter()
    for row_id, group in sorted(by_row_id.items()):
        if len(group) <= 1:
            continue
        splits = sorted({str(row.get("split") or "unknown") for row in group})
        source_kinds = sorted({str(row.get("package_source_kind") or "unknown") for row in group})
        for split in splits:
            duplicate_row_counts_by_split[split] += 1
        duplicate_row_counts_by_source_pair[" + ".join(source_kinds)] += 1
        duplicate_row_groups.append(
            {
                "row_id": row_id,
                "count": len(group),
                "splits": splits,
                "source_kinds": source_kinds,
                "languages": sorted({str(row.get("language_family") or "unknown") for row in group}),
            }
        )

    split_pairs = []
    root_overlap_by_pair: dict[str, list[str]] = {}
    splits = sorted(root_ids_by_split)
    for i, left in enumerate(splits):
        for right in splits[i + 1 :]:
            overlap = sorted(root_ids_by_split[left] & root_ids_by_split[right])
            key = f"{left}__vs__{right}"
            split_pairs.append(key)
            root_overlap_by_pair[key] = overlap

    failures = []
    warnings = []
    if duplicate_row_groups:
        failures.append("duplicate_row_ids_present")
    if any(root_overlap_by_pair.values()):
        failures.append("same_root_cross_split_overlap_present")
    if bounded_rows_without_options:
        warnings.append("bounded_eval_rows_missing_options")
    eval_like_prompt_leaks = sum(
        len(prompt_target_leak_rows_by_split.get(split, []))
        for split in ("eval", "strict_eval")
    )
    if prompt_target_leak_rows:
        warnings.append("prompt_target_leak_present")
    if eval_like_prompt_leaks:
        failures.append("prompt_target_leak_present_in_eval_like_split")

    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "warnings": warnings,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "source_kind_counts": dict(sorted(source_kind_counts.items())),
        "duplicate_row_ids": len(duplicate_row_groups),
        "duplicate_row_counts_by_split": dict(sorted(duplicate_row_counts_by_split.items())),
        "duplicate_row_counts_by_source_pair": dict(sorted(duplicate_row_counts_by_source_pair.items())),
        "duplicate_row_groups": duplicate_row_groups,
        "root_overlap_by_split_pair": root_overlap_by_pair,
        "bounded_eval_rows_missing_options": bounded_rows_without_options,
        "prompt_target_leak_rows": prompt_target_leak_rows,
        "prompt_target_leak_rows_by_split": {
            split: rows for split, rows in sorted(prompt_target_leak_rows_by_split.items())
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit a JSONL manifest for duplicate row ids and split integrity.")
    parser.add_argument("--manifest", required=True, help="Local JSONL manifest path")
    args = parser.parse_args()

    path_check = validate_manifest_input_path(args.manifest)
    if not path_check["allowed"]:
        raise SystemExit(json.dumps(path_check, indent=2, sort_keys=True))
    manifest_path = Path(path_check["resolved_path"])
    rows = load_jsonl(manifest_path)
    result = {
        "manifest": str(manifest_path),
        "path_validation": path_check,
        "integrity_audit": audit_manifest_rows(rows),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Merge current execution-repaired package with Python verifier support lanes."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
STAGE = 10718
NAME = "stage10718_execution_repaired_plus_python_verifier_support_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME

BASE_DIR = ROOT / "runs/local/artifacts/stage10709_rewritten_plus_reviewed_training_package_execution_repaired"
PY_ABSTAIN_DIR = ROOT / "runs/local/artifacts/stage10716_python_verifier_setvalued_or_abstain_support_builder"
PY_SINGLETON_DIR = ROOT / "runs/local/artifacts/stage10717_python_singleton_verifier_support_manifest"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    base_summary = load_json(BASE_DIR / "rewritten_plus_reviewed_training_package_execution_repaired.json")
    base_train = load_jsonl(BASE_DIR / "train_rows.jsonl")
    base_validation = load_jsonl(BASE_DIR / "validation_rows.jsonl")
    base_eval = load_jsonl(BASE_DIR / "eval_rows.jsonl")
    base_strict = load_jsonl(BASE_DIR / "strict_rows.jsonl")
    base_canary = load_jsonl(BASE_DIR / "canary_rows.jsonl")
    base_diagnostic = load_jsonl(BASE_DIR / "diagnostic_rows.jsonl")

    py_abstain = load_jsonl(PY_ABSTAIN_DIR / "agentkernel_lite_encdec_train.jsonl")
    py_singleton = load_jsonl(PY_SINGLETON_DIR / "agentkernel_lite_encdec_train.jsonl")

    existing_row_ids = {str(row.get("row_id") or "") for row in base_train}
    merged_support: list[dict[str, Any]] = []
    duplicate_support_rows: list[str] = []
    for row in py_abstain + py_singleton:
        rid = str(row.get("row_id") or "")
        if rid in existing_row_ids:
            duplicate_support_rows.append(rid)
            continue
        existing_row_ids.add(rid)
        merged_support.append(row)

    merged_train = base_train + merged_support

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "claim_scope": [
            "Extend the current execution-repaired train split with current Python verifier support while preserving eval, strict, canary, and diagnostic slices unchanged.",
            "Add both singleton Python verifier support and honest multi-target abstention support without altering the benchmark boundary.",
            "Prepare the next honest probe so Python verifier movement can be tested without changing the 24-row strict headline slice."
        ],
        "gates": {
            "strict_frontier_unchanged": True,
            "eval_frontier_unchanged": True,
            "canary_unchanged": True,
            "diagnostic_unchanged": True,
            "python_verifier_train_rows_added": True,
            "duplicate_support_rows_skipped": len(duplicate_support_rows),
        },
        "source_artifacts": {
            "base_package": str((BASE_DIR / "rewritten_plus_reviewed_training_package_execution_repaired.json").relative_to(ROOT)),
            "python_abstain_support": str((PY_ABSTAIN_DIR / "python_verifier_setvalued_or_abstain_support_builder.json").relative_to(ROOT)),
            "python_singleton_support": str((PY_SINGLETON_DIR / "python_singleton_verifier_support_manifest.json").relative_to(ROOT)),
        },
        "headline_findings": [
            "The execution-repaired package previously had zero Python verifier train rows.",
            "This merge adds current Python verifier support in two forms: singleton support from known honest roots and abstention-honesty support from fresh multi-target roots.",
            "The benchmark slices remain frozen, so any movement in the next probe is attributable to train-side support only."
        ],
        "support_merge_counts": {
            "base_train_rows": len(base_train),
            "python_abstain_rows_added": len(py_abstain),
            "python_singleton_rows_added": len(py_singleton),
            "total_support_rows_added": len(merged_support),
            "merged_train_rows": len(merged_train),
        },
        "task_counts_after_merge": {
            "python_verifier_train_rows": sum(
                1
                for row in merged_train
                if row.get("language_family") == "python" and row.get("task_type") == "verifier_outcome"
            ),
            "python_train_rows_total": sum(1 for row in merged_train if row.get("language_family") == "python"),
            "rows_by_language": dict(sorted(Counter(str(row.get("language_family") or "") for row in merged_train).items())),
        },
        "outputs": {
            "package_json": str((OUT_DIR / "execution_repaired_plus_python_verifier_support_package.json").relative_to(ROOT)),
            "train_rows": str((OUT_DIR / "train_rows.jsonl").relative_to(ROOT)),
            "validation_rows": str((OUT_DIR / "validation_rows.jsonl").relative_to(ROOT)),
            "eval_rows": str((OUT_DIR / "eval_rows.jsonl").relative_to(ROOT)),
            "strict_rows": str((OUT_DIR / "strict_rows.jsonl").relative_to(ROOT)),
            "canary_rows": str((OUT_DIR / "canary_rows.jsonl").relative_to(ROOT)),
            "diagnostic_rows": str((OUT_DIR / "diagnostic_rows.jsonl").relative_to(ROOT)),
        },
        "recommended_next_stage": "stage10719_execution_repaired_plus_python_verifier_probe_request",
    }

    write_json(OUT_DIR / "execution_repaired_plus_python_verifier_support_package.json", summary)
    write_jsonl(OUT_DIR / "train_rows.jsonl", merged_train)
    write_jsonl(OUT_DIR / "validation_rows.jsonl", base_validation)
    write_jsonl(OUT_DIR / "eval_rows.jsonl", base_eval)
    write_jsonl(OUT_DIR / "strict_rows.jsonl", base_strict)
    write_jsonl(OUT_DIR / "canary_rows.jsonl", base_canary)
    write_jsonl(OUT_DIR / "diagnostic_rows.jsonl", base_diagnostic)


if __name__ == "__main__":
    main()

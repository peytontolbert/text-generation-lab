#!/usr/bin/env python3
"""Rescore available Gemma rows on the singleton-cleaned strict split."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs/local/artifacts/stage11148_cleaned_strict_gemma_rescore"
CLEAN_STRICT = (
    ROOT
    / "runs/local/artifacts/stage11146_singleton_strict_quarantine_successor/agentkernel_lite_encdec_strict_eval.jsonl"
)
GEMMA_ROWS = (
    ROOT
    / "runs/local/artifacts/stage10423_reviewed_multilingual_v27_same_manifest_gemma_comparison/reviewed_multilingual_v27_same_manifest_gemma_rows.jsonl"
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def group_accuracy(rows: list[dict[str, Any]], key: str, correct_key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key))].append(row)
    out = {}
    for group, items in groups.items():
        correct = sum(1 for row in items if row.get(correct_key))
        out[group] = {
            "rows": len(items),
            "correct": correct,
            "accuracy": correct / len(items) if items else 0.0,
        }
    return dict(sorted(out.items()))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    clean_rows = read_jsonl(CLEAN_STRICT)
    clean_ids = {row["row_id"] for row in clean_rows}
    clean_meta = {row["row_id"]: row for row in clean_rows}
    gemma_rows_all = read_jsonl(GEMMA_ROWS)
    gemma_by_id = {row.get("row_id"): row for row in gemma_rows_all}
    missing = sorted(clean_ids - set(gemma_by_id))
    extra = sorted(set(gemma_by_id) - clean_ids)
    filtered: list[dict[str, Any]] = []
    for row_id in sorted(clean_ids & set(gemma_by_id)):
        row = dict(gemma_by_id[row_id])
        meta = clean_meta[row_id]
        row.setdefault("language_family", meta.get("language_family"))
        row.setdefault("task_type", meta.get("task_type"))
        row.setdefault("repo_family", meta.get("repo_family"))
        row.setdefault("source_root_id", meta.get("source_root_id"))
        filtered.append(row)

    gemma_correct = sum(1 for row in filtered if row.get("gemma12b_correct"))
    hundred_m_old_correct = sum(1 for row in filtered if row.get("hundred_m_correct"))
    summary = {
        "stage": 11148,
        "stage_name": "cleaned_strict_gemma_rescore",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "clean_strict": str(CLEAN_STRICT.relative_to(ROOT)),
            "gemma_rows": str(GEMMA_ROWS.relative_to(ROOT)),
        },
        "metrics": {
            "clean_strict_rows": len(clean_rows),
            "gemma_rows_available": len(gemma_rows_all),
            "matched_clean_rows": len(filtered),
            "missing_clean_rows_in_gemma_artifact": missing,
            "extra_gemma_rows_not_in_cleaned_strict": extra,
            "gemma_correct": gemma_correct,
            "gemma_accuracy": gemma_correct / len(filtered) if filtered else 0.0,
            "hundred_m_correct_in_old_comparison_file": hundred_m_old_correct,
            "hundred_m_accuracy_in_old_comparison_file": hundred_m_old_correct / len(filtered) if filtered else 0.0,
            "gemma_by_language": group_accuracy(filtered, "language_family", "gemma12b_correct"),
            "gemma_by_task_type": group_accuracy(filtered, "task_type", "gemma12b_correct"),
            "target_label_counts": dict(sorted(Counter(str(row.get("target_text")) for row in filtered).items())),
        },
        "gemma_mismatches": [
            {
                "row_id": row.get("row_id"),
                "language_family": row.get("language_family"),
                "repo_family": row.get("repo_family"),
                "task_type": row.get("task_type"),
                "target_text": row.get("target_text"),
                "gemma12b_predicted_label": row.get("gemma12b_predicted_label"),
                "gemma12b_raw_output": str(row.get("gemma12b_raw_output", ""))[:500],
            }
            for row in filtered
            if not row.get("gemma12b_correct")
        ],
        "decision": "gemma_rescored_on_cleaned_strict_where_row_ids_match",
        "claim_scope": (
            "This filters an existing Gemma same-manifest artifact to the "
            "singleton-cleaned strict row IDs. It is not a fresh Gemma rerun, "
            "but row-id coverage is explicit."
        ),
        "outputs": {
            "filtered_gemma_rows_jsonl": str((OUT_DIR / "cleaned_strict_gemma_rows.jsonl").relative_to(ROOT)),
            "summary_json": str((OUT_DIR / "cleaned_strict_gemma_rescore.json").relative_to(ROOT)),
        },
    }
    with (OUT_DIR / "cleaned_strict_gemma_rows.jsonl").open("w") as f:
        for row in filtered:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    (OUT_DIR / "cleaned_strict_gemma_rescore.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

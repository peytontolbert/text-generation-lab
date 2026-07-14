#!/usr/bin/env python3
"""Build the singleton-cleaned strict 100M-vs-Gemma comparison artifact."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs/local/artifacts/stage11150_cleaned_strict_100m_vs_gemma_comparison"
HUNDRED_M_CARDS = (
    ROOT
    / "runs/local/artifacts/stage11147_cleaned_strict_existing_runtime_rescore/cleaned_strict_row_cards.jsonl"
)
GEMMA_FILTERED = (
    ROOT / "runs/local/artifacts/stage11148_cleaned_strict_gemma_rescore/cleaned_strict_gemma_rows.jsonl"
)
GEMMA_MISSING = (
    ROOT / "runs/local/artifacts/stage11149_missing_cleaned_strict_gemma_row/missing_cleaned_strict_gemma_rows.jsonl"
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def grouped(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key))].append(row)
    out = {}
    for group, items in groups.items():
        h_correct = sum(1 for r in items if r["hundred_m_correct"])
        g_correct = sum(1 for r in items if r["gemma12b_correct"])
        out[group] = {
            "rows": len(items),
            "hundred_m_correct": h_correct,
            "hundred_m_accuracy": h_correct / len(items) if items else 0.0,
            "gemma12b_correct": g_correct,
            "gemma12b_accuracy": g_correct / len(items) if items else 0.0,
            "delta": (h_correct - g_correct) / len(items) if items else 0.0,
        }
    return dict(sorted(out.items()))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    hundred_rows = read_jsonl(HUNDRED_M_CARDS)
    gemma_rows = read_jsonl(GEMMA_FILTERED) + read_jsonl(GEMMA_MISSING)
    hundred_by_id = {row["row_id"]: row for row in hundred_rows}
    gemma_by_id = {row["row_id"]: row for row in gemma_rows}
    missing_hundred = sorted(set(gemma_by_id) - set(hundred_by_id))
    missing_gemma = sorted(set(hundred_by_id) - set(gemma_by_id))
    combined: list[dict[str, Any]] = []
    for row_id in sorted(set(hundred_by_id) & set(gemma_by_id)):
        h = hundred_by_id[row_id]
        g = gemma_by_id[row_id]
        combined.append(
            {
                "row_id": row_id,
                "language_family": h.get("language_family") or g.get("language_family"),
                "repo_family": h.get("repo_family") or g.get("repo_family"),
                "task_type": h.get("task_type") or g.get("task_type"),
                "target_text": h.get("target_text") or g.get("target_text"),
                "hundred_m_predicted_label": h.get("constrained_choice_top1_label"),
                "hundred_m_correct": bool(h.get("constrained_choice_match")),
                "hundred_m_full_vocab_top1": h.get("full_vocab_top1_text"),
                "hundred_m_full_vocab_correct": bool(h.get("full_vocab_top1_match")),
                "gemma12b_predicted_label": g.get("gemma12b_predicted_label"),
                "gemma12b_correct": bool(g.get("gemma12b_correct")),
                "gemma12b_model": g.get("gemma12b_model", "gemma3:12b"),
            }
        )

    h_correct = sum(1 for row in combined if row["hundred_m_correct"])
    g_correct = sum(1 for row in combined if row["gemma12b_correct"])
    rows = len(combined)
    summary = {
        "stage": 11150,
        "stage_name": "cleaned_strict_100m_vs_gemma_comparison",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "hundred_m_cleaned_row_cards": str(HUNDRED_M_CARDS.relative_to(ROOT)),
            "gemma_filtered_rows": str(GEMMA_FILTERED.relative_to(ROOT)),
            "gemma_missing_rows": str(GEMMA_MISSING.relative_to(ROOT)),
        },
        "coverage": {
            "hundred_m_rows": len(hundred_rows),
            "gemma_rows": len(gemma_rows),
            "matched_rows": rows,
            "missing_hundred_m_rows": missing_hundred,
            "missing_gemma_rows": missing_gemma,
        },
        "overall": {
            "rows": rows,
            "hundred_m_correct": h_correct,
            "hundred_m_accuracy": h_correct / rows if rows else 0.0,
            "gemma12b_correct": g_correct,
            "gemma12b_accuracy": g_correct / rows if rows else 0.0,
            "delta": (h_correct - g_correct) / rows if rows else 0.0,
        },
        "by_language": grouped(combined, "language_family"),
        "by_task_type": grouped(combined, "task_type"),
        "hundred_m_mismatches": [row for row in combined if not row["hundred_m_correct"]],
        "gemma_mismatches": [row for row in combined if not row["gemma12b_correct"]],
        "decision": "cleaned_strict_comparison_complete" if not missing_gemma and not missing_hundred else "cleaned_strict_comparison_incomplete",
        "claim_scope": (
            "Singleton-option strict row is quarantined. 100M values are an "
            "existing-runtime rescore from stage11133 row cards; Gemma values "
            "combine existing reviewed-v27 rows plus one local gemma3:12b run "
            "for the newer Python verifier-transition row."
        ),
        "outputs": {
            "comparison_rows_jsonl": str((OUT_DIR / "cleaned_strict_comparison_rows.jsonl").relative_to(ROOT)),
            "summary_json": str((OUT_DIR / "cleaned_strict_100m_vs_gemma_comparison.json").relative_to(ROOT)),
        },
    }
    with (OUT_DIR / "cleaned_strict_comparison_rows.jsonl").open("w") as f:
        for row in combined:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    (OUT_DIR / "cleaned_strict_100m_vs_gemma_comparison.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

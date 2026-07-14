#!/usr/bin/env python3
"""Quarantine singleton-option rows from strict bounded-choice evaluation.

Strict bounded-choice eval should measure discrimination.  Rows with fewer
than two options can be useful as guardrails, but they should not count in the
strict discrimination denominator.  This stage creates a cleaned successor
split from stage11131 without modifying the original artifacts.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT / "runs/local/artifacts/stage11131_evidence_item_support_package"
OUT_DIR = ROOT / "runs/local/artifacts/stage11146_singleton_strict_quarantine_successor"

SPLIT_NAMES = {
    "train": "agentkernel_lite_encdec_train.jsonl",
    "validation": "agentkernel_lite_encdec_validation.jsonl",
    "strict_eval": "agentkernel_lite_encdec_strict_eval.jsonl",
    "stress_eval": "agentkernel_lite_encdec_stress_eval.jsonl",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def option_count(row: dict[str, Any]) -> int:
    options = row.get("opaque_options")
    return len(options) if isinstance(options, list) else 0


def row_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "row_id": row.get("row_id"),
        "source_root_id": row.get("source_root_id"),
        "repo_id": row.get("repo_id"),
        "repo_family": row.get("repo_family"),
        "language_family": row.get("language_family"),
        "task_type": row.get("task_type"),
        "target_text": row.get("target_text"),
        "option_count": option_count(row),
        "opaque_options": row.get("opaque_options"),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    split_rows = {
        name: read_jsonl(BASE_DIR / filename) for name, filename in SPLIT_NAMES.items()
    }

    strict_rows = split_rows["strict_eval"]
    quarantined = [row for row in strict_rows if option_count(row) < 2]
    cleaned_strict = [row for row in strict_rows if option_count(row) >= 2]

    # Preserve original split files except strict_eval gets the cleaned successor.
    for split, rows in split_rows.items():
        out_rows = cleaned_strict if split == "strict_eval" else rows
        write_jsonl(OUT_DIR / SPLIT_NAMES[split], out_rows)
    write_jsonl(OUT_DIR / "quarantined_singleton_strict_rows.jsonl", quarantined)

    strict_by_lang = Counter(str(row.get("language_family")) for row in strict_rows)
    cleaned_by_lang = Counter(str(row.get("language_family")) for row in cleaned_strict)
    quarantine_by_lang = Counter(str(row.get("language_family")) for row in quarantined)
    quarantine_by_task = Counter(str(row.get("task_type")) for row in quarantined)

    summary = {
        "stage": 11146,
        "stage_name": "singleton_strict_quarantine_successor",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "base_package_dir": str(BASE_DIR.relative_to(ROOT)),
            "base_summary": str((BASE_DIR / "evidence_item_support_package.json").relative_to(ROOT)),
        },
        "metrics": {
            "train_rows": len(split_rows["train"]),
            "validation_rows": len(split_rows["validation"]),
            "stress_rows": len(split_rows["stress_eval"]),
            "strict_rows_before": len(strict_rows),
            "strict_rows_after": len(cleaned_strict),
            "strict_singleton_quarantined": len(quarantined),
            "strict_by_language_before": dict(sorted(strict_by_lang.items())),
            "strict_by_language_after": dict(sorted(cleaned_by_lang.items())),
            "quarantined_by_language": dict(sorted(quarantine_by_lang.items())),
            "quarantined_by_task": dict(sorted(quarantine_by_task.items())),
        },
        "quarantined_rows": [row_summary(row) for row in quarantined],
        "decision": (
            "strict_successor_ready_for_discrimination_eval"
            if quarantined
            else "no_singleton_rows_found"
        ),
        "claim_scope": (
            "This successor only fixes strict denominator hygiene. It is not a "
            "new model-capability result until the current 100M and Gemma are "
            "rerun or rescored on the cleaned strict split."
        ),
        "outputs": {
            "train_jsonl": str((OUT_DIR / SPLIT_NAMES["train"]).relative_to(ROOT)),
            "validation_jsonl": str((OUT_DIR / SPLIT_NAMES["validation"]).relative_to(ROOT)),
            "strict_jsonl": str((OUT_DIR / SPLIT_NAMES["strict_eval"]).relative_to(ROOT)),
            "stress_jsonl": str((OUT_DIR / SPLIT_NAMES["stress_eval"]).relative_to(ROOT)),
            "quarantined_jsonl": str((OUT_DIR / "quarantined_singleton_strict_rows.jsonl").relative_to(ROOT)),
            "summary_json": str((OUT_DIR / "singleton_strict_quarantine_successor.json").relative_to(ROOT)),
        },
    }
    (OUT_DIR / "singleton_strict_quarantine_successor.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

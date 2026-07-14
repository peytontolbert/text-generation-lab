#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10625
NAME = "stage10625_multilingual_deleaked_train_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "multilingual_deleaked_train_package.json"
MANIFEST_JSONL = OUT_DIR / "multilingual_deleaked_train_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage10622_multilingual_deduped_eval_package/multilingual_deduped_eval_manifest.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def prompt_target_leaks(row: dict[str, Any]) -> bool:
    prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    target = str(row.get("target_text") or "")
    if not target or len(target) < 8:
        return False
    prompt_before_options = prompt.split("\nOptions:\n", 1)[0]
    return target in prompt_before_options


def main() -> None:
    rows = load_jsonl(SOURCE_MANIFEST)
    kept_rows: list[dict[str, Any]] = []
    removed_rows: list[dict[str, Any]] = []

    for row in rows:
        split = str(row.get("split") or "unknown")
        if split == "train" and prompt_target_leaks(row):
            removed_rows.append(row)
        else:
            kept_rows.append(row)

    kept_rows.sort(key=lambda row: (str(row.get("split") or ""), str(row.get("row_id") or "")))
    write_jsonl(MANIFEST_JSONL, kept_rows)

    split_counts = Counter(str(row.get("split") or "unknown") for row in kept_rows)
    removed_split_counts = Counter(str(row.get("split") or "unknown") for row in removed_rows)
    removed_language_counts = Counter(str(row.get("language_family") or "unknown") for row in removed_rows)
    removed_subtype_counts = Counter(str(row.get("target_subtype") or "unknown") for row in removed_rows)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "train_side_prompt_leaks_removed_from_multilingual_package",
        "claim_scope": [
            "Build a de-leaked successor to stage10622 by removing train rows whose target text is visible in the prompt before any options block.",
            "Preserve eval and strict_eval rows unchanged.",
            "This is a training-surface cleanup successor, not a changed multilingual strict benchmark.",
        ],
        "source_manifest": display(SOURCE_MANIFEST),
        "manifest": display(MANIFEST_JSONL),
        "rows": len(kept_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "removed_rows": {
            "count": len(removed_rows),
            "split_counts": dict(sorted(removed_split_counts.items())),
            "language_counts": dict(sorted(removed_language_counts.items())),
            "target_subtype_counts": dict(sorted(removed_subtype_counts.items())),
            "sample_row_ids": [str(row.get("row_id") or "") for row in removed_rows[:32]],
        },
        "next_best_step": "Rerun the target_100m multilingual probe on this de-leaked package and compare against stage10623 to measure whether the honest strict score holds without train-side prompt leakage.",
    }
    write_json(PACKAGE_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "manifest": display(MANIFEST_JSONL),
            "rows": len(kept_rows),
            "train_rows": split_counts.get("train", 0),
        },
    )
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": True,
                "rows": len(kept_rows),
                "removed_rows": len(removed_rows),
                "train_rows": split_counts.get("train", 0),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

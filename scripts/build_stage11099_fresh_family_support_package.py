#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11099
NAME = "stage11099_fresh_family_support_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_family_support_package.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED_ROWS_JSONL = OUT_DIR / "added_fresh_family_support_rows.jsonl"

BASE_DIR = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence"
BASE_SUMMARY = BASE_DIR / "successor_residual_support_plus_priority_evidence.json"
BASE_TRAIN = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

SCOREABLE_ROWS = ARTIFACTS / "stage11097_fresh_family_materialized_rows" / "scoreable_support_rows.jsonl"
VERIFIER_ROWS = ARTIFACTS / "stage11097_fresh_family_materialized_rows" / "verifier_support_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "missing") for row in rows).items()))


def main() -> None:
    base_summary = load_json(BASE_SUMMARY)
    base_train = load_jsonl(BASE_TRAIN)
    validation_rows = load_jsonl(BASE_VALIDATION)
    strict_rows = load_jsonl(BASE_STRICT)
    stress_rows = load_jsonl(BASE_STRESS)
    added_rows = [*load_jsonl(SCOREABLE_ROWS), *load_jsonl(VERIFIER_ROWS)]

    existing_ids = {str(row.get("row_id") or "") for row in base_train}
    deduped_added_rows = [row for row in added_rows if str(row.get("row_id") or "") not in existing_ids]
    train_rows = [*base_train, *deduped_added_rows]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(deduped_added_rows),
        "decision": "fresh_family_support_package_ready",
        "claim_scope": [
            "Extend the latest clean support package with support-eligible fresh-family rows only.",
            "Keep validation, strict, and stress unchanged while adding new train-only retrieve/verifier supervision from the fresh families.",
        ],
        "metrics": {
            "train_rows_before": len(base_train),
            "train_rows_after": len(train_rows),
            "rows_added_total": len(deduped_added_rows),
            "added_by_language": count_by(deduped_added_rows, "language_family"),
            "added_by_task": count_by(deduped_added_rows, "task_type"),
            "added_by_repo_family": count_by(deduped_added_rows, "repo_family"),
            "validation_rows_unchanged": len(validation_rows),
            "strict_rows_unchanged": len(strict_rows),
            "stress_rows_unchanged": len(stress_rows),
        },
        "headline_findings": [
            "The fresh-family queue now contributes concrete train support without altering the current heldout surfaces.",
            "Only scoreable packet rows and verifier-transition support rows are merged; heuristic evidence rows remain outside train on purpose.",
            "This package is the right next training base if the goal is to widen root supply without contaminating the current strict overlay.",
        ],
        "limits": [
            "Evidence candidate rows are deliberately excluded until their heuristic golds are reviewed.",
            "Web remains support-only and not promotable from this package.",
        ],
        "next_best_step": "Use this package for the next bounded support probe while keeping the current heldout overlay and reviewed canary unchanged.",
        "source_artifacts": {
            "base_support_package": rel(BASE_SUMMARY),
            "scoreable_rows": rel(SCOREABLE_ROWS),
            "verifier_rows": rel(VERIFIER_ROWS),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_rows_jsonl": rel(TRAIN_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_JSONL),
            "strict_rows_jsonl": rel(STRICT_JSONL),
            "stress_rows_jsonl": rel(STRESS_JSONL),
            "added_rows_jsonl": rel(ADDED_ROWS_JSONL),
        },
        "base_snapshot": base_summary.get("metrics"),
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(VALIDATION_JSONL, validation_rows)
    write_jsonl(STRICT_JSONL, strict_rows)
    write_jsonl(STRESS_JSONL, stress_rows)
    write_jsonl(ADDED_ROWS_JSONL, deduped_added_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

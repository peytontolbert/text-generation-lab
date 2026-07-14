#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11065
NAME = "stage11065_singleton_eval_quarantine_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "singleton_eval_quarantine_package.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
QUARANTINED_ROWS_JSONL = OUT_DIR / "quarantined_singleton_eval_rows.jsonl"

BASE_DIR = ARTIFACTS / "stage11061_ready_lane_fresh_support_package"
BASE_SUMMARY = BASE_DIR / "ready_lane_fresh_support_package.json"
BASE_TRAIN = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
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


def option_count(row: dict[str, Any]) -> int:
    opaque = row.get("opaque_options")
    if isinstance(opaque, list):
        return len(opaque)
    labels = row.get("option_labels")
    if isinstance(labels, list):
        return len(labels)
    return 0


def quarantine_singletons(rows: list[dict[str, Any]], split_name: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for row in rows:
        if option_count(row) <= 1:
            updated = dict(row)
            updated["quarantine_stage"] = STAGE
            updated["quarantine_reason"] = "singleton_eval_options"
            updated["quarantine_split_origin"] = split_name
            anti_cheat = dict(updated.get("anti_cheat") or {})
            anti_cheat["singleton_eval_quarantined"] = True
            updated["anti_cheat"] = anti_cheat
            quarantined.append(updated)
            continue
        kept.append(row)
    return kept, quarantined


def main() -> None:
    base_summary = load_json(BASE_SUMMARY)
    train_rows = load_jsonl(BASE_TRAIN)
    validation_rows = load_jsonl(BASE_VALIDATION)
    strict_rows = load_jsonl(BASE_STRICT)
    stress_rows = load_jsonl(BASE_STRESS)

    cleaned_validation, quarantined_validation = quarantine_singletons(validation_rows, "eval")
    cleaned_strict, quarantined_strict = quarantine_singletons(strict_rows, "strict_eval")
    quarantined_rows = [*quarantined_validation, *quarantined_strict]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "singleton_eval_rows_quarantined",
        "claim_scope": [
            "Repair the promotable successor overlay by removing singleton-option evaluation rows that cannot measure discriminative maintainer judgment.",
            "Preserve train and stress surfaces unchanged so this package only narrows the heldout claim surface rather than retuning the task mix.",
        ],
        "source_artifacts": {
            "base_package_summary": rel(BASE_SUMMARY),
            "base_train_rows": rel(BASE_TRAIN),
            "base_validation_rows": rel(BASE_VALIDATION),
            "base_strict_rows": rel(BASE_STRICT),
            "base_stress_rows": rel(BASE_STRESS),
        },
        "metrics": {
            "train_rows": len(train_rows),
            "validation_rows_before": len(validation_rows),
            "validation_rows_after": len(cleaned_validation),
            "strict_rows_before": len(strict_rows),
            "strict_rows_after": len(cleaned_strict),
            "stress_rows": len(stress_rows),
            "quarantined_rows_total": len(quarantined_rows),
            "quarantined_rows_by_split": count_by(quarantined_rows, "quarantine_split_origin"),
            "quarantined_rows_by_language": count_by(quarantined_rows, "language_family"),
            "quarantined_rows_by_task": count_by(quarantined_rows, "task_type"),
            "quarantined_row_ids": [str(row.get("row_id") or "") for row in quarantined_rows],
            "base_support_package_metrics": base_summary.get("metrics"),
        },
        "findings": [
            "The stage11061 successor overlay still contained singleton verifier-outcome rows in both validation and strict, which inflated apparent answerability without testing choice discrimination.",
            "This package quarantines those singleton rows out of promotable eval while keeping the broader successor branch intact.",
            "The revised heldout surface is smaller but structurally cleaner and is a better target for the next probe or scorer audit.",
        ],
        "required_honesty_gates": [
            "Any score on this package must be reported against the reduced 22-row validation and 22-row strict surfaces, not compared naively to the older 23-row overlay.",
            "Quarantined singleton rows may still exist in historical artifacts for continuity, but they are no longer valid promotable heldout evidence.",
        ],
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_rows_jsonl": rel(TRAIN_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_JSONL),
            "strict_rows_jsonl": rel(STRICT_JSONL),
            "stress_rows_jsonl": rel(STRESS_JSONL),
            "quarantined_rows_jsonl": rel(QUARANTINED_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(VALIDATION_JSONL, cleaned_validation)
    write_jsonl(STRICT_JSONL, cleaned_strict)
    write_jsonl(STRESS_JSONL, stress_rows)
    write_jsonl(QUARANTINED_ROWS_JSONL, quarantined_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

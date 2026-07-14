#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10904
NAME = "stage10904_python_verifier_transition_support_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "python_verifier_transition_support_package.json"
TRAIN_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

BASE_DIR = ARTIFACTS / "stage10864_residual_family_support_package_plus_second_python_materialized"
BASE_SUMMARY = BASE_DIR / "residual_family_support_package_plus_second_python_materialized.json"
BASE_TRAIN = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"

CANDIDATE_DIR = ARTIFACTS / "stage10871_verifier_candidate_semantic_support_package"
CANDIDATE_ROWS = CANDIDATE_DIR / "added_verifier_candidate_rows.jsonl"

CANARY_DIR = ARTIFACTS / "stage10881_evidence_alias_quarantine_successor"
CANARY_VALIDATION = CANARY_DIR / "agentkernel_lite_encdec_validation.jsonl"
CANARY_STRICT = CANARY_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"

SUCCESSOR_DIR = ARTIFACTS / "stage10902_python_verifier_transition_candidate_slice"
SUCCESSOR_STRICT = SUCCESSOR_DIR / "strict_candidate_rows.jsonl"


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


def with_split(row: dict[str, Any], split: str) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = split
    return updated


def main() -> None:
    base_summary = load_json(BASE_SUMMARY)
    base_train = load_jsonl(BASE_TRAIN)
    candidate_rows = load_jsonl(CANDIDATE_ROWS)
    canary_validation = load_jsonl(CANARY_VALIDATION)
    canary_strict = load_jsonl(CANARY_STRICT)
    successor_strict = load_jsonl(SUCCESSOR_STRICT)

    python_base_rows = [
        with_split(row, "train")
        for row in base_train
        if row.get("language_family") == "python"
    ]
    python_candidate_rows = [
        with_split(row, "train")
        for row in candidate_rows
        if row.get("language_family") == "python"
    ]
    train_rows = python_base_rows + python_candidate_rows
    validation_rows = [with_split(row, "eval") for row in canary_validation]
    strict_rows = [with_split(row, "strict_eval") for row in successor_strict]
    stress_rows = [with_split(row, "stress_eval") for row in canary_strict]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(train_rows) and bool(validation_rows) and bool(strict_rows),
        "decision": "python_verifier_transition_support_package_ready",
        "claim_scope": [
            "Build a Python-only diagnostic support package aimed at the remaining verifier-transition boundary rather than another multilingual preservation mix.",
            "Use the cleaned 23-row quarantined reviewed-v2.7 validation set for regression tracking while reserving the fresh 2-row Python verifier-transition slice as the strict target.",
        ],
        "required_honesty_gates": [
            "Fresh verifier-transition slice remains strict-only and non-promotable.",
            "Quarantined 23-row canary remains untouched and is used only for regression tracking.",
            "All train rows remain train-support only, including derived verifier-candidate semantic rows.",
        ],
        "source_artifacts": {
            "base_summary": rel(BASE_SUMMARY),
            "base_train": rel(BASE_TRAIN),
            "candidate_rows": rel(CANDIDATE_ROWS),
            "canary_validation": rel(CANARY_VALIDATION),
            "canary_strict_stress": rel(CANARY_STRICT),
            "successor_strict": rel(SUCCESSOR_STRICT),
        },
        "metrics": {
            "train_rows": len(train_rows),
            "validation_rows": len(validation_rows),
            "strict_rows": len(strict_rows),
            "stress_rows": len(stress_rows),
            "train_by_task": dict(sorted(Counter(str(row.get("task_type") or "unknown") for row in train_rows).items())),
            "train_by_target": dict(sorted(Counter(str(row.get("target_text") or "unknown") for row in train_rows).items())),
            "train_roots": len({row.get("source_root_id") or row.get("root_id") or row.get("source_bundle_id") or row.get("row_id") for row in train_rows}),
            "base_python_rows": len(python_base_rows),
            "derived_candidate_rows": len(python_candidate_rows),
            "base_metrics_snapshot": base_summary.get("metrics"),
        },
        "diagnostic_focus": {
            "primary": "python_verifier_outcome_semantic_transition",
            "strict_row_ids": [row.get("row_id") for row in strict_rows],
            "strict_source_roots": [row.get("source_root_id") for row in strict_rows],
            "canary_validation_rows": len(validation_rows),
            "canary_stress_rows": len(stress_rows),
        },
        "next_best_step": "Run a Python-only diagnostic probe from the current alias-safe runtime, then compare whether the stronger stage10894 verifier-transition row flips without regressing the quarantined canary.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_rows_jsonl": rel(TRAIN_ROWS_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_ROWS_JSONL),
            "strict_rows_jsonl": rel(STRICT_ROWS_JSONL),
            "stress_rows_jsonl": rel(STRESS_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, payload)
    write_jsonl(TRAIN_ROWS_JSONL, train_rows)
    write_jsonl(VALIDATION_ROWS_JSONL, validation_rows)
    write_jsonl(STRICT_ROWS_JSONL, strict_rows)
    write_jsonl(STRESS_ROWS_JSONL, stress_rows)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

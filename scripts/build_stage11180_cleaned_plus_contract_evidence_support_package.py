#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11180
NAME = "stage11180_cleaned_plus_contract_evidence_support_package"
OUT_DIR = ARTIFACTS / NAME

BASE_DIR = ARTIFACTS / "stage11168_cleaned_plus_external_fail_to_pass_support_package"
BASE_SUMMARY = BASE_DIR / "cleaned_plus_external_fail_to_pass_support_package.json"
BASE_TRAIN = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

ADMISSION_DIR = ARTIFACTS / "stage11179_contract_aware_evidence_admission_audit"
ADMISSION_SUMMARY = ADMISSION_DIR / "contract_aware_evidence_admission_audit.json"
ADMITTED_ROWS = ARTIFACTS / "stage11178_contract_aware_evidence_rows/contract_aware_evidence_rows.jsonl"

SUMMARY_JSON = OUT_DIR / "cleaned_plus_contract_evidence_support_package.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED_JSONL = OUT_DIR / "added_contract_aware_evidence_rows.jsonl"


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


def sps_value(row: dict[str, Any]) -> str:
    return str((row.get("standalone_projection_source") or {}).get("gold_value") or "missing")


def main() -> None:
    base_summary = load_json(BASE_SUMMARY)
    admission = load_json(ADMISSION_SUMMARY)
    if not admission.get("train_admission_passed"):
        raise SystemExit("stage11179 admission did not pass")

    base_train = load_jsonl(BASE_TRAIN)
    validation = load_jsonl(BASE_VALIDATION)
    strict = load_jsonl(BASE_STRICT)
    stress = load_jsonl(BASE_STRESS)
    admitted = load_jsonl(ADMITTED_ROWS)

    existing_ids = {str(row.get("row_id") or "") for row in base_train}
    added = [row for row in admitted if str(row.get("row_id") or "") not in existing_ids]
    train = [*base_train, *added]

    added_roots = {str(row.get("root_id") or "") for row in added}
    eval_roots = {str(row.get("root_id") or "") for row in [*validation, *strict, *stress] if row.get("root_id")}
    root_overlap = sorted(added_roots & eval_roots)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(added) and not root_overlap,
        "decision": "support_package_ready_for_diagnostic_probe" if added and not root_overlap else "support_package_blocked",
        "claim_scope": [
            "Add stage11179 contract-aware evidence-role rows as train-support-only supervision.",
            "Keep cleaned validation, strict, and stress surfaces unchanged from stage11168.",
            "Do not treat added rows as heldout or promotable evaluation evidence.",
        ],
        "metrics": {
            "train_rows_before": len(base_train),
            "train_rows_after": len(train),
            "rows_added": len(added),
            "added_unique_roots": len(added_roots),
            "validation_rows": len(validation),
            "strict_rows": len(strict),
            "stress_rows": len(stress),
            "added_by_language": count_by(added, "language_family"),
            "added_by_repo_family": count_by(added, "repo_family"),
            "added_by_task": count_by(added, "task_type"),
            "added_by_gold_value": dict(sorted(Counter(sps_value(row) for row in added).items())),
            "root_overlap_with_eval_or_stress": root_overlap,
        },
        "source_artifacts": {
            "base_package": rel(BASE_SUMMARY),
            "admission_audit": rel(ADMISSION_SUMMARY),
            "admitted_rows": rel(ADMITTED_ROWS),
        },
        "limits": [
            "C/C++ evidence support remains thin despite all three roles being represented.",
            "This package tests whether cleaner root-disjoint evidence-role geometry moves the reserved evidence bank; it is not a benchmark expansion.",
        ],
        "next_best_step": "Run exactly one diagnostic probe from this package, then audit clean strict, clean validation, reserved residual, and evidence-residual movement.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_rows_jsonl": rel(TRAIN_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_JSONL),
            "strict_rows_jsonl": rel(STRICT_JSONL),
            "stress_rows_jsonl": rel(STRESS_JSONL),
            "added_rows_jsonl": rel(ADDED_JSONL),
        },
        "base_snapshot": base_summary.get("metrics"),
        "admission_snapshot": {
            "admitted_rows": admission.get("admitted_rows"),
            "gold_value_counts": admission.get("gold_value_counts"),
            "language_counts": admission.get("language_counts"),
            "train_admission_passed": admission.get("train_admission_passed"),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(TRAIN_JSONL, train)
    write_jsonl(VALIDATION_JSONL, validation)
    write_jsonl(STRICT_JSONL, strict)
    write_jsonl(STRESS_JSONL, stress)
    write_jsonl(ADDED_JSONL, added)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

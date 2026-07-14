#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11114
NAME = "stage11114_fresh_family_support_package_with_trainable_admitted_evidence"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_family_support_package_with_trainable_admitted_evidence.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED_ROWS_JSONL = OUT_DIR / "added_admitted_evidence_rows_trainable.jsonl"

BASE_DIR = ARTIFACTS / "stage11099_fresh_family_support_package"
BASE_SUMMARY = BASE_DIR / "fresh_family_support_package.json"
BASE_TRAIN = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

ADMISSION_DIR = ARTIFACTS / "stage11113_fresh_family_evidence_admission_audit_trainable"
ADMISSION_SUMMARY = ADMISSION_DIR / "fresh_family_evidence_admission_audit_trainable.json"
ADMITTED_ROWS = ADMISSION_DIR / "admitted_evidence_rows_trainable.jsonl"


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
    admission_summary = load_json(ADMISSION_SUMMARY)
    base_train = load_jsonl(BASE_TRAIN)
    validation_rows = load_jsonl(BASE_VALIDATION)
    strict_rows = load_jsonl(BASE_STRICT)
    stress_rows = load_jsonl(BASE_STRESS)
    admitted_rows = load_jsonl(ADMITTED_ROWS)

    existing_ids = {str(row.get("row_id") or "") for row in base_train}
    deduped_added_rows = [row for row in admitted_rows if str(row.get("row_id") or "") not in existing_ids]
    train_rows = [*base_train, *deduped_added_rows]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(deduped_added_rows),
        "decision": "fresh_family_support_package_with_trainable_admitted_evidence_ready",
        "claim_scope": [
            "Extend the latest clean fresh-family support package with admitted train-support-only evidence rows that now satisfy the trainer loss contract.",
            "Keep validation, strict, and stress unchanged while adding only deshortcutted, leak-audited evidence supervision.",
        ],
        "metrics": {
            "train_rows_before": len(base_train),
            "train_rows_after": len(train_rows),
            "rows_added_total": len(deduped_added_rows),
            "added_by_language": count_by(deduped_added_rows, "language_family"),
            "added_by_repo_family": count_by(deduped_added_rows, "repo_family"),
            "added_by_target": count_by(deduped_added_rows, "target_text"),
            "added_by_task": count_by(deduped_added_rows, "task_type"),
            "validation_rows_unchanged": len(validation_rows),
            "strict_rows_unchanged": len(strict_rows),
            "stress_rows_unchanged": len(stress_rows),
        },
        "headline_findings": [
            "This package adds the first leak-audited evidence-citation replenishment rows from the fresh-family pipeline in a trainable form accepted by the trainer.",
            "The new rows are train-support-only and explicitly not promotable strict-eval rows.",
            "The package still does not solve the deeper scorer-objective mismatch by itself; it only provides cleaner evidence-role supervision.",
        ],
        "limits": [
            "All added evidence rows remain heuristic and same-surface-inadmissible for headline claims.",
            "Rust is still absent from this admitted evidence batch, and web remains support-only.",
        ],
        "next_best_step": "Use this package only for a support-only probe or for scorer-objective experiments, not for a new promotable benchmark claim.",
        "source_artifacts": {
            "base_support_package": rel(BASE_SUMMARY),
            "evidence_admission_audit": rel(ADMISSION_SUMMARY),
            "admitted_rows": rel(ADMITTED_ROWS),
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
        "admission_snapshot": admission_summary.get("metrics"),
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

#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10881
NAME = "stage10881_evidence_alias_quarantine_successor"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "evidence_alias_quarantine_successor.json"
TRAIN_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

BASE_DIR = ARTIFACTS / "stage10864_residual_family_support_package_plus_second_python_materialized"
AUDIT_JSON = ARTIFACTS / "stage10880_evidence_alias_anticheat_audit" / "evidence_alias_anticheat_audit.json"


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


def main() -> None:
    audit = load_json(AUDIT_JSON)
    blocked_ids = {str(item["row_id"]) for item in audit["blocked_rows"]}

    train_rows = [row for row in load_jsonl(BASE_DIR / "agentkernel_lite_encdec_train.jsonl") if str(row.get("row_id")) not in blocked_ids]
    validation_rows = [row for row in load_jsonl(BASE_DIR / "agentkernel_lite_encdec_validation.jsonl") if str(row.get("row_id")) not in blocked_ids]
    strict_rows = [row for row in load_jsonl(BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl") if str(row.get("row_id")) not in blocked_ids]
    stress_rows = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl")

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "evidence_alias_quarantine_successor_ready",
        "claim_scope": [
            "Produce an anti-cheat-clean successor package that quarantines evidence_citation rows with duplicated visible evidence under different semantic labels.",
            "Preserve all non-blocked rows unchanged and leave stress rows untouched.",
        ],
        "source_package": rel(BASE_DIR / "residual_family_support_package_plus_second_python_materialized.json"),
        "source_audit": rel(AUDIT_JSON),
        "metrics": {
            "train_rows": len(train_rows),
            "validation_rows": len(validation_rows),
            "strict_rows": len(strict_rows),
            "stress_rows": len(stress_rows),
            "blocked_row_count": len(blocked_ids),
            "blocked_row_ids": sorted(blocked_ids),
        },
        "limitations": [
            "This quarantine successor improves honesty but reduces Rust evidence coverage in validation/strict.",
            "A fresh reviewed Rust evidence root is still required before restoring a balanced multilingual promotable evidence slice.",
        ],
        "next_best_step": "Use this successor as the honest anti-cheat baseline for future evidence-family work, and replenish Rust evidence evaluation with a fresh non-aliased reviewed root before making multilingual v2.7 headline claims.",
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

#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10747
NAME = "stage10747_python_rust_residual_targeted_support_package"
OUT_DIR = ARTIFACTS / NAME
PACKAGE_JSON = OUT_DIR / "python_rust_residual_targeted_support_package.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ROWS_JSONL = OUT_DIR / "python_rust_residual_targeted_support_rows.jsonl"

BASE_VALIDATION = ARTIFACTS / "stage10743_reviewed_v27_plus_cpp_bootstrap_train_support_package/agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = ARTIFACTS / "stage10743_reviewed_v27_plus_cpp_bootstrap_train_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = ARTIFACTS / "stage10743_reviewed_v27_plus_cpp_bootstrap_train_support_package/agentkernel_lite_encdec_stress_eval.jsonl"
CURRENT_TRAIN = ARTIFACTS / "stage10743_reviewed_v27_plus_cpp_bootstrap_train_support_package/agentkernel_lite_encdec_train.jsonl"
PYTHON_SUPPORT = ARTIFACTS / "stage10487_deleaked_python_verifier_support_package/deleaked_python_verifier_support_rows.jsonl"

RUST_BUNDLE_IDS = {
    "stage10413::candle::candle-flash-attn::rust",
    "stage10674::linux::rust",
    "stage10674::candle::candle-datasets",
}
RUST_TASKS = {"evidence_citation", "verifier_outcome"}


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


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    validation_rows = load_jsonl(BASE_VALIDATION)
    strict_rows = load_jsonl(BASE_STRICT)
    stress_rows = load_jsonl(BASE_STRESS)
    current_train_rows = load_jsonl(CURRENT_TRAIN)
    python_rows = load_jsonl(PYTHON_SUPPORT)

    rust_rows = [
        row
        for row in current_train_rows
        if row.get("language_family") == "rust"
        and row.get("task_type") in RUST_TASKS
        and row.get("source_bundle_id") in RUST_BUNDLE_IDS
    ]

    train_rows = python_rows + rust_rows
    all_rows = train_rows + validation_rows + strict_rows

    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(VALIDATION_JSONL, validation_rows)
    write_jsonl(STRICT_JSONL, strict_rows)
    write_jsonl(STRESS_JSONL, stress_rows)
    write_jsonl(ROWS_JSONL, train_rows)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(train_rows),
        "decision": "python_rust_residual_targeted_support_package_ready",
        "claim_boundary": [
            "This is a narrow residual-targeted support package, not a promoted multilingual frontier package.",
            "Strict and validation rows remain unchanged from the current reviewed v2.7 standalone frontier.",
            "Python train rows are limited to deleaked disjoint verifier support; Rust train rows are limited to honest citation/verifier support roots aligned with the surviving rust miss family.",
        ],
        "metrics": {
            "train_rows": len(train_rows),
            "validation_rows": len(validation_rows),
            "strict_eval_rows": len(strict_rows),
            "stress_rows": len(stress_rows),
            "train_language_counts": count_by(train_rows, "language_family"),
            "train_task_counts": count_by(train_rows, "task_type"),
            "train_repo_counts": count_by(train_rows, "repo_id"),
        },
        "selected_train_sources": {
            "python_deleaked_support_row_ids": [row["row_id"] for row in python_rows],
            "rust_support_row_ids": [row["row_id"] for row in rust_rows],
        },
        "outputs": {
            "train_rows": str(TRAIN_JSONL.relative_to(ROOT)),
            "validation_rows": str(VALIDATION_JSONL.relative_to(ROOT)),
            "strict_rows": str(STRICT_JSONL.relative_to(ROOT)),
            "stress_rows": str(STRESS_JSONL.relative_to(ROOT)),
            "support_rows": str(ROWS_JSONL.relative_to(ROOT)),
        },
        "next_best_step": "Run a narrow support-only probe from the latest preserved runtime and require improvement beyond 22/24 with zero new strict regressions before any promotion.",
    }
    write_json(PACKAGE_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

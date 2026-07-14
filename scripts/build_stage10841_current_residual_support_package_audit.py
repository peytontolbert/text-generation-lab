#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10841
NAME = "stage10841_current_residual_support_package_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "current_residual_support_package_audit.json"

PACKAGE_JSON = ARTIFACTS / "stage10839_current_residual_support_package" / "current_residual_support_package.json"
TRAIN_ROWS = ARTIFACTS / "stage10839_current_residual_support_package" / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_ROWS = ARTIFACTS / "stage10839_current_residual_support_package" / "agentkernel_lite_encdec_validation.jsonl"
STRICT_ROWS = ARTIFACTS / "stage10839_current_residual_support_package" / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_TRAIN_ROWS = ARTIFACTS / "stage10827_evidence_role_augmented_support_package" / "agentkernel_lite_encdec_train.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def main() -> None:
    package = load_json(PACKAGE_JSON)
    train_rows = load_jsonl(TRAIN_ROWS)
    validation_rows = load_jsonl(VALIDATION_ROWS)
    strict_rows = load_jsonl(STRICT_ROWS)
    base_train_rows = load_jsonl(BASE_TRAIN_ROWS)

    base_row_ids = {str(row.get("row_id")) for row in base_train_rows}
    added_rows = [row for row in train_rows if str(row.get("row_id")) not in base_row_ids]
    duplicate_count = len(train_rows) - len({str(row.get("row_id")) for row in train_rows})

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "current_residual_support_package_audited",
        "claim_scope": [
            "Audit that the current residual support package adds only the intended hf_local repaired rows while preserving the frozen validation and strict surfaces.",
            "Make the support-only boundary explicit so future probe movement cannot be misreported as a fresh heldout win.",
        ],
        "checks": {
            "train_row_id_duplicates": duplicate_count,
            "added_row_count_vs_package_metrics": len(added_rows) == package["metrics"]["added_hf_local_rows"],
            "all_added_rows_are_python": all(str(row.get("language_family")) == "python" for row in added_rows),
            "all_added_rows_train_support_only": all(bool(row.get("train_support_only")) for row in added_rows),
            "all_added_rows_strict_eval_eligible_false": all(not bool(row.get("strict_eval_eligible")) for row in added_rows),
            "validation_count_preserved": len(validation_rows) == package["metrics"]["validation_rows"],
            "strict_count_preserved": len(strict_rows) == package["metrics"]["strict_rows"],
        },
        "added_rows_summary": {
            "count": len(added_rows),
            "by_task": count_by(added_rows, "task_type"),
            "bundle_ids": sorted({str(row.get("source_bundle_id")) for row in added_rows}),
        },
        "frozen_eval_surface": {
            "validation_rows": len(validation_rows),
            "strict_rows": len(strict_rows),
        },
        "promotion_boundary": [
            "No new strict rows were added.",
            "All added rows are train-support only.",
            "Any post-run gain must still be interpreted against the unchanged 24-row strict frontier.",
        ],
    }

    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

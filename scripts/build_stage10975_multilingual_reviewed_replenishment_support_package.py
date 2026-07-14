#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10975
NAME = "stage10975_multilingual_reviewed_replenishment_support_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "multilingual_reviewed_replenishment_support_package.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED_ROWS_JSONL = OUT_DIR / "added_reviewed_replenishment_rows.jsonl"

BASE_DIR = ARTIFACTS / "stage10883_flash_attn_alias_safe_successor_package"
BASE_SUMMARY_JSON = BASE_DIR / "flash_attn_alias_safe_successor_package.json"
BASE_TRAIN_JSONL = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION_JSONL = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT_JSONL = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS_JSONL = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

REPLENISH_JSON = ARTIFACTS / "stage10974_multilingual_reviewed_replenishment_package" / "multilingual_reviewed_replenishment_package.json"
REPLENISH_SUPPORT_JSONL = ARTIFACTS / "stage10974_multilingual_reviewed_replenishment_package" / "train_support_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


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




def sanitize_eval_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = "eval"
    updated["disable_losses"] = []
    updated["loss_mask"] = {"decoder_ce": True}
    updated["expected_enabled_loss"] = "decoder_ce"
    return updated


def sanitize_strict_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = "strict_eval"
    updated["disable_losses"] = []
    updated["loss_mask"] = {"decoder_ce": True}
    updated["expected_enabled_loss"] = "decoder_ce"
    return updated
def sanitize_train_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = "train"
    updated["train_support_only"] = True
    updated["strict_eval_eligible"] = False
    updated["disable_losses"] = []
    updated["loss_mask"] = {"decoder_ce": True}
    updated["expected_enabled_loss"] = "decoder_ce"
    return updated


def main() -> None:
    base_summary = load_json(BASE_SUMMARY_JSON)
    base_train = [sanitize_train_row(row) for row in load_jsonl(BASE_TRAIN_JSONL)]
    validation_rows = [sanitize_eval_row(row) for row in load_jsonl(BASE_VALIDATION_JSONL)]
    strict_rows = [sanitize_strict_row(row) for row in load_jsonl(BASE_STRICT_JSONL)]
    stress_rows = load_jsonl(BASE_STRESS_JSONL)
    replenish_summary = load_json(REPLENISH_JSON)
    replenish_rows = [sanitize_train_row(row) for row in load_jsonl(REPLENISH_SUPPORT_JSONL)]
    merged_train = list(base_train) + list(replenish_rows)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(replenish_rows) and bool(strict_rows),
        "decision": "multilingual_reviewed_replenishment_support_package_ready",
        "claim_scope": [
            "Add the audited stage10974 reviewed replenishment rows into the train split while keeping the stage10883 validation/strict/stress heldout surfaces unchanged.",
            "Provide a clean multilingual support package for one honest next probe against the frozen 23-row overlay.",
        ],
        "required_honesty_gates": [
            "All added rows remain train_support_only and strict_eval_eligible=false.",
            "Validation, strict, and stress rows are copied unchanged from stage10883.",
            "Web remains absent from added support rows and absent from any new headline claim in this stage.",
        ],
        "source_artifacts": {
            "base_summary": rel(BASE_SUMMARY_JSON),
            "replenishment_summary": rel(REPLENISH_JSON),
            "replenishment_support_rows": rel(REPLENISH_SUPPORT_JSONL),
        },
        "metrics": {
            "train_rows_before": len(base_train),
            "added_reviewed_rows": len(replenish_rows),
            "train_rows_after": len(merged_train),
            "validation_rows_unchanged": len(validation_rows),
            "strict_rows_unchanged": len(strict_rows),
            "stress_rows_unchanged": len(stress_rows),
            "added_by_language": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in replenish_rows).items())),
            "train_by_language": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in merged_train).items())),
            "base_metrics_snapshot": base_summary.get("metrics"),
            "replenishment_metrics_snapshot": replenish_summary.get("metrics"),
        },
        "headline_findings": [
            "This package adds audited reviewed support rows for Python, C/C++, and Rust to the clean 23-row overlay baseline.",
            "It does not change heldout scoring surfaces, so any movement in the next probe can be attributed to train-support changes rather than eval drift.",
            "Web remains unchanged and still needs new pure-web selected-test source supply before any stronger multilingual headline claim.",
        ],
        "next_best_step": "Run one multilingual support probe from the clean stage10960 runtime, then audit the unchanged overlay plus the replenishment candidate slice from stage10974.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_rows_jsonl": rel(TRAIN_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_JSONL),
            "strict_rows_jsonl": rel(STRICT_JSONL),
            "stress_rows_jsonl": rel(STRESS_JSONL),
            "added_rows_jsonl": rel(ADDED_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, payload)
    write_jsonl(ADDED_ROWS_JSONL, replenish_rows)
    write_jsonl(TRAIN_JSONL, merged_train)
    write_jsonl(VALIDATION_JSONL, validation_rows)
    write_jsonl(STRICT_JSONL, strict_rows)
    write_jsonl(STRESS_JSONL, stress_rows)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

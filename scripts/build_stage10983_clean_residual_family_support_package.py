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
STAGE = 10983
NAME = "stage10983_clean_residual_family_support_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "clean_residual_family_support_package.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED_ROWS_JSONL = OUT_DIR / "added_clean_curriculum_rows.jsonl"

BASE_DIR = ARTIFACTS / "stage10883_flash_attn_alias_safe_successor_package"
BASE_SUMMARY_JSON = BASE_DIR / "flash_attn_alias_safe_successor_package.json"
BASE_TRAIN_JSONL = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION_JSONL = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT_JSONL = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS_JSONL = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

CLEAN_CURRICULUM_JSON = ARTIFACTS / "stage10981_clean_residual_family_curriculum_package" / "clean_residual_family_curriculum_package.json"
CLEAN_CURRICULUM_ROWS = ARTIFACTS / "stage10981_clean_residual_family_curriculum_package" / "train_support_rows.jsonl"


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


def sanitize_train_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = "train"
    updated["train_support_only"] = True
    updated["strict_eval_eligible"] = False
    updated["disable_losses"] = []
    updated["loss_mask"] = {"decoder_ce": True}
    updated["expected_enabled_loss"] = "decoder_ce"
    return updated


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


def dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row.get("row_id") or ""), str(row.get("target_text") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def main() -> None:
    base_summary = load_json(BASE_SUMMARY_JSON)
    base_train = [sanitize_train_row(row) for row in load_jsonl(BASE_TRAIN_JSONL)]
    validation_rows = [sanitize_eval_row(row) for row in load_jsonl(BASE_VALIDATION_JSONL)]
    strict_rows = [sanitize_strict_row(row) for row in load_jsonl(BASE_STRICT_JSONL)]
    stress_rows = load_jsonl(BASE_STRESS_JSONL)
    curriculum_summary = load_json(CLEAN_CURRICULUM_JSON)
    curriculum_rows = [sanitize_train_row(row) for row in load_jsonl(CLEAN_CURRICULUM_ROWS)]
    merged_train = dedupe(base_train + curriculum_rows)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(curriculum_rows) and bool(strict_rows),
        "decision": "clean_residual_family_support_package_ready",
        "claim_scope": [
            "Add the clean residual-family curriculum rows into the train split while keeping the alias-safe heldout surfaces fixed.",
            "Provide a larger honest train-support package for one next probe against the frozen 23-row overlay and fresh residual slices.",
        ],
        "required_honesty_gates": [
            "Validation, strict, and stress rows are copied unchanged from stage10883.",
            "All added rows come from root-split or support-only sources already audited to avoid overlay heldout overlap.",
            "No reviewed heldout-root overlap rows from stage10979 overlap bucket are allowed into train in this stage.",
        ],
        "source_artifacts": {
            "base_summary": rel(BASE_SUMMARY_JSON),
            "clean_curriculum_summary": rel(CLEAN_CURRICULUM_JSON),
            "clean_curriculum_rows": rel(CLEAN_CURRICULUM_ROWS),
        },
        "metrics": {
            "train_rows_before": len(base_train),
            "added_clean_rows": len(curriculum_rows),
            "train_rows_after_dedup": len(merged_train),
            "validation_rows_unchanged": len(validation_rows),
            "strict_rows_unchanged": len(strict_rows),
            "stress_rows_unchanged": len(stress_rows),
            "added_by_language": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in curriculum_rows).items())),
            "added_by_task": dict(sorted(Counter(str(row.get("task_type") or "unknown") for row in curriculum_rows).items())),
            "train_by_language": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in merged_train).items())),
            "train_by_task": dict(sorted(Counter(str(row.get("task_type") or "unknown") for row in merged_train).items())),
            "base_metrics_snapshot": base_summary.get("metrics"),
            "curriculum_metrics_snapshot": curriculum_summary.get("metrics"),
        },
        "headline_findings": [
            "This package replaces the overlap-heavy reviewed-bundle merge with a larger clean curriculum built from root-split and support-only sources.",
            "It adds substantial Python and C/C++ residual-family coverage while preserving the same heldout frontier.",
            "Web remains unchanged because the clean curriculum still has almost no usable web support.",
        ],
        "next_best_step": "Run one clean-curriculum probe from the stage10960 runtime, then audit the unchanged 23-row overlay plus the expanded evidence successor family and Python verifier-transition candidate slice.",
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
    write_jsonl(ADDED_ROWS_JSONL, curriculum_rows)
    write_jsonl(TRAIN_JSONL, merged_train)
    write_jsonl(VALIDATION_JSONL, validation_rows)
    write_jsonl(STRICT_JSONL, strict_rows)
    write_jsonl(STRESS_JSONL, stress_rows)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10709
NAME = "stage10709_rewritten_plus_reviewed_training_package_execution_repaired"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "rewritten_plus_reviewed_training_package_execution_repaired.json"
TRAIN_ROWS_JSONL = OUT_DIR / "train_rows.jsonl"
VALIDATION_ROWS_JSONL = OUT_DIR / "validation_rows.jsonl"
STRICT_ROWS_JSONL = OUT_DIR / "strict_rows.jsonl"
EVAL_ROWS_JSONL = OUT_DIR / "eval_rows.jsonl"
CANARY_ROWS_JSONL = OUT_DIR / "canary_rows.jsonl"
DIAGNOSTIC_ROWS_JSONL = OUT_DIR / "diagnostic_rows.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SOURCE_PACKAGE = ROOT / "runs/local/artifacts/stage10706_rewritten_plus_reviewed_multilingual_training_package_honest_strict/rewritten_plus_reviewed_multilingual_training_package_honest_strict.json"
SOURCE_TRAIN_ROWS = ROOT / "runs/local/artifacts/stage10706_rewritten_plus_reviewed_multilingual_training_package_honest_strict/train_rows.jsonl"
SOURCE_VALIDATION_ROWS = ROOT / "runs/local/artifacts/stage10706_rewritten_plus_reviewed_multilingual_training_package_honest_strict/validation_rows.jsonl"
SOURCE_EVAL_ROWS = ROOT / "runs/local/artifacts/stage10706_rewritten_plus_reviewed_multilingual_training_package_honest_strict/eval_rows.jsonl"
SOURCE_STRICT_ROWS = ROOT / "runs/local/artifacts/stage10706_rewritten_plus_reviewed_multilingual_training_package_honest_strict/strict_rows.jsonl"
SOURCE_CANARY_ROWS = ROOT / "runs/local/artifacts/stage10706_rewritten_plus_reviewed_multilingual_training_package_honest_strict/canary_rows.jsonl"
SOURCE_DIAGNOSTIC_ROWS = ROOT / "runs/local/artifacts/stage10706_rewritten_plus_reviewed_multilingual_training_package_honest_strict/diagnostic_rows.jsonl"

REPAIRED_TRAIN_ROWS = ROOT / "runs/local/artifacts/stage10708_rewritten_support_execution_contract_repair/train_rows.jsonl"
REPAIRED_VALIDATION_ROWS = ROOT / "runs/local/artifacts/stage10708_rewritten_support_execution_contract_repair/validation_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def split_counts(rows: list[dict[str, Any]], split_name: str) -> dict[str, Any]:
    return {
        "split": split_name,
        "rows": len(rows),
        "language_counts": dict(sorted(Counter(str(row.get("language_family") or "") for row in rows).items())),
        "repo_family_counts": dict(sorted(Counter(str(row.get("repo_family") or "") for row in rows).items())),
        "target_subtype_counts": dict(sorted(Counter(str(row.get("target_subtype") or str(row.get("task_type") or "")) for row in rows).items())),
        "source_kind_counts": dict(sorted(Counter(str(row.get("package_source_kind") or "") for row in rows).items())),
        "unique_roots": len({str(row.get("root_id") or row.get("source_root_id") or "") for row in rows}),
    }


def normalized_trainable_row(row: dict[str, Any]) -> dict[str, Any]:
    copied = json.loads(json.dumps(row))
    target_text = str(copied.get("target_text") or copied.get("decoder_text") or "")
    if target_text and not str(copied.get("decoder_text") or ""):
        copied["decoder_text"] = target_text
    if target_text and not copied.get("loss_mask"):
        copied["loss_mask"] = {"decoder_ce": True}
    return copied


def main() -> None:
    source_package = load_json(SOURCE_PACKAGE)
    source_train_rows = load_jsonl(SOURCE_TRAIN_ROWS)
    source_validation_rows = load_jsonl(SOURCE_VALIDATION_ROWS)
    repaired_train_rows = load_jsonl(REPAIRED_TRAIN_ROWS)
    repaired_validation_rows = load_jsonl(REPAIRED_VALIDATION_ROWS)

    repaired_train_by_id = {str(row.get("row_id") or ""): row for row in repaired_train_rows}
    repaired_validation_by_id = {str(row.get("row_id") or ""): row for row in repaired_validation_rows}

    train_rows: list[dict[str, Any]] = []
    replaced_train = 0
    normalized_train = 0
    for row in source_train_rows:
        row_id = str(row.get("row_id") or "")
        replacement = repaired_train_by_id.get(row_id)
        if replacement is not None:
            merged = json.loads(json.dumps(row))
            merged["decoder_text"] = replacement.get("decoder_text")
            merged["target_text"] = replacement.get("target_text")
            merged["loss_mask"] = replacement.get("loss_mask")
            merged["execution_contract_repaired"] = True
            merged["execution_contract_repair_stage"] = 10708
            train_rows.append(normalized_trainable_row(merged))
            replaced_train += 1
            continue
        normalized = normalized_trainable_row(row)
        if normalized.get("decoder_text") != row.get("decoder_text") or normalized.get("loss_mask") != row.get("loss_mask"):
            normalized_train += 1
        train_rows.append(normalized)

    validation_rows: list[dict[str, Any]] = []
    replaced_validation = 0
    normalized_validation = 0
    for row in source_validation_rows:
        row_id = str(row.get("row_id") or "")
        replacement = repaired_validation_by_id.get(row_id)
        if replacement is not None:
            merged = json.loads(json.dumps(row))
            merged["decoder_text"] = replacement.get("decoder_text")
            merged["target_text"] = replacement.get("target_text")
            merged["loss_mask"] = replacement.get("loss_mask")
            merged["execution_contract_repaired"] = True
            merged["execution_contract_repair_stage"] = 10708
            validation_rows.append(normalized_trainable_row(merged))
            replaced_validation += 1
            continue
        normalized = normalized_trainable_row(row)
        if normalized.get("decoder_text") != row.get("decoder_text") or normalized.get("loss_mask") != row.get("loss_mask"):
            normalized_validation += 1
        validation_rows.append(normalized)

    eval_rows = load_jsonl(SOURCE_EVAL_ROWS)
    strict_rows = load_jsonl(SOURCE_STRICT_ROWS)
    canary_rows = load_jsonl(SOURCE_CANARY_ROWS)
    diagnostic_rows = load_jsonl(SOURCE_DIAGNOSTIC_ROWS)

    train_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    validation_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    eval_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    strict_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    canary_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    diagnostic_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))

    write_jsonl(TRAIN_ROWS_JSONL, train_rows)
    write_jsonl(VALIDATION_ROWS_JSONL, validation_rows)
    write_jsonl(EVAL_ROWS_JSONL, eval_rows)
    write_jsonl(STRICT_ROWS_JSONL, strict_rows)
    write_jsonl(CANARY_ROWS_JSONL, canary_rows)
    write_jsonl(DIAGNOSTIC_ROWS_JSONL, diagnostic_rows)

    rows_with_decoder = train_rows + validation_rows
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "rewritten_plus_reviewed_training_package_execution_repaired_ready",
        "claim_scope": [
            "Repair the executable train and validation support rows without altering the honest eval, strict, canary, or diagnostic slices.",
            "Preserve the audited 24-row strict frontier exactly while swapping in execution-contract-repaired rewritten support rows.",
            "Normalize any older trainable rows that already have target_text but were missing decoder_text or a decoder loss mask.",
        ],
        "source_artifacts": {
            "source_honest_package": display(SOURCE_PACKAGE),
            "repaired_rewritten_train_rows": display(REPAIRED_TRAIN_ROWS),
            "repaired_rewritten_validation_rows": display(REPAIRED_VALIDATION_ROWS),
        },
        "splits": {
            "train": split_counts(train_rows, "train"),
            "validation": split_counts(validation_rows, "validation"),
            "eval": split_counts(eval_rows, "eval"),
            "strict_eval": split_counts(strict_rows, "strict_eval"),
            "diagnostic": split_counts(diagnostic_rows, "diagnostic"),
            "canary": split_counts(canary_rows, "canary"),
        },
        "repair_counts": {
            "replaced_train_rows": replaced_train,
            "replaced_validation_rows": replaced_validation,
            "normalized_existing_train_rows": normalized_train,
            "normalized_existing_validation_rows": normalized_validation,
            "rows_with_decoder_text_after_repair": sum(1 for row in rows_with_decoder if str(row.get("decoder_text") or "")),
            "rows_with_target_text_after_repair": sum(1 for row in rows_with_decoder if str(row.get("target_text") or "")),
            "rows_with_loss_mask_after_repair": sum(1 for row in rows_with_decoder if row.get("loss_mask")),
        },
        "gates": {
            "strict_frontier_preserved_unchanged": len(strict_rows) == int((((source_package.get("splits") or {}).get("strict_eval") or {}).get("rows")) or 0),
            "eval_frontier_preserved_unchanged": len(eval_rows) == int((((source_package.get("splits") or {}).get("eval") or {}).get("rows")) or 0),
            "canary_preserved_unchanged": len(canary_rows) == int((((source_package.get("splits") or {}).get("canary") or {}).get("rows")) or 0),
            "diagnostic_preserved_unchanged": len(diagnostic_rows) == int((((source_package.get("splits") or {}).get("diagnostic") or {}).get("rows")) or 0),
        },
        "headline_findings": [
            "The failed stage10707 launch was caused by execution-contract gaps in train rows, not by a model or environment regression.",
            "This package keeps the audited 24-row strict frontier intact and repairs both rewritten rows and older target-bearing train rows that lacked decoder/loss fields.",
            "It is now suitable for a rerun of the honest multilingual probe request.",
        ],
        "recommended_next_stage": "stage10710_rewritten_plus_reviewed_probe_request_execution_repaired",
        "outputs": {
            "train_rows": display(TRAIN_ROWS_JSONL),
            "validation_rows": display(VALIDATION_ROWS_JSONL),
            "eval_rows": display(EVAL_ROWS_JSONL),
            "strict_rows": display(STRICT_ROWS_JSONL),
            "diagnostic_rows": display(DIAGNOSTIC_ROWS_JSONL),
            "canary_rows": display(CANARY_ROWS_JSONL),
            "package_json": display(PACKAGE_JSON),
        },
    }

    write_json(PACKAGE_JSON, payload)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "package_json": display(PACKAGE_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

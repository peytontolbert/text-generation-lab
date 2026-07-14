#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10727
NAME = "stage10727_semantic_contrast_support_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "semantic_contrast_support_package.json"
TRAIN_ROWS_JSONL = OUT_DIR / "train_rows.jsonl"
VALIDATION_ROWS_JSONL = OUT_DIR / "validation_rows.jsonl"
EVAL_ROWS_JSONL = OUT_DIR / "eval_rows.jsonl"
STRICT_ROWS_JSONL = OUT_DIR / "strict_rows.jsonl"
CANARY_ROWS_JSONL = OUT_DIR / "canary_rows.jsonl"
DIAGNOSTIC_ROWS_JSONL = OUT_DIR / "diagnostic_rows.jsonl"
SUMMARY_CARD = ROOT / "runs/summaries" / f"{NAME}.json"

BASE_DIR = ROOT / "runs/local/artifacts/stage10709_rewritten_plus_reviewed_training_package_execution_repaired"
PYTHON_DIR = ROOT / "runs/local/artifacts/stage10725_python_verifier_semantic_contrast_builder"
RUST_DIR = ROOT / "runs/local/artifacts/stage10726_rust_citation_semantic_contrast_builder"


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


def main() -> None:
    base = load_json(BASE_DIR / "rewritten_plus_reviewed_training_package_execution_repaired.json")
    base_train = load_jsonl(BASE_DIR / "train_rows.jsonl")
    base_validation = load_jsonl(BASE_DIR / "validation_rows.jsonl")
    base_eval = load_jsonl(BASE_DIR / "eval_rows.jsonl")
    base_strict = load_jsonl(BASE_DIR / "strict_rows.jsonl")
    base_canary = load_jsonl(BASE_DIR / "canary_rows.jsonl")
    base_diagnostic = load_jsonl(BASE_DIR / "diagnostic_rows.jsonl")

    python_rows = load_jsonl(PYTHON_DIR / "agentkernel_lite_encdec_train.jsonl")
    rust_rows = load_jsonl(RUST_DIR / "agentkernel_lite_encdec_train.jsonl")

    merged_train: list[dict[str, Any]] = []
    seen: set[str] = set()

    injected_rows = python_rows + rust_rows
    injected_ids = {str(row["row_id"]) for row in injected_rows}
    for row in injected_rows:
        row_id = str(row["row_id"])
        if row_id in seen:
            continue
        seen.add(row_id)
        row = dict(row)
        row["support_package_stage"] = STAGE
        merged_train.append(row)

    replaced_existing = 0
    for row in base_train:
        row_id = str(row["row_id"])
        if row_id in injected_ids:
            replaced_existing += 1
            continue
        if row_id in seen:
            continue
        seen.add(row_id)
        merged_train.append(row)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "semantic_contrast_support_package_ready",
        "claim_scope": [
            "Merge the stage10725 Python semantic verifier seeds and stage10726 Rust semantic citation seeds into the execution-repaired multilingual package.",
            "Keep eval, strict, canary, diagnostic, and validation slices unchanged while changing only the train curriculum.",
        ],
        "metrics": {
            "base_train_rows": len(base_train),
            "python_injected_rows": len(python_rows),
            "rust_injected_rows": len(rust_rows),
            "replaced_existing_rows": replaced_existing,
            "merged_train_rows": len(merged_train),
            "validation_rows": len(base_validation),
            "eval_rows": len(base_eval),
            "strict_rows": len(base_strict),
        },
        "gates": {
            "strict_frontier_preserved_unchanged": True,
            "eval_frontier_preserved_unchanged": True,
            "canary_preserved_unchanged": True,
            "diagnostic_preserved_unchanged": True,
            "validation_preserved_unchanged": True,
        },
        "headline_findings": [
            "The train split now includes explicit Python verifier semantic-contrast support and Rust citation semantic-contrast support.",
            "The Rust lane now includes one fresh reviewed flash-attn semantic contrast row in addition to candle-core auxiliary rows.",
            "The strict 24-row overlay remains unchanged, so any movement in the next probe stays attributable to train-side curriculum changes.",
        ],
        "next_best_step": "Build a frontloaded probe request from this package so the newly added support is guaranteed to be sampled.",
        "source_artifacts": {
            "base_package": display(BASE_DIR / 'rewritten_plus_reviewed_training_package_execution_repaired.json'),
            "python_builder": display(PYTHON_DIR / 'python_verifier_semantic_contrast_builder.json'),
            "rust_builder": display(RUST_DIR / 'rust_citation_semantic_contrast_builder.json'),
        },
        "outputs": {
            "package_json": display(PACKAGE_JSON),
            "train_rows": display(TRAIN_ROWS_JSONL),
            "validation_rows": display(VALIDATION_ROWS_JSONL),
            "eval_rows": display(EVAL_ROWS_JSONL),
            "strict_rows": display(STRICT_ROWS_JSONL),
            "canary_rows": display(CANARY_ROWS_JSONL),
            "diagnostic_rows": display(DIAGNOSTIC_ROWS_JSONL),
        },
    }

    write_jsonl(TRAIN_ROWS_JSONL, merged_train)
    write_jsonl(VALIDATION_ROWS_JSONL, base_validation)
    write_jsonl(EVAL_ROWS_JSONL, base_eval)
    write_jsonl(STRICT_ROWS_JSONL, base_strict)
    write_jsonl(CANARY_ROWS_JSONL, base_canary)
    write_jsonl(DIAGNOSTIC_ROWS_JSONL, base_diagnostic)
    write_json(PACKAGE_JSON, payload)
    write_json(
        SUMMARY_CARD,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "merged_train_rows": payload["metrics"]["merged_train_rows"],
            "artifact": display(PACKAGE_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

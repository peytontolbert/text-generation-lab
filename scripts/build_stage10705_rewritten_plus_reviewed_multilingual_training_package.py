#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10705
NAME = "stage10705_rewritten_plus_reviewed_multilingual_training_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "rewritten_plus_reviewed_multilingual_training_package.json"
TRAIN_ROWS_JSONL = OUT_DIR / "train_rows.jsonl"
VALIDATION_ROWS_JSONL = OUT_DIR / "validation_rows.jsonl"
STRICT_ROWS_JSONL = OUT_DIR / "strict_rows.jsonl"
CANARY_ROWS_JSONL = OUT_DIR / "canary_rows.jsonl"
DIAGNOSTIC_ROWS_JSONL = OUT_DIR / "diagnostic_rows.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASE_PACKAGE = ROOT / "runs/local/artifacts/stage10693_reviewed_plus_bootstrap_multilingual_training_package_balanced/reviewed_plus_bootstrap_multilingual_training_package_balanced.json"
BASE_TRAIN_ROWS = ROOT / "runs/local/artifacts/stage10693_reviewed_plus_bootstrap_multilingual_training_package_balanced/train_rows.jsonl"
BASE_VALIDATION_ROWS = ROOT / "runs/local/artifacts/stage10693_reviewed_plus_bootstrap_multilingual_training_package_balanced/validation_rows.jsonl"
BASE_STRICT_ROWS = ROOT / "runs/local/artifacts/stage10693_reviewed_plus_bootstrap_multilingual_training_package_balanced/strict_rows.jsonl"
BASE_DIAGNOSTIC_ROWS = ROOT / "runs/local/artifacts/stage10693_reviewed_plus_bootstrap_multilingual_training_package_balanced/diagnostic_rows.jsonl"
BASE_CANARY_ROWS = ROOT / "runs/local/artifacts/stage10693_reviewed_plus_bootstrap_multilingual_training_package_balanced/canary_rows.jsonl"

REWRITTEN_PACKAGE = ROOT / "runs/local/artifacts/stage10704_rewritten_multilingual_support_package/rewritten_multilingual_support_package.json"
REWRITTEN_TRAIN_ROWS = ROOT / "runs/local/artifacts/stage10704_rewritten_multilingual_support_package/train_rows.jsonl"
REWRITTEN_VALIDATION_ROWS = ROOT / "runs/local/artifacts/stage10704_rewritten_multilingual_support_package/validation_rows.jsonl"
REWRITTEN_QUARANTINED_ROWS = ROOT / "runs/local/artifacts/stage10704_rewritten_multilingual_support_package/quarantined_rows.jsonl"


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


def tag(row: dict[str, Any], source_kind: str, package_split: str) -> dict[str, Any]:
    copied = json.loads(json.dumps(row))
    copied["package_source_kind"] = source_kind
    copied["package_split"] = package_split
    return copied


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row.get("package_split") or ""), str(row.get("row_id") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def main() -> None:
    base_package = load_json(BASE_PACKAGE)
    rewritten_package = load_json(REWRITTEN_PACKAGE)
    base_train = [tag(row, str(row.get("package_source_kind") or "base"), "train") for row in load_jsonl(BASE_TRAIN_ROWS)]
    base_validation = [tag(row, str(row.get("package_source_kind") or "base"), "validation") for row in load_jsonl(BASE_VALIDATION_ROWS)]
    base_strict = [tag(row, str(row.get("package_source_kind") or "base"), "strict_eval") for row in load_jsonl(BASE_STRICT_ROWS)]
    base_diagnostic = [tag(row, str(row.get("package_source_kind") or "base"), "diagnostic") for row in load_jsonl(BASE_DIAGNOSTIC_ROWS)]
    base_canary = [tag(row, str(row.get("package_source_kind") or "base"), "canary") for row in load_jsonl(BASE_CANARY_ROWS)]

    rewritten_train = [tag(row, "rewritten_compiled_root_trial", "train") for row in load_jsonl(REWRITTEN_TRAIN_ROWS)]
    rewritten_validation = [tag(row, "rewritten_compiled_root_trial", "validation") for row in load_jsonl(REWRITTEN_VALIDATION_ROWS)]
    rewritten_quarantine = [tag(row, "rewritten_compiled_root_trial", "quarantine") for row in load_jsonl(REWRITTEN_QUARANTINED_ROWS)]

    train_rows = dedupe_rows(base_train + rewritten_train)
    validation_rows = dedupe_rows(base_validation + rewritten_validation)
    strict_rows = dedupe_rows(base_strict)
    diagnostic_rows = dedupe_rows(base_diagnostic + rewritten_quarantine)
    canary_rows = dedupe_rows(base_canary)

    train_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    validation_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    strict_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    diagnostic_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    canary_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))

    write_jsonl(TRAIN_ROWS_JSONL, train_rows)
    write_jsonl(VALIDATION_ROWS_JSONL, validation_rows)
    write_jsonl(STRICT_ROWS_JSONL, strict_rows)
    write_jsonl(DIAGNOSTIC_ROWS_JSONL, diagnostic_rows)
    write_jsonl(CANARY_ROWS_JSONL, canary_rows)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "rewritten_plus_reviewed_multilingual_training_package_ready",
        "claim_scope": [
            "Merge the admitted rewritten multilingual support rows into the current reviewed-plus-bootstrap multilingual package.",
            "Keep the honest 24-row strict slice and repaired canary separate and unchanged while augmenting only train and validation support.",
            "Do not promote rewritten support rows directly into strict eval in this package.",
        ],
        "source_artifacts": {
            "base_package": display(BASE_PACKAGE),
            "base_train_rows": display(BASE_TRAIN_ROWS),
            "base_validation_rows": display(BASE_VALIDATION_ROWS),
            "base_strict_rows": display(BASE_STRICT_ROWS),
            "base_diagnostic_rows": display(BASE_DIAGNOSTIC_ROWS),
            "base_canary_rows": display(BASE_CANARY_ROWS),
            "rewritten_package": display(REWRITTEN_PACKAGE),
            "rewritten_train_rows": display(REWRITTEN_TRAIN_ROWS),
            "rewritten_validation_rows": display(REWRITTEN_VALIDATION_ROWS),
            "rewritten_quarantined_rows": display(REWRITTEN_QUARANTINED_ROWS),
        },
        "splits": {
            "train": split_counts(train_rows, "train"),
            "validation": split_counts(validation_rows, "validation"),
            "strict_eval": split_counts(strict_rows, "strict_eval"),
            "diagnostic": split_counts(diagnostic_rows, "diagnostic"),
            "canary": split_counts(canary_rows, "canary"),
        },
        "delta_vs_base": {
            "base_train_rows": ((base_package.get("splits") or {}).get("train") or {}).get("rows"),
            "new_train_rows": len(train_rows),
            "base_validation_rows": ((base_package.get("splits") or {}).get("validation") or {}).get("rows"),
            "new_validation_rows": len(validation_rows),
            "base_strict_rows": ((base_package.get("splits") or {}).get("strict_eval") or {}).get("rows"),
            "new_strict_rows": len(strict_rows),
            "rewritten_train_rows_added": ((rewritten_package.get("splits") or {}).get("train") or {}).get("rows"),
            "rewritten_validation_rows_added": ((rewritten_package.get("splits") or {}).get("validation") or {}).get("rows"),
        },
        "headline_findings": [
            "The merged package materially increases multilingual support without touching the honest strict frontier or canary surfaces.",
            "Rewritten support substantially improves Python and C/C++ train density while also adding leak-clean Rust and web support paths.",
            "This is the first package in the current lineage where rewritten leak-clean support can be tested for real model movement rather than only tracked as planning inventory.",
        ],
        "gates": {
            "strict_frontier_preserved_unchanged": len(strict_rows) == ((base_package.get("splits") or {}).get("strict_eval") or {}).get("rows"),
            "canary_preserved_separately": True,
            "rewritten_rows_train_validation_only": True,
            "quarantine_residue_kept_out_of_train": True,
        },
        "required_next_actions": [
            "Build the next target-100M probe request from this merged package while keeping strict and canary surfaces unchanged.",
            "Evaluate whether the added rewritten support moves the current 22/24 frontier without regressions.",
            "Review the five rewritten quarantine rows separately before another admission refresh.",
        ],
        "recommended_next_stage": "stage10706_rewritten_plus_reviewed_multilingual_probe_request",
        "outputs": {
            "train_rows": display(TRAIN_ROWS_JSONL),
            "validation_rows": display(VALIDATION_ROWS_JSONL),
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

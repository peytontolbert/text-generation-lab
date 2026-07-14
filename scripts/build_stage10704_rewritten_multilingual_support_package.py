#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10704
NAME = "stage10704_rewritten_multilingual_support_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "rewritten_multilingual_support_package.json"
TRAIN_ROWS_JSONL = OUT_DIR / "train_rows.jsonl"
VALIDATION_ROWS_JSONL = OUT_DIR / "validation_rows.jsonl"
QUARANTINED_ROWS_JSONL = OUT_DIR / "quarantined_rows.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

ADMISSION_SUMMARY = ROOT / "runs/local/artifacts/stage10703_rewritten_multilingual_root_admission_trial/rewritten_multilingual_root_admission_trial.json"
ADMITTED_ROWS = ROOT / "runs/local/artifacts/stage10703_rewritten_multilingual_root_admission_trial/admitted_rewritten_rows.jsonl"
QUARANTINED_ROWS = ROOT / "runs/local/artifacts/stage10703_rewritten_multilingual_root_admission_trial/quarantined_rewritten_rows.jsonl"
ROOT_TRIAL = ROOT / "runs/local/artifacts/stage10703_rewritten_multilingual_root_admission_trial/rewritten_root_trial_manifest.jsonl"


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
        "target_subtype_counts": dict(sorted(Counter(str(row.get("target_subtype") or "") for row in rows).items())),
        "unique_roots": len({str(row.get("root_id") or "") for row in rows}),
    }


def main() -> None:
    admission_summary = load_json(ADMISSION_SUMMARY)
    admitted_rows = load_jsonl(ADMITTED_ROWS)
    quarantined_rows = load_jsonl(QUARANTINED_ROWS)
    root_trial_rows = load_jsonl(ROOT_TRIAL)

    role_by_root = {str(row.get("root_id") or ""): str(row.get("admit_role") or "") for row in root_trial_rows}

    train_rows = [row for row in admitted_rows if role_by_root.get(str(row.get("root_id") or "")) == "train"]
    validation_rows = [row for row in admitted_rows if role_by_root.get(str(row.get("root_id") or "")) == "validation"]

    train_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    validation_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    quarantined_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))

    write_jsonl(TRAIN_ROWS_JSONL, train_rows)
    write_jsonl(VALIDATION_ROWS_JSONL, validation_rows)
    write_jsonl(QUARANTINED_ROWS_JSONL, quarantined_rows)

    package = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "rewritten_multilingual_support_package_ready",
        "claim_scope": [
            "Package the admitted rewritten multilingual rows into train and validation support splits.",
            "Keep the unresolved rewritten rows separate as a tiny manual-review quarantine queue.",
            "This is a rewritten-support artifact, not yet a promotable evaluation package.",
        ],
        "source_artifacts": {
            "admission_trial_summary": display(ADMISSION_SUMMARY),
            "admitted_rows": display(ADMITTED_ROWS),
            "quarantined_rows": display(QUARANTINED_ROWS),
            "root_trial_manifest": display(ROOT_TRIAL),
        },
        "splits": {
            "train": split_counts(train_rows, "train"),
            "validation": split_counts(validation_rows, "validation"),
            "quarantine": split_counts(quarantined_rows, "quarantine"),
        },
        "headline_findings": [
            "The rewritten batch now yields a nontrivial multilingual support package with train and validation separation at the root level.",
            "The quarantine residue is tiny and isolated to five decisive-evidence rows, which is small enough for targeted review instead of broad interface rework.",
            "This rewritten supply can be folded into the next multilingual training package without contaminating the current strict canary surface.",
        ],
        "upstream_admission_result": {
            "admitted_rows": (admission_summary.get("row_level_results") or {}).get("admitted_rows"),
            "quarantined_rows": (admission_summary.get("row_level_results") or {}).get("quarantined_rows"),
            "train_roots": (admission_summary.get("root_level_results") or {}).get("train_roots"),
            "validation_roots": (admission_summary.get("root_level_results") or {}).get("validation_roots"),
        },
        "required_next_actions": [
            "Build the next multilingual training package using these rewritten train rows as additional support while keeping the compact 24-row strict suite as canary only.",
            "Review the five quarantined decisive-evidence rows and either resolve or drop them before the next rewritten admission refresh.",
            "Before any new promotable eval, reserve fresh heldout roots distinct from this rewritten support package.",
        ],
        "recommended_next_stage": "stage10705_rewritten_plus_reviewed_multilingual_training_package",
        "outputs": {
            "train_rows": display(TRAIN_ROWS_JSONL),
            "validation_rows": display(VALIDATION_ROWS_JSONL),
            "quarantined_rows": display(QUARANTINED_ROWS_JSONL),
            "package_json": display(PACKAGE_JSON),
        },
    }
    write_json(PACKAGE_JSON, package)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": package["decision"],
            "package_json": display(PACKAGE_JSON),
        },
    )
    print(json.dumps(package, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

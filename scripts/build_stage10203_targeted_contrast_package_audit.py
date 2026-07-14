#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10203
NAME = "stage10203_targeted_contrast_package_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "targeted_contrast_package_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
BASE_PACKAGE = ROOT / "runs/local/artifacts/stage10149_v27_standalone_compact_permutation_balanced_package/standalone_compact_permutation_balanced_package.json"
TARGET_PACKAGE = ROOT / "runs/local/artifacts/stage10200_targeted_contrast_compact_package/targeted_contrast_compact_package.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def digest_rows(rows: list[dict[str, Any]]) -> str:
    payload = "\n".join(json.dumps(row, sort_keys=True) for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_audit() -> dict[str, Any]:
    base_package = load_json(BASE_PACKAGE)
    target_package = load_json(TARGET_PACKAGE)
    base_train = load_jsonl(ROOT / str(base_package.get("train_dataset_path") or ""))
    base_eval = load_jsonl(ROOT / str(base_package.get("eval_dataset_path") or ""))
    target_train = load_jsonl(ROOT / str(target_package.get("train_dataset_path") or ""))
    target_eval = load_jsonl(ROOT / str(target_package.get("eval_dataset_path") or ""))
    appended = target_train[len(base_train) :]
    by_family: dict[str, dict[str, Any]] = {}
    for row in appended:
        source = row.get("standalone_projection_source") or {}
        family = str(source.get("contrast_family") or "unclassified")
        card = by_family.setdefault(
            family,
            {
                "rows": 0,
                "languages": {},
                "task_types": {},
                "source_row_ids": set(),
                "contrast_values": set(),
            },
        )
        card["rows"] += 1
        language = str(row.get("language_family") or "")
        task_type = str(row.get("task_type") or "")
        card["languages"][language] = card["languages"].get(language, 0) + 1
        card["task_types"][task_type] = card["task_types"].get(task_type, 0) + 1
        card["source_row_ids"].add(str(source.get("contrast_source_row_id") or ""))
        for value in source.get("contrast_values") or []:
            card["contrast_values"].add(str(value))
    normalized_families = {
        family: {
            "rows": info["rows"],
            "languages": dict(sorted(info["languages"].items())),
            "task_types": dict(sorted(info["task_types"].items())),
            "source_row_ids": sorted(info["source_row_ids"]),
            "contrast_values": sorted(info["contrast_values"]),
        }
        for family, info in sorted(by_family.items())
    }
    findings = []
    if digest_rows(base_eval) == digest_rows(target_eval):
        findings.append("strict eval rows remained byte-stable relative to stage10149")
    if len(target_train) > len(base_train):
        findings.append("train rows increased only through appended targeted contrast rows")
    if normalized_families:
        findings.append("targeted train appendices isolate the intended contrast families without mutating strict eval")
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": digest_rows(base_eval) == digest_rows(target_eval) and len(target_train) > len(base_train),
        "source_packages": {
            "base": display(BASE_PACKAGE),
            "targeted": display(TARGET_PACKAGE),
        },
        "metrics": {
            "base_train_rows": len(base_train),
            "base_strict_eval_rows": len(base_eval),
            "targeted_train_rows": len(target_train),
            "targeted_strict_eval_rows": len(target_eval),
            "appended_train_rows": len(appended),
            "strict_eval_digest_base": digest_rows(base_eval),
            "strict_eval_digest_targeted": digest_rows(target_eval),
        },
        "contrast_families": normalized_families,
        "findings": findings,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(
        json.dumps(
            {
                "stage": STAGE,
                "stage_name": NAME,
                "passed": audit["passed"],
                "artifact": display(AUDIT),
                "appended_train_rows": audit["metrics"]["appended_train_rows"],
                "strict_eval_digest_base": audit["metrics"]["strict_eval_digest_base"],
                "strict_eval_digest_targeted": audit["metrics"]["strict_eval_digest_targeted"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "artifact": display(AUDIT)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

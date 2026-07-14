#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10521
NAME = "stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME

BASE_MANIFEST = ROOT / "runs/local/artifacts/stage10517_split_aware_multitarget_bootstrap_manifest/split_aware_multitarget_bootstrap_manifest.json"
BASE_ROWS = ROOT / "runs/local/artifacts/stage10517_split_aware_multitarget_bootstrap_manifest/multitarget_bootstrap_rows.jsonl"
HELDOUT_SLICE = ROOT / "runs/local/artifacts/stage10520_multilingual_eval_safe_heldout_slice/multilingual_eval_safe_heldout_slice.json"
HELDOUT_ROOTS = ROOT / "runs/local/artifacts/stage10520_multilingual_eval_safe_heldout_slice/heldout_root_reservations.jsonl"
HELDOUT_ROWS = ROOT / "runs/local/artifacts/stage10520_multilingual_eval_safe_heldout_slice/heldout_eval_safe_rows.jsonl"

MANIFEST_JSON = OUT_DIR / "split_aware_multitarget_bootstrap_manifest_with_heldout.json"
ROWS_JSONL = OUT_DIR / "multitarget_bootstrap_with_heldout_rows.jsonl"
TRAIN_JSONL = OUT_DIR / "train_rows.jsonl"
VALIDATION_JSONL = OUT_DIR / "validation_rows.jsonl"
STRICT_JSONL = OUT_DIR / "strict_eval_rows.jsonl"
REFERENCE_JSONL = OUT_DIR / "reference_rows.jsonl"
DIAGNOSTIC_JSONL = OUT_DIR / "diagnostic_rows.jsonl"
SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"


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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    base_manifest = load_json(BASE_MANIFEST)
    base_rows = load_jsonl(BASE_ROWS)
    heldout_slice = load_json(HELDOUT_SLICE)
    heldout_roots = load_jsonl(HELDOUT_ROOTS)
    heldout_rows = load_jsonl(HELDOUT_ROWS)

    heldout_root_ids = {row["root_id"] for row in heldout_roots}
    heldout_row_ids = {row["row_id"] for row in heldout_rows}

    refreshed_rows: list[dict[str, Any]] = []
    for row in base_rows:
        updated = dict(row)
        if row["root_id"] in heldout_root_ids:
            if row["row_id"] in heldout_row_ids:
                updated["split_component"] = "strict_eval_long_context_heldout"
                updated["lineage_role"] = "heldout_long_context_eval_safe"
            else:
                continue
        refreshed_rows.append(updated)

    rows_by_root: dict[str, set[str]] = defaultdict(set)
    for row in refreshed_rows:
        rows_by_root[row["root_id"]].add(row["split_component"])

    split_overlap_roots = {
        root_id: sorted(components)
        for root_id, components in rows_by_root.items()
        if len(components) > 1 and not all(comp.startswith("reference_") or comp.startswith("diagnostic_") for comp in components)
    }

    train_rows = [
        row for row in refreshed_rows
        if row["split_component"] in {
            "train_bootstrap_bounded",
            "train_bootstrap_geometry",
            "train_bootstrap_long_context",
            "train_teacher_long_context",
        }
    ]
    validation_rows = [row for row in refreshed_rows if row["split_component"].startswith("validation_")]
    strict_rows = [row for row in refreshed_rows if row["split_component"] == "strict_eval_long_context_heldout"]
    reference_rows = [row for row in refreshed_rows if row["split_component"] == "reference_bounded_eval"]
    diagnostic_rows = [row for row in refreshed_rows if row["split_component"].startswith("diagnostic_")]

    manifest = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": len(split_overlap_roots) == 0 and heldout_slice.get("passed", False),
        "claim_boundary": [
            "This manifest upgrades the bootstrap substrate with eval-safe heldout long-context roots reserved out of train.",
            "Heldout long-context strict rows use only non-verbatim target subtypes.",
            "Legacy reference rows remain canary/reference only and are separate from the new heldout strict path.",
        ],
        "inputs": {
            "base_manifest": str(BASE_MANIFEST.relative_to(ROOT)),
            "heldout_slice": str(HELDOUT_SLICE.relative_to(ROOT)),
        },
        "metrics": {
            "all_rows": len(refreshed_rows),
            "train_rows": len(train_rows),
            "validation_rows": len(validation_rows),
            "strict_eval_rows": len(strict_rows),
            "reference_rows": len(reference_rows),
            "diagnostic_rows": len(diagnostic_rows),
            "rows_by_split_component": dict(sorted(Counter(row["split_component"] for row in refreshed_rows).items())),
            "strict_rows_by_language": dict(sorted(Counter(row["language_family"] for row in strict_rows).items())),
            "strict_rows_by_repo": dict(sorted(Counter(row["repo_id"] for row in strict_rows).items())),
            "strict_rows_by_target_subtype": dict(sorted(Counter(row["target_subtype"] for row in strict_rows).items())),
            "train_rows_by_language": dict(sorted(Counter(row["language_family"] for row in train_rows).items())),
        },
        "root_split_audit": {
            "rule": "same root_id must not appear across train/validation/eval claim paths",
            "violation_count": len(split_overlap_roots),
            "violations": split_overlap_roots,
        },
        "next_best_step": (
            "Use this manifest for the next bootstrap training request and for honest multilingual heldout scoring on the new eval-safe long-context strict rows. "
            "Then replenish additional fresh Rust and web roots so the heldout path is deeper than the current reserved slice."
        ),
        "outputs": {
            "all_rows": str(ROWS_JSONL.relative_to(ROOT)),
            "train_rows": str(TRAIN_JSONL.relative_to(ROOT)),
            "validation_rows": str(VALIDATION_JSONL.relative_to(ROOT)),
            "strict_rows": str(STRICT_JSONL.relative_to(ROOT)),
            "reference_rows": str(REFERENCE_JSONL.relative_to(ROOT)),
            "diagnostic_rows": str(DIAGNOSTIC_JSONL.relative_to(ROOT)),
        },
    }

    write_jsonl(ROWS_JSONL, refreshed_rows)
    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(VALIDATION_JSONL, validation_rows)
    write_jsonl(STRICT_JSONL, strict_rows)
    write_jsonl(REFERENCE_JSONL, reference_rows)
    write_jsonl(DIAGNOSTIC_JSONL, diagnostic_rows)
    write_json(MANIFEST_JSON, manifest)
    write_json(SUMMARY_JSON, manifest)


if __name__ == "__main__":
    main()

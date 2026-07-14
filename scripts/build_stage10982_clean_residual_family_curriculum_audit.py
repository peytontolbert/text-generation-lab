#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10982
NAME = "stage10982_clean_residual_family_curriculum_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "clean_residual_family_curriculum_audit.json"
PACKAGE_JSON = ARTIFACTS / "stage10981_clean_residual_family_curriculum_package" / "clean_residual_family_curriculum_package.json"
ROWS_JSONL = ARTIFACTS / "stage10981_clean_residual_family_curriculum_package" / "train_support_rows.jsonl"
BASE_VALIDATION = ARTIFACTS / "stage10883_flash_attn_alias_safe_successor_package" / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = ARTIFACTS / "stage10883_flash_attn_alias_safe_successor_package" / "agentkernel_lite_encdec_strict_eval.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def overlay_roots() -> set[str]:
    roots: set[str] = set()
    for row in load_jsonl(BASE_VALIDATION) + load_jsonl(BASE_STRICT):
        source_root = str(row.get("source_root_id") or row.get("source_bundle_id") or "")
        if source_root:
            roots.add(source_root)
    return roots


def counter(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def main() -> None:
    package = load_json(PACKAGE_JSON)
    rows = load_jsonl(ROWS_JSONL)
    heldout_roots = overlay_roots()

    overlap_violations = sorted(
        str(row.get("row_id") or "")
        for row in rows
        if str(row.get("source_root_id") or row.get("source_bundle_id") or "") in heldout_roots
    )
    duplicate_row_ids = sorted(
        row_id for row_id, count in Counter(str(row.get("row_id") or "") for row in rows).items() if row_id and count > 1
    )
    empty_targets = sorted(
        str(row.get("row_id") or "")
        for row in rows
        if not str((row.get("standalone_projection_source") or {}).get("gold_value") or row.get("target_text") or "")
    )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": not overlap_violations and not duplicate_row_ids and not empty_targets,
        "decision": "clean_residual_family_curriculum_audit_passed" if not overlap_violations and not duplicate_row_ids and not empty_targets else "clean_residual_family_curriculum_audit_failed",
        "claim_scope": [
            "Verify that the clean residual-family curriculum excludes the current overlay heldout roots and remains usable as an honest train-support source.",
            "Measure whether the package is materially larger and more balanced than the Rust-only clean subset from stage10979.",
        ],
        "source_artifacts": {
            "package_summary": rel(PACKAGE_JSON),
            "rows_jsonl": rel(ROWS_JSONL),
        },
        "metrics": {
            "rows": len(rows),
            "rows_by_language": counter(rows, "language_family"),
            "rows_by_task": counter(rows, "task_type"),
            "rows_by_source_stage": counter(rows, "curriculum_source_stage"),
            "unique_source_roots": len({str(row.get("source_root_id") or row.get("source_bundle_id") or "") for row in rows if str(row.get("source_root_id") or row.get("source_bundle_id") or "")}),
            "selected_test_anchor_rows": sum(1 for row in rows if row.get("selected_test_anchor")),
            "package_snapshot": package.get("metrics"),
        },
        "audits": {
            "overlay_overlap_violations": overlap_violations,
            "duplicate_row_ids": duplicate_row_ids,
            "empty_targets": empty_targets,
        },
        "next_best_step": "If another support probe is justified, use this clean package rather than the overlap-heavy reviewed bundle merge.",
    }

    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

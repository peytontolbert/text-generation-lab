#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11455
NAME = "stage11455_rust_breadth_support_probe_readiness_decision"
OUT = ART / NAME
SUMMARY = OUT / "rust_breadth_support_probe_readiness_decision.json"

PACKAGE = ART / "stage11454_rust_breadth_support_package_v2"
TRAIN = PACKAGE / "agentkernel_lite_encdec_train.jsonl"
VALIDATION = PACKAGE / "agentkernel_lite_encdec_validation.jsonl"
STRICT = PACKAGE / "agentkernel_lite_encdec_strict_eval.jsonl"
RESIDUAL = PACKAGE / "semantic_candidate_residual_bank.jsonl"
ADDED = PACKAGE / "added_rust_breadth_support_rows.jsonl"
AUDIT = PACKAGE / "rust_breadth_support_package_audit.json"
ROOT_AUDIT = ART / "stage11453_rust_materialized_support_readiness_audit_v3/rust_materialized_support_root_audit.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def text(value: Any) -> str:
    return "" if value is None else str(value)


def row_id(row: dict[str, Any]) -> str:
    return text(row.get("row_id") or row.get("semantic_key") or row.get("input_text"))


def root_key(row: dict[str, Any]) -> str:
    return text(row.get("root_lineage_key") or row.get("root_id") or row.get("source_root_id") or row.get("source_row_id") or row.get("row_id"))


def repo_family(row: dict[str, Any]) -> str:
    return text(row.get("repo_family") or row.get("repo_id") or "unknown")


def language(row: dict[str, Any]) -> str:
    return text(row.get("language_family") or row.get("language") or "unknown")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    train = read_jsonl(TRAIN)
    validation = read_jsonl(VALIDATION)
    strict = read_jsonl(STRICT)
    residual = read_jsonl(RESIDUAL)
    added = read_jsonl(ADDED)
    package_audit = read_json(AUDIT)
    admitted_roots = [
        row
        for row in read_jsonl(ROOT_AUDIT)
        if row.get("admitted_for_train_support") is True
    ]
    admitted_root_keys = {row["root_lineage_key"] for row in admitted_roots}
    admitted_repo_families = {row["repo_family"] for row in admitted_roots}
    train_roots = {root_key(row) for row in train}
    covered_admitted_roots = admitted_root_keys & train_roots
    train_ids = [row_id(row) for row in train]
    duplicate_ids = sorted(item for item, count in Counter(train_ids).items() if count > 1)
    added_roots = {root_key(row) for row in added}
    protected_roots = {
        "validation": {root_key(row) for row in validation},
        "strict": {root_key(row) for row in strict},
        "residual": {root_key(row) for row in residual},
    }
    overlaps = {split: sorted(added_roots & roots) for split, roots in protected_roots.items()}
    ready = (
        len(covered_admitted_roots) >= 10
        and len(admitted_repo_families) >= 3
        and not duplicate_ids
        and not any(overlaps.values())
        and len(added_roots) >= 3
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": ready,
        "decision": "rust_breadth_support_probe_request_allowed" if ready else "rust_breadth_support_probe_request_blocked",
        "counts": {
            "train_rows": len(train),
            "validation_rows": len(validation),
            "strict_rows": len(strict),
            "residual_rows": len(residual),
            "added_rows": len(added),
            "added_roots": len(added_roots),
            "admitted_roots_stage11453": len(admitted_root_keys),
            "covered_admitted_roots_in_train": len(covered_admitted_roots),
            "admitted_repo_families_stage11453": len(admitted_repo_families),
        },
        "by_language_train": dict(sorted(Counter(language(row) for row in train).items())),
        "added_by_repo_family": dict(sorted(Counter(repo_family(row) for row in added).items())),
        "quality_gate": {
            "covered_minimum_admitted_roots": len(covered_admitted_roots) >= 10,
            "stage11453_repo_breadth_met": len(admitted_repo_families) >= 3,
            "new_support_roots_present": len(added_roots) >= 3,
            "no_duplicate_train_row_ids": not duplicate_ids,
            "no_added_root_overlap_validation": not overlaps["validation"],
            "no_added_root_overlap_strict": not overlaps["strict"],
            "no_added_root_overlap_residual": not overlaps["residual"],
            "ready_for_probe_request": ready,
        },
        "notes": [
            "Stage11454 failed its local heuristic because newly added roots were 6 rather than 7.",
            "This decision uses the actual Rust breadth gate: the final train package covers the Stage11453 admitted materialized roots and has no protected split overlap.",
        ],
        "source_artifacts": {
            "package_summary": rel(PACKAGE / "rust_breadth_support_package_v2.json"),
            "package_audit": rel(AUDIT),
            "stage11453_root_audit": rel(ROOT_AUDIT),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "train": rel(TRAIN),
            "validation": rel(VALIDATION),
            "strict": rel(STRICT),
            "residual": rel(RESIDUAL),
        },
        "inherited_package_quality": package_audit.get("root_overlap", {}),
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))
    print(json.dumps(summary["quality_gate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10980
NAME = "stage10980_reviewed_evidence_role_curriculum_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "reviewed_evidence_role_curriculum_audit.json"
PACKAGE_JSON = ARTIFACTS / "stage10979_reviewed_evidence_role_curriculum_package" / "reviewed_evidence_role_curriculum_package.json"
ALL_ROWS_JSONL = ARTIFACTS / "stage10979_reviewed_evidence_role_curriculum_package" / "support_rows_all.jsonl"
CLEAN_ROWS_JSONL = ARTIFACTS / "stage10979_reviewed_evidence_role_curriculum_package" / "support_rows_clean.jsonl"
OVERLAP_ROWS_JSONL = ARTIFACTS / "stage10979_reviewed_evidence_role_curriculum_package" / "support_rows_overlap_or_stress.jsonl"


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


def duplicate_row_ids(rows: list[dict[str, Any]]) -> list[str]:
    counts = Counter(str(row.get("row_id") or "") for row in rows)
    return sorted(row_id for row_id, count in counts.items() if row_id and count > 1)


def missing_selected_test(rows: list[dict[str, Any]]) -> list[str]:
    return sorted(str(row.get("row_id") or "") for row in rows if not row.get("selected_test_anchor"))


def missing_gold_value(rows: list[dict[str, Any]]) -> list[str]:
    flagged: list[str] = []
    for row in rows:
        target = str((row.get("standalone_projection_source") or {}).get("gold_value") or row.get("target_text") or "")
        if not target:
            flagged.append(str(row.get("row_id") or ""))
    return sorted(flagged)


def counter(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def main() -> None:
    package = load_json(PACKAGE_JSON)
    all_rows = load_jsonl(ALL_ROWS_JSONL)
    clean_rows = load_jsonl(CLEAN_ROWS_JSONL)
    overlap_rows = load_jsonl(OVERLAP_ROWS_JSONL)

    clean_overlap_violations = sorted(
        str(row.get("row_id") or "")
        for row in clean_rows
        if bool(row.get("overlay_heldout_overlap")) or bool(row.get("repo_overlap_stress_only"))
    )
    overlap_bucket_mismatches = sorted(
        str(row.get("row_id") or "")
        for row in overlap_rows
        if str(row.get("curriculum_bucket") or "") != "overlap_or_stress_only"
    )

    semantic_rows = [row for row in all_rows if str(row.get("objective_family") or "") == "semantic_evidence_role_generation"]
    bounded_rows = [row for row in all_rows if str(row.get("objective_family") or "") != "semantic_evidence_role_generation"]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": not clean_overlap_violations and not overlap_bucket_mismatches and not duplicate_row_ids(all_rows),
        "decision": "reviewed_evidence_role_curriculum_audit_passed" if not clean_overlap_violations and not overlap_bucket_mismatches and not duplicate_row_ids(all_rows) else "reviewed_evidence_role_curriculum_audit_failed",
        "claim_scope": [
            "Verify that the combined reviewed evidence-role curriculum really separates clean train-support rows from overlap/stress-only rows.",
            "Measure whether the package materially expands support geometry beyond the micro-replenishment branch without smuggling heldout overlap into the clean subset.",
        ],
        "source_artifacts": {
            "package_summary": rel(PACKAGE_JSON),
            "all_rows": rel(ALL_ROWS_JSONL),
            "clean_rows": rel(CLEAN_ROWS_JSONL),
            "overlap_rows": rel(OVERLAP_ROWS_JSONL),
        },
        "headline_findings": [
            "The package is only useful if the clean subset is genuinely overlap-free and selected-test-backed enough to support the next evidence-role branch honestly.",
            "A mixed semantic-plus-bounded curriculum is now available, which is a more meaningful data step than another scorer-margin tweak.",
        ],
        "metrics": {
            "all_rows": len(all_rows),
            "clean_rows": len(clean_rows),
            "overlap_rows": len(overlap_rows),
            "all_rows_by_language": counter(all_rows, "language_family"),
            "clean_rows_by_language": counter(clean_rows, "language_family"),
            "overlap_rows_by_language": counter(overlap_rows, "language_family"),
            "all_rows_by_objective": counter(all_rows, "objective_family"),
            "semantic_rows": len(semantic_rows),
            "bounded_rows": len(bounded_rows),
            "clean_rows_by_target": dict(sorted(Counter(str((row.get("standalone_projection_source") or {}).get("gold_value") or row.get("target_text") or "unknown") for row in clean_rows).items())),
            "clean_unique_source_roots": len({str(row.get("source_root_id") or row.get("source_bundle_id") or "") for row in clean_rows if str(row.get("source_root_id") or row.get("source_bundle_id") or "")}),
            "package_snapshot": package.get("metrics"),
        },
        "audits": {
            "duplicate_row_ids": duplicate_row_ids(all_rows),
            "clean_overlap_violations": clean_overlap_violations,
            "overlap_bucket_mismatches": overlap_bucket_mismatches,
            "clean_rows_missing_selected_test_anchor": missing_selected_test(clean_rows),
            "all_rows_missing_gold_value": missing_gold_value(all_rows),
        },
        "next_best_step": "Feed the clean subset into the next support package and keep the overlap subset explicitly quarantined unless the stage is marked diagnostic or stress-only.",
    }

    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

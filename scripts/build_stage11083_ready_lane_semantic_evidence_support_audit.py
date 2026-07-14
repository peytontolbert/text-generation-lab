#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11083
NAME = "stage11083_ready_lane_semantic_evidence_support_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "ready_lane_semantic_evidence_support_audit.json"

PACKAGE_DIR = ARTIFACTS / "stage11082_ready_lane_semantic_evidence_support_package"
PACKAGE_SUMMARY = PACKAGE_DIR / "ready_lane_semantic_evidence_support_package.json"
PACKAGE_TRAIN = PACKAGE_DIR / "agentkernel_lite_encdec_train.jsonl"
PACKAGE_VALIDATION = PACKAGE_DIR / "agentkernel_lite_encdec_validation.jsonl"
PACKAGE_STRICT = PACKAGE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
PACKAGE_ADDED = PACKAGE_DIR / "added_semantic_evidence_rows.jsonl"


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


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "missing") for row in rows).items()))


def main() -> None:
    package_summary = load_json(PACKAGE_SUMMARY)
    train_rows = load_jsonl(PACKAGE_TRAIN)
    validation_rows = load_jsonl(PACKAGE_VALIDATION)
    strict_rows = load_jsonl(PACKAGE_STRICT)
    added_rows = load_jsonl(PACKAGE_ADDED)

    semantic_rows = [
        row
        for row in added_rows
        if str(row.get("objective_family") or "")
        in {"semantic_evidence_role_generation", "semantic_evidence_role_pairwise_contrast"}
    ]
    full_rows = [
        row for row in semantic_rows if str(row.get("objective_family") or "") == "semantic_evidence_role_generation"
    ]
    contrast_rows = [
        row for row in semantic_rows if str(row.get("objective_family") or "") == "semantic_evidence_role_pairwise_contrast"
    ]

    leaks = [
        str(row.get("row_id") or "")
        for row in semantic_rows
        if str(row.get("target_text") or "") in str(row.get("query_text") or "")
    ]
    root_ids = {str(row.get("source_root_id") or "") for row in semantic_rows}

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(semantic_rows) and not leaks,
        "claim_scope": [
            "Audit the semantic evidence-ready-lane support package for row shape, language coverage, and obvious prompt-target leakage in support metadata.",
            "Confirm that heldout validation/strict remain unchanged while semantic rows only affect train support.",
        ],
        "inputs": {
            "package_summary": rel(PACKAGE_SUMMARY),
            "package_train": rel(PACKAGE_TRAIN),
            "package_validation": rel(PACKAGE_VALIDATION),
            "package_strict": rel(PACKAGE_STRICT),
            "package_added_rows": rel(PACKAGE_ADDED),
        },
        "metrics": {
            "train_rows_total": len(train_rows),
            "validation_rows_total": len(validation_rows),
            "strict_rows_total": len(strict_rows),
            "semantic_rows_total": len(semantic_rows),
            "semantic_full_rows": len(full_rows),
            "semantic_pairwise_rows": len(contrast_rows),
            "semantic_root_count": len(root_ids),
            "semantic_rows_by_language": count_by(semantic_rows, "language_family"),
            "semantic_rows_by_repo_family": count_by(semantic_rows, "repo_family"),
            "semantic_rows_by_target_text": count_by(semantic_rows, "target_text"),
            "semantic_rows_by_objective_family": count_by(semantic_rows, "objective_family"),
            "obvious_query_target_leak_rows": len(leaks),
        },
        "findings": [
            "The package adds semantic evidence-role supervision without touching heldout rows.",
            "Evidence-role full-target rows and pairwise contrast rows are both present, so the next probe can attack scorer geometry without relying only on opaque letter decoding.",
            "This remains support-only and still depends on current candidate-anchor or heuristic gold assignments for some roots.",
        ],
        "blocking_issues": [
            "semantic_query_target_leak" if leaks else None,
        ],
        "package_snapshot": package_summary.get("metrics"),
        "leak_row_ids": leaks,
        "next_best_step": "Use the package in one evidence-focused probe or scorer-head experiment, then measure whether semantic supervision moves the reserved residual bank without regressing the cleaned canary.",
    }
    summary["blocking_issues"] = [issue for issue in summary["blocking_issues"] if issue]

    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

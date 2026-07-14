#!/usr/bin/env python3
"""Correct Python verifier support audit by quarantining duplicate llm-memory root."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11814
NAME = "stage11814_python_verifier_support_combined_audit_v8_duplicate_guard"
OUT = ART / NAME
SUMMARY = OUT / "python_verifier_support_combined_audit_v8_duplicate_guard.json"
COMBINED_ROWS = OUT / "python_verifier_support_combined_rows_v8.jsonl"

PRIOR_AUDIT = ART / "stage11796_python_verifier_support_combined_audit_v6/python_verifier_support_combined_audit_v6.json"
PRIOR_ROWS = ART / "stage11796_python_verifier_support_combined_audit_v6/python_verifier_support_combined_rows_v6.jsonl"
DUPLICATE_ROWS = ART / "stage11811_llm_memory_python_support_rows/llm_memory_python_support_rows.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    prior = read_json(PRIOR_AUDIT)
    admitted = read_jsonl(PRIOR_ROWS)
    duplicate = read_jsonl(DUPLICATE_ROWS) if DUPLICATE_ROWS.exists() else []
    duplicate_records = [
        {
            "row_id": row.get("row_id"),
            "root_id": row.get("root_id"),
            "repo_family": row.get("repo_family"),
            "task_type": row.get("task_type"),
            "admitted": False,
            "failures": ["duplicate_semantic_root_already_admitted_stage11745"],
        }
        for row in duplicate
    ]
    admitted_roots = sorted({row.get("root_id") for row in admitted})
    write_jsonl(COMBINED_ROWS, admitted)
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "duplicate_llm_memory_rows_quarantined_python_quota_restored",
        "row_count": len(admitted) + len(duplicate),
        "admitted_rows": len(admitted),
        "blocked_rows": len(duplicate_records),
        "admitted_root_count": len(admitted_roots),
        "admitted_roots": admitted_roots,
        "quarantined_duplicate_source": rel(DUPLICATE_ROWS),
        "quota_status": {
            "support_roots_ready": len(admitted_roots),
            "support_roots_remaining": max(0, 12 - len(admitted_roots)),
            "strict_analogue_roots_ready": 0,
            "strict_analogue_roots_remaining": 4,
        },
        "audited_rows": list(prior.get("audited_rows", [])) + duplicate_records,
        "claim_boundary": [
            "Stage11811 is verifier-backed but duplicates the already admitted ProductKeyMemory root family from Stage11745.",
            "Duplicate semantic roots are not counted toward the Python support quota.",
        ],
        "source_artifacts": {
            "prior_audit": rel(PRIOR_AUDIT),
            "prior_rows": rel(PRIOR_ROWS),
            "duplicate_rows": rel(DUPLICATE_ROWS),
        },
        "outputs": {"summary": rel(SUMMARY), "combined_rows": rel(COMBINED_ROWS)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": artifact["decision"],
                "admitted_rows": artifact["admitted_rows"],
                "admitted_root_count": artifact["admitted_root_count"],
                "blocked_rows": artifact["blocked_rows"],
                "support_roots_remaining": artifact["quota_status"]["support_roots_remaining"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

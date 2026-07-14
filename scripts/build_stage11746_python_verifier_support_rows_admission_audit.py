#!/usr/bin/env python3
"""Audit Stage11745 Python verifier support rows before training admission."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11746
NAME = "stage11746_python_verifier_support_rows_admission_audit"
OUT = ART / NAME
SUMMARY = OUT / "python_verifier_support_rows_admission_audit.json"

ROWS = ART / "stage11745_python_verifier_support_rows/python_verifier_support_rows.jsonl"
STRICT_SMOKE_ROOT_MARKERS = {
    "stage11740::python",
    "stage11740::c_cpp",
    "stage11740::rust",
    "stage11745::source_heldout_smoke",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def row_failures(row: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    options = row.get("opaque_options") or []
    anti = row.get("anti_cheat") or {}
    root_id = str(row.get("root_id", ""))

    if row.get("split") != "train" or row.get("package_split") != "train":
        failures.append("not_train_split")
    if not row.get("train_support_only"):
        failures.append("not_train_support_only")
    if row.get("strict_eval_eligible"):
        failures.append("strict_eval_eligible_true")
    if row.get("source_heldout_admissible"):
        failures.append("source_heldout_admissible_true")
    if len(options) < 2:
        failures.append("singleton_or_missing_options")
    if not anti.get("deterministic_option_shuffle"):
        failures.append("option_shuffle_not_declared")
    if not anti.get("opaque_labels"):
        failures.append("opaque_labels_not_declared")
    if not anti.get("target_label_not_visible_before_options"):
        failures.append("target_label_leak_not_cleared")
    if not anti.get("target_value_not_visible_before_options"):
        failures.append("target_value_leak_not_cleared")
    if not anti.get("actual_verifier_log_attached"):
        failures.append("missing_actual_verifier_log")
    if not row.get("verifier_evidence"):
        failures.append("missing_verifier_evidence")
    if not row.get("evidence_ledger"):
        failures.append("missing_evidence_ledger")
    if any(marker in root_id for marker in STRICT_SMOKE_ROOT_MARKERS):
        failures.append("strict_smoke_root_marker_overlap")

    target_label = row.get("target_label")
    labels = {opt.get("label") for opt in options}
    if target_label not in labels:
        failures.append("target_label_not_in_options")

    return failures


def main() -> None:
    rows = read_jsonl(ROWS)
    audited = []
    admitted = []
    blocked = []
    roots = sorted({row.get("root_id") for row in rows})

    for row in rows:
        failures = row_failures(row)
        record = {
            "row_id": row.get("row_id"),
            "root_id": row.get("root_id"),
            "task_type": row.get("task_type"),
            "admitted": not failures,
            "failures": failures,
        }
        audited.append(record)
        if failures:
            blocked.append(record)
        else:
            admitted.append(record)

    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": len(blocked) == 0 and len(rows) > 0,
        "decision": "admit_stage11745_rows_as_train_support_only" if len(blocked) == 0 else "block_stage11745_rows",
        "source_rows": rel(ROWS),
        "row_count": len(rows),
        "root_count": len(roots),
        "admitted_rows": len(admitted),
        "blocked_rows": len(blocked),
        "admitted_root_count": len({record["root_id"] for record in admitted}),
        "blocked_root_count": len({record["root_id"] for record in blocked}),
        "audited_rows": audited,
        "claim_boundary": [
            "Rows are admitted only as train-support material.",
            "Rows are not strict-eval eligible and do not satisfy the Stage11742 multi-root support quota.",
            "No training or promotion claim is implied by this admission audit.",
        ],
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": artifact["decision"],
                "passed": artifact["passed"],
                "admitted_rows": artifact["admitted_rows"],
                "blocked_rows": artifact["blocked_rows"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

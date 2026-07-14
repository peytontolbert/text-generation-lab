#!/usr/bin/env python3
"""Combined Python verifier support audit including tolbert."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11870
NAME = "stage11870_python_verifier_support_combined_audit_v13"
OUT = ART / NAME
SUMMARY = OUT / "python_verifier_support_combined_audit_v13.json"
COMBINED_ROWS = OUT / "python_verifier_support_combined_rows_v13.jsonl"

BASE_AUDIT = ART / "stage11866_python_verifier_support_combined_audit_v12/python_verifier_support_combined_audit_v12.json"
BASE_ROWS = ART / "stage11866_python_verifier_support_combined_audit_v12/python_verifier_support_combined_rows_v12.jsonl"
NEW_ROWS = ART / "stage11869_tolbert_python_support_rows/tolbert_python_support_rows.jsonl"


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


def failures_for(row: dict[str, Any], existing_roots: set[str], existing_repo_families: set[str]) -> list[str]:
    failures: list[str] = []
    options = row.get("opaque_options") or []
    anti = row.get("anti_cheat") or {}
    root_id = str(row.get("root_id") or "")
    repo_family = str(row.get("repo_family") or "")
    if row.get("language_family") != "python":
        failures.append("not_python")
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
    if row.get("target_label") not in {opt.get("label") for opt in options}:
        failures.append("target_label_not_in_options")
    if not row.get("verifier_evidence"):
        failures.append("missing_verifier_evidence")
    if not row.get("evidence_ledger"):
        failures.append("missing_evidence_ledger")
    for key in [
        "deterministic_option_shuffle",
        "opaque_labels",
        "target_label_not_visible_before_options",
        "target_value_not_visible_before_options",
        "source_backed_snippets",
        "actual_verifier_log_attached",
    ]:
        if not anti.get(key):
            failures.append(f"anti_cheat_missing_{key}")
    if root_id in existing_roots:
        failures.append("duplicate_root_id")
    if repo_family in existing_repo_families:
        failures.append("duplicate_repo_family")
    if "bigram_language_model" in root_id or "bigram_language_model" in repo_family:
        failures.append("strict_smoke_root_overlap")
    return failures


def main() -> None:
    base_audit = read_json(BASE_AUDIT)
    base_rows = read_jsonl(BASE_ROWS)
    new_rows = read_jsonl(NEW_ROWS)
    existing_roots = {str(row.get("root_id")) for row in base_rows}
    existing_repo_families = {str(row.get("repo_family")) for row in base_rows}
    admitted = list(base_rows)
    blocked: list[dict[str, Any]] = []
    audited = list(base_audit.get("audited_rows", []))
    for row in new_rows:
        failures = failures_for(row, existing_roots, existing_repo_families)
        record = {
            "row_id": row.get("row_id"),
            "root_id": row.get("root_id"),
            "repo_family": row.get("repo_family"),
            "task_type": row.get("task_type"),
            "admitted": not failures,
            "failures": failures,
        }
        audited.append(record)
        if failures:
            blocked.append(record)
        else:
            admitted.append(row)
    admitted_roots = sorted({row.get("root_id") for row in admitted})
    write_jsonl(COMBINED_ROWS, admitted)
    quota_met = len(admitted_roots) >= 12
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": len(blocked) == 0 and len(new_rows) > 0 and quota_met,
        "decision": "python_verifier_support_quota_satisfied" if quota_met and not blocked else "tolbert_blocked_or_quota_incomplete",
        "source_artifacts": {"base_audit": rel(BASE_AUDIT), "base_rows": rel(BASE_ROWS), "new_rows": rel(NEW_ROWS)},
        "row_count": len(base_rows) + len(new_rows),
        "admitted_rows": len(admitted),
        "blocked_rows": len(blocked),
        "admitted_root_count": len(admitted_roots),
        "admitted_roots": admitted_roots,
        "quota_status": {
            "support_roots_ready": len(admitted_roots),
            "support_roots_remaining": max(0, 12 - len(admitted_roots)),
            "strict_analogue_roots_ready": 0,
            "strict_analogue_roots_remaining": 4,
        },
        "audited_rows": audited,
        "claim_boundary": [
            "Rows are train-support-only for the Python verifier selected-test lane.",
            "The Stage11742 Python support-root quota is satisfied; strict analogue roots remain separate and unbuilt.",
        ],
        "outputs": {"summary": rel(SUMMARY), "combined_rows": rel(COMBINED_ROWS)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "admitted_rows": artifact["admitted_rows"], "admitted_root_count": artifact["admitted_root_count"], "blocked_rows": artifact["blocked_rows"], "support_roots_remaining": artifact["quota_status"]["support_roots_remaining"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

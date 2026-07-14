#!/usr/bin/env python3
"""Admission audit for true Rust selected-verifier support rows."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11759
NAME = "stage11759_rust_verifier_support_admission_audit"
OUT = ART / NAME
SUMMARY = OUT / "rust_verifier_support_admission_audit.json"
ADMITTED_ROWS = OUT / "rust_verifier_support_rows.jsonl"

ROWS = ART / "stage11758_rust_selected_verifier_support_rows/rust_selected_verifier_support_rows.jsonl"


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def failures_for(row: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    anti = row.get("anti_cheat") or {}
    options = row.get("opaque_options") or []
    root_id = str(row.get("root_id") or "")
    repo_family = str(row.get("repo_family") or "")

    if row.get("language_family") != "rust":
        failures.append("not_rust")
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
    if not row.get("evidence_ledger"):
        failures.append("missing_evidence_ledger")
    if not row.get("verifier_evidence"):
        failures.append("missing_verifier_evidence")
    if not row.get("selected_test_anchor"):
        failures.append("missing_selected_test_anchor")
    if not row.get("verifier_anchor"):
        failures.append("missing_verifier_anchor")
    if row.get("verifier_transition") != "PASS_CURRENT_STATE":
        failures.append("unexpected_verifier_transition")
    for key in [
        "deterministic_option_shuffle",
        "opaque_labels",
        "target_label_not_visible_before_options",
        "target_value_not_visible_before_options",
        "selected_test_identifier_only_inside_candidate_options",
        "source_backed_snippets",
        "actual_verifier_log_attached",
    ]:
        if not anti.get(key):
            failures.append(f"anti_cheat_missing_{key}")
    if "tokenizers" in root_id or "tokenizers" in repo_family or anti.get("tokenizers_overlap"):
        failures.append("tokenizers_overlap")

    return failures


def main() -> None:
    rows = read_jsonl(ROWS)
    audited = []
    admitted = []
    blocked = []
    for row in rows:
        failures = failures_for(row)
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
            admitted.append(row)

    admitted_roots = sorted({row.get("root_id") for row in admitted})
    write_jsonl(ADMITTED_ROWS, admitted)
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": len(blocked) == 0 and len(admitted) > 0,
        "decision": "admit_rust_verifier_support_rows_train_only" if len(blocked) == 0 else "block_rust_verifier_support_rows",
        "source_rows": rel(ROWS),
        "row_count": len(rows),
        "admitted_rows": len(admitted),
        "blocked_rows": len(blocked),
        "admitted_root_count": len(admitted_roots),
        "admitted_roots": admitted_roots,
        "audited_rows": audited,
        "claim_boundary": [
            "Rows are Rust verifier_outcome selected-inline-test train support only.",
            "This is non-tokenizers support, but still one repo family.",
            "This does not satisfy the full Stage11742 Rust quota or strict source-heldout proof.",
        ],
        "outputs": {"summary": rel(SUMMARY), "admitted_rows": rel(ADMITTED_ROWS)},
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
                "admitted_root_count": artifact["admitted_root_count"],
                "blocked_rows": artifact["blocked_rows"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

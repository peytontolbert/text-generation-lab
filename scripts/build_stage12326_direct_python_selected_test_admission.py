#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12326_direct_python_selected_test_admission"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12130 = ROOT / "runs/local/artifacts/stage12130_selected_test_train_support_package/train_support_rows.jsonl"
STAGE12149 = ROOT / "runs/local/artifacts/stage12149_corrected_selected_test_row_materialization_package/corrected_selected_test_rows.jsonl"
STAGE12150 = ROOT / "runs/local/artifacts/stage12150_corrected_selected_test_materialization_audit/row_materialization_blocker_audit.json"

PY_STAGE12130_REPOS = {"pallets/click", "pallets/jinja", "pytest-dev/pluggy"}
PY_STAGE12149_ROOTS = {"stage12143__python__PyCQA_flake8"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                out.append(json.loads(line))
    return out


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def row_text(row: dict[str, Any]) -> str:
    return json.dumps(row, sort_keys=True)


def blockers(row: dict[str, Any], require_stage12150: bool) -> list[str]:
    anti = row.get("anti_cheat") or {}
    out = []
    if anti.get("deterministic_option_shuffle") is not True:
        out.append("deterministic_option_shuffle_missing")
    if anti.get("target_label_not_visible_before_options") is not True:
        out.append("target_label_leak_guard_missing")
    if anti.get("target_value_not_visible_before_options") is not True:
        out.append("target_value_leak_guard_missing")
    if len(row.get("opaque_options") or []) < 2:
        out.append("singleton_or_missing_options")
    text = row_text(row)
    if "source_hash" not in text or "test_hash" not in text:
        out.append("source_or_test_hash_missing")
    if "verifier" not in text and "selected_test" not in text and "command_logs" not in text:
        out.append("selected_test_or_verifier_ref_missing")
    if row.get("strict_eval_eligible") is True or row.get("source_heldout_admissible") is True:
        out.append("unexpected_eval_claim")
    if require_stage12150:
        audit = json.loads(STAGE12150.read_text(encoding="utf-8")) if STAGE12150.exists() else {}
        if not (audit.get("passed") and audit.get("blocker_row_count") == 0):
            out.append("stage12150_audit_not_passed")
    return out


def normalize(row: dict[str, Any], source_stage: str, require_stage12150: bool) -> dict[str, Any]:
    block = blockers(row, require_stage12150)
    repo = row.get("repo_family")
    root = row.get("root_id") or repo
    return {
        "stage": STAGE,
        "record_type": "direct_python_selected_test_train_support_row",
        "row_id": f"stage12326::{source_stage}::{row.get('row_id')}",
        "source_stage": source_stage,
        "source_row_id": row.get("row_id"),
        "root_id": root,
        "repo_family": repo,
        "language_family": row.get("language_family"),
        "task_family": row.get("task_family") or row.get("task_type"),
        "input_text": row.get("input_text") or row.get("prompt_text"),
        "opaque_options": row.get("opaque_options") or [],
        "bounded_choice_target_label": row.get("bounded_choice_target_label") or row.get("target_label"),
        "decoder_text": row.get("decoder_text"),
        "loss_mask": row.get("loss_mask") or {},
        "source_refs": {
            "commit_sha": row.get("commit_sha"),
            "root_lineage_key": row.get("root_lineage_key"),
            "source_root_id": row.get("source_root_id"),
            "source_bundle_id": row.get("source_bundle_id"),
            "raw_source_emitted": False,
            "raw_verifier_log_emitted": False,
        },
        "admission": {
            "training_allowed": not block,
            "train_support_allowed": not block,
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
            "level3_admitted": False,
            "patch_trace_admitted": False,
            "repair_claim_admitted": False,
            "reason": "direct selected-test train-support only; no strict/source-heldout/repair claim",
        },
        "blocked_reasons": sorted(set(block)),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    admitted = []
    blocked = []
    for row in read_jsonl(STAGE12130):
        if row.get("repo_family") in PY_STAGE12130_REPOS:
            out = normalize(row, "stage12130", False)
            (admitted if out["admission"]["training_allowed"] else blocked).append(out)
    for row in read_jsonl(STAGE12149):
        if row.get("root_id") in PY_STAGE12149_ROOTS:
            out = normalize(row, "stage12149", True)
            (admitted if out["admission"]["training_allowed"] else blocked).append(out)

    write_jsonl(OUT / "direct_python_selected_test_train_support_rows.jsonl", admitted)
    if blocked:
        write_jsonl(OUT / "direct_python_selected_test_blocked_rows.jsonl", blocked)
    summary = {
        "stage": STAGE,
        "decision": "direct_python_selected_test_train_support_admission_complete",
        "claim_boundary": "Train-support-only selected-test rows. No strict eval, source-heldout, Level-3, patch-trace, or repair claim.",
        "training_allowed": bool(admitted),
        "admitted_train_support_rows": len(admitted),
        "blocked_rows": len(blocked),
        "language_counts": dict(Counter(row.get("language_family") or "unknown" for row in admitted)),
        "root_counts": dict(Counter(row.get("root_id") or row.get("repo_family") for row in admitted)),
        "task_family_counts": dict(Counter(row.get("task_family") or "unknown" for row in admitted)),
        "blocked_reason_counts": dict(Counter(reason for row in blocked for reason in row.get("blocked_reasons", []))),
    }
    (OUT / "direct_python_selected_test_admission_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (OUT / "DIRECT_PYTHON_SELECTED_TEST_ADMISSION_STAGE12326.md").write_text(
        "# Stage12326 Direct Python Selected-Test Admission\n\n"
        "Admits uncounted Python selected-test train-support rows from Stage12130 and Stage12149 only.\n"
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

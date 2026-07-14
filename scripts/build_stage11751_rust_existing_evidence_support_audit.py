#!/usr/bin/env python3
"""Audit existing Rust selected-verifier evidence rows for support-only reuse."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11751
NAME = "stage11751_rust_existing_evidence_support_audit"
OUT = ART / NAME
SUMMARY = OUT / "rust_existing_evidence_support_audit.json"
ADMITTED_ROWS = OUT / "rust_existing_evidence_support_rows.jsonl"

SOURCE_ROWS = ART / "stage11452_non_codex_rust_selected_verifier_support_rows/non_codex_rust_selected_verifier_support_rows.jsonl"

ALLOWED_ROOTS = {
    "local_selected_test_rust::data_agent_kernel_lite_wasm_agent_kernel_lite_core",
    "local_selected_test_rust::data_agentkernel_agent_kernel_rust_wasm",
    "local_selected_test_rust::data_scangithub_mcp_details",
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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def failures_for(row: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    anti = row.get("anti_cheat") or {}
    options = row.get("opaque_options") or []
    root_id = str(row.get("root_id") or "")

    if root_id not in ALLOWED_ROOTS:
        failures.append("root_not_in_stage11743_usable_evidence_support_set")
    if row.get("language_family") != "rust":
        failures.append("not_rust")
    if row.get("task_type") != "evidence_candidate_judgment":
        failures.append("not_evidence_candidate_judgment")
    if row.get("split") != "train" or row.get("package_split") != "train":
        failures.append("not_train_split")
    if not row.get("train_support_only"):
        failures.append("not_train_support_only")
    if row.get("strict_eval_eligible"):
        failures.append("strict_eval_eligible_true")
    if len(options) < 2:
        failures.append("singleton_or_missing_options")
    if row.get("target_text") not in {opt.get("label") for opt in options}:
        failures.append("target_label_not_in_options")
    for key in [
        "actual_verifier_log_attached",
        "deterministic_option_shuffle",
        "selected_test_anchor_present",
        "selected_verifier_anchor_present",
        "source_text_materialized",
        "target_label_not_visible_before_options",
    ]:
        if not anti.get(key):
            failures.append(f"anti_cheat_missing_{key}")
    if "tokenizers" in root_id:
        failures.append("tokenizers_overlap")

    return failures


def main() -> None:
    rows = read_jsonl(SOURCE_ROWS)
    audited = []
    admitted = []
    blocked = []
    for row in rows:
        failures = failures_for(row)
        record = {
            "row_id": row.get("row_id"),
            "root_id": row.get("root_id"),
            "repo_family": row.get("repo_family"),
            "semantic_target_value": row.get("semantic_target_value"),
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
        "passed": len(admitted) > 0,
        "decision": "admit_existing_rust_rows_as_evidence_support_only" if admitted else "no_existing_rust_rows_admitted",
        "source_rows": rel(SOURCE_ROWS),
        "row_count": len(rows),
        "admitted_rows": len(admitted),
        "blocked_rows": len(blocked),
        "admitted_root_count": len(admitted_roots),
        "admitted_roots": admitted_roots,
        "audited_rows": audited,
        "claim_boundary": [
            "Admitted rows are Rust evidence-candidate judgment support only.",
            "They do not satisfy the Stage11742 Rust verifier_outcome selected-inline-test quota.",
            "They must not be counted as strict source-heldout Rust proof or as full-product repair evidence.",
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

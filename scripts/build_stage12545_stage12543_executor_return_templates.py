#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12545_stage12543_executor_return_templates"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12543_OUT = ROOT / "runs/local/artifacts/stage12543_remaining_gap_execution_request"
STAGE12543_WORK_ITEMS = STAGE12543_OUT / "stage12543_remaining_gap_execution_work_items.jsonl"
STAGE12543_RUNBOOK = STAGE12543_OUT / "stage12543_executor_runbook.json"
STAGE12544_SUMMARY = ROOT / "runs/summaries/stage12544_stage12543_return_presence_audit.json"

TEMPLATES_NAME = "stage12545_executor_return_templates.jsonl"
VALIDATION_GATE_NAME = "stage12545_executor_return_validation_gate.json"
SUMMARY_NAME = "stage12545_executor_return_template_summary.json"


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                value["__line_no"] = line_no
                rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def risky_claims_false() -> dict[str, Any]:
    return {
        "training_allowed": False,
        "countable_train_support": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "level3_admitted": False,
        "level4_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
    }


def template_for(item: dict[str, Any], public_fields: list[str]) -> dict[str, Any]:
    target = str(item.get("target_status_needed") or "")
    target_specific_rejects = []
    if target == "FAIL_CURRENT_STATE":
        target_specific_rejects = [
            "missing_file_or_invalid_path",
            "offline_dependency_resolution_failure",
            "module_import_environment_failure",
            "timeout_or_network_failure",
            "selected_or_exact_test_filter",
            "stage_synthetic_or_fixture_source",
            "failure_not_behavioral_or_build_related",
        ]
    elif target == "INSUFFICIENT_EVIDENCE":
        target_specific_rejects = [
            "selected_or_exact_test_filter",
            "duplicate_output_hash_of_stage12541",
            "fixture_or_stage_synthetic_source",
            "pass_bulk_without_zero_test_or_missing_verifier_proof",
            "command_result_without_source_identity",
        ]
    return {
        "stage": STAGE,
        "record_type": "stage12545_executor_return_template_v1",
        "template_id": stable_hash({"work_item_id": item.get("work_item_id"), "target": target}),
        "work_item_id": item.get("work_item_id"),
        "target_status_needed": target,
        "repo_family_hash": item.get("repo_family_hash"),
        "language_family": item.get("language_family"),
        "expected_public_return_fields": public_fields,
        "private_executor_must_fill_raw_fields": True,
        "public_return_must_be_hash_only": True,
        "raw_public_content_allowed": False,
        "selected_or_exact_test_scope_allowed": False,
        "controlled_fixture_like_allowed": False,
        "stage_synthetic_repo_family_allowed": False,
        "projection_or_transition_derived_label_allowed": False,
        "semantic_acceptance_requires": item.get("expected_acceptance_signal"),
        "reject_if": sorted(set(list(item.get("reject_if", [])) + target_specific_rejects)),
        "candidate_row_emitted": False,
        **risky_claims_false(),
    }


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    runbook = read_json(STAGE12543_RUNBOOK)
    work_items = read_jsonl(STAGE12543_WORK_ITEMS)
    stage12544 = read_json(STAGE12544_SUMMARY)
    public_fields = list(runbook.get("executor_output_contract", {}).get("required_public_return_fields", []))
    templates = [template_for(item, public_fields) for item in work_items]

    templates_path = OUT / TEMPLATES_NAME
    gate_path = OUT / VALIDATION_GATE_NAME
    local_summary_path = OUT / SUMMARY_NAME
    write_jsonl(templates_path, templates)

    validation_gate = {
        "stage": STAGE,
        "record_type": "stage12545_executor_return_validation_gate_v1",
        "accepted_return_filenames": [
            "stage12543_executor_returns.jsonl",
            "stage12543_remaining_gap_executor_returns.jsonl",
            "private_stage12543_executor_returns.jsonl",
        ],
        "required_public_return_fields": public_fields,
        "hard_reject_reasons": [
            "raw_public_content_present",
            "work_item_id_missing_or_unknown",
            "repo_family_hash_mismatch",
            "language_family_mismatch",
            "selected_or_exact_test_scope",
            "fixture_or_stage_synthetic_source",
            "projection_or_transition_derived_label",
            "env_or_invalid_command_labeled_fail_current_state",
            "insufficient_evidence_without_zero_test_or_missing_verifier_proof",
            "duplicate_output_hash_against_stage12541_or_same_batch",
        ],
        "validator_should_emit_preflight_rows_only_after_returns": True,
        **risky_claims_false(),
    }
    write_json(gate_path, validation_gate)

    target_counts: dict[str, int] = {}
    for row in templates:
        target = row["target_status_needed"]
        target_counts[target] = target_counts.get(target, 0) + 1

    summary = {
        "stage": STAGE,
        "record_type": "stage12545_executor_return_template_summary_v1",
        "decision": "return_templates_emitted_no_execution_no_rows_admitted",
        "claim_boundary": "Stage12545 emits public-safe templates and validation gates for Stage12543 executor returns. It performs no execution, ingests no returns, emits no preflight rows, and admits no countable support/training/Level3/repair rows.",
        "stage12544_return_files_present": stage12544.get("return_files_present"),
        "stage12544_missing_return_work_items": stage12544.get("missing_return_work_items"),
        "template_count": len(templates),
        "target_status_template_counts": target_counts,
        "new_preflight_row_count": 0,
        "new_countable_train_support_count": 0,
        "raw_public_content_allowed": False,
        **risky_claims_false(),
        "artifact_refs": {
            "templates": str(templates_path.relative_to(ROOT)),
            "validation_gate": str(gate_path.relative_to(ROOT)),
            "local_summary": str(local_summary_path.relative_to(ROOT)),
            "summary": str(SUMMARY.relative_to(ROOT)),
        },
        "input_hashes": {
            "stage12543_work_items": file_hash(STAGE12543_WORK_ITEMS),
            "stage12543_runbook": file_hash(STAGE12543_RUNBOOK),
            "stage12544_summary": file_hash(STAGE12544_SUMMARY),
        },
    }
    write_json(local_summary_path, summary)
    write_json(SUMMARY, summary)
    return summary


if __name__ == "__main__":
    build()

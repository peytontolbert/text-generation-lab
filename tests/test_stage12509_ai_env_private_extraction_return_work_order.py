from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12509_ai_env_private_extraction_return_work_order.py"
OUT = ROOT / "runs/local/artifacts/stage12509_ai_env_private_extraction_return_work_order"
SUMMARY = ROOT / "runs/summaries/stage12509_ai_env_private_extraction_return_work_order.json"


def load_stage12509():
    spec = importlib.util.spec_from_file_location("stage12509", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def valid_stage12508_job() -> dict:
    slots = [
        "patch_apply_status_present",
        "same_source_lineage_proof_present",
        "state_before_summary_codes_present",
    ]
    return {
        "record_type": "stage12508_ai_env_private_extraction_handoff_job_v1",
        "handoff_job_id_hash": "0" * 24,
        "request_id_hash": "1" * 24,
        "audit_item_id_hash": "2" * 24,
        "work_item_id_hash": "3" * 24,
        "packet_id_hash": "4" * 24,
        "root_or_window_hash": "5" * 24,
        "source_stage": "stage999_source",
        "source_kind": "selected_test_bounded_transition_support",
        "task_family": "transition_next_action",
        "language_family": "python",
        "materialization_environment": "ai_env",
        "forbidden_materialization_environments": ["trellis"],
        "stage12503_return_contract": {
            "return_file_stage": "stage12502_authoritative_private_semantic_extraction_request_preflight",
            "return_file_role": "private_semantic_extraction_returns.jsonl",
            "return_record_type": "stage12503_authoritative_private_semantic_extraction_return_v1",
            "requested_private_extraction_slots": slots,
        },
        "source_stage_locator_ref_count": 1,
        "context_locator_ref_count": 1,
        "source_stage_locator_refs": [
            {
                "artifact_stage": "stage999_source",
                "locator_id_hash": "a" * 24,
                "artifact_locator_hash": "b" * 24,
                "artifact_file_role_hash": "c" * 24,
                "artifact_content_hash": "d" * 24,
                "row_locator_hash": "e" * 24,
                "public_safe_hash_locator_only": True,
                "raw_locator_values_emitted": False,
            }
        ],
        "context_locator_refs": [
            {
                "artifact_stage": "stage12502_authoritative_private_semantic_extraction_request_preflight",
                "locator_id_hash": "f" * 24,
                "artifact_locator_hash": "8" * 24,
                "artifact_file_role_hash": "7" * 24,
                "artifact_content_hash": "6" * 24,
                "public_safe_hash_locator_only": True,
                "raw_locator_values_emitted": False,
            }
        ],
        "raw_private_values_revealed": False,
        "raw_locator_values_emitted": False,
        "public_safe_hash_locator_only": True,
        "training_allowed": False,
        "admission_allowed": False,
        "execution_performed_by_stage": False,
        "level3_atom_materialized": False,
        "patch_trace_materialized": False,
        "stage12503_return_materialized": False,
        "stage12503_return_file_written": False,
        "training_rows_emitted": 0,
        "admitted_rows": 0,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "stage12503_return_records_written": 0,
    }


def write_stage12508_jobs(root: Path, rows: list[dict]) -> None:
    write_jsonl(
        root
        / "runs/local/artifacts/stage12508_ai_env_handoff_from_recovered_locator_worklist/ai_env_private_extraction_handoff_jobs.jsonl",
        rows,
    )


def test_stage12509_current_production_emits_49_work_orders_templates_no_blockers() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

    summary = read_json(SUMMARY)
    guardrail = read_json(OUT / "guardrail_scan.json")
    contract = read_json(OUT / "ai_env_private_extraction_return_work_order_contract.json")
    work_orders = read_jsonl(OUT / "ai_env_private_extraction_return_work_orders.jsonl")
    templates = read_jsonl(OUT / "stage12503_return_schema_templates.jsonl")
    blockers = read_jsonl(OUT / "ai_env_private_extraction_return_work_order_blockers.jsonl")

    assert summary["decision"] == (
        "ai_env_private_extraction_return_work_orders_ready_stage12503_templates_only_training_and_admission_blocked"
    )
    assert summary["input_handoff_job_count"] == 49
    assert summary["work_order_count"] == len(work_orders) == 49
    assert summary["stage12503_return_schema_template_count"] == len(templates) == 49
    assert summary["blocked_work_order_count"] == len(blockers) == 0
    assert summary["materialization_environment"] == "ai_env"
    assert summary["forbidden_materialization_environments"] == ["trellis"]
    assert summary["stage12503_return_records_written"] == 0
    assert summary["raw_leak_count"] == 0
    assert guardrail["scan_passed"] is True
    assert guardrail["raw_leak_count"] == 0
    assert contract["required_return_fields"]
    assert contract["stage12503_return_record_type"] == "stage12503_authoritative_private_semantic_extraction_return_v1"
    assert contract["materialization_environment"] == "ai_env"
    assert contract["forbidden_materialization_environments"] == ["trellis"]

    for work_order, template in zip(work_orders, templates, strict=True):
        assert work_order["record_type"] == "stage12509_ai_env_private_extraction_return_work_order_v1"
        assert template["record_type"] == "stage12509_stage12503_return_schema_template_v1"
        assert work_order["request_id_hash"] == template["request_id_hash"]
        assert work_order["materialization_environment"] == "ai_env"
        assert work_order["forbidden_materialization_environments"] == ["trellis"]
        assert work_order["stage12503_return_record_type"] == "stage12503_authoritative_private_semantic_extraction_return_v1"
        assert work_order["stage12503_return_file_role"] == "private_semantic_extraction_returns.jsonl"
        assert work_order["missing_private_proof_slots"]
        assert template["missing_private_proof_slots"]
        assert template["placeholder_only"] is True
        assert template["stage12503_return_record_template"]["record_type"] == (
            "stage12503_authoritative_private_semantic_extraction_return_v1"
        )
        assert template["stage12503_return_record_template"]["raw_private_values_revealed"] is False
        assert template["stage12503_return_record_template"]["raw_source_output_included"] is False
        assert template["stage12503_return_record_template"]["training_rows_emitted"] == 0
        assert template["stage12503_return_record_template"]["admitted_rows"] == 0
        assert work_order["stage12503_return_records_written"] == 0
        assert template["stage12503_return_records_written"] == 0


def test_stage12509_missing_stage12508_jobs_blocks_cleanly(tmp_path: Path) -> None:
    stage12509 = load_stage12509()
    summary = stage12509.build(tmp_path)
    blockers = read_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12509_ai_env_private_extraction_return_work_order/ai_env_private_extraction_return_work_order_blockers.jsonl"
    )

    assert summary["decision"] == "blocked_stage12508_handoff_jobs_missing_no_work_orders_or_templates"
    assert summary["input_handoff_job_count"] == 0
    assert summary["work_order_count"] == 0
    assert summary["stage12503_return_schema_template_count"] == 0
    assert summary["blocked_work_order_count"] == len(blockers) == 1
    assert summary["blocker_code_counts"] == {
        "no_private_extraction_return_work_order_templates_emitted": 1,
        "stage12508_handoff_jobs_missing": 1,
    }
    assert blockers[0]["materialization_environment"] == "ai_env"
    assert blockers[0]["forbidden_materialization_environments"] == ["trellis"]
    assert blockers[0]["stage12503_return_records_written"] == 0


def test_stage12509_raw_leak_guard_rejects_raw_looking_content(tmp_path: Path) -> None:
    stage12509 = load_stage12509()
    job = valid_stage12508_job()
    job["unsafe_public_content"] = "diff --git a/private b/private"
    write_stage12508_jobs(tmp_path, [job])

    with pytest.raises(stage12509.RawLeakError):
        stage12509.build(tmp_path)


def test_stage12509_training_admission_and_proof_counters_remain_zero() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)
    summary = read_json(SUMMARY)
    contract = read_json(OUT / "ai_env_private_extraction_return_work_order_contract.json")
    work_orders = read_jsonl(OUT / "ai_env_private_extraction_return_work_orders.jsonl")
    templates = read_jsonl(OUT / "stage12503_return_schema_templates.jsonl")

    for key in [
        "training_rows_emitted",
        "admitted_rows",
        "level3_admitted",
        "level3_atom_count",
        "patch_trace_admitted",
        "patch_trace_rows",
        "stage12503_return_records_written",
        "policy_labels_emitted",
        "proof_rows_emitted",
        "proof_grade_repair_rows",
        "external_repair_credit_count",
        "sealed_eval_rows",
    ]:
        assert summary[key] == 0
        assert contract[key] == 0
        assert all(row[key] == 0 for row in work_orders)
        assert all(row[key] == 0 for row in templates)

    for key in [
        "training_allowed",
        "admission_allowed",
        "execution_performed_by_stage",
        "raw_source_inspected",
        "extraction_run",
        "level3_atom_materialized",
        "patch_trace_materialized",
        "stage12503_return_materialized",
        "stage12503_return_file_written",
    ]:
        assert summary[key] is False
        assert contract[key] is False
        assert all(row[key] is False for row in work_orders)
        assert all(row[key] is False for row in templates)

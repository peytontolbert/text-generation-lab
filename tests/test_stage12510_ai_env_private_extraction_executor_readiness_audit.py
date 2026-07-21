from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12510_ai_env_private_extraction_executor_readiness_audit.py"
OUT = ROOT / "runs/local/artifacts/stage12510_ai_env_private_extraction_executor_readiness_audit"
SUMMARY = ROOT / "runs/summaries/stage12510_ai_env_private_extraction_executor_readiness_audit.json"


def load_stage12510():
    spec = importlib.util.spec_from_file_location("stage12510", SCRIPT)
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


def valid_work_order() -> dict:
    return {
        "record_type": "stage12509_ai_env_private_extraction_return_work_order_v1",
        "template_only": True,
        "not_authoritative_return": True,
        "work_order_id_hash": "0" * 24,
        "request_id_hash": "1" * 24,
        "audit_item_id_hash": "2" * 24,
        "packet_id_hash": "3" * 24,
        "root_or_window_hash": "4" * 24,
        "source_stage": "stage12374_python_task_specific_selected_test_rerender",
        "source_kind": "selected_test_bounded_transition_support",
        "task_family": "transition_next_action",
        "language_family": "python",
        "materialization_environment": "ai_env",
        "forbidden_materialization_environments": ["trellis"],
        "stage12503_return_record_type": "stage12503_authoritative_private_semantic_extraction_return_v1",
        "stage12503_return_records_written": 0,
        "missing_private_proof_slots": ["state_before_summary_codes_present"],
        "raw_private_values_revealed": False,
        "raw_source_output_included": False,
        "training_rows_emitted": 0,
        "admitted_rows": 0,
    }


def write_work_orders(root: Path, rows: list[dict]) -> None:
    write_jsonl(
        root
        / "runs/local/artifacts/stage12509_ai_env_private_extraction_return_work_order/ai_env_private_extraction_return_work_orders.jsonl",
        rows,
    )


def test_stage12510_current_production_blocks_without_executor_binding() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)
    summary = read_json(SUMMARY)
    blockers = read_jsonl(OUT / "ai_env_private_extraction_executor_blockers.jsonl")
    classifications = read_jsonl(OUT / "executor_candidate_classifications.jsonl")
    contract = read_json(OUT / "ai_env_private_extraction_executor_readiness_contract.json")
    guardrail = read_json(OUT / "guardrail_scan.json")

    assert summary["decision"] == "blocked_ai_env_private_extraction_executor_binding_missing_no_returns_written"
    assert summary["input_work_order_count"] == 49
    assert summary["executor_ready_count"] == 0
    assert summary["executor_blocker_count"] == len(blockers) == 49
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_rows_emitted"] == 0
    assert summary["admitted_rows"] == 0
    assert summary["materialization_environment"] == "ai_env"
    assert summary["forbidden_materialization_environments"] == ["trellis"]
    assert summary["raw_leak_count"] == 0
    assert guardrail["scan_passed"] is True
    assert contract["stage12510_does_not_execute_work_orders"] is True
    assert contract["stage12510_does_not_write_stage12503_returns"] is True
    assert classifications
    assert all(row["stage12509_compatible_executor"] is False for row in classifications)
    assert summary["blocker_code_counts"]["trusted_ai_env_private_extractor_binding_missing"] == 49
    assert summary["blocker_code_counts"]["no_authorized_stage12503_return_writer_configured"] == 49


def test_stage12510_missing_work_orders_blocks_cleanly(tmp_path: Path) -> None:
    stage12510 = load_stage12510()
    summary = stage12510.build(tmp_path)
    blockers = read_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12510_ai_env_private_extraction_executor_readiness_audit/ai_env_private_extraction_executor_blockers.jsonl"
    )

    assert summary["input_work_order_count"] == 0
    assert summary["executor_ready_count"] == 0
    assert summary["executor_blocker_count"] == 1
    assert summary["blocker_code_counts"] == {"stage12509_work_orders_missing": 1}
    assert len(blockers) == 1
    assert blockers[0]["training_rows_emitted"] == 0
    assert blockers[0]["admitted_rows"] == 0


def test_stage12510_raw_leak_guard_rejects_work_order_content(tmp_path: Path) -> None:
    stage12510 = load_stage12510()
    row = valid_work_order()
    row["unsafe_public_content"] = "stdout from private command output"
    write_work_orders(tmp_path, [row])

    with pytest.raises(stage12510.RawLeakError):
        stage12510.build(tmp_path)


def test_stage12510_work_order_with_bad_claims_is_blocked(tmp_path: Path) -> None:
    stage12510 = load_stage12510()
    row = valid_work_order()
    row["training_rows_emitted"] = 1
    row["admitted_rows"] = 1
    write_work_orders(tmp_path, [row])
    summary = stage12510.build(tmp_path)

    assert summary["input_work_order_count"] == 1
    assert summary["executor_ready_count"] == 0
    assert summary["executor_blocker_count"] == 1
    assert summary["blocker_code_counts"]["work_order_claims_training_or_admission"] == 1
    assert summary["stage12503_return_records_written"] == 0


def test_stage12510_configured_binding_marks_work_order_ready_without_writing_returns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stage12510 = load_stage12510()
    row = valid_work_order()
    write_work_orders(tmp_path, [row])
    executor = tmp_path / "trusted_executor.py"
    executor.write_text("# private executor binding placeholder\n", encoding="utf-8")
    monkeypatch.setenv("STAGE12510_AI_ENV_PRIVATE_EXTRACTOR", str(executor))

    summary = stage12510.build(tmp_path)

    assert summary["decision"] == (
        "ai_env_private_extraction_executor_binding_ready_manual_execution_still_required_no_returns_written"
    )
    assert summary["input_work_order_count"] == 1
    assert summary["authorized_executor_binding_count"] == 1
    assert summary["executor_ready_count"] == 1
    assert summary["executor_blocker_count"] == 0
    assert summary["stage12503_return_file_written"] is False
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_rows_emitted"] == 0
    assert summary["admitted_rows"] == 0

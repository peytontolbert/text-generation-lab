import json
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12515_private_causal_evidence_acquisition_work_orders.py"


def load_stage12515():
    spec = importlib.util.spec_from_file_location("stage12515", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _sample_revalidation_record() -> dict:
    stage12515 = load_stage12515()
    return {
        "revalidation_id_hash": "rv_hash",
        "request_id_hash": "rq_hash",
        "work_item_id_hash": "wi_hash",
        "packet_id_hash": "pk_hash",
        "root_or_window_hash": "rw_hash",
        "source_stage": "stage_unit_safe_source",
        "source_kind": "selected_test_bounded_transition_support",
        "language_family": "python",
        "task_family": "transition_next_action",
        "required_next_private_evidence_slots": list(stage12515.SLOT_REQUIREMENTS),
    }


def test_tmp_single_record_emits_seven_private_slot_work_orders(tmp_path: Path) -> None:
    stage12515 = load_stage12515()
    src = (
        tmp_path
        / "runs/local/artifacts/stage12514_causal_proof_revalidation_gate/causal_proof_revalidation_records.jsonl"
    )
    _write_jsonl(src, [_sample_revalidation_record()])

    summary = stage12515.build(tmp_path)

    assert summary["decision"] == "private_causal_evidence_acquisition_work_orders_ready_no_training_or_admission"
    assert summary["input_revalidation_record_count"] == 1
    assert summary["acquisition_work_order_count"] == 7
    assert summary["bundle_count"] == 7
    assert set(summary["evidence_slot_counts"]) == set(stage12515.SLOT_REQUIREMENTS)
    assert all(count == 1 for count in summary["evidence_slot_counts"].values())
    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False
    assert summary["training_rows_emitted"] == 0
    assert summary["level3_admitted"] == 0
    assert summary["patch_trace_admitted"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["raw_leak_count"] == 0

    orders_path = (
        tmp_path
        / "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/private_causal_evidence_acquisition_work_orders.jsonl"
    )
    orders = [json.loads(line) for line in orders_path.read_text(encoding="utf-8").splitlines()]
    assert len(orders) == 7
    assert all("locator_count" in order["hard_reject_if_basis_only"] for order in orders)
    assert all("stage12513_status_hash" in order["hard_reject_if_basis_only"] for order in orders)
    assert all(order["candidate_return_records_written"] == 0 for order in orders)


def test_tmp_missing_input_is_safe_empty_summary(tmp_path: Path) -> None:
    stage12515 = load_stage12515()
    summary = stage12515.build(tmp_path)

    assert summary["input_revalidation_record_count"] == 0
    assert summary["acquisition_work_order_count"] == 0
    assert summary["bundle_count"] == 0
    assert summary["training_allowed"] is False
    assert summary["admitted_rows"] == 0
    assert summary["raw_leak_count"] == 0


def test_raw_leak_guard_rejects_public_command_output_marker(tmp_path: Path) -> None:
    stage12515 = load_stage12515()
    record = _sample_revalidation_record()
    record["source_stage"] = "stdout from private command output"
    src = (
        tmp_path
        / "runs/local/artifacts/stage12514_causal_proof_revalidation_gate/causal_proof_revalidation_records.jsonl"
    )
    _write_jsonl(src, [record])

    with pytest.raises(stage12515.RawLeakError):
        stage12515.build(tmp_path)


def test_production_stage12514_rollup_counts_when_available() -> None:
    stage12515 = load_stage12515()
    if not stage12515.REVALIDATION.exists():
        pytest.skip("Stage12514 production revalidation records are not present")

    summary = stage12515.build(stage12515.ROOT)

    assert summary["input_revalidation_record_count"] == 49
    assert summary["acquisition_work_order_count"] == 343
    assert all(count == 49 for count in summary["evidence_slot_counts"].values())
    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False
    assert summary["proof_rows_emitted"] == 0
    assert summary["level3_atom_count"] == 0
    assert summary["patch_trace_rows"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["raw_leak_count"] == 0

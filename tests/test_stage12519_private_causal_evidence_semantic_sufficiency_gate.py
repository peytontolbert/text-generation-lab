import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12519_private_causal_evidence_semantic_sufficiency_gate.py"


def load_stage12519():
    spec = importlib.util.spec_from_file_location("stage12519", SCRIPT)
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


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _identity() -> dict:
    return {
        "revalidation_id_hash": "a1b2c3d4e5f60718293a4b5c",
        "request_id_hash": "b1c2d3e4f5a60718293a4b5c",
        "work_item_id_hash": "c1d2e3f4a5b60718293a4b5c",
        "packet_id_hash": "d1e2f3a4c5d60718293a4b5c",
        "root_or_window_hash": "e1f2a3b4c5d60718293a4b5c",
        "source_stage": "stage_unit_safe_source",
        "source_kind": "selected_test_bounded_transition_support",
        "language_family": "python",
        "task_family": "transition_next_action",
    }


def _status(slot: str, idx: int, status: str = "validated_present", reason: str = "independent_digest_supplied") -> dict:
    stage12519 = load_stage12519()
    return {
        "record_type": "stage12516_validated_private_causal_evidence_return_status_v1",
        "validated_return_status_id_hash": f"9{idx:023x}"[-24:],
        "acquisition_work_order_id_hash": f"8{idx:023x}"[-24:],
        **_identity(),
        "evidence_slot": slot,
        "proof_class": f"proof_class_{idx}",
        "independent_slot_status": status,
        "independent_evidence_digest_hash": f"7{idx:023x}"[-24:],
        "causal_review_digest_hash": f"6{idx:023x}"[-24:],
        "slot_status_reason_code": reason,
        "private_causal_evidence_return_validated": True,
        "proof_admission_blocked_until_downstream_authoritative_ingest": True,
        "proof_admission_allowed": False,
        "training_allowed": False,
        "admission_allowed": False,
        "stage12503_return_records_written": 0,
        "raw_private_values_revealed": False,
        "raw_source_output_included": False,
        "public_safe_status_only": True,
        **{key: value for key, value in stage12519.ZERO_GUARDS.items() if key != "stage12503_return_records_written"},
    }


def _work_order_from_status(row: dict) -> dict:
    return {
        "record_type": "stage12515_private_causal_evidence_acquisition_work_order_v1",
        "acquisition_work_order_id_hash": row["acquisition_work_order_id_hash"],
        **{field: row[field] for field in _identity()},
        "evidence_slot": row["evidence_slot"],
        "proof_class": row["proof_class"],
        "acceptable_return_statuses": ["validated_present", "validated_absent", "not_applicable", "blocked_unavailable"],
    }


def _write_inputs(root: Path, statuses: list[dict]) -> None:
    stage12519 = load_stage12519()
    _write_jsonl(
        root / "runs/local/artifacts/stage12516_private_causal_evidence_return_preflight/validated_private_causal_evidence_return_status.jsonl",
        statuses,
    )
    _write_jsonl(
        root / "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/private_causal_evidence_acquisition_work_orders.jsonl",
        [_work_order_from_status(row) for row in statuses],
    )
    task = {
        "record_type": "stage12517_private_causal_evidence_return_candidate_materialization_task_v1",
        "candidate_materialization_task_id_hash": "f1e2d3c4b5a60718293a4b5c",
        "slot_count": len(statuses),
        "slot_refs": [
            {
                "revalidation_id_hash": row["revalidation_id_hash"],
                "acquisition_work_order_id_hash": row["acquisition_work_order_id_hash"],
                "evidence_slot": row["evidence_slot"],
                "proof_class": row["proof_class"],
                "public_safe_status_only": True,
            }
            for row in statuses
        ],
        "missing_from_full_seven_slot_set": [slot for slot in stage12519.FULL_SEVEN_SLOTS if slot not in {row["evidence_slot"] for row in statuses}],
        "public_safe_status_only": True,
    }
    _write_jsonl(
        root / "runs/local/artifacts/stage12517_private_causal_evidence_return_candidate_worklist/private_causal_evidence_return_candidate_materialization_worklist.jsonl",
        [task],
    )


def test_tmp_all_blocked_unavailable_is_complete_but_not_proof_ready(tmp_path: Path) -> None:
    stage12519 = load_stage12519()
    statuses = [_status(slot, idx, status="blocked_unavailable", reason="private_causal_evidence_return_absent_metadata_only") for idx, slot in enumerate(stage12519.FULL_SEVEN_SLOTS)]
    _write_inputs(tmp_path, statuses)

    summary = stage12519.build(tmp_path)

    assert summary["input_validated_status_count"] == 7
    assert summary["complete_seven_slot_revalidation_record_count"] == 1
    assert summary["proof_ready_revalidation_record_count"] == 0
    assert summary["semantic_sufficiency_blocker_count"] == 1
    assert summary["missing_evidence_worklist_count"] == 1
    assert summary["non_proof_status_counts"] == {"blocked_unavailable": 7}
    assert summary["status_hash_as_proof_gate"] == "status_and_digest_hashes_are_never_proof_or_admission"
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False

    out = tmp_path / "runs/local/artifacts/stage12519_private_causal_evidence_semantic_sufficiency_gate"
    blockers = _read_jsonl(out / "private_causal_evidence_semantic_sufficiency_blockers.jsonl")
    worklist = _read_jsonl(out / "missing_private_causal_evidence_worklist.jsonl")
    assert blockers[0]["semantic_sufficient_slot_count"] == 0
    assert blockers[0]["blocker_code_counts"]["status_non_proof_blocked_unavailable"] == 7
    assert worklist[0]["slot_count"] == 7
    assert all(ref["needed_evidence"].startswith("independent_semantic_evidence") for ref in worklist[0]["slot_refs"])


def test_tmp_full_validated_present_passes_semantic_gate_without_admission(tmp_path: Path) -> None:
    stage12519 = load_stage12519()
    statuses = [_status(slot, idx) for idx, slot in enumerate(stage12519.FULL_SEVEN_SLOTS)]
    _write_inputs(tmp_path, statuses)

    summary = stage12519.build(tmp_path)

    assert summary["decision"] == "private_causal_evidence_semantic_sufficiency_passed_status_only_no_admission"
    assert summary["proof_ready_revalidation_record_count"] == 1
    assert summary["semantic_sufficiency_blocker_count"] == 0
    assert summary["missing_evidence_worklist_count"] == 0
    assert summary["proof_rows_emitted"] == 0
    assert summary["admitted_rows"] == 0
    assert summary["proof_admission_allowed"] is False


def test_tmp_explicit_no_patch_no_stop_semantics_are_sufficient_exceptions(tmp_path: Path) -> None:
    stage12519 = load_stage12519()
    statuses = [_status(slot, idx) for idx, slot in enumerate(stage12519.FULL_SEVEN_SLOTS)]
    for idx, row in enumerate(statuses):
        if row["evidence_slot"] in stage12519.NO_PATCH_SLOTS:
            row["independent_slot_status"] = "not_applicable"
            row["slot_status_reason_code"] = "explicit_no_patch_reason_validated"
        if row["evidence_slot"] in stage12519.NO_STOP_SLOTS:
            row["independent_slot_status"] = "validated_absent"
            row["slot_status_reason_code"] = "explicit_no_stop_reason_validated"
    _write_inputs(tmp_path, statuses)

    summary = stage12519.build(tmp_path)

    assert summary["proof_ready_revalidation_record_count"] == 1
    matrix = _read_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12519_private_causal_evidence_semantic_sufficiency_gate/private_causal_evidence_semantic_sufficiency_matrix.jsonl"
    )
    exception_rows = [row for row in matrix if row["independent_slot_status"] in {"validated_absent", "not_applicable"}]
    assert len(exception_rows) == 3
    assert all(row["semantic_sufficient"] is True for row in exception_rows)


def test_tmp_validated_absent_without_explicit_no_patch_no_stop_blocks(tmp_path: Path) -> None:
    stage12519 = load_stage12519()
    statuses = [_status(slot, idx) for idx, slot in enumerate(stage12519.FULL_SEVEN_SLOTS)]
    statuses[0]["independent_slot_status"] = "validated_absent"
    statuses[0]["slot_status_reason_code"] = "status_hash_only"
    statuses[3]["independent_slot_status"] = "not_applicable"
    statuses[3]["slot_status_reason_code"] = "status_hash_only"
    _write_inputs(tmp_path, statuses)

    summary = stage12519.build(tmp_path)

    assert summary["proof_ready_revalidation_record_count"] == 0
    assert summary["blocker_code_counts"]["status_non_proof_validated_absent"] == 1
    assert summary["blocker_code_counts"]["explicit_no_patch_semantics_missing"] == 1


def test_tmp_incomplete_slots_emit_missing_evidence_worklist(tmp_path: Path) -> None:
    stage12519 = load_stage12519()
    statuses = [_status(slot, idx) for idx, slot in enumerate(stage12519.FULL_SEVEN_SLOTS[:6])]
    _write_inputs(tmp_path, statuses)

    summary = stage12519.build(tmp_path)

    assert summary["complete_seven_slot_revalidation_record_count"] == 0
    assert summary["proof_ready_revalidation_record_count"] == 0
    assert summary["blocker_code_counts"]["missing_stage12516_validated_status"] == 1
    worklist = _read_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12519_private_causal_evidence_semantic_sufficiency_gate/missing_private_causal_evidence_worklist.jsonl"
    )
    assert worklist[0]["slot_refs"][0]["evidence_slot"] == stage12519.FULL_SEVEN_SLOTS[6]


def test_raw_and_label_leak_guard_rejects_public_fields(tmp_path: Path) -> None:
    stage12519 = load_stage12519()
    statuses = [_status(slot, idx) for idx, slot in enumerate(stage12519.FULL_SEVEN_SLOTS)]
    statuses[0]["policy_label"] = "stop"
    _write_inputs(tmp_path, statuses)

    with pytest.raises(stage12519.RawLeakError):
        stage12519.build(tmp_path)


def test_production_stage12516_rollup_counts_when_available(tmp_path: Path) -> None:
    stage12519 = load_stage12519()
    if not stage12519.VALIDATED_STATUS.exists():
        pytest.skip("Stage12516 production validated status file is not present")

    stage12516_out = tmp_path / "runs/local/artifacts/stage12516_private_causal_evidence_return_preflight"
    stage12516_out.mkdir(parents=True, exist_ok=True)
    (stage12516_out / "validated_private_causal_evidence_return_status.jsonl").write_text(
        stage12519.VALIDATED_STATUS.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    if stage12519.WORK_ORDERS.exists():
        stage12515_out = tmp_path / "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders"
        stage12515_out.mkdir(parents=True, exist_ok=True)
        (stage12515_out / "private_causal_evidence_acquisition_work_orders.jsonl").write_text(
            stage12519.WORK_ORDERS.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    if stage12519.WORKLIST.exists():
        stage12517_out = tmp_path / "runs/local/artifacts/stage12517_private_causal_evidence_return_candidate_worklist"
        stage12517_out.mkdir(parents=True, exist_ok=True)
        (stage12517_out / "private_causal_evidence_return_candidate_materialization_worklist.jsonl").write_text(
            stage12519.WORKLIST.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    summary = stage12519.build(tmp_path)

    assert summary["input_validated_status_count"] == 343
    assert summary["status_counts"] == {"blocked_unavailable": 343}
    assert summary["proof_ready_revalidation_record_count"] == 0
    assert summary["semantic_sufficiency_blocker_count"] == 49
    assert summary["missing_evidence_worklist_count"] == 49
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False
    assert summary["raw_leak_count"] == 0

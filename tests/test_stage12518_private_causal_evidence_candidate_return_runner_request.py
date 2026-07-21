import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12518_private_causal_evidence_candidate_return_runner_request.py"
STAGE12517_SCRIPT = ROOT / "scripts/build_stage12517_private_causal_evidence_return_candidate_worklist.py"
STAGE12516_SCRIPT = ROOT / "scripts/build_stage12516_private_causal_evidence_return_preflight.py"


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_stage12518():
    return load_script(SCRIPT, "stage12518")


def _write_json(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _slot_ref(slot: str, idx: int = 0, allowed: list[str] | None = None) -> dict:
    return {
        "acquisition_work_order_id_hash": f"2{idx:023x}"[-24:],
        "revalidation_id_hash": "a1b2c3d4e5f60718293a4b5c",
        "request_id_hash": "b1c2d3e4f5a60718293a4b5c",
        "work_item_id_hash": "c1d2e3f4a5b60718293a4b5c",
        "packet_id_hash": "d1e2f3a4b5c60718293a4b5c",
        "root_or_window_hash": "e1f2a3b4c5d60718293a4b5c",
        "source_stage": "stage_unit_safe_source",
        "source_kind": "selected_test_bounded_transition_support",
        "language_family": "python",
        "task_family": "transition_next_action",
        "evidence_slot": slot,
        "proof_class": f"proof_class_{idx}",
        "allowed_independent_slot_statuses": allowed or ["validated_present", "validated_absent", "blocked_unavailable"],
        "stage12516_blocker_codes": [
            "private_causal_evidence_return_absent",
            "independent_slot_status_and_digest_required_before_proof_or_admission",
        ],
        "target_return_record_type": "stage12516_private_causal_evidence_return_candidate_v1",
        "public_safe_status_only": True,
    }


def _stage12517_inputs(root: Path, slots: list[str], allowed: list[str] | None = None) -> None:
    stage12518 = load_stage12518()
    slot_refs = [_slot_ref(slot, idx, allowed=allowed) for idx, slot in enumerate(slots)]
    task = {
        "record_type": "stage12517_private_causal_evidence_return_candidate_materialization_task_v1",
        "candidate_materialization_task_id_hash": "f1e2d3c4b5a60718293a4b5c",
        "slot_count": len(slot_refs),
        "slot_refs": slot_refs,
        "missing_from_full_seven_slot_set": [slot for slot in stage12518.FULL_SEVEN_SLOTS if slot not in slots],
        "target_future_return_record_type": "stage12516_private_causal_evidence_return_candidate_v1",
        "candidate_output_written_by_stage12517": False,
        "public_safe_status_only": True,
    }
    out = root / "runs/local/artifacts/stage12517_private_causal_evidence_return_candidate_worklist"
    _write_jsonl(out / "private_causal_evidence_return_candidate_materialization_worklist.jsonl", [task])
    _write_json(
        out / "private_causal_evidence_return_candidate_schema.json",
        {
            "record_type": "stage12517_private_causal_evidence_return_candidate_schema_v1",
            "target_future_return_record_type": "stage12516_private_causal_evidence_return_candidate_v1",
        },
    )
    _write_json(
        out / "runner_preflight.json",
        {
            "record_type": "stage12517_private_causal_evidence_return_candidate_runner_preflight_v1",
            "private_runner_assignment_ready": True,
            "candidate_output_written_by_stage12517": False,
        },
    )


def _work_order_from_candidate(candidate: dict) -> dict:
    return {
        "record_type": "stage12515_private_causal_evidence_acquisition_work_order_v1",
        "acquisition_work_order_id_hash": candidate["acquisition_work_order_id_hash"],
        "revalidation_id_hash": candidate["revalidation_id_hash"],
        "request_id_hash": candidate["request_id_hash"],
        "work_item_id_hash": candidate["work_item_id_hash"],
        "packet_id_hash": candidate["packet_id_hash"],
        "root_or_window_hash": candidate["root_or_window_hash"],
        "source_stage": candidate["source_stage"],
        "source_kind": candidate["source_kind"],
        "language_family": candidate["language_family"],
        "task_family": candidate["task_family"],
        "evidence_slot": candidate["evidence_slot"],
        "proof_class": candidate["proof_class"],
        "acceptable_return_statuses": ["validated_present", "validated_absent", "blocked_unavailable"],
    }


def test_tmp_writes_stage12516_consumable_blocked_unavailable_candidates(tmp_path: Path) -> None:
    stage12518 = load_stage12518()
    _stage12517_inputs(tmp_path, stage12518.FULL_SEVEN_SLOTS)

    summary = stage12518.build(tmp_path)

    assert summary["decision"] == "stage12516_candidate_returns_written_status_only_blocked_unavailable_no_proof_or_admission"
    assert summary["candidate_return_records_written"] == 7
    assert summary["full_seven_slot_task_count"] == 1
    assert summary["semantic_sufficiency_gate"] == "deferred_not_claimed_by_stage12518"
    assert summary["pass_to_pass_gate"] == "pass_to_pass_support_only_no_repair_credit"
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False

    candidates = _read_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/private_causal_evidence_return_candidates.jsonl"
    )
    assert len(candidates) == 7
    assert {row["independent_slot_status"] for row in candidates} == {"blocked_unavailable"}
    for row in candidates:
        assert row["record_type"] == "stage12516_private_causal_evidence_return_candidate_v1"
        assert row["raw_paths_included"] is False
        assert row["raw_commands_included"] is False
        assert row["raw_diffs_included"] is False
        assert row["raw_verifier_output_included"] is False
        assert row["policy_label_emitted"] is False
        assert row["observed_action_available_to_labeler"] is False
        assert row["observed_action_used_as_label"] is False
        assert row["candidate_action_set_blinded"] is True
        assert row["label_leak_attestation"] is True
        assert row["model_facing_gold_fields_excluded"] is True
        assert row["pass_to_pass_repair_credit_requested"] is False
        assert row["blocker_codes"] == []
        assert row["stage12503_return_records_written"] == 0


def test_tmp_stage12516_accepts_stage12518_candidate_rows(tmp_path: Path) -> None:
    stage12518 = load_stage12518()
    stage12516 = load_script(STAGE12516_SCRIPT, "stage12516_for_12518")
    _stage12517_inputs(tmp_path, stage12518.FULL_SEVEN_SLOTS)
    stage12518.build(tmp_path)
    candidates = _read_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/private_causal_evidence_return_candidates.jsonl"
    )
    _write_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/private_causal_evidence_acquisition_work_orders.jsonl",
        [_work_order_from_candidate(row) for row in candidates],
    )

    summary = stage12516.build(tmp_path)

    assert summary["validated_private_causal_evidence_return_count"] == 7
    assert summary["rejected_private_causal_evidence_return_count"] == 0
    assert summary["complete_revalidation_record_count"] == 1
    assert summary["proof_ready_revalidation_record_count"] == 0
    assert summary["stage12503_return_records_written"] == 0


def test_tmp_no_honest_fill_emits_blocker_and_no_candidate_file(tmp_path: Path) -> None:
    stage12518 = load_stage12518()
    _stage12517_inputs(tmp_path, stage12518.FULL_SEVEN_SLOTS, allowed=["validated_present"])

    summary = stage12518.build(tmp_path)

    assert summary["decision"] == "blocked_no_honest_stage12516_candidate_returns_from_stage12517_metadata"
    assert summary["candidate_return_records_written"] == 0
    assert summary["blocker_record_count"] == 1
    assert not (
        tmp_path
        / "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/private_causal_evidence_return_candidates.jsonl"
    ).exists()
    blockers = _read_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12518_private_causal_evidence_candidate_return_runner_request/private_causal_evidence_candidate_return_blockers.jsonl"
    )
    assert blockers[0]["decision"] == "blocked_no_honest_stage12516_candidate_returns_from_stage12517_metadata"
    assert blockers[0]["candidate_return_records_written"] == 0


def test_tmp_incomplete_seven_slot_task_blocks_candidate_writes(tmp_path: Path) -> None:
    stage12518 = load_stage12518()
    _stage12517_inputs(tmp_path, stage12518.FULL_SEVEN_SLOTS[:6])

    summary = stage12518.build(tmp_path)

    assert summary["candidate_return_records_written"] == 0
    assert summary["full_seven_slot_task_count"] == 0
    assert summary["blocker_code_counts"]["stage12517_task_not_full_seven_slot_ready"] == 1


def test_raw_leak_guard_rejects_stage12517_raw_marker(tmp_path: Path) -> None:
    stage12518 = load_stage12518()
    _stage12517_inputs(tmp_path, stage12518.FULL_SEVEN_SLOTS)
    worklist_path = (
        tmp_path
        / "runs/local/artifacts/stage12517_private_causal_evidence_return_candidate_worklist/private_causal_evidence_return_candidate_materialization_worklist.jsonl"
    )
    rows = _read_jsonl(worklist_path)
    rows[0]["slot_refs"][0]["source_stage"] = "stdout from private verifier output"
    _write_jsonl(worklist_path, rows)

    with pytest.raises(stage12518.RawLeakError):
        stage12518.build(tmp_path)


def test_production_stage12517_rollup_when_available(tmp_path: Path) -> None:
    stage12518 = load_stage12518()
    if not stage12518.WORKLIST.exists() or not stage12518.SCHEMA.exists() or not stage12518.RUNNER_PREFLIGHT.exists():
        pytest.skip("Stage12517 production runner artifacts are not present")
    out = tmp_path / "runs/local/artifacts/stage12517_private_causal_evidence_return_candidate_worklist"
    out.mkdir(parents=True, exist_ok=True)
    (out / "private_causal_evidence_return_candidate_materialization_worklist.jsonl").write_text(
        stage12518.WORKLIST.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (out / "private_causal_evidence_return_candidate_schema.json").write_text(
        stage12518.SCHEMA.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (out / "runner_preflight.json").write_text(
        stage12518.RUNNER_PREFLIGHT.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    summary = stage12518.build(tmp_path)

    assert summary["stage12517_task_count"] == 49
    assert summary["full_seven_slot_task_count"] == 49
    assert summary["candidate_return_records_written"] == 343
    assert summary["candidate_status_counts"] == {"blocked_unavailable": 343}
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False

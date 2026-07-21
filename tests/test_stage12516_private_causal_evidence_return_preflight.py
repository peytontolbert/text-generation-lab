import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12516_private_causal_evidence_return_preflight.py"


def load_stage12516():
    spec = importlib.util.spec_from_file_location("stage12516", SCRIPT)
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


def _sample_work_order() -> dict:
    return {
        "record_type": "stage12515_private_causal_evidence_acquisition_work_order_v1",
        "acquisition_work_order_id_hash": "a1b2c3d4e5f60718293a4b5c",
        "revalidation_id_hash": "b1c2d3e4f5a60718293a4b5c",
        "request_id_hash": "c1d2e3f4a5b60718293a4b5c",
        "work_item_id_hash": "d1e2f3a4b5c60718293a4b5c",
        "packet_id_hash": "e1f2a3b4c5d60718293a4b5c",
        "root_or_window_hash": "f1a2b3c4d5e60718293a4b5c",
        "source_stage": "stage_unit_safe_source",
        "source_kind": "selected_test_bounded_transition_support",
        "language_family": "python",
        "task_family": "transition_next_action",
        "evidence_slot": "structured_state_before_codes",
        "proof_class": "state_before",
        "acceptable_return_statuses": ["validated_present", "validated_absent", "blocked_unavailable"],
    }


def _valid_return_for(work_order: dict) -> dict:
    return {
        "record_type": "stage12516_private_causal_evidence_return_candidate_v1",
        "acquisition_work_order_id_hash": work_order["acquisition_work_order_id_hash"],
        "revalidation_id_hash": work_order["revalidation_id_hash"],
        "request_id_hash": work_order["request_id_hash"],
        "work_item_id_hash": work_order["work_item_id_hash"],
        "packet_id_hash": work_order["packet_id_hash"],
        "root_or_window_hash": work_order["root_or_window_hash"],
        "source_stage": work_order["source_stage"],
        "source_kind": work_order["source_kind"],
        "language_family": work_order["language_family"],
        "task_family": work_order["task_family"],
        "evidence_slot": work_order["evidence_slot"],
        "proof_class": work_order["proof_class"],
        "private_reviewer_id_hash": "1234567890abcdef12345678",
        "reviewer_conflict_check_hash": "234567890abcdef123456789",
        "reviewer_independence_attestation": True,
        "independent_slot_status": "validated_present",
        "independent_evidence_digest_hash": "34567890abcdef1234567890",
        "slot_status_reason_code": "independent_digest_supplied",
        "causal_review_digest_hash": "4567890abcdef12345678901",
        "raw_private_values_revealed": False,
        "raw_source_output_included": False,
        "raw_paths_included": False,
        "raw_commands_included": False,
        "raw_diffs_included": False,
        "raw_verifier_output_included": False,
        "local_model_authority": False,
        "policy_label_emitted": False,
        "proof_or_admission_requested": False,
        "acceptance_criteria_passed": True,
        "observed_action_available_to_labeler": False,
        "observed_action_used_as_label": False,
        "candidate_action_set_blinded": True,
        "label_leak_attestation": True,
        "model_facing_gold_fields_excluded": True,
        "pass_to_pass_repair_credit_requested": False,
        "repair_credit_requires_before_fail_after_pass_same_verifier": True,
        "blocker_codes": [],
        "training_allowed": False,
        "admission_allowed": False,
        "stage12503_return_file_written": False,
        "stage12503_return_records_written": 0,
    }


def test_tmp_missing_returns_emits_template_and_blocks_proof_admission(tmp_path: Path) -> None:
    stage12516 = load_stage12516()
    work_order = _sample_work_order()
    _write_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/private_causal_evidence_acquisition_work_orders.jsonl",
        [work_order],
    )

    summary = stage12516.build(tmp_path)

    assert summary["decision"] == "private_causal_evidence_return_templates_ready_no_valid_returns_no_training_or_admission"
    assert summary["input_work_order_count"] == 1
    assert summary["return_template_count"] == 1
    assert summary["candidate_return_file_present"] is False
    assert summary["validated_private_causal_evidence_return_count"] == 0
    assert summary["blocked_work_order_count"] == 1
    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False
    assert summary["proof_admission_allowed"] is False
    assert summary["stage12503_return_records_written"] == 0
    assert summary["complete_revalidation_record_count"] == 0
    assert summary["proof_ready_revalidation_record_count"] == 0
    assert summary["raw_leak_count"] == 0

    out = tmp_path / "runs/local/artifacts/stage12516_private_causal_evidence_return_preflight"
    templates = _read_jsonl(out / "private_causal_evidence_return_templates.jsonl")
    blockers = _read_jsonl(out / "private_causal_evidence_return_preflight_blockers.jsonl")
    assert templates[0]["target_return_record_type"] == "stage12516_private_causal_evidence_return_candidate_v1"
    assert "independent_evidence_digest_hash" in templates[0]["required_digest_fields"]
    assert "raw_paths_included" in templates[0]["required_boolean_false_fields"]
    assert "observed_action_available_to_labeler" in templates[0]["required_boolean_false_fields"]
    assert "candidate_action_set_blinded" in templates[0]["required_boolean_true_fields"]
    assert templates[0]["pass_to_pass_rule"].startswith("pass_to_pass_status_is_support_only")
    assert "private_causal_evidence_return_absent" in blockers[0]["blocker_codes"]
    assert "independent_slot_status_and_digest_required_before_proof_or_admission" in blockers[0]["blocker_codes"]


def test_tmp_valid_candidate_return_is_status_only_and_writes_no_stage12503_return(tmp_path: Path) -> None:
    stage12516 = load_stage12516()
    work_order = _sample_work_order()
    stage12515_out = tmp_path / "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders"
    _write_jsonl(stage12515_out / "private_causal_evidence_acquisition_work_orders.jsonl", [work_order])
    _write_jsonl(stage12515_out / "private_causal_evidence_return_candidates.jsonl", [_valid_return_for(work_order)])

    summary = stage12516.build(tmp_path)

    assert summary["decision"] == "private_causal_evidence_return_candidates_validated_preflight_only_no_training_or_admission"
    assert summary["validated_private_causal_evidence_return_count"] == 1
    assert summary["blocked_work_order_count"] == 0
    assert summary["proof_rows_emitted"] == 0
    assert summary["admitted_rows"] == 0
    assert summary["stage12503_return_file_written"] is False
    assert summary["stage12503_return_records_written"] == 0
    assert summary["complete_revalidation_record_count"] == 1
    assert summary["proof_ready_revalidation_record_count"] == 0
    assert summary["all_slots_joined_for_any_revalidation_record"] is True

    accepted = _read_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12516_private_causal_evidence_return_preflight/validated_private_causal_evidence_return_status.jsonl"
    )
    assert accepted[0]["private_causal_evidence_return_validated"] is True
    assert accepted[0]["proof_admission_blocked_until_downstream_authoritative_ingest"] is True
    assert accepted[0]["independent_evidence_digest_hash"] == "34567890abcdef1234567890"
    assert accepted[0]["stage12503_return_records_written"] == 0


def test_tmp_rejects_candidate_without_independent_digest_and_with_raw_field(tmp_path: Path) -> None:
    stage12516 = load_stage12516()
    work_order = _sample_work_order()
    bad = _valid_return_for(work_order)
    bad.pop("independent_evidence_digest_hash")
    bad["raw_output"] = "not public safe"
    bad["proof_or_admission_requested"] = True
    stage12515_out = tmp_path / "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders"
    _write_jsonl(stage12515_out / "private_causal_evidence_acquisition_work_orders.jsonl", [work_order])
    _write_jsonl(stage12515_out / "private_causal_evidence_return_candidates.jsonl", [bad])

    summary = stage12516.build(tmp_path)

    assert summary["validated_private_causal_evidence_return_count"] == 0
    assert summary["rejected_private_causal_evidence_return_count"] == 1
    assert summary["blocked_work_order_count"] == 1
    assert summary["training_rows_emitted"] == 0
    assert summary["stage12503_return_records_written"] == 0

    rejected = _read_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12516_private_causal_evidence_return_preflight/rejected_private_causal_evidence_returns.jsonl"
    )
    assert "missing_independent_evidence_digest_hash" in rejected[0]["rejection_codes"]
    assert "independent_evidence_digest_hash_missing_or_unsafe" in rejected[0]["rejection_codes"]
    assert "forbidden_raw_or_proof_field_present" in rejected[0]["rejection_codes"]
    assert "proof_or_admission_requested_not_false" in rejected[0]["rejection_codes"]


def test_tmp_rejects_observed_action_imitation_and_duplicate_returns(tmp_path: Path) -> None:
    stage12516 = load_stage12516()
    work_order = _sample_work_order()
    bad = _valid_return_for(work_order)
    bad["observed_action_available_to_labeler"] = True
    bad["observed_action_used_as_label"] = True
    bad["candidate_action_set_blinded"] = False
    stage12515_out = tmp_path / "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders"
    _write_jsonl(stage12515_out / "private_causal_evidence_acquisition_work_orders.jsonl", [work_order])
    _write_jsonl(stage12515_out / "private_causal_evidence_return_candidates.jsonl", [bad, _valid_return_for(work_order)])

    summary = stage12516.build(tmp_path)

    assert summary["validated_private_causal_evidence_return_count"] == 0
    assert summary["rejected_private_causal_evidence_return_count"] == 2
    rejected = _read_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12516_private_causal_evidence_return_preflight/rejected_private_causal_evidence_returns.jsonl"
    )
    rejection_codes = {code for row in rejected for code in row["rejection_codes"]}
    assert "duplicate_return_for_acquisition_work_order" in rejection_codes
    assert "observed_action_available_to_labeler_not_false" in rejection_codes
    assert "observed_action_used_as_label_not_false" in rejection_codes
    assert "candidate_action_set_blinded_not_true" in rejection_codes


def test_raw_leak_guard_rejects_template_source_stage_path_marker(tmp_path: Path) -> None:
    stage12516 = load_stage12516()
    work_order = _sample_work_order()
    work_order["source_stage"] = "/private/raw/source/path"
    _write_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/private_causal_evidence_acquisition_work_orders.jsonl",
        [work_order],
    )

    with pytest.raises(stage12516.RawLeakError):
        stage12516.build(tmp_path)


def test_production_stage12515_rollup_counts_when_available(tmp_path: Path) -> None:
    stage12516 = load_stage12516()
    if not stage12516.WORK_ORDERS.exists():
        pytest.skip("Stage12515 production work orders are not present")

    tmp_work_orders = (
        tmp_path
        / "runs/local/artifacts/stage12515_private_causal_evidence_acquisition_work_orders/private_causal_evidence_acquisition_work_orders.jsonl"
    )
    tmp_work_orders.parent.mkdir(parents=True, exist_ok=True)
    tmp_work_orders.write_text(stage12516.WORK_ORDERS.read_text(encoding="utf-8"), encoding="utf-8")

    summary = stage12516.build(tmp_path)

    assert summary["input_work_order_count"] == 343
    assert summary["return_template_count"] == 343
    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False
    assert summary["proof_admission_allowed"] is False
    assert summary["proof_rows_emitted"] == 0
    assert summary["level3_atom_count"] == 0
    assert summary["patch_trace_rows"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["complete_revalidation_record_count"] == 0
    assert summary["proof_ready_revalidation_record_count"] == 0
    assert summary["raw_leak_count"] == 0

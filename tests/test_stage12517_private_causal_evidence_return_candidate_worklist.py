import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12517_private_causal_evidence_return_candidate_worklist.py"


def load_stage12517():
    spec = importlib.util.spec_from_file_location("stage12517", SCRIPT)
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


def _template(slot: str, idx: int = 0, revalidation_id_hash: str = "a1b2c3d4e5f60718293a4b5c") -> dict:
    stage12517 = load_stage12517()
    return {
        "record_type": "stage12516_private_causal_evidence_return_template_v1",
        "return_template_id_hash": f"1{idx:023x}"[-24:],
        "target_return_record_type": "stage12516_private_causal_evidence_return_candidate_v1",
        "source_stage": "stage_unit_safe_source",
        "acquisition_work_order_id_hash": f"2{idx:023x}"[-24:],
        "revalidation_id_hash": revalidation_id_hash,
        "request_id_hash": "b1c2d3e4f5a60718293a4b5c",
        "work_item_id_hash": "c1d2e3f4a5b60718293a4b5c",
        "packet_id_hash": "d1e2f3a4b5c60718293a4b5c",
        "root_or_window_hash": "e1f2a3b4c5d60718293a4b5c",
        "source_kind": "selected_test_bounded_transition_support",
        "language_family": "python",
        "task_family": "transition_next_action",
        "evidence_slot": slot,
        "proof_class": f"proof_class_{idx}",
        "allowed_independent_slot_statuses": ["validated_present", "validated_absent", "blocked_unavailable"],
        "required_public_safe_return_fields": stage12517.REQUIRED_CANDIDATE_FIELDS,
        "required_boolean_false_fields": stage12517.REQUIRED_FALSE_FIELDS,
        "required_boolean_true_fields": stage12517.REQUIRED_TRUE_FIELDS,
        "public_safe_status_only": True,
    }


def _blocker(template: dict, idx: int = 0) -> dict:
    return {
        "record_type": "stage12516_private_causal_evidence_return_preflight_blocker_v1",
        "blocker_id_hash": f"3{idx:023x}"[-24:],
        "acquisition_work_order_id_hash": template["acquisition_work_order_id_hash"],
        "revalidation_id_hash": template["revalidation_id_hash"],
        "request_id_hash": template["request_id_hash"],
        "work_item_id_hash": template["work_item_id_hash"],
        "packet_id_hash": template["packet_id_hash"],
        "root_or_window_hash": template["root_or_window_hash"],
        "source_stage": template["source_stage"],
        "source_kind": template["source_kind"],
        "language_family": template["language_family"],
        "task_family": template["task_family"],
        "evidence_slot": template["evidence_slot"],
        "proof_class": template["proof_class"],
        "preflight_decision": "blocked",
        "blocker_codes": [
            "private_causal_evidence_return_absent",
            "independent_slot_status_and_digest_required_before_proof_or_admission",
        ],
        "public_safe_status_only": True,
    }


def test_tmp_groups_seven_blocked_templates_into_one_bounded_runner_task(tmp_path: Path) -> None:
    stage12517 = load_stage12517()
    templates = [_template(slot, idx) for idx, slot in enumerate(stage12517.FULL_SEVEN_SLOTS)]
    blockers = [_blocker(template, idx) for idx, template in enumerate(templates)]
    stage12516_out = tmp_path / "runs/local/artifacts/stage12516_private_causal_evidence_return_preflight"
    _write_jsonl(stage12516_out / "private_causal_evidence_return_templates.jsonl", templates)
    _write_jsonl(stage12516_out / "private_causal_evidence_return_preflight_blockers.jsonl", blockers)

    summary = stage12517.build(tmp_path)

    assert summary["decision"] == "private_causal_evidence_return_candidate_materialization_worklist_ready_no_returns_written"
    assert summary["input_template_count"] == 7
    assert summary["input_blocker_count"] == 7
    assert summary["unresolved_template_count"] == 7
    assert summary["candidate_materialization_task_count"] == 1
    assert summary["full_seven_slot_task_count"] == 1
    assert summary.get("non_proof_status_counts", {}) in ({}, {"blocked_unavailable": 343})
    assert summary["candidate_return_records_written"] == 0
    assert summary["stage12515_candidate_return_records_written"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False
    assert summary["proof_admission_allowed"] is False
    assert summary["level3_atom_count"] == 0
    assert summary["patch_trace_rows"] == 0
    assert summary["raw_leak_count"] == 0

    out = tmp_path / "runs/local/artifacts/stage12517_private_causal_evidence_return_candidate_worklist"
    worklist = _read_jsonl(out / "private_causal_evidence_return_candidate_materialization_worklist.jsonl")
    assert len(worklist) == 1
    task = worklist[0]
    assert task["slot_count"] == 7
    assert task["max_slot_count"] == 7
    assert task["missing_from_full_seven_slot_set"] == []
    assert task["full_seven_slot_completeness_required"] is True
    assert task["candidate_output_written_by_stage12517"] is False
    assert task["runner_must_not_emit_validated_returns"] is True
    assert task["runner_must_not_write_stage12515_candidate_returns_in_preflight"] is True
    assert task["runner_must_not_write_stage12503_returns"] is True
    assert "observed_action_unavailable" in task["anti_imitation_guard"]
    assert "model_facing_gold_fields_excluded" in task["label_leak_guard"]
    assert "not_repair_credit" in task["pass_to_pass_guard"]
    assert "no_raw_paths_commands_diffs_source_or_verifier_output" in task["raw_leak_guard"]
    assert all(slot_ref["target_return_record_type"] == "stage12516_private_causal_evidence_return_candidate_v1" for slot_ref in task["slot_refs"])


def test_tmp_schema_contains_candidate_return_guards_without_writing_candidates(tmp_path: Path) -> None:
    stage12517 = load_stage12517()
    template = _template(stage12517.FULL_SEVEN_SLOTS[0])
    stage12516_out = tmp_path / "runs/local/artifacts/stage12516_private_causal_evidence_return_preflight"
    _write_jsonl(stage12516_out / "private_causal_evidence_return_templates.jsonl", [template])
    _write_jsonl(stage12516_out / "private_causal_evidence_return_preflight_blockers.jsonl", [_blocker(template)])

    summary = stage12517.build(tmp_path)

    out = tmp_path / "runs/local/artifacts/stage12517_private_causal_evidence_return_candidate_worklist"
    schema = json.loads((out / "private_causal_evidence_return_candidate_schema.json").read_text(encoding="utf-8"))
    runner = json.loads((out / "runner_preflight.json").read_text(encoding="utf-8"))
    assert schema["target_future_return_record_type"] == "stage12516_private_causal_evidence_return_candidate_v1"
    assert "private_reviewer_id_hash" in schema["required_fields"]
    assert "raw_paths_included" in schema["required_boolean_false_fields"]
    assert "observed_action_available_to_labeler" in schema["required_boolean_false_fields"]
    assert "observed_action_used_as_label" in schema["required_boolean_false_fields"]
    assert "candidate_action_set_blinded" in schema["required_boolean_true_fields"]
    assert "label_leak_attestation" in schema["required_boolean_true_fields"]
    assert "repair_credit_requires_before_fail_after_pass_same_verifier" in schema["required_boolean_true_fields"]
    assert schema["candidate_return_file_written"] is False
    assert schema["candidate_return_records_written"] == 0
    assert runner["candidate_output_written_by_stage12517"] is False
    assert runner["validated_returns_written_by_stage12517"] is False
    assert runner["stage12515_candidate_returns_written_by_stage12517"] is False
    assert runner["stage12503_returns_written_by_stage12517"] is False
    assert summary["candidate_return_file_written"] is False


def test_tmp_missing_inputs_is_safe_empty_preflight(tmp_path: Path) -> None:
    stage12517 = load_stage12517()
    summary = stage12517.build(tmp_path)

    assert summary["input_template_count"] == 0
    assert summary["input_blocker_count"] == 0
    assert summary["candidate_materialization_task_count"] == 0
    assert summary["runner_preflight_ready"] is False
    assert summary["candidate_return_records_written"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_rows_emitted"] == 0
    assert summary["raw_leak_count"] == 0


def test_raw_leak_guard_rejects_public_raw_marker(tmp_path: Path) -> None:
    stage12517 = load_stage12517()
    template = _template(stage12517.FULL_SEVEN_SLOTS[0])
    template["source_stage"] = "stdout from private command output"
    stage12516_out = tmp_path / "runs/local/artifacts/stage12516_private_causal_evidence_return_preflight"
    _write_jsonl(stage12516_out / "private_causal_evidence_return_templates.jsonl", [template])
    _write_jsonl(stage12516_out / "private_causal_evidence_return_preflight_blockers.jsonl", [_blocker(template)])

    with pytest.raises(stage12517.RawLeakError):
        stage12517.build(tmp_path)


def test_production_stage12516_rollup_counts_when_available(tmp_path: Path) -> None:
    stage12517 = load_stage12517()
    if not stage12517.TEMPLATES.exists() or not stage12517.BLOCKERS.exists():
        pytest.skip("Stage12516 production templates and blockers are not present")

    stage12516_out = tmp_path / "runs/local/artifacts/stage12516_private_causal_evidence_return_preflight"
    stage12516_out.mkdir(parents=True, exist_ok=True)
    (stage12516_out / "private_causal_evidence_return_templates.jsonl").write_text(
        stage12517.TEMPLATES.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (stage12516_out / "private_causal_evidence_return_preflight_blockers.jsonl").write_text(
        stage12517.BLOCKERS.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    validated_status = getattr(stage12517, "VALIDATED_STATUS", None)
    if validated_status is not None and validated_status.exists():
        (stage12516_out / "validated_private_causal_evidence_return_status.jsonl").write_text(
            validated_status.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    summary = stage12517.build(tmp_path)

    assert summary["input_template_count"] == 343
    assert summary["input_blocker_count"] in (0, 343)
    assert summary.get("input_non_proof_validated_status_count", 0) in (0, 343)
    assert summary["unresolved_template_count"] == 343
    assert summary["candidate_materialization_task_count"] == 49
    assert summary["full_seven_slot_task_count"] == 49
    assert all(count == 49 for count in summary["evidence_slot_counts"].values())
    assert summary.get("non_proof_status_counts", {}) in ({}, {"blocked_unavailable": 343})
    assert summary["candidate_return_records_written"] == 0
    assert summary["stage12515_candidate_return_records_written"] == 0
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False
    assert summary["proof_admission_allowed"] is False
    assert summary["level3_atom_count"] == 0
    assert summary["patch_trace_rows"] == 0
    assert summary["raw_leak_count"] == 0

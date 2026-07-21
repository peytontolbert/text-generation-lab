from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12498_review_return_template_work_order.py"
OUT = ROOT / "runs/local/artifacts/stage12498_review_return_template_work_order"
SUMMARY = ROOT / "runs/summaries/stage12498_review_return_template_work_order.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_stage12498_builds_public_safe_review_return_work_order() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

    summary = read_json(SUMMARY)
    guardrail = read_json(OUT / "guardrail_scan.json")
    work_order = read_json(OUT / "review_return_operator_work_order.json")
    schema = read_json(OUT / "sample_review_return_schema.json")
    slots = read_jsonl(OUT / "review_return_work_order_slots.jsonl")
    event_local_refs = read_jsonl(OUT / "event_local_non_promotion_refs.jsonl")

    assert summary["decision"] == "review_return_work_order_ready_training_blocked"
    assert summary["input_work_item_count"] == 56
    assert summary["return_eligible_work_item_count"] == 24
    assert summary["review_return_work_order_slot_count"] == len(slots) == 24
    assert summary["event_local_input_count"] == 32
    assert summary["event_local_excluded_count"] == len(event_local_refs) == 32
    assert summary["event_local_promoted_count"] == 0
    assert summary["stage12496_accepted_return_count"] == 0
    assert summary["stage12497_blocked_gate_count"] == 1
    assert summary["sample_schema_uses_placeholders_only"] is True
    assert summary["local_model_suggestions_authoritative_count"] == 0
    assert summary["observed_action_access_allowed_count"] == 0
    assert summary["private_raw_value_output_count"] == 0
    assert summary["raw_path_output_count"] == 0
    assert summary["raw_command_output_count"] == 0
    assert summary["raw_source_output_count"] == 0
    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False
    assert summary["training_rows_emitted"] == 0
    assert summary["admitted_rows"] == 0
    assert summary["reviewed_train_support_rows"] == 0
    assert summary["proof_grade_repair_rows"] == 0
    assert summary["external_repair_credit_count"] == 0
    assert guardrail["scan_passed"] is True
    assert summary["raw_leak_count"] == guardrail["raw_leak_count"] == 0

    assert work_order["target_validator_stage"] == "stage12496_policy_label_review_return_validator"
    assert "local_model_authority_false" in work_order["acceptance_criteria"]
    assert "observed_action_available_to_labeler_false" in work_order["acceptance_criteria"]
    assert "deterministic_blinded_shuffle_hash_present" in work_order["acceptance_criteria"]
    assert "hard_negative_count_at_least_2" in work_order["acceptance_criteria"]

    sample_return = schema["stage12496_return_record"]
    assert schema["placeholder_only"] is True
    assert sample_return["record_type"] == "stage12496_policy_label_review_return_v1"
    assert sample_return["review_item_id_hash"] == "<review_item_id_hash>"
    assert sample_return["independent_policy_label_hash"] == "<independent_policy_label_hash>"
    assert sample_return["reviewer_independence_attestation"] is True
    assert sample_return["local_model_authority"] is False
    assert sample_return["observed_action_available_to_labeler"] is False
    assert sample_return["observed_action_used_as_label"] is False
    assert sample_return["raw_private_values_revealed"] is False
    assert sample_return["event_local_promoted"] is False
    assert sample_return["blocker_codes"] == []
    assert sample_return["training_allowed"] is False
    assert sample_return["admission_allowed"] is False
    assert sample_return["training_rows_emitted"] == 0
    assert sample_return["admitted_rows"] == 0

    assert {slot["task_family"] for slot in slots} == {
        "transition_continue_or_stop",
        "transition_next_action",
        "transition_verifier_transition",
    }
    for slot in slots:
        assert slot["return_eligible_for_stage12496"] is True
        assert slot["local_model_authority"] is False
        assert slot["observed_action_access_allowed_count"] == 0
        assert slot["training_allowed"] is False
        assert slot["admission_allowed"] is False
        assert slot["training_rows_emitted"] == 0
        assert slot["admitted_rows"] == 0
        assert "deterministic_blinded_shuffle_hash" in slot["must_fill_hash_fields"]
        assert "hard_negative_audit_hash" in slot["must_fill_hash_fields"]

    for ref in event_local_refs:
        assert ref["return_eligible_for_stage12496"] is False
        assert ref["event_local_promoted"] is False
        assert "event_local_non_promotion_required" in ref["reason_codes"]
        assert ref["training_rows_emitted"] == 0

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12545_stage12543_executor_return_templates.py"
SUMMARY = ROOT / "runs/summaries/stage12545_stage12543_executor_return_templates.json"
TEMPLATES = ROOT / "runs/local/artifacts/stage12545_stage12543_executor_return_templates/stage12545_executor_return_templates.jsonl"
GATE = ROOT / "runs/local/artifacts/stage12545_stage12543_executor_return_templates/stage12545_executor_return_validation_gate.json"


def load_builder():
    spec = importlib.util.spec_from_file_location("stage12545_builder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_stage12545_emits_templates_only_no_execution_or_rows():
    module = load_builder()
    summary = module.build()

    assert summary["stage"] == "stage12545_stage12543_executor_return_templates"
    assert summary["decision"] == "return_templates_emitted_no_execution_no_rows_admitted"
    assert summary["stage12544_return_files_present"] == 0
    assert summary["stage12544_missing_return_work_items"] == 6
    assert summary["template_count"] == 6
    assert summary["target_status_template_counts"] == {"FAIL_CURRENT_STATE": 3, "INSUFFICIENT_EVIDENCE": 3}
    assert summary["new_preflight_row_count"] == 0
    assert summary["new_countable_train_support_count"] == 0
    assert summary["training_allowed"] is False
    assert summary["countable_train_support"] is False
    assert summary["level3_admitted"] is False
    assert summary["repair_claim_admitted"] is False
    assert summary["raw_public_content_allowed"] is False


def test_stage12545_templates_are_hash_only_and_reject_bad_scopes():
    module = load_builder()
    module.build()
    rows = module.read_jsonl(TEMPLATES)

    assert len(rows) == 6
    for row in rows:
        assert row["candidate_row_emitted"] is False
        assert row["public_return_must_be_hash_only"] is True
        assert row["raw_public_content_allowed"] is False
        assert row["selected_or_exact_test_scope_allowed"] is False
        assert row["controlled_fixture_like_allowed"] is False
        assert row["stage_synthetic_repo_family_allowed"] is False
        assert row["projection_or_transition_derived_label_allowed"] is False
        assert "verifier_output_hash" in row["expected_public_return_fields"]
        assert "command_observation_join_hash" in row["expected_public_return_fields"]
        assert "raw_command" not in row
        assert "stdout" not in row
        assert "stderr" not in row


def test_stage12545_validation_gate_blocks_known_false_progress_modes():
    module = load_builder()
    module.build()
    gate = module.read_json(GATE)

    assert gate["validator_should_emit_preflight_rows_only_after_returns"] is True
    for reason in [
        "raw_public_content_present",
        "selected_or_exact_test_scope",
        "fixture_or_stage_synthetic_source",
        "env_or_invalid_command_labeled_fail_current_state",
        "insufficient_evidence_without_zero_test_or_missing_verifier_proof",
        "duplicate_output_hash_against_stage12541_or_same_batch",
    ]:
        assert reason in gate["hard_reject_reasons"]

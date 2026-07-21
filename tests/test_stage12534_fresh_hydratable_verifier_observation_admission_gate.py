import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12534_fresh_hydratable_verifier_observation_admission_gate.py"
SUMMARY = ROOT / "runs/summaries/stage12534_fresh_hydratable_verifier_observation_admission_gate.json"


def load_builder():
    spec = importlib.util.spec_from_file_location("stage12534_builder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_stage12534_prepares_fresh_hydratable_gate_without_overclaiming():
    module = load_builder()
    module.main()
    summary = module.read_json(SUMMARY)

    assert summary["stage"] == "stage12534_fresh_hydratable_verifier_observation_admission_gate"
    assert summary["training_allowed"] is False
    assert summary["countable_train_support"]["stage12533_repaired_countable_total"] == 127
    assert summary["countable_train_support"]["admitted_additional_fresh_hydratable_rows"] == 0
    assert summary["countable_train_support"]["current_countable_total"] == 127
    assert summary["remaining_gap_to_500"] == 373
    assert summary["gate_type"] == "executable_public_local_verifier_observation_supply_validator"
    assert summary["fresh_supply_input_present"] is False
    assert summary["fresh_supply_candidate_count"] == 0
    assert summary["fresh_supply_admitted_count"] == 0
    assert summary["new_countable_train_support_count"] == 0
    assert summary["post_admission_collapse_group_count"] == 0

    assert summary["source_inventory"]["stage12533_repaired_rows"] == 101
    assert summary["source_inventory"]["stage12216_normalized_source_rows"] == 146
    assert summary["source_inventory"]["stage12418_sanitized_projection_rows"] == 292
    assert summary["source_inventory"]["stage12421_direct_projection_rows"] == 26

    assert summary["candidate_counts"]["stage12216_stage12418_projected_candidates"] == 292
    assert summary["candidate_counts"]["stage12421_direct_candidates"] == 26
    assert summary["candidate_counts"]["fresh_public_local_adoption_candidates"] == 0
    assert summary["candidate_counts"]["admitted_additional_train_support_rows"] == 0

    assert summary["guardrail_scan_passed"] is True
    assert summary["raw_leak_count"] == 0
    assert summary["checks"]["derived_stage12216_rows_not_counted_as_fresh"] is True
    assert summary["checks"]["selected_test_control_rows_not_counted_as_fresh"] is True
    assert summary["checks"]["zero_level3_patch_trace_repair_credit"] is True
    assert summary["countable_only_language_counts"] == {}
    assert summary["countable_only_projection_counts"] == {}
    assert summary["next_admission_gate"]["gate_is_executable"] is True
    assert summary["next_admission_gate"]["schema_ref"].endswith("public_local_verifier_observation_supply_schema.json")
    assert summary["next_admission_gate"]["rejection_rules_ref"].endswith("public_local_verifier_observation_rejection_rules.json")
    assert summary["next_admission_gate"]["deterministic_commands_ref"].endswith("deterministic_supply_gate_commands.json")
    assert summary["next_stage"] == "supply_fresh_public_local_verifier_observation_rows_then_run_stage12534_validate_supply"
    assert summary["level3_admitted_rows"] == 0
    assert summary["patch_trace_admitted_rows"] == 0
    assert summary["repair_claim_admitted_rows"] == 0
    assert summary["fail_to_pass_claim_admitted_rows"] == 0
    assert summary["strict_eval_eligible_count"] == 0
    assert summary["source_heldout_admissible_count"] == 0
    assert "no_fresh_non_derivative_public_local_hydratable_verifier_observation_rows_identified" in summary["training_blockers"]
    assert "500_countable_train_support_floor_not_reached" in summary["training_blockers"]


def grounded_row(**overrides):
    row = {
        "source_stage": "stage_public_local_fixture_for_gate_contract",
        "source_line_hash": "a" * 24,
        "root_lineage_key_hash": "b" * 24,
        "repo_family_hash": "c" * 24,
        "language_family": "python",
        "task_projection": "transition_verifier_transition",
        "target_semantic_value": "PASS_CURRENT_STATE",
        "verifier_status": "PASS_CURRENT_STATE",
        "source_lineage_checked": True,
        "hydratable_verifier_observation_candidate": True,
        "controlled_fixture_like": False,
        "actual_verifier_command_output_observation_provenance": True,
        "verifier_command_ref_hash": "d" * 24,
        "command_result_id_hash": "e" * 24,
        "verifier_exit_status_class": "exit_zero",
        "verifier_stdout_hash": "f" * 64,
        "verifier_stderr_hash": "1" * 64,
        "verifier_output_hash": "2" * 24,
        "verifier_observation_hash": "3" * 24,
        "target_binding_class": "target_semantic_value_from_observed_verifier_result_status",
        "target_binding_rule_id_hash": "4" * 24,
        "derived_projection_lane": False,
        "private_or_status_return": False,
        "generic_selected_test_collapsed": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "level3_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
        "training_allowed": False,
    }
    row.update(overrides)
    return row


def test_stage12534_validate_supply_entrypoint_accepts_command_output_grounded_nonfixture_row(tmp_path):
    module = load_builder()
    row = grounded_row()
    result = module.validate_supply_rows([row], module.read_jsonl(module.STAGE12533_REPAIRED_ROWS))

    assert len(result["accepted_rows"]) == 1
    accepted = result["accepted_rows"][0]
    assert accepted["countable_train_support"] is True
    assert accepted["training_allowed"] is False
    assert accepted["actual_verifier_command_output_observation_provenance"] is True
    assert accepted["verifier_output_hash"] == row["verifier_output_hash"]
    assert result["guardrail_scan"]["scan_passed"] is True
    assert result["anti_collapse"]["collapse_group_count"] == 0


def test_stage12534_rejects_hash_only_metadata_inventory_rows():
    module = load_builder()
    row = {
        "source_stage": "stage12535_public_local_repo_verifier_observation_supply",
        "source_line_hash": "a" * 24,
        "root_lineage_key_hash": "b" * 24,
        "repo_family_hash": "c" * 24,
        "language_family": "python",
        "task_projection": "transition_verifier_transition",
        "target_semantic_value": "PASS_CURRENT_STATE",
        "verifier_status": "PASS_CURRENT_STATE",
        "source_lineage_checked": True,
        "hydratable_verifier_observation_candidate": True,
        "controlled_fixture_like": False,
        "derived_projection_lane": False,
        "private_or_status_return": False,
        "generic_selected_test_collapsed": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "level3_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
        "training_allowed": False,
    }
    result = module.validate_supply_rows([row], module.read_jsonl(module.STAGE12533_REPAIRED_ROWS))

    assert result["accepted_rows"] == []
    assert len(result["rejected_rows"]) == 1
    blockers = set(result["rejected_rows"][0]["blocked_reasons"])
    assert "actual_verifier_command_output_observation_provenance_not_true" in blockers
    assert "verifier_command_ref_hash_not_hash" in blockers
    assert "verifier_output_hash_not_hash" in blockers


def test_stage12534_validate_supply_rejects_fixtures_and_claims():
    module = load_builder()
    row = grounded_row(
        source_line_hash="d" * 24,
        root_lineage_key_hash="e" * 24,
        repo_family_hash="f" * 24,
        language_family="rust",
        task_projection="transition_continue_or_stop",
        target_semantic_value="CONTINUE_SINGLE_VERIFIER_EVIDENCE",
        verifier_status="CONTINUE_SINGLE_VERIFIER_EVIDENCE",
        controlled_fixture_like=True,
        patch_trace_admitted=True,
    )
    result = module.validate_supply_rows([row], module.read_jsonl(module.STAGE12533_REPAIRED_ROWS))

    assert result["accepted_rows"] == []
    assert len(result["rejected_rows"]) == 1
    assert "controlled_fixture_like_not_false" in result["rejected_rows"][0]["blocked_reasons"]
    assert "patch_trace_admitted" in result["rejected_rows"][0]["blocked_reasons"]


def test_stage12534_rejects_same_observation_reused_with_different_target():
    module = load_builder()
    row_a = grounded_row(
        target_semantic_value="PASS_CURRENT_STATE",
        verifier_status="PASS_CURRENT_STATE",
        verifier_observation_hash="5" * 24,
        command_result_id_hash="6" * 24,
    )
    row_b = grounded_row(
        source_line_hash="7" * 24,
        root_lineage_key_hash="8" * 24,
        target_semantic_value="FAIL_CURRENT_STATE",
        verifier_status="FAIL_CURRENT_STATE",
        verifier_exit_status_class="exit_nonzero",
        verifier_observation_hash="5" * 24,
        command_result_id_hash="6" * 24,
    )
    result = module.validate_supply_rows([row_a, row_b], module.read_jsonl(module.STAGE12533_REPAIRED_ROWS))

    assert len(result["accepted_rows"]) == 1
    assert len(result["rejected_rows"]) == 1
    blockers = set(result["rejected_rows"][0]["blocked_reasons"])
    assert "same_verifier_observation_hash_reused_with_different_target" in blockers
    assert "same_command_result_hash_reused_with_different_target" in blockers


def test_stage12534_rejects_target_not_bound_to_verifier_status():
    module = load_builder()
    row = grounded_row(target_semantic_value="PASS_CURRENT_STATE", verifier_status="FAIL_CURRENT_STATE")
    result = module.validate_supply_rows([row], module.read_jsonl(module.STAGE12533_REPAIRED_ROWS))

    assert result["accepted_rows"] == []
    assert "target_not_bound_to_observed_verifier_status" in result["rejected_rows"][0]["blocked_reasons"]

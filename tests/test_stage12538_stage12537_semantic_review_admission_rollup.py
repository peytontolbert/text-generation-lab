import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12538_stage12537_semantic_review_admission_rollup.py"
SUMMARY = ROOT / "runs/summaries/stage12538_stage12537_semantic_review_admission_rollup.json"
ADMITTED = (
    ROOT
    / "runs/local/artifacts/stage12538_stage12537_semantic_review_admission_rollup"
    / "stage12537_semantic_review_admitted_train_support_rows.jsonl"
)
WORKLIST = (
    ROOT
    / "runs/local/artifacts/stage12538_stage12537_semantic_review_admission_rollup"
    / "remaining_gap_source_expansion_worklist.jsonl"
)


def load_builder():
    spec = importlib.util.spec_from_file_location("stage12538_builder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def grounded_candidate(**overrides):
    row = {
        "stage": "stage12537_command_output_verifier_observation_materialization_preflight",
        "record_type": "real_command_output_verifier_observation_materialization_candidate_v1",
        "candidate_ref_hash": "a" * 24,
        "source_stage": "stage_public_local_fixture_for_stage12538_unit",
        "source_line_hash": "b" * 24,
        "root_lineage_key_hash": "c" * 24,
        "repo_family_hash": "d" * 24,
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
        "actual_verifier_command_output_observation_provenance": True,
        "verifier_command_ref_hash": "e" * 24,
        "command_result_id_hash": "f" * 24,
        "verifier_exit_status_class": "exit_zero",
        "verifier_stdout_hash": "1" * 64,
        "verifier_stderr_hash": "2" * 64,
        "verifier_output_hash": "3" * 24,
        "verifier_observation_hash": "4" * 24,
        "target_binding_class": "target_semantic_value_from_observed_verifier_result_status",
        "target_binding_rule_id_hash": "5" * 24,
        "stage12534_constraint_preflight_passed": True,
        "countable_train_support": False,
        "training_allowed": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "level3_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
        "command_observation_join_hash": "6" * 24,
    }
    row.update(overrides)
    return row


def test_stage12538_blocks_current_stage12537_batch_until_balance_and_scope_gates_pass():
    module = load_builder()
    summary = module.build()

    assert summary["stage"] == "stage12538_stage12537_semantic_review_admission_rollup"
    assert summary["decision"] == "fail_closed_no_stage12537_rows_admitted"
    assert summary["admission_counts"]["semantic_review_admitted_train_support_only_rows"] == 0
    assert summary["admission_counts"]["stage12534_validation_passed_rows"] == 13
    assert summary["admission_counts"]["semantic_review_rejected_rows"] == 13
    assert summary["new_countable_train_support_count"] == 0
    assert summary["countable_train_support"]["prior_stage12533_countable_total"] == 127
    assert summary["countable_train_support"]["current_countable_total"] == 127
    assert summary["remaining_gap_to_500"] == 373
    assert summary["training_allowed"] is False
    assert summary["guardrail_scan_passed"] is True
    assert summary["raw_leak_count"] == 0
    assert summary["target_balance_audit"]["passed"] is False
    assert summary["target_balance_audit"]["max_target_share"] > 0.50
    assert summary["selected_test_scope_audit"]["passed"] is False
    assert summary["command_observation_join_audit"]["passed"] is False
    assert "stage12538_target_balance_failed" in summary["batch_block_reasons"]
    assert "stage12538_selected_test_scope_not_countable_without_explicit_policy" in summary["batch_block_reasons"]
    assert "stage12538_command_observation_join_hash_missing" in summary["batch_block_reasons"]
    assert summary["level3_admitted_rows"] == 0
    assert summary["patch_trace_admitted_rows"] == 0
    assert summary["repair_claim_admitted_rows"] == 0
    assert summary["fail_to_pass_claim_admitted_rows"] == 0
    assert summary["strict_eval_eligible_count"] == 0
    assert summary["source_heldout_admissible_count"] == 0
    assert summary["gemma_or_product_claims"] == 0

    rows = module.read_jsonl(ADMITTED)
    assert rows == []


def test_stage12538_semantic_candidate_gate_requires_provenance_and_target_binding():
    module = load_builder()

    missing_provenance = grounded_candidate(actual_verifier_command_output_observation_provenance=False)
    assert "actual_verifier_command_output_observation_provenance_not_true" in module.semantic_candidate_issues(
        missing_provenance
    )

    unbound = grounded_candidate(target_semantic_value="PASS_CURRENT_STATE", verifier_status="FAIL_CURRENT_STATE")
    assert "target_not_bound_to_observed_verifier_status" in module.semantic_candidate_issues(unbound)

    bad_binding = grounded_candidate(target_binding_class="target_from_index_position")
    assert "target_binding_not_observed_verifier_status" in module.semantic_candidate_issues(bad_binding)

    risky = grounded_candidate(patch_trace_admitted=True)
    assert "patch_trace_admitted" in module.semantic_candidate_issues(risky)


def test_stage12538_target_balance_selected_scope_and_join_gates():
    module = load_builder()
    rows = [
        grounded_candidate(candidate_ref_hash="a" * 24, source_stage="stage_generic", target_semantic_value="PASS_CURRENT_STATE", verifier_status="PASS_CURRENT_STATE"),
        grounded_candidate(candidate_ref_hash="b" * 24, source_line_hash="7" * 24, root_lineage_key_hash="8" * 24, source_stage="stage_generic", target_semantic_value="PASS_CURRENT_STATE", verifier_status="PASS_CURRENT_STATE"),
        grounded_candidate(candidate_ref_hash="c" * 24, source_line_hash="9" * 24, root_lineage_key_hash="a1" * 12, source_stage="stage_generic", target_semantic_value="FAIL_CURRENT_STATE", verifier_status="FAIL_CURRENT_STATE"),
        grounded_candidate(candidate_ref_hash="d" * 24, source_line_hash="a2" * 12, root_lineage_key_hash="a3" * 12, source_stage="stage_generic", target_semantic_value="FAIL_CURRENT_STATE", verifier_status="FAIL_CURRENT_STATE"),
        grounded_candidate(candidate_ref_hash="e" * 24, source_line_hash="a4" * 12, root_lineage_key_hash="a5" * 12, source_stage="stage_generic", target_semantic_value="INSUFFICIENT_EVIDENCE", verifier_status="INSUFFICIENT_EVIDENCE"),
        grounded_candidate(candidate_ref_hash="f" * 24, source_line_hash="a6" * 12, root_lineage_key_hash="a7" * 12, source_stage="stage_generic", target_semantic_value="INSUFFICIENT_EVIDENCE", verifier_status="INSUFFICIENT_EVIDENCE"),
    ]
    assert module.target_balance_audit(rows)["passed"] is True
    assert module.selected_test_scope_audit(rows)["passed"] is True
    assert module.command_observation_join_audit(rows)["passed"] is True

    assert module.target_balance_audit(rows[:3])["passed"] is False
    assert module.selected_test_scope_audit([grounded_candidate(source_stage="stage_selected_test")])["passed"] is False
    assert module.command_observation_join_audit([grounded_candidate(command_observation_join_hash=None)])["passed"] is False


def test_stage12538_detects_duplicate_command_or_observation_conflicting_labels():
    module = load_builder()
    row_a = grounded_candidate()
    row_b = grounded_candidate(
        candidate_ref_hash="6" * 24,
        source_line_hash="7" * 24,
        root_lineage_key_hash="8" * 24,
        target_semantic_value="FAIL_CURRENT_STATE",
        verifier_status="FAIL_CURRENT_STATE",
        verifier_exit_status_class="exit_nonzero",
    )

    audit = module.duplicate_conflict_audit([row_a, row_b])
    reasons = {conflict["reason"] for conflict in audit["conflicts"]}

    assert audit["duplicate_conflict_count"] == 3
    assert "same_verifier_observation_hash_reused_with_different_target" in reasons
    assert "same_command_result_hash_reused_with_different_target" in reasons


def test_stage12538_remaining_gap_worklist_rolls_up_stage12536_and_stage12537_blockers():
    module = load_builder()
    summary = module.build()
    rows = module.read_jsonl(WORKLIST)
    reasons = {row["blocker_reason"] for row in rows}

    assert rows
    assert summary["remaining_gap_worklist"]["work_item_count"] == len(rows)
    assert "stage12535_rows_lack_real_command_output_observation_hashes" in reasons
    assert "stage12535_target_labels_match_deterministic_rotation_pattern" in reasons
    assert "missing_actual_verifier_command_output_observation_provenance" in reasons
    assert "controlled_fixture_like_not_materialized" in reasons
    for row in rows:
        assert row["remaining_gap_to_500_at_rollup"] == 373
        assert row["training_allowed"] is False
        assert row["countable_train_support"] is False
        assert row["level3_admitted"] is False
        assert row["patch_trace_admitted"] is False
        assert row["repair_claim_admitted"] is False

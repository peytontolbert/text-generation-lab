import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12539_targeted_command_output_source_expansion_planner.py"
SUMMARY = ROOT / "runs/summaries/stage12539_targeted_command_output_source_expansion_planner.json"
PREFLIGHT = (
    ROOT
    / "runs/local/artifacts/stage12539_targeted_command_output_source_expansion_planner"
    / "stage12539_gate_ready_preflight_candidate_rows.jsonl"
)
WORKLIST = (
    ROOT
    / "runs/local/artifacts/stage12539_targeted_command_output_source_expansion_planner"
    / "stage12539_prioritized_source_expansion_worklist.jsonl"
)
BLOCKED = (
    ROOT
    / "runs/local/artifacts/stage12539_targeted_command_output_source_expansion_planner"
    / "stage12539_existing_candidate_gate_blocked_rows.jsonl"
)


def load_builder():
    spec = importlib.util.spec_from_file_location("stage12539_builder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def candidate(ref: str, target: str, **overrides):
    row = {
        "candidate_ref_hash": ref * 24,
        "source_stage": "stage_direct_command_output_fixture",
        "source_line_hash": "1" * 24,
        "root_lineage_key_hash": f"{ref}2" * 12,
        "repo_family_hash": f"{ref}3" * 12,
        "language_family": "python",
        "task_projection": "transition_verifier_transition",
        "target_semantic_value": target,
        "verifier_status": target,
        "actual_verifier_command_output_observation_provenance": True,
        "verifier_command_ref_hash": f"{ref}4" * 12,
        "command_result_id_hash": f"{ref}5" * 12,
        "verifier_exit_status_class": "exit_zero" if target == "PASS_CURRENT_STATE" else "exit_nonzero",
        "verifier_stdout_hash": ref * 64,
        "verifier_stderr_hash": "9" * 64,
        "verifier_output_hash": f"{ref}6" * 12,
        "verifier_observation_hash": f"{ref}7" * 12,
        "target_binding_class": "target_semantic_value_from_observed_verifier_result_status",
        "target_binding_rule_id_hash": f"{ref}8" * 12,
        "source_lineage_checked": True,
        "hydratable_verifier_observation_candidate": True,
        "controlled_fixture_like": False,
        "training_allowed": False,
        "countable_train_support": False,
    }
    row.update(overrides)
    return row


def test_stage12539_current_artifacts_fail_closed_to_worklist_without_preflight_rows():
    module = load_builder()
    summary = module.build()

    assert summary["stage"] == "stage12539_targeted_command_output_source_expansion_planner"
    assert summary["decision"] == "fail_closed_prioritized_source_expansion_worklist_emitted_no_preflight_rows"
    assert summary["gate_ready_preflight_candidate_rows"] == 0
    assert summary["stage12537_candidate_rows_scanned"] == 13
    assert summary["existing_candidate_gate_blocked_rows"] >= 13
    assert summary["target_balance_audit"]["passed"] is False
    assert "INSUFFICIENT_EVIDENCE" in summary["target_balance_audit"]["missing_target_classes"]
    assert summary["target_status_shortfall"] == {"FAIL_CURRENT_STATE": 1, "INSUFFICIENT_EVIDENCE": 2}
    assert summary["selected_test_scope_blocked_rows"] == 7
    assert summary["duplicate_output_audit"]["duplicate_same_target_output_rows_collapsed"] == 1
    assert summary["command_observation_join_hash_present_on_all_prepared_rows"] is True
    assert summary["training_allowed"] is False
    assert summary["countable_train_support"] is False
    assert summary["new_countable_train_support_count"] == 0

    assert module.read_jsonl(PREFLIGHT) == []
    worklist = module.read_jsonl(WORKLIST)
    reasons = {row["blocker_reason"] for row in worklist}
    assert "target_status_shortfall_after_stage12538_gates" in reasons
    assert "stage12538_command_observation_join_hash_missing" in reasons
    assert "stage12538_duplicate_output_hash_requires_collapse_or_block" in reasons
    assert "stage12538_selected_test_scope_not_countable_without_explicit_policy" in reasons
    assert "stage12538_target_balance_failed" in reasons
    shortfall = {row.get("target_status"): row.get("minimum_new_rows_needed") for row in worklist if row.get("blocker_reason") == "target_status_shortfall_after_stage12538_gates"}
    assert shortfall == {"FAIL_CURRENT_STATE": 1, "INSUFFICIENT_EVIDENCE": 2}

    blocked = module.read_jsonl(BLOCKED)
    assert all(row["training_allowed"] is False for row in blocked)
    assert all(row["countable_train_support"] is False for row in blocked)


def test_stage12539_materializes_only_when_join_scope_collapse_and_target_balance_pass():
    module = load_builder()
    rows = [
        candidate("a", "PASS_CURRENT_STATE"),
        candidate("b", "PASS_CURRENT_STATE"),
        candidate("c", "FAIL_CURRENT_STATE"),
        candidate("d", "FAIL_CURRENT_STATE"),
        candidate("e", "INSUFFICIENT_EVIDENCE"),
        candidate("f", "INSUFFICIENT_EVIDENCE"),
    ]

    materialized, blocked, audit = module.materialize_gate_ready_preflight(rows)

    assert len(materialized) == 6
    assert blocked == []
    assert audit["target_balance_audit"]["passed"] is True
    assert audit["command_observation_join_hash_present_on_all_prepared_rows"] is True
    for row in materialized:
        assert row["command_observation_join_hash"]
        assert row["selected_test_scope_policy"] == "non_selected_test_source_scope"
        assert row["training_allowed"] is False
        assert row["countable_train_support"] is False


def test_stage12539_blocks_selected_scope_and_collapses_duplicate_output_before_balance():
    module = load_builder()
    duplicate = candidate("b", "PASS_CURRENT_STATE", verifier_output_hash="same" * 6)
    rows = [
        candidate("a", "PASS_CURRENT_STATE", source_stage="stage_selected_test_scope"),
        duplicate,
        candidate("c", "PASS_CURRENT_STATE", verifier_output_hash="same" * 6),
        candidate("d", "FAIL_CURRENT_STATE"),
        candidate("e", "FAIL_CURRENT_STATE"),
        candidate("f", "INSUFFICIENT_EVIDENCE"),
        candidate("9", "INSUFFICIENT_EVIDENCE"),
    ]

    materialized, blocked, audit = module.materialize_gate_ready_preflight(rows)
    reasons = {reason for row in blocked for reason in row["blocked_reasons"]}

    assert len(materialized) == 0
    assert audit["duplicate_output_audit"]["duplicate_same_target_output_rows_collapsed"] == 1
    assert audit["selected_test_scope_blocked_rows"] == 1
    assert "selected_test_scope_policy_unresolved" in reasons
    assert "duplicate_verifier_output_hash_collapsed_same_target" in reasons
    assert "target_balance_failed_after_join_scope_and_duplicate_collapse" in reasons


def test_stage12539_target_shortfall_solves_max_share_not_only_min_class_counts():
    module = load_builder()
    balance = {
        "target_counts": {"PASS_CURRENT_STATE": 4, "FAIL_CURRENT_STATE": 1},
    }

    assert module.target_shortfall(balance) == {"FAIL_CURRENT_STATE": 1, "INSUFFICIENT_EVIDENCE": 2}

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12540_command_output_verifier_observation_preflight_rows.py"
ROWS = (
    ROOT
    / "runs/local/artifacts/stage12540_command_output_verifier_observation_preflight_rows"
    / "stage12540_real_command_output_verifier_observation_preflight_rows.jsonl"
)
BLOCKED = (
    ROOT
    / "runs/local/artifacts/stage12540_command_output_verifier_observation_preflight_rows"
    / "stage12540_blocked_candidate_rows.jsonl"
)
WORKLIST = (
    ROOT
    / "runs/local/artifacts/stage12540_command_output_verifier_observation_preflight_rows"
    / "stage12540_remaining_materialization_worklist.jsonl"
)


def load_builder():
    spec = importlib.util.spec_from_file_location("stage12540_builder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def candidate(ref: str, target: str, output_hash: str | None = None, **overrides):
    row = {
        "stage": "stage12540_command_output_verifier_observation_preflight_rows",
        "record_type": "stage12540_real_command_output_verifier_observation_preflight_row_v1",
        "candidate_ref_hash": ref * 24,
        "source_stage": "stage_unit_source",
        "source_line_hash": ref * 24,
        "root_lineage_key_hash": f"{ref}1" * 12,
        "repo_family_hash": f"{ref}2" * 12,
        "language_family": "python",
        "task_projection": "transition_verifier_transition",
        "target_semantic_value": target,
        "verifier_status": target,
        "actual_verifier_command_output_observation_provenance": True,
        "verifier_command_ref_hash": f"{ref}3" * 12,
        "command_result_id_hash": f"{ref}4" * 12,
        "verifier_exit_status_class": "exit_nonzero",
        "verifier_stdout_hash": ref * 64,
        "verifier_stderr_hash": "9" * 64,
        "verifier_output_hash": output_hash or f"{ref}5" * 12,
        "verifier_observation_hash": f"{ref}6" * 12,
        "command_observation_join_hash": f"{ref}7" * 12,
        "target_binding_class": "target_semantic_value_from_same_source_observed_verifier_status",
        "target_binding_rule_id_hash": f"{ref}8" * 12,
        "source_lineage_checked": True,
        "hydratable_verifier_observation_candidate": True,
        "controlled_fixture_like": False,
        "selected_test_scope_policy": "non_selected_test_source_scope",
        "selected_test_scope_materialization_allowed": True,
        "training_allowed": False,
        "countable_train_support": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "level3_admitted": False,
        "level4_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
    }
    row.update(overrides)
    return row


def test_stage12540_blocks_current_sources_and_emits_worklist_only():
    module = load_builder()
    summary = module.build()

    assert summary["stage"] == "stage12540_command_output_verifier_observation_preflight_rows"
    assert summary["decision"] == "insufficient_evidence_worklist_only_or_partial_preflight_no_countable_support"
    assert summary["stage12539_target_shortfall"] == {"FAIL_CURRENT_STATE": 1, "INSUFFICIENT_EVIDENCE": 2}
    assert summary["preflight_row_count"] == 0
    assert summary["preflight_status_counts"] == {}
    assert summary["shortfall_satisfied_by_preflight_rows"] is False
    assert summary["command_observation_join_hash_present_on_all_rows"] is True
    assert summary["training_allowed"] is False
    assert summary["countable_train_support"] is False
    assert summary["new_countable_train_support_count"] == 0
    assert summary["controlled_fixture_like_rows"] == 0
    assert summary["selected_test_scope_rows"] == 0
    assert summary["level3_admitted"] is False
    assert summary["patch_trace_admitted"] is False
    assert summary["repair_claim_admitted"] is False
    assert summary["strict_eval_eligible"] is False
    assert summary["source_heldout_admissible"] is False

    assert module.read_jsonl(ROWS) == []
    blocked = module.read_jsonl(BLOCKED)
    reasons = {reason for row in blocked for reason in row["blocked_reasons"]}
    assert "selected_test_scope_not_countable_for_stage12540_source_expansion" in reasons
    assert "controlled_fixture_like_source_not_stage12540_materializable" in reasons
    worklist = module.read_jsonl(WORKLIST)
    shortfalls = {
        row.get("target_status"): row.get("minimum_new_rows_needed")
        for row in worklist
        if row.get("blocker_reason") == "target_status_shortfall_after_stage12540_materialization"
    }
    assert shortfalls == {"FAIL_CURRENT_STATE": 1, "INSUFFICIENT_EVIDENCE": 2}

def test_stage12540_selected_scope_is_blocked_even_when_non_countable():
    module = load_builder()
    row = {"selected_tests": ["tests/test_x.py"], "training_allowed": False, "countable_train_support": False}

    policy, allowed = module.explicitly_non_countable_selected_scope("stage_selected_replay", row)

    assert policy == "selected_test_scope_blocked_for_stage12540_source_expansion"
    assert allowed is False

def test_stage12540_collapse_blocks_prior_and_same_target_duplicate_outputs():
    module = load_builder()
    prior = [candidate("p", "FAIL_CURRENT_STATE", output_hash="already_seen")]
    rows = [
        candidate("a", "FAIL_CURRENT_STATE", output_hash="same"),
        candidate("b", "FAIL_CURRENT_STATE", output_hash="same"),
        candidate("c", "INSUFFICIENT_EVIDENCE", output_hash="already_seen"),
    ]

    accepted, blocked, audit = module.collapse_duplicate_outputs(rows, prior)
    reasons = {reason for row in blocked for reason in row["blocked_reasons"]}

    assert len(accepted) == 1
    assert audit["duplicate_same_target_output_rows_collapsed"] == 1
    assert audit["duplicate_output_rows_matching_prior_candidates_blocked"] == 1
    assert "duplicate_output_hash_collapsed_same_target" in reasons
    assert "duplicate_output_hash_matches_prior_candidate_blocked" in reasons


def test_stage12540_worklist_remains_if_shortfall_not_satisfied():
    module = load_builder()
    selected, blocked, audit = module.select_to_shortfall(
        [candidate("a", "INSUFFICIENT_EVIDENCE")],
        {"FAIL_CURRENT_STATE": 1, "INSUFFICIENT_EVIDENCE": 2},
    )
    worklist = module.build_worklist({"FAIL_CURRENT_STATE": 1, "INSUFFICIENT_EVIDENCE": 2}, audit, blocked)

    assert len(selected) == 1
    shortfalls = {row.get("target_status"): row.get("minimum_new_rows_needed") for row in worklist}
    assert shortfalls == {"FAIL_CURRENT_STATE": 1, "INSUFFICIENT_EVIDENCE": 1}

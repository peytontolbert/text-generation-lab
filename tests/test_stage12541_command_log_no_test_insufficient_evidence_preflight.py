import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12541_command_log_no_test_insufficient_evidence_preflight.py"
SUMMARY = ROOT / "runs/summaries/stage12541_command_log_no_test_insufficient_evidence_preflight.json"
ROWS = (
    ROOT
    / "runs/local/artifacts/stage12541_command_log_no_test_insufficient_evidence_preflight"
    / "stage12541_command_log_insufficient_evidence_preflight_rows.jsonl"
)
BLOCKED = (
    ROOT
    / "runs/local/artifacts/stage12541_command_log_no_test_insufficient_evidence_preflight"
    / "stage12541_blocked_command_log_rows.jsonl"
)
WORKLIST = (
    ROOT
    / "runs/local/artifacts/stage12541_command_log_no_test_insufficient_evidence_preflight"
    / "stage12541_remaining_source_expansion_worklist.jsonl"
)


def load_builder():
    spec = importlib.util.spec_from_file_location("stage12541_builder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_stage12541_emits_one_hash_only_insufficient_preflight_row_and_keeps_gap_open():
    module = load_builder()
    summary = module.build()

    assert summary["stage"] == "stage12541_command_log_no_test_insufficient_evidence_preflight"
    assert summary["decision"] == "partial_insufficient_evidence_preflight_rows_materialized_training_blocked"
    assert summary["stage12540_target_shortfall"] == {"FAIL_CURRENT_STATE": 1, "INSUFFICIENT_EVIDENCE": 2}
    assert summary["preflight_row_count"] == 1
    assert summary["preflight_status_counts"] == {"INSUFFICIENT_EVIDENCE": 1}
    assert summary["remaining_shortfall_after_stage12541"] == {"FAIL_CURRENT_STATE": 1, "INSUFFICIENT_EVIDENCE": 1}
    assert summary["shortfall_satisfied_by_preflight_rows"] is False
    assert summary["selected_test_scope_rows"] == 0
    assert summary["controlled_fixture_like_rows"] == 0
    assert summary["training_allowed"] is False
    assert summary["countable_train_support"] is False
    assert summary["new_countable_train_support_count"] == 0
    assert summary["level3_admitted"] is False
    assert summary["patch_trace_admitted"] is False
    assert summary["repair_claim_admitted"] is False

    rows = module.read_jsonl(ROWS)
    assert len(rows) == 1
    row = rows[0]
    assert row["target_semantic_value"] == "INSUFFICIENT_EVIDENCE"
    assert row["verifier_status"] == "INSUFFICIENT_EVIDENCE"
    assert row["target_binding_class"] == module.TARGET_BINDING_CLASS
    assert row["selected_test_scope_policy"] == "non_selected_test_source_scope"
    assert row["controlled_fixture_like"] is False
    assert row["command_observation_join_hash"]
    forbidden = {"command", "command_text", "cwd", "stdout_tail", "stderr_tail", "stdout_tail_preview", "stderr_tail_preview", "path"}
    assert not (forbidden & set(row))

    worklist = module.read_jsonl(WORKLIST)
    remaining = {
        item.get("target_status"): item.get("minimum_new_rows_needed")
        for item in worklist
        if item.get("blocker_reason") == "target_status_shortfall_after_stage12541_materialization"
    }
    assert remaining == {"FAIL_CURRENT_STATE": 1, "INSUFFICIENT_EVIDENCE": 1}


def test_stage12541_blocks_selected_fixture_and_env_failures():
    module = load_builder()
    module.build()
    blocked = module.read_jsonl(BLOCKED)
    reasons = {reason for row in blocked for reason in row["blocked_reasons"]}

    assert "selected_or_exact_test_scope_not_source_expansion" in reasons
    assert "fixture_or_stage_synthetic_repo_family" in reasons
    assert "fail_status_is_env_or_invalid_command_not_behavior_failure" in reasons


def test_stage12541_no_test_classifier_rejects_selected_scope_even_if_output_has_no_tests():
    module = load_builder()
    index_row = {
        "__line_no": 1,
        "repo_family": "real/repo",
        "language": "python",
        "command": "python -m pytest --collect-only tests/test_x.py",
        "status": "PASS_CURRENT_STATE",
        "stdout_tail_preview": "no tests collected in 0.00s",
        "stderr_tail_preview": "",
        "path": "missing.json",
        "heldout_or_do_not_train_risk": False,
    }

    candidate, blocker = module.candidate_from_command_log(index_row)

    assert candidate is None
    assert blocker is not None
    assert "selected_or_exact_test_scope_not_source_expansion" in blocker["blocked_reasons"]

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12542_remaining_command_output_gap_feasibility_audit.py"
SUMMARY = ROOT / "runs/summaries/stage12542_remaining_command_output_gap_feasibility_audit.json"
FEASIBILITY = (
    ROOT
    / "runs/local/artifacts/stage12542_remaining_command_output_gap_feasibility_audit"
    / "stage12542_command_log_remaining_gap_feasibility_rows.jsonl"
)
WORKLIST = (
    ROOT
    / "runs/local/artifacts/stage12542_remaining_command_output_gap_feasibility_audit"
    / "stage12542_remaining_gap_worklist.jsonl"
)


def load_builder():
    spec = importlib.util.spec_from_file_location("stage12542_builder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_stage12542_is_worklist_only_and_preserves_remaining_shortfall():
    module = load_builder()
    summary = module.build()

    assert summary["stage"] == "stage12542_remaining_command_output_gap_feasibility_audit"
    assert summary["decision"] == "worklist_only_no_additional_safe_command_log_preflight_rows"
    assert summary["new_preflight_row_count"] == 0
    assert summary["remaining_shortfall_after_stage12542"] == {"FAIL_CURRENT_STATE": 1, "INSUFFICIENT_EVIDENCE": 1}
    assert summary["training_allowed"] is False
    assert summary["countable_train_support"] is False
    assert summary["new_countable_train_support_count"] == 0
    assert summary["level3_admitted"] is False
    assert summary["patch_trace_admitted"] is False
    assert summary["repair_claim_admitted"] is False

    rows = module.read_jsonl(FEASIBILITY)
    assert rows
    assert all(row["feasibility"] == "blocked" for row in rows)
    assert all(row["training_allowed"] is False for row in rows)
    assert all(row["countable_train_support"] is False for row in rows)

    worklist = module.read_jsonl(WORKLIST)
    remaining = {
        row.get("target_status"): row.get("minimum_new_rows_needed")
        for row in worklist
        if row.get("blocker_reason") == "target_status_shortfall_after_stage12542_feasibility_audit"
    }
    assert remaining == {"FAIL_CURRENT_STATE": 1, "INSUFFICIENT_EVIDENCE": 1}


def test_stage12542_blocks_env_fail_and_additional_no_test_without_materializing():
    module = load_builder()
    summary = module.build()
    reasons = set(summary["blocked_reason_counts"])

    assert "fail_status_is_env_or_invalid_command_not_behavior_failure" in reasons
    assert "no_additional_nonduplicate_no_test_candidate_after_stage12541" in reasons
    assert "selected_or_exact_test_scope_not_source_expansion" in reasons
    assert "fixture_or_stage_synthetic_repo_family" in reasons


def test_stage12542_fail_classifier_never_admits_directly():
    module = load_builder()
    row = {
        "__line_no": 1,
        "repo_family": "real/repo",
        "language": "python",
        "command": "python -m pytest -q",
        "status": "FAIL_CURRENT_STATE",
        "returncode": 1,
        "stdout_tail_preview": "FAILED tests/test_behavior.py::test_x - AssertionError",
        "stderr_tail_preview": "",
        "heldout_or_do_not_train_risk": False,
    }

    result = module.classify_command_log(row, set())

    assert result["feasibility"] == "blocked"
    assert result["potential_target_status"] == "FAIL_CURRENT_STATE"
    assert "fail_status_not_admissible_without_behavioral_or_build_failure_semantic_review" in result["blocked_reasons"]

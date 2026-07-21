import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12543_remaining_gap_execution_request.py"
SUMMARY = ROOT / "runs/summaries/stage12543_remaining_gap_execution_request.json"
WORK_ITEMS = ROOT / "runs/local/artifacts/stage12543_remaining_gap_execution_request/stage12543_remaining_gap_execution_work_items.jsonl"
RUNBOOK = ROOT / "runs/local/artifacts/stage12543_remaining_gap_execution_request/stage12543_executor_runbook.json"


def load_builder():
    spec = importlib.util.spec_from_file_location("stage12543_builder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_stage12543_is_execution_request_only_with_no_rows_admitted():
    module = load_builder()
    summary = module.build()

    assert summary["stage"] == "stage12543_remaining_gap_execution_request"
    assert summary["decision"] == "execution_request_only_no_rows_admitted"
    assert summary["stage12542_remaining_shortfall"] == {"FAIL_CURRENT_STATE": 1, "INSUFFICIENT_EVIDENCE": 1}
    assert summary["new_preflight_row_count"] == 0
    assert summary["new_countable_train_support_count"] == 0
    assert summary["training_allowed"] is False
    assert summary["countable_train_support"] is False
    assert summary["level3_admitted"] is False
    assert summary["patch_trace_admitted"] is False
    assert summary["repair_claim_admitted"] is False
    assert summary["raw_public_content_emitted"] is False

    work_items = module.read_jsonl(WORK_ITEMS)
    assert len(work_items) == 6
    assert summary["target_status_work_item_counts"] == {"FAIL_CURRENT_STATE": 3, "INSUFFICIENT_EVIDENCE": 3}
    assert all(item["candidate_row_emitted"] is False for item in work_items)
    assert all(item["selected_or_exact_test_scope_allowed"] is False for item in work_items)
    assert all(item["controlled_fixture_like_allowed"] is False for item in work_items)
    assert all(item["stage_synthetic_repo_family_allowed"] is False for item in work_items)
    assert all(item["projection_or_transition_derived_label_allowed"] is False for item in work_items)


def test_stage12543_fail_items_reject_env_and_selected_scope():
    module = load_builder()
    module.build()
    fail_items = [item for item in module.read_jsonl(WORK_ITEMS) if item["target_status_needed"] == "FAIL_CURRENT_STATE"]

    assert fail_items
    for item in fail_items:
        assert item["execution_intent_class"] == "broad_behavioral_or_build_verifier_failure_discovery"
        assert item["verifier_scope_required"] == "broad_repo_or_package_verifier_not_selected_test_not_exact_filter"
        assert "missing_file_or_invalid_path" in item["reject_if"]
        assert "offline_dependency_resolution_failure" in item["reject_if"]
        assert "selected_or_exact_test_filter" in item["reject_if"]


def test_stage12543_runbook_requires_hash_only_public_returns():
    module = load_builder()
    module.build()
    runbook = module.read_json(RUNBOOK)

    assert runbook["decision"] == "execution_request_only_training_blocked"
    assert runbook["executor_output_contract"]["raw_content_public_return_allowed"] is False
    assert "raw_command" in runbook["executor_output_contract"]["required_private_fields"]
    assert "verifier_output_hash" in runbook["executor_output_contract"]["required_public_return_fields"]
    assert "FAIL_CURRENT_STATE must be behavioral/build failure, not env/invalid command" in runbook["acceptance_requires"]

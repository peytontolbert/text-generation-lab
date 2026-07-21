import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12537_command_output_verifier_observation_materialization_preflight.py"
SUMMARY = ROOT / "runs/summaries/stage12537_command_output_verifier_observation_materialization_preflight.json"
CANDIDATES = (
    ROOT
    / "runs/local/artifacts/stage12537_command_output_verifier_observation_materialization_preflight"
    / "real_command_output_verifier_observation_candidate_rows.jsonl"
)
BLOCKERS = (
    ROOT
    / "runs/local/artifacts/stage12537_command_output_verifier_observation_materialization_preflight"
    / "real_command_output_verifier_observation_blocker_worklist.jsonl"
)


def load_builder():
    spec = importlib.util.spec_from_file_location("stage12537_builder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def observed_row(**overrides):
    row = {
        "stage": "stage12216_normalized_verifier_observation_dataset",
        "source_stage": "stage_public_local_fixture_for_stage12537_unit",
        "stage12216_source_line": 7,
        "repo_family": "fixture/repo",
        "root_id": "fixture-root",
        "language_family": "python",
        "controlled_fixture_like": False,
        "command_result": {
            "command_result_id": "stage12205_command_fixture",
            "command": "python -m pytest -q tests/test_fixture.py",
            "cwd": "/tmp/fixture",
            "returncode": 0,
            "stdout_sha256": "a" * 64,
            "stderr_sha256": "b" * 64,
        },
        "observation": {
            "observation_id": "stage12205_observation_fixture",
            "observation_type": "authoritative_selected_verifier_command_output",
            "verifier_status": "PASS_CURRENT_STATE",
        },
        "verifier_result": {
            "verifier_status": "PASS_CURRENT_STATE",
            "verifier_transition": "PASS_CURRENT_STATE",
        },
    }
    row.update(overrides)
    return row


def test_stage12537_builds_sanitized_preflight_candidates_from_real_observations():
    module = load_builder()
    summary = module.build()

    assert summary["stage"] == "stage12537_command_output_verifier_observation_materialization_preflight"
    assert summary["decision"] == "real_command_output_verifier_observation_candidates_materialized_preflight_only"
    assert summary["candidate_row_count"] > 0
    assert summary["stage12216_rows_with_actual_command_output_observation_provenance"] >= summary["candidate_row_count"]
    assert summary["training_allowed"] is False
    assert summary["countable_train_support"] is False
    assert summary["new_countable_train_support_count"] == 0
    assert summary["level3_admitted_rows"] == 0
    assert summary["patch_trace_admitted_rows"] == 0
    assert summary["repair_claim_admitted_rows"] == 0
    assert summary["strict_eval_eligible_count"] == 0
    assert summary["source_heldout_admissible_count"] == 0
    assert summary["guardrail_scan_passed"] is True
    assert summary["raw_leak_count"] == 0

    rows = module.read_jsonl(CANDIDATES)
    assert len(rows) == summary["candidate_row_count"]
    for row in rows:
        assert row["actual_verifier_command_output_observation_provenance"] is True
        assert row["target_binding_class"] == "target_semantic_value_from_observed_verifier_result_status"
        assert row["target_semantic_value"] in module.DIRECT_VERIFIER_STATUSES
        assert row["verifier_command_ref_hash"]
        assert row["command_result_id_hash"]
        assert row["verifier_exit_status_class"] in {"exit_zero", "exit_nonzero"}
        assert len(row["verifier_stdout_hash"]) == 64
        assert len(row["verifier_stderr_hash"]) == 64
        assert row["verifier_output_hash"]
        assert row["training_allowed"] is False
        assert row["countable_train_support"] is False
        assert row["level3_admitted"] is False
        assert row["patch_trace_admitted"] is False
        assert row["repair_claim_admitted"] is False
        assert row["fail_to_pass_claim_admitted"] is False
        assert module.stage12534_constraint_issues(row) == []

    assert module.read_jsonl(BLOCKERS)


def test_stage12537_candidate_target_comes_from_observed_verifier_status_not_index():
    module = load_builder()
    row = observed_row(verifier_result={"verifier_status": "FAIL_CURRENT_STATE"})
    candidate, blocker = module.stage12216_candidate(row)

    assert blocker is None
    assert candidate is not None
    assert candidate["target_semantic_value"] == "FAIL_CURRENT_STATE"
    assert candidate["verifier_status"] == "FAIL_CURRENT_STATE"
    assert candidate["source_lineage_checked"] is True
    assert candidate["stage12534_constraint_preflight_passed"] is True
    assert module.guardrail_scan(candidate)["scan_passed"] is True


def test_stage12537_fails_closed_without_command_output_digest_provenance():
    module = load_builder()
    row = observed_row(command_result={"command_result_id": "stage12205_command_fixture", "returncode": 0})
    candidate, blocker = module.stage12216_candidate(row)

    assert candidate is None
    assert blocker is not None
    assert blocker["candidate_row_emitted"] is False
    assert "missing_actual_verifier_command_output_observation_provenance" in blocker["blocked_reasons"]
    assert blocker["training_allowed"] is False
    assert blocker["level3_admitted"] is False
    assert blocker["repair_claim_admitted"] is False


def test_stage12537_blocks_forbidden_fail_to_pass_status_instead_of_claiming_repair():
    module = load_builder()
    row = observed_row(verifier_result={"verifier_status": "FAIL_TO_PASS"})
    candidate, blocker = module.stage12216_candidate(row)

    assert candidate is None
    assert blocker is not None
    assert "unsupported_or_forbidden_target_status_for_stage12537_preflight" in blocker["blocked_reasons"]
    assert blocker["fail_to_pass_claim_admitted"] is False

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12505_ai_env_extraction_handoff_or_blocker.py"
OUT = ROOT / "runs/local/artifacts/stage12505_ai_env_extraction_handoff_or_blocker"
SUMMARY = ROOT / "runs/summaries/stage12505_ai_env_extraction_handoff_or_blocker.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_stage12505_blocks_context_only_locators_without_training_or_returns() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

    summary = read_json(SUMMARY)
    guardrail = read_json(OUT / "guardrail_scan.json")
    contract = read_json(OUT / "ai_env_private_extraction_handoff_contract.json")
    jobs = read_jsonl(OUT / "ai_env_private_extraction_handoff_jobs.jsonl")
    blockers = read_jsonl(OUT / "ai_env_private_extraction_handoff_blockers.jsonl")

    assert summary["decision"] == "blocked_stage12504_locators_are_context_only_no_ai_env_extraction_handoff"
    assert summary["stage12504_decision"] == "trusted_private_extractor_hash_locator_worklist_ready_training_and_admission_blocked"
    assert summary["input_work_item_count"] == 49
    assert summary["handoff_job_count"] == len(jobs) == 0
    assert summary["blocked_handoff_count"] == len(blockers) == 49
    assert summary["context_only_blocked_count"] == 49
    assert summary["source_stage_locator_ready_count"] == 0
    assert summary["context_locator_only_count"] == 49
    assert summary["materialization_environment"] == "ai_env"
    assert "trellis" in summary["forbidden_materialization_environments"]
    assert summary["stage12503_return_record_type_required"] == (
        "stage12503_authoritative_private_semantic_extraction_return_v1"
    )
    assert summary["stage12503_return_file_role"] == "private_semantic_extraction_returns.jsonl"
    assert summary["stage12503_return_records_written"] == 0
    assert summary["next_stage"] == "rebuild_source_stage_locator_recovery_then_rerun_stage12505"

    assert summary["language_counts"] == {
        "c_cpp": 6,
        "python": 15,
        "rust": 12,
        "web_js_ts_html": 16,
    }
    assert summary["task_family_counts"] == {
        "transition_candidate_selection": 1,
        "transition_continue_or_stop": 16,
        "transition_next_action": 16,
        "transition_verifier_transition": 16,
    }
    assert set(summary["source_stage_counts"]) == {
        "stage12322_priority_rust_cpp_selected_test_admission",
        "stage12331_luxon_web_selected_test_admission",
        "stage12368_cpp_task_specific_selected_test_admission",
        "stage12372_git_rust_task_specific_selected_test_rerender",
        "stage12374_python_task_specific_selected_test_rerender",
        "stage12378_web_fallback_task_specific_selected_test_rerender",
        "stage12380_openclaw_task_specific_selected_test_rerender",
        "stage12382_einops_task_specific_selected_test_rerender",
    }
    assert set(summary["locator_artifact_stage_counts"]) == {
        "stage12500_closed_loop_candidate_packet_router",
        "stage12502_authoritative_private_semantic_extraction_request_preflight",
        "stage12503_private_semantic_extraction_return_validator",
    }
    assert summary["blocker_code_counts"] == {
        "original_source_stage_locator_refs_missing": 49,
    }

    for key in [
        "training_allowed",
        "admission_allowed",
        "packaging_allowed",
        "execution_performed_by_stage",
        "hydration_performed_by_stage",
        "replay_performed_by_stage",
        "network_performed_by_stage",
        "policy_label_materialized",
        "level3_atom_materialized",
        "patch_trace_materialized",
        "stage12503_return_materialized",
        "stage12503_return_file_written",
    ]:
        assert summary[key] is False
        assert contract[key] is False
    for key in [
        "training_rows_emitted",
        "admitted_rows",
        "level3_admitted",
        "level3_atom_count",
        "patch_trace_admitted",
        "patch_trace_rows",
        "stage12496_return_records_written",
        "stage12503_return_records_written",
        "policy_labels_emitted",
        "proof_rows_emitted",
        "proof_grade_repair_rows",
        "external_repair_credit_count",
        "sealed_eval_rows",
    ]:
        assert summary[key] == 0
        assert contract[key] == 0

    assert guardrail["scan_passed"] is True
    assert guardrail["raw_leak_count"] == summary["raw_leak_count"] == 0
    assert contract["materialization_environment"] == "ai_env"
    assert contract["forbidden_materialization_environments"] == ["trellis"]
    assert contract["execution_gate"] == "requires_nonzero_original_source_stage_locator_refs_per_request"

    for row in blockers:
        assert row["record_type"] == "stage12505_ai_env_extraction_handoff_blocker_v1"
        assert row["blocking_decision"] == "blocked_do_not_execute_ai_env_extractor_until_original_source_stage_locators_exist"
        assert row["materialization_environment"] == "ai_env"
        assert row["forbidden_materialization_environments"] == ["trellis"]
        assert row["source_stage_locator_ref_count"] == 0
        assert row["context_locator_ref_count"] > 0
        assert row["source_stage_locator_refs"] == []
        assert "original_source_stage_locator_refs_missing" in row["blocker_codes"]
        assert row["raw_private_values_revealed"] is False
        assert row["raw_locator_values_emitted"] is False
        assert row["public_safe_hash_locator_only"] is True
        assert row["training_allowed"] is False
        assert row["admission_allowed"] is False
        assert row["training_rows_emitted"] == 0
        assert row["admitted_rows"] == 0
        assert row["level3_admitted"] == 0
        assert row["patch_trace_admitted"] == 0
        assert row["stage12503_return_records_written"] == 0
        assert row["stage12503_return_contract"]["return_record_type"] == (
            "stage12503_authoritative_private_semantic_extraction_return_v1"
        )
        assert "trellis" not in row["safe_next_action"]

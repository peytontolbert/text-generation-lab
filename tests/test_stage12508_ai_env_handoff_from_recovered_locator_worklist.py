from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12508_ai_env_handoff_from_recovered_locator_worklist.py"
OUT = ROOT / "runs/local/artifacts/stage12508_ai_env_handoff_from_recovered_locator_worklist"
SUMMARY = ROOT / "runs/summaries/stage12508_ai_env_handoff_from_recovered_locator_worklist.json"


def load_stage12508():
    spec = importlib.util.spec_from_file_location("stage12508", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def valid_work_item(source_stage: str = "stage999_source") -> dict:
    return {
        "request_id_hash": "1" * 24,
        "audit_item_id_hash": "2" * 24,
        "work_item_id_hash": "3" * 24,
        "packet_id_hash": "4" * 24,
        "root_or_window_hash": "5" * 24,
        "source_stage": source_stage,
        "source_kind": "selected_test_bounded_transition_support",
        "task_family": "transition_next_action",
        "language_family": "python",
        "materialization_environment": "ai_env",
        "source_locator_worklist_ready": True,
        "stage12505_rerun_ready": True,
        "stage12503_expected_return_record_type": "stage12503_authoritative_private_semantic_extraction_return_v1",
        "stage12503_return_file_role_hash": "6" * 24,
        "requested_private_extraction_slots": ["same_source_lineage_proof_present"],
        "raw_private_values_revealed": False,
        "raw_locator_values_emitted": False,
        "public_safe_hash_locator_only": True,
        "hash_locator_records": [
            {
                "artifact_stage": "stage12500_closed_loop_candidate_packet_router",
                "locator_id_hash": "a" * 24,
                "artifact_locator_hash": "b" * 24,
                "artifact_file_role_hash": "c" * 24,
                "artifact_content_hash": "d" * 24,
                "matched_lookup_key_count": 1,
                "matched_lookup_key_names": ["request_id_hash"],
                "public_safe_hash_locator_only": True,
                "raw_locator_values_emitted": False,
            },
            {
                "artifact_stage": source_stage,
                "locator_id_hash": "e" * 24,
                "artifact_locator_hash": "f" * 24,
                "artifact_file_role_hash": "0" * 24,
                "artifact_content_hash": "9" * 24,
                "row_locator_hash": "8" * 24,
                "matched_lookup_key_names": ["row_id_hash"],
                "public_safe_hash_locator_only": True,
                "raw_locator_values_emitted": False,
            },
        ],
    }


def write_stage12507_worklist(root: Path, rows: list[dict]) -> None:
    write_jsonl(
        root
        / "runs/local/artifacts/stage12507_recovered_source_locator_integration_preflight/patched_private_extractor_source_locator_worklist.jsonl",
        rows,
    )


def test_stage12508_current_production_emits_49_handoff_jobs_no_blockers() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

    summary = read_json(SUMMARY)
    guardrail = read_json(OUT / "guardrail_scan.json")
    contract = read_json(OUT / "ai_env_private_extraction_handoff_contract.json")
    jobs = read_jsonl(OUT / "ai_env_private_extraction_handoff_jobs.jsonl")
    blockers = read_jsonl(OUT / "ai_env_private_extraction_handoff_blockers.jsonl")

    assert summary["decision"] == (
        "ai_env_private_extraction_handoff_ready_from_stage12507_patched_worklist_training_and_admission_blocked"
    )
    assert summary["input_work_item_count"] == 49
    assert summary["handoff_job_count"] == len(jobs) == 49
    assert summary["blocked_handoff_count"] == len(blockers) == 0
    assert summary["source_stage_locator_ready_count"] == 49
    assert summary["source_stage_locator_ref_total"] == 49
    assert summary["context_locator_ref_total"] == 294
    assert summary["materialization_environment"] == "ai_env"
    assert summary["forbidden_materialization_environments"] == ["trellis"]
    assert "trellis" in summary["forbidden_materialization_environments"]
    assert summary["raw_leak_count"] == 0
    assert guardrail["scan_passed"] is True
    assert guardrail["raw_leak_count"] == 0
    assert contract["materialization_environment"] == "ai_env"
    assert contract["forbidden_materialization_environments"] == ["trellis"]
    assert contract["stage12503_return_record_type_required"] == (
        "stage12503_authoritative_private_semantic_extraction_return_v1"
    )

    for job in jobs:
        assert job["record_type"] == "stage12508_ai_env_private_extraction_handoff_job_v1"
        assert job["materialization_environment"] == "ai_env"
        assert job["forbidden_materialization_environments"] == ["trellis"]
        assert job["source_stage"] not in {
            "stage12500_closed_loop_candidate_packet_router",
            "stage12502_authoritative_private_semantic_extraction_request_preflight",
            "stage12503_private_semantic_extraction_return_validator",
            "stage12504_private_extractor_source_locator_worklist",
            "stage12505_ai_env_extraction_handoff_or_blocker",
            "stage12506_source_stage_locator_recovery_preflight",
            "stage12507_recovered_source_locator_integration_preflight",
            "stage12508_ai_env_handoff_from_recovered_locator_worklist",
        }
        assert job["source_stage_locator_ref_count"] > 0
        assert job["context_locator_ref_count"] > 0
        assert all(ref["artifact_stage"] == job["source_stage"] for ref in job["source_stage_locator_refs"])
        assert all(ref["public_safe_hash_locator_only"] is True for ref in job["source_stage_locator_refs"])
        assert all(ref["public_safe_hash_locator_only"] is True for ref in job["context_locator_refs"])
        assert job["raw_private_values_revealed"] is False
        assert job["raw_locator_values_emitted"] is False
        assert job["public_safe_hash_locator_only"] is True


def test_stage12508_context_only_source_refs_block(tmp_path: Path) -> None:
    stage12508 = load_stage12508()
    row = valid_work_item()
    row["hash_locator_records"] = [row["hash_locator_records"][0]]
    write_stage12507_worklist(tmp_path, [row])

    summary = stage12508.build(tmp_path)
    jobs = read_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12508_ai_env_handoff_from_recovered_locator_worklist/ai_env_private_extraction_handoff_jobs.jsonl"
    )
    blockers = read_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12508_ai_env_handoff_from_recovered_locator_worklist/ai_env_private_extraction_handoff_blockers.jsonl"
    )

    assert summary["handoff_job_count"] == len(jobs) == 0
    assert summary["blocked_handoff_count"] == len(blockers) == 1
    assert "source_stage_locator_refs_missing" in blockers[0]["blocker_codes"]
    assert blockers[0]["context_locator_ref_count"] == 1
    assert blockers[0]["source_stage_locator_ref_count"] == 0


def test_stage12508_missing_stage12507_patched_worklist_blocks(tmp_path: Path) -> None:
    stage12508 = load_stage12508()
    summary = stage12508.build(tmp_path)
    blockers = read_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12508_ai_env_handoff_from_recovered_locator_worklist/ai_env_private_extraction_handoff_blockers.jsonl"
    )

    assert summary["decision"] == "blocked_stage12507_patched_worklist_missing_no_ai_env_handoff"
    assert summary["input_work_item_count"] == 0
    assert summary["handoff_job_count"] == 0
    assert summary["blocked_handoff_count"] == len(blockers) == 1
    assert summary["blocker_code_counts"] == {"stage12507_patched_worklist_missing": 1}
    assert blockers[0]["blocker_codes"] == ["stage12507_patched_worklist_missing"]


def test_stage12508_raw_leak_guard_rejects_raw_looking_content(tmp_path: Path) -> None:
    stage12508 = load_stage12508()
    row = valid_work_item()
    row["unsafe_public_content"] = "diff --git a/private b/private"
    write_stage12507_worklist(tmp_path, [row])

    with pytest.raises(stage12508.RawLeakError):
        stage12508.build(tmp_path)


def test_stage12508_training_admission_and_proof_counters_remain_zero() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)
    summary = read_json(SUMMARY)
    contract = read_json(OUT / "ai_env_private_extraction_handoff_contract.json")
    jobs = read_jsonl(OUT / "ai_env_private_extraction_handoff_jobs.jsonl")

    for key in [
        "training_rows_emitted",
        "admitted_rows",
        "level3_admitted",
        "level3_atom_count",
        "patch_trace_admitted",
        "patch_trace_rows",
        "stage12503_return_records_written",
        "policy_labels_emitted",
        "proof_rows_emitted",
        "proof_grade_repair_rows",
        "external_repair_credit_count",
        "sealed_eval_rows",
    ]:
        assert summary[key] == 0
        assert contract[key] == 0
        assert all(job[key] == 0 for job in jobs)

    for key in [
        "training_allowed",
        "admission_allowed",
        "execution_performed_by_stage",
        "level3_atom_materialized",
        "patch_trace_materialized",
        "stage12503_return_materialized",
        "stage12503_return_file_written",
    ]:
        assert summary[key] is False
        assert contract[key] is False
        assert all(job[key] is False for job in jobs)

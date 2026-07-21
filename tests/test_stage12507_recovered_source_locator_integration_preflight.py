from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12507_recovered_source_locator_integration_preflight.py"
OUT = ROOT / "runs/local/artifacts/stage12507_recovered_source_locator_integration_preflight"
SUMMARY = ROOT / "runs/summaries/stage12507_recovered_source_locator_integration_preflight.json"


def load_stage12507():
    spec = importlib.util.spec_from_file_location("stage12507", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_stage12507_integrates_current_recovered_refs_without_training_or_handoff() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)
    summary = read_json(SUMMARY)
    patched = read_jsonl(OUT / "patched_private_extractor_source_locator_worklist.jsonl")
    blockers = read_jsonl(OUT / "recovered_source_locator_integration_blockers.jsonl")
    contract = read_json(OUT / "recovered_source_locator_integration_contract.json")

    assert summary["decision"] == "recovered_source_locator_integration_ready_for_stage12505_rerun_no_training_or_handoff"
    assert summary["input_work_item_count"] == 49
    assert summary["stage12505_blocker_count"] == 49
    assert summary["stage12506_candidate_count"] == 49
    assert summary["patched_work_item_count"] == len(patched) == 49
    assert summary["integration_blocker_count"] == len(blockers) == 0
    assert summary["integrated_source_stage_locator_ref_count"] == 49
    assert summary["materialization_environment"] == "ai_env"
    assert summary["forbidden_materialization_environments"] == ["trellis"]
    assert summary["raw_leak_count"] == 0
    assert contract["handoff_policy"] == "stage12507_does_not_emit_handoff_jobs_rerun_stage12505_on_patched_worklist"
    assert contract["semantic_proof_policy"] == "locator_recovery_is_not_private_semantic_extraction_or_level3_proof"
    for key in ["training_rows_emitted", "admitted_rows", "level3_admitted", "patch_trace_admitted", "handoff_job_count"]:
        assert summary[key] == 0
        assert contract[key] == 0
    assert all(row["stage12505_rerun_ready"] is True for row in patched)
    assert all(row["stage12505_handoff_emitted_by_stage12507"] is False for row in patched)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def test_stage12507_blocks_when_stage12506_candidate_missing(tmp_path: Path) -> None:
    stage12507 = load_stage12507()
    req = "1" * 24
    work = {
        "request_id_hash": req,
        "audit_item_id_hash": "2" * 24,
        "work_item_id_hash": "3" * 24,
        "packet_id_hash": "4" * 24,
        "root_or_window_hash": "5" * 24,
        "source_stage": "stage999_source",
        "task_family": "transition_next_action",
        "language_family": "python",
        "materialization_environment": "ai_env",
        "hash_locator_records": [{"artifact_stage": "stage12500_closed_loop_candidate_packet_router"}],
    }
    blocker = {"request_id_hash": req, "source_stage": "stage999_source"}
    write_jsonl(tmp_path / "runs/local/artifacts/stage12504_private_extractor_source_locator_worklist/private_extractor_source_locator_worklist.jsonl", [work])
    write_jsonl(tmp_path / "runs/local/artifacts/stage12505_ai_env_extraction_handoff_or_blocker/ai_env_private_extraction_handoff_blockers.jsonl", [blocker])
    write_jsonl(tmp_path / "runs/local/artifacts/stage12506_source_stage_locator_recovery_preflight/source_stage_locator_recovery_candidates.jsonl", [])

    summary = stage12507.build(tmp_path)
    blocked = read_jsonl(tmp_path / "runs/local/artifacts/stage12507_recovered_source_locator_integration_preflight/recovered_source_locator_integration_blockers.jsonl")
    assert summary["patched_work_item_count"] == 0
    assert summary["integration_blocker_count"] == 1
    assert "stage12506_recovery_candidate_missing" in blocked[0]["blocker_codes"]
    assert summary["training_rows_emitted"] == 0
    assert summary["handoff_job_count"] == 0


def test_stage12507_rejects_context_only_recovered_ref(tmp_path: Path) -> None:
    stage12507 = load_stage12507()
    req = "a" * 24
    work = {
        "request_id_hash": req,
        "audit_item_id_hash": "b" * 24,
        "work_item_id_hash": "c" * 24,
        "packet_id_hash": "d" * 24,
        "root_or_window_hash": "e" * 24,
        "source_stage": "stage999_source",
        "task_family": "transition_next_action",
        "language_family": "python",
        "materialization_environment": "ai_env",
        "hash_locator_records": [],
    }
    candidate = {
        "request_id_hash": req,
        "source_stage": "stage999_source",
        "source_stage_locator_refs": [{"artifact_stage": "stage12500_closed_loop_candidate_packet_router", "public_safe_hash_locator_only": True, "raw_locator_values_emitted": False}],
    }
    write_jsonl(tmp_path / "runs/local/artifacts/stage12504_private_extractor_source_locator_worklist/private_extractor_source_locator_worklist.jsonl", [work])
    write_jsonl(tmp_path / "runs/local/artifacts/stage12505_ai_env_extraction_handoff_or_blocker/ai_env_private_extraction_handoff_blockers.jsonl", [{"request_id_hash": req}])
    write_jsonl(tmp_path / "runs/local/artifacts/stage12506_source_stage_locator_recovery_preflight/source_stage_locator_recovery_candidates.jsonl", [candidate])

    summary = stage12507.build(tmp_path)
    blocked = read_jsonl(tmp_path / "runs/local/artifacts/stage12507_recovered_source_locator_integration_preflight/recovered_source_locator_integration_blockers.jsonl")
    assert summary["patched_work_item_count"] == 0
    assert "recovered_original_source_stage_locator_refs_missing" in blocked[0]["blocker_codes"]
    assert summary["context_only_promoted_count"] == 0


def test_stage12507_context_only_source_stage_inputs_still_block(tmp_path: Path) -> None:
    stage12507 = load_stage12507()
    req = "f" * 24
    source_stage = "stage12500_closed_loop_candidate_packet_router"
    work = {
        "request_id_hash": req,
        "audit_item_id_hash": "1" * 24,
        "work_item_id_hash": "2" * 24,
        "packet_id_hash": "3" * 24,
        "root_or_window_hash": "4" * 24,
        "source_stage": source_stage,
        "task_family": "transition_next_action",
        "language_family": "python",
        "materialization_environment": "ai_env",
        "hash_locator_records": [{"artifact_stage": source_stage}],
    }
    candidate = {
        "request_id_hash": req,
        "source_stage": source_stage,
        "source_stage_locator_refs": [{"artifact_stage": source_stage, "public_safe_hash_locator_only": True, "raw_locator_values_emitted": False}],
    }
    write_jsonl(tmp_path / "runs/local/artifacts/stage12504_private_extractor_source_locator_worklist/private_extractor_source_locator_worklist.jsonl", [work])
    write_jsonl(tmp_path / "runs/local/artifacts/stage12505_ai_env_extraction_handoff_or_blocker/ai_env_private_extraction_handoff_blockers.jsonl", [{"request_id_hash": req}])
    write_jsonl(tmp_path / "runs/local/artifacts/stage12506_source_stage_locator_recovery_preflight/source_stage_locator_recovery_candidates.jsonl", [candidate])

    summary = stage12507.build(tmp_path)
    blocked = read_jsonl(tmp_path / "runs/local/artifacts/stage12507_recovered_source_locator_integration_preflight/recovered_source_locator_integration_blockers.jsonl")
    assert summary["patched_work_item_count"] == 0
    assert summary["integration_blocker_count"] == 1
    assert "source_stage_missing_or_context_only" in blocked[0]["blocker_codes"]
    assert "recovered_original_source_stage_locator_refs_missing" in blocked[0]["blocker_codes"]
    assert summary["context_only_promoted_count"] == 0
    assert summary["training_rows_emitted"] == 0
    assert summary["admitted_rows"] == 0
    assert summary["handoff_job_count"] == 0


def test_stage12507_raw_leak_guard_rejects_raw_public_content() -> None:
    stage12507 = load_stage12507()
    with pytest.raises(stage12507.RawLeakError):
        stage12507.enforce_no_raw_leaks({"unsafe": "diff --git a/x b/x"})

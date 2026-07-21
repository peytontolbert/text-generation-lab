from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12511_stage12503_private_return_candidate_ingest.py"
OUT = ROOT / "runs/local/artifacts/stage12511_stage12503_private_return_candidate_ingest"
SUMMARY = ROOT / "runs/summaries/stage12511_stage12503_private_return_candidate_ingest.json"


def load_stage12511():
    spec = importlib.util.spec_from_file_location("stage12511", SCRIPT)
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


def request_row() -> dict:
    slots = [
        "patch_apply_status_present",
        "same_source_lineage_proof_present",
        "state_before_summary_codes_present",
    ]
    return {
        "record_type": "stage12502_private_semantic_extraction_request_v1",
        "request_id_hash": "1" * 24,
        "audit_item_id_hash": "2" * 24,
        "work_item_id_hash": "3" * 24,
        "packet_id_hash": "4" * 24,
        "root_or_window_hash": "5" * 24,
        "source_stage": "stage12374_python_task_specific_selected_test_rerender",
        "source_kind": "selected_test_bounded_transition_support",
        "task_family": "transition_next_action",
        "language_family": "python",
        "requested_private_extraction_slots": slots,
    }


def valid_candidate(req: dict) -> dict:
    slots = req["requested_private_extraction_slots"]
    return {
        "record_type": "stage12503_authoritative_private_semantic_extraction_return_v1",
        "request_id_hash": req["request_id_hash"],
        "audit_item_id_hash": req["audit_item_id_hash"],
        "work_item_id_hash": req["work_item_id_hash"],
        "packet_id_hash": req["packet_id_hash"],
        "root_or_window_hash": req["root_or_window_hash"],
        "source_stage": req["source_stage"],
        "source_kind": req["source_kind"],
        "task_family": req["task_family"],
        "language_family": req["language_family"],
        "extractor_id_hash": "a" * 24,
        "extractor_authority_attestation": True,
        "extractor_conflict_check_hash": "b" * 24,
        "requested_private_extraction_slots": slots,
        "extracted_slot_statuses": {slot: "validated_present" for slot in slots},
        "extracted_slot_proof_hashes": {slot: "c" * 24 for slot in slots},
        "source_locator_hash": "d" * 24,
        "causal_review_hash": "e" * 24,
        "patch_apply_status_enum": "applies",
        "stop_continue_status_enum": "continue",
        "raw_private_values_revealed": False,
        "raw_source_output_included": False,
        "local_model_authority": False,
        "policy_label_emitted": False,
        "acceptance_criteria_passed": True,
        "blocker_codes": [],
        "training_allowed": False,
        "admission_allowed": False,
        "training_rows_emitted": 0,
        "admitted_rows": 0,
    }


def write_requests(root: Path, rows: list[dict]) -> None:
    write_jsonl(
        root
        / "runs/local/artifacts/stage12502_authoritative_private_semantic_extraction_request_preflight/private_semantic_extraction_requests.jsonl",
        rows,
    )


def write_candidates(root: Path, rows: list[dict]) -> None:
    write_jsonl(
        root
        / "runs/local/artifacts/stage12510_ai_env_private_extraction_executor_readiness_audit/private_semantic_extraction_return_candidates.jsonl",
        rows,
    )


def test_stage12511_current_production_matches_candidate_file_state() -> None:
    candidate_file = (
        ROOT
        / "runs/local/artifacts/stage12510_ai_env_private_extraction_executor_readiness_audit/private_semantic_extraction_return_candidates.jsonl"
    )
    candidate_count = len(read_jsonl(candidate_file)) if candidate_file.exists() else 0
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)
    summary = read_json(SUMMARY)
    guardrail = read_json(OUT / "guardrail_scan.json")
    rejected = read_jsonl(OUT / "rejected_private_semantic_extraction_return_candidates.jsonl")

    assert summary["request_count"] == 49
    assert summary["candidate_return_count"] == candidate_count
    assert summary["rejected_candidate_return_count"] == len(rejected)
    assert summary["training_rows_emitted"] == 0
    assert summary["admitted_rows"] == 0
    assert summary["raw_leak_count"] == 0
    assert guardrail["scan_passed"] is True
    if candidate_count:
        assert summary["decision"] == "stage12503_private_return_file_written_from_validated_private_candidates_training_and_admission_blocked"
        assert summary["valid_candidate_return_count"] == candidate_count
        assert summary["stage12503_return_file_written"] is True
        assert summary["stage12503_return_records_written"] == candidate_count
    else:
        assert summary["decision"] == "blocked_private_semantic_extraction_return_candidates_missing_or_invalid_no_returns_written"
        assert summary["valid_candidate_return_count"] == 0
        assert summary["stage12503_return_file_written"] is False
        assert summary["stage12503_return_records_written"] == 0
        assert rejected == []


def test_stage12511_valid_private_candidate_writes_official_return_file(tmp_path: Path) -> None:
    stage12511 = load_stage12511()
    req = request_row()
    write_requests(tmp_path, [req])
    write_candidates(tmp_path, [valid_candidate(req)])

    summary = stage12511.build(tmp_path)
    official = tmp_path / "runs/local/artifacts/stage12502_authoritative_private_semantic_extraction_request_preflight/private_semantic_extraction_returns.jsonl"
    returns = read_jsonl(official)

    assert summary["decision"] == "stage12503_private_return_file_written_from_validated_private_candidates_training_and_admission_blocked"
    assert summary["candidate_return_count"] == 1
    assert summary["valid_candidate_return_count"] == 1
    assert summary["rejected_candidate_return_count"] == 0
    assert summary["stage12503_return_file_written"] is True
    assert summary["stage12503_return_records_written"] == 1
    assert summary["training_rows_emitted"] == 0
    assert summary["admitted_rows"] == 0
    assert len(returns) == 1
    assert returns[0]["training_allowed"] is False
    assert returns[0]["admission_allowed"] is False


def test_stage12511_invalid_candidate_does_not_write_return_file(tmp_path: Path) -> None:
    stage12511 = load_stage12511()
    req = request_row()
    bad = valid_candidate(req)
    bad["acceptance_criteria_passed"] = False
    write_requests(tmp_path, [req])
    write_candidates(tmp_path, [bad])

    summary = stage12511.build(tmp_path)
    official = tmp_path / "runs/local/artifacts/stage12502_authoritative_private_semantic_extraction_request_preflight/private_semantic_extraction_returns.jsonl"
    rejected = read_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12511_stage12503_private_return_candidate_ingest/rejected_private_semantic_extraction_return_candidates.jsonl"
    )

    assert summary["stage12503_return_file_written"] is False
    assert summary["stage12503_return_records_written"] == 0
    assert not official.exists()
    assert summary["rejected_candidate_return_count"] == 1
    assert rejected[0]["rejection_codes"] == ["acceptance_criteria_failed"]


def test_stage12511_mixed_valid_invalid_candidates_fail_closed(tmp_path: Path) -> None:
    stage12511 = load_stage12511()
    req = request_row()
    good = valid_candidate(req)
    bad = valid_candidate(req)
    bad["source_locator_hash"] = "not-a-safe-hash"
    write_requests(tmp_path, [req])
    write_candidates(tmp_path, [good, bad])

    summary = stage12511.build(tmp_path)
    official = tmp_path / "runs/local/artifacts/stage12502_authoritative_private_semantic_extraction_request_preflight/private_semantic_extraction_returns.jsonl"

    assert summary["valid_candidate_return_count"] == 1
    assert summary["rejected_candidate_return_count"] == 1
    assert summary["stage12503_return_file_written"] is False
    assert not official.exists()


def test_stage12511_public_outputs_reject_raw_leak_patterns(tmp_path: Path) -> None:
    stage12511 = load_stage12511()
    req = request_row()
    bad = valid_candidate(req)
    bad["source_stage"] = "stdout from private command output"
    write_requests(tmp_path, [req])
    write_candidates(tmp_path, [bad])

    with pytest.raises(stage12511.RawLeakError):
        stage12511.build(tmp_path)

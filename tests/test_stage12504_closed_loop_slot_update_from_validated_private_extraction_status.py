from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12504_closed_loop_slot_update_from_validated_private_extraction_status.py"
OUT = ROOT / "runs/local/artifacts/stage12504_closed_loop_slot_update_from_validated_private_extraction_status"
SUMMARY = ROOT / "runs/summaries/stage12504_closed_loop_slot_update_from_validated_private_extraction_status.json"
STAGE12503_SCRIPT = ROOT / "scripts/build_stage12503_private_semantic_extraction_return_validator.py"
STAGE12503_OUT = ROOT / "runs/local/artifacts/stage12503_private_semantic_extraction_return_validator"
STAGE12502_OUT = ROOT / "runs/local/artifacts/stage12502_authoritative_private_semantic_extraction_request_preflight"
REQUESTS = STAGE12502_OUT / "private_semantic_extraction_requests.jsonl"
RETURN_FILE = STAGE12502_OUT / "private_semantic_extraction_returns.jsonl"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def valid_return_for(request: dict) -> dict:
    slots = sorted(request["requested_private_extraction_slots"])
    return {
        "record_type": "stage12503_authoritative_private_semantic_extraction_return_v1",
        "request_id_hash": request["request_id_hash"],
        "audit_item_id_hash": request["audit_item_id_hash"],
        "work_item_id_hash": request["work_item_id_hash"],
        "packet_id_hash": request["packet_id_hash"],
        "root_or_window_hash": request["root_or_window_hash"],
        "source_stage": request["source_stage"],
        "source_kind": request["source_kind"],
        "task_family": request["task_family"],
        "language_family": request["language_family"],
        "extractor_id_hash": "a" * 24,
        "extractor_authority_attestation": True,
        "extractor_conflict_check_hash": "b" * 24,
        "source_locator_hash": "c" * 24,
        "causal_review_hash": "d" * 24,
        "requested_private_extraction_slots": slots,
        "extracted_slot_statuses": {slot: "validated_present" for slot in slots},
        "extracted_slot_proof_hashes": {slot: ("e" * 24) for slot in slots},
        "patch_apply_status_enum": "not_applicable",
        "stop_continue_status_enum": "unknown",
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


def run_stage12503_without_returns() -> None:
    old_return_file = RETURN_FILE.read_text(encoding="utf-8") if RETURN_FILE.exists() else None
    try:
        if RETURN_FILE.exists():
            RETURN_FILE.unlink()
        subprocess.run([sys.executable, str(STAGE12503_SCRIPT)], cwd=ROOT, check=True)
    finally:
        if old_return_file is not None:
            RETURN_FILE.parent.mkdir(parents=True, exist_ok=True)
            RETURN_FILE.write_text(old_return_file, encoding="utf-8")


def regenerate_current_pipeline_state() -> None:
    subprocess.run([sys.executable, str(STAGE12503_SCRIPT)], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)


def test_stage12504_blocks_when_no_validated_private_extraction_status_exists() -> None:
    run_stage12503_without_returns()

    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

    summary = read_json(SUMMARY)
    guardrail = read_json(OUT / "guardrail_scan.json")
    updates = read_jsonl(OUT / "closed_loop_proof_slot_update_ledger.jsonl")
    blockers = read_jsonl(OUT / "authoritative_proof_slot_update_blockers.jsonl")

    assert summary["decision"] == "blocked_no_validated_private_semantic_extraction_status_to_apply"
    assert summary["validated_private_semantic_extraction_status_count"] == 0
    assert summary["proof_slot_update_record_count"] == len(updates) == 0
    assert summary["blocked_request_count_carried_forward"] == len(blockers) == 49
    assert summary["event_local_promoted_count"] == 0
    assert summary["guardrail_scan_passed"] is True
    assert guardrail["raw_leak_count"] == summary["raw_leak_count"] == 0

    for key in [
        "training_allowed",
        "admission_allowed",
        "policy_label_materialized",
        "level3_atom_materialized",
        "patch_trace_materialized",
        "event_local_promoted",
    ]:
        assert summary[key] is False
    for key in [
        "training_rows_emitted",
        "admitted_rows",
        "level3_admitted",
        "level3_atom_count",
        "patch_trace_admitted",
        "patch_trace_rows",
        "policy_labels_emitted",
        "proof_rows_emitted",
    ]:
        assert summary[key] == 0

    assert "stage12504_requires_stage12503_validated_private_semantic_extraction_status" in blockers[0]["blocker_codes"]
    assert blockers[0]["training_allowed"] is False
    assert blockers[0]["admission_allowed"] is False
    assert blockers[0]["level3_admitted"] == 0
    assert blockers[0]["patch_trace_admitted"] == 0


def test_stage12504_applies_validated_hash_only_slot_status_without_promotion() -> None:
    old_return_file = RETURN_FILE.read_text(encoding="utf-8") if RETURN_FILE.exists() else None
    try:
        request = read_jsonl(REQUESTS)[0]
        RETURN_FILE.write_text(json.dumps(valid_return_for(request), sort_keys=True) + "\n", encoding="utf-8")
        subprocess.run([sys.executable, str(STAGE12503_SCRIPT)], cwd=ROOT, check=True)

        subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

        summary = read_json(SUMMARY)
        updates = read_jsonl(OUT / "closed_loop_proof_slot_update_ledger.jsonl")
        blockers = read_jsonl(OUT / "authoritative_proof_slot_update_blockers.jsonl")
        stage12503_validated = read_jsonl(STAGE12503_OUT / "validated_private_semantic_extraction_status.jsonl")

        assert summary["decision"] == "authoritative_private_semantic_slot_updates_ingested_level3_admission_blocked"
        assert summary["validated_private_semantic_extraction_status_count"] == len(stage12503_validated) == 1
        assert summary["proof_slot_update_record_count"] == len(updates) == 1
        assert summary["blocked_request_count_carried_forward"] == len(blockers) == 48
        assert summary["proof_slots_updated_counts"] == {
            "authoritative_state_before": 1,
            "patch_apply_status": 1,
            "same_source_causal_lineage": 1,
            "state_delta_or_state_after": 1,
            "stop_continue": 1,
        }
        assert summary["event_local_promoted_count"] == 0

        update = updates[0]
        assert update["slot_update_decision"] == "authoritative_status_applied"
        assert update["updated_proof_slot_count"] == 5
        assert update["proof_slot_updates"]["state_delta_or_state_after"]["validated_present"] is True
        assert update["proof_slot_updates"]["state_delta_or_state_after"]["proof_hash"] == "e" * 24
        assert update["source_locator_hash"] == "c" * 24
        assert update["causal_review_hash"] == "d" * 24
        assert update["level3_complete_after_update"] is False
        assert update["patch_trace_candidate_after_update"] is False
        assert "independent_policy_label_missing" in update["residual_blocker_codes"]
        assert "external_patch_effect_proof_missing" in update["residual_blocker_codes"]

        for row in updates + blockers:
            assert row["raw_private_values_revealed"] is False
            assert row["training_allowed"] is False
            assert row["admission_allowed"] is False
            assert row["training_rows_emitted"] == 0
            assert row["admitted_rows"] == 0
            assert row["level3_admitted"] == 0
            assert row["patch_trace_admitted"] == 0
            assert row["policy_labels_emitted"] == 0
    finally:
        if old_return_file is None:
            if RETURN_FILE.exists():
                RETURN_FILE.unlink()
        else:
            RETURN_FILE.write_text(old_return_file, encoding="utf-8")
        regenerate_current_pipeline_state()

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12503_private_semantic_extraction_return_validator.py"
OUT = ROOT / "runs/local/artifacts/stage12503_private_semantic_extraction_return_validator"
SUMMARY = ROOT / "runs/summaries/stage12503_private_semantic_extraction_return_validator.json"
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


def test_stage12503_blocks_without_authoritative_private_extraction_returns() -> None:
    old_return_file = RETURN_FILE.read_text(encoding="utf-8") if RETURN_FILE.exists() else None
    try:
        if RETURN_FILE.exists():
            RETURN_FILE.unlink()

        subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

        summary = read_json(SUMMARY)
        guardrail = read_json(OUT / "guardrail_scan.json")
        accepted = read_jsonl(OUT / "validated_private_semantic_extraction_status.jsonl")
        rejected = read_jsonl(OUT / "rejected_private_semantic_extraction_returns.jsonl")
        blockers = read_jsonl(OUT / "private_semantic_extraction_ingest_blockers.jsonl")

        assert summary["decision"] == "blocked_no_valid_authoritative_private_semantic_extraction_returns"
        assert summary["stage12502_decision"] == "private_extraction_requests_ready_training_and_admission_blocked"
        assert summary["input_request_count"] == 49
        assert summary["return_file_present"] is False
        assert summary["return_record_count"] == 0
        assert summary["validated_private_semantic_extraction_return_count"] == len(accepted) == 0
        assert summary["rejected_private_semantic_extraction_return_count"] == len(rejected) == 0
        assert summary["blocked_request_count"] == len(blockers) == 49
        assert summary["public_artifact_policy"] == "hash_enum_status_only_no_raw_paths_commands_diffs_source_or_verifier_output"
        assert summary["next_stage"] == "authoritative_private_semantic_extraction_return_acquisition"

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
        assert summary["blocker_code_counts"] == {
            "authoritative_private_semantic_extraction_return_absent": 49,
            "do_not_materialize_labels_or_proofs_from_stage12502_request": 49,
            "honest_ingest_requires_valid_authoritative_return_record": 49,
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
        ]:
            assert summary[key] is False
        for key in [
            "training_rows_emitted",
            "admitted_rows",
            "level3_admitted",
            "level3_atom_count",
            "patch_trace_admitted",
            "patch_trace_rows",
            "stage12496_return_records_written",
            "policy_labels_emitted",
            "proof_rows_emitted",
            "proof_grade_repair_rows",
            "external_repair_credit_count",
            "sealed_eval_rows",
        ]:
            assert summary[key] == 0

        assert guardrail["scan_passed"] is True
        assert guardrail["raw_leak_count"] == summary["raw_leak_count"] == 0
        assert not RETURN_FILE.exists()

        for row in blockers:
            assert row["record_type"] == "stage12503_private_semantic_extraction_ingest_blocker_v1"
            assert row["ingest_decision"] == "blocked"
            assert row["public_safe_status_only"] is True
            assert row["raw_private_values_revealed"] is False
            assert "authoritative_private_semantic_extraction_return_absent" in row["blocker_codes"]
            assert "do_not_materialize_labels_or_proofs_from_stage12502_request" in row["blocker_codes"]
            assert row["training_allowed"] is False
            assert row["admission_allowed"] is False
            assert row["training_rows_emitted"] == 0
            assert row["admitted_rows"] == 0
            assert row["level3_admitted"] == 0
            assert row["patch_trace_admitted"] == 0
            assert row["policy_labels_emitted"] == 0
    finally:
        if old_return_file is not None:
            RETURN_FILE.parent.mkdir(parents=True, exist_ok=True)
            RETURN_FILE.write_text(old_return_file, encoding="utf-8")


def _first_request() -> dict:
    return read_jsonl(REQUESTS)[0]


def _valid_return_for(request: dict) -> dict:
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


def test_stage12503_rejects_incomplete_or_raw_private_returns() -> None:
    old_return_file = RETURN_FILE.read_text(encoding="utf-8") if RETURN_FILE.exists() else None
    try:
        request = _first_request()
        forged = _valid_return_for(request)
        forged.pop("extracted_slot_proof_hashes")
        forged["raw_private_values_revealed"] = True
        forged["raw_output"] = "not public safe"
        RETURN_FILE.write_text(json.dumps(forged, sort_keys=True) + "\n", encoding="utf-8")

        subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

        summary = read_json(SUMMARY)
        rejected = read_jsonl(OUT / "rejected_private_semantic_extraction_returns.jsonl")
        blockers = read_jsonl(OUT / "private_semantic_extraction_ingest_blockers.jsonl")

        assert summary["validated_private_semantic_extraction_return_count"] == 0
        assert summary["rejected_private_semantic_extraction_return_count"] == len(rejected) == 1
        assert summary["blocked_request_count"] == len(blockers) == 49
        assert "extracted_slot_proof_hashes_not_object" in rejected[0]["rejection_codes"]
        assert "raw_private_values_revealed" in rejected[0]["rejection_codes"]
        assert "forbidden_raw_or_label_field_present" in rejected[0]["rejection_codes"]
        assert summary["training_rows_emitted"] == 0
        assert summary["admitted_rows"] == 0
        assert summary["level3_admitted"] == 0
        assert summary["patch_trace_admitted"] == 0
    finally:
        if old_return_file is None:
            if RETURN_FILE.exists():
                RETURN_FILE.unlink()
        else:
            RETURN_FILE.write_text(old_return_file, encoding="utf-8")


def test_stage12503_accepts_only_proof_hashed_extraction_status_not_training() -> None:
    old_return_file = RETURN_FILE.read_text(encoding="utf-8") if RETURN_FILE.exists() else None
    try:
        request = _first_request()
        RETURN_FILE.write_text(json.dumps(_valid_return_for(request), sort_keys=True) + "\n", encoding="utf-8")

        subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

        summary = read_json(SUMMARY)
        accepted = read_jsonl(OUT / "validated_private_semantic_extraction_status.jsonl")
        blockers = read_jsonl(OUT / "private_semantic_extraction_ingest_blockers.jsonl")

        assert summary["decision"] == "validated_private_semantic_extraction_returns_ingested_training_and_admission_blocked"
        assert summary["validated_private_semantic_extraction_return_count"] == len(accepted) == 1
        assert summary["blocked_request_count"] == len(blockers) == 48
        assert accepted[0]["authoritative_extraction_return_validated"] is True
        assert accepted[0]["extracted_slot_proof_hashes"]
        assert accepted[0]["source_locator_hash"] == "c" * 24
        assert accepted[0]["causal_review_hash"] == "d" * 24
        for key in [
            "training_allowed",
            "admission_allowed",
            "policy_label_materialized",
            "level3_atom_materialized",
            "patch_trace_materialized",
        ]:
            assert summary[key] is False
        for key in [
            "training_rows_emitted",
            "admitted_rows",
            "level3_admitted",
            "level3_atom_count",
            "patch_trace_admitted",
            "patch_trace_rows",
            "stage12496_return_records_written",
            "policy_labels_emitted",
        ]:
            assert summary[key] == 0
    finally:
        if old_return_file is None:
            if RETURN_FILE.exists():
                RETURN_FILE.unlink()
        else:
            RETURN_FILE.write_text(old_return_file, encoding="utf-8")

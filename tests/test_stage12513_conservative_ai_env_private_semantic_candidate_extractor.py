from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12513_conservative_ai_env_private_semantic_candidate_extractor.py"
STAGE12511_SCRIPT = ROOT / "scripts/build_stage12511_stage12503_private_return_candidate_ingest.py"
OUT = ROOT / "runs/local/artifacts/stage12513_conservative_ai_env_private_semantic_candidate_extractor"
SUMMARY = ROOT / "runs/summaries/stage12513_conservative_ai_env_private_semantic_candidate_extractor.json"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
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
        "state_delta_codes_present",
        "stop_continue_label_present",
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


def work_order(req: dict, *, locator_count: int = 1) -> dict:
    return {
        "record_type": "stage12509_ai_env_private_extraction_return_work_order_v1",
        "work_order_id_hash": "6" * 24,
        "request_id_hash": req["request_id_hash"],
        "source_stage": req["source_stage"],
        "source_kind": req["source_kind"],
        "task_family": req["task_family"],
        "language_family": req["language_family"],
        "source_stage_locator_ref_count": locator_count,
        "missing_private_proof_slots": req["requested_private_extraction_slots"],
        "training_rows_emitted": 0,
        "admitted_rows": 0,
    }


def test_stage12513_cli_writes_conservative_candidate_returns(tmp_path: Path) -> None:
    req = request_row()
    work_orders = tmp_path / "work_orders.jsonl"
    requests = tmp_path / "requests.jsonl"
    output = tmp_path / "candidates.jsonl"
    write_jsonl(work_orders, [work_order(req)])
    write_jsonl(requests, [req])

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--work-orders-jsonl",
            str(work_orders),
            "--requests-jsonl",
            str(requests),
            "--candidate-output-jsonl",
            str(output),
        ],
        cwd=ROOT,
        check=True,
    )
    rows = read_jsonl(output)
    summary = read_json(SUMMARY)

    assert len(rows) == 1
    row = rows[0]
    assert row["record_type"] == "stage12503_authoritative_private_semantic_extraction_return_v1"
    assert row["training_allowed"] is False
    assert row["admission_allowed"] is False
    assert row["training_rows_emitted"] == 0
    assert row["admitted_rows"] == 0
    assert row["raw_private_values_revealed"] is False
    assert row["raw_source_output_included"] is False
    assert row["extracted_slot_statuses"]["same_source_lineage_proof_present"] == "validated_present"
    assert row["extracted_slot_statuses"]["patch_apply_status_present"] == "blocked_unavailable"
    assert row["extracted_slot_statuses"]["state_before_summary_codes_present"] == "blocked_unavailable"
    assert row["extracted_slot_statuses"]["state_delta_codes_present"] == "blocked_unavailable"
    assert row["extracted_slot_statuses"]["stop_continue_label_present"] == "blocked_unavailable"
    assert summary["candidate_return_count"] == 1
    assert summary["slot_status_counts"]["same_source_lineage_proof_present:validated_present"] == 1


def test_stage12513_candidates_validate_through_stage12511_without_admission(tmp_path: Path) -> None:
    stage12513 = load_module(SCRIPT, "stage12513")
    stage12511 = load_module(STAGE12511_SCRIPT, "stage12511")
    req = request_row()
    work_orders = tmp_path / "work_orders.jsonl"
    requests = tmp_path / "runs/local/artifacts/stage12502_authoritative_private_semantic_extraction_request_preflight/private_semantic_extraction_requests.jsonl"
    candidates = tmp_path / "runs/local/artifacts/stage12510_ai_env_private_extraction_executor_readiness_audit/private_semantic_extraction_return_candidates.jsonl"
    write_jsonl(work_orders, [work_order(req)])
    write_jsonl(requests, [req])

    stage12513.build(work_orders, requests, candidates, tmp_path)
    summary = stage12511.build(tmp_path)
    official = tmp_path / "runs/local/artifacts/stage12502_authoritative_private_semantic_extraction_request_preflight/private_semantic_extraction_returns.jsonl"
    returns = read_jsonl(official)

    assert summary["stage12503_return_file_written"] is True
    assert summary["stage12503_return_records_written"] == 1
    assert summary["training_rows_emitted"] == 0
    assert summary["admitted_rows"] == 0
    assert returns[0]["extracted_slot_statuses"]["patch_apply_status_present"] == "blocked_unavailable"


def test_stage12513_missing_request_blocks_without_candidates(tmp_path: Path) -> None:
    stage12513 = load_module(SCRIPT, "stage12513")
    req = request_row()
    work_orders = tmp_path / "work_orders.jsonl"
    requests = tmp_path / "requests.jsonl"
    output = tmp_path / "candidates.jsonl"
    write_jsonl(work_orders, [work_order(req)])
    write_jsonl(requests, [])

    summary = stage12513.build(work_orders, requests, output, tmp_path)
    blockers = read_jsonl(tmp_path / "runs/local/artifacts/stage12513_conservative_ai_env_private_semantic_candidate_extractor/conservative_candidate_extractor_blockers.jsonl")

    assert summary["candidate_return_count"] == 0
    assert summary["blocker_count"] == 1
    assert summary["blocker_code_counts"] == {"no_candidate_returns_emitted": 1, "request_identity_missing_for_work_order": 1}
    assert not output.exists()
    assert blockers[0]["training_rows_emitted"] == 0
    assert blockers[0]["admitted_rows"] == 0


def test_stage12513_no_locator_does_not_claim_lineage_present(tmp_path: Path) -> None:
    stage12513 = load_module(SCRIPT, "stage12513")
    req = request_row()
    work_orders = tmp_path / "work_orders.jsonl"
    requests = tmp_path / "requests.jsonl"
    output = tmp_path / "candidates.jsonl"
    write_jsonl(work_orders, [work_order(req, locator_count=0)])
    write_jsonl(requests, [req])

    stage12513.build(work_orders, requests, output, tmp_path)
    row = read_jsonl(output)[0]

    assert row["extracted_slot_statuses"]["same_source_lineage_proof_present"] == "blocked_unavailable"
    assert row["extracted_slot_proof_hashes"]["same_source_lineage_proof_present"] is None

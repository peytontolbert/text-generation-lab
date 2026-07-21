from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12512_ai_env_private_extractor_candidate_producer_runner.py"
OUT = ROOT / "runs/local/artifacts/stage12512_ai_env_private_extractor_candidate_producer_runner"
SUMMARY = ROOT / "runs/summaries/stage12512_ai_env_private_extractor_candidate_producer_runner.json"


def load_stage12512():
    spec = importlib.util.spec_from_file_location("stage12512", SCRIPT)
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
    slots = ["state_before_summary_codes_present"]
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


def work_order(req: dict) -> dict:
    return {
        "record_type": "stage12509_ai_env_private_extraction_return_work_order_v1",
        "work_order_id_hash": "6" * 24,
        "request_id_hash": req["request_id_hash"],
        "source_stage": req["source_stage"],
        "task_family": req["task_family"],
        "language_family": req["language_family"],
        "training_rows_emitted": 0,
        "admitted_rows": 0,
    }


def write_inputs(root: Path, reqs: list[dict], work_orders: list[dict]) -> None:
    write_jsonl(
        root / "runs/local/artifacts/stage12502_authoritative_private_semantic_extraction_request_preflight/private_semantic_extraction_requests.jsonl",
        reqs,
    )
    write_jsonl(
        root / "runs/local/artifacts/stage12509_ai_env_private_extraction_return_work_order/ai_env_private_extraction_return_work_orders.jsonl",
        work_orders,
    )


def write_fake_extractor(path: Path, body: str) -> None:
    path.write_text(body.lstrip(), encoding="utf-8")


def test_stage12512_current_production_blocks_without_configured_extractor() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)
    summary = read_json(SUMMARY)
    blockers = read_jsonl(OUT / "private_extractor_candidate_producer_blockers.jsonl")
    contract = read_json(OUT / "private_extractor_candidate_producer_runner_contract.json")

    assert summary["decision"] == "blocked_trusted_ai_env_private_extractor_not_ready_no_candidate_returns_written"
    assert summary["input_work_order_count"] == 49
    assert summary["input_request_count"] == 49
    assert summary["extractor_configured"] is False
    assert summary["execution_performed_by_stage"] is False
    assert summary["candidate_return_records_written"] == 0
    assert summary["stage12503_return_file_written"] is False
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_rows_emitted"] == 0
    assert summary["admitted_rows"] == 0
    assert summary["raw_leak_count"] == 0
    assert summary["blocker_code_counts"] == {"trusted_ai_env_private_extractor_script_missing": 49}
    assert len(blockers) == 49
    assert contract["stage12512_never_writes_official_stage12503_return_file"] is True


def test_stage12512_configured_extractor_writes_candidate_file_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stage12512 = load_stage12512()
    req = request_row()
    write_inputs(tmp_path, [req], [work_order(req)])
    extractor = tmp_path / "extractor.py"
    write_fake_extractor(
        extractor,
        """
from __future__ import annotations
import argparse, json
p=argparse.ArgumentParser()
p.add_argument('--work-orders-jsonl')
p.add_argument('--requests-jsonl')
p.add_argument('--candidate-output-jsonl')
a=p.parse_args()
req=json.loads(open(a.requests_jsonl, encoding='utf-8').read().splitlines()[0])
slots=req['requested_private_extraction_slots']
row={
 'record_type':'stage12503_authoritative_private_semantic_extraction_return_v1',
 'request_id_hash':req['request_id_hash'],
 'audit_item_id_hash':req['audit_item_id_hash'],
 'work_item_id_hash':req['work_item_id_hash'],
 'packet_id_hash':req['packet_id_hash'],
 'root_or_window_hash':req['root_or_window_hash'],
 'source_stage':req['source_stage'],
 'source_kind':req['source_kind'],
 'task_family':req['task_family'],
 'language_family':req['language_family'],
 'extractor_id_hash':'a'*24,
 'extractor_authority_attestation':True,
 'extractor_conflict_check_hash':'b'*24,
 'requested_private_extraction_slots':slots,
 'extracted_slot_statuses':{s:'validated_present' for s in slots},
 'extracted_slot_proof_hashes':{s:'c'*24 for s in slots},
 'source_locator_hash':'d'*24,
 'causal_review_hash':'e'*24,
 'patch_apply_status_enum':'not_applicable',
 'stop_continue_status_enum':'continue',
 'raw_private_values_revealed':False,
 'raw_source_output_included':False,
 'local_model_authority':False,
 'policy_label_emitted':False,
 'acceptance_criteria_passed':True,
 'blocker_codes':[],
 'training_allowed':False,
 'admission_allowed':False,
 'training_rows_emitted':0,
 'admitted_rows':0,
}
open(a.candidate_output_jsonl,'w',encoding='utf-8').write(json.dumps(row, sort_keys=True)+'\\n')
""",
    )
    monkeypatch.setenv("STAGE12512_AI_ENV_PRIVATE_EXTRACTOR_SCRIPT", str(extractor))

    summary = stage12512.build(tmp_path)
    candidate_file = tmp_path / "runs/local/artifacts/stage12510_ai_env_private_extraction_executor_readiness_audit/private_semantic_extraction_return_candidates.jsonl"
    official_return = tmp_path / "runs/local/artifacts/stage12502_authoritative_private_semantic_extraction_request_preflight/private_semantic_extraction_returns.jsonl"

    assert summary["decision"] == "trusted_ai_env_private_extractor_candidate_file_written_rerun_stage12511"
    assert summary["execution_performed_by_stage"] is True
    assert summary["candidate_return_records_written"] == 1
    assert summary["candidate_output_file_present"] is True
    assert candidate_file.exists()
    assert not official_return.exists()
    assert summary["stage12503_return_file_written"] is False
    assert summary["stage12503_return_records_written"] == 0
    assert summary["training_rows_emitted"] == 0
    assert summary["admitted_rows"] == 0


def test_stage12512_nonzero_extractor_exit_blocks_without_candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stage12512 = load_stage12512()
    req = request_row()
    write_inputs(tmp_path, [req], [work_order(req)])
    extractor = tmp_path / "bad_extractor.py"
    write_fake_extractor(extractor, "import sys; sys.exit(7)\n")
    monkeypatch.setenv("STAGE12512_AI_ENV_PRIVATE_EXTRACTOR_SCRIPT", str(extractor))

    summary = stage12512.build(tmp_path)

    assert summary["execution_performed_by_stage"] is True
    assert summary["subprocess_returncode"] == 7
    assert summary["candidate_return_records_written"] == 0
    assert summary["blocker_code_counts"] == {"trusted_extractor_script_nonzero_exit": 1}
    assert summary["stage12503_return_records_written"] == 0


def test_stage12512_rejects_bad_candidate_record_type(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stage12512 = load_stage12512()
    req = request_row()
    write_inputs(tmp_path, [req], [work_order(req)])
    extractor = tmp_path / "bad_record_type.py"
    write_fake_extractor(
        extractor,
        """
from __future__ import annotations
import argparse, json
p=argparse.ArgumentParser(); p.add_argument('--work-orders-jsonl'); p.add_argument('--requests-jsonl'); p.add_argument('--candidate-output-jsonl'); a=p.parse_args()
open(a.candidate_output_jsonl,'w',encoding='utf-8').write(json.dumps({'record_type':'bad'})+'\\n')
""",
    )
    monkeypatch.setenv("STAGE12512_AI_ENV_PRIVATE_EXTRACTOR_SCRIPT", str(extractor))

    summary = stage12512.build(tmp_path)

    assert summary["candidate_return_records_written"] == 0
    assert summary["blocker_code_counts"] == {"trusted_extractor_candidate_record_type_invalid": 1}
    assert summary["stage12503_return_file_written"] is False


def test_stage12512_raw_leak_guard_rejects_public_blocker_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stage12512 = load_stage12512()
    req = request_row()
    wo = work_order(req)
    wo["source_stage"] = "stdout from private command output"
    write_inputs(tmp_path, [req], [wo])

    with pytest.raises(stage12512.RawLeakError):
        stage12512.build(tmp_path)

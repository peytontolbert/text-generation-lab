from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12500_closed_loop_candidate_packet_router.py"
OUT = ROOT / "runs/local/artifacts/stage12500_closed_loop_candidate_packet_router"
SUMMARY = ROOT / "runs/summaries/stage12500_closed_loop_candidate_packet_router.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_stage12500_routes_current_supply_into_closed_loop_candidate_worklist() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

    summary = read_json(SUMMARY)
    guardrail = read_json(OUT / "guardrail_scan.json")
    packets = read_jsonl(OUT / "closed_loop_candidate_packets.jsonl")
    worklist = read_jsonl(OUT / "closed_loop_materialization_worklist.jsonl")
    carryforward = read_jsonl(OUT / "stage12477_action_queue_carryforward.jsonl")

    assert summary["decision"] == "closed_loop_candidate_packets_ready_training_blocked"
    assert summary["input_source_row_count"] == 172
    assert summary["candidate_packet_count"] == len(packets) == 172
    assert summary["materialization_work_item_count"] == len(worklist) == 64
    assert summary["stage12499_blocked_slot_count_carried_forward"] == 24
    assert summary["stage12499_event_local_excluded_count_carried_forward"] == 32
    assert summary["stage12477_action_queue_count_carried_forward"] == len(carryforward) == 4

    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False
    assert summary["packaging_allowed"] is False
    assert summary["execution_performed_by_stage"] is False
    assert summary["training_rows_emitted"] == 0
    assert summary["admitted_rows"] == 0
    assert summary["level3_admitted"] == 0
    assert summary["patch_trace_admitted"] == 0
    assert summary["proof_grade_repair_rows"] == 0
    assert summary["external_repair_credit_count"] == 0
    assert summary["sealed_eval_rows"] == 0

    assert guardrail["scan_passed"] is True
    assert guardrail["raw_leak_count"] == summary["raw_leak_count"] == 0
    assert summary["language_counts"] == {
        "c_cpp": 10,
        "python": 25,
        "rust": 20,
        "session_unknown_language": 91,
        "web_js_ts_html": 26,
    }
    assert summary["task_family_counts"]["event_local_transition_observation"] == 91
    assert summary["task_family_counts"]["transition_next_action"] == 16
    assert summary["source_kind_counts"] == {
        "event_local_observation_status_support": 91,
        "selected_test_bounded_transition_support": 81,
    }
    assert summary["worklist_materialization_focus_counts"] == {
        "same_source_lineage_and_state_delta_recovery": 64,
    }
    assert summary["worklist_task_family_counts"] == {
        "event_local_transition_observation": 15,
        "transition_candidate_selection": 1,
        "transition_continue_or_stop": 16,
        "transition_next_action": 16,
        "transition_verifier_transition": 16,
    }
    assert summary["worklist_language_counts"] == {
        "c_cpp": 6,
        "python": 15,
        "rust": 12,
        "session_unknown_language": 15,
        "web_js_ts_html": 16,
    }
    assert "event_local_rows_are_recovery_only_not_policy_labels_without_independent_review" in summary["stage12501_claim_limits"]
    assert "session_unknown_language_rows_require_language_recovery_before_training_or_eval" in summary["stage12501_claim_limits"]
    assert summary["closed_loop_slot_present_counts"]["candidate_action_set_materialized"] == 172
    assert summary["missing_proof_slot_counts"]["same_source_lineage_proof_present"] == 172

    packet_ids = {packet["packet_id_hash"] for packet in packets}
    assert len(packet_ids) == len(packets)
    for packet in packets:
        assert packet["record_type"] == "stage12500_closed_loop_candidate_packet_v1"
        assert packet["candidate_action_set_status"]["candidate_action_set_materialized"] is True
        assert packet["closed_loop_slot_status"]["level3_complete"] is False
        assert packet["training_allowed"] is False
        assert packet["admission_allowed"] is False
        assert packet["training_rows_emitted"] == 0
        assert packet["admitted_rows"] == 0
        assert packet["level3_admitted"] == 0
        assert packet["patch_trace_admitted"] == 0
        assert "same_source_lineage_proof_present" in packet["missing_proof_slots"]
        assert packet["source_refs_public_policy"] == "hashes_and_enums_only_no_paths_commands_diffs_source_or_verifier_output"

    work_packet_ids = {row["packet_id_hash"] for row in worklist}
    assert work_packet_ids.issubset(packet_ids)
    assert len(work_packet_ids) == len(worklist)
    for row in worklist:
        assert row["record_type"] == "stage12500_materialization_work_item_v1"
        assert row["training_allowed"] is False
        assert row["admission_allowed"] is False
        assert row["training_rows_emitted"] == 0
        assert row["admitted_rows"] == 0
        assert "same_source_lineage_proof_present" in row["required_materialization"]

    for row in carryforward:
        assert row["record_type"] == "stage12500_stage12477_action_queue_carryforward_v1"
        assert row["training_allowed"] is False
        assert row["admission_allowed"] is False
        assert row["emitted_training_rows"] == 0

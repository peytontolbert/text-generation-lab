from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12501_closed_loop_slot_materialization_audit.py"
OUT = ROOT / "runs/local/artifacts/stage12501_closed_loop_slot_materialization_audit"
SUMMARY = ROOT / "runs/summaries/stage12501_closed_loop_slot_materialization_audit.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_stage12501_blocks_unproven_stage12500_materialization_worklist() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

    summary = read_json(SUMMARY)
    guardrail = read_json(OUT / "guardrail_scan.json")
    audits = read_jsonl(OUT / "closed_loop_slot_materialization_audit.jsonl")
    blocked = read_jsonl(OUT / "blocked_closed_loop_slot_materialization.jsonl")
    materialized = read_jsonl(OUT / "materialized_closed_loop_slot_records.jsonl")

    assert summary["decision"] == "closed_loop_slot_materialization_blocked_no_authoritative_private_or_same_source_proofs"
    assert summary["input_stage12500_decision"] == "closed_loop_candidate_packets_ready_training_blocked"
    assert summary["input_work_item_count"] == 64
    assert summary["audit_record_count"] == len(audits) == 64
    assert summary["blocked_work_item_count"] == len(blocked) == 64
    assert summary["materialized_record_count"] == len(materialized) == 0
    assert summary["event_local_blocked_count"] == 15
    assert summary["unknown_language_blocked_count"] == 15

    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False
    assert summary["packaging_allowed"] is False
    assert summary["execution_performed_by_stage"] is False
    assert summary["hydration_performed_by_stage"] is False
    assert summary["private_review_performed_by_stage"] is False
    assert summary["local_model_label_authority_used"] is False
    assert summary["training_rows_emitted"] == 0
    assert summary["admitted_rows"] == 0
    assert summary["level3_admitted"] == 0
    assert summary["level3_atom_count"] == 0
    assert summary["patch_trace_admitted"] == 0
    assert summary["patch_trace_rows"] == 0
    assert summary["proof_grade_repair_rows"] == 0
    assert summary["external_repair_credit_count"] == 0
    assert summary["sealed_eval_rows"] == 0

    assert guardrail["scan_passed"] is True
    assert guardrail["raw_leak_count"] == summary["raw_leak_count"] == 0
    assert summary["language_counts"] == {
        "c_cpp": 6,
        "python": 15,
        "rust": 12,
        "session_unknown_language": 15,
        "web_js_ts_html": 16,
    }
    assert summary["task_family_counts"] == {
        "event_local_transition_observation": 15,
        "transition_candidate_selection": 1,
        "transition_continue_or_stop": 16,
        "transition_next_action": 16,
        "transition_verifier_transition": 16,
    }
    assert summary["source_kind_counts"] == {
        "event_local_observation_status_support": 15,
        "selected_test_bounded_transition_support": 49,
    }

    blocker_counts = summary["blocker_code_counts"]
    assert blocker_counts["same_source_causal_lineage_missing"] == 64
    assert blocker_counts["same_source_lineage_required_by_upstream"] == 49
    assert blocker_counts["candidate_action_set_policy_validity_not_authoritatively_reviewed"] == 64
    assert blocker_counts["observed_action_imitation_not_ruled_out"] == 64
    assert blocker_counts["raw_private_semantic_review_not_performed"] == 64
    assert blocker_counts["state_delta_or_state_after_missing"] == 49
    assert blocker_counts["state_delta_required_by_upstream"] == 49
    assert blocker_counts["event_local_recovery_only_independent_review_missing"] == 15
    assert blocker_counts["language_family_unrecovered"] == 15

    audit_ids = {row["audit_id_hash"] for row in audits}
    assert len(audit_ids) == len(audits)
    for row in audits:
        assert row["record_type"] == "stage12501_closed_loop_slot_materialization_audit_v1"
        assert row["materialization_decision"] == "blocked"
        assert row["materialized_closed_loop_record"] is False
        assert row["level3_candidate"] is False
        assert row["patch_trace_candidate"] is False
        assert row["training_allowed"] is False
        assert row["admission_allowed"] is False
        assert row["training_rows_emitted"] == 0
        assert row["admitted_rows"] == 0
        assert row["level3_atom_count"] == 0
        assert row["patch_trace_rows"] == 0
        assert "same_source_causal_lineage_missing" in row["blocker_codes"]
        assert "observed_action_imitation_not_ruled_out" in row["blocker_codes"]
        assert all(value is False for value in row["proved_slots"].values())

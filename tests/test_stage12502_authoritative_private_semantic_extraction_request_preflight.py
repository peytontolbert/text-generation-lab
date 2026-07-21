from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12502_authoritative_private_semantic_extraction_request_preflight.py"
OUT = ROOT / "runs/local/artifacts/stage12502_authoritative_private_semantic_extraction_request_preflight"
SUMMARY = ROOT / "runs/summaries/stage12502_authoritative_private_semantic_extraction_request_preflight.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_stage12502_preflights_stage12500_worklist_without_materializing_labels() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

    summary = read_json(SUMMARY)
    guardrail = read_json(OUT / "guardrail_scan.json")
    audits = read_jsonl(OUT / "materialization_preflight_item_audit.jsonl")
    requests = read_jsonl(OUT / "private_semantic_extraction_requests.jsonl")
    blockers = read_jsonl(OUT / "materialization_preflight_blockers.jsonl")
    groups = read_jsonl(OUT / "missing_proof_risk_groups.jsonl")

    assert summary["decision"] == "private_extraction_requests_ready_training_and_admission_blocked"
    assert summary["input_work_item_count"] == 64
    assert summary["preflight_item_count"] == len(audits) == 64
    assert summary["private_semantic_extraction_request_count"] == len(requests) == 49
    assert summary["per_item_blocker_count"] == len(blockers) == 15
    assert summary["missing_proof_risk_group_count"] == len(groups)
    assert summary["stage12499_blocked_slot_count_carried_forward"] == 24
    assert summary["stage12499_event_local_excluded_count_carried_forward"] == 32
    assert summary["event_local_promoted_count"] == 0
    assert summary["unknown_language_extraction_request_count"] == 0

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
    assert summary["materialization_focus_counts"] == {
        "same_source_lineage_and_state_delta_recovery": 64,
    }
    assert summary["underrepresented_lane_counts"] == {
        "transition_candidate_selection": 1,
        "transition_evidence_citation": 0,
    }
    assert summary["requestable_private_extraction_slot_counts"]["state_delta_codes_present"] == 49
    assert summary["blocked_proof_slot_counts"]["chosen_action_policy_label_present"] == 64
    assert summary["blocked_proof_slot_counts"]["external_patch_effect_proof_present"] == 64
    assert "event_local_rows_blocked_from_policy_label_use" in summary["required_guards"]
    assert "raw_leakage_guard" in summary["required_guards"]

    for key in [
        "training_allowed",
        "admission_allowed",
        "packaging_allowed",
        "execution_performed_by_stage",
        "hydration_performed_by_stage",
        "replay_performed_by_stage",
        "network_performed_by_stage",
    ]:
        assert summary[key] is False
    for key in [
        "training_rows_emitted",
        "admitted_rows",
        "level3_admitted",
        "patch_trace_admitted",
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

    request_ids = {row["audit_item_id_hash"] for row in requests}
    blocker_ids = {row["audit_item_id_hash"] for row in blockers}
    assert request_ids.isdisjoint(blocker_ids)
    assert len(request_ids | blocker_ids) == len(audits)

    for row in audits:
        assert row["record_type"] == "stage12502_materialization_preflight_item_audit_v1"
        assert row["training_allowed"] is False
        assert row["admission_allowed"] is False
        assert row["training_rows_emitted"] == 0
        assert row["admitted_rows"] == 0
        assert row["level3_admitted"] == 0
        assert row["patch_trace_admitted"] == 0
        assert row["stage12496_return_records_written"] == 0
        assert row["policy_labels_emitted"] == 0
        assert row["proof_rows_emitted"] == 0
        assert row["raw_private_values_revealed"] is False
        assert row["policy_label_materialized"] is False
        assert row["level3_atom_materialized"] is False
        assert row["stage12496_return_materialized"] is False
        assert "chosen_action_policy_label_present" in row["blocked_proof_slots"]
        assert "external_patch_effect_proof_present" in row["blocked_proof_slots"]

    for row in requests:
        assert row["record_type"] == "stage12502_private_semantic_extraction_request_v1"
        assert row["language_family"] != "session_unknown_language"
        assert row["source_kind"] == "selected_test_bounded_transition_support"
        assert "training_rows" in row["forbidden_outputs"]
        assert "policy_labels" in row["forbidden_outputs"]
        assert "raw_private_values" in row["forbidden_outputs"]
        assert "do_not_derive_policy_label_from_observed_action" in row["required_private_review_guards"]
        assert row["policy_labels_emitted"] == 0
        assert row["proof_rows_emitted"] == 0

    for row in blockers:
        assert row["record_type"] == "stage12502_materialization_preflight_blocker_v1"
        assert row["language_family"] == "session_unknown_language"
        assert row["source_kind"] == "event_local_observation_status_support"
        assert "event_local_row_requires_independent_private_review_before_policy_use" in row["blocker_codes"]
        assert "language_family_recovery_required_before_extraction" in row["blocker_codes"]

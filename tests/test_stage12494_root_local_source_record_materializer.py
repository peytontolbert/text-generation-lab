from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12494_root_local_source_record_materializer.py"
OUT = ROOT / "runs/local/artifacts/stage12494_root_local_source_record_materializer"
SUMMARY = ROOT / "runs/summaries/stage12494_root_local_source_record_materializer.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_stage12494_materializes_review_packets_but_blocks_training() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

    summary = read_json(SUMMARY)
    guardrail = read_json(OUT / "guardrail_scan.json")
    packets = read_jsonl(OUT / "root_local_materialization_review_packets.jsonl")
    blocked = read_jsonl(OUT / "blocked_materialization_refs.jsonl")

    assert summary["decision"] == "materialization_review_packets_ready_training_blocked"
    assert summary["review_packet_count"] == len(packets) == 56
    assert summary["blocked_packet_count"] == len(blocked) == 56
    assert summary["complete_review_packet_count"] == 0
    assert summary["language_counts"] == {
        "c_cpp": 14,
        "python": 14,
        "rust": 14,
        "web_js_ts_html": 14,
    }
    assert summary["max_source_family_share"] <= 0.15
    assert guardrail["scan_passed"] is True
    assert summary["raw_leak_count"] == guardrail["raw_leak_count"] == 0
    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False
    assert summary["external_repair_credit_count"] == 0
    assert summary["training_rows_emitted"] == 0

    missing_counts = summary["completion_slot_missing_counts"]
    for slot in [
        "state_before_codes",
        "candidate_action_set_rewritten_hash",
        "independent_policy_label_hash",
        "state_delta_codes",
        "stop_continue_label_hash",
        "renderer_contract_hash",
        "anti_shortcut_audit_hash",
    ]:
        assert missing_counts[slot] == 56

    source_kinds = Counter(row["source_record_kind"] for row in packets)
    assert source_kinds["direct_authoritative_verifier_observation_source"] > 0
    assert source_kinds["direct_verifier_log_bounded_train_support_source"] > 0
    assert source_kinds["combined_train_support_source"] > 0
    assert source_kinds["event_local_observation_status_source"] > 0

    for row in packets:
        assert row["training_allowed"] is False
        assert row["admission_allowed"] is False
        assert row["external_repair_credit_count"] == 0
        assert row["complete_root_local_materialized_rows"] == 0
        assert row["materialization_status"] == "blocked_pending_independent_review"
        assert row["claim_boundary"] == {
            "materialization_review_packet": True,
            "reviewed_train_support": False,
            "level3_closed_loop_episode": False,
            "proof_grade_repair": False,
        }
        assert row["completion_slots_missing"]
        assert "independent_policy_label_missing" in row["blocker_codes"]
        assert "candidate_action_set_must_be_rewritten_without_observed_action_markers" in row["blocker_codes"]

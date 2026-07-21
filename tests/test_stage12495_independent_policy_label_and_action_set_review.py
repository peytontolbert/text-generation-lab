from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12495_independent_policy_label_and_action_set_review.py"
OUT = ROOT / "runs/local/artifacts/stage12495_independent_policy_label_and_action_set_review"
SUMMARY = ROOT / "runs/summaries/stage12495_independent_policy_label_and_action_set_review.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_stage12495_builds_review_worklist_without_gold_labels() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

    summary = read_json(SUMMARY)
    guardrail = read_json(OUT / "guardrail_scan.json")
    rows = read_jsonl(OUT / "independent_policy_label_review_work_items.jsonl")

    assert summary["decision"] == "policy_label_review_worklist_ready_training_blocked"
    assert summary["input_packet_count"] == 56
    assert summary["review_item_count"] == len(rows) == 56
    assert summary["review_completed_count"] == 0
    assert summary["accepted_policy_label_count"] == 0
    assert summary["blocked_review_item_count"] == 56
    assert summary["local_model_suggestions_authoritative_count"] == 0
    assert summary["private_raw_value_output_count"] == 0
    assert summary["observed_action_imitation_failure_count"] == 0
    assert summary["observed_action_exposure_count"] == 8
    assert summary["candidate_action_set_leak_count"] == 0
    assert summary["event_local_input_count"] == 32
    assert summary["event_local_blocked_count"] == 32
    assert summary["event_local_promoted_count"] == 0
    assert summary["language_counts"] == {
        "c_cpp": 14,
        "python": 14,
        "rust": 14,
        "web_js_ts_html": 14,
    }
    assert guardrail["scan_passed"] is True
    assert summary["raw_leak_count"] == guardrail["raw_leak_count"] == 0
    assert summary["training_allowed"] is False
    assert summary["admission_allowed"] is False
    assert summary["external_repair_credit_count"] == 0

    for row in rows:
        assert row["gold_label_status"] == "missing_independent_review"
        assert row["gold_label_hash"] is None
        assert row["reviewer_independence_attestation"] is False
        assert row["local_model_authority"] is False
        assert row["raw_private_values_revealed"] is False
        assert row["observed_action_available_to_labeler"] is False
        assert row["deterministic_blinded_shuffle"] is False
        assert row["candidate_options_public_safe"]
        assert all(option["is_gold"] is False for option in row["candidate_options_public_safe"])
        assert all(option["target_visible"] is False for option in row["candidate_options_public_safe"])
        assert row["training_allowed"] is False
        assert row["admission_allowed"] is False
        assert "independent_policy_label_missing" in row["blocker_codes"]
        assert "reviewer_independence_attestation_missing" in row["blocker_codes"]
        assert "policy_label_missing_independent_evidence_rationale" in row["blocker_codes"]
        assert row["claim_boundary"] == {
            "policy_label_review_work_item": True,
            "reviewed_train_support": False,
            "level3_closed_loop_episode": False,
            "proof_grade_repair": False,
        }

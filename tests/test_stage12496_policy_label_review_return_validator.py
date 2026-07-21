from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12496_policy_label_review_return_validator.py"
RETURN_FILE = (
    ROOT
    / "runs/local/artifacts/stage12495_independent_policy_label_and_action_set_review/"
    "independent_policy_label_review_returns.jsonl"
)
WORK_ITEMS = (
    ROOT
    / "runs/local/artifacts/stage12495_independent_policy_label_and_action_set_review/"
    "independent_policy_label_review_work_items.jsonl"
)
OUT = ROOT / "runs/local/artifacts/stage12496_policy_label_review_return_validator"
SUMMARY = ROOT / "runs/summaries/stage12496_policy_label_review_return_validator.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def run_stage() -> dict:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)
    return read_json(SUMMARY)


def test_stage12496_blocks_when_review_returns_are_missing() -> None:
    old = RETURN_FILE.read_text(encoding="utf-8") if RETURN_FILE.exists() else None
    try:
        if RETURN_FILE.exists():
            RETURN_FILE.unlink()
        summary = run_stage()
        guardrail = read_json(OUT / "guardrail_scan.json")
        accepted = read_jsonl(OUT / "validated_policy_label_review_results.jsonl")

        assert summary["decision"] == "blocked_policy_label_review_returns_missing_or_invalid"
        assert summary["return_file_present"] is False
        assert summary["input_work_item_count"] == 56
        assert summary["review_return_count"] == 0
        assert summary["valid_review_return_count"] == 0
        assert summary["missing_return_count"] == 56
        assert summary["accepted_policy_label_count"] == 0
        assert summary["event_local_input_count"] == 32
        assert summary["event_local_promoted_count"] == 0
        assert summary["rejection_reason_counts"] == {"return_file_missing": 56}
        assert summary["training_allowed"] is False
        assert summary["admission_allowed"] is False
        assert summary["training_rows_emitted"] == 0
        assert summary["admitted_rows"] == 0
        assert guardrail["scan_passed"] is True
        assert summary["raw_leak_count"] == guardrail["raw_leak_count"] == 0
        assert accepted == []
    finally:
        if old is not None:
            RETURN_FILE.write_text(old, encoding="utf-8")


def test_stage12496_rejects_malformed_review_return() -> None:
    old = RETURN_FILE.read_text(encoding="utf-8") if RETURN_FILE.exists() else None
    try:
        item = read_jsonl(WORK_ITEMS)[0]
        RETURN_FILE.parent.mkdir(parents=True, exist_ok=True)
        RETURN_FILE.write_text(
            json.dumps(
                {
                    "record_type": "stage12496_policy_label_review_return_v1",
                    "review_item_id_hash": item["review_item_id_hash"],
                    "packet_id_hash": item["packet_id_hash"],
                    "source_candidate_id_hash": item["source_candidate_id_hash"],
                    "work_item_id_hash": item["work_item_id_hash"],
                    "task_family": item["task_family"],
                    "language_family": item["language_family"],
                    "candidate_option_set_hash": item["candidate_option_set_hash"],
                    "reviewer_independence_attestation": False,
                    "local_model_authority": True,
                    "raw_private_values_revealed": False,
                    "observed_action_available_to_labeler": True,
                    "observed_action_used_as_label": True,
                    "event_local_promoted": False,
                    "acceptance_criteria_passed": False,
                    "blocker_codes": ["manual_block"],
                    "training_allowed": True,
                    "admission_allowed": False,
                    "admitted_rows": 0,
                    "training_rows_emitted": 1,
                    "candidate_action_family_count": 1,
                    "hard_negative_count": 0,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        summary = run_stage()
        rejected = read_jsonl(OUT / "rejected_policy_label_review_returns.jsonl")

        assert summary["return_file_present"] is True
        assert summary["review_return_count"] == 1
        assert summary["valid_review_return_count"] == 0
        assert summary["invalid_review_return_count"] == 1
        assert summary["missing_return_count"] == 55
        assert summary["accepted_policy_label_count"] == 0
        assert summary["local_model_authority_violation_count"] == 1
        assert summary["observed_action_imitation_failure_count"] == 1
        assert summary["training_allowed"] is False
        assert summary["admission_allowed"] is False
        assert rejected
        reasons = set(rejected[0]["reason_codes"])
        assert "reviewer_independence_attestation_missing" in reasons
        assert "local_model_authority_claimed" in reasons
        assert "observed_action_available_to_labeler" in reasons
        assert "observed_action_used_as_label" in reasons
        assert "training_or_admission_requested" in reasons
        assert "nonzero_training_rows_requested" in reasons
    finally:
        if old is None:
            if RETURN_FILE.exists():
                RETURN_FILE.unlink()
        else:
            RETURN_FILE.write_text(old, encoding="utf-8")

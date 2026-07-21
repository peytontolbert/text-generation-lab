from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12499_private_semantic_return_materializer_or_blocker.py"
OUT = ROOT / "runs/local/artifacts/stage12499_private_semantic_return_materializer_or_blocker"
SUMMARY = ROOT / "runs/summaries/stage12499_private_semantic_return_materializer_or_blocker.json"
RETURN_FILE = (
    ROOT
    / "runs/local/artifacts/stage12495_independent_policy_label_and_action_set_review/"
    "independent_policy_label_review_returns.jsonl"
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_stage12499_blocks_without_fabricating_private_semantic_returns() -> None:
    old_return_file = RETURN_FILE.read_text(encoding="utf-8") if RETURN_FILE.exists() else None
    try:
        if RETURN_FILE.exists():
            RETURN_FILE.unlink()

        subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

        summary = read_json(SUMMARY)
        guardrail = read_json(OUT / "guardrail_scan.json")
        blockers = read_jsonl(OUT / "return_production_blocker_slots.jsonl")
        shards = read_jsonl(OUT / "return_production_blocker_shard_manifests.jsonl")
        event_local = read_jsonl(OUT / "event_local_exclusion_preserved.jsonl")

        assert summary["decision"] == "blocked_honest_stage12496_return_materialization_missing_private_semantic_proofs"
        assert summary["input_work_item_count"] == 56
        assert summary["stage12498_slot_count"] == 24
        assert summary["eligible_slot_count"] == len(blockers) == 24
        assert summary["blocked_slot_count"] == 24
        assert summary["return_file_preexisting"] is False
        assert summary["return_file_created_by_stage"] is False
        assert summary["return_records_written"] == 0
        assert summary["stage12496_return_records_written"] == 0
        assert summary["stage12496_validatable_return_count"] == 0
        assert summary["independent_semantic_label_materialized_count"] == 0
        assert summary["candidate_action_set_rewrite_materialized_count"] == 0
        assert summary["state_before_review_materialized_count"] == 0
        assert summary["state_delta_review_materialized_count"] == 0
        assert summary["hard_negative_audit_materialized_count"] == 0
        assert summary["anti_shortcut_audit_materialized_count"] == 0
        assert summary["option_permutation_audit_materialized_count"] == 0
        assert summary["blinded_shuffle_materialized_count"] == 0
        assert summary["fabrication_prevented_count"] == 24
        assert summary["event_local_input_count"] == 32
        assert summary["event_local_excluded_count"] == len(event_local) == 32
        assert summary["event_local_promoted_count"] == 0
        assert summary["training_allowed"] is False
        assert summary["admission_allowed"] is False
        assert summary["training_rows_emitted"] == 0
        assert summary["admitted_rows"] == 0
        assert summary["reviewed_train_support_rows"] == 0
        assert summary["proof_grade_repair_rows"] == 0
        assert summary["external_repair_credit_count"] == 0
        assert summary["independent_policy_labels_validated"] == 0
        assert guardrail["scan_passed"] is True
        assert summary["raw_leak_count"] == guardrail["raw_leak_count"] == 0
        assert not RETURN_FILE.exists()

        assert summary["language_counts"] == {
            "c_cpp": 6,
            "python": 6,
            "rust": 6,
            "web_js_ts_html": 6,
        }
        assert summary["task_family_counts"] == {
            "transition_continue_or_stop": 8,
            "transition_next_action": 8,
            "transition_verifier_transition": 8,
        }
        assert len(shards) == 12
        assert {shard["slot_count"] for shard in shards} == {2}

        required_missing = {
            "candidate_action_set_rewritten_hash",
            "independent_policy_label_hash",
            "state_before_semantic_review_hash",
            "state_delta_semantic_review_hash",
            "hard_negative_audit_hash",
            "anti_shortcut_audit_hash",
            "option_permutation_audit_hash",
            "deterministic_blinded_shuffle_hash",
        }
        for row in blockers:
            assert row["return_eligible_for_stage12496"] is True
            assert row["return_created"] is False
            assert row["can_honestly_materialize_return"] is False
            assert row["identity_field_mismatch_count"] == 0
            assert required_missing.issubset(set(row["missing_private_proof_fields"]))
            assert "honest_stage12496_return_would_require_fabrication" in row["blocker_codes"]
            assert row["raw_private_values_revealed"] is False
            assert row["observed_action_available_to_labeler"] is False
            assert row["observed_action_used_as_label"] is False
            assert row["local_model_authority"] is False
            assert row["event_local_promoted"] is False
            assert row["training_allowed"] is False
            assert row["admission_allowed"] is False
            assert row["training_rows_emitted"] == 0
            assert row["admitted_rows"] == 0
            assert row["stage12496_return_records_written"] == 0

        for ref in event_local:
            assert ref["return_eligible_for_stage12496"] is False
            assert ref["event_local_promoted"] is False
            assert ref["training_rows_emitted"] == 0
            assert ref["admitted_rows"] == 0
    finally:
        if old_return_file is not None:
            RETURN_FILE.parent.mkdir(parents=True, exist_ok=True)
            RETURN_FILE.write_text(old_return_file, encoding="utf-8")

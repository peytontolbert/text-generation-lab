from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12504_private_extractor_source_locator_worklist.py"
OUT = ROOT / "runs/local/artifacts/stage12504_private_extractor_source_locator_worklist"
SUMMARY = ROOT / "runs/summaries/stage12504_private_extractor_source_locator_worklist.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_stage12504_builds_hash_only_private_extractor_locators_without_returns() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

    summary = read_json(SUMMARY)
    guardrail = read_json(OUT / "guardrail_scan.json")
    worklist = read_jsonl(OUT / "private_extractor_source_locator_worklist.jsonl")
    ready = read_jsonl(OUT / "private_extractor_source_locator_ready.jsonl")
    blockers = read_jsonl(OUT / "private_extractor_source_locator_blockers.jsonl")
    groups = read_jsonl(OUT / "private_extractor_source_locator_groups.jsonl")

    assert summary["decision"] == "trusted_private_extractor_hash_locator_worklist_ready_training_and_admission_blocked"
    assert summary["stage12502_decision"] == "private_extraction_requests_ready_training_and_admission_blocked"
    assert summary["stage12503_decision"] in {
        "blocked_no_valid_authoritative_private_semantic_extraction_returns",
        "validated_private_semantic_extraction_returns_ingested_training_and_admission_blocked",
    }
    assert summary["input_request_count"] == len(worklist) == 49
    assert summary["source_locator_ready_count"] == len(ready) == 49
    assert summary["source_locator_blocked_count"] == len(blockers) == 0
    assert summary["hash_locator_record_count"] > 0
    assert summary["max_hash_locators_per_request"] > 0
    assert summary["group_count"] == len(groups)
    assert summary["event_local_promoted_count"] == 0
    assert summary["stage12503_return_record_type_required"] == (
        "stage12503_authoritative_private_semantic_extraction_return_v1"
    )
    assert summary["materialization_environment"] == "ai_env"
    assert "trellis" in summary["forbidden_materialization_environments"]
    assert summary["public_artifact_policy"] == (
        "hashes_stage_ids_enums_only_no_raw_paths_commands_diffs_source_or_verifier_output"
    )
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
        "stage12503_return_materialized",
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
        "stage12503_return_records_written",
        "policy_labels_emitted",
        "proof_rows_emitted",
        "proof_grade_repair_rows",
        "external_repair_credit_count",
        "sealed_eval_rows",
    ]:
        assert summary[key] == 0

    assert guardrail["scan_passed"] is True
    assert guardrail["raw_leak_count"] == summary["raw_leak_count"] == 0

    for row in worklist:
        assert row["record_type"] == "stage12504_private_extractor_source_locator_work_item_v1"
        assert row["source_locator_worklist_ready"] is True
        assert row["blocker_codes"] == []
        assert row["hash_locator_count"] > 0
        assert row["raw_private_values_revealed"] is False
        assert row["raw_locator_values_emitted"] is False
        assert row["public_safe_hash_locator_only"] is True
        assert row["training_allowed"] is False
        assert row["admission_allowed"] is False
        assert row["training_rows_emitted"] == 0
        assert row["admitted_rows"] == 0
        assert row["level3_admitted"] == 0
        assert row["patch_trace_admitted"] == 0
        assert row["stage12503_return_records_written"] == 0
        assert row["materialization_environment"] == "ai_env"
        assert "execute_inside_ai_env_not_trellis" in row["required_private_extractor_actions"]
        assert "emit_only_stage12503_authoritative_private_semantic_extraction_return_v1" in (
            row["required_private_extractor_actions"]
        )
        assert "raw_paths" in row["forbidden_public_outputs"]
        assert "training_rows" in row["forbidden_public_outputs"]
        assert "level3_atoms" in row["forbidden_public_outputs"]
        assert set(row["hash_lookup_keys"]) >= {
            "request_id_hash",
            "work_item_id_hash",
            "packet_id_hash",
            "root_or_window_hash",
        }
        for locator in row["hash_locator_records"]:
            assert locator["record_type"] == "stage12504_hash_only_artifact_locator_v1"
            assert locator["public_safe_hash_locator_only"] is True
            assert locator["raw_locator_values_emitted"] is False
            assert locator["matched_lookup_key_count"] > 0
            assert "artifact_locator_hash" in locator
            assert "artifact_file_role_hash" in locator
            assert "artifact_content_hash" in locator
            assert "artifact_path" not in locator
            assert "raw_path" not in locator

    for row in ready:
        assert row["source_locator_worklist_ready"] is True

    for row in groups:
        assert row["record_type"] == "stage12504_locator_group_summary_v1"
        assert row["source_locator_ready_count"] == row["request_count"]
        assert row["blocked_count"] == 0
        assert row["training_rows_emitted"] == 0
        assert row["admitted_rows"] == 0

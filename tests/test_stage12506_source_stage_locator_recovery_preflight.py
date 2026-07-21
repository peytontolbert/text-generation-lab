from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12506_source_stage_locator_recovery_preflight.py"
OUT = ROOT / "runs/local/artifacts/stage12506_source_stage_locator_recovery_preflight"
SUMMARY = ROOT / "runs/summaries/stage12506_source_stage_locator_recovery_preflight.json"


def load_stage12506():
    spec = importlib.util.spec_from_file_location("stage12506", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def base_work_item(source_stage: str = "stage99999_original_source") -> dict:
    return {
        "record_type": "stage12504_private_extractor_source_locator_work_item_v1",
        "request_id_hash": "111111111111111111111111",
        "audit_item_id_hash": "222222222222222222222222",
        "work_item_id_hash": "333333333333333333333333",
        "packet_id_hash": "444444444444444444444444",
        "root_or_window_hash": "555555555555555555555555",
        "source_stage": source_stage,
        "source_kind": "synthetic_source_kind",
        "task_family": "transition_next_action",
        "language_family": "python",
        "materialization_environment": "ai_env",
        "hash_lookup_keys": {
            "source_row_id_hash": "aaaaaaaaaaaaaaaaaaaaaaaa",
            "source_ref_hash": "bbbbbbbbbbbbbbbbbbbbbbbb",
            "root_or_window_hash": "555555555555555555555555",
            "request_id_hash": "111111111111111111111111",
        },
        "hash_locator_records": [
            {
                "artifact_stage": "stage12500_closed_loop_candidate_packet_router",
                "locator_id_hash": "666666666666666666666666",
                "artifact_locator_hash": "777777777777777777777777",
                "artifact_file_role_hash": "888888888888888888888888",
                "artifact_content_hash": "999999999999999999999999",
                "matched_lookup_key_names": ["request_id_hash"],
                "matched_lookup_key_count": 1,
                "public_safe_hash_locator_only": True,
            }
        ],
    }


def base_stage12505_blocker(source_stage: str = "stage99999_original_source") -> dict:
    row = base_work_item(source_stage)
    return {
        "record_type": "stage12505_ai_env_extraction_handoff_blocker_v1",
        "request_id_hash": row["request_id_hash"],
        "audit_item_id_hash": row["audit_item_id_hash"],
        "work_item_id_hash": row["work_item_id_hash"],
        "packet_id_hash": row["packet_id_hash"],
        "root_or_window_hash": row["root_or_window_hash"],
        "source_stage": source_stage,
        "context_locator_ref_count": 1,
        "source_stage_locator_ref_count": 0,
        "blocker_codes": ["original_source_stage_locator_refs_missing"],
        "materialization_environment": "ai_env",
    }


def write_stage_inputs(tmp_path: Path, work_item: dict, blocker: dict) -> None:
    write_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12504_private_extractor_source_locator_worklist/private_extractor_source_locator_worklist.jsonl",
        [work_item],
    )
    write_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12505_ai_env_extraction_handoff_or_blocker/ai_env_private_extraction_handoff_blockers.jsonl",
        [blocker],
    )
    write_json(
        tmp_path / "runs/summaries/stage12504_private_extractor_source_locator_worklist.json",
        {"decision": "fixture_stage12504_ready"},
    )
    write_json(
        tmp_path / "runs/summaries/stage12505_ai_env_extraction_handoff_or_blocker.json",
        {"decision": "fixture_stage12505_blocked"},
    )


def test_stage12506_current_production_is_deterministic_without_training() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)
    first_candidates = (OUT / "source_stage_locator_recovery_candidates.jsonl").read_text(encoding="utf-8")
    first_blockers = (OUT / "source_stage_locator_recovery_blockers.jsonl").read_text(encoding="utf-8")

    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)
    summary = read_json(SUMMARY)
    guardrail = read_json(OUT / "guardrail_scan.json")
    contract = read_json(OUT / "source_stage_locator_recovery_contract.json")
    candidates = read_jsonl(OUT / "source_stage_locator_recovery_candidates.jsonl")
    blockers = read_jsonl(OUT / "source_stage_locator_recovery_blockers.jsonl")

    assert (OUT / "source_stage_locator_recovery_candidates.jsonl").read_text(encoding="utf-8") == first_candidates
    assert (OUT / "source_stage_locator_recovery_blockers.jsonl").read_text(encoding="utf-8") == first_blockers
    assert summary["input_blocked_item_count"] == 49
    assert summary["recovery_candidate_count"] == len(candidates)
    assert summary["recovery_blocker_count"] == len(blockers)
    assert summary["recovery_candidate_count"] + summary["recovery_blocker_count"] == 49
    assert summary["recovery_candidate_count"] == 49
    assert summary["recovery_blocker_count"] == 0
    assert summary["recovered_source_stage_locator_ref_count"] == 49
    assert summary["handoff_job_count"] == 0
    assert summary["materialization_environment"] == "ai_env"
    assert summary["forbidden_materialization_environments"] == ["trellis"]
    assert summary["raw_leak_count"] == 0
    assert guardrail["scan_passed"] is True
    assert contract["context_only_locator_policy"] == (
        "never_promote_context_only_stage_locators_to_source_stage_locators"
    )
    assert contract["recovery_gate"] == (
        "requires_stage12500_identity_replay_over_stage12385_or_declared_source_stage_and_unique_original_source_stage_row_join"
    )

    for key in [
        "training_rows_emitted",
        "admitted_rows",
        "level3_admitted",
        "patch_trace_admitted",
    ]:
        assert summary[key] == 0
        assert contract[key] == 0
    assert all(
        candidate["source_stage_recovery_verification"]["unique_stage12385_match"]
        and candidate["source_stage_recovery_verification"]["unique_source_stage_artifact_match"]
        and candidate["source_stage_locator_refs"][0]["recovery_method"]
        in {
            "replay_stage12500_identity_over_stage12385_then_unique_row_join_to_source_stage_artifact",
            "replay_stage12500_identity_over_original_source_stage_artifact",
        }
        for candidate in candidates
    )


def test_stage12506_context_only_locators_do_not_pass_as_source_stage_locators(tmp_path: Path) -> None:
    stage12506 = load_stage12506()
    source_stage = "stage12500_closed_loop_candidate_packet_router"
    write_stage_inputs(tmp_path, base_work_item(source_stage), base_stage12505_blocker(source_stage))

    summary = stage12506.build(tmp_path)
    candidates = read_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12506_source_stage_locator_recovery_preflight/source_stage_locator_recovery_candidates.jsonl"
    )
    blockers = read_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12506_source_stage_locator_recovery_preflight/source_stage_locator_recovery_blockers.jsonl"
    )

    assert summary["recovery_candidate_count"] == len(candidates) == 0
    assert summary["recovery_blocker_count"] == len(blockers) == 1
    assert blockers[0]["source_stage_locator_ref_count"] == 0
    assert "source_stage_is_context_only" in blockers[0]["blocker_codes"]
    assert "original_source_stage_locator_refs_unproven" in blockers[0]["blocker_codes"]
    assert summary["context_only_promoted_count"] == 0
    assert summary["training_rows_emitted"] == 0
    assert summary["admitted_rows"] == 0


def test_stage12506_recovers_synthetic_upstream_source_stage_locator(tmp_path: Path) -> None:
    stage12506 = load_stage12506()
    source_stage = "stage99999_original_source"
    work_item = base_work_item(source_stage)
    write_stage_inputs(tmp_path, work_item, base_stage12505_blocker(source_stage))
    write_jsonl(
        tmp_path / f"runs/local/artifacts/{source_stage}/source_rows.jsonl",
        [
            {
                "record_type": "synthetic_source_row_hash_index_v1",
                "source_row_id_hash": "aaaaaaaaaaaaaaaaaaaaaaaa",
                "source_ref_hash": "bbbbbbbbbbbbbbbbbbbbbbbb",
            }
        ],
    )

    summary = stage12506.build(tmp_path)
    candidates = read_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12506_source_stage_locator_recovery_preflight/source_stage_locator_recovery_candidates.jsonl"
    )
    blockers = read_jsonl(
        tmp_path
        / "runs/local/artifacts/stage12506_source_stage_locator_recovery_preflight/source_stage_locator_recovery_blockers.jsonl"
    )

    assert summary["recovery_candidate_count"] == len(candidates) == 1
    assert summary["recovery_blocker_count"] == len(blockers) == 0
    assert summary["training_rows_emitted"] == 0
    assert summary["admitted_rows"] == 0
    assert candidates[0]["source_stage_locator_ref_count"] == 1
    assert candidates[0]["source_stage_locator_refs"][0]["artifact_stage"] == source_stage
    assert candidates[0]["source_stage_locator_refs"][0]["matched_lookup_key_names"] == [
        "source_ref_hash",
        "source_row_id_hash",
    ]
    assert candidates[0]["source_stage_locator_refs"][0]["public_safe_hash_locator_only"] is True
    assert candidates[0]["handoff_job_count"] == 0


def test_stage12506_raw_leak_guard_rejects_raw_looking_public_content() -> None:
    stage12506 = load_stage12506()

    with pytest.raises(stage12506.RawLeakError):
        stage12506.enforce_no_raw_leaks({"unsafe_public_field": "diff --git a/file b/file"})

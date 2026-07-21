from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12549_minijinja_external_patch_effect_replay_request.py"
SPEC = importlib.util.spec_from_file_location("stage12549", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


DIFF = """diff --git a/minijinja/src/value/ops.rs b/minijinja/src/value/ops.rs
--- a/minijinja/src/value/ops.rs
+++ b/minijinja/src/value/ops.rs
@@ -1 +1 @@
-old
+new
"""
TEST_DIFF = """diff --git a/minijinja/tests/test_value.rs b/minijinja/tests/test_value.rs
--- a/minijinja/tests/test_value.rs
+++ b/minijinja/tests/test_value.rs
@@ -1 +1,2 @@
 old
+fn test_slice_and_index() {}
"""


def command_turn(command: str) -> dict[str, object]:
    return {
        "role": "assistant",
        "tool_calls": [{"function": {"arguments": json.dumps({"command": command}), "name": "execute_bash"}}],
    }


def output_turn(exit_code: int, content: str = "") -> dict[str, object]:
    return {"role": "tool", "content": f"{content}\n[Command finished with exit code {exit_code}]"}


def complete_row(after_command: str | None = None) -> dict[str, object]:
    verifier = MODULE.VERIFIER
    return {
        **MODULE.TARGET,
        "model_patch": DIFF,
        "trajectory": [
            command_turn(f"cd /workspace/repo && {verifier} 2>&1"),
            output_turn(101, "compile failed"),
            command_turn(f"cd /workspace/repo && {after_command or verifier} 2>&1"),
            output_turn(0, "test passed"),
            {"role": "tool", "content": TEST_DIFF + "[The command completed with exit code 0.]"},
        ],
    }


def manifest(tmp_path: Path) -> Path:
    path = tmp_path / "locked.jsonl"
    path.write_text('{"unrelated":"value"}\n', encoding="utf-8")
    return path


def build(tmp_path: Path, rows: list[dict[str, object]]) -> dict[str, object]:
    source = tmp_path / "source.parquet"
    source.write_bytes(b"unit parquet identity")
    return MODULE.build_request(source, rows=rows, manifest_paths=[manifest(tmp_path)])["request"]


def test_missing_source_fails_closed(tmp_path: Path) -> None:
    result = MODULE.build_request(tmp_path / "missing.parquet", rows=[complete_row()], manifest_paths=[manifest(tmp_path)])["request"]
    assert result["source_binding_valid"] is False
    assert "source_parquet_missing" in result["blocking_reasons"]
    assert result["admission_allowed"] is False


def test_multiple_source_row_matches_fail_closed(tmp_path: Path) -> None:
    result = build(tmp_path, [complete_row(), complete_row()])
    assert result["source_binding_valid"] is False
    assert "source_row_match_count_not_one" in result["blocking_reasons"]


def test_mismatched_verifier_fails_closed(tmp_path: Path) -> None:
    result = build(tmp_path, [complete_row(MODULE.VERIFIER + " --quiet")])
    assert result["source_binding_valid"] is False
    assert "candidate_verifier_identity_mismatch" in result["blocking_reasons"]


def test_missing_diff_fails_closed(tmp_path: Path) -> None:
    row = complete_row()
    row["model_patch"] = ""
    result = build(tmp_path, [row])
    assert result["source_binding_valid"] is False
    assert "source_model_patch_missing_or_not_real_diff" in result["blocking_reasons"]


def test_candidate_authored_nonbaseline_verifier_is_rejected(tmp_path: Path) -> None:
    result = build(tmp_path, [complete_row()])
    assert result["source_native_row_match_count"] == 1
    assert result["source_binding_valid"] is False
    assert result["request_status"] == "rejected_not_replayable"
    assert result["fresh_replay_valid"] is False
    assert "candidate_authored_or_nonbaseline_verifier" in result["blocking_reasons"]
    assert "source_native_base_commit_missing" in result["blocking_reasons"]
    assert result["candidate_evidence"]["trace_co_occurrence_proves_patch_effect"] is False
    assert result["execution_contract"]["candidate_authored_test_or_verifier_allowed"] is False
    assert result["training_allowed"] is False
    assert result["admission_allowed"] is False
    assert result["root_credit"] is False


def test_contract_requires_same_verifier_revert_and_immutable_trees(tmp_path: Path) -> None:
    result = build(tmp_path, [complete_row()])
    contract = result["execution_contract"]
    assert contract["exact_verifier"] == MODULE.VERIFIER
    assert contract["require_verifier_present_at_immutable_baseline"] is True
    assert contract["candidate_authored_test_or_verifier_allowed"] is False
    assert contract["required_exit_sequence"] == [101, 0, 101]
    assert contract["hash_test_tree_before_patch_after_patch_and_after_revert"] is True
    assert contract["revert_model_patch_explicitly"] is True
    assert contract["require_locked_manifest_overlap_audit"] is True



def test_open_swe_overlap_is_unresolved_without_authoritative_source_universe(tmp_path: Path) -> None:
    result = MODULE.build_request(
        tmp_path / "source.parquet",
        rows=[],
        manifest_paths=[manifest(tmp_path)],
    )
    overlap = result["overlap"]
    assert overlap["source_universe"] == "open_swe_traces"
    assert overlap["authoritative_source_universe_covered"] is False
    assert overlap["overlap_resolved"] is False
    assert overlap["overlap_clear"] is False
    assert "authoritative_open_swe_protected_universe_missing" in result["request"]["blocking_reasons"]


def test_self_attested_replay_dictionary_never_becomes_valid(tmp_path: Path) -> None:
    fake = {
        "fresh_checkout_created": True,
        "checkout_before_full_commit_sha": "1" * 40,
        "checkout_before_clean": True,
        "test_tree_before_sha256": "2" * 64,
        "test_tree_after_patch_sha256": "2" * 64,
        "test_tree_after_revert_sha256": "2" * 64,
        "applied_model_patch_sha256": MODULE.sha256_text(DIFF),
        "model_patch_applied_explicitly": True,
        "before_verifier_command": MODULE.VERIFIER,
        "before_exit_code": 101,
        "after_verifier_command": MODULE.VERIFIER,
        "after_exit_code": 0,
        "model_patch_reverted_explicitly": True,
        "revert_verifier_command": MODULE.VERIFIER,
        "revert_exit_code": 101,
        "environment_capture_sha256": "3" * 64,
        "cargo_lock_before_sha256": "4" * 64,
        "cargo_lock_after_sha256": "4" * 64,
    }
    source = tmp_path / "source.parquet"
    source.write_bytes(b"unit parquet identity")
    result = MODULE.build_request(
        source,
        rows=[complete_row()],
        manifest_paths=[manifest(tmp_path)],
        fresh_replay=fake,
    )["request"]
    assert result["fresh_replay_valid"] is False
    assert "content_addressed_executor_evidence_not_verified" in result["blocking_reasons"]

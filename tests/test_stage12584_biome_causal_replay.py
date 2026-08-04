from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_or_run_stage12584_biome_causal_replay.py"
SPEC = importlib.util.spec_from_file_location("stage12584", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)
ARTIFACTS = ROOT / "runs/local/artifacts/stage12584_biome_causal_replay"


def read_single_jsonl(path: Path) -> dict[str, object]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    assert len(rows) == 1
    return rows[0]


def all_keys(value: object):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from all_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_keys(child)


def test_pinned_commit_path_split_and_hashes_regenerate_exactly() -> None:
    pinned = mod.validate_pinned_source()
    assert pinned["commit_changed_paths"] == sorted(mod.EXPECTED_COMMIT_PATHS)
    assert pinned["test_only_paths"] == list(mod.TEST_PATHS)
    assert pinned["production_only_paths"] == list(mod.PRODUCTION_PATHS)
    assert pinned["excluded_paths"] == list(mod.EXCLUDED_PATHS)
    assert pinned["path_overlap"] == []
    assert pinned["diff_hashes"] == {
        "test_patch_sha256": mod.TEST_PATCH_SHA256,
        "production_patch_sha256": mod.PRODUCTION_PATCH_SHA256,
        "selected_diff_sha256": mod.SELECTED_DIFF_SHA256,
        "excluded_diff_sha256": mod.EXCLUDED_DIFF_SHA256,
        "full_diff_sha256": mod.FULL_DIFF_SHA256,
    }


def suite_output(status: str, passed: int, failed: int, test_status: str, duration: str = "0.29s") -> str:
    return (
        "running 33 tests\n"
        f"test {mod.EXPECTED_TEST_NAME} ... {test_status}\n"
        f"test result: {status}. {passed} passed; {failed} failed; 0 ignored; "
        f"0 measured; 0 filtered out; finished in {duration}\n"
    )


def binary_stderr(temp_token: str = "abc") -> str:
    return (
        "Running tests/spec_tests.rs "
        f"(/data/tmp/{mod.STAGE}-{temp_token}/target/debug/deps/spec_tests-deadbeef)\n"
    )


def synthetic_observation(
    *,
    label: str = "before",
    test_name: str | None = None,
    test_status: str | None = None,
    binary_path: str = "tests/spec_tests.rs",
    temp_token: str = "abc",
    duration: str = "0.29s",
    process_duration: float = 4.2,
) -> dict[str, object]:
    expected = mod.EXPECTED_BEFORE if label == "before" else mod.EXPECTED_AFTER
    status = "FAILED" if label == "before" else "ok"
    expected_test_status = mod.EXPECTED_TEST_STATUS[label]
    stdout = suite_output(
        status,
        expected["passed"],
        expected["failed"],
        test_status or expected_test_status,
        duration,
    )
    if test_name is not None:
        stdout = stdout.replace(mod.EXPECTED_TEST_NAME, test_name)
    stderr = binary_stderr(temp_token).replace(mod.EXPECTED_TEST_BINARY, binary_path)
    observation = {
        "return_code": expected["exit_code"],
        "timed_out": False,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_sha256": mod.sha256_bytes(stdout.encode()),
        "stderr_sha256": mod.sha256_bytes(stderr.encode()),
        "duration_seconds": process_duration,
        "cwd": f"/data/tmp/{mod.STAGE}-{temp_token}/biome",
        "logical_command": "cargo test -p biome_migrate",
        "verifier_identity_sha256": "a" * 64,
        "suite_results": mod.parse_test_results(stdout),
        "test_binary_headers": mod.parse_test_binary_headers(stderr),
    }
    mod.validate_observation(observation, expected, label)
    return observation


def test_cargo_result_parser_retains_all_tuples_and_hashes() -> None:
    output = (
        "running 33 tests\n"
        f"test {mod.EXPECTED_TEST_NAME} ... ok\n"
        "test result: ok. 33 passed; 0 failed; 0 ignored; finished in 0.29s\n"
        "running 0 tests\n"
        "test result: ok. 0 passed; 0 failed; 0 ignored; finished in 0.00s\n"
    )
    results = mod.parse_test_results(output)
    assert [(row["passed"], row["failed"]) for row in results] == [(33, 0), (0, 0)]
    assert [row["declared_test_count"] for row in results] == [33, 0]
    assert all(len(row["result_line_sha256"]) == 64 for row in results)
    with pytest.raises(mod.GateError, match="cargo_test_results_missing"):
        mod.parse_test_results("Finished test profile")


def test_observation_validation_binds_binary_suite_and_named_test() -> None:
    observation = synthetic_observation()
    binding = observation["intended_suite_binding"]
    assert observation["expected_suite_tuple"] == [32, 1]
    assert binding["package"] == "biome_migrate"
    assert binding["test_binary_source_path"] == mod.EXPECTED_TEST_BINARY
    assert binding["named_test"]["name"] == mod.EXPECTED_TEST_NAME
    assert binding["named_test"]["status"] == "failed"


def test_observation_validation_rejects_adversarial_count_only_matches() -> None:
    with pytest.raises(mod.GateError, match="named_test_evidence_match_count"):
        synthetic_observation(test_name="specs::unrelated_count_collision")
    with pytest.raises(mod.GateError, match="named_test_status_mismatch"):
        synthetic_observation(test_status="ok")
    with pytest.raises(mod.GateError, match="intended_test_binary_match_count"):
        synthetic_observation(binary_path="tests/unrelated.rs")

    expected = mod.EXPECTED_BEFORE
    stdout = (
        "running 33 tests\n"
        f"test {mod.EXPECTED_TEST_NAME} ... FAILED\n"
        "test result: ok. 33 passed; 0 failed; 0 ignored; finished in 0.1s\n"
        "running 33 tests\n"
        "test specs::unrelated ... FAILED\n"
        "test result: FAILED. 32 passed; 1 failed; 0 ignored; finished in 0.1s\n"
    )
    observation = {
        "return_code": 101,
        "timed_out": False,
        "suite_results": mod.parse_test_results(stdout),
        "test_binary_headers": mod.parse_test_binary_headers(binary_stderr()),
    }
    with pytest.raises(mod.GateError, match="expected_tuple_not_in_intended_suite"):
        mod.validate_observation(observation, expected, "before")


def test_canonical_observation_identity_ignores_temp_and_duration_volatility() -> None:
    first = synthetic_observation(temp_token="one", duration="0.29s", process_duration=70.1)
    second = synthetic_observation(temp_token="two", duration="1.93s", process_duration=2.2)
    assert first["cwd"] != second["cwd"]
    assert first["duration_seconds"] != second["duration_seconds"]
    assert first["stdout_sha256"] != second["stdout_sha256"]
    assert first["canonical_identity"] == second["canonical_identity"]
    assert first["canonical_identity_sha256"] == second["canonical_identity_sha256"]


def test_generated_output_cleanup_is_scoped_and_symlink_safe(tmp_path: Path) -> None:
    out = tmp_path / "out"
    partitions = out / "partitions"
    partitions.mkdir(parents=True)
    (out / "raw_private_evidence.jsonl").write_text("stale")
    (out / "raw_private_candidate.jsonl").write_text("stale")
    external = tmp_path / "external"
    external.write_text("keep")
    (partitions / "test_setup.patch").symlink_to(external)
    (partitions / "production_repair.patch").write_text("stale")
    (out / "summary.json").write_text("keep")

    mod.clear_generated_outputs(out)

    assert external.read_text() == "keep"
    assert (out / "summary.json").read_text() == "keep"
    assert not (out / "raw_private_evidence.jsonl").exists()
    assert not (out / "raw_private_candidate.jsonl").exists()
    assert not partitions.exists()


def test_reject_clears_stale_and_partial_generated_outputs(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "out"
    summary = tmp_path / "summary.json"
    (out / "partitions").mkdir(parents=True)
    (out / "raw_private_evidence.jsonl").write_text("stale")
    (out / "raw_private_candidate.jsonl").write_text("stale")

    def rejected_replay(path: Path):
        (path / "partitions" / "test_setup.patch").write_text("partial")
        (path / "partitions" / "production_repair.patch").write_text("partial")
        raise mod.GateError("synthetic_reject")

    monkeypatch.setattr(mod, "replay", rejected_replay)
    result = mod.execute(out, summary)

    assert result["status"] == "REJECTED"
    assert result["training_allowed"] is False
    assert not (out / "raw_private_evidence.jsonl").exists()
    assert not (out / "raw_private_candidate.jsonl").exists()
    assert not (out / "partitions").exists()


def test_verifier_identity_is_ai_cpu_only_and_test_bound(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    for path, digest in mod.SELECTED_TEST_SHA256.items():
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(bytes.fromhex(digest))
    with pytest.raises(mod.GateError, match="selected_test_hash_mismatch"):
        mod.verifier_identity(repo, tmp_path / "target")

    for path in mod.TEST_PATHS:
        blob = mod.git_bytes(mod.SOURCE_REPO, "show", f"{mod.AFTER}:{path}")
        (repo / path).write_bytes(blob)
    identity = mod.verifier_identity(repo, tmp_path / "target")["normalized"]
    assert identity["logical_command"] == "cargo test -p biome_migrate"
    assert identity["conda_environment"] == "ai"
    assert identity["cpu_only"] is True
    assert identity["environment"]["CUDA_VISIBLE_DEVICES"] == ""
    assert identity["environment"]["CARGO_NET_OFFLINE"] == "true"
    assert identity["selected_test_content_sha256"] == mod.SELECTED_TEST_SHA256


def test_forbidden_training_shapes_are_rejected_recursively() -> None:
    for key in mod.FORBIDDEN_OUTPUT_KEYS:
        with pytest.raises(mod.GateError, match="forbidden_output_key"):
            mod.assert_no_forbidden_keys({"nested": [{key: []}]})


def test_materialized_artifacts_are_raw_private_and_zero_admission() -> None:
    evidence = read_single_jsonl(ARTIFACTS / "raw_private_evidence.jsonl")
    candidate = read_single_jsonl(ARTIFACTS / "raw_private_candidate.jsonl")
    assert candidate["candidate_identity_sha256"] == mod.stable_hash(
        {key: value for key, value in candidate.items() if key != "candidate_identity_sha256"}
    )
    summary = json.loads((ARTIFACTS / "summary.json").read_text(encoding="utf-8"))
    external_summary = json.loads(
        (ROOT / "runs/summaries/stage12584_biome_causal_replay.json").read_text(encoding="utf-8")
    )

    assert summary == external_summary
    assert summary["status"] == "RAW_PRIVATE_REPLAY_MATERIALIZED"
    for record in (evidence, candidate, summary):
        assert record["training_allowed"] is False
        assert record["strict_eval"] is False
        assert record["source_heldout"] is False
        assert not mod.FORBIDDEN_OUTPUT_KEYS.intersection(all_keys(record))
    assert summary["admitted_files"] == []
    assert summary["counters"] == mod.ADMISSION_COUNTERS
    assert all(value == 0 for value in summary["counters"].values())
    assert candidate["admitted_files"] == []
    assert candidate["admission_counters"] == mod.ADMISSION_COUNTERS


def test_materialized_evidence_binds_replay_and_final_state() -> None:
    evidence = read_single_jsonl(ARTIFACTS / "raw_private_evidence.jsonl")
    before = evidence["observations"]["before"]
    after = evidence["observations"]["after"]
    assert before["return_code"] == 101
    assert after["return_code"] == 0
    assert before["expected_suite_tuple"] == [32, 1]
    assert after["expected_suite_tuple"] == [33, 0]
    assert before["expected_suite_match_count"] == after["expected_suite_match_count"] == 1
    for phase, expected_status in ((before, "failed"), (after, "ok")):
        binding = phase["intended_suite_binding"]
        assert binding["package"] == "biome_migrate"
        assert binding["test_binary_source_path"] == mod.EXPECTED_TEST_BINARY
        assert binding["named_test"]["name"] == mod.EXPECTED_TEST_NAME
        assert binding["named_test"]["status"] == expected_status
        assert phase["canonical_identity_sha256"] == mod.stable_hash(
            phase["canonical_identity"]
        )
        assert "duration_seconds" not in phase["canonical_identity"]
        assert phase["duration_seconds"] >= 0
    assert all("result_line_sha256" in row for row in before["suite_results"])
    assert all("result_line_sha256" in row for row in after["suite_results"])
    assert any((row["passed"], row["failed"]) == (0, 0) for row in after["suite_results"])
    assert before["suite_results_sha256"] == mod.stable_hash(before["suite_results"])
    assert after["suite_results_sha256"] == mod.stable_hash(after["suite_results"])
    assert before["verifier_identity_sha256"] == after["verifier_identity_sha256"]
    assert evidence["verifier"]["identical_before_after"] is True
    assert evidence["patch_split"]["diff_hashes"]["selected_diff_sha256"] == mod.SELECTED_DIFF_SHA256
    assert evidence["selected_test_content_sha256"] == mod.SELECTED_TEST_SHA256
    assert evidence["evidence_sha256"] == mod.stable_hash(evidence["canonical_identity"])
    assert evidence["canonical_identity"] == mod.canonical_evidence_identity(evidence)
    assert evidence["source"]["before_commit"] == mod.BEFORE
    assert evidence["source"]["after_commit"] == mod.AFTER
    assert evidence["source"]["source_unchanged"] is True
    audit = evidence["mutation_audit"]
    assert all(value is True for key, value in audit.items() if key.endswith("unchanged") or key.endswith("exact"))
    assert audit["final_changed_paths"] == sorted((*mod.PRODUCTION_PATHS, *mod.TEST_PATHS))
    assert audit["final_diff_sha256"] == mod.SELECTED_DIFF_SHA256
    assert audit["pinned_diff_check"] == {
        "return_code": 2,
        "output_sha256": mod.SELECTED_DIFF_CHECK_SHA256,
        "expected_snapshot_whitespace_diagnostics": True,
    }


def test_no_admitted_or_model_input_artifacts_exist() -> None:
    relative_files = {
        str(path.relative_to(ARTIFACTS)) for path in ARTIFACTS.rglob("*") if path.is_file()
    }
    assert relative_files == {
        "partitions/test_setup.patch",
        "partitions/production_repair.patch",
        "raw_private_evidence.jsonl",
        "raw_private_candidate.jsonl",
        "replay_diagnostics.json",
        "summary.json",
    }
    lowered = " ".join(relative_files).lower()
    assert "admitted" not in lowered
    assert "model_input" not in lowered

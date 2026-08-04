import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts/build_stage12597_manual_executor_source_preflight.py"
RUNNER = ROOT / "scripts/run_stage12597_manual_trusted_replay_executor.py"
SPEC = importlib.util.spec_from_file_location("stage12597_builder", BUILDER)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)
RUNNER_SPEC = importlib.util.spec_from_file_location("stage12597_runner", RUNNER)
assert RUNNER_SPEC and RUNNER_SPEC.loader
runner = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(runner)


def read_json(path: Path):
    return json.loads(path.read_text())


def copy_tree(src: Path, dst: Path):
    for path in src.rglob("*"):
        if path.is_file():
            target = dst / path.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())


def copy_stage12596(tmp_path: Path):
    dst = tmp_path / "stage12596"
    copy_tree(stage.S12596, dst)
    return dst


def assert_false_boundaries(record):
    for field in (
        "authorizes_execution", "execution_allowed", "execution_performed", "replay_trustworthy",
        "level_3_materialized", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted",
        "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "training_allowed",
        "ranking_allowed", "positive_stop",
    ):
        assert record[field] is False


def assert_public_sanitized(record):
    encoded = json.dumps(record, sort_keys=True)
    for forbidden in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
        assert forbidden not in encoded


def test_stage12597_preflight_validates_stage12594_12596_pin_chain():
    packet, report = stage.validate_runner_source()
    assert report["stage12594_publication_generation_id"] == runner.EXPECTED_STAGE12594_GENERATION
    assert report["stage12594_publication_manifest_sha256"] == runner.EXPECTED_STAGE12594_MANIFEST
    assert report["stage12595_slots_sha256"] == runner.EXPECTED_STAGE12595_SLOTS
    assert report["stage12596_private_executor_contract_sha256"] == runner.EXPECTED_STAGE12596_PRIVATE_CONTRACT
    assert report["stage12596_private_review_intake_sha256"] == runner.EXPECTED_STAGE12596_REVIEW_INTAKE
    assert report["manual_executor_preflight_source_present"] is True
    assert "manual_executor_source_present" not in report
    assert report["slot_count"] == 2
    assert report["this_stage_runs_replay"] is False
    assert report["executor_command_manifest_present"] is False
    assert report["raw_replay_evidence_present"] is False
    assert packet["private_contract"]["executor_command_manifest_present"] is False
    assert [row["required_phase_sequence"] for row in packet["slots"]] == [["initial", "patched", "final"], ["initial", "patched", "final"]]
    assert [row["binding_payload_sha256"] for row in packet["slots"]] == list(runner.EXPECTED_BINDINGS)
    assert_false_boundaries(report)


def test_stage12597_rejects_execute_and_run_cli_without_artifacts(tmp_path):
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    for flag in ("--execute", "--run"):
        result = subprocess.run(
            [sys.executable, str(RUNNER), "--stage12596-root", str(runner.S12596), flag],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
        )
        assert result.returncode != 0
        assert "manual_replay_execution_disabled_pending_independent_source_review" in result.stderr
    default = subprocess.run(
        [sys.executable, str(RUNNER), "--stage12596-root", str(runner.S12596)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    assert default.returncode != 0
    assert "preflight_only_flag_required" in default.stderr
    after = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    assert after == before


def test_stage12597_preflight_only_emits_false_gated_static_packet(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/executor_source_review_intake.json",
        "summary.json",
    ]
    assert not any("stdout.raw" in name or "stderr.raw" in name or "pytest" in name for name in emitted)
    assert not any("clone" in name or "repo" in name or "command_manifest" in name for name in emitted)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    intake = read_json(out / "private/executor_source_review_intake.json")
    assert summary["decision"] == "BLOCKED_EXECUTOR_SOURCE_REVIEW_REQUIRED"
    assert summary["manual_executor_preflight_source_present"] is True
    assert summary["execute_path_enabled"] is False
    assert summary["this_stage_runs_replay"] is False
    assert summary["executor_command_manifest_present"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert summary["independent_executor_source_review_present"] is False
    assert summary["execution_request_ready_count"] == 0
    assert summary["stage12598_allowed"] is False
    assert contract["this_stage_runs_replay"] is False
    assert contract["execute_path_enabled"] is False
    assert contract["executor_command_manifest_present"] is False
    assert contract["raw_replay_evidence_present"] is False
    assert pointer["manual_executor_preflight_source_sha256"] == stage.sha256_file(RUNNER)
    assert pointer["private_source_review_intake_sha256"] == stage.stable_hash(intake)
    assert intake["this_stage_runs_replay"] is False
    assert intake["executor_command_manifest_present"] is False
    assert intake["raw_replay_evidence_present"] is False
    assert "independent_executor_source_review_absent" in intake["review_limits"]
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, intake):
        assert_false_boundaries(record)


def test_stage12597_rejects_pin_drift_before_preflight_report(tmp_path):
    root = copy_stage12596(tmp_path)
    pointer = read_json(root / "digest_pointer.json")
    pointer["private_executor_contract_sha256"] = "0" * 64
    (root / "digest_pointer.json").write_text(json.dumps(pointer), encoding="utf-8")
    with pytest.raises(runner.GateError, match="stage12596_private_contract_pin_drift"):
        runner.load_stage12596_packet(root)


def test_stage12597_rejects_stage12594_manifest_drift(tmp_path):
    root = copy_stage12596(tmp_path)
    summary = read_json(root / "summary.json")
    summary["stage12594_publication_manifest_sha256"] = "0" * 64
    (root / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(runner.GateError, match="stage12596_stage12594_manifest_drift"):
        runner.load_stage12596_packet(root)



def test_stage12597_generated_artifacts_match_current_source_and_private_digests():
    out = stage.OUT
    summary_path = stage.SUMMARY
    summary = read_json(out / "summary.json")
    external = read_json(summary_path)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    intake = read_json(out / "private/executor_source_review_intake.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/executor_source_review_intake.json",
        "summary.json",
    ]
    source_sha256 = stage.sha256_file(RUNNER)
    assert summary == external
    assert summary["manual_executor_preflight_source_sha256"] == source_sha256
    assert contract["manual_executor_preflight_source_sha256"] == source_sha256
    assert pointer["manual_executor_preflight_source_sha256"] == source_sha256
    assert intake["manual_executor_preflight_source_sha256"] == source_sha256
    assert pointer["private_source_review_intake_sha256"] == stage.stable_hash(intake)
    assert pointer["stage12596_private_executor_contract_sha256"] == summary["stage12596_private_executor_contract_sha256"]
    assert summary["decision"] == "BLOCKED_EXECUTOR_SOURCE_REVIEW_REQUIRED"
    assert summary["manual_executor_preflight_source_present"] is True
    assert "manual_executor_source_present" not in summary
    assert summary["execute_path_enabled"] is False
    assert summary["this_stage_runs_replay"] is False
    assert summary["executor_command_manifest_present"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert summary["independent_executor_source_review_present"] is False
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, intake):
        assert_false_boundaries(record)

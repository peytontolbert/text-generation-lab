import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12612_trusted_replay_resumption_gate_blocker.py"
SPEC = importlib.util.spec_from_file_location("stage12612", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def assert_false_boundaries(record):
    for field in (
        "implementation_ready", "stage12595_allowed", "execution_performed", "replay_trustworthy",
        "raw_replay_evidence_present", "trusted_replay_raw_evidence_present", "causal_transition_atoms_present",
        "causal_transition_atoms_materialized", "causal_transition_atoms_allowed",
        "causally_committed_pre_outcome_candidate_set_present", "observed_stop_continue_decision_provenance_present",
        "level3_preflight_allowed", "level_3_materialized", "level_3_materialization_allowed",
        "training_admission_preflight_allowed", "training_admission_allowed", "training_admitted",
        "training_allowed", "training_run_allowed", "gpu_allocation_requested", "cuda2_training_allowed",
        "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
        "admission_allowed", "ranking_allowed", "positive_stop", "stage12613_allowed",
    ):
        if field in record:
            assert record[field] is False


def assert_public_sanitized(record):
    encoded = json.dumps(record, sort_keys=True)
    for forbidden in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
        assert forbidden not in encoded


def test_load_stage12611_requires_training_blocker():
    loaded = stage.load_stage12611()
    summary = loaded["summary"]
    assert summary["decision"] == "BLOCKED_SEPARATE_TRAINING_ADMISSION_REQUIREMENTS_UNMET"
    assert summary["separate_training_admission_required"] is True
    assert summary["training_admission_allowed"] is False
    assert summary["stage12612_allowed"] is False
    for record in loaded.values():
        assert_false_boundaries(record)


def test_resumption_requirements_define_exact_evidence_and_followup_order():
    requirements = stage.resumption_requirements()
    assert requirements["required_external_evidence_file_count"] == 14
    assert "slot_1/reviewed_slot_execution_result.json" in requirements["required_external_evidence_relative_files"]
    assert "slot_2/final.stderr.raw" in requirements["required_external_evidence_relative_files"]
    followups = requirements["required_after_evidence_arrives"]
    assert followups[0] == "verify_stage12607_private_handoff_pin"
    assert "independent_execution_artifact_review" in followups
    assert "run_separate_training_admission_gate" in followups
    assert "gpu_allocation" in requirements["still_forbidden_at_resumption_gate"]


def test_inspect_external_evidence_root_reports_missing_current_root():
    evidence = stage.inspect_external_evidence_root()
    assert evidence["future_private_evidence_root_exists"] is False
    assert evidence["required_external_evidence_file_count"] == 14
    assert evidence["present_external_evidence_file_count"] == 0
    assert evidence["missing_external_evidence_file_count"] == 14
    assert evidence["external_evidence_complete"] is False
    assert "slot_1/initial.stdout.raw" in evidence["missing_relative_files"]


def test_build_resumption_gate_packet_blocks_all_downstream_claims():
    loaded = stage.load_stage12611()
    evidence = stage.inspect_external_evidence_root()
    summary, contract, private = stage.build_resumption_gate_packet(loaded, evidence)
    assert summary["decision"] == "BLOCKED_TRUSTED_REPLAY_RESUMPTION_REQUIRES_EXTERNAL_BWRAP_EVIDENCE"
    assert summary["trusted_replay_resumption_gate_recorded"] is True
    assert summary["external_bwrap_execution_required"] is True
    assert summary["external_bwrap_execution_evidence_present"] is False
    assert summary["required_external_evidence_file_count"] == 14
    assert summary["present_external_evidence_file_count"] == 0
    assert summary["missing_external_evidence_file_count"] == 14
    assert summary["training_admitted"] is False
    assert summary["level_3_materialized"] is False
    assert summary["causal_transition_atoms_materialized"] is False
    assert contract["private_resumption_gate_blocker_sha256"] == stage.stable_hash(private)
    assert summary["resumption_requirement_manifest_sha256"] == stage.stable_hash(private["resumption_requirement_manifest"])
    for public_record in (summary, contract):
        assert_public_sanitized(public_record)
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_resumption_gate_blocker_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/trusted_replay_resumption_gate_blocker.json",
        "summary.json",
    ]
    assert not any("stdout.raw" in name or "stderr.raw" in name or "pytest" in name for name in emitted)
    assert not any("patches" in name or "future_evidence" in name or "snapshot" in name for name in emitted)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/trusted_replay_resumption_gate_blocker.json")
    assert pointer["private_resumption_gate_blocker_sha256"] == stage.stable_hash(private)
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_generated_artifacts_match_current_resumption_gate_blocker():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/trusted_replay_resumption_gate_blocker.json",
        "summary.json",
    ]
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/trusted_replay_resumption_gate_blocker.json")
    assert summary == external
    assert summary["external_bwrap_execution_evidence_present"] is False
    assert summary["execution_performed"] is False
    assert summary["replay_trustworthy"] is False
    assert summary["training_admitted"] is False
    assert pointer["private_resumption_gate_blocker_sha256"] == stage.stable_hash(private)
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_build_resumption_gate_rejects_complete_external_evidence():
    loaded = stage.load_stage12611()
    evidence = stage.inspect_external_evidence_root()
    complete = dict(evidence, external_evidence_complete=True, missing_external_evidence_file_count=0)
    with pytest.raises(stage.ResumptionGateError, match="unexpected_complete_external_replay_evidence_present"):
        stage.build_resumption_gate_packet(loaded, complete)

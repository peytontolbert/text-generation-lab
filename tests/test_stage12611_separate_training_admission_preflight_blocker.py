import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12611_separate_training_admission_preflight_blocker.py"
SPEC = importlib.util.spec_from_file_location("stage12611", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def assert_false_boundaries(record):
    for field in (
        "implementation_ready", "stage12595_allowed", "execution_performed", "replay_trustworthy",
        "raw_replay_evidence_present", "causal_transition_atoms_present", "causal_transition_atoms_materialized",
        "causal_transition_atoms_allowed", "causally_committed_pre_outcome_candidate_set_present",
        "observed_stop_continue_decision_provenance_present", "level3_preflight_allowed",
        "level_3_materialized", "level_3_materialization_allowed",
        "training_admission_preflight_allowed", "training_admission_allowed", "training_admitted",
        "training_allowed", "training_run_allowed", "gpu_allocation_requested", "cuda2_training_allowed",
        "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
        "admission_allowed", "ranking_allowed", "positive_stop",
    ):
        if field in record:
            assert record[field] is False


def assert_public_sanitized(record):
    encoded = json.dumps(record, sort_keys=True)
    for forbidden in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
        assert forbidden not in encoded


def test_load_stage12610_requires_level3_blocker_and_training_separation():
    loaded = stage.load_stage12610()
    summary = loaded["summary"]
    private = loaded["private"]
    assert summary["decision"] == "BLOCKED_CAUSAL_TRANSITION_ATOMS_AND_PROVENANCE_REQUIRED_FOR_LEVEL3"
    assert summary["level_3_materialized"] is False
    assert summary["stage12611_allowed"] is False
    assert summary["training_admission_preflight_allowed"] is False
    assert "level3_materialization_alone" in private["level3_requirement_manifest"]["not_sufficient_for_training"]
    for record in loaded.values():
        assert_false_boundaries(record)


def test_training_admission_requirements_keep_gpu_and_eval_separate():
    requirements = stage.training_admission_requirements()
    required = requirements["required_before_training_admission"]
    assert "level_3_materialized" in required
    assert "separate_training_data_admission_review_passed" in required
    assert "train_eval_contamination_guard_passed" in required
    assert "gpu_allocation_explicitly_authorized_for_cuda2_only_if_training_runs" in required
    assert "level3_materialization_alone" in requirements["not_sufficient_for_training"]
    assert "training_run_allowed" in requirements["forbidden_until_requirements_met"]
    assert "strict_eval_admitted" in requirements["forbidden_until_requirements_met"]
    assert "sealed_eval_admitted" in requirements["forbidden_until_requirements_met"]


def test_build_training_preflight_packet_blocks_training_eval_and_gpu():
    loaded = stage.load_stage12610()
    summary, contract, private = stage.build_training_preflight_packet(loaded)
    assert summary["decision"] == "BLOCKED_SEPARATE_TRAINING_ADMISSION_REQUIREMENTS_UNMET"
    assert summary["level_3_materialized"] is False
    assert summary["trusted_replay_raw_evidence_present"] is False
    assert summary["separate_training_data_admission_review_present"] is False
    assert summary["separate_training_admission_required"] is True
    assert summary["level3_not_sufficient_for_training"] is True
    assert summary["training_admission_blocker_recorded"] is True
    assert summary["causal_transition_atoms_present"] is False
    assert summary["causally_committed_pre_outcome_candidate_set_present"] is False
    assert summary["observed_stop_continue_decision_provenance_present"] is False
    assert summary["stage12612_allowed"] is False
    assert summary["future_training_candidate_intake_allowed"] is False
    assert summary["separate_training_admission_required"] is True
    assert summary["level3_not_sufficient_for_training"] is True
    assert summary["training_admission_blocker_recorded"] is True
    assert summary["training_admitted"] is False
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert summary["gpu_allocation_requested"] is False
    assert summary["cuda2_training_allowed"] is False
    assert contract["private_training_preflight_blocker_sha256"] == stage.stable_hash(private)
    assert summary["training_admission_requirement_manifest_sha256"] == stage.stable_hash(private["training_admission_requirement_manifest"])
    for public_record in (summary, contract):
        assert_public_sanitized(public_record)
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_training_preflight_blocker_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/separate_training_admission_preflight_blocker.json",
        "summary.json",
    ]
    assert not any("stdout.raw" in name or "stderr.raw" in name or "pytest" in name for name in emitted)
    assert not any("patches" in name or "future_evidence" in name or "snapshot" in name for name in emitted)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/separate_training_admission_preflight_blocker.json")
    assert pointer["private_training_preflight_blocker_sha256"] == stage.stable_hash(private)
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    assert pointer["separate_training_admission_required"] is True
    assert pointer["level3_not_sufficient_for_training"] is True
    assert pointer["training_admission_blocker_recorded"] is True
    assert pointer["training_admitted"] is False
    assert pointer["gpu_allocation_requested"] is False
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_generated_artifacts_match_current_training_preflight_blocker():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/separate_training_admission_preflight_blocker.json",
        "summary.json",
    ]
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/separate_training_admission_preflight_blocker.json")
    assert summary == external
    assert summary["separate_training_admission_required"] is True
    assert summary["level3_not_sufficient_for_training"] is True
    assert summary["training_admission_blocker_recorded"] is True
    assert summary["training_admitted"] is False
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert summary["gpu_allocation_requested"] is False
    assert summary["strict_eval_admitted"] is False
    assert summary["sealed_eval_admitted"] is False
    assert pointer["private_training_preflight_blocker_sha256"] == stage.stable_hash(private)
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)

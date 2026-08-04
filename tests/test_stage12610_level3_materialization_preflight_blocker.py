import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12610_level3_materialization_preflight_blocker.py"
SPEC = importlib.util.spec_from_file_location("stage12610", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def assert_false_boundaries(record):
    for field in (
        "implementation_ready", "stage12595_allowed", "execution_performed", "replay_trustworthy",
        "raw_replay_evidence_present", "causal_transition_atoms_materialized", "causal_transition_atoms_allowed",
        "level3_preflight_allowed", "level_3_materialized", "level_3_materialization_allowed",
        "training_admitted", "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible",
        "sealed_eval_eligible", "admission_allowed", "training_allowed", "ranking_allowed", "positive_stop",
    ):
        if field in record:
            assert record[field] is False


def assert_public_sanitized(record):
    encoded = json.dumps(record, sort_keys=True)
    for forbidden in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
        assert forbidden not in encoded


def test_load_stage12609_requires_atom_blocker():
    loaded = stage.load_stage12609()
    summary = loaded["summary"]
    assert summary["decision"] == "BLOCKED_TRUSTED_REPLAY_EXECUTION_EVIDENCE_REQUIRED_FOR_CAUSAL_ATOMS"
    assert summary["causal_transition_atom_count"] == 0
    assert summary["stage12610_allowed"] is False
    assert summary["level3_preflight_allowed"] is False
    for record in loaded.values():
        assert_false_boundaries(record)


def test_level3_requirements_keep_training_separate():
    requirements = stage.level3_requirements()
    required = requirements["required_before_level3"]
    assert "causal_transition_atom_count_positive" in required
    assert "causally_committed_pre_outcome_candidate_set_present" in required
    assert "observed_stop_continue_decision_provenance_present" in required
    assert "level3_materialization_alone" in requirements["not_sufficient_for_training"]
    assert "training_admitted" in requirements["forbidden_until_requirements_met"]


def test_build_level3_preflight_packet_blocks_materialization_and_training():
    loaded = stage.load_stage12609()
    summary, contract, private = stage.build_level3_preflight_packet(loaded)
    assert summary["decision"] == "BLOCKED_CAUSAL_TRANSITION_ATOMS_AND_PROVENANCE_REQUIRED_FOR_LEVEL3"
    assert summary["causal_transition_atom_count"] == 0
    assert summary["causal_transition_atoms_present"] is False
    assert summary["causally_committed_pre_outcome_candidate_set_present"] is False
    assert summary["observed_stop_continue_decision_provenance_present"] is False
    assert summary["level_3_materialized"] is False
    assert summary["level_3_materialization_allowed"] is False
    assert summary["stage12611_allowed"] is False
    assert summary["training_admission_preflight_allowed"] is False
    assert contract["private_level3_preflight_blocker_sha256"] == stage.stable_hash(private)
    assert summary["level3_requirement_manifest_sha256"] == stage.stable_hash(private["level3_requirement_manifest"])
    for public_record in (summary, contract):
        assert_public_sanitized(public_record)
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_level3_preflight_blocker_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/level3_materialization_preflight_blocker.json",
        "summary.json",
    ]
    assert not any("stdout.raw" in name or "stderr.raw" in name or "pytest" in name for name in emitted)
    assert not any("patches" in name or "future_evidence" in name or "snapshot" in name for name in emitted)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/level3_materialization_preflight_blocker.json")
    assert pointer["private_level3_preflight_blocker_sha256"] == stage.stable_hash(private)
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    assert pointer["level_3_materialized"] is False
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_generated_artifacts_match_current_level3_preflight_blocker():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/level3_materialization_preflight_blocker.json",
        "summary.json",
    ]
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/level3_materialization_preflight_blocker.json")
    assert summary == external
    assert summary["level_3_materialized"] is False
    assert summary["level_3_materialization_allowed"] is False
    assert summary["training_admitted"] is False
    assert summary["training_admission_preflight_allowed"] is False
    assert pointer["private_level3_preflight_blocker_sha256"] == stage.stable_hash(private)
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)

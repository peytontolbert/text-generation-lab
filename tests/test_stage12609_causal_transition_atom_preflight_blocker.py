import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12609_causal_transition_atom_preflight_blocker.py"
SPEC = importlib.util.spec_from_file_location("stage12609", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def assert_false_boundaries(record):
    for field in (
        "implementation_ready", "stage12595_allowed", "execution_performed", "replay_trustworthy",
        "raw_replay_evidence_present", "causal_transition_atoms_materialized", "causal_transition_atoms_allowed",
        "level_3_materialized", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted",
        "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "training_allowed",
        "ranking_allowed", "positive_stop",
    ):
        if field in record:
            assert record[field] is False


def assert_public_sanitized(record):
    encoded = json.dumps(record, sort_keys=True)
    for forbidden in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
        assert forbidden not in encoded


def test_load_stage12608_requires_missing_execution_evidence_and_no_atoms():
    loaded = stage.load_stage12608()
    summary = loaded["summary"]
    private = loaded["private"]
    assert summary["decision"] == "BLOCKED_EXTERNAL_BWRAP_CAPABLE_EXECUTION_ARTIFACTS_MISSING"
    assert summary["external_bwrap_capable_execution_artifacts_present"] is False
    assert summary["stage12609_allowed"] is False
    assert summary["causal_transition_atoms_allowed"] is False
    assert private["future_evidence_inspection"]["all_required_evidence_present"] is False
    for record in loaded.values():
        assert_false_boundaries(record)


def test_atom_requirements_include_level3_provenance_prerequisites():
    requirements = stage.atom_requirements()
    required = requirements["required_before_any_atom"]
    assert "all_stage12608_required_external_execution_artifacts_present" in required
    assert "independent_execution_artifact_review_passed" in required
    assert "causally_committed_pre_outcome_candidate_set_present" in required
    assert "observed_stop_continue_decision_provenance_present" in required
    assert "level_3_materialized" in requirements["forbidden_until_requirements_met"]
    assert "training_admitted" in requirements["forbidden_until_requirements_met"]


def test_build_atom_preflight_packet_blocks_atoms_level3_and_training():
    loaded = stage.load_stage12608()
    summary, contract, private = stage.build_atom_preflight_packet(loaded)
    assert summary["decision"] == "BLOCKED_TRUSTED_REPLAY_EXECUTION_EVIDENCE_REQUIRED_FOR_CAUSAL_ATOMS"
    assert summary["source_external_execution_artifacts_present"] is False
    assert summary["source_present_evidence_file_count"] == 0
    assert summary["source_missing_evidence_file_count"] == 14
    assert summary["causal_transition_atom_count"] == 0
    assert summary["stage12610_allowed"] is False
    assert summary["level3_preflight_allowed"] is False
    assert contract["private_atom_preflight_blocker_sha256"] == stage.stable_hash(private)
    assert summary["causal_atom_requirement_manifest_sha256"] == stage.stable_hash(private["causal_atom_requirement_manifest"])
    for public_record in (summary, contract):
        assert_public_sanitized(public_record)
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_atom_preflight_blocker_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/causal_transition_atom_preflight_blocker.json",
        "summary.json",
    ]
    assert not any("stdout.raw" in name or "stderr.raw" in name or "pytest" in name for name in emitted)
    assert not any("patches" in name or "future_evidence" in name or "snapshot" in name for name in emitted)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/causal_transition_atom_preflight_blocker.json")
    assert pointer["private_atom_preflight_blocker_sha256"] == stage.stable_hash(private)
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    assert pointer["causal_transition_atom_count"] == 0
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_generated_artifacts_match_current_atom_preflight_blocker():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/causal_transition_atom_preflight_blocker.json",
        "summary.json",
    ]
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/causal_transition_atom_preflight_blocker.json")
    assert summary == external
    assert summary["causal_transition_atom_count"] == 0
    assert summary["causal_transition_atoms_materialized"] is False
    assert summary["level_3_materialized"] is False
    assert summary["training_admitted"] is False
    assert pointer["private_atom_preflight_blocker_sha256"] == stage.stable_hash(private)
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12613_stronger_isolation_remediation_preflight.py"
SPEC = importlib.util.spec_from_file_location("stage12613", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def assert_false_boundaries(record):
    for field in (
        "implementation_ready", "stage12595_allowed", "stage12613_allowed", "stage12614_allowed",
        "execution_performed", "replay_trustworthy", "raw_replay_evidence_present",
        "trusted_replay_raw_evidence_present", "external_bwrap_execution_evidence_present",
        "alternate_replay_evidence_present", "alternate_replay_trustworthy",
        "causal_transition_atoms_present", "causal_transition_atoms_materialized",
        "causal_transition_atoms_allowed", "causally_committed_pre_outcome_candidate_set_present",
        "observed_stop_continue_decision_provenance_present", "level3_preflight_allowed",
        "level_3_materialized", "level_3_materialization_allowed",
        "training_admission_preflight_allowed", "training_admission_allowed", "training_admitted",
        "training_allowed", "training_run_allowed", "gpu_allocation_requested", "cuda2_training_allowed",
        "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
        "admission_allowed", "ranking_allowed", "positive_stop",
    ):
        assert field in record
        assert record[field] is False


def assert_optional_false_boundaries(record):
    for field in (
        "implementation_ready", "stage12595_allowed", "stage12613_allowed", "stage12614_allowed",
        "execution_performed", "replay_trustworthy", "raw_replay_evidence_present",
        "trusted_replay_raw_evidence_present", "external_bwrap_execution_evidence_present",
        "alternate_replay_evidence_present", "alternate_replay_trustworthy",
        "causal_transition_atoms_present", "causal_transition_atoms_materialized",
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


def test_load_stage12612_preserves_existing_blocker():
    loaded = stage.load_stage12612()
    summary = loaded["summary"]
    assert summary["decision"] == "BLOCKED_TRUSTED_REPLAY_RESUMPTION_REQUIRES_EXTERNAL_BWRAP_EVIDENCE"
    assert summary["stage12613_allowed"] is False
    assert summary["required_external_evidence_file_count"] == 14
    assert summary["present_external_evidence_file_count"] == 0
    assert summary["training_allowed"] is False
    for record in loaded.values():
        assert_optional_false_boundaries(record)


def test_isolation_contract_recommends_vm_or_microvm_not_plain_process():
    contract = stage.isolation_remediation_contract()
    assert contract["trust_objective"] == "independently_auditable_replay_evidence_not_a_specific_sandbox_brand"
    assert contract["preferred_runner_tier"] == "disposable_vm_or_microvm"
    assert "firecracker_microvm_when_available" in contract["preferred_runner_examples"]
    assert "separate_guest_kernel_boundary_or_vm_backed_isolation" in contract["why_stronger_than_bwrap"]
    plain = [item for item in contract["acceptable_fallback_tiers"] if item["tier"] == "plain_local_process"]
    assert plain and plain[0]["status"] == "not_acceptable_for_trusted_replay_claims"
    assert "admitting_training" in contract["still_forbidden"]


def test_build_remediation_packet_does_not_resume_replay_or_training():
    loaded = stage.load_stage12612()
    summary, contract, private = stage.build_remediation_packet(loaded)
    assert summary["decision"] == "BLOCKED_REPLAY_REMEDIATION_CONTRACT_REVIEW_REQUIRED"
    assert summary["remediation_preflight_only"] is True
    assert summary["stage12612_blocker_preserved"] is True
    assert summary["recommended_stronger_runner"] == "disposable_vm_or_microvm"
    assert summary["alternate_contract_is_draft"] is True
    assert summary["alternate_contract_requires_future_independent_review"] is True
    assert summary["execution_performed"] is False
    assert summary["replay_trustworthy"] is False
    assert summary["level_3_materialized"] is False
    assert summary["training_admitted"] is False
    assert contract["private_remediation_preflight_sha256"] == stage.stable_hash(private)
    assert summary["isolation_remediation_contract_sha256"] == stage.stable_hash(
        private["isolation_remediation_contract"]
    )
    for public_record in (summary, contract):
        assert_public_sanitized(public_record)
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_remediation_preflight_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/stronger_isolation_remediation_preflight.json",
        "summary.json",
    ]
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/stronger_isolation_remediation_preflight.json")
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    assert pointer["private_remediation_preflight_sha256"] == stage.stable_hash(private)
    assert summary["private_remediation_preflight_sha256"] == stage.stable_hash(private)
    assert summary["isolation_remediation_contract_sha256"] == stage.stable_hash(
        private["isolation_remediation_contract"]
    )
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_generated_artifacts_match_current_remediation_preflight():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/stronger_isolation_remediation_preflight.json",
        "summary.json",
    ]
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/stronger_isolation_remediation_preflight.json")
    assert summary == external
    assert summary["stage12612_blocker_preserved"] is True
    assert summary["recommended_stronger_runner"] == "disposable_vm_or_microvm"
    assert summary["training_allowed"] is False
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    assert pointer["private_remediation_preflight_sha256"] == stage.stable_hash(private)
    assert summary["private_remediation_preflight_sha256"] == stage.stable_hash(private)
    assert summary["isolation_remediation_contract_sha256"] == stage.stable_hash(
        private["isolation_remediation_contract"]
    )
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12614_disposable_vm_runner_contract_preflight.py"
SPEC = importlib.util.spec_from_file_location("stage12614", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def assert_false_boundaries(record):
    for field in (
        "implementation_ready", "stage12595_allowed", "stage12613_allowed", "stage12614_allowed",
        "stage12615_allowed", "execution_performed", "replay_trustworthy", "raw_replay_evidence_present",
        "trusted_replay_raw_evidence_present", "external_bwrap_execution_evidence_present",
        "alternate_replay_evidence_present", "alternate_replay_trustworthy",
        "vm_runner_contract_review_passed", "vm_runner_implementation_ready",
        "vm_runner_execution_allowed", "vm_runner_evidence_present", "vm_runner_trustworthy",
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


def assert_public_sanitized(record):
    encoded = json.dumps(record, sort_keys=True)
    for forbidden in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
        assert forbidden not in encoded


def test_load_stage12613_preserves_remediation_blocker():
    loaded = stage.load_stage12613()
    summary = loaded["summary"]
    assert summary["decision"] == "BLOCKED_REPLAY_REMEDIATION_CONTRACT_REVIEW_REQUIRED"
    assert summary["recommended_stronger_runner"] == "disposable_vm_or_microvm"
    assert summary["stage12614_allowed"] is False
    assert summary["training_allowed"] is False
    for record in loaded.values():
        for field in stage.FALSE_FIELDS:
            if field in record:
                assert record[field] is False


def test_private_vm_contract_defines_specific_evidence_bundle():
    contract = stage.vm_runner_contract()
    files = contract["required_private_evidence_relative_files"]
    assert contract["preferred_runner"] == "qemu_kvm_disposable_vm_first"
    assert contract["fallback_runner"] == "qemu_tcg_only_if_kvm_unavailable_and_runtime_is_acceptable"
    assert contract["execution_authority"] == "none_in_this_stage"
    assert contract["required_private_evidence_file_count"] == len(files)
    assert contract["required_private_evidence_file_count"] == 37
    assert "independent_security_artifact_review.json" in files
    assert "slot_1/initial/stdout.raw" in files
    assert "slot_2/final/stderr.raw" in files
    assert "no_network_device_attached" in contract["minimum_isolation_controls"]
    assert "no_gpu_device_exposed" in contract["minimum_isolation_controls"]
    assert "plain_local_pytest_process" in contract["rejected_shortcuts"]


def test_public_vm_contract_hides_private_file_names_and_blocks_execution():
    loaded = stage.load_stage12613()
    summary, contract, private = stage.build_vm_contract_packet(loaded)
    assert summary["decision"] == "BLOCKED_INDEPENDENT_VM_RUNNER_CONTRACT_REVIEW_REQUIRED"
    assert summary["out_of_band_remediation_contract_only"] is True
    assert summary["stage12613_stage12614_allowance_preserved_false"] is True
    assert summary["preferred_runner"] == "qemu_kvm_disposable_vm_first"
    assert summary["vm_runner_contract_defined"] is True
    assert summary["vm_runner_contract_review_passed"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["execution_performed"] is False
    assert summary["training_allowed"] is False
    assert summary["vm_runner_contract_sha256"] == stage.stable_hash(private["vm_runner_contract"])
    assert contract["private_vm_contract_preflight_sha256"] == stage.stable_hash(private)
    for public_record in (summary, contract):
        assert_public_sanitized(public_record)
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_vm_contract_preflight_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/disposable_vm_runner_contract_preflight.json",
        "summary.json",
    ]
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/disposable_vm_runner_contract_preflight.json")
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    assert pointer["private_vm_contract_preflight_sha256"] == stage.stable_hash(private)
    assert summary["private_vm_contract_preflight_sha256"] == stage.stable_hash(private)
    assert summary["vm_runner_contract_sha256"] == stage.stable_hash(private["vm_runner_contract"])
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_generated_artifacts_match_current_vm_contract_preflight():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/disposable_vm_runner_contract_preflight.json",
        "summary.json",
    ]
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/disposable_vm_runner_contract_preflight.json")
    assert summary == external
    assert summary["preferred_runner"] == "qemu_kvm_disposable_vm_first"
    assert summary["required_private_evidence_file_count"] == 37
    assert summary["training_allowed"] is False
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    assert pointer["private_vm_contract_preflight_sha256"] == stage.stable_hash(private)
    assert summary["private_vm_contract_preflight_sha256"] == stage.stable_hash(private)
    assert summary["vm_runner_contract_sha256"] == stage.stable_hash(private["vm_runner_contract"])
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12616_independent_vm_storage_contract_review.py"
SPEC = importlib.util.spec_from_file_location("stage12616", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def assert_false_boundaries(record):
    for field in (
        "implementation_ready", "source_packet_implementation_allowed", "stage12595_allowed",
        "stage12613_allowed", "stage12614_allowed", "stage12615_allowed", "stage12616_allowed",
        "stage12617_allowed", "execution_performed", "replay_trustworthy",
        "raw_replay_evidence_present", "trusted_replay_raw_evidence_present",
        "external_bwrap_execution_evidence_present", "alternate_replay_evidence_present",
        "alternate_replay_trustworthy", "vm_runner_implementation_ready",
        "vm_runner_execution_allowed", "vm_runner_evidence_present", "vm_runner_trustworthy",
        "storage_root_created", "storage_write_performed", "host_workspace_mounted_in_guest",
        "host_volume_mounted_in_guest", "guest_network_enabled", "guest_gpu_enabled",
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


def test_load_stage12615_requires_containment_blocker_and_safety_booleans():
    loaded = stage.load_stage12615()
    summary = loaded["summary"]
    assert summary["decision"] == "BLOCKED_STORAGE_CONTAINMENT_REVIEW_REQUIRED"
    assert summary["storage_capacity_requirement_met"] is True
    assert summary["scratch_parent_is_mount"] is True
    assert summary["scratch_parent_separate_device_from_root"] is True
    assert summary["scratch_parent_separate_device_from_workspace"] is True
    assert summary["stage12616_allowed"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["training_allowed"] is False
    for record in loaded.values():
        for field in stage.FALSE_FIELDS:
            if field in record:
                assert record[field] is False


def test_review_findings_cover_vm_and_storage_escape_controls():
    findings = stage.review_findings()
    passed = findings["passed_checks"]
    residual = findings["residual_assumptions"]
    forbidden = findings["forbidden_after_review_pass"]
    assert "vm_contract_requires_no_network_and_no_gpu" in passed
    assert "vm_contract_requires_independent_security_artifact_review_source_file" in passed
    assert "storage_contract_forbids_workspace_mounts" in passed
    assert "storage_contract_forbids_private_scratch_root_mounts_into_guest" in passed
    assert "storage_contract_requires_private_scratch_parent_device_separate_from_root_and_workspace" in passed
    assert "future_qemu_command_review_must prove no host mounts or network devices" in residual
    assert "creating_private_scratch_root" in forbidden
    assert "launching_qemu" in forbidden
    assert "admitting_training" in forbidden


def test_review_pass_does_not_authorize_source_packet_execution_or_training():
    loaded = stage.load_stage12615()
    summary, contract, private = stage.build_review_packet(loaded)
    assert summary["decision"] == "INDEPENDENT_VM_STORAGE_CONTRACT_REVIEW_PASSED_SOURCE_PACKET_STILL_BLOCKED"
    assert summary["independent_contract_review_performed"] is True
    assert summary["independent_contract_review_passed"] is True
    assert summary["vm_runner_contract_review_passed"] is True
    assert summary["storage_containment_review_passed"] is True
    assert summary["source_packet_recommended"] is True
    assert summary["source_packet_implementation_allowed"] is False
    assert summary["stage12617_allowed"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["execution_performed"] is False
    assert summary["training_allowed"] is False
    assert summary["review_findings_sha256"] == stage.stable_hash(private["review_findings"])
    assert contract["private_contract_review_sha256"] == stage.stable_hash(private)
    for public_record in (summary, contract):
        assert_public_sanitized(public_record)
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_contract_review_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/independent_vm_storage_contract_review.json",
        "summary.json",
    ]
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/independent_vm_storage_contract_review.json")
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    assert pointer["private_contract_review_sha256"] == stage.stable_hash(private)
    assert summary["private_contract_review_sha256"] == stage.stable_hash(private)
    assert summary["review_findings_sha256"] == stage.stable_hash(private["review_findings"])
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_generated_artifacts_match_current_contract_review():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/independent_vm_storage_contract_review.json",
        "summary.json",
    ]
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/independent_vm_storage_contract_review.json")
    assert summary == external
    assert summary["independent_contract_review_passed"] is True
    assert summary["source_packet_recommended"] is True
    assert summary["source_packet_implementation_allowed"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["training_allowed"] is False
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    assert pointer["private_contract_review_sha256"] == stage.stable_hash(private)
    assert summary["private_contract_review_sha256"] == stage.stable_hash(private)
    assert summary["review_findings_sha256"] == stage.stable_hash(private["review_findings"])
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)

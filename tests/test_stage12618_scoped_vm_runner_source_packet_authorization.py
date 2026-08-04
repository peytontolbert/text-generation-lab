import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12618_scoped_vm_runner_source_packet_authorization.py"
SPEC = importlib.util.spec_from_file_location("stage12618", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def assert_false_boundaries(record):
    for field in (
        "implementation_ready", "source_packet_implementation_allowed",
        "source_packet_materialized", "source_packet_executable",
        "stage12595_allowed", "stage12613_allowed", "stage12614_allowed", "stage12615_allowed",
        "stage12616_allowed", "stage12617_allowed",
        "execution_performed", "replay_trustworthy", "raw_replay_evidence_present",
        "trusted_replay_raw_evidence_present", "external_bwrap_execution_evidence_present",
        "alternate_replay_evidence_present", "alternate_replay_trustworthy",
        "vm_runner_implementation_ready", "vm_runner_execution_allowed", "vm_runner_evidence_present",
        "vm_runner_trustworthy", "storage_root_created", "storage_write_performed",
        "host_workspace_mounted_in_guest", "host_volume_mounted_in_guest",
        "guest_network_enabled", "guest_gpu_enabled", "causal_transition_atoms_present",
        "causal_transition_atoms_materialized", "causal_transition_atoms_allowed",
        "causally_committed_pre_outcome_candidate_set_present",
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


def test_public_forbidden_substrings_include_required_private_leak_patterns():
    required = {
        "/data/",
        "/arxiv/",
        "agentkernel_vm_replay",
        "/dev/",
        "stdout.raw",
        "stderr.raw",
        "before_commit_oid",
        "after_commit_oid",
        "production_path",
        "production_patch_sha256",
        "manual_executor_slot_contracts",
        "slot_1.patch",
        "slot_2.patch",
        "repository_root",
        "patch_path",
        "slot_1/",
        "slot_2/",
    }
    assert required.issubset(set(stage.PUBLIC_FORBIDDEN_SUBSTRINGS))


def test_load_stage12617_requires_authorization_blocker():
    loaded = stage.load_stage12617()
    summary = loaded["summary"]
    assert summary["decision"] == "BLOCKED_MINIMAL_VM_RUNNER_SOURCE_PACKET_AUTHORIZATION_REQUIRED"
    assert summary["source_packet_authorization_required"] is True
    assert summary["source_packet_implementation_allowed"] is False
    assert summary["source_packet_materialized"] is False
    assert summary["stage12618_allowed"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["training_allowed"] is False
    for record in loaded.values():
        for field in stage.FALSE_FIELDS:
            if field in record:
                assert record[field] is False


def test_authorization_scope_grants_only_non_executable_materialization_next():
    scope = stage.authorization_scope()
    grants = scope["authorization_grants"]
    boundaries = scope["required_boundaries_for_authorized_materialization"]
    forbidden = scope["still_forbidden"]
    assert scope["authorized_next_stage"] == "stage12619_minimal_vm_runner_source_packet_materialization"
    assert "materialize_non_executable_source_packet_files" in grants
    assert "materialize_static_tests_for_source_packet_files" in grants
    assert "no_subprocess_invocation" in boundaries
    assert "no_qemu_launch_path" in boundaries
    assert "no_private_scratch_root_creation" in boundaries
    assert "no_arxiv_write" in boundaries
    assert "no_host_workspace_mount_argument" in boundaries
    assert "no_network_gpu_usb_argument" in boundaries
    assert "creating_private_scratch_root" in forbidden
    assert "launching_qemu" in forbidden
    assert "admitting_training" in forbidden


def test_authorization_allows_source_packet_only_and_blocks_execution_training():
    loaded = stage.load_stage12617()
    summary, contract, private = stage.build_authorization_packet(loaded)
    assert summary["decision"] == "SCOPED_SOURCE_PACKET_MATERIALIZATION_AUTHORIZED_EXECUTION_STILL_BLOCKED"
    assert summary["source_packet_authorization_recorded"] is True
    assert summary["successor_authorization_adjudicates_stage12617_blocked_state"] is True
    assert summary["stage12618_allowed"] is True
    assert summary["source_packet_implementation_allowed"] is False
    assert summary["source_packet_non_executable_materialization_allowed"] is True
    assert summary["stage12619_allowed"] is True
    assert summary["source_packet_materialized"] is False
    assert summary["source_packet_executable"] is False
    assert summary["storage_write_performed"] is False
    assert summary["storage_root_created"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["execution_performed"] is False
    assert summary["training_allowed"] is False
    assert summary["authorization_scope_sha256"] == stage.stable_hash(private["authorization_scope"])
    assert contract["private_source_packet_authorization_sha256"] == stage.stable_hash(private)
    for public_record in (summary, contract):
        assert_public_sanitized(public_record)
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_authorization_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/scoped_vm_runner_source_packet_authorization.json",
        "summary.json",
    ]
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/scoped_vm_runner_source_packet_authorization.json")
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    assert pointer["private_source_packet_authorization_sha256"] == stage.stable_hash(private)
    assert summary["private_source_packet_authorization_sha256"] == stage.stable_hash(private)
    assert summary["authorization_scope_sha256"] == stage.stable_hash(private["authorization_scope"])
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)



def test_generated_artifacts_have_only_independently_allowed_true_gates():
    allowed_true = {
        "source_packet_authorization_recorded",
        "successor_authorization_adjudicates_stage12617_blocked_state",
        "stage12618_allowed",
        "source_packet_non_executable_materialization_allowed",
        "stage12619_allowed",
    }
    paths = [
        stage.OUT / "summary.json",
        stage.SUMMARY,
        stage.OUT / "contract.json",
        stage.OUT / "digest_pointer.json",
        stage.OUT / "private/scoped_vm_runner_source_packet_authorization.json",
    ]
    critical_false = {
        "source_packet_implementation_allowed",
        "source_packet_materialized",
        "source_packet_executable",
        "storage_root_created",
        "storage_write_performed",
        "vm_runner_implementation_ready",
        "vm_runner_execution_allowed",
        "vm_runner_evidence_present",
        "vm_runner_trustworthy",
        "execution_performed",
        "replay_trustworthy",
        "raw_replay_evidence_present",
        "trusted_replay_raw_evidence_present",
        "causal_transition_atoms_present",
        "level_3_materialized",
        "training_allowed",
        "training_admitted",
        "strict_eval_admitted",
        "sealed_eval_admitted",
    }
    for path in paths:
        record = read_json(path)
        assert {key for key, value in record.items() if value is True} == allowed_true
        for key in critical_false:
            assert record[key] is False


def test_public_artifacts_pass_independent_literal_leak_scan():
    forbidden = (
        "/data/",
        "/arxiv/",
        "agentkernel_vm_replay",
        "/dev/",
        "selector",
        "raw_stream",
        "stdout.raw",
        "stderr.raw",
        "before_commit_oid",
        "after_commit_oid",
        "production_path",
        "production_patch_sha256",
        "manual_executor_slot_contracts",
        "slot_1.patch",
        "slot_2.patch",
        "repository_root",
        "patch_path",
        "slot_1/",
        "slot_2/",
    )
    public_paths = [
        stage.OUT / "summary.json",
        stage.SUMMARY,
        stage.OUT / "contract.json",
        stage.OUT / "digest_pointer.json",
    ]
    for path in public_paths:
        encoded = json.dumps(read_json(path), sort_keys=True)
        assert not [needle for needle in forbidden if needle in encoded]

def test_generated_artifacts_match_current_authorization():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/scoped_vm_runner_source_packet_authorization.json",
        "summary.json",
    ]
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/scoped_vm_runner_source_packet_authorization.json")
    assert summary == external
    assert summary["successor_authorization_adjudicates_stage12617_blocked_state"] is True
    assert summary["stage12618_allowed"] is True
    assert summary["source_packet_implementation_allowed"] is False
    assert summary["source_packet_non_executable_materialization_allowed"] is True
    assert summary["stage12619_allowed"] is True
    assert summary["source_packet_materialized"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["training_allowed"] is False
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    assert pointer["private_source_packet_authorization_sha256"] == stage.stable_hash(private)
    assert summary["private_source_packet_authorization_sha256"] == stage.stable_hash(private)
    assert summary["authorization_scope_sha256"] == stage.stable_hash(private["authorization_scope"])
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)

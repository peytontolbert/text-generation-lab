import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12617_minimal_vm_runner_source_packet_preflight.py"
SPEC = importlib.util.spec_from_file_location("stage12617", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def assert_false_boundaries(record):
    for field in (
        "implementation_ready", "source_packet_implementation_allowed", "source_packet_materialized",
        "source_packet_executable", "stage12595_allowed", "stage12613_allowed", "stage12614_allowed",
        "stage12615_allowed", "stage12616_allowed", "stage12617_allowed", "stage12618_allowed",
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


def test_load_stage12616_requires_review_pass_but_no_source_authority():
    loaded = stage.load_stage12616()
    summary = loaded["summary"]
    assert summary["decision"] == "INDEPENDENT_VM_STORAGE_CONTRACT_REVIEW_PASSED_SOURCE_PACKET_STILL_BLOCKED"
    assert summary["independent_contract_review_passed"] is True
    assert summary["source_packet_recommended"] is True
    assert summary["source_packet_implementation_allowed"] is False
    assert summary["stage12617_allowed"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["training_allowed"] is False
    for record in loaded.values():
        for field in stage.FALSE_FIELDS:
            if field in record:
                assert record[field] is False


def test_source_packet_requirements_define_non_executable_minimal_runner_boundary():
    requirements = stage.source_packet_requirements()
    assert requirements["implementation_authority"] == "none_in_this_stage"
    modules = requirements["minimum_future_modules"]
    hard = requirements["hard_source_packet_requirements"]
    review = requirements["required_static_review_checks_before_implementation_can_be_called_ready"]
    forbidden = requirements["still_forbidden"]
    assert "qemu_command_renderer" in modules
    assert "qcow2_overlay_planner" in modules
    assert "public_private_artifact_splitter" in modules
    assert "no_subprocess_execution_in_source_packet_build_stage" in hard
    assert "no_qemu_launch_path_until_explicit_execution_gate" in hard
    assert "no_network_device_argument_generation" in hard
    assert "no_gpu_or_usb_passthrough_argument_generation" in hard
    assert "no_virtiofs_9p_or_host_shared_folder_argument_generation" in hard
    assert "command_renderer_unit_tests_reject_host_mounts_network_gpu_usb" in review
    assert "writing_runner_source_files_as_authorized_implementation" in forbidden
    assert "launching_qemu" in forbidden
    assert "admitting_training" in forbidden


def test_source_packet_preflight_blocks_materialization_execution_and_training():
    loaded = stage.load_stage12616()
    summary, contract, private = stage.build_source_packet_preflight(loaded)
    assert summary["decision"] == "BLOCKED_MINIMAL_VM_RUNNER_SOURCE_PACKET_AUTHORIZATION_REQUIRED"
    assert summary["source_packet_preflight_only"] is True
    assert summary["source_packet_requirements_defined"] is True
    assert summary["source_packet_recommended_by_stage12616"] is True
    assert summary["source_packet_authorization_required"] is True
    assert summary["source_packet_implementation_allowed"] is False
    assert summary["source_packet_materialized"] is False
    assert summary["source_packet_executable"] is False
    assert summary["stage12618_allowed"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["execution_performed"] is False
    assert summary["training_allowed"] is False
    assert summary["source_packet_requirements_sha256"] == stage.stable_hash(
        private["source_packet_requirements"]
    )
    assert contract["private_source_packet_preflight_sha256"] == stage.stable_hash(private)
    for public_record in (summary, contract):
        assert_public_sanitized(public_record)
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_source_packet_preflight_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/minimal_vm_runner_source_packet_preflight.json",
        "summary.json",
    ]
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/minimal_vm_runner_source_packet_preflight.json")
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    assert pointer["private_source_packet_preflight_sha256"] == stage.stable_hash(private)
    assert summary["private_source_packet_preflight_sha256"] == stage.stable_hash(private)
    assert summary["source_packet_requirements_sha256"] == stage.stable_hash(
        private["source_packet_requirements"]
    )
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_generated_artifacts_match_current_source_packet_preflight():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/minimal_vm_runner_source_packet_preflight.json",
        "summary.json",
    ]
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/minimal_vm_runner_source_packet_preflight.json")
    assert summary == external
    assert summary["source_packet_requirements_defined"] is True
    assert summary["source_packet_implementation_allowed"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["training_allowed"] is False
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    assert pointer["private_source_packet_preflight_sha256"] == stage.stable_hash(private)
    assert summary["private_source_packet_preflight_sha256"] == stage.stable_hash(private)
    assert summary["source_packet_requirements_sha256"] == stage.stable_hash(
        private["source_packet_requirements"]
    )
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)

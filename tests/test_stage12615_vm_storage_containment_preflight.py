import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12615_vm_storage_containment_preflight.py"
SPEC = importlib.util.spec_from_file_location("stage12615", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def assert_false_boundaries(record):
    for field in (
        "implementation_ready", "stage12595_allowed", "stage12613_allowed", "stage12614_allowed",
        "stage12615_allowed", "stage12616_allowed", "execution_performed", "replay_trustworthy",
        "raw_replay_evidence_present", "trusted_replay_raw_evidence_present",
        "external_bwrap_execution_evidence_present", "alternate_replay_evidence_present",
        "alternate_replay_trustworthy", "vm_runner_contract_review_passed",
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


def test_load_stage12614_preserves_vm_contract_blocker():
    loaded = stage.load_stage12614()
    summary = loaded["summary"]
    assert summary["decision"] == "BLOCKED_INDEPENDENT_VM_RUNNER_CONTRACT_REVIEW_REQUIRED"
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["stage12615_allowed"] is False
    assert summary["training_allowed"] is False
    for record in loaded.values():
        for field in stage.FALSE_FIELDS:
            if field in record:
                assert record[field] is False


def test_storage_inspection_is_private_and_non_writing():
    storage = stage.inspect_private_storage_root()
    assert storage["private_scratch_root"] == "/arxiv/agentkernel_vm_replay"
    assert storage["private_scratch_parent"] == "/arxiv"
    assert storage["storage_write_performed"] is False
    assert storage["storage_root_created"] is False
    assert storage["minimum_available_gib_required"] == 20
    assert storage["minimum_available_gib_met"] is True
    assert storage["scratch_parent_is_mount"] is True
    assert storage["scratch_parent_separate_device_from_root"] is True
    assert storage["scratch_parent_separate_device_from_workspace"] is True
    assert storage["scratch_parent_device_id"] != storage["root_device_id"]
    assert storage["scratch_parent_device_id"] != storage["workspace_device_id"]
    assert storage["scratch_parent_mount_record"]["mount_point"] == "/arxiv"


def test_storage_contract_forbids_host_mount_escape_paths():
    contract = stage.storage_containment_contract()
    exposure = contract["host_filesystem_exposure_policy"]
    devices = contract["guest_device_policy"]
    image_policy = contract["image_policy"]
    assert "do_not_mount_host_workspace_into_guest" in exposure
    assert "do_not_mount_private_scratch_root_into_guest" in exposure
    assert "do_not_use_virtiofs_9p_or_shared_host_folders" in exposure
    assert "do_not_pass_host_block_devices_to_guest" in exposure
    assert "allow_only_qcow2_images_created_under_private_scratch_root" in exposure
    assert "evidence_extraction_after_guest_shutdown_only" in exposure
    assert "no_network_device" in devices
    assert "no_gpu_device" in devices
    assert "canonical_private_root_dirfd_required" in image_policy
    assert "creating_vm_images" in contract["forbidden_until_later_review"]


def test_public_storage_packet_sanitizes_private_root_and_blocks_execution():
    loaded = stage.load_stage12614()
    summary, contract, private = stage.build_storage_packet(loaded)
    assert summary["decision"] == "BLOCKED_STORAGE_CONTAINMENT_REVIEW_REQUIRED"
    assert summary["storage_containment_preflight_only"] is True
    assert summary["private_scratch_root_label"] == "private_external_scratch_root"
    assert summary["storage_capacity_requirement_met"] is True
    assert summary["scratch_parent_is_mount"] is True
    assert summary["scratch_parent_separate_device_from_root"] is True
    assert summary["scratch_parent_separate_device_from_workspace"] is True
    assert summary["storage_write_performed"] is False
    assert summary["storage_root_created"] is False
    assert summary["host_workspace_mounted_in_guest"] is False
    assert summary["host_volume_mounted_in_guest"] is False
    assert summary["guest_network_enabled"] is False
    assert summary["guest_gpu_enabled"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["training_allowed"] is False
    assert "/arxiv/agentkernel_vm_replay" == private["private_storage_inspection"]["private_scratch_root"]
    assert summary["storage_containment_contract_sha256"] == stage.stable_hash(
        private["storage_containment_contract"]
    )
    assert contract["private_storage_containment_preflight_sha256"] == stage.stable_hash(private)
    for public_record in (summary, contract):
        assert_public_sanitized(public_record)
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_storage_packet_rejects_shared_or_unmounted_scratch_parent(monkeypatch):
    loaded = stage.load_stage12614()
    good = stage.inspect_private_storage_root()
    for field, message in (
        ("scratch_parent_is_mount", "private_scratch_parent_not_mountpoint"),
        ("scratch_parent_separate_device_from_root", "private_scratch_parent_shares_root_device"),
        ("scratch_parent_separate_device_from_workspace", "private_scratch_parent_shares_workspace_device"),
    ):
        bad = dict(good)
        bad[field] = False
        monkeypatch.setattr(stage, "inspect_private_storage_root", lambda bad=bad: bad)
        with pytest.raises(stage.StorageContainmentPreflightError, match=message):
            stage.build_storage_packet(loaded)


def test_build_writes_only_storage_containment_preflight_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/vm_storage_containment_preflight.json",
        "summary.json",
    ]
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/vm_storage_containment_preflight.json")
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    assert pointer["private_storage_containment_preflight_sha256"] == stage.stable_hash(private)
    assert summary["private_storage_containment_preflight_sha256"] == stage.stable_hash(private)
    assert summary["storage_containment_contract_sha256"] == stage.stable_hash(
        private["storage_containment_contract"]
    )
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_generated_artifacts_match_current_storage_containment_preflight():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/vm_storage_containment_preflight.json",
        "summary.json",
    ]
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/vm_storage_containment_preflight.json")
    assert summary == external
    assert summary["storage_containment_preflight_only"] is True
    assert summary["private_scratch_root_label"] == "private_external_scratch_root"
    assert summary["reserved_storage_gib"] == 20
    assert summary["scratch_parent_is_mount"] is True
    assert summary["scratch_parent_separate_device_from_root"] is True
    assert summary["scratch_parent_separate_device_from_workspace"] is True
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["training_allowed"] is False
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    assert pointer["private_storage_containment_preflight_sha256"] == stage.stable_hash(private)
    assert summary["private_storage_containment_preflight_sha256"] == stage.stable_hash(private)
    assert summary["storage_containment_contract_sha256"] == stage.stable_hash(
        private["storage_containment_contract"]
    )
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)

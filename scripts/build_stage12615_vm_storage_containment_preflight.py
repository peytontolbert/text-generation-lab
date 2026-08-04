#!/usr/bin/env python3
"""Build Stage12615 VM storage containment preflight.

Stage12614 defines the disposable VM evidence contract. This stage adds the
host-storage containment contract for using a private external scratch volume
without exposing the host workspace or the rest of the hard drive to the guest.
It performs no writes to the scratch volume and authorizes no VM execution.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12615_vm_storage_containment_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12614 = ROOT / "runs/local/artifacts/stage12614_disposable_vm_runner_contract_preflight"
S12614_EXTERNAL = ROOT / "runs/summaries/stage12614_disposable_vm_runner_contract_preflight.json"
EXPECTED_STAGE12614_SUMMARY = "c8397a7eedaca2638d0543d51e6f26722e13d96c874a43a0898d731ad2e14033"
EXPECTED_STAGE12614_CONTRACT = "d641d86f214851ea098f4eff10321e7994231f6875956ec7f92dc2264bef2878"
EXPECTED_STAGE12614_POINTER = "bb156b0e574bb43f452cea1f64ae2ddbe9f064c03fc84236c252c79739dfb248"
EXPECTED_STAGE12614_PRIVATE = "da717af7aab8dfc3aafa5f9a23012654fe4762d96d76c0c930a491c22965760c"
EXPECTED_GATE_SCOPE = "reviewed_stage12602_execute_reviewed_slot_function_only"
PRIVATE_SCRATCH_ROOT = Path("/arxiv/agentkernel_vm_replay")
MINIMUM_AVAILABLE_GIB = 20
MAX_PER_REPLAY_GIB = 16
MAX_EVIDENCE_MIB = 256

FALSE_FIELDS = (
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
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "agentkernel_vm_replay", "selector", "raw_stream", "stdout.raw",
    "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path",
    "production_patch_sha256", "manual_executor_slot_contracts", "slot_1.patch",
    "slot_2.patch", "repository_root", "patch_path", "slot_1/", "slot_2/",
)


class StorageContainmentPreflightError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def stable_hash(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise StorageContainmentPreflightError("json_object_required:" + path.name)
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def no_claim_fields() -> dict[str, Any]:
    return {
        "implementation_ready": False,
        "stage12595_allowed": False,
        "stage12613_allowed": False,
        "stage12614_allowed": False,
        "stage12615_allowed": False,
        "stage12616_allowed": False,
        "execution_performed": False,
        "replay_trustworthy": False,
        "raw_replay_evidence_present": False,
        "trusted_replay_raw_evidence_present": False,
        "external_bwrap_execution_evidence_present": False,
        "alternate_replay_evidence_present": False,
        "alternate_replay_trustworthy": False,
        "vm_runner_contract_review_passed": False,
        "vm_runner_implementation_ready": False,
        "vm_runner_execution_allowed": False,
        "vm_runner_evidence_present": False,
        "vm_runner_trustworthy": False,
        "storage_root_created": False,
        "storage_write_performed": False,
        "host_workspace_mounted_in_guest": False,
        "host_volume_mounted_in_guest": False,
        "guest_network_enabled": False,
        "guest_gpu_enabled": False,
        "causal_transition_atoms_present": False,
        "causal_transition_atoms_materialized": False,
        "causal_transition_atoms_allowed": False,
        "causally_committed_pre_outcome_candidate_set_present": False,
        "observed_stop_continue_decision_provenance_present": False,
        "level3_preflight_allowed": False,
        "level_3_materialized": False,
        "level_3_materialization_allowed": False,
        "training_admission_preflight_allowed": False,
        "training_admission_allowed": False,
        "training_admitted": False,
        "training_allowed": False,
        "training_run_allowed": False,
        "gpu_allocation_requested": False,
        "cuda2_training_allowed": False,
        "strict_eval_admitted": False,
        "sealed_eval_admitted": False,
        "strict_eval_eligible": False,
        "sealed_eval_eligible": False,
        "admission_allowed": False,
        "ranking_allowed": False,
        "positive_stop": False,
    }


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise StorageContainmentPreflightError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise StorageContainmentPreflightError(f"{label}_public_leak:{needle}")


def load_stage12614() -> dict[str, Any]:
    summary = read_json(S12614 / "summary.json")
    external = read_json(S12614_EXTERNAL)
    contract = read_json(S12614 / "contract.json")
    pointer = read_json(S12614 / "digest_pointer.json")
    private = read_json(S12614 / "private/disposable_vm_runner_contract_preflight.json")
    if summary != external:
        raise StorageContainmentPreflightError("stage12614_external_summary_mismatch")
    expected = (
        (stable_hash(summary), EXPECTED_STAGE12614_SUMMARY, "summary"),
        (stable_hash(contract), EXPECTED_STAGE12614_CONTRACT, "contract"),
        (stable_hash(pointer), EXPECTED_STAGE12614_POINTER, "pointer"),
        (stable_hash(private), EXPECTED_STAGE12614_PRIVATE, "private"),
    )
    for actual, expected_hash, label in expected:
        if actual != expected_hash:
            raise StorageContainmentPreflightError("stage12614_pin_drift:" + label)
    if summary.get("decision") != "BLOCKED_INDEPENDENT_VM_RUNNER_CONTRACT_REVIEW_REQUIRED":
        raise StorageContainmentPreflightError("stage12614_decision_drift")
    if summary.get("vm_runner_execution_allowed") is not False:
        raise StorageContainmentPreflightError("stage12614_execution_gate_drift")
    if summary.get("stage12615_allowed") is not False:
        raise StorageContainmentPreflightError("stage12614_stage12615_gate_drift")
    if summary.get("training_allowed") is not False:
        raise StorageContainmentPreflightError("stage12614_training_gate_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_false(record, "stage12614_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private}


def mount_record_for(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    best: dict[str, Any] | None = None
    best_len = -1
    for line in Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines():
        left, separator, right = line.partition(" - ")
        if not separator:
            continue
        left_fields = left.split()
        right_fields = right.split()
        if len(left_fields) < 5 or len(right_fields) < 3:
            continue
        mount_point = left_fields[4].replace("\\040", " ")
        mount_path = Path(mount_point)
        try:
            candidate = mount_path.resolve()
        except OSError:
            continue
        if resolved == candidate or resolved.is_relative_to(candidate):
            length = len(str(candidate))
            if length > best_len:
                best_len = length
                best = {
                    "mount_point": str(mount_path),
                    "filesystem_type": right_fields[0],
                    "mount_source": right_fields[1],
                    "super_options": right_fields[2],
                }
    if best is None:
        raise StorageContainmentPreflightError("scratch_parent_mount_record_missing")
    return best


def inspect_private_storage_root() -> dict[str, Any]:
    scratch_parent = PRIVATE_SCRATCH_ROOT.parent
    usage = shutil.disk_usage(scratch_parent)
    available_gib = usage.free // (1024 ** 3)
    scratch_parent_stat = scratch_parent.stat()
    root_stat = Path("/").stat()
    workspace_stat = ROOT.stat()
    mount_record = mount_record_for(scratch_parent)
    scratch_parent_is_mount = os.path.ismount(scratch_parent)
    separate_from_root = scratch_parent_stat.st_dev != root_stat.st_dev
    separate_from_workspace = scratch_parent_stat.st_dev != workspace_stat.st_dev
    return {
        "private_scratch_root": str(PRIVATE_SCRATCH_ROOT),
        "private_scratch_parent": str(scratch_parent),
        "private_scratch_root_exists": PRIVATE_SCRATCH_ROOT.exists(),
        "storage_write_performed": False,
        "storage_root_created": False,
        "available_gib_floor": int(available_gib),
        "minimum_available_gib_required": MINIMUM_AVAILABLE_GIB,
        "minimum_available_gib_met": available_gib >= MINIMUM_AVAILABLE_GIB,
        "max_per_replay_gib": MAX_PER_REPLAY_GIB,
        "max_evidence_mib": MAX_EVIDENCE_MIB,
        "scratch_parent_is_mount": scratch_parent_is_mount,
        "scratch_parent_device_id": int(scratch_parent_stat.st_dev),
        "root_device_id": int(root_stat.st_dev),
        "workspace_device_id": int(workspace_stat.st_dev),
        "scratch_parent_separate_device_from_root": separate_from_root,
        "scratch_parent_separate_device_from_workspace": separate_from_workspace,
        "scratch_parent_mount_record": mount_record,
    }


def storage_containment_contract() -> dict[str, Any]:
    return {
        "record_type": "stage12615_vm_storage_containment_contract_v1",
        "private_scratch_root_label": "private_external_scratch_root",
        "reserved_storage_gib": MINIMUM_AVAILABLE_GIB,
        "max_per_replay_gib": MAX_PER_REPLAY_GIB,
        "max_evidence_mib": MAX_EVIDENCE_MIB,
        "host_filesystem_exposure_policy": [
            "do_not_mount_host_workspace_into_guest",
            "do_not_mount_private_scratch_root_into_guest",
            "do_not_use_virtiofs_9p_or_shared_host_folders",
            "do_not_pass_host_block_devices_to_guest",
            "allow_only_qcow2_images_created_under_private_scratch_root",
            "evidence_extraction_after_guest_shutdown_only",
        ],
        "guest_device_policy": [
            "no_network_device",
            "no_gpu_device",
            "no_usb_passthrough",
            "no_host_serial_command_channel_after_boot",
            "kvm_acceleration_allowed_only_as_cpu_accelerator_not_storage_access",
        ],
        "image_policy": [
            "base_image_read_only",
            "ephemeral_overlay_created_exclusive",
            "overlay_parent_fsynced_after_create_and_after_remove",
            "artifact_image_created_exclusive",
            "no_symlink_or_hardlink_paths",
            "canonical_private_root_dirfd_required",
        ],
        "run_time_limits": [
            "fixed_command_manifest_only",
            "fixed_initial_patched_final_phase_sequence",
            "bounded_stdout_stderr_capture",
            "wall_clock_timeout_required",
            "process_tree_kill_on_timeout",
        ],
        "forbidden_until_later_review": [
            "creating_private_scratch_root",
            "creating_vm_images",
            "launching_qemu",
            "mounting_any_guest_image",
            "extracting_evidence",
            "claiming_replay_success",
        ],
    }


def build_storage_packet(stage12614: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    storage = inspect_private_storage_root()
    if storage["minimum_available_gib_met"] is not True:
        raise StorageContainmentPreflightError("private_scratch_parent_capacity_below_minimum")
    if storage["scratch_parent_is_mount"] is not True:
        raise StorageContainmentPreflightError("private_scratch_parent_not_mountpoint")
    if storage["scratch_parent_separate_device_from_root"] is not True:
        raise StorageContainmentPreflightError("private_scratch_parent_shares_root_device")
    if storage["scratch_parent_separate_device_from_workspace"] is not True:
        raise StorageContainmentPreflightError("private_scratch_parent_shares_workspace_device")
    contract_manifest = storage_containment_contract()
    private = {
        "record_type": "stage12615_private_vm_storage_containment_preflight_v1",
        "stage12614_summary_sha256": EXPECTED_STAGE12614_SUMMARY,
        "stage12614_private_vm_contract_preflight_sha256": EXPECTED_STAGE12614_PRIVATE,
        "source_decision": stage12614["summary"]["decision"],
        "gate_scope": EXPECTED_GATE_SCOPE,
        "storage_containment_preflight_only": True,
        "stage12614_stage12615_allowance_preserved_false": True,
        "private_storage_inspection": storage,
        "storage_containment_contract": contract_manifest,
        "decision": "BLOCKED_STORAGE_CONTAINMENT_REVIEW_REQUIRED",
        **no_claim_fields(),
    }
    contract = {
        "record_type": "stage12615_public_vm_storage_containment_contract_v1",
        "stage12614_summary_sha256": EXPECTED_STAGE12614_SUMMARY,
        "stage12614_contract_sha256": EXPECTED_STAGE12614_CONTRACT,
        "stage12614_private_vm_contract_preflight_sha256": EXPECTED_STAGE12614_PRIVATE,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "storage_containment_preflight_only": True,
        "stage12614_stage12615_allowance_preserved_false": True,
        "private_scratch_root_label": "private_external_scratch_root",
        "storage_capacity_requirement_met": storage["minimum_available_gib_met"],
        "scratch_parent_is_mount": storage["scratch_parent_is_mount"],
        "scratch_parent_separate_device_from_root": storage["scratch_parent_separate_device_from_root"],
        "scratch_parent_separate_device_from_workspace": storage["scratch_parent_separate_device_from_workspace"],
        "reserved_storage_gib": MINIMUM_AVAILABLE_GIB,
        "max_per_replay_gib": MAX_PER_REPLAY_GIB,
        "max_evidence_mib": MAX_EVIDENCE_MIB,
        "storage_containment_contract_sha256": stable_hash(contract_manifest),
        "private_storage_containment_preflight_sha256": stable_hash(private),
        "claim_boundary": {
            "purpose": "define_host_storage_containment_without_writing_or_running_vm",
            "storage_write": "not_performed",
            "vm_launch": "not_authorized",
            "host_mounts_to_guest": "forbidden",
            "training": "not_authorized",
        },
        **no_claim_fields(),
    }
    summary = {
        "record_type": "stage12615_public_vm_storage_containment_preflight_summary_v1",
        "stage": STAGE,
        "decision": "BLOCKED_STORAGE_CONTAINMENT_REVIEW_REQUIRED",
        "stage12614_summary_sha256": EXPECTED_STAGE12614_SUMMARY,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "storage_containment_preflight_only": True,
        "stage12614_stage12615_allowance_preserved_false": True,
        "private_scratch_root_label": "private_external_scratch_root",
        "storage_capacity_requirement_met": storage["minimum_available_gib_met"],
        "scratch_parent_is_mount": storage["scratch_parent_is_mount"],
        "scratch_parent_separate_device_from_root": storage["scratch_parent_separate_device_from_root"],
        "scratch_parent_separate_device_from_workspace": storage["scratch_parent_separate_device_from_workspace"],
        "reserved_storage_gib": MINIMUM_AVAILABLE_GIB,
        "max_per_replay_gib": MAX_PER_REPLAY_GIB,
        "max_evidence_mib": MAX_EVIDENCE_MIB,
        "storage_containment_contract_sha256": stable_hash(contract_manifest),
        "private_storage_containment_preflight_sha256": stable_hash(private),
        "downstream_blockers": [
            "stage12614_stage12615_allowance_remains_false",
            "storage_containment_review_absent",
            "storage_root_not_created_by_this_stage",
            "vm_runner_implementation_absent",
            "trusted_replay_raw_evidence_absent",
            "causal_transition_atoms_absent",
            "level3_materialization_forbidden",
            "training_admission_forbidden",
        ],
        **no_claim_fields(),
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12615_" + label)
        assert_public_sanitized(record, "stage12615_" + label)
    check_false(private, "stage12615_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12614 = load_stage12614()
    summary, contract, private = build_storage_packet(stage12614)
    pointer = {
        "record_type": "stage12615_public_private_vm_storage_containment_pointer_v1",
        "stage12614_summary_sha256": EXPECTED_STAGE12614_SUMMARY,
        "contract_sha256": stable_hash(contract),
        "private_storage_containment_preflight_sha256": stable_hash(private),
        "storage_containment_preflight_only": True,
        "stage12614_stage12615_allowance_preserved_false": True,
        "private_scratch_root_label": "private_external_scratch_root",
        "storage_capacity_requirement_met": summary["storage_capacity_requirement_met"],
        **no_claim_fields(),
    }
    check_false(pointer, "stage12615_pointer")
    assert_public_sanitized(pointer, "stage12615_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/vm_storage_containment_preflight.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))

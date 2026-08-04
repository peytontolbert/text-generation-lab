#!/usr/bin/env python3
"""Build Stage12619 minimal VM runner source-packet materialization.

Stage12618 authorized only non-executable source-packet materialization for
Stage12619. This stage writes static schema/specification artifacts and review
fixtures. It does not create executable runner source, scratch storage, VM
images, launch commands, replay evidence, causal atoms, or training admission.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12619_minimal_vm_runner_source_packet_materialization"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12618 = ROOT / "runs/local/artifacts/stage12618_scoped_vm_runner_source_packet_authorization"
S12618_EXTERNAL = ROOT / "runs/summaries/stage12618_scoped_vm_runner_source_packet_authorization.json"
EXPECTED_STAGE12618_SUMMARY = "34088923f55706f8d8334e329a5287fc39e3dc8c9fb22cc666ead6d6506266c6"
EXPECTED_STAGE12618_CONTRACT = "1aff77a2a74c2c6c5b86a3d30db532001b391ed817916505e2c6f0c87203d284"
EXPECTED_STAGE12618_POINTER = "f0a77de686f661ccf409b5c9874fccb4c6ff046c1644ac5475a7617066c32e3e"
EXPECTED_STAGE12618_PRIVATE = "281df2c2b07b8c86862595d931692bc51949c8795c998fbc04e1528ba7ef27d5"
EXPECTED_GATE_SCOPE = "reviewed_stage12602_execute_reviewed_slot_function_only"

FALSE_FIELDS = (
    "implementation_ready", "source_packet_implementation_allowed", "source_packet_executable",
    "stage12595_allowed", "stage12613_allowed", "stage12614_allowed", "stage12615_allowed",
    "stage12616_allowed", "stage12617_allowed", "stage12618_allowed", "stage12619_allowed", "stage12620_allowed",
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
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream",
    "stdout.raw", "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path",
    "production_patch_sha256", "manual_executor_slot_contracts", "slot_1.patch",
    "slot_2.patch", "repository_root", "patch_path", "slot_1/", "slot_2/",
)
SOURCE_PACKET_FORBIDDEN_SUBSTRINGS = (
    "subprocess", "Popen", "os.system", "exec(", "eval(", "qemu-system", "--enable-kvm",
    "-net", "-nic", "virtiofs", "9p", "/arxiv/", "/data/", "/dev/", "CUDA_VISIBLE_DEVICES",
    "socket", "requests", "urllib", "paramiko", "scp ", "ssh ", "mount ", "mkfs", "truncate ",
)


class SourcePacketMaterializationError(RuntimeError):
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
        raise SourcePacketMaterializationError("json_object_required:" + path.name)
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
        "source_packet_implementation_allowed": False,
        "source_packet_executable": False,
        "stage12595_allowed": False,
        "stage12613_allowed": False,
        "stage12614_allowed": False,
        "stage12615_allowed": False,
        "stage12616_allowed": False,
        "stage12617_allowed": False,
        "stage12618_allowed": False,
        "stage12619_allowed": False,
        "stage12620_allowed": False,
        "execution_performed": False,
        "replay_trustworthy": False,
        "raw_replay_evidence_present": False,
        "trusted_replay_raw_evidence_present": False,
        "external_bwrap_execution_evidence_present": False,
        "alternate_replay_evidence_present": False,
        "alternate_replay_trustworthy": False,
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
            raise SourcePacketMaterializationError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise SourcePacketMaterializationError(f"{label}_public_leak:{needle}")


def check_stage12618_authorized_truth(record: Mapping[str, Any], label: str) -> None:
    allowed_true = {
        "source_packet_authorization_recorded",
        "successor_authorization_adjudicates_stage12617_blocked_state",
        "stage12618_allowed",
        "source_packet_non_executable_materialization_allowed",
        "stage12619_allowed",
    }
    unexpected = sorted(key for key, value in record.items() if value is True and key not in allowed_true)
    if unexpected:
        raise SourcePacketMaterializationError(f"{label}_unexpected_true:" + ",".join(unexpected))
    required_false = (
        "source_packet_implementation_allowed", "source_packet_materialized", "source_packet_executable",
        "vm_runner_execution_allowed", "storage_write_performed", "training_allowed",
        "execution_performed", "replay_trustworthy", "level_3_materialized",
    )
    for field in required_false:
        if field in record and record[field] is not False:
            raise SourcePacketMaterializationError(f"{label}_required_false_drift:" + field)


def load_stage12618() -> dict[str, Any]:
    summary = read_json(S12618 / "summary.json")
    external = read_json(S12618_EXTERNAL)
    contract = read_json(S12618 / "contract.json")
    pointer = read_json(S12618 / "digest_pointer.json")
    private = read_json(S12618 / "private/scoped_vm_runner_source_packet_authorization.json")
    if summary != external:
        raise SourcePacketMaterializationError("stage12618_external_summary_mismatch")
    expected = (
        (stable_hash(summary), EXPECTED_STAGE12618_SUMMARY, "summary"),
        (stable_hash(contract), EXPECTED_STAGE12618_CONTRACT, "contract"),
        (stable_hash(pointer), EXPECTED_STAGE12618_POINTER, "pointer"),
        (stable_hash(private), EXPECTED_STAGE12618_PRIVATE, "private"),
    )
    for actual, expected_hash, label in expected:
        if actual != expected_hash:
            raise SourcePacketMaterializationError("stage12618_pin_drift:" + label)
    if summary.get("decision") != "SCOPED_SOURCE_PACKET_MATERIALIZATION_AUTHORIZED_EXECUTION_STILL_BLOCKED":
        raise SourcePacketMaterializationError("stage12618_decision_drift")
    required_true = (
        "source_packet_authorization_recorded",
        "successor_authorization_adjudicates_stage12617_blocked_state",
        "stage12618_allowed",
        "source_packet_non_executable_materialization_allowed",
        "stage12619_allowed",
    )
    for field in required_true:
        if summary.get(field) is not True:
            raise SourcePacketMaterializationError("stage12618_required_true_drift:" + field)
    required_false = (
        "source_packet_implementation_allowed", "source_packet_materialized", "source_packet_executable",
        "vm_runner_execution_allowed", "storage_write_performed", "training_allowed",
    )
    for field in required_false:
        if summary.get(field) is not False:
            raise SourcePacketMaterializationError("stage12618_required_false_drift:" + field)
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_stage12618_authorized_truth(record, "stage12618_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private}


def module_specs() -> list[dict[str, Any]]:
    names = [
        "contract_manifest_loader",
        "private_scratch_dirfd_allocator",
        "qcow2_overlay_planner",
        "qemu_command_renderer",
        "guest_command_manifest_renderer",
        "phase_evidence_collector",
        "public_private_artifact_splitter",
        "public_leak_scanner",
        "exit_status_consistency_checker",
        "tree_digest_revert_checker",
    ]
    return [
        {
            "name": name,
            "file": f"source_packet/module_specs/{name}.json",
            "artifact_type": "non_executable_schema_spec",
            "runtime_behavior": "none",
            "review_status": "static_review_required_before_code_generation",
        }
        for name in names
    ]


def static_test_specs() -> list[dict[str, Any]]:
    return [
        {"name": "no_process_invocation_tokens", "target": "source_packet", "expected": "absent"},
        {"name": "no_vm_launch_tokens", "target": "source_packet", "expected": "absent"},
        {"name": "no_host_or_private_path_leaks_in_public_records", "target": "public_artifacts", "expected": "absent"},
        {"name": "only_non_executable_materialization_gate_true", "target": "all_records", "expected": "exact"},
        {"name": "stage12618_pins_are_current", "target": "predecessor", "expected": "exact"},
    ]


def materialized_source_packet() -> dict[str, Any]:
    specs = module_specs()
    tests = static_test_specs()
    manifest = {
        "record_type": "stage12619_non_executable_source_packet_manifest_v1",
        "packet_scope": EXPECTED_GATE_SCOPE,
        "source_packet_kind": "static_schema_specs_only",
        "module_count": len(specs),
        "static_test_spec_count": len(tests),
        "module_specs": specs,
        "static_test_specs": tests,
        "non_executable_constraints": [
            "json_specs_only",
            "no_py_files_materialized",
            "no_executable_mode_bits",
            "no_process_invocation_api_names",
            "no_vm_launch_command_tokens",
            "no_storage_root_creation_actions",
            "no_replay_execution_actions",
            "no_training_or_eval_admission_claims",
        ],
        "next_required_review": "stage12620_independent_source_packet_static_review",
    }
    return manifest


def packet_file_payloads(manifest: Mapping[str, Any]) -> dict[str, Any]:
    payloads: dict[str, Any] = {"source_packet/manifest.json": manifest}
    for spec in manifest["module_specs"]:
        payloads[spec["file"]] = spec
    payloads["source_packet/static_review_tests.json"] = {
        "record_type": "stage12619_static_review_test_specs_v1",
        "tests": manifest["static_test_specs"],
    }
    return payloads


def validate_packet_payloads(payloads: Mapping[str, Any]) -> None:
    for relpath, payload in payloads.items():
        if relpath.startswith("/") or ".." in Path(relpath).parts:
            raise SourcePacketMaterializationError("bad_packet_path:" + relpath)
        if not relpath.endswith(".json"):
            raise SourcePacketMaterializationError("non_json_packet_file:" + relpath)
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        for needle in SOURCE_PACKET_FORBIDDEN_SUBSTRINGS:
            if needle in encoded:
                raise SourcePacketMaterializationError("source_packet_forbidden_token:" + needle)


def build_materialization_packet(stage12618: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest = materialized_source_packet()
    payloads = packet_file_payloads(manifest)
    validate_packet_payloads(payloads)
    packet_hashes = {relpath: stable_hash(payload) for relpath, payload in sorted(payloads.items())}
    packet_manifest_hash = stable_hash(manifest)
    private = {
        "record_type": "stage12619_private_minimal_vm_runner_source_packet_materialization_v1",
        **no_claim_fields(),
        "stage12618_summary_sha256": EXPECTED_STAGE12618_SUMMARY,
        "stage12618_private_authorization_sha256": EXPECTED_STAGE12618_PRIVATE,
        "source_decision": stage12618["summary"]["decision"],
        "gate_scope": EXPECTED_GATE_SCOPE,
        "source_packet_materialized": True,
        "source_packet_non_executable_materialization_allowed": True,
        "source_packet_static_review_required": True,
        "stage12620_static_review_only_allowed": True,
        "source_packet_file_hashes": packet_hashes,
        "source_packet_manifest": manifest,
        "decision": "NON_EXECUTABLE_SOURCE_PACKET_MATERIALIZED_STATIC_REVIEW_REQUIRED",
    }
    contract = {
        "record_type": "stage12619_public_minimal_vm_runner_source_packet_materialization_v1",
        **no_claim_fields(),
        "stage12618_summary_sha256": EXPECTED_STAGE12618_SUMMARY,
        "stage12618_contract_sha256": EXPECTED_STAGE12618_CONTRACT,
        "stage12618_private_authorization_sha256": EXPECTED_STAGE12618_PRIVATE,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "source_packet_materialized": True,
        "source_packet_non_executable_materialization_allowed": True,
        "source_packet_static_review_required": True,
        "stage12620_static_review_only_allowed": True,
        "source_packet_file_count": len(payloads),
        "source_packet_manifest_sha256": packet_manifest_hash,
        "private_source_packet_materialization_sha256": stable_hash(private),
        "claim_boundary": {
            "source_packet": "non_executable_specs_materialized",
            "implementation": "not_authorized",
            "storage_write": "not_authorized",
            "vm_launch": "not_authorized",
            "replay": "not_authorized",
            "training": "not_authorized",
        },
    }
    summary = {
        "record_type": "stage12619_public_minimal_vm_runner_source_packet_materialization_summary_v1",
        **no_claim_fields(),
        "stage": STAGE,
        "decision": "NON_EXECUTABLE_SOURCE_PACKET_MATERIALIZED_STATIC_REVIEW_REQUIRED",
        "stage12618_summary_sha256": EXPECTED_STAGE12618_SUMMARY,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "source_packet_materialized": True,
        "source_packet_non_executable_materialization_allowed": True,
        "source_packet_static_review_required": True,
        "stage12620_static_review_only_allowed": True,
        "source_packet_file_count": len(payloads),
        "source_packet_manifest_sha256": packet_manifest_hash,
        "private_source_packet_materialization_sha256": stable_hash(private),
        "downstream_blockers": [
            "independent_source_packet_static_review_absent",
            "vm_runner_implementation_still_not_authorized",
            "vm_runner_execution_gate_absent",
            "private_scratch_root_not_created",
            "trusted_replay_raw_evidence_absent",
            "causal_transition_atoms_absent",
            "level3_materialization_forbidden",
            "training_admission_forbidden",
        ],
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12619_" + label)
        assert_public_sanitized(record, "stage12619_" + label)
    check_false(private, "stage12619_private")
    return summary, contract, private, payloads


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12618 = load_stage12618()
    summary, contract, private, payloads = build_materialization_packet(stage12618)
    pointer = {
        "record_type": "stage12619_public_private_minimal_vm_runner_source_packet_materialization_pointer_v1",
        **no_claim_fields(),
        "stage12618_summary_sha256": EXPECTED_STAGE12618_SUMMARY,
        "contract_sha256": stable_hash(contract),
        "private_source_packet_materialization_sha256": stable_hash(private),
        "source_packet_materialized": True,
        "source_packet_non_executable_materialization_allowed": True,
        "source_packet_static_review_required": True,
        "stage12620_static_review_only_allowed": True,
    }
    check_false(pointer, "stage12619_pointer")
    assert_public_sanitized(pointer, "stage12619_pointer")
    for relpath, payload in payloads.items():
        write_json(out / relpath, payload)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/minimal_vm_runner_source_packet_materialization.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))

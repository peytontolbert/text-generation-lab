#!/usr/bin/env python3
"""Build Stage12620 independent static review for the Stage12619 source packet.

This stage reviews the non-executable JSON source packet materialized by
Stage12619. It does not authorize implementation, create runner source, create
storage, launch a VM, execute replay, materialize causal atoms, or admit
training.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12620_independent_source_packet_static_review"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12619 = ROOT / "runs/local/artifacts/stage12619_minimal_vm_runner_source_packet_materialization"
S12619_EXTERNAL = ROOT / "runs/summaries/stage12619_minimal_vm_runner_source_packet_materialization.json"
EXPECTED_STAGE12619_SUMMARY = "afa3b36205ceda8bf1942c2548c79ebabb0d823fc9c2cb758dc469bc51aa592d"
EXPECTED_STAGE12619_CONTRACT = "e3722650934339259240a65ef5396d1fc59e9dda86a862176ce5c49c560b301f"
EXPECTED_STAGE12619_POINTER = "64aacc398edb2b4dd4a203ce951b8c7b5bf14c354cb9540d3902ddf1370b342c"
EXPECTED_STAGE12619_PRIVATE = "45dd61c51bd843551cc8f38886eb08f88829b7e318e7746c0dc6c109cefcab7f"
EXPECTED_STAGE12619_MANIFEST = "ae001901c1b799ecf75ae499d75839c7ee71f21cd3126ebba756b360f2e76080"
EXPECTED_GATE_SCOPE = "reviewed_stage12602_execute_reviewed_slot_function_only"
EXPECTED_MODULES = (
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
)

FALSE_FIELDS = (
    "implementation_ready", "source_packet_implementation_allowed", "source_packet_executable",
    "stage12595_allowed", "stage12613_allowed", "stage12614_allowed", "stage12615_allowed",
    "stage12616_allowed", "stage12617_allowed", "stage12618_allowed", "stage12619_allowed",
    "stage12620_allowed", "stage12621_allowed", "execution_performed", "replay_trustworthy",
    "raw_replay_evidence_present", "trusted_replay_raw_evidence_present",
    "external_bwrap_execution_evidence_present", "alternate_replay_evidence_present",
    "alternate_replay_trustworthy", "vm_runner_implementation_ready", "vm_runner_execution_allowed",
    "vm_runner_evidence_present", "vm_runner_trustworthy", "storage_root_created", "storage_write_performed",
    "host_workspace_mounted_in_guest", "host_volume_mounted_in_guest", "guest_network_enabled",
    "guest_gpu_enabled", "causal_transition_atoms_present", "causal_transition_atoms_materialized",
    "causal_transition_atoms_allowed", "causally_committed_pre_outcome_candidate_set_present",
    "observed_stop_continue_decision_provenance_present", "level3_preflight_allowed",
    "level_3_materialized", "level_3_materialization_allowed", "training_admission_preflight_allowed",
    "training_admission_allowed", "training_admitted", "training_allowed", "training_run_allowed",
    "gpu_allocation_requested", "cuda2_training_allowed", "strict_eval_admitted", "sealed_eval_admitted",
    "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "ranking_allowed", "positive_stop",
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


class SourcePacketStaticReviewError(RuntimeError):
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
        raise SourcePacketStaticReviewError("json_object_required:" + path.name)
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
        "stage12621_allowed": False,
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
            raise SourcePacketStaticReviewError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise SourcePacketStaticReviewError(f"{label}_public_leak:{needle}")


def check_stage12619_truth(record: Mapping[str, Any], label: str) -> None:
    allowed_true = {
        "source_packet_materialized",
        "source_packet_non_executable_materialization_allowed",
        "source_packet_static_review_required",
        "stage12620_static_review_only_allowed",
    }
    unexpected = sorted(key for key, value in record.items() if value is True and key not in allowed_true)
    if unexpected:
        raise SourcePacketStaticReviewError(f"{label}_unexpected_true:" + ",".join(unexpected))
    required_false = (
        "stage12620_allowed", "source_packet_implementation_allowed", "source_packet_executable",
        "vm_runner_implementation_ready", "vm_runner_execution_allowed", "storage_write_performed",
        "execution_performed", "replay_trustworthy", "level_3_materialized", "training_allowed",
    )
    for field in required_false:
        if record.get(field) is not False:
            raise SourcePacketStaticReviewError(f"{label}_required_false_drift:" + field)


def load_stage12619() -> dict[str, Any]:
    summary = read_json(S12619 / "summary.json")
    external = read_json(S12619_EXTERNAL)
    contract = read_json(S12619 / "contract.json")
    pointer = read_json(S12619 / "digest_pointer.json")
    private = read_json(S12619 / "private/minimal_vm_runner_source_packet_materialization.json")
    manifest = read_json(S12619 / "source_packet/manifest.json")
    if summary != external:
        raise SourcePacketStaticReviewError("stage12619_external_summary_mismatch")
    expected = (
        (stable_hash(summary), EXPECTED_STAGE12619_SUMMARY, "summary"),
        (stable_hash(contract), EXPECTED_STAGE12619_CONTRACT, "contract"),
        (stable_hash(pointer), EXPECTED_STAGE12619_POINTER, "pointer"),
        (stable_hash(private), EXPECTED_STAGE12619_PRIVATE, "private"),
        (stable_hash(manifest), EXPECTED_STAGE12619_MANIFEST, "manifest"),
    )
    for actual, expected_hash, label in expected:
        if actual != expected_hash:
            raise SourcePacketStaticReviewError("stage12619_pin_drift:" + label)
    if summary.get("decision") != "NON_EXECUTABLE_SOURCE_PACKET_MATERIALIZED_STATIC_REVIEW_REQUIRED":
        raise SourcePacketStaticReviewError("stage12619_decision_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_stage12619_truth(record, "stage12619_" + label)
    if summary.get("source_packet_file_count") != 12:
        raise SourcePacketStaticReviewError("stage12619_file_count_drift")
    if summary.get("source_packet_manifest_sha256") != EXPECTED_STAGE12619_MANIFEST:
        raise SourcePacketStaticReviewError("stage12619_manifest_hash_drift")
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private, "manifest": manifest}


def source_packet_paths() -> list[Path]:
    return sorted((S12619 / "source_packet").rglob("*.json"))


def review_source_packet() -> dict[str, Any]:
    paths = source_packet_paths()
    relpaths = [path.relative_to(S12619).as_posix() for path in paths]
    expected_relpaths = sorted([
        "source_packet/manifest.json",
        "source_packet/static_review_tests.json",
        *[f"source_packet/module_specs/{name}.json" for name in EXPECTED_MODULES],
    ])
    if relpaths != expected_relpaths:
        raise SourcePacketStaticReviewError("source_packet_file_set_drift")
    file_hashes: dict[str, str] = {}
    forbidden_hits: dict[str, list[str]] = {}
    executable_modes: list[str] = []
    for path in paths:
        relpath = path.relative_to(S12619).as_posix()
        if path.stat().st_mode & 0o111:
            executable_modes.append(relpath)
        payload = read_json(path)
        file_hashes[relpath] = stable_hash(payload)
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        hits = [needle for needle in SOURCE_PACKET_FORBIDDEN_SUBSTRINGS if needle in encoded]
        if hits:
            forbidden_hits[relpath] = hits
    manifest = read_json(S12619 / "source_packet/manifest.json")
    module_names = sorted(spec.get("name") for spec in manifest.get("module_specs", []))
    required_tests = sorted(test.get("name") for test in manifest.get("static_test_specs", []))
    if tuple(module_names) != tuple(sorted(EXPECTED_MODULES)):
        raise SourcePacketStaticReviewError("manifest_module_name_drift")
    required_static_tests = sorted([
        "no_process_invocation_tokens",
        "no_vm_launch_tokens",
        "no_host_or_private_path_leaks_in_public_records",
        "only_non_executable_materialization_gate_true",
        "stage12618_pins_are_current",
    ])
    if required_tests != required_static_tests:
        raise SourcePacketStaticReviewError("manifest_static_test_spec_drift")
    if manifest.get("source_packet_kind") != "static_schema_specs_only":
        raise SourcePacketStaticReviewError("manifest_source_packet_kind_drift")
    if manifest.get("next_required_review") != "stage12620_independent_source_packet_static_review":
        raise SourcePacketStaticReviewError("manifest_next_review_drift")
    if forbidden_hits:
        raise SourcePacketStaticReviewError("source_packet_forbidden_token_hits")
    if executable_modes:
        raise SourcePacketStaticReviewError("source_packet_executable_mode_hits")
    return {
        "record_type": "stage12620_source_packet_static_review_report_v1",
        "reviewed_file_count": len(paths),
        "reviewed_file_hashes": file_hashes,
        "json_only_confirmed": True,
        "non_executable_modes_confirmed": True,
        "forbidden_token_scan_passed": True,
        "manifest_module_specs_confirmed": True,
        "manifest_static_tests_confirmed": True,
        "source_packet_kind_confirmed": True,
    }


def build_review_packet(stage12619: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    report = review_source_packet()
    report_hash = stable_hash(report)
    private = {
        "record_type": "stage12620_private_independent_source_packet_static_review_v1",
        **no_claim_fields(),
        "stage12619_summary_sha256": EXPECTED_STAGE12619_SUMMARY,
        "stage12619_private_materialization_sha256": EXPECTED_STAGE12619_PRIVATE,
        "source_decision": stage12619["summary"]["decision"],
        "gate_scope": EXPECTED_GATE_SCOPE,
        "independent_source_packet_static_review_passed": True,
        "stage12620_static_review_only_allowed": True,
        "source_packet_json_only_confirmed": True,
        "source_packet_non_executable_confirmed": True,
        "source_packet_forbidden_token_scan_passed": True,
        "source_packet_public_leak_scan_passed": True,
        "source_packet_static_review_report_sha256": report_hash,
        "source_packet_static_review_report": report,
        "stage12621_source_implementation_authorization_review_only_allowed": True,
        "decision": "INDEPENDENT_SOURCE_PACKET_STATIC_REVIEW_PASSED_IMPLEMENTATION_AUTHORIZATION_STILL_BLOCKED",
    }
    contract = {
        "record_type": "stage12620_public_independent_source_packet_static_review_v1",
        **no_claim_fields(),
        "stage12619_summary_sha256": EXPECTED_STAGE12619_SUMMARY,
        "stage12619_contract_sha256": EXPECTED_STAGE12619_CONTRACT,
        "stage12619_private_materialization_sha256": EXPECTED_STAGE12619_PRIVATE,
        "source_packet_manifest_sha256": EXPECTED_STAGE12619_MANIFEST,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "independent_source_packet_static_review_passed": True,
        "stage12620_static_review_only_allowed": True,
        "source_packet_json_only_confirmed": True,
        "source_packet_non_executable_confirmed": True,
        "source_packet_forbidden_token_scan_passed": True,
        "source_packet_public_leak_scan_passed": True,
        "source_packet_static_review_report_sha256": report_hash,
        "private_source_packet_static_review_sha256": stable_hash(private),
        "stage12621_source_implementation_authorization_review_only_allowed": True,
        "claim_boundary": {
            "source_packet_review": "passed_static_json_only_review",
            "implementation": "not_authorized",
            "storage_write": "not_authorized",
            "vm_launch": "not_authorized",
            "replay": "not_authorized",
            "training": "not_authorized",
        },
    }
    summary = {
        "record_type": "stage12620_public_independent_source_packet_static_review_summary_v1",
        **no_claim_fields(),
        "stage": STAGE,
        "decision": "INDEPENDENT_SOURCE_PACKET_STATIC_REVIEW_PASSED_IMPLEMENTATION_AUTHORIZATION_STILL_BLOCKED",
        "stage12619_summary_sha256": EXPECTED_STAGE12619_SUMMARY,
        "source_packet_manifest_sha256": EXPECTED_STAGE12619_MANIFEST,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "independent_source_packet_static_review_passed": True,
        "stage12620_static_review_only_allowed": True,
        "source_packet_json_only_confirmed": True,
        "source_packet_non_executable_confirmed": True,
        "source_packet_forbidden_token_scan_passed": True,
        "source_packet_public_leak_scan_passed": True,
        "source_packet_static_review_report_sha256": report_hash,
        "private_source_packet_static_review_sha256": stable_hash(private),
        "stage12621_source_implementation_authorization_review_only_allowed": True,
        "downstream_blockers": [
            "vm_runner_implementation_authorization_absent",
            "vm_runner_source_absent",
            "independent_implemented_source_review_absent",
            "vm_runner_execution_gate_absent",
            "private_scratch_root_not_created",
            "trusted_replay_raw_evidence_absent",
            "causal_transition_atoms_absent",
            "level3_materialization_forbidden",
            "training_admission_forbidden",
        ],
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12620_" + label)
        assert_public_sanitized(record, "stage12620_" + label)
    check_false(private, "stage12620_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12619 = load_stage12619()
    summary, contract, private = build_review_packet(stage12619)
    pointer = {
        "record_type": "stage12620_public_private_independent_source_packet_static_review_pointer_v1",
        **no_claim_fields(),
        "stage12619_summary_sha256": EXPECTED_STAGE12619_SUMMARY,
        "contract_sha256": stable_hash(contract),
        "private_source_packet_static_review_sha256": stable_hash(private),
        "independent_source_packet_static_review_passed": True,
        "stage12620_static_review_only_allowed": True,
        "source_packet_json_only_confirmed": True,
        "source_packet_non_executable_confirmed": True,
        "source_packet_forbidden_token_scan_passed": True,
        "source_packet_public_leak_scan_passed": True,
        "stage12621_source_implementation_authorization_review_only_allowed": True,
    }
    check_false(pointer, "stage12620_pointer")
    assert_public_sanitized(pointer, "stage12620_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/independent_source_packet_static_review.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))

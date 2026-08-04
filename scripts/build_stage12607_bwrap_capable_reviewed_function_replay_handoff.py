#!/usr/bin/env python3
"""Build Stage12607 bwrap-capable reviewed-function replay handoff.

Stage12606 proved the current host cannot run the required inner bwrap replay.
This stage packages a pinned, private invocation handoff for a future bwrap-
capable environment. It does not invoke replay, does not call the Stage12602
runner CLI, does not create raw evidence, and does not advance Level-3 or
training/eval admission.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12607_bwrap_capable_reviewed_function_replay_handoff"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
RUNNER = ROOT / "scripts/run_stage12602_clean_manual_replay_executor.py"
S12604 = ROOT / "runs/local/artifacts/stage12604_reviewed_execution_request_materials"
S12605 = ROOT / "runs/local/artifacts/stage12605_reviewed_execution_gate"
S12606 = ROOT / "runs/local/artifacts/stage12606_reviewed_function_replay_execution_blocker"
S12606_EXTERNAL = ROOT / "runs/summaries/stage12606_reviewed_function_replay_execution_blocker.json"
EXPECTED_STAGE12602_RUNNER = "d1ded97530116a515fdf41db5fd5ab42ff725a14ef570c6d6de18ef93c286e19"
EXPECTED_STAGE12604_COMMAND_MANIFEST = "92abb4b6f1d6d922c3dd90a93a96cde696e121cfc730f47cec170000404e6911"
EXPECTED_STAGE12604_PRIVATE_REQUEST = "d2429452c290b517a5858892032fded88fd964e3057e98fc8c64280083081b99"
EXPECTED_STAGE12605_PRIVATE_GATE = "b20f07723310ee334dd5c80535f6a936c31cd7232eb687fa8317f35540d5eea6"
EXPECTED_STAGE12606_SUMMARY = "ac639d976e073fe3f0412964cd85a7f3e5e80289c01bc3a9b6a9b79678a4227a"
EXPECTED_STAGE12606_CONTRACT = "9bbe58e359e5676796c45e007e0a6779635c9b8908d5ef6863519b4817afb27c"
EXPECTED_STAGE12606_POINTER = "c009c09c25df57b3fa0df6896fb9a6bc1b2f9be5e56a99742cf43dce8544e8a6"
EXPECTED_STAGE12606_PRIVATE = "831a0cbe75a033a0ea67fa5560a1321e42b69ae0b45bcc225c0f8f5db6b5f8d3"
EXPECTED_GATE_SCOPE = "reviewed_stage12602_execute_reviewed_slot_function_only"
REPOSITORY_ROOTS_BY_BINDING = {
    "9debfb351017b950db9830d7c74832de54fca66bd6cb2d13b7abf834e580688b": "/arxiv/repositories/pytest",
    "890bc20899934d6a532842e0861e544c2e6f55f646a982b204a922eead39820a": "/arxiv/repositories/networkx",
}
FALSE_FIELDS = (
    "implementation_ready", "stage12595_allowed", "execution_performed", "replay_trustworthy",
    "level_3_materialized", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted",
    "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "training_allowed",
    "ranking_allowed", "positive_stop", "raw_replay_evidence_present",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "selector", "raw_stream", "stdout.raw", "stderr.raw", "before_commit_oid",
    "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
    "slot_1.patch", "slot_2.patch", "future_evidence", "repository_root", "patch_path",
)


class HandoffError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def stable_hash(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise HandoffError("json_object_required:" + path.name)
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def no_replay_claim_fields() -> dict[str, Any]:
    return {
        "implementation_ready": False,
        "stage12595_allowed": False,
        "execution_performed": False,
        "replay_trustworthy": False,
        "level_3_materialized": False,
        "training_admitted": False,
        "strict_eval_admitted": False,
        "sealed_eval_admitted": False,
        "strict_eval_eligible": False,
        "sealed_eval_eligible": False,
        "admission_allowed": False,
        "training_allowed": False,
        "ranking_allowed": False,
        "positive_stop": False,
        "raw_replay_evidence_present": False,
    }


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if record.get(field) is not False:
            raise HandoffError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise HandoffError(f"{label}_public_leak:{needle}")


def load_stage12606() -> dict[str, Any]:
    summary = read_json(S12606 / "summary.json")
    external = read_json(S12606_EXTERNAL)
    contract = read_json(S12606 / "contract.json")
    pointer = read_json(S12606 / "digest_pointer.json")
    private = read_json(S12606 / "private/reviewed_function_replay_execution_blocker.json")
    if summary != external:
        raise HandoffError("stage12606_external_summary_mismatch")
    expected = (
        (stable_hash(summary), EXPECTED_STAGE12606_SUMMARY, "summary"),
        (stable_hash(contract), EXPECTED_STAGE12606_CONTRACT, "contract"),
        (stable_hash(pointer), EXPECTED_STAGE12606_POINTER, "pointer"),
        (stable_hash(private), EXPECTED_STAGE12606_PRIVATE, "private"),
    )
    for actual, expected_hash, label in expected:
        if actual != expected_hash:
            raise HandoffError("stage12606_pin_drift:" + label)
    if summary.get("decision") != "BLOCKED_BWRAP_LOOPBACK_UNAVAILABLE":
        raise HandoffError("stage12606_decision_drift")
    if private.get("bwrap_probe", {}).get("blocker") != "BWRAP_LOOPBACK_UNAVAILABLE":
        raise HandoffError("stage12606_private_probe_drift")
    if "Failed RTM_NEWADDR" not in private.get("bwrap_probe", {}).get("stderr_text", ""):
        raise HandoffError("stage12606_loopback_evidence_missing")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        if record.get("gate_scope") != EXPECTED_GATE_SCOPE and label in ("summary", "contract", "private"):
            raise HandoffError("stage12606_scope_drift:" + label)
        if record.get("execute_reviewed_slot_called") is not False:
            raise HandoffError("stage12606_unexpected_execution:" + label)
        check_false(record, "stage12606_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private}


def load_private_inputs() -> dict[str, Any]:
    command_manifest = read_json(S12604 / "private/executor_command_manifest.json")
    private_request = read_json(S12604 / "private/reviewed_execution_request_materials.json")
    private_gate = read_json(S12605 / "private/reviewed_execution_gate.json")
    if sha256_file(RUNNER) != EXPECTED_STAGE12602_RUNNER:
        raise HandoffError("stage12602_runner_pin_drift")
    if stable_hash(command_manifest) != EXPECTED_STAGE12604_COMMAND_MANIFEST:
        raise HandoffError("stage12604_command_manifest_pin_drift")
    if stable_hash(private_request) != EXPECTED_STAGE12604_PRIVATE_REQUEST:
        raise HandoffError("stage12604_private_request_pin_drift")
    if stable_hash(private_gate) != EXPECTED_STAGE12605_PRIVATE_GATE:
        raise HandoffError("stage12605_private_gate_pin_drift")
    if private_gate.get("gate_scope") != EXPECTED_GATE_SCOPE:
        raise HandoffError("stage12605_private_gate_scope_drift")
    if private_gate.get("cli_execute_entrypoint_enabled") is not False:
        raise HandoffError("stage12605_cli_drift")
    if private_gate.get("reviewed_function_execute_path_enabled") is not True:
        raise HandoffError("stage12605_reviewed_function_path_missing")
    if command_manifest.get("slot_count") != 2 or len(command_manifest.get("slots", [])) != 2:
        raise HandoffError("stage12604_slot_count_drift")
    for label, record in (("private_request", private_request), ("private_gate", private_gate)):
        check_false(record, "stage12607_input_" + label)
    return {"command_manifest": command_manifest, "private_request": private_request, "private_gate": private_gate}


def build_private_invocations(command_manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    invocations = []
    for slot in command_manifest["slots"]:
        binding = str(slot["binding_payload_sha256"])
        repository_root = REPOSITORY_ROOTS_BY_BINDING.get(binding)
        if repository_root is None:
            raise HandoffError("repository_root_for_binding_missing")
        patch_name = f"slot_{slot['slot_ordinal']}.patch"
        patch_path = S12604 / "private/patches" / patch_name
        if not patch_path.is_file():
            raise HandoffError("stage12604_patch_file_missing:" + patch_name)
        if sha256_file(patch_path) != slot.get("production_patch_sha256"):
            raise HandoffError("stage12604_patch_file_pin_drift:" + patch_name)
        invocations.append({
            "slot_ordinal": slot["slot_ordinal"],
            "binding_payload_sha256": binding,
            "repository_root": repository_root,
            "repository_root_sha256": sha256_bytes(repository_root.encode("utf-8")),
            "runner_module_path": str(RUNNER),
            "reviewed_function_name": "execute_reviewed_slot",
            "cli_execute_entrypoint_forbidden": True,
            "slot_source": "stage12604_private_executor_command_manifest",
            "production_path": slot["production_path"],
            "production_patch_sha256": slot["production_patch_sha256"],
            "patch_path": str(patch_path),
            "patch_file_sha256": sha256_file(patch_path),
            "evidence_root_required_empty_before_run": True,
            "future_private_evidence_root": str(ROOT / "runs/local/private/stage12608_bwrap_capable_reviewed_function_replay_execution"),
            "stage12605_private_gate_sha256": EXPECTED_STAGE12605_PRIVATE_GATE,
        })
    return invocations


def build_handoff_packet(stage12606: Mapping[str, Any], inputs: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    invocations = build_private_invocations(inputs["command_manifest"])
    private = {
        "record_type": "stage12607_private_bwrap_capable_reviewed_function_replay_handoff_v1",
        "stage12606_summary_sha256": EXPECTED_STAGE12606_SUMMARY,
        "stage12606_private_blocker_sha256": EXPECTED_STAGE12606_PRIVATE,
        "stage12602_runner_sha256": EXPECTED_STAGE12602_RUNNER,
        "stage12604_command_manifest_sha256": EXPECTED_STAGE12604_COMMAND_MANIFEST,
        "stage12604_private_request_sha256": EXPECTED_STAGE12604_PRIVATE_REQUEST,
        "stage12605_private_gate_sha256": EXPECTED_STAGE12605_PRIVATE_GATE,
        "source_environment_blocker": stage12606["summary"]["environment_blocker"],
        "handoff_ready_for_bwrap_capable_environment": True,
        "bwrap_capable_environment_required": True,
        "reviewed_function_execute_path_enabled": True,
        "cli_execute_entrypoint_enabled": False,
        "cli_execute_entrypoint_forbidden": True,
        "reviewed_function_name": "execute_reviewed_slot",
        "gate_scope": EXPECTED_GATE_SCOPE,
        "slot_count": len(invocations),
        "private_slot_invocations": invocations,
        "execution_handoff_runs_replay": False,
        "independent_execution_artifact_review_required_after_future_run": True,
        **no_replay_claim_fields(),
    }
    contract = {
        "record_type": "stage12607_public_bwrap_capable_reviewed_function_replay_handoff_contract_v1",
        "stage12606_summary_sha256": EXPECTED_STAGE12606_SUMMARY,
        "stage12602_runner_sha256": EXPECTED_STAGE12602_RUNNER,
        "stage12604_command_manifest_sha256": EXPECTED_STAGE12604_COMMAND_MANIFEST,
        "stage12605_private_gate_sha256": EXPECTED_STAGE12605_PRIVATE_GATE,
        "source_environment_blocker": stage12606["summary"]["environment_blocker"],
        "handoff_ready_for_bwrap_capable_environment": True,
        "bwrap_capable_environment_required": True,
        "reviewed_function_execute_path_enabled": True,
        "cli_execute_entrypoint_enabled": False,
        "cli_execute_entrypoint_forbidden": True,
        "reviewed_function_name": "execute_reviewed_slot",
        "gate_scope": EXPECTED_GATE_SCOPE,
        "slot_count": len(invocations),
        "private_handoff_sha256": stable_hash(private),
        "execution_handoff_runs_replay": False,
        "independent_execution_artifact_review_required_after_future_run": True,
        "claim_boundary": {
            "future_run_path": "import_reviewed_stage12602_function_only",
            "cli_execute": "forbidden",
            "replay_success_claim": "forbidden_until_future_private_raw_artifacts_exist_and_are_independently_reviewed",
            "level3_claim": "forbidden_until_causal_candidate_and_stop_continue_provenance_exist",
            "training_admission": "separate_future_gate_required",
        },
        **no_replay_claim_fields(),
    }
    summary = {
        "record_type": "stage12607_public_bwrap_capable_reviewed_function_replay_handoff_summary_v1",
        "stage": STAGE,
        "decision": "BWRAP_CAPABLE_REVIEWED_FUNCTION_REPLAY_HANDOFF_READY_EXECUTION_NOT_RUN",
        "stage12606_summary_sha256": EXPECTED_STAGE12606_SUMMARY,
        "source_environment_blocker": stage12606["summary"]["environment_blocker"],
        "handoff_ready_for_bwrap_capable_environment": True,
        "bwrap_capable_environment_required": True,
        "reviewed_function_execute_path_enabled": True,
        "cli_execute_entrypoint_enabled": False,
        "cli_execute_entrypoint_forbidden": True,
        "reviewed_function_name": "execute_reviewed_slot",
        "gate_scope": EXPECTED_GATE_SCOPE,
        "slot_count": len(invocations),
        "private_handoff_sha256": stable_hash(private),
        "execution_handoff_runs_replay": False,
        "independent_execution_artifact_review_required_after_future_run": True,
        "stage12608_allowed": False,
        "stage12608_bwrap_capable_function_execution_review_allowed": True,
        "downstream_blockers": [
            "bwrap_capable_environment_not_available_in_current_host",
            "reviewed_function_replay_not_executed",
            "trusted_replay_raw_evidence_absent",
            "independent_execution_artifact_review_absent",
            "causally_committed_pre_outcome_candidate_set_absent",
            "observed_stop_continue_decision_absent",
            "level3_materialization_forbidden",
            "training_admission_forbidden",
            "strict_eval_admission_forbidden",
            "sealed_eval_admission_forbidden",
        ],
        **no_replay_claim_fields(),
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12607_" + label)
        assert_public_sanitized(record, "stage12607_" + label)
    check_false(private, "stage12607_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12606 = load_stage12606()
    inputs = load_private_inputs()
    summary, contract, private = build_handoff_packet(stage12606, inputs)
    pointer = {
        "record_type": "stage12607_public_private_bwrap_capable_reviewed_function_replay_handoff_pointer_v1",
        "stage12606_summary_sha256": EXPECTED_STAGE12606_SUMMARY,
        "private_handoff_sha256": stable_hash(private),
        "contract_sha256": stable_hash(contract),
        "handoff_ready_for_bwrap_capable_environment": True,
        "bwrap_capable_environment_required": True,
        "reviewed_function_execute_path_enabled": True,
        "cli_execute_entrypoint_enabled": False,
        "cli_execute_entrypoint_forbidden": True,
        "execution_handoff_runs_replay": False,
        "execution_performed": False,
        "raw_replay_evidence_present": False,
        "replay_trustworthy": False,
        "level_3_materialized": False,
        "training_admitted": False,
        "strict_eval_admitted": False,
        "sealed_eval_admitted": False,
        "stage12608_allowed": False,
        "stage12608_bwrap_capable_function_execution_review_allowed": True,
        **no_replay_claim_fields(),
    }
    check_false(pointer, "stage12607_pointer")
    assert_public_sanitized(pointer, "stage12607_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/bwrap_capable_reviewed_function_replay_handoff.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))

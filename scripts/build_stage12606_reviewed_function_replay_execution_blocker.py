#!/usr/bin/env python3
"""Build Stage12606 reviewed-function replay execution blocker.

Stage12605 authorizes only the reviewed Stage12602 execute_reviewed_slot
function path. This stage checks that narrow gate and records that the current
environment cannot run the required inner bwrap namespace, so no replay is run
and no raw replay evidence is emitted.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12606_reviewed_function_replay_execution_blocker"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12605 = ROOT / "runs/local/artifacts/stage12605_reviewed_execution_gate"
S12605_EXTERNAL = ROOT / "runs/summaries/stage12605_reviewed_execution_gate.json"
EXPECTED_STAGE12605_SUMMARY = "099fef71f90d879f765102bed4ad26157495cfdf66620033777f248cbf8d0a02"
EXPECTED_STAGE12605_CONTRACT = "6e65785a5a76042f0ddc7a8dac1366f4e0b3f68d9317da53a7520551ac21e3c6"
EXPECTED_STAGE12605_POINTER = "e791b612c6d10a3377ca134278cd384ccc95c06dbbcc3c4ddbcf2969fdb25af1"
EXPECTED_STAGE12605_PRIVATE_GATE = "b20f07723310ee334dd5c80535f6a936c31cd7232eb687fa8317f35540d5eea6"
EXPECTED_GATE_SCOPE = "reviewed_stage12602_execute_reviewed_slot_function_only"
FALSE_FIELDS = (
    "implementation_ready", "stage12595_allowed", "execution_performed", "replay_trustworthy",
    "level_3_materialized", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted",
    "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "training_allowed",
    "ranking_allowed", "positive_stop", "raw_replay_evidence_present",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "selector", "raw_stream", "stdout.raw", "stderr.raw", "before_commit_oid",
    "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
    "slot_1.patch", "slot_2.patch", "snapshot",
)
BWRAP_PROBE_COMMAND = (
    "bwrap", "--unshare-all", "--die-with-parent", "--new-session", "--clearenv",
    "--ro-bind", "/usr", "/usr",
    "--ro-bind", "/bin", "/bin",
    "--ro-bind", "/lib", "/lib",
    "--ro-bind", "/lib64", "/lib64",
    "--dev", "/dev",
    "--proc", "/proc",
    "--tmpfs", "/tmp",
    "/bin/true",
)


class BlockerError(RuntimeError):
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
        raise BlockerError("json_object_required:" + path.name)
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
            raise BlockerError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise BlockerError(f"{label}_public_leak:{needle}")


def load_stage12605() -> dict[str, Any]:
    summary = read_json(S12605 / "summary.json")
    external = read_json(S12605_EXTERNAL)
    contract = read_json(S12605 / "contract.json")
    pointer = read_json(S12605 / "digest_pointer.json")
    private_gate = read_json(S12605 / "private/reviewed_execution_gate.json")
    if summary != external:
        raise BlockerError("stage12605_external_summary_mismatch")
    expected = (
        (stable_hash(summary), EXPECTED_STAGE12605_SUMMARY, "summary"),
        (stable_hash(contract), EXPECTED_STAGE12605_CONTRACT, "contract"),
        (stable_hash(pointer), EXPECTED_STAGE12605_POINTER, "pointer"),
        (stable_hash(private_gate), EXPECTED_STAGE12605_PRIVATE_GATE, "private_gate"),
    )
    for actual, expected_hash, label in expected:
        if actual != expected_hash:
            raise BlockerError("stage12605_pin_drift:" + label)
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private_gate", private_gate)):
        if record.get("gate_scope") != EXPECTED_GATE_SCOPE:
            raise BlockerError("stage12605_scope_drift:" + label)
        if record.get("execution_gate_granted") is not True:
            raise BlockerError("stage12605_gate_missing:" + label)
        if record.get("reviewed_function_execute_path_enabled") is not True:
            raise BlockerError("stage12605_reviewed_function_path_missing:" + label)
        if record.get("cli_execute_entrypoint_enabled") is not False:
            raise BlockerError("stage12605_cli_drift:" + label)
        check_false(record, "stage12605_" + label)
    if summary.get("stage12606_allowed") is not False or pointer.get("stage12606_allowed") is not False:
        raise BlockerError("stage12605_broad_stage12606_drift")
    if summary.get("stage12606_reviewed_function_replay_allowed") is not True:
        raise BlockerError("stage12605_scoped_stage12606_missing")
    if pointer.get("stage12606_reviewed_function_replay_allowed") is not True:
        raise BlockerError("stage12605_pointer_scoped_stage12606_missing")
    return {"summary": summary, "contract": contract, "pointer": pointer, "private_gate": private_gate}


def run_bwrap_probe(command: Sequence[str] = BWRAP_PROBE_COMMAND) -> dict[str, Any]:
    result = subprocess.run(list(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=30)
    stderr_text = result.stderr.decode("utf-8", errors="replace")
    stdout_text = result.stdout.decode("utf-8", errors="replace")
    if result.returncode == 0:
        blocker = "NONE"
    elif "Failed RTM_NEWADDR" in stderr_text and "Operation not permitted" in stderr_text:
        blocker = "BWRAP_LOOPBACK_UNAVAILABLE"
    else:
        blocker = "BWRAP_CAPABILITY_UNAVAILABLE"
    return {
        "command_name": command[0],
        "returncode": result.returncode,
        "stdout_sha256": sha256_bytes(result.stdout),
        "stderr_sha256": sha256_bytes(result.stderr),
        "stdout_text": stdout_text,
        "stderr_text": stderr_text,
        "blocker": blocker,
    }


def build_blocker_packet(stage12605: Mapping[str, Any], probe: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if probe.get("returncode") == 0:
        raise BlockerError("bwrap_probe_unexpectedly_available")
    decision = "BLOCKED_" + str(probe["blocker"])
    private = {
        "record_type": "stage12606_private_reviewed_function_replay_execution_blocker_v1",
        "stage12605_summary_sha256": EXPECTED_STAGE12605_SUMMARY,
        "stage12605_private_gate_sha256": EXPECTED_STAGE12605_PRIVATE_GATE,
        "reviewed_function_execute_path_enabled": True,
        "cli_execute_entrypoint_enabled": False,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "stage12606_allowed": False,
        "stage12606_reviewed_function_replay_allowed": True,
        "attempted_operation": "minimal_bwrap_capability_probe_only",
        "execute_reviewed_slot_called": False,
        "replay_slot_count_attempted": 0,
        "bwrap_probe": dict(probe),
        "decision": decision,
        **no_replay_claim_fields(),
    }
    contract = {
        "record_type": "stage12606_public_reviewed_function_replay_execution_blocker_contract_v1",
        "stage12605_summary_sha256": EXPECTED_STAGE12605_SUMMARY,
        "stage12605_contract_sha256": EXPECTED_STAGE12605_CONTRACT,
        "reviewed_function_execute_path_enabled": True,
        "cli_execute_entrypoint_enabled": False,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "stage12606_allowed": False,
        "stage12606_reviewed_function_replay_allowed": True,
        "attempted_operation": "minimal_bwrap_capability_probe_only",
        "execute_reviewed_slot_called": False,
        "replay_slot_count_attempted": 0,
        "environment_blocker": probe["blocker"],
        "private_probe_sha256": stable_hash(private["bwrap_probe"]),
        "claim_boundary": {
            "replay_success_claim": "forbidden_until_reviewed_function_completes_and_raw_artifacts_exist",
            "level3_claim": "forbidden_until_causal_candidate_and_stop_continue_provenance_exist",
            "training_admission": "separate_future_gate_required",
        },
        **no_replay_claim_fields(),
    }
    summary = {
        "record_type": "stage12606_public_reviewed_function_replay_execution_blocker_summary_v1",
        "stage": STAGE,
        "decision": decision,
        "stage12605_summary_sha256": EXPECTED_STAGE12605_SUMMARY,
        "reviewed_function_execute_path_enabled": True,
        "cli_execute_entrypoint_enabled": False,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "stage12606_allowed": False,
        "stage12606_reviewed_function_replay_allowed": True,
        "attempted_operation": "minimal_bwrap_capability_probe_only",
        "execute_reviewed_slot_called": False,
        "replay_slot_count_attempted": 0,
        "environment_blocker": probe["blocker"],
        "bwrap_probe_returncode": probe["returncode"],
        "private_probe_sha256": stable_hash(private["bwrap_probe"]),
        "downstream_blockers": [
            "reviewed_function_replay_not_executed",
            "trusted_replay_raw_evidence_absent",
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
        check_false(record, "stage12606_" + label)
        assert_public_sanitized(record, "stage12606_" + label)
    check_false(private, "stage12606_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12605 = load_stage12605()
    probe = run_bwrap_probe()
    summary, contract, private = build_blocker_packet(stage12605, probe)
    pointer = {
        "record_type": "stage12606_public_private_reviewed_function_replay_execution_blocker_pointer_v1",
        "stage12605_summary_sha256": EXPECTED_STAGE12605_SUMMARY,
        "private_blocker_sha256": stable_hash(private),
        "contract_sha256": stable_hash(contract),
        "stage12606_allowed": False,
        "stage12606_reviewed_function_replay_allowed": True,
        "execute_reviewed_slot_called": False,
        "execution_performed": False,
        "raw_replay_evidence_present": False,
        "replay_trustworthy": False,
        "level_3_materialized": False,
        "training_admitted": False,
        "strict_eval_admitted": False,
        "sealed_eval_admitted": False,
        "environment_blocker": probe["blocker"],
        **no_replay_claim_fields(),
    }
    check_false(pointer, "stage12606_pointer")
    assert_public_sanitized(pointer, "stage12606_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/reviewed_function_replay_execution_blocker.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))

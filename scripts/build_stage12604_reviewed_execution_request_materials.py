#!/usr/bin/env python3
"""Build Stage12604 reviewed execution request materials.

This stage prepares private replay execution request materials for the reviewed
Stage12602 clean runner: exact production patch files and a command manifest. It
does not grant the execution gate, enable --execute, run replay, publish raw
replay evidence, materialize Level-3, or admit training/eval.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12604_reviewed_execution_request_materials"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
RUNNER = ROOT / "scripts/run_stage12602_clean_manual_replay_executor.py"
S12593 = ROOT / "runs/local/artifacts/stage12593_private_static_verifier_binding_sidecar"
S12594 = ROOT / "runs/local/artifacts/stage12594_trusted_external_causal_replay_runner_preflight"
S12595 = ROOT / "runs/local/artifacts/stage12595_trusted_replay_execution_handoff"
S12603 = ROOT / "runs/local/artifacts/stage12603_independent_clean_source_review"
S12603_EXTERNAL = ROOT / "runs/summaries/stage12603_independent_clean_source_review.json"
EXPECTED_STAGE12602_RUNNER = "d1ded97530116a515fdf41db5fd5ab42ff725a14ef570c6d6de18ef93c286e19"
EXPECTED_STAGE12603_SUMMARY = "77f8a4892c177e4f6b2a5d9bfa24ce441f2bfb937c3c2e698b3d72f6a6ecc1ce"
EXPECTED_STAGE12603_CONTRACT = "32b66f3ea0dec59522bc6bb1fb4ee27cd88df517b937928d703b20591894ac01"
EXPECTED_STAGE12603_POINTER = "b0100c6fad6b795fd0103c2591db21a1fb0948f8d2c18f7daedb32bd1594e656"
EXPECTED_STAGE12603_PRIVATE = "c8e36fa9fa53ea7d9c95930829fcb16e11315facb246c13cf43bbd601a3c0ad7"
EXPECTED_STAGE12595_SLOTS = "8ddfdfb0872c8cb74a46f0041801bced7e674228d74af98b30ce7631afebe3a0"
FALSE_FIELDS = (
    "implementation_ready", "stage12595_allowed", "authorizes_execution", "execution_allowed",
    "execution_performed", "replay_trustworthy", "level_3_materialized", "training_admitted",
    "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
    "admission_allowed", "training_allowed", "ranking_allowed", "positive_stop", "stage12605_allowed",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "selector", "raw_stream", "stdout.raw", "stderr.raw", "before_commit_oid",
    "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
    "slot_1.patch", "slot_2.patch",
)


class GateError(RuntimeError):
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
        raise GateError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise GateError(f"jsonl_object_required:{path.name}:{number}")
        rows.append(value)
    return rows


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def write_json(path: Path, value: Any) -> None:
    write_bytes(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n")


def no_claim_fields() -> dict[str, Any]:
    return {
        "implementation_ready": False,
        "stage12595_allowed": False,
        "authorizes_execution": False,
        "execution_allowed": False,
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
    }


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise GateError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise GateError(f"{label}_public_leak:{needle}")


def load_stage12603() -> dict[str, Any]:
    summary = read_json(S12603 / "summary.json")
    external = read_json(S12603_EXTERNAL)
    contract = read_json(S12603 / "contract.json")
    pointer = read_json(S12603 / "digest_pointer.json")
    private = read_json(S12603 / "private/independent_clean_source_review.json")
    if summary != external:
        raise GateError("stage12603_external_summary_mismatch")
    expected = (
        (stable_hash(summary), EXPECTED_STAGE12603_SUMMARY, "summary"),
        (stable_hash(contract), EXPECTED_STAGE12603_CONTRACT, "contract"),
        (stable_hash(pointer), EXPECTED_STAGE12603_POINTER, "pointer"),
        (stable_hash(private), EXPECTED_STAGE12603_PRIVATE, "private"),
    )
    for actual, expected_hash, label in expected:
        if actual != expected_hash:
            raise GateError("stage12603_pin_drift:" + label)
    if summary.get("decision") != "BLOCKED_EXECUTION_GATE_REQUIRED":
        raise GateError("stage12603_decision_drift")
    if summary.get("reviewed_execution_capable_source_present") is not True:
        raise GateError("stage12603_reviewed_source_missing")
    if summary.get("independent_execution_capable_source_review_passed") is not True:
        raise GateError("stage12603_review_pass_missing")
    if summary.get("execute_path_enabled") is not False or summary.get("execution_gate_granted") is not False:
        raise GateError("stage12603_execution_gate_drift")
    if summary.get("execution_request_ready_count") != 0:
        raise GateError("stage12603_request_count_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_false(record, "stage12603_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private}


def load_runner():
    if sha256_file(RUNNER) != EXPECTED_STAGE12602_RUNNER:
        raise GateError("stage12602_runner_pin_drift")
    spec = importlib.util.spec_from_file_location("stage12602_runner", RUNNER)
    if spec is None or spec.loader is None:
        raise GateError("stage12602_runner_import_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_slots() -> list[dict[str, Any]]:
    slots = read_jsonl(S12595 / "private/manual_replay_execution_slots.jsonl")
    if stable_hash(slots) != EXPECTED_STAGE12595_SLOTS:
        raise GateError("stage12595_slots_pin_drift")
    if len(slots) != 2:
        raise GateError("stage12595_slot_count_drift")
    for ordinal, slot in enumerate(slots, 1):
        if slot.get("slot_ordinal") != ordinal:
            raise GateError("stage12595_slot_order_drift")
        check_false(slot, f"stage12595_slot_{ordinal}")
    return slots


def load_binding_payloads() -> dict[str, dict[str, Any]]:
    rows = read_jsonl(S12593 / "private/verifier_binding_sidecar.jsonl")
    payloads: dict[str, dict[str, Any]] = {}
    for row in rows:
        check_false(row, "stage12593_binding_row")
        payloads[row["binding_payload_sha256"]] = row["binding_payload"]
    return payloads


def git_diff_patch(repo_path: str, before_commit: str, after_commit: str, production_path: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", repo_path, "diff", before_commit, after_commit, "--", production_path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode != 0:
        raise GateError("git_diff_patch_failed")
    return result.stdout


def materialize_patch_files(patch_root: Path) -> list[dict[str, Any]]:
    slots = load_slots()
    payloads = load_binding_payloads()
    records: list[dict[str, Any]] = []
    for slot in slots:
        payload = payloads.get(slot["binding_payload_sha256"])
        if not payload:
            raise GateError("binding_payload_missing_for_slot")
        repo = payload["repository"]
        patch_meta = payload["production_patch"]
        if patch_meta.get("sha256") != slot.get("production_patch_sha256"):
            raise GateError("production_patch_digest_pin_mismatch")
        if patch_meta.get("path") != slot.get("production_path"):
            raise GateError("production_patch_path_pin_mismatch")
        patch_bytes = git_diff_patch(repo["path"], slot["before_commit_oid"], slot["after_commit_oid"], slot["production_path"])
        actual = sha256_bytes(patch_bytes)
        if actual != slot["production_patch_sha256"]:
            raise GateError("materialized_patch_digest_mismatch")
        if len(patch_bytes) != patch_meta.get("byte_count"):
            raise GateError("materialized_patch_byte_count_mismatch")
        patch_path = patch_root / f"slot_{slot['slot_ordinal']}.patch"
        write_bytes(patch_path, patch_bytes)
        records.append({
            "record_type": "stage12604_private_patch_material_record_v1",
            "slot_ordinal": slot["slot_ordinal"],
            "binding_payload_sha256": slot["binding_payload_sha256"],
            "patch_file": patch_path.name,
            "patch_sha256": actual,
            "patch_byte_count": len(patch_bytes),
            "production_path": slot["production_path"],
            "before_commit_oid": slot["before_commit_oid"],
            "after_commit_oid": slot["after_commit_oid"],
            **no_claim_fields(),
        })
    return records


def build_private_materials(out: Path = OUT) -> tuple[dict[str, Any], dict[str, Any]]:
    runner = load_runner()
    patch_root = out / "private/patches"
    evidence_root = out / "private/future_evidence_root"
    patch_records = materialize_patch_files(patch_root)
    stage12594 = runner.load_stage12594_snapshot_contract()
    stage12595 = runner.load_stage12595_manual_slots()
    command_manifest = runner.build_execution_command_manifest(stage12594, stage12595, patch_root, evidence_root)
    if command_manifest.get("slot_count") != 2:
        raise GateError("command_manifest_slot_count_drift")
    for record in patch_records:
        check_false(record, f"stage12604_patch_record_{record['slot_ordinal']}")
    write_json(out / "private/patch_material_records.json", {"records": patch_records, **no_claim_fields()})
    write_json(out / "private/executor_command_manifest.json", command_manifest)
    private_request = {
        "record_type": "stage12604_private_reviewed_execution_request_materials_v1",
        "stage12602_runner_sha256": EXPECTED_STAGE12602_RUNNER,
        "stage12603_summary_sha256": EXPECTED_STAGE12603_SUMMARY,
        "patch_material_count": len(patch_records),
        "patch_material_records_sha256": stable_hash(patch_records),
        "executor_command_manifest_sha256": stable_hash(command_manifest),
        "execution_request_ready_count": len(patch_records),
        "execution_gate_granted": False,
        "execute_path_enabled": False,
        "this_stage_runs_replay": False,
        "raw_replay_evidence_present": False,
        **no_claim_fields(),
    }
    check_false(private_request, "stage12604_private_request")
    write_json(out / "private/reviewed_execution_request_materials.json", private_request)
    return private_request, command_manifest


def build_public_packet(private_request: Mapping[str, Any], command_manifest: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    public_contract = {
        "record_type": "stage12604_public_reviewed_execution_request_materials_contract_v1",
        "stage12602_runner_sha256": EXPECTED_STAGE12602_RUNNER,
        "stage12603_summary_sha256": EXPECTED_STAGE12603_SUMMARY,
        "reviewed_execution_capable_source_present": True,
        "independent_execution_capable_source_review_present": True,
        "independent_execution_capable_source_review_passed": True,
        "execution_request_materials_present": True,
        "patch_material_count": private_request["patch_material_count"],
        "executor_command_manifest_present": True,
        "executor_command_manifest_sha256": private_request["executor_command_manifest_sha256"],
        "execution_request_ready_count": private_request["execution_request_ready_count"],
        "execution_gate_granted": False,
        "execute_path_enabled": False,
        "this_stage_runs_replay": False,
        "raw_replay_evidence_present": False,
        "claim_boundary": {
            "execution_authorization": "separate_execution_gate_required",
            "replay_success_claim": "forbidden_until_manual_executor_raw_artifacts_exist",
            "level3_claim": "forbidden_until_causal_candidate_and_stop_continue_provenance_exist",
            "training_admission": "separate_future_gate_required",
        },
        **no_claim_fields(),
    }
    summary = {
        "record_type": "stage12604_public_reviewed_execution_request_materials_summary_v1",
        "stage": STAGE,
        "decision": "BLOCKED_EXECUTION_GATE_GRANT_REQUIRED",
        "stage12602_runner_sha256": EXPECTED_STAGE12602_RUNNER,
        "stage12603_summary_sha256": EXPECTED_STAGE12603_SUMMARY,
        "reviewed_execution_capable_source_present": True,
        "independent_execution_capable_source_review_present": True,
        "independent_execution_capable_source_review_passed": True,
        "execution_request_materials_present": True,
        "patch_material_count": private_request["patch_material_count"],
        "executor_command_manifest_present": True,
        "executor_command_manifest_sha256": private_request["executor_command_manifest_sha256"],
        "execution_request_ready_count": private_request["execution_request_ready_count"],
        "execution_gate_granted": False,
        "execute_path_enabled": False,
        "execution_allowed": False,
        "execution_performed": False,
        "this_stage_runs_replay": False,
        "raw_replay_evidence_present": False,
        "stage12605_allowed": False,
        "level3_atom_count": 0,
        "downstream_blockers": [
            "execution_gate_not_granted_for_reviewed_source",
            "execute_path_disabled_pending_execution_gate",
            "manual_replay_execution_not_performed",
            "trusted_replay_raw_evidence_absent",
            "causally_committed_pre_outcome_candidate_set_absent_even_after_future_replay",
            "observed_stop_continue_decision_absent_even_after_future_replay",
            "level3_materialization_forbidden",
            "training_admission_forbidden",
            "strict_eval_admission_forbidden",
            "sealed_eval_admission_forbidden",
        ],
        **no_claim_fields(),
    }
    for label, record in (("summary", summary), ("contract", public_contract)):
        check_false(record, "stage12604_" + label)
        assert_public_sanitized(record, "stage12604_" + label)
    return summary, public_contract


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    load_stage12603()
    out.mkdir(parents=True, exist_ok=True)
    private_request, command_manifest = build_private_materials(out)
    summary, public_contract = build_public_packet(private_request, command_manifest)
    write_json(out / "contract.json", public_contract)
    pointer = {
        "record_type": "stage12604_public_private_execution_request_materials_pointer_v1",
        "stage12602_runner_sha256": EXPECTED_STAGE12602_RUNNER,
        "stage12603_summary_sha256": EXPECTED_STAGE12603_SUMMARY,
        "private_reviewed_execution_request_materials_sha256": stable_hash(private_request),
        "private_executor_command_manifest_sha256": stable_hash(command_manifest),
        "private_patch_material_records_sha256": private_request["patch_material_records_sha256"],
        **no_claim_fields(),
    }
    check_false(pointer, "stage12604_pointer")
    assert_public_sanitized(pointer, "stage12604_pointer")
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))

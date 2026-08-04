#!/usr/bin/env python3
"""Build Stage12596 reviewed manual replay executor packet.

This stage still does not execute replay. It verifies Stage12594 and Stage12595
handoff integrity, then emits a reviewed executor-contract packet for a future,
separately implemented and manually invoked replay executor.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12596_reviewed_manual_replay_executor_packet"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12594 = ROOT / "runs/local/artifacts/stage12594_trusted_external_causal_replay_runner_preflight"
S12595 = ROOT / "runs/local/artifacts/stage12595_trusted_replay_execution_handoff"
S12595_EXTERNAL = ROOT / "runs/summaries/stage12595_trusted_replay_execution_handoff.json"
EXPECTED_STAGE12594_GENERATION = "91d0cda6e9acdf2e09c4d04b7d8e00159351bedf1ef0e7f70c4912d48c34475d"
EXPECTED_STAGE12594_MANIFEST = "5f5353b63591f77433a6a0a01141211796906ef13c02c2569c48f65a59c5a856"
EXPECTED_STAGE12595_SLOT_SHA256 = "8ddfdfb0872c8cb74a46f0041801bced7e674228d74af98b30ce7631afebe3a0"
EXPECTED_BINDINGS = (
    "9debfb351017b950db9830d7c74832de54fca66bd6cb2d13b7abf834e580688b",
    "890bc20899934d6a532842e0861e544c2e6f55f646a982b204a922eead39820a",
)
FALSE_FIELDS = (
    "authorizes_execution", "execution_allowed", "execution_performed", "replay_trustworthy",
    "level_3_materialized", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted",
    "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "training_allowed",
    "ranking_allowed", "positive_stop", "stage12596_allowed", "stage12597_allowed",
)
REQUIRED_STAGE12595_BLOCKERS = (
    "manual_replay_execution_not_performed",
    "trusted_replay_raw_evidence_absent",
    "causally_committed_pre_outcome_candidate_set_absent_even_after_future_replay",
    "observed_stop_continue_decision_absent_even_after_future_replay",
    "level3_materialization_forbidden",
    "training_admission_forbidden",
    "strict_eval_admission_forbidden",
    "sealed_eval_admission_forbidden",
)
REQUIRED_EXECUTOR_CONTROLS = (
    "load_stage12594_generation_and_verify_manifest_before_execution",
    "create_no_local_no_hardlinks_detached_snapshot",
    "rerun_namespace_manifest_match_before_material_read",
    "run_initial_patched_final_phases_inside_hardened_bwrap",
    "capture_full_pytest_phase_reports_and_raw_stream_digests",
    "assert_patched_only_changes_bound_production_path",
    "assert_final_reverts_to_initial_failure_fingerprint",
    "publish_private_raw_evidence_only_after_public_leak_scan",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "selector", "raw_stream", "stdout.raw", "stderr.raw", "manual_replay_execution_slots",
    "before_commit_oid", "after_commit_oid", "production_path", "production_patch_sha256",
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


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = b"".join(canonical_bytes(dict(row)) + b"\n" for row in rows)
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def no_claim_fields() -> dict[str, Any]:
    return {
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


def load_stage12594(root: Path = S12594) -> dict[str, Any]:
    summary = read_json(root / "summary.json")
    contract = read_json(root / "contract.json")
    manifest = read_json(root / "publication_manifest.json")
    leak = read_json(root / "public_leak_scan.json")
    snapshot = read_json(root / "private/pinned_snapshot_contract.json")
    if summary.get("decision") != "BLOCKED_TRUSTED_REPLAY_NOT_EXECUTED":
        raise GateError("stage12594_decision_mismatch")
    generation = summary.get("publication_generation_id")
    if generation != EXPECTED_STAGE12594_GENERATION:
        raise GateError("stage12594_generation_drift")
    if manifest.get("manifest_sha256") != EXPECTED_STAGE12594_MANIFEST:
        raise GateError("stage12594_manifest_pin_drift")
    if contract.get("publication_generation_id") != generation:
        raise GateError("stage12594_contract_generation_mismatch")
    if contract.get("external_repository_execution") != "requires_reviewed_separate_manually_invoked_executor":
        raise GateError("stage12594_executor_boundary_missing")
    if leak.get("passed") is not True or leak.get("leak_count") != 0:
        raise GateError("stage12594_public_leak_scan_not_clean")
    for row in manifest.get("files", []):
        relative = row.get("path")
        if not isinstance(relative, str):
            raise GateError("stage12594_manifest_path_invalid")
        path = root / relative
        if not path.is_file():
            raise GateError("stage12594_manifest_file_missing:" + relative)
        if sha256_file(path) != row.get("sha256"):
            raise GateError("stage12594_manifest_digest_mismatch:" + relative)
    if tuple(row.get("binding_payload_sha256") for row in snapshot.get("binding_snapshots", [])) != EXPECTED_BINDINGS:
        raise GateError("stage12594_snapshot_binding_set_mismatch")
    for label, record in (("summary", summary), ("contract", contract), ("manifest", manifest),
                          ("leak", leak), ("snapshot", snapshot)):
        check_false(record, "stage12594_" + label)
    return {"summary": summary, "contract": contract, "manifest": manifest, "leak": leak, "snapshot": snapshot}


def load_stage12595(root: Path = S12595, external_path: Path = S12595_EXTERNAL) -> dict[str, Any]:
    summary = read_json(root / "summary.json")
    external = read_json(external_path)
    contract = read_json(root / "contract.json")
    pointer = read_json(root / "digest_pointer.json")
    plan = read_json(root / "private/manual_replay_execution_handoff.json")
    slots = read_jsonl(root / "private/manual_replay_execution_slots.jsonl")
    if external != summary:
        raise GateError("stage12595_external_summary_mismatch")
    if summary.get("decision") != "BLOCKED_MANUAL_TRUSTED_REPLAY_EXECUTION_REQUIRED":
        raise GateError("stage12595_decision_mismatch")
    if summary.get("stage12594_publication_generation_id") != EXPECTED_STAGE12594_GENERATION:
        raise GateError("stage12595_stage12594_generation_drift")
    if sorted(summary.get("downstream_blockers", [])) != sorted(REQUIRED_STAGE12595_BLOCKERS):
        raise GateError("stage12595_blocker_set_mismatch")
    if summary.get("manual_replay_slot_count") != 2 or summary.get("execution_request_ready_count") != 0:
        raise GateError("stage12595_count_boundary_mismatch")
    if summary.get("stage12596_allowed") is not False:
        raise GateError("stage12595_stage12596_boundary_drift")
    if contract.get("manual_executor_only") is not True or contract.get("this_stage_runs_replay") is not False:
        raise GateError("stage12595_manual_executor_boundary_mismatch")
    if contract.get("executor_source_in_this_stage") is not False:
        raise GateError("stage12595_executor_source_boundary_mismatch")
    if contract.get("execution_request_ready_count") != 0 or contract.get("allowed_slot_count") != 2:
        raise GateError("stage12595_contract_count_boundary_mismatch")
    if plan.get("manual_executor_review_required") is not True:
        raise GateError("stage12595_review_gate_missing")
    if plan.get("execution_not_performed_by_this_stage") is not True:
        raise GateError("stage12595_execution_boundary_missing")
    if plan.get("slot_count") != 2 or len(slots) != 2:
        raise GateError("stage12595_private_slot_count_mismatch")
    if plan.get("slots_sha256") != EXPECTED_STAGE12595_SLOT_SHA256:
        raise GateError("stage12595_slot_hash_pin_drift")
    if stable_hash(slots) != plan.get("slots_sha256"):
        raise GateError("stage12595_slots_digest_mismatch")
    if pointer.get("private_handoff_sha256") != stable_hash({"plan": plan, "slots": slots}):
        raise GateError("stage12595_private_handoff_digest_mismatch")
    if pointer.get("slot_count") != len(slots):
        raise GateError("stage12595_pointer_slot_count_mismatch")
    if tuple(row.get("binding_payload_sha256") for row in slots) != EXPECTED_BINDINGS:
        raise GateError("stage12595_binding_set_mismatch")
    for row in slots:
        controls = row.get("manual_executor_required_controls")
        if tuple(controls or ()) != REQUIRED_EXECUTOR_CONTROLS:
            raise GateError("stage12595_required_control_drift")
    for label, record in (("summary", summary), ("external", external), ("contract", contract),
                          ("pointer", pointer), ("plan", plan), *[(f"slot_{i}", row) for i, row in enumerate(slots, 1)]):
        check_false(record, "stage12595_" + label)
    return {"summary": summary, "external": external, "contract": contract, "pointer": pointer,
            "plan": plan, "slots": slots}


def build_executor_packet(
    stage12594: Mapping[str, Any],
    stage12595: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    slots = stage12595["slots"]
    generation = stage12594["summary"]["publication_generation_id"]
    if stage12595["summary"]["stage12594_publication_generation_id"] != generation:
        raise GateError("stage12594_stage12595_generation_mismatch")
    slot_contracts = []
    for row in slots:
        slot_contracts.append({
            "record_type": "stage12596_private_manual_executor_slot_contract_v1",
            "slot_ordinal": row["slot_ordinal"],
            "stage12594_publication_generation_id": generation,
            "stage12594_publication_manifest_sha256": stage12594["manifest"]["manifest_sha256"],
            "stage12595_slots_sha256": stage12595["plan"]["slots_sha256"],
            "binding_payload_sha256": row["binding_payload_sha256"],
            "before_commit_oid": row["before_commit_oid"],
            "after_commit_oid": row["after_commit_oid"],
            "production_path": row["production_path"],
            "production_patch_sha256": row["production_patch_sha256"],
            "namespace_input_manifest_sha256": row["namespace_input_manifest_sha256"],
            "required_phase_sequence": ["initial", "patched", "final"],
            "required_execution_controls": list(REQUIRED_EXECUTOR_CONTROLS),
            "required_publication_controls": [
                "raw_replay_evidence_private_only",
                "public_summary_contains_only_digest_pointers_and_gate_state",
                "no_level3_claim_without_pre_outcome_candidate_and_stop_continue_provenance",
            ],
            **no_claim_fields(),
        })
    executor_contract = {
        "record_type": "stage12596_private_manual_executor_source_contract_v1",
        "stage12594_publication_generation_id": generation,
        "stage12594_publication_manifest_sha256": stage12594["manifest"]["manifest_sha256"],
        "stage12595_private_handoff_sha256": stage12595["pointer"]["private_handoff_sha256"],
        "stage12595_slots_sha256": stage12595["plan"]["slots_sha256"],
        "slot_contract_count": len(slot_contracts),
        "executor_source_contract_present": True,
        "executable_runner_present": False,
        "executor_command_manifest_present": False,
        "execution_not_performed_by_this_stage": True,
        "source_review_scope": "static_contract_for_future_separate_executor_only",
        "future_executor_requirements": [
            "must_be_separate_manually_invoked_program",
            "must_refuse_any_slot_not_pinned_by_stage12595",
            "must_verify_stage12594_generation_and_manifest_before_material_read",
            "must_verify_stage12595_private_handoff_digest_before_any_execution",
            "must_run_only_initial_patched_final_pytest_phases",
            "must_capture_raw_stream_digests_and_complete_pytest_phase_reports",
            "must_publish_raw_outputs_private_only_after_leak_scan",
            "must_not_materialize_level3_or_training_or_eval_admission",
        ],
        "forbidden_operations": [
            "automated_training",
            "gpu_use",
            "tokenizer_modification",
            "github_publication",
            "generic_dataset_mining",
            "sealed_or_strict_eval_admission",
            "level3_materialization",
        ],
        "slot_contracts_sha256": stable_hash(slot_contracts),
        **no_claim_fields(),
    }
    review = {
        "record_type": "stage12596_private_executor_contract_review_intake_v1",
        "review_result": "review_intake_packet_created_for_non_executing_executor_contract",
        "reviewed_stage12594_publication_generation_id": generation,
        "reviewed_stage12594_publication_manifest_sha256": stage12594["manifest"]["manifest_sha256"],
        "reviewed_stage12595_private_handoff_sha256": stage12595["pointer"]["private_handoff_sha256"],
        "reviewed_stage12595_slots_sha256": stage12595["plan"]["slots_sha256"],
        "reviewed_executor_contract_sha256": stable_hash(executor_contract),
        "reviewed_slot_contracts_sha256": stable_hash(slot_contracts),
        "review_scope": [
            "future_executor_contract_only",
            "stage12594_generation_and_manifest_pin",
            "stage12595_private_handoff_digest_pin",
            "non_execution_boundary",
            "no_level3_training_eval_authority",
            "public_output_sanitization_boundary",
        ],
        "review_limits": [
            "actual_executor_source_not_present",
            "trusted_replay_not_executed",
            "raw_replay_evidence_absent",
        ],
        **no_claim_fields(),
    }
    public_contract = {
        "record_type": "stage12596_public_reviewed_executor_packet_contract_v1",
        "stage12594_publication_generation_id": generation,
        "stage12594_publication_manifest_sha256": stage12594["manifest"]["manifest_sha256"],
        "stage12595_slots_sha256": stage12595["plan"]["slots_sha256"],
        "executor_source_contract_present": True,
        "executable_runner_present": False,
        "executor_command_manifest_present": False,
        "executor_contract_review_intake": "private_review_intake_packet_for_non_executing_contract_only",
        "manual_executor_only": True,
        "this_stage_runs_replay": False,
        "execution_request_ready_count": 0,
        "reviewed_slot_contract_count": len(slot_contracts),
        "claim_boundary": {
            "replay_success_claim": "forbidden_until_manual_executor_raw_artifacts_exist",
            "level3_claim": "forbidden_until_causal_candidate_and_stop_continue_provenance_exist",
            "training_admission": "separate_future_gate_required",
        },
        **no_claim_fields(),
    }
    summary = {
        "record_type": "stage12596_public_reviewed_executor_packet_summary_v1",
        "stage": STAGE,
        "decision": "BLOCKED_TRUSTED_REPLAY_EXECUTION_NOT_PERFORMED",
        "stage12594_publication_generation_id": generation,
        "stage12594_publication_manifest_sha256": stage12594["manifest"]["manifest_sha256"],
        "stage12595_slots_sha256": stage12595["plan"]["slots_sha256"],
        "executor_source_contract_present": True,
        "executable_runner_present": False,
        "executor_command_manifest_present": False,
        "executor_contract_review_intake_present": True,
        "reviewed_slot_contract_count": len(slot_contracts),
        "manual_replay_slot_count": len(slot_contracts),
        "execution_request_ready_count": 0,
        "stage12597_allowed": False,
        "level3_atom_count": 0,
        "downstream_blockers": [
            "separate_manual_executor_source_not_implemented",
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
    for label, record in (("summary", summary), ("public_contract", public_contract)):
        assert_public_sanitized(record, "stage12596_" + label)
    private_packet = {"executor_contract": executor_contract, "review": review}
    return summary, slot_contracts, {"private_packet": private_packet, "public_contract": public_contract}


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12594 = load_stage12594()
    stage12595 = load_stage12595()
    summary, slot_contracts, bundle = build_executor_packet(stage12594, stage12595)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "contract.json", bundle["public_contract"])
    write_json(out / "private/manual_executor_source_contract.json", bundle["private_packet"]["executor_contract"])
    write_json(out / "private/independent_executor_contract_review.json", bundle["private_packet"]["review"])
    write_jsonl(out / "private/manual_executor_slot_contracts.jsonl", slot_contracts)
    public_pointer = {
        "record_type": "stage12596_public_private_executor_packet_pointer_v1",
        "private_executor_contract_sha256": stable_hash(bundle["private_packet"]["executor_contract"]),
        "private_review_intake_sha256": stable_hash(bundle["private_packet"]["review"]),
        "private_slot_contracts_sha256": stable_hash(slot_contracts),
        "slot_count": len(slot_contracts),
        **no_claim_fields(),
    }
    assert_public_sanitized(public_pointer, "stage12596_pointer")
    write_json(out / "digest_pointer.json", public_pointer)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))

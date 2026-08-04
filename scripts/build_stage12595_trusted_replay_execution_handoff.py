#!/usr/bin/env python3
"""Build Stage12595 trusted replay execution handoff.

This stage does not execute replay. It verifies the reviewed Stage12594
publication generation and emits a manual-only executor handoff for a separate,
reviewed replay runner.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12595_trusted_replay_execution_handoff"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12594 = ROOT / "runs/local/artifacts/stage12594_trusted_external_causal_replay_runner_preflight"
S12594_EXTERNAL = ROOT / "runs/summaries/stage12594_trusted_external_causal_replay_runner_preflight.json"
EXPECTED_STAGE12594_GENERATION = "91d0cda6e9acdf2e09c4d04b7d8e00159351bedf1ef0e7f70c4912d48c34475d"
EXPECTED_STAGE12594_MANIFEST = "5f5353b63591f77433a6a0a01141211796906ef13c02c2569c48f65a59c5a856"
EXPECTED_BINDINGS = (
    "9debfb351017b950db9830d7c74832de54fca66bd6cb2d13b7abf834e580688b",
    "890bc20899934d6a532842e0861e544c2e6f55f646a982b204a922eead39820a",
)
FALSE_FIELDS = (
    "implementation_ready", "stage12595_allowed", "replay_trustworthy", "level_3_materialized",
    "training_admitted", "strict_eval_admitted", "sealed_eval_admitted", "sealed_eval_eligible",
    "strict_eval_eligible", "execution_allowed", "execution_performed", "training_allowed",
    "ranking_allowed", "admission_allowed", "authorizes_execution",
)
REMAINING_STAGE12594_BLOCKERS = (
    "causally_committed_pre_outcome_candidate_set_absent_even_after_future_replay",
    "observed_stop_continue_decision_absent_even_after_future_replay",
    "trusted_external_replay_not_executed",
    "level3_materialization_forbidden",
    "training_admission_forbidden",
    "strict_eval_admission_forbidden",
    "sealed_eval_admission_forbidden",
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
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise GateError("jsonl_object_required:" + path.name)
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


def load_stage12594(root: Path = S12594, external_path: Path = S12594_EXTERNAL) -> dict[str, Any]:
    summary = read_json(root / "summary.json")
    contract = read_json(root / "contract.json")
    manifest = read_json(root / "publication_manifest.json")
    external = read_json(external_path)
    leak = read_json(root / "public_leak_scan.json")
    review = read_json(root / "private/independent_security_review.json")
    snapshot = read_json(root / "private/pinned_snapshot_contract.json")
    binding_pins = read_jsonl(root / "private/binding_pins.jsonl")
    input_pin_manifest = read_json(root / "private/input_pin_manifest.json")
    if summary.get("decision") != "BLOCKED_TRUSTED_REPLAY_NOT_EXECUTED":
        raise GateError("stage12594_decision_not_replay_blocked")
    generation = summary.get("publication_generation_id")
    if generation != EXPECTED_STAGE12594_GENERATION:
        raise GateError("stage12594_generation_drift")
    if manifest.get("manifest_sha256") != EXPECTED_STAGE12594_MANIFEST:
        raise GateError("stage12594_manifest_pin_drift")
    if external.get("publication_generation_id") != generation:
        raise GateError("stage12594_external_generation_mismatch")
    if external.get("publication_manifest_sha256") != manifest.get("manifest_sha256"):
        raise GateError("stage12594_external_manifest_mismatch")
    if sorted(summary.get("downstream_blockers", [])) != sorted(REMAINING_STAGE12594_BLOCKERS):
        raise GateError("stage12594_blocker_set_mismatch")
    if contract.get("external_repository_execution") != "requires_reviewed_separate_manually_invoked_executor":
        raise GateError("stage12594_executor_boundary_missing")
    if review.get("review_result") != "passed_no_blocker_found":
        raise GateError("stage12594_review_not_passed")
    if review.get("reviewed_publication_generation_id") != generation:
        raise GateError("stage12594_review_generation_mismatch")
    if leak.get("passed") is not True or leak.get("leak_count") != 0:
        raise GateError("stage12594_public_leak_scan_not_clean")
    for relative in [row.get("path") for row in manifest.get("files", [])]:
        if not isinstance(relative, str):
            raise GateError("stage12594_manifest_path_invalid")
        path = root / relative
        if not path.is_file():
            raise GateError("stage12594_manifest_file_missing:" + relative)
        row = next(item for item in manifest["files"] if item["path"] == relative)
        if sha256_file(path) != row.get("sha256"):
            raise GateError("stage12594_manifest_digest_mismatch:" + relative)
    for label, record in (
        ("summary", summary), ("contract", contract), ("manifest", manifest),
        ("external", external), ("review", review), ("snapshot", snapshot), ("leak", leak),
    ):
        check_false(record, "stage12594_" + label)
    if tuple(row.get("binding_payload_sha256") for row in snapshot.get("binding_snapshots", [])) != EXPECTED_BINDINGS:
        raise GateError("stage12594_snapshot_binding_set_mismatch")
    return {
        "summary": summary,
        "contract": contract,
        "manifest": manifest,
        "external": external,
        "leak": leak,
        "review": review,
        "snapshot": snapshot,
        "binding_pins": binding_pins,
        "input_pin_manifest": input_pin_manifest,
    }


def build_execution_handoff(stage12594: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    snapshot = stage12594["snapshot"]
    generation = stage12594["summary"]["publication_generation_id"]
    rows = []
    for item in snapshot["binding_snapshots"]:
        rows.append({
            "record_type": "stage12595_private_manual_replay_execution_slot_v1",
            "slot_ordinal": item["ordinal"],
            "stage12594_publication_generation_id": generation,
            "binding_payload_sha256": item["binding_payload_sha256"],
            "before_commit_oid": item["before_commit_oid"],
            "after_commit_oid": item["after_commit_oid"],
            "production_path": item["production_path"],
            "production_patch_sha256": item["production_patch_sha256"],
            "namespace_input_manifest_sha256": item["namespace_input_manifest_sha256"],
            "manual_executor_required_controls": [
                "load_stage12594_generation_and_verify_manifest_before_execution",
                "create_no_local_no_hardlinks_detached_snapshot",
                "rerun_namespace_manifest_match_before_material_read",
                "run_initial_patched_final_phases_inside_hardened_bwrap",
                "capture_full_pytest_phase_reports_and_raw_stream_digests",
                "assert_patched_only_changes_bound_production_path",
                "assert_final_reverts_to_initial_failure_fingerprint",
                "publish_private_raw_evidence_only_after_public_leak_scan",
            ],
            **no_claim_fields(),
        })
    private_plan = {
        "record_type": "stage12595_private_manual_replay_execution_handoff_v1",
        "stage12594_publication_generation_id": generation,
        "slot_count": len(rows),
        "manual_executor_review_required": True,
        "execution_not_performed_by_this_stage": True,
        "slots_sha256": stable_hash(rows),
        "review_gate_before_execution": [
            "review_separate_executor_source_against_stage12594_contract",
            "review_runtime_mounts_and_environment_against_stage12594_contract",
            "operator_confirms_manual_invocation_scope_exactly_two_slots",
        ],
        **no_claim_fields(),
    }
    summary = {
        "record_type": "stage12595_public_manual_replay_execution_handoff_summary_v1",
        "stage": STAGE,
        "decision": "BLOCKED_MANUAL_TRUSTED_REPLAY_EXECUTION_REQUIRED",
        "stage12594_publication_generation_id": generation,
        "reviewed_stage12594_security_hardening": True,
        "manual_replay_slot_count": len(rows),
        "execution_request_ready_count": 0,
        "execution_performed": False,
        "execution_allowed": False,
        "stage12596_allowed": False,
        "level3_atom_count": 0,
        "downstream_blockers": [
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
    public_contract = {
        "record_type": "stage12595_public_manual_replay_execution_handoff_contract_v1",
        "purpose": "prepare_exact_manual_replay_executor_scope_after_stage12594_security_review",
        "stage12594_publication_generation_id": generation,
        "manual_executor_only": True,
        "this_stage_runs_replay": False,
        "executor_source_in_this_stage": False,
        "generic_execution_authority": False,
        "allowed_slot_count": len(rows),
        "execution_request_ready_count": 0,
        "required_controls": private_plan["review_gate_before_execution"],
        "claim_boundary": {
            "replay_success_claim": "forbidden_until_manual_executor_artifacts_exist",
            "level3_claim": "forbidden_even_after_replay_until_causal_candidate_and_stop_provenance_exist",
            "training_admission": "separate_future_gate_required",
        },
        **no_claim_fields(),
    }
    return summary, rows, {"private_plan": private_plan, "public_contract": public_contract}


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12594 = load_stage12594()
    summary, slots, bundle = build_execution_handoff(stage12594)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "contract.json", bundle["public_contract"])
    write_json(out / "private/manual_replay_execution_handoff.json", bundle["private_plan"])
    write_jsonl(out / "private/manual_replay_execution_slots.jsonl", slots)
    public_pointer = {
        "record_type": "stage12595_public_private_handoff_pointer_v1",
        "private_handoff_sha256": stable_hash({"plan": bundle["private_plan"], "slots": slots}),
        "slot_count": len(slots),
        **no_claim_fields(),
    }
    write_json(out / "digest_pointer.json", public_pointer)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))

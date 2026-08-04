#!/usr/bin/env python3
"""Stage12597 manual replay executor source preflight.

This is a separate executor source file, but it is preflight-only. It validates
Stage12596's reviewed contract packet and refuses replay execution until a later
independent source review and explicit execution gate exist.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
S12596 = ROOT / "runs/local/artifacts/stage12596_reviewed_manual_replay_executor_packet"
EXPECTED_STAGE12594_GENERATION = "91d0cda6e9acdf2e09c4d04b7d8e00159351bedf1ef0e7f70c4912d48c34475d"
EXPECTED_STAGE12594_MANIFEST = "5f5353b63591f77433a6a0a01141211796906ef13c02c2569c48f65a59c5a856"
EXPECTED_STAGE12595_SLOTS = "8ddfdfb0872c8cb74a46f0041801bced7e674228d74af98b30ce7631afebe3a0"
EXPECTED_STAGE12596_PRIVATE_CONTRACT = "f880781f4462211c29b071941e8105064f138a665647bffc5bb00c90c1d56edc"
EXPECTED_STAGE12596_REVIEW_INTAKE = "5296d754da03a6695a99504c8c6d7b7a717eb908e47ed80cfb6eb909b71cb0e5"
EXPECTED_STAGE12596_SLOT_CONTRACTS = "dea5b2bd14a40a208ffe2d668a54c46634c06d9d9d6c4f6eea97b5c24e9198a5"
EXPECTED_BINDINGS = (
    "9debfb351017b950db9830d7c74832de54fca66bd6cb2d13b7abf834e580688b",
    "890bc20899934d6a532842e0861e544c2e6f55f646a982b204a922eead39820a",
)
FALSE_FIELDS = (
    "authorizes_execution", "execution_allowed", "execution_performed", "replay_trustworthy",
    "level_3_materialized", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted",
    "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "training_allowed",
    "ranking_allowed", "positive_stop", "stage12597_allowed", "stage12598_allowed",
)
REQUIRED_STAGE12596_BLOCKERS = (
    "separate_manual_executor_source_not_implemented",
    "manual_replay_execution_not_performed",
    "trusted_replay_raw_evidence_absent",
    "causally_committed_pre_outcome_candidate_set_absent_even_after_future_replay",
    "observed_stop_continue_decision_absent_even_after_future_replay",
    "level3_materialization_forbidden",
    "training_admission_forbidden",
    "strict_eval_admission_forbidden",
    "sealed_eval_admission_forbidden",
)


class GateError(RuntimeError):
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


def load_stage12596_packet(root: Path = S12596) -> dict[str, Any]:
    summary = read_json(root / "summary.json")
    contract = read_json(root / "contract.json")
    pointer = read_json(root / "digest_pointer.json")
    private_contract = read_json(root / "private/manual_executor_source_contract.json")
    review_intake = read_json(root / "private/independent_executor_contract_review.json")
    slots = read_jsonl(root / "private/manual_executor_slot_contracts.jsonl")
    if summary.get("decision") != "BLOCKED_TRUSTED_REPLAY_EXECUTION_NOT_PERFORMED":
        raise GateError("stage12596_decision_mismatch")
    if summary.get("stage12594_publication_generation_id") != EXPECTED_STAGE12594_GENERATION:
        raise GateError("stage12596_stage12594_generation_drift")
    if summary.get("stage12594_publication_manifest_sha256") != EXPECTED_STAGE12594_MANIFEST:
        raise GateError("stage12596_stage12594_manifest_drift")
    if summary.get("stage12595_slots_sha256") != EXPECTED_STAGE12595_SLOTS:
        raise GateError("stage12596_stage12595_slot_pin_drift")
    if sorted(summary.get("downstream_blockers", [])) != sorted(REQUIRED_STAGE12596_BLOCKERS):
        raise GateError("stage12596_blocker_set_mismatch")
    if summary.get("execution_request_ready_count") != 0 or summary.get("stage12597_allowed") is not False:
        raise GateError("stage12596_execution_boundary_mismatch")
    if summary.get("executable_runner_present") is not False or summary.get("executor_command_manifest_present") is not False:
        raise GateError("stage12596_runner_boundary_mismatch")
    if summary.get("executor_contract_review_intake_present") is not True:
        raise GateError("stage12596_review_intake_missing")
    if "independent_executor_contract_review_passed" in summary:
        raise GateError("stage12596_independent_review_overclaim")
    if contract.get("this_stage_runs_replay") is not False or contract.get("execution_request_ready_count") != 0:
        raise GateError("stage12596_contract_execution_boundary_mismatch")
    if private_contract.get("executable_runner_present") is not False:
        raise GateError("stage12596_private_runner_boundary_mismatch")
    if private_contract.get("executor_command_manifest_present") is not False:
        raise GateError("stage12596_private_command_boundary_mismatch")
    if review_intake.get("review_result") != "review_intake_packet_created_for_non_executing_executor_contract":
        raise GateError("stage12596_review_intake_result_mismatch")
    if review_intake.get("reviewed_executor_contract_sha256") != stable_hash(private_contract):
        raise GateError("stage12596_review_private_contract_digest_mismatch")
    if review_intake.get("reviewed_slot_contracts_sha256") != stable_hash(slots):
        raise GateError("stage12596_review_slot_contract_digest_mismatch")
    if pointer.get("private_executor_contract_sha256") != EXPECTED_STAGE12596_PRIVATE_CONTRACT:
        raise GateError("stage12596_private_contract_pin_drift")
    if pointer.get("private_review_intake_sha256") != EXPECTED_STAGE12596_REVIEW_INTAKE:
        raise GateError("stage12596_review_intake_pin_drift")
    if pointer.get("private_slot_contracts_sha256") != EXPECTED_STAGE12596_SLOT_CONTRACTS:
        raise GateError("stage12596_slot_contract_pin_drift")
    if stable_hash(private_contract) != pointer.get("private_executor_contract_sha256"):
        raise GateError("stage12596_private_contract_digest_mismatch")
    if stable_hash(review_intake) != pointer.get("private_review_intake_sha256"):
        raise GateError("stage12596_review_intake_digest_mismatch")
    if stable_hash(slots) != pointer.get("private_slot_contracts_sha256"):
        raise GateError("stage12596_slot_contract_digest_mismatch")
    if pointer.get("slot_count") != 2 or len(slots) != 2:
        raise GateError("stage12596_slot_count_mismatch")
    if tuple(row.get("binding_payload_sha256") for row in slots) != EXPECTED_BINDINGS:
        raise GateError("stage12596_binding_set_mismatch")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer),
                          ("private_contract", private_contract), ("review_intake", review_intake),
                          *[(f"slot_{i}", row) for i, row in enumerate(slots, 1)]):
        check_false(record, "stage12596_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer,
            "private_contract": private_contract, "review_intake": review_intake, "slots": slots}


def build_preflight_report(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "stage12597_manual_executor_source_preflight_report_v1",
        "stage12594_publication_generation_id": packet["summary"]["stage12594_publication_generation_id"],
        "stage12594_publication_manifest_sha256": packet["summary"]["stage12594_publication_manifest_sha256"],
        "stage12595_slots_sha256": packet["summary"]["stage12595_slots_sha256"],
        "stage12596_private_executor_contract_sha256": packet["pointer"]["private_executor_contract_sha256"],
        "stage12596_private_review_intake_sha256": packet["pointer"]["private_review_intake_sha256"],
        "manual_executor_preflight_source_present": True,
        "preflight_cli_present": True,
        "execute_path_enabled": False,
        "this_stage_runs_replay": False,
        "executor_command_manifest_present": False,
        "raw_replay_evidence_present": False,
        "execution_request_ready_count": 0,
        "slot_count": len(packet["slots"]),
        "required_future_gate": "independent_executor_source_review_before_any_execute_path",
        **no_claim_fields(),
    }


def run_preflight(root: Path = S12596) -> dict[str, Any]:
    return build_preflight_report(load_stage12596_packet(root))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage12596-root", type=Path, default=S12596)
    parser.add_argument("--preflight-only", action="store_true", help="validate packet and print preflight report")
    parser.add_argument("--execute", action="store_true", help="always rejected until independent source review")
    parser.add_argument("--run", action="store_true", help="always rejected until independent source review")
    args = parser.parse_args()
    if args.execute or args.run:
        raise GateError("manual_replay_execution_disabled_pending_independent_source_review")
    if not args.preflight_only:
        raise GateError("preflight_only_flag_required")
    print(json.dumps(run_preflight(args.stage12596_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

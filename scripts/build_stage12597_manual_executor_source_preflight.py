#!/usr/bin/env python3
"""Build Stage12597 manual executor source preflight packet.

This stage introduces a separate preflight-only executor source file. It does
not enable replay execution and does not claim independent source review.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12597_manual_executor_source_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
RUNNER = ROOT / "scripts/run_stage12597_manual_trusted_replay_executor.py"
S12596 = ROOT / "runs/local/artifacts/stage12596_reviewed_manual_replay_executor_packet"
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "selector", "raw_stream", "stdout.raw", "stderr.raw", "before_commit_oid",
    "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
)
FALSE_FIELDS = (
    "authorizes_execution", "execution_allowed", "execution_performed", "replay_trustworthy",
    "level_3_materialized", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted",
    "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "training_allowed",
    "ranking_allowed", "positive_stop", "stage12598_allowed",
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


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
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


def load_runner(path: Path = RUNNER):
    if not path.is_file():
        raise GateError("manual_executor_source_missing")
    spec = importlib.util.spec_from_file_location("stage12597_runner", path)
    if spec is None or spec.loader is None:
        raise GateError("manual_executor_source_import_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_cli(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)


def validate_runner_source(runner_path: Path = RUNNER, stage12596_root: Path = S12596) -> tuple[dict[str, Any], dict[str, Any]]:
    runner = load_runner(runner_path)
    packet = runner.load_stage12596_packet(stage12596_root)
    report = runner.build_preflight_report(packet)
    check_false(report, "runner_report")
    if report.get("execute_path_enabled") is not False:
        raise GateError("runner_execute_path_enabled")
    if report.get("execution_request_ready_count") != 0:
        raise GateError("runner_execution_request_count_drift")
    result = run_cli([sys.executable, str(runner_path), "--stage12596-root", str(stage12596_root), "--execute"])
    if result.returncode == 0 or "manual_replay_execution_disabled_pending_independent_source_review" not in result.stderr:
        raise GateError("runner_execute_not_rejected")
    preflight = run_cli([sys.executable, str(runner_path), "--stage12596-root", str(stage12596_root), "--preflight-only"])
    if preflight.returncode != 0:
        raise GateError("runner_preflight_cli_failed")
    cli_report = json.loads(preflight.stdout)
    if cli_report != report:
        raise GateError("runner_preflight_cli_report_mismatch")
    return packet, report


def build_packet(packet: Mapping[str, Any], report: Mapping[str, Any], runner_sha256: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    source_review_intake = {
        "record_type": "stage12597_private_executor_source_review_intake_v1",
        "review_result": "source_preflight_packet_created_independent_review_absent",
        "manual_executor_preflight_source_sha256": runner_sha256,
        "stage12596_private_executor_contract_sha256": packet["pointer"]["private_executor_contract_sha256"],
        "stage12596_private_review_intake_sha256": packet["pointer"]["private_review_intake_sha256"],
        "stage12596_private_slot_contracts_sha256": packet["pointer"]["private_slot_contracts_sha256"],
        "validated_cli_modes": ["preflight_only"],
        "rejected_cli_modes": ["execute", "run"],
        "this_stage_runs_replay": False,
        "executor_command_manifest_present": False,
        "raw_replay_evidence_present": False,
        "review_limits": [
            "independent_executor_source_review_absent",
            "execute_path_disabled",
            "trusted_replay_not_executed",
            "raw_replay_evidence_absent",
        ],
        **no_claim_fields(),
    }
    public_contract = {
        "record_type": "stage12597_public_manual_executor_source_preflight_contract_v1",
        "stage12594_publication_generation_id": report["stage12594_publication_generation_id"],
        "stage12594_publication_manifest_sha256": report["stage12594_publication_manifest_sha256"],
        "stage12595_slots_sha256": report["stage12595_slots_sha256"],
        "stage12596_private_executor_contract_sha256": packet["pointer"]["private_executor_contract_sha256"],
        "manual_executor_preflight_source_present": True,
        "manual_executor_preflight_source_sha256": runner_sha256,
        "preflight_cli_present": True,
        "execute_path_enabled": False,
        "executor_command_manifest_present": False,
        "raw_replay_evidence_present": False,
        "independent_executor_source_review_present": False,
        "this_stage_runs_replay": False,
        "execution_request_ready_count": 0,
        "claim_boundary": {
            "replay_success_claim": "forbidden_until_manual_executor_raw_artifacts_exist",
            "level3_claim": "forbidden_until_causal_candidate_and_stop_continue_provenance_exist",
            "training_admission": "separate_future_gate_required",
        },
        **no_claim_fields(),
    }
    summary = {
        "record_type": "stage12597_public_manual_executor_source_preflight_summary_v1",
        "stage": STAGE,
        "decision": "BLOCKED_EXECUTOR_SOURCE_REVIEW_REQUIRED",
        "stage12594_publication_generation_id": report["stage12594_publication_generation_id"],
        "stage12594_publication_manifest_sha256": report["stage12594_publication_manifest_sha256"],
        "stage12595_slots_sha256": report["stage12595_slots_sha256"],
        "stage12596_private_executor_contract_sha256": packet["pointer"]["private_executor_contract_sha256"],
        "manual_executor_preflight_source_present": True,
        "manual_executor_preflight_source_sha256": runner_sha256,
        "preflight_cli_present": True,
        "execute_path_enabled": False,
        "executor_command_manifest_present": False,
        "raw_replay_evidence_present": False,
        "independent_executor_source_review_present": False,
        "this_stage_runs_replay": False,
        "manual_replay_slot_count": report["slot_count"],
        "execution_request_ready_count": 0,
        "stage12598_allowed": False,
        "level3_atom_count": 0,
        "downstream_blockers": [
            "independent_executor_source_review_absent",
            "execute_path_disabled_pending_independent_review",
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
        check_false(record, "stage12597_" + label)
        assert_public_sanitized(record, "stage12597_" + label)
    check_false(source_review_intake, "stage12597_source_review_intake")
    return summary, public_contract, source_review_intake


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    runner_sha256 = sha256_file(RUNNER)
    packet, report = validate_runner_source(RUNNER, S12596)
    summary, public_contract, source_review_intake = build_packet(packet, report, runner_sha256)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "contract.json", public_contract)
    write_json(out / "private/executor_source_review_intake.json", source_review_intake)
    pointer = {
        "record_type": "stage12597_public_private_executor_source_pointer_v1",
        "manual_executor_preflight_source_sha256": runner_sha256,
        "private_source_review_intake_sha256": stable_hash(source_review_intake),
        "stage12596_private_executor_contract_sha256": packet["pointer"]["private_executor_contract_sha256"],
        "stage12596_private_slot_contracts_sha256": packet["pointer"]["private_slot_contracts_sha256"],
        **no_claim_fields(),
    }
    check_false(pointer, "stage12597_pointer")
    assert_public_sanitized(pointer, "stage12597_pointer")
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))

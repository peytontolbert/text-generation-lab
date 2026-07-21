#!/usr/bin/env python3
"""Audit whether Stage12483 has an in-repo executor path.

This stage is deliberately fail-closed. It does not execute private proof
bundles, hydrate repos, replay tasks, validate credit, emit training rows, or
write Stage12468 return files. It only classifies known scripts in the current
proof-bundle chain so the next step cannot drift into another planning-only
stage while assuming an executor exists.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12484_private_proof_bundle_executor_readiness_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12483 = "stage12483_private_proof_bundle_acquisition_work_order"
STAGE12483_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12483}.json"
STAGE12483_WORK_ITEMS = ROOT / "runs/local/artifacts" / STAGE12483 / "private_proof_bundle_work_items_ref.jsonl"

STAGE12468 = "stage12468_non_bears_patch_effect_private_return_validator"
STAGE12468_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12468}.json"
STAGE12468_CONTRACT = ROOT / "runs/local/artifacts" / STAGE12468 / "validator_contract.json"

PRIVATE_RETURN_FILE = (
    ROOT
    / "runs/local/artifacts/stage12467_non_bears_trace_transition_repair_proof_request_preflight"
    / "private_proof_slot_returns.jsonl"
)


SCRIPT_CANDIDATES = [
    {
        "stage_ref": "stage12286_external_repair_replay_smoke_executor",
        "script": "scripts/build_stage12286_external_repair_replay_smoke_executor.py",
        "classification": "external_repair_smoke_executor_not_stage12468_bundle_executor",
        "reason": "executes old replay targets and emits PE2 candidates; does not consume Stage12483 work items or write Stage12468 private returns",
        "stage12483_compatible": False,
    },
    {
        "stage_ref": "stage12437_open_swe_private_replay_executor_pilot_20_request_or_postrun",
        "script": "scripts/build_stage12437_open_swe_private_replay_executor_pilot_20_request_or_postrun.py",
        "classification": "request_or_public_postrun_summary_no_execution",
        "reason": "configured fail-closed as request-only unless external private evidence already exists",
        "stage12483_compatible": False,
    },
    {
        "stage_ref": "stage12447_adapter_executor_work_order_shards",
        "script": "scripts/build_stage12447_adapter_executor_work_order_shards.py",
        "classification": "work_order_shards_no_execution",
        "reason": "prepares executor shards; does not perform private execution or produce validator returns",
        "stage12483_compatible": False,
    },
    {
        "stage_ref": "stage12468_non_bears_patch_effect_private_return_validator",
        "script": "scripts/build_stage12468_non_bears_patch_effect_private_return_validator.py",
        "classification": "validator_credit_authority_no_execution",
        "reason": "validates hash/status private return rows only; never executes, hydrates, replays, or admits",
        "stage12483_compatible": False,
    },
    {
        "stage_ref": "stage12474_private_executor_request_contract",
        "script": "scripts/build_stage12474_private_executor_request_contract.py",
        "classification": "request_contract_no_execution",
        "reason": "handoff contract for executor items; no private proof-slot execution",
        "stage12483_compatible": False,
    },
    {
        "stage_ref": "stage12478_private_return_fill_packet",
        "script": "scripts/build_stage12478_private_return_fill_packet.py",
        "classification": "return_template_no_execution",
        "reason": "emits hash-only fill templates; no raw inspection or proof acquisition",
        "stage12483_compatible": False,
    },
    {
        "stage_ref": "stage12481_private_return_materialization_attempt",
        "script": "scripts/build_stage12481_private_return_materialization_attempt.py",
        "classification": "non_executing_materialization_attempt",
        "reason": "inspects existing locator sidecar structure and blocks incomplete proof bundles",
        "stage12483_compatible": False,
    },
    {
        "stage_ref": "stage12483_private_proof_bundle_acquisition_work_order",
        "script": "scripts/build_stage12483_private_proof_bundle_acquisition_work_order.py",
        "classification": "proof_bundle_work_order_no_execution",
        "reason": "creates proof-bundle work items and shard files; does not acquire proof evidence",
        "stage12483_compatible": False,
    },
]


REQUIRED_EXECUTOR_CAPABILITIES = [
    "consume_stage12483_work_items",
    "inspect_private_locator_sidecars_without_public_raw_leakage",
    "recover_same_source_before_state",
    "run_or_join_before_verifier_failure_output",
    "recover_or_apply_patch_diff",
    "run_or_join_after_or_before_plus_patch_passing_verifier_output",
    "prove_same_verifier_identity_and_relevance",
    "prove_ordered_patch_to_verifier_causality",
    "emit_state_before_and_state_after_semantic_codes",
    "emit_candidate_action_set_and_chosen_action_semantics",
    "emit_stop_continue_semantics",
    "write_stage12468_private_return_file_atomically",
    "emit_hash_status_enum_only_public_returns",
]


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def summary_count(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def classify_scripts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in SCRIPT_CANDIDATES:
        script_path = ROOT / candidate["script"]
        rows.append(
            {
                "record_type": "stage12484_executor_path_candidate_classification_v1",
                "stage_ref": candidate["stage_ref"],
                "script_ref": candidate["script"],
                "script_present": script_path.exists(),
                "script_sha256_24": file_hash(script_path),
                "classification": candidate["classification"],
                "reason_code": candidate["reason"],
                "stage12483_compatible_executor": candidate["stage12483_compatible"],
            }
        )
    return rows


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Stage12484 Private Proof Bundle Executor Readiness Audit",
        "",
        "Decision: no in-repo Stage12483-compatible executor is currently identified.",
        "",
        "This stage is fail-closed. It performed no execution, hydration, replay, admission, training, packaging, or credit assignment.",
        "",
        "Critical path:",
        "1. Implement or run a private proof-bundle executor that consumes Stage12483 work items.",
        "2. It must emit only Stage12468-compatible hash/status private return rows.",
        "3. Rerun Stage12468; only validator-complete returns count toward external repair credit.",
        "",
        "Current counters:",
        f"- Stage12483 work items: {summary['stage12483_work_item_count']}",
        f"- Existing private return file present: {summary['private_return_file_present']}",
        f"- Existing private return row count: {summary['private_return_row_count']}",
        f"- Compatible executor candidates found: {summary['stage12483_compatible_executor_count']}",
        f"- Training allowed: {summary['training_allowed']}",
        "",
        "Required executor capabilities:",
    ]
    lines.extend(f"- {cap}" for cap in REQUIRED_EXECUTOR_CAPABILITIES)
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stage12483_summary = read_json(STAGE12483_SUMMARY)
    stage12468_summary = read_json(STAGE12468_SUMMARY)
    stage12468_contract = read_json(STAGE12468_CONTRACT)
    script_rows = classify_scripts()
    compatible_count = sum(1 for row in script_rows if row["stage12483_compatible_executor"])
    work_item_count = count_jsonl(STAGE12483_WORK_ITEMS) or summary_count(
        stage12483_summary.get("proof_bundle_work_item_count")
    )
    private_return_row_count = count_jsonl(PRIVATE_RETURN_FILE)

    decision = (
        "ready_to_run_stage12483_compatible_executor"
        if compatible_count > 0
        else "blocked_no_stage12483_compatible_executor_identified"
    )
    next_action = (
        "run_or_integrate_identified_private_executor_then_rerun_stage12468"
        if compatible_count > 0
        else "implement_private_proof_bundle_executor_v1_or_invoke_external_executor_for_stage12483_work_items"
    )

    summary = {
        "stage": STAGE,
        "record_type": "stage12484_private_proof_bundle_executor_readiness_audit_summary_v1",
        "decision": decision,
        "next_action": next_action,
        "source_stage_refs": [STAGE12483, STAGE12468],
        "stage12483_work_item_count": work_item_count,
        "stage12483_summary_sha256_24": file_hash(STAGE12483_SUMMARY),
        "stage12483_work_items_sha256_24": file_hash(STAGE12483_WORK_ITEMS),
        "stage12468_summary_sha256_24": file_hash(STAGE12468_SUMMARY),
        "stage12468_contract_sha256_24": file_hash(STAGE12468_CONTRACT),
        "private_return_file_present": PRIVATE_RETURN_FILE.exists(),
        "private_return_row_count": private_return_row_count,
        "stage12483_compatible_executor_count": compatible_count,
        "script_candidate_count": len(script_rows),
        "required_executor_capability_count": len(REQUIRED_EXECUTOR_CAPABILITIES),
        "required_executor_capabilities": REQUIRED_EXECUTOR_CAPABILITIES,
        "blocked_condition_count": 0 if compatible_count > 0 else 1,
        "blocked_conditions": [] if compatible_count > 0 else ["no_stage12483_compatible_executor_script_identified"],
        "schema_issue_count": 0,
        "raw_leak_count": 0,
        "execution_performed_by_stage": False,
        "hydration_performed_by_stage": False,
        "replay_performed_by_stage": False,
        "training_rows_emitted": 0,
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "external_repair_credit_count": 0,
        "stage12468_current_decision": stage12468_summary.get("decision", "missing"),
        "stage12468_required_return_fields": stage12468_contract.get("required_return_fields", []),
        "stage12483_current_decision": stage12483_summary.get("decision", "missing"),
        "audit_note": (
            "This blocks another planning-only loop. The next useful stage must either run a private executor "
            "outside public artifacts or implement private_proof_bundle_executor_v1 with atomic Stage12468 return-file output."
        ),
    }

    write_jsonl(OUT_DIR / "executor_path_candidate_classification.jsonl", script_rows)
    write_json(OUT_DIR / "required_executor_capabilities.json", {"required_executor_capabilities": REQUIRED_EXECUTOR_CAPABILITIES})
    write_json(OUT_DIR / "summary.json", summary)
    write_json(SUMMARY_OUT, summary)
    (OUT_DIR / "PRIVATE_PROOF_BUNDLE_EXECUTOR_READINESS_STAGE12484.md").write_text(
        build_markdown(summary), encoding="utf-8"
    )


if __name__ == "__main__":
    main()

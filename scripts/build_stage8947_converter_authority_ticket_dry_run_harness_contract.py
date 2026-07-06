#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED, apply_diagnostic_gate_fields, audit_diagnostic_ticket_fields
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED, apply_diagnostic_gate_fields, audit_diagnostic_ticket_fields  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8947
NAME = "stage8947_converter_authority_ticket_dry_run_harness_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CONVERTER_AUTHORITY_TICKET_DRY_RUN_HARNESS_CONTRACT_STAGE8947.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "converter_authority_ticket_dry_run_harness_contract.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8946_converter_implementation_audit_skeleton.json"

AUTHORITY_TICKET_SCHEMA = {
    "ticket_id": "required_string",
    "scope": "converter_audit_only_or_materialization",
    "source_checkpoint_path": "required_path_if_load_authorized",
    "target_checkpoint_path": "required_path_if_write_authorized",
    "allowed_operations": "explicit_list",
    "packed_bitnet_semantics_version": "required_string",
    "golden_vector_fixture_hash": "required_hash",
    "rollback_plan": "required_string",
    "runtime_budget": "required_budget_object",
    "human_approval_record": "required_string",
}

DRY_RUN_HARNESS_STEPS = [
    "load_manifest_metadata_only",
    "validate_authority_ticket_schema",
    "validate_diagnostic_gate_fields",
    "validate_path_allowlist_without_opening_checkpoint",
    "validate_tokenizer_hashlock",
    "validate_bitnet_semantics_fixture_hash",
    "validate_expected_shape_delta_schema",
    "validate_checkpoint_write_target_is_unopened",
    "emit_noop_audit_report",
]

FORBIDDEN_WITHOUT_FUTURE_TICKET = [
    "open_source_checkpoint",
    "read_weight_bytes",
    "decode_packed_bitnet",
    "instantiate_model",
    "load_state_dict",
    "write_checkpoint",
    "run_forward",
    "run_training_step",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    placeholder_ticket = apply_diagnostic_gate_fields({
        "ticket_id": None,
        "scope": "not_granted",
        "source_checkpoint_path": None,
        "target_checkpoint_path": None,
        "allowed_operations": [],
        "packed_bitnet_semantics_version": None,
        "golden_vector_fixture_hash": None,
        "rollback_plan": None,
        "runtime_budget": None,
        "human_approval_record": None,
        "authority": dict(AUTHORITY_CLOSED),
    })
    diagnostic_failures = audit_diagnostic_ticket_fields(placeholder_ticket)
    checks = {
        "source_stage8946_passed": load_json(SOURCE_SUMMARY).get("passed") is True,
        "ticket_schema_fields_recorded": len(AUTHORITY_TICKET_SCHEMA) >= 10,
        "dry_run_harness_steps_recorded": len(DRY_RUN_HARNESS_STEPS) >= 9,
        "forbidden_without_ticket_recorded": len(FORBIDDEN_WITHOUT_FUTURE_TICKET) >= 8,
        "diagnostic_gate_fields_present": diagnostic_failures == [],
        "placeholder_ticket_grants_no_operations": placeholder_ticket["allowed_operations"] == [],
        "no_checkpoint_open_authorized": True,
        "no_real_weight_read_authorized": True,
        "no_converter_execution_authorized": True,
        "no_checkpoint_write_authorized": True,
        "no_model_execution_authorized": True,
        "no_training_authorized": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CONVERTER_AUTHORITY_TICKET_DRY_RUN_HARNESS_CONTRACT_ONLY",
        "source_stage": 8946,
        "authority_ticket_schema": AUTHORITY_TICKET_SCHEMA,
        "placeholder_ticket": placeholder_ticket,
        "dry_run_harness_steps": DRY_RUN_HARNESS_STEPS,
        "forbidden_without_future_ticket": FORBIDDEN_WITHOUT_FUTURE_TICKET,
        "checks": checks,
        "metrics": {
            "ticket_schema_fields": len(AUTHORITY_TICKET_SCHEMA),
            "dry_run_harness_steps": len(DRY_RUN_HARNESS_STEPS),
            "forbidden_without_ticket": len(FORBIDDEN_WITHOUT_FUTURE_TICKET),
            "future_ticket_present": False,
            "future_ticket_validated": False,
            "checkpoint_open_authorized": False,
            "real_weight_read_authorized": False,
            "converter_execution_authorized": False,
            "checkpoint_write_authorized": False,
            "model_execution_authorized_now": False,
            "runtime_authorized_flag": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "The converter path now has an explicit future authority-ticket schema and a no-op dry-run harness contract. The placeholder ticket grants no operations; no checkpoint is opened, no weights are read, no converter is executed, no checkpoint is written, no model runs, and no training occurs.",
    }


def validate_contract(contract: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in contract["checks"].items() if value is not True]
    if any((contract.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8946, 8947, 8948, 8949, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if contract["placeholder_ticket"].get("allowed_operations") != []:
        failures.append("placeholder_ticket_allows_operations")
    for key in [
        "future_ticket_present",
        "checkpoint_open_authorized",
        "real_weight_read_authorized",
        "converter_execution_authorized",
        "checkpoint_write_authorized",
        "model_execution_authorized_now",
        "training_authorized",
    ]:
        if contract["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    contract = build_contract(registry)
    failures = validate_contract(contract, registry)
    CONTRACT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": failures,
            **contract["metrics"],
        },
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT))},
        "decision": contract["decision"],
        "next_best_step": "Recover converter implementation acceptance tests as fixture-only specifications. Do not open checkpoints, decode real weights, execute converter code, run models, or train.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8947 Converter Authority Ticket Dry-Run Harness Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines the future converter authority-ticket schema and no-op dry-run harness contract. It does not grant a ticket and does not open checkpoints, read weights, execute converter code, write checkpoints, run models, train, or mine data.",
        "",
        f"Ticket schema fields: `{contract['metrics']['ticket_schema_fields']}`",
        f"Dry-run harness steps: `{contract['metrics']['dry_run_harness_steps']}`",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8947 Converter Authority Ticket Dry-Run Harness Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8947 defines the future authority-ticket schema and no-op dry-run harness contract for converter work. It grants no ticket and keeps checkpoint open/read/write, converter execution, model execution, runtime, and training closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

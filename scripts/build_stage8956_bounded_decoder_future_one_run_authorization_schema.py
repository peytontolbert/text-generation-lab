#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import (
        AUTHORITY_CLOSED,
        apply_diagnostic_gate_fields,
        audit_diagnostic_ticket_fields,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import (  # type: ignore
        AUTHORITY_CLOSED,
        apply_diagnostic_gate_fields,
        audit_diagnostic_ticket_fields,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8956
NAME = "stage8956_bounded_decoder_future_one_run_authorization_schema"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BOUNDED_DECODER_FUTURE_ONE_RUN_AUTHORIZATION_SCHEMA_STAGE8956.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TEMPLATE = OUT_DIR / "future_bounded_decoder_ce_one_run_ticket_template_inactive.json"
AUDIT = OUT_DIR / "future_bounded_decoder_ce_one_run_authorization_schema_audit.json"

SOURCE_SUMMARIES = {
    8954: "stage8954_bounded_decoder_trainer_loss_mask_readiness_refresh",
    8955: "stage8955_bounded_decoder_no_execution_telemetry_gate",
}

REQUIRED_LIMITS = {
    "mode": "bounded_decoder_ce_probe",
    "max_train_rows": 32,
    "max_eval_rows": 16,
    "max_strict_rows": 16,
    "max_steps": 16,
    "batch_size_max": 2,
    "max_decoder_tokens": 768,
    "decoder_ce_weight": 1.0,
    "structured_aux_weight": 0.0,
    "denoise_weight": 0.0,
    "runtime": False,
    "final_checkpoint_export": False,
    "cleanup_checkpoints_after_probe": True,
}

REQUIRED_PRECONDITION_STAGES = [
    "stage8954_bounded_decoder_trainer_loss_mask_readiness_refresh",
    "stage8955_bounded_decoder_no_execution_telemetry_gate",
    "stage8902_diagnostic_promotion_gate",
    "stage8903_diagnostics_closure_audit",
]

DENIED_NOW_OPERATIONS = [
    "materialize_command",
    "run_trainer",
    "run_converter",
    "open_checkpoint",
    "read_tensor_bytes",
    "decode_packed_weight",
    "instantiate_model",
    "run_model_forward",
    "run_training_step",
    "generate_model_output",
    "run_runtime",
    "call_gemma",
    "score_output",
    "emit_source_body",
    "export_checkpoint",
    "promote_model",
    "walk_arxiv",
    "mine_repositories",
]

FUTURE_AUTHORIZATION_REQUIREMENTS = [
    "explicit_user_one_run_request",
    "fresh_pre_execution_audit_passed_after_ticket",
    "manifest_path_audit_passed",
    "loss_mask_rows_match_stage8592_or_fresh_equivalent",
    "telemetry_gate_stage8955_required",
    "post_run_stage8902_diagnostics_required",
    "metrics_interpretation_blocked_until_diagnostics_pass",
    "no_final_checkpoint_export",
    "cleanup_proof_required",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def summary_path(stage_name: str) -> Path:
    return ROOT / "runs/summaries" / f"{stage_name}.json"


def build_inactive_ticket() -> dict[str, Any]:
    ticket = {
        "ticket_id": "future_bounded_decoder_ce_one_run_template__inactive_stage8956",
        "ticket_status": "TEMPLATE_ONLY_INACTIVE",
        "requested_stage": "future_unassigned",
        "requested_stage_name": "future_tiny_bounded_decoder_ce_probe",
        "requested_capability": "tiny_bounded_decoder_ce_probe",
        "requires_explicit_user_authorization": True,
        "requires_fresh_pre_execution_audit": True,
        "requires_manifest_path_audit": True,
        "requires_loss_mask_enforcement_audit": True,
        "requires_post_run_telemetry_gate": True,
        "command_materialized": False,
        "execution_authorized_now": False,
        "allowed_operations_now": [],
        "denied_operations_now": list(DENIED_NOW_OPERATIONS),
        "future_authorization_requirements": list(FUTURE_AUTHORIZATION_REQUIREMENTS),
        "required_precondition_stages": list(REQUIRED_PRECONDITION_STAGES),
        "required_limits": dict(REQUIRED_LIMITS),
        "authority": dict(AUTHORITY_CLOSED),
    }
    return apply_diagnostic_gate_fields(ticket)


def audit_ticket(ticket: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    failures = audit_diagnostic_ticket_fields(ticket)
    for stage, name in SOURCE_SUMMARIES.items():
        summary = load_json(summary_path(name))
        if summary.get("passed") is not True:
            failures.append(f"source_stage_not_passed:{stage}")
    if ticket.get("ticket_status") != "TEMPLATE_ONLY_INACTIVE":
        failures.append("ticket_not_template_only_inactive")
    if ticket.get("execution_authorized_now") is not False:
        failures.append("execution_authorized_now_not_false")
    if ticket.get("allowed_operations_now") != []:
        failures.append("allowed_operations_now_not_empty")
    if ticket.get("command_materialized") is not False:
        failures.append("command_materialized_not_false")
    limits = ticket.get("required_limits") or {}
    for key, value in REQUIRED_LIMITS.items():
        if limits.get(key) != value:
            failures.append(f"limit_mismatch:{key}")
    denied = set(ticket.get("denied_operations_now") or [])
    for operation in DENIED_NOW_OPERATIONS:
        if operation not in denied:
            failures.append(f"operation_not_denied_now:{operation}")
    requirements = set(ticket.get("future_authorization_requirements") or [])
    for requirement in FUTURE_AUTHORIZATION_REQUIREMENTS:
        if requirement not in requirements:
            failures.append(f"future_requirement_missing:{requirement}")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8955, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(int(authority_counts.get(key, 0)) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    return {
        "passed": not failures,
        "failures": failures,
        "ticket_contract_failures": audit_diagnostic_ticket_fields(ticket),
        "denied_operations_now": len(ticket.get("denied_operations_now") or []),
        "future_authorization_requirements": len(ticket.get("future_authorization_requirements") or []),
        "limits_checked": len(REQUIRED_LIMITS),
        "registry_latest_stage_observed": latest,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    ticket = build_inactive_ticket()
    audit = audit_ticket(ticket, registry)
    TEMPLATE.write_text(json.dumps(ticket, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": audit["failures"],
            "ticket_contract_failures": len(audit["ticket_contract_failures"]),
            "denied_operations_now": audit["denied_operations_now"],
            "future_authorization_requirements": audit["future_authorization_requirements"],
            "limits_checked": audit["limits_checked"],
            "command_materialized": False,
            "execution_authorized_now": False,
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "data_mining_authorized": False,
        },
        "artifacts": {"ticket_template": str(TEMPLATE.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT))},
        "decision": "Inactive future one-run authorization schema for a tiny bounded decoder CE probe is recovered. It grants no operations now and requires explicit user authorization, fresh pre-execution audit, manifest/loss-mask checks, Stage8955 telemetry, and Stage8902 diagnostics before any future metrics can be interpreted.",
        "next_best_step": "Return to compiler/dataset readiness gaps or wait for an explicit future one-run request. Do not run bounded decoder CE from this template.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8956 Bounded Decoder Future One-Run Authorization Schema",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage creates an inactive/template schema for a possible future tiny bounded decoder CE one-run ticket. It does not authorize execution.",
        "",
        f"Denied operations now: `{audit['denied_operations_now']}`",
        f"Future requirements: `{audit['future_authorization_requirements']}`",
        f"Execution authorized now: `{summary['metrics']['execution_authorized_now']}`",
        "",
        "No command is materialized. No model execution, converter execution, runtime, mining, decoder CE, denoise CE, checkpoint export, or training is authorized.",
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
    marker = "## Stage8956 Bounded Decoder Future One-Run Authorization Schema"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8956 adds an inactive/template one-run authorization schema for a future tiny bounded decoder CE probe. It grants no operation now and requires explicit user authorization, fresh pre-execution audit, Stage8955 telemetry, and Stage8902 diagnostics before any future metrics can be interpreted.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

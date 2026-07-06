#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8906
NAME = "stage8906_diagnostic_gate_ticket_integration"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DIAGNOSTIC_GATE_TICKET_INTEGRATION_STAGE8906.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TEMPLATE_PATH = OUT_DIR / "future_live_probe_ticket_diagnostic_gate_template.json"
AUDIT_PATH = OUT_DIR / "diagnostic_gate_ticket_integration_audit.json"

SOURCE_SUMMARIES = [
    ROOT / "runs/summaries/stage8887_stage8890_inactive_execution_ticket_gate_audit.json",
    ROOT / "runs/summaries/stage8895_stage8890_live_authorization_checklist.json",
    ROOT / "runs/summaries/stage8902_diagnostic_promotion_gate.json",
    ROOT / "runs/summaries/stage8903_diagnostics_closure_audit.json",
]

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}

FORBIDDEN_WITHOUT_DIAGNOSTICS = [
    "interpret_model_metrics",
    "claim_training_quality",
    "claim_decoder_quality",
    "promote_probe",
    "export_checkpoint",
    "merge_controller",
    "open_runtime",
    "open_source_or_body_emission",
    "use_hidden_or_locked_eval_for_tuning",
]

REQUIRED_TICKET_FIELDS = [
    "ticket_status",
    "execution_authorized_now",
    "allowed_operations_now",
    "post_run_diagnostic_gate_required",
    "post_run_diagnostic_gate_stage",
    "post_run_artifact_contract_stage",
    "diagnostic_closure_stage",
    "promotion_blocked_until_diagnostics_pass",
    "metrics_interpretation_blocked_until_diagnostics_pass",
    "forbidden_without_passing_diagnostics",
    "authority",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def authority_is_closed(authority: dict[str, Any]) -> bool:
    return all(authority.get(key) is False for key in AUTHORITY_CLOSED)


def build_future_ticket_template() -> dict[str, Any]:
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "ticket_status": "TEMPLATE_ONLY_INACTIVE",
        "execution_authorized_now": False,
        "allowed_operations_now": [],
        "post_run_diagnostic_gate_required": True,
        "post_run_diagnostic_gate_stage": "stage8902_diagnostic_promotion_gate",
        "post_run_artifact_contract_stage": "stage8862_native_probe_interpretability_artifact_contract",
        "diagnostic_closure_stage": "stage8903_diagnostics_closure_audit",
        "promotion_blocked_until_diagnostics_pass": True,
        "metrics_interpretation_blocked_until_diagnostics_pass": True,
        "required_modes": ["structured_aux_probe", "bounded_decoder_ce_probe"],
        "required_future_run_artifact_classes": [
            "row_field_logits_or_row_token_loss",
            "row_field_losses_or_decoder_token_loss_maps",
            "row_gradient_norms",
            "activation_summary",
            "row_dynamics_history",
            "module_delta_norms",
            "failure_bucket_card",
            "cleanup_proof",
        ],
        "forbidden_without_passing_diagnostics": FORBIDDEN_WITHOUT_DIAGNOSTICS,
        "diagnostic_gate_enforcement_points": [
            "after_probe_artifact_write",
            "before_metric_interpretation",
            "before_checkpoint_export",
            "before_controller_merge",
            "before_any_promotion_claim",
        ],
        "authority": AUTHORITY_CLOSED,
    }


def audit_ticket_template(ticket: dict[str, Any], source_cards: list[dict[str, Any]], registry: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    missing = [field for field in REQUIRED_TICKET_FIELDS if field not in ticket]
    if missing:
        failures.append(f"missing_ticket_fields:{missing}")
    if ticket.get("ticket_status") != "TEMPLATE_ONLY_INACTIVE":
        failures.append("ticket_not_template_only_inactive")
    if ticket.get("execution_authorized_now") is not False:
        failures.append("execution_authorized_now_not_false")
    if ticket.get("allowed_operations_now") != []:
        failures.append("allowed_operations_now_not_empty")
    if ticket.get("post_run_diagnostic_gate_required") is not True:
        failures.append("post_run_diagnostic_gate_not_required")
    if ticket.get("post_run_diagnostic_gate_stage") != "stage8902_diagnostic_promotion_gate":
        failures.append("wrong_diagnostic_gate_stage")
    if ticket.get("post_run_artifact_contract_stage") != "stage8862_native_probe_interpretability_artifact_contract":
        failures.append("wrong_artifact_contract_stage")
    if ticket.get("diagnostic_closure_stage") != "stage8903_diagnostics_closure_audit":
        failures.append("wrong_diagnostic_closure_stage")
    if ticket.get("promotion_blocked_until_diagnostics_pass") is not True:
        failures.append("promotion_not_blocked_until_diagnostics")
    if ticket.get("metrics_interpretation_blocked_until_diagnostics_pass") is not True:
        failures.append("metrics_interpretation_not_blocked_until_diagnostics")
    if set(ticket.get("forbidden_without_passing_diagnostics", [])) != set(FORBIDDEN_WITHOUT_DIAGNOSTICS):
        failures.append("forbidden_without_diagnostics_mismatch")
    if not authority_is_closed(ticket.get("authority", {})):
        failures.append("ticket_authority_open")

    for source in source_cards:
        name = source.get("stage_name") or source.get("name") or "unknown"
        if source.get("passed") is not True:
            failures.append(f"source_not_passed:{name}")
        if not authority_is_closed(source.get("authority", {})):
            failures.append(f"source_authority_open:{name}")

    metrics = registry.get("metrics") or {}
    latest = int(metrics.get("latest_stage", -1))
    if latest not in {8905, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    authority_counts = metrics.get("authority_counts") or {}
    if any(int(authority_counts.get(key, 0)) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")

    return {
        "passed": not failures,
        "failures": failures,
        "required_ticket_fields": REQUIRED_TICKET_FIELDS,
        "source_summaries_checked": len(source_cards),
        "source_summaries_passing": sum(1 for source in source_cards if source.get("passed") is True),
        "forbidden_without_diagnostics_count": len(FORBIDDEN_WITHOUT_DIAGNOSTICS),
        "registry_latest_stage_observed": latest,
    }


def build_card(ticket: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": audit["failures"],
            "source_summaries_checked": audit["source_summaries_checked"],
            "source_summaries_passing": audit["source_summaries_passing"],
            "required_ticket_fields": len(REQUIRED_TICKET_FIELDS),
            "forbidden_without_diagnostics_count": audit["forbidden_without_diagnostics_count"],
            "post_run_diagnostic_gate_required": ticket["post_run_diagnostic_gate_required"],
            "promotion_blocked_until_diagnostics_pass": ticket["promotion_blocked_until_diagnostics_pass"],
            "metrics_interpretation_blocked_until_diagnostics_pass": ticket["metrics_interpretation_blocked_until_diagnostics_pass"],
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "data_mining_authorized": False,
        },
        "artifacts": {
            "ticket_template": str(TEMPLATE_PATH.relative_to(ROOT)),
            "audit": str(AUDIT_PATH.relative_to(ROOT)),
        },
        "decision": "Future live probe tickets must embed the diagnostic promotion gate before any metrics interpretation or promotion. This stage is template-only and opens no execution." if audit["passed"] else "Diagnostic gate ticket integration failed.",
        "next_best_step": "Patch future probe/ticket builders to emit these diagnostic-gate fields by construction; keep execution/training/decoder CE closed until a separate explicit one-run ticket exists.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def write_doc(card: dict[str, Any]) -> None:
    DOC.write_text("\n".join([
        "# Stage8906 Diagnostic Gate Ticket Integration",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This no-execution stage connects the diagnostic promotion gate to any future live probe ticket.",
        "",
        "Required rule: after any future authorized probe writes artifacts, Stage8902 diagnostic promotion checks must pass before metrics can be interpreted, checkpoints exported, controller merge considered, or promotion claimed.",
        "",
        "Current authority remains closed: no model execution, training, decoder CE, denoise CE, runtime, mining, source/body emission, Gemma, harness, scoring, controller merge, or promotion.",
        "",
        "Next implementation target: future ticket/probe builders should emit the diagnostic-gate fields by construction, then tests should reject tickets that omit them.",
        "",
    ]), encoding="utf-8")


def update_registry(card: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": card["passed"],
        "path": str(SUMMARY),
        "authority": AUTHORITY_CLOSED,
        "next_best_step": card["next_best_step"],
    })
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": card["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def update_spine() -> None:
    marker = "## Stage8906 Diagnostic Gate Ticket Integration"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker in spine_text:
        return
    SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
        marker,
        "",
        "Stage8906 connects the diagnostics closure path to future live authorization tickets: every future probe ticket must require Stage8902 post-run diagnostic promotion checks before metrics interpretation, checkpoint export, controller merge, or promotion.",
        "",
    ]), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_cards = [load_json(path) for path in SOURCE_SUMMARIES]
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    ticket = build_future_ticket_template()
    audit = audit_ticket_template(ticket, source_cards, registry)
    card = build_card(ticket, audit)
    TEMPLATE_PATH.write_text(json.dumps(ticket, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    AUDIT_PATH.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(card)
    update_registry(card)
    update_spine()
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()

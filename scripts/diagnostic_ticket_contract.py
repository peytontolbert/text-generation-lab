from __future__ import annotations

from typing import Any

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

REQUIRED_DIAGNOSTIC_TICKET_FIELDS = [
    "post_run_diagnostic_gate_required",
    "post_run_diagnostic_gate_stage",
    "post_run_artifact_contract_stage",
    "diagnostic_closure_stage",
    "promotion_blocked_until_diagnostics_pass",
    "metrics_interpretation_blocked_until_diagnostics_pass",
    "forbidden_without_passing_diagnostics",
]

DIAGNOSTIC_GATE_FIELDS = {
    "post_run_diagnostic_gate_required": True,
    "post_run_diagnostic_gate_stage": "stage8902_diagnostic_promotion_gate",
    "post_run_artifact_contract_stage": "stage8862_native_probe_interpretability_artifact_contract",
    "diagnostic_closure_stage": "stage8903_diagnostics_closure_audit",
    "promotion_blocked_until_diagnostics_pass": True,
    "metrics_interpretation_blocked_until_diagnostics_pass": True,
    "forbidden_without_passing_diagnostics": list(FORBIDDEN_WITHOUT_DIAGNOSTICS),
}


def diagnostic_gate_fields() -> dict[str, Any]:
    return {key: (list(value) if isinstance(value, list) else value) for key, value in DIAGNOSTIC_GATE_FIELDS.items()}


def apply_diagnostic_gate_fields(ticket: dict[str, Any]) -> dict[str, Any]:
    merged = dict(ticket)
    merged.update(diagnostic_gate_fields())
    return merged


def authority_is_closed(authority: dict[str, Any]) -> bool:
    return all(authority.get(key) is False for key in AUTHORITY_CLOSED)


def audit_diagnostic_ticket_fields(ticket: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for field in REQUIRED_DIAGNOSTIC_TICKET_FIELDS:
        if field not in ticket:
            failures.append(f"missing:{field}")
    if ticket.get("post_run_diagnostic_gate_required") is not True:
        failures.append("post_run_diagnostic_gate_not_required")
    if ticket.get("post_run_diagnostic_gate_stage") != DIAGNOSTIC_GATE_FIELDS["post_run_diagnostic_gate_stage"]:
        failures.append("wrong_post_run_diagnostic_gate_stage")
    if ticket.get("post_run_artifact_contract_stage") != DIAGNOSTIC_GATE_FIELDS["post_run_artifact_contract_stage"]:
        failures.append("wrong_post_run_artifact_contract_stage")
    if ticket.get("diagnostic_closure_stage") != DIAGNOSTIC_GATE_FIELDS["diagnostic_closure_stage"]:
        failures.append("wrong_diagnostic_closure_stage")
    if ticket.get("promotion_blocked_until_diagnostics_pass") is not True:
        failures.append("promotion_not_blocked_until_diagnostics")
    if ticket.get("metrics_interpretation_blocked_until_diagnostics_pass") is not True:
        failures.append("metrics_interpretation_not_blocked_until_diagnostics")
    if set(ticket.get("forbidden_without_passing_diagnostics", [])) != set(FORBIDDEN_WITHOUT_DIAGNOSTICS):
        failures.append("forbidden_without_diagnostics_mismatch")
    if "authority" in ticket and not authority_is_closed(ticket.get("authority", {})):
        failures.append("authority_open")
    return failures

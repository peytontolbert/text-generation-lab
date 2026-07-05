from __future__ import annotations

from collections import Counter
from typing import Any

try:
    from scripts.model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED

LOSS_MASK_CLOSED = {
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
    "heldout_eval_metric": False,
}

REQUIRED_TICKET_FIELDS = [
    "ticket_id",
    "requested_stage",
    "request_scope",
    "allowed_operations",
    "denied_operations",
    "artifact_scope",
    "dataset_scope",
    "checkpoint_scope",
    "expiry_policy",
    "reviewer",
    "audit_log_ref",
]

GATED_OPERATIONS = [
    "load_checkpoint",
    "run_forward",
    "decode_tokens",
    "write_model_output_artifact",
    "compute_decoder_ce",
    "compute_denoise_ce",
    "run_runtime",
    "call_gemma",
    "score_output",
    "emit_source_body",
    "promote_model",
]

REQUIRED_DENIALS = GATED_OPERATIONS

REQUIRED_ARTIFACT_SCOPE_FIELDS = [
    "output_root",
    "allowed_write_kinds",
    "forbidden_write_kinds",
    "max_rows",
    "no_overwrite_existing",
]

FORBIDDEN_WRITE_KINDS = [
    "model_output_packet",
    "generated_text",
    "runtime_result",
    "gemma_score",
    "decoder_ce_loss",
    "source_body",
    "promotion_marker",
]


def build_authority_ticket_schema_rows(runner_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in runner_rows:
        contract = row.get("runner_contract") or {}
        if any(contract.values()):
            continue
        rows.append({
            "row_id": f"stage8840_authority_ticket::{row.get('row_id')}",
            "semantic_key": f"{row.get('split')}:authority_ticket_schema:{row.get('row_id')}",
            "source_stage": "stage8840_from_stage8837_runner_static_design",
            "source_row_ref": {"row_id": row.get("row_id"), "split": row.get("split")},
            "split": row.get("split"),
            "objective_family": "future_model_output_capture_authority_ticket_schema",
            "route": "AUTHORITY_TICKET_SCHEMA_ONLY",
            "ticket_schema": {
                "schema_name": "model_output_capture_authority_ticket_v1",
                "required_ticket_fields": REQUIRED_TICKET_FIELDS,
                "gated_operations": GATED_OPERATIONS,
                "default_allowed_operations": [],
                "default_denied_operations": REQUIRED_DENIALS,
                "required_artifact_scope_fields": REQUIRED_ARTIFACT_SCOPE_FIELDS,
                "forbidden_write_kinds": FORBIDDEN_WRITE_KINDS,
                "requires_human_or_policy_review": True,
                "requires_explicit_stage_match": True,
                "requires_expiry": True,
            },
            "example_closed_ticket": {
                "ticket_id": "closed-design-placeholder",
                "requested_stage": "future",
                "request_scope": "schema_only",
                "allowed_operations": [],
                "denied_operations": REQUIRED_DENIALS,
                "artifact_scope": {
                    "output_root": "runs/local/artifacts/future_authorized_only",
                    "allowed_write_kinds": [],
                    "forbidden_write_kinds": FORBIDDEN_WRITE_KINDS,
                    "max_rows": 0,
                    "no_overwrite_existing": True,
                },
                "dataset_scope": "none",
                "checkpoint_scope": "none",
                "expiry_policy": "immediate_closed_placeholder",
                "reviewer": "not_authorized",
                "audit_log_ref": "not_created",
            },
            "authority": dict(AUTHORITY_CLOSED),
            "loss_mask": dict(LOSS_MASK_CLOSED),
            "anti_cheat": {
                "opens_model_execution": False,
                "opens_decode": False,
                "opens_ce": False,
                "opens_runtime": False,
                "opens_gemma": False,
                "opens_scoring": False,
                "opens_source_body": False,
                "opens_promotion": False,
                "contains_model_output": False,
            },
            "hard_blockers": [
                "actual_authority_ticket_not_issued",
                "checkpoint_load_not_authorized",
                "model_forward_not_authorized",
                "decode_not_authorized",
                "artifact_write_not_authorized",
            ],
        })
    return rows


def build_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_ticket_field_rows = 0
    missing_gated_operation_rows = 0
    missing_denial_rows = 0
    missing_artifact_scope_rows = 0
    forbidden_write_guard_rows = 0
    allowed_operation_rows = 0
    authority_open_rows = 0
    loss_open_rows = 0
    opening_rows = 0
    bad_route_rows = 0
    for row in rows:
        schema = row.get("ticket_schema") or {}
        ticket = row.get("example_closed_ticket") or {}
        artifact_scope = ticket.get("artifact_scope") or {}
        if set(REQUIRED_TICKET_FIELDS) - set(schema.get("required_ticket_fields", [])):
            missing_ticket_field_rows += 1
        if set(GATED_OPERATIONS) - set(schema.get("gated_operations", [])):
            missing_gated_operation_rows += 1
        if set(REQUIRED_DENIALS) - set(ticket.get("denied_operations", [])):
            missing_denial_rows += 1
        if set(REQUIRED_ARTIFACT_SCOPE_FIELDS) - set(artifact_scope):
            missing_artifact_scope_rows += 1
        if set(FORBIDDEN_WRITE_KINDS) - set(artifact_scope.get("forbidden_write_kinds", [])):
            forbidden_write_guard_rows += 1
        if ticket.get("allowed_operations"):
            allowed_operation_rows += 1
        if any((row.get("authority") or {}).values()):
            authority_open_rows += 1
        if any((row.get("loss_mask") or {}).values()):
            loss_open_rows += 1
        if any((row.get("anti_cheat") or {}).values()):
            opening_rows += 1
        if row.get("route") != "AUTHORITY_TICKET_SCHEMA_ONLY":
            bad_route_rows += 1
    failing = {
        "missing_ticket_field_rows": missing_ticket_field_rows,
        "missing_gated_operation_rows": missing_gated_operation_rows,
        "missing_denial_rows": missing_denial_rows,
        "missing_artifact_scope_rows": missing_artifact_scope_rows,
        "forbidden_write_guard_rows": forbidden_write_guard_rows,
        "allowed_operation_rows": allowed_operation_rows,
        "authority_open_rows": authority_open_rows,
        "loss_open_rows": loss_open_rows,
        "opening_rows": opening_rows,
        "bad_route_rows": bad_route_rows,
    }
    return {
        "rows": len(rows),
        "split_counts": dict(sorted(Counter(row.get("split") for row in rows).items())),
        **failing,
        "authority_ticket_schema_ready_rows": len(rows) if rows and all(value == 0 for value in failing.values()) else 0,
        "ready_for_model_execution": False,
        "ready_for_decoder_ce": False,
        "passed": bool(rows) and all(value == 0 for value in failing.values()),
    }

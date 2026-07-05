from __future__ import annotations

from collections import Counter
from typing import Any

try:
    from scripts.authority_ticket_schema_builder import (
        FORBIDDEN_WRITE_KINDS,
        GATED_OPERATIONS,
        REQUIRED_ARTIFACT_SCOPE_FIELDS,
        REQUIRED_TICKET_FIELDS,
    )
except ModuleNotFoundError:
    from authority_ticket_schema_builder import (
        FORBIDDEN_WRITE_KINDS,
        GATED_OPERATIONS,
        REQUIRED_ARTIFACT_SCOPE_FIELDS,
        REQUIRED_TICKET_FIELDS,
    )


def audit_ticket_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_ticket_field_rows = 0
    missing_gated_operation_rows = 0
    missing_denial_rows = 0
    missing_artifact_scope_rows = 0
    missing_forbidden_write_rows = 0
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
        if set(GATED_OPERATIONS) - set(ticket.get("denied_operations", [])):
            missing_denial_rows += 1
        if set(REQUIRED_ARTIFACT_SCOPE_FIELDS) - set(artifact_scope):
            missing_artifact_scope_rows += 1
        if set(FORBIDDEN_WRITE_KINDS) - set(artifact_scope.get("forbidden_write_kinds", [])):
            missing_forbidden_write_rows += 1
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
        "missing_forbidden_write_rows": missing_forbidden_write_rows,
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
        "ticket_gate_pass_rows": len(rows) if rows and all(value == 0 for value in failing.values()) else 0,
        "ready_for_model_execution": False,
        "ready_for_decoder_ce": False,
        "passed": bool(rows) and all(value == 0 for value in failing.values()),
    }

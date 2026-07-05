from __future__ import annotations

from collections import Counter
from typing import Any

try:
    from scripts.model_output_capture_preflight_design_builder import BLOCKED_OPERATIONS, REQUIRED_PREFLIGHT_FIELDS
except ModuleNotFoundError:
    from model_output_capture_preflight_design_builder import BLOCKED_OPERATIONS, REQUIRED_PREFLIGHT_FIELDS


def audit_preflight_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    authority_open_rows = 0
    loss_open_rows = 0
    missing_preflight_field_rows = 0
    missing_blocked_operation_rows = 0
    model_execution_ready_rows = 0
    decoder_ce_ready_rows = 0
    probe_ready_rows = 0
    model_output_rows = 0
    bad_route_rows = 0
    for row in rows:
        clean = row.get("clean_state") or {}
        if any((row.get("authority") or {}).values()):
            authority_open_rows += 1
        if any((row.get("loss_mask") or {}).values()):
            loss_open_rows += 1
        if set(REQUIRED_PREFLIGHT_FIELDS) - set(clean.get("required_preflight_fields", [])):
            missing_preflight_field_rows += 1
        if set(BLOCKED_OPERATIONS) - set(clean.get("blocked_operations", [])):
            missing_blocked_operation_rows += 1
        if clean.get("ready_for_model_execution") is True:
            model_execution_ready_rows += 1
        if clean.get("ready_for_decoder_ce") is True:
            decoder_ce_ready_rows += 1
        if clean.get("probe_ready") is True:
            probe_ready_rows += 1
        if (row.get("anti_cheat") or {}).get("contains_model_output") is True:
            model_output_rows += 1
        if row.get("route") != "CAPTURE_PREFLIGHT_DESIGN_ONLY":
            bad_route_rows += 1
    failing = {
        "authority_open_rows": authority_open_rows,
        "loss_open_rows": loss_open_rows,
        "missing_preflight_field_rows": missing_preflight_field_rows,
        "missing_blocked_operation_rows": missing_blocked_operation_rows,
        "model_execution_ready_rows": model_execution_ready_rows,
        "decoder_ce_ready_rows": decoder_ce_ready_rows,
        "probe_ready_rows": probe_ready_rows,
        "model_output_rows": model_output_rows,
        "bad_route_rows": bad_route_rows,
    }
    return {
        "rows": len(rows),
        "split_counts": dict(sorted(Counter(row.get("split") for row in rows).items())),
        "argument_counts": dict(sorted(Counter((row.get("corrupted_state") or {}).get("bounded_argument_type") for row in rows).items())),
        **failing,
        "static_gate_pass_rows": len(rows) if all(value == 0 for value in failing.values()) else 0,
        "passed": bool(rows) and all(value == 0 for value in failing.values()),
    }

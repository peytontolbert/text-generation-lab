from __future__ import annotations

from collections import Counter
from typing import Any

try:
    from scripts.model_output_packet_telemetry_contract_builder import (
        AUTHORITY_CLOSED,
        FORBIDDEN_PACKET_FIELDS,
        REQUIRED_CHECKS,
        REQUIRED_PACKET_FIELDS,
        REQUIRED_TELEMETRY,
    )
except ModuleNotFoundError:
    from model_output_packet_telemetry_contract_builder import (
        AUTHORITY_CLOSED,
        FORBIDDEN_PACKET_FIELDS,
        REQUIRED_CHECKS,
        REQUIRED_PACKET_FIELDS,
        REQUIRED_TELEMETRY,
    )


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_field = []
    missing_check = []
    missing_telemetry = []
    forbidden_missing = []
    authority_open = []
    loss_open = []
    probe_ready = []
    ce_eligible = []
    bad_route = []
    for row in rows:
        row_id = row.get("row_id")
        clean = row.get("clean_state") or {}
        authority = row.get("authority") or {}
        loss_mask = row.get("loss_mask") or {}
        if set(REQUIRED_PACKET_FIELDS) - set(clean.get("required_packet_fields", [])):
            missing_field.append(row_id)
        if set(REQUIRED_CHECKS) - set(clean.get("required_checks", [])):
            missing_check.append(row_id)
        if set(REQUIRED_TELEMETRY) - set(clean.get("required_telemetry", [])):
            missing_telemetry.append(row_id)
        if set(FORBIDDEN_PACKET_FIELDS) - set(clean.get("forbidden_packet_fields", [])):
            forbidden_missing.append(row_id)
        if any(authority.values()):
            authority_open.append(row_id)
        if any(loss_mask.values()):
            loss_open.append(row_id)
        if clean.get("probe_ready") is True:
            probe_ready.append(row_id)
        if clean.get("decoder_ce_eligible_now") is True:
            ce_eligible.append(row_id)
        if row.get("route") != "PACKET_SCHEMA_TELEMETRY_CONTRACT_ONLY":
            bad_route.append(row_id)
    failing = {
        "missing_required_field_rows": len(missing_field),
        "missing_required_check_rows": len(missing_check),
        "missing_required_telemetry_rows": len(missing_telemetry),
        "missing_forbidden_field_guard_rows": len(forbidden_missing),
        "authority_open_rows": len(authority_open),
        "loss_open_rows": len(loss_open),
        "unexpected_probe_ready_rows": len(probe_ready),
        "unexpected_decoder_ce_eligible_rows": len(ce_eligible),
        "bad_route_rows": len(bad_route),
    }
    return {
        "rows": len(rows),
        "split_counts": dict(sorted(Counter(row.get("split") for row in rows).items())),
        "argument_counts": dict(sorted(Counter((row.get("corrupted_state") or {}).get("bounded_argument_type") for row in rows).items())),
        **failing,
        "contract_ready_rows": len(rows) if all(value == 0 for value in failing.values()) else 0,
        "passed": bool(rows) and all(value == 0 for value in failing.values()),
        "authority": AUTHORITY_CLOSED,
    }

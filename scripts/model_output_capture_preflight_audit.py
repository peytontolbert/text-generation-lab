from __future__ import annotations

from collections import Counter
from typing import Any

try:
    from scripts.model_output_capture_preflight_builder import CAPTURE_CHECKS, REQUIRED_CAPTURE_FIELDS, TELEMETRY_HOOKS
    from scripts.model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from model_output_capture_preflight_builder import CAPTURE_CHECKS, REQUIRED_CAPTURE_FIELDS, TELEMETRY_HOOKS
    from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_field_rows = 0
    missing_check_rows = 0
    missing_hook_rows = 0
    authority_open_rows = 0
    loss_open_rows = 0
    model_output_rows = 0
    artifact_write_rows = 0
    execution_allowed_rows = 0
    bad_route_rows = 0
    for row in rows:
        preflight = row.get("preflight") or {}
        capture = row.get("capture_contract") or {}
        if set(REQUIRED_CAPTURE_FIELDS) - set(preflight):
            missing_field_rows += 1
        if set(CAPTURE_CHECKS) - set(preflight.get("capture_checks", [])):
            missing_check_rows += 1
        if set(TELEMETRY_HOOKS) - set(preflight.get("telemetry_hooks", [])):
            missing_hook_rows += 1
        if any((row.get("authority") or {}).values()) or any((preflight.get("authority") or {}).values()):
            authority_open_rows += 1
        if any((row.get("loss_mask") or {}).values()):
            loss_open_rows += 1
        if (row.get("anti_cheat") or {}).get("contains_model_output") is True:
            model_output_rows += 1
        if capture.get("writes_model_output_artifact_now") is True:
            artifact_write_rows += 1
        if any(capture.get(key) is True for key in ["model_execution_allowed", "decoder_ce_allowed", "runtime_allowed", "gemma_scoring_allowed", "harness_allowed"]):
            execution_allowed_rows += 1
        if row.get("route") != "CAPTURE_PREFLIGHT_DESIGN_ONLY":
            bad_route_rows += 1
    failing = {
        "missing_field_rows": missing_field_rows,
        "missing_check_rows": missing_check_rows,
        "missing_hook_rows": missing_hook_rows,
        "authority_open_rows": authority_open_rows,
        "loss_open_rows": loss_open_rows,
        "model_output_rows": model_output_rows,
        "artifact_write_rows": artifact_write_rows,
        "execution_allowed_rows": execution_allowed_rows,
        "bad_route_rows": bad_route_rows,
    }
    return {
        "rows": len(rows),
        "split_counts": dict(sorted(Counter(row.get("split") for row in rows).items())),
        **failing,
        "audit_ready_rows": len(rows) if rows and all(value == 0 for value in failing.values()) else 0,
        "ready_for_model_execution": False,
        "ready_for_decoder_ce": False,
        "authority": AUTHORITY_CLOSED,
        "passed": bool(rows) and all(value == 0 for value in failing.values()),
    }

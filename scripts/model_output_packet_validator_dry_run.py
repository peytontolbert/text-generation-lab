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


def build_placeholder_packets(contract_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for row in contract_rows:
        clean = row.get("clean_state") or {}
        corrupted = row.get("corrupted_state") or {}
        if clean.get("packet_contract") != "model_output_packet_telemetry_v1":
            continue
        packet = {
            "packet_id": f"synthetic_packet::{row.get('row_id')}",
            "eval_design_row_id": (row.get("source_row_ref") or {}).get("row_id"),
            "split": row.get("split"),
            "objective_family": "future_probe_packet_validator_dry_run",
            "prompt_packet_ref": f"synthetic://prompt/{row.get('row_id')}",
            "generated_text_ref": "synthetic://placeholder/no_model_output",
            "surface_type": "bounded_decoder_surface_placeholder",
            "bounded_argument_type": corrupted.get("bounded_argument_type"),
            "decode_budget": {"max_new_tokens": 0, "model_execution": False},
            "checks": {name: "synthetic_not_run" for name in REQUIRED_CHECKS},
            "telemetry": {name: "synthetic_not_recorded" for name in REQUIRED_TELEMETRY},
            "authority": dict(AUTHORITY_CLOSED),
            "anti_cheat": {
                "contains_model_output": False,
                "contains_target_text": False,
                "contains_runtime_result": False,
                "contains_gemma_score": False,
                "contains_hidden_eval_answer": False,
                "contains_source_body_text": False,
            },
        }
        packets.append(packet)
    return packets


def validate_packets(packets: list[dict[str, Any]]) -> dict[str, Any]:
    missing_field_rows = 0
    missing_check_rows = 0
    missing_telemetry_rows = 0
    forbidden_field_rows = 0
    authority_open_rows = 0
    model_output_rows = 0
    for packet in packets:
        if set(REQUIRED_PACKET_FIELDS) - set(packet):
            missing_field_rows += 1
        if set(REQUIRED_CHECKS) - set((packet.get("checks") or {}).keys()):
            missing_check_rows += 1
        if set(REQUIRED_TELEMETRY) - set((packet.get("telemetry") or {}).keys()):
            missing_telemetry_rows += 1
        if any(field in packet for field in FORBIDDEN_PACKET_FIELDS):
            forbidden_field_rows += 1
        if any((packet.get("authority") or {}).values()):
            authority_open_rows += 1
        if (packet.get("anti_cheat") or {}).get("contains_model_output") is True:
            model_output_rows += 1
    failing = {
        "missing_field_rows": missing_field_rows,
        "missing_check_rows": missing_check_rows,
        "missing_telemetry_rows": missing_telemetry_rows,
        "forbidden_field_rows": forbidden_field_rows,
        "authority_open_rows": authority_open_rows,
        "model_output_rows": model_output_rows,
    }
    return {
        "rows": len(packets),
        "split_counts": dict(sorted(Counter(packet.get("split") for packet in packets).items())),
        "argument_counts": dict(sorted(Counter(packet.get("bounded_argument_type") for packet in packets).items())),
        **failing,
        "valid_packet_rows": len(packets) if all(value == 0 for value in failing.values()) else 0,
        "passed": bool(packets) and all(value == 0 for value in failing.values()),
    }

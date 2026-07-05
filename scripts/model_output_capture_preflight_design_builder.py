from __future__ import annotations

from collections import Counter
from typing import Any

try:
    from scripts.model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED, REQUIRED_CHECKS, REQUIRED_TELEMETRY
except ModuleNotFoundError:
    from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED, REQUIRED_CHECKS, REQUIRED_TELEMETRY

LOSS_MASK_CLOSED = {
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
    "heldout_eval_metric": False,
}

REQUIRED_PREFLIGHT_FIELDS = [
    "preflight_id",
    "packet_contract",
    "placeholder_packet_ref",
    "future_capture_inputs",
    "future_capture_outputs",
    "required_checks",
    "required_telemetry",
    "blocked_operations",
    "authority",
]

BLOCKED_OPERATIONS = [
    "load_model_checkpoint",
    "run_model_forward",
    "decode_tokens",
    "compute_decoder_ce",
    "run_runtime",
    "call_gemma",
    "score_output",
    "emit_source_body",
    "promote_model",
]

FUTURE_CAPTURE_INPUTS = [
    "validated_prompt_packet_ref",
    "checkpoint_ref",
    "tokenizer_ref",
    "decode_config_ref",
    "authority_ticket_ref",
]

FUTURE_CAPTURE_OUTPUTS = [
    "model_output_packet_ref",
    "generated_text_ref",
    "decode_telemetry_ref",
    "check_results_ref",
    "authority_audit_ref",
]


def build_preflight_rows(packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for packet in packets:
        anti = packet.get("anti_cheat") or {}
        if anti.get("contains_model_output") is True:
            continue
        rows.append({
            "row_id": f"stage8831_capture_preflight::{packet.get('packet_id')}",
            "semantic_key": f"{packet.get('split')}:authority_closed_model_output_capture_preflight:{packet.get('packet_id')}",
            "source_stage": "stage8831_from_stage8828_synthetic_packet_validator",
            "source_row_ref": {
                "packet_id": packet.get("packet_id"),
                "split": packet.get("split"),
            },
            "objective_family": "authority_closed_model_output_capture_preflight_design",
            "split": packet.get("split"),
            "route": "CAPTURE_PREFLIGHT_DESIGN_ONLY",
            "corrupted_state": {
                "task_family": "authority_closed_model_output_capture_preflight_design",
                "bounded_argument_type": packet.get("bounded_argument_type"),
                "placeholder_packet_validated": True,
                "real_model_output_absent": True,
            },
            "clean_state": {
                "preflight_contract": "authority_closed_model_output_capture_preflight_v1",
                "packet_contract": "model_output_packet_telemetry_v1",
                "required_preflight_fields": REQUIRED_PREFLIGHT_FIELDS,
                "future_capture_inputs": FUTURE_CAPTURE_INPUTS,
                "future_capture_outputs": FUTURE_CAPTURE_OUTPUTS,
                "required_checks": REQUIRED_CHECKS,
                "required_telemetry": REQUIRED_TELEMETRY,
                "blocked_operations": BLOCKED_OPERATIONS,
                "ready_for_model_execution": False,
                "ready_for_decoder_ce": False,
                "probe_ready": False,
            },
            "authority": dict(AUTHORITY_CLOSED),
            "loss_mask": dict(LOSS_MASK_CLOSED),
            "anti_cheat": {
                "contains_model_output": False,
                "contains_target_text": False,
                "contains_runtime_result": False,
                "contains_gemma_score": False,
                "contains_source_body_text": False,
                "opens_authority": False,
            },
            "hard_blockers": [
                "explicit_model_execution_authorization_missing",
                "checkpoint_load_not_authorized",
                "decoder_ce_loss_not_authorized",
                "runtime_not_authorized",
                "gemma_not_authorized",
            ],
        })
    return rows


def build_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "split_counts": dict(sorted(Counter(row.get("split") for row in rows).items())),
        "argument_counts": dict(sorted(Counter((row.get("corrupted_state") or {}).get("bounded_argument_type") for row in rows).items())),
        "authority_rows": sum(int(any((row.get("authority") or {}).values())) for row in rows),
        "loss_rows": sum(int(any((row.get("loss_mask") or {}).values())) for row in rows),
        "probe_ready_rows": sum(int((row.get("clean_state") or {}).get("probe_ready") is True) for row in rows),
        "ready_for_model_execution_rows": sum(int((row.get("clean_state") or {}).get("ready_for_model_execution") is True) for row in rows),
        "ready_for_decoder_ce_rows": sum(int((row.get("clean_state") or {}).get("ready_for_decoder_ce") is True) for row in rows),
        "model_output_rows": sum(int((row.get("anti_cheat") or {}).get("contains_model_output") is True) for row in rows),
        "missing_preflight_field_rows": sum(int(bool(set(REQUIRED_PREFLIGHT_FIELDS) - set((row.get("clean_state") or {}).get("required_preflight_fields", [])))) for row in rows),
        "missing_blocked_operation_rows": sum(int(bool(set(BLOCKED_OPERATIONS) - set((row.get("clean_state") or {}).get("blocked_operations", [])))) for row in rows),
    }

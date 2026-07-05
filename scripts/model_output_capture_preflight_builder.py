from __future__ import annotations

import hashlib
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

REQUIRED_CAPTURE_FIELDS = [
    "preflight_id",
    "source_packet_id",
    "capture_mode",
    "prompt_packet_ref",
    "future_generated_text_ref",
    "packet_contract",
    "capture_checks",
    "telemetry_hooks",
    "authority",
]

CAPTURE_CHECKS = [
    "packet_schema_validate_before_capture",
    "model_execution_authority_check",
    "decoder_ce_authority_check",
    "runtime_authority_check",
    "gemma_scoring_authority_check",
    "target_text_absence_check",
    "artifact_path_scope_check",
    "post_capture_packet_revalidation",
]

TELEMETRY_HOOKS = [
    "decode_invocation_record",
    "decode_token_count_record",
    "eos_stop_reason_record",
    "token_entropy_record",
    "topk_margin_record",
    "internal_token_logit_record",
    "short_output_record",
    "repetition_record",
]


def stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]


def build_preflight_rows(packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for packet in packets:
        if packet.get("generated_text_ref") != "synthetic://placeholder/no_model_output":
            continue
        sid = stable_id(str(packet.get("packet_id")), str(packet.get("split")), str(packet.get("bounded_argument_type")))
        rows.append({
            "row_id": f"stage8831_capture_preflight_{sid}",
            "semantic_key": f"{packet.get('split')}:authority_closed_capture_preflight:{sid}",
            "source_stage": "stage8831_from_stage8828_synthetic_packet_validator_dry_run",
            "source_packet_ref": packet.get("packet_id"),
            "split": packet.get("split"),
            "objective_family": "authority_closed_model_output_capture_preflight",
            "route": "CAPTURE_PREFLIGHT_DESIGN_ONLY",
            "preflight": {
                "preflight_id": f"capture_preflight::{sid}",
                "source_packet_id": packet.get("packet_id"),
                "capture_mode": "AUTHORITY_CLOSED_NO_MODEL_OUTPUT",
                "prompt_packet_ref": packet.get("prompt_packet_ref"),
                "future_generated_text_ref": "future://model_output/not_created",
                "packet_contract": "model_output_packet_telemetry_v1",
                "capture_checks": CAPTURE_CHECKS,
                "telemetry_hooks": TELEMETRY_HOOKS,
                "authority": dict(AUTHORITY_CLOSED),
            },
            "capture_contract": {
                "model_execution_allowed": False,
                "decoder_ce_allowed": False,
                "runtime_allowed": False,
                "gemma_scoring_allowed": False,
                "harness_allowed": False,
                "writes_model_output_artifact_now": False,
                "uses_synthetic_placeholder_only": True,
            },
            "authority": dict(AUTHORITY_CLOSED),
            "loss_mask": dict(LOSS_MASK_CLOSED),
            "anti_cheat": {
                "contains_model_output": False,
                "contains_target_text": False,
                "contains_runtime_result": False,
                "contains_gemma_score": False,
                "contains_hidden_eval_answer": False,
                "contains_source_body_text": False,
            },
            "hard_blockers": [
                "model_execution_not_authorized",
                "decoder_ce_loss_not_authorized",
                "runtime_not_authorized",
                "future_capture_runner_missing",
            ],
        })
    return rows


def build_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    required = set(REQUIRED_CAPTURE_FIELDS)
    missing_capture_field_rows = 0
    missing_capture_check_rows = 0
    missing_telemetry_hook_rows = 0
    authority_open_rows = 0
    loss_open_rows = 0
    model_output_rows = 0
    artifact_write_rows = 0
    for row in rows:
        preflight = row.get("preflight") or {}
        capture = row.get("capture_contract") or {}
        if required - set(preflight):
            missing_capture_field_rows += 1
        if set(CAPTURE_CHECKS) - set(preflight.get("capture_checks", [])):
            missing_capture_check_rows += 1
        if set(TELEMETRY_HOOKS) - set(preflight.get("telemetry_hooks", [])):
            missing_telemetry_hook_rows += 1
        if any((row.get("authority") or {}).values()) or any((preflight.get("authority") or {}).values()):
            authority_open_rows += 1
        if any((row.get("loss_mask") or {}).values()):
            loss_open_rows += 1
        if (row.get("anti_cheat") or {}).get("contains_model_output") is True:
            model_output_rows += 1
        if capture.get("writes_model_output_artifact_now") is True:
            artifact_write_rows += 1
    failing = {
        "missing_capture_field_rows": missing_capture_field_rows,
        "missing_capture_check_rows": missing_capture_check_rows,
        "missing_telemetry_hook_rows": missing_telemetry_hook_rows,
        "authority_open_rows": authority_open_rows,
        "loss_open_rows": loss_open_rows,
        "model_output_rows": model_output_rows,
        "artifact_write_rows": artifact_write_rows,
    }
    return {
        "rows": len(rows),
        "split_counts": dict(sorted(Counter(row.get("split") for row in rows).items())),
        **failing,
        "preflight_design_ready_rows": len(rows) if rows and all(value == 0 for value in failing.values()) else 0,
        "ready_for_model_execution": False,
        "ready_for_decoder_ce": False,
        "passed": bool(rows) and all(value == 0 for value in failing.values()),
    }

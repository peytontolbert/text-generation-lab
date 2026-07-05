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

REQUIRED_RUNNER_FLAGS = [
    "--input-preflight-manifest",
    "--output-packet-dir",
    "--checkpoint-ref",
    "--tokenizer-ref",
    "--decode-config",
    "--authority-ticket",
    "--dry-run",
]

REQUIRED_RUNNER_ASSERTIONS = [
    "authority_ticket_required",
    "dry_run_default_true",
    "checkpoint_load_blocked_without_ticket",
    "model_forward_blocked_without_ticket",
    "decode_blocked_without_ticket",
    "decoder_ce_blocked",
    "runtime_blocked",
    "gemma_blocked",
    "output_packet_schema_revalidated",
    "no_target_text_in_inputs",
]

REQUIRED_ARTIFACT_PATHS = [
    "packet_manifest_out",
    "telemetry_manifest_out",
    "authority_audit_out",
    "rejection_manifest_out",
]


def build_runner_design_rows(preflight_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in preflight_rows:
        capture = row.get("capture_contract") or {}
        if capture.get("writes_model_output_artifact_now") is True:
            continue
        rows.append({
            "row_id": f"stage8837_runner_static::{row.get('row_id')}",
            "semantic_key": f"{row.get('split')}:future_capture_runner_static_design:{row.get('row_id')}",
            "source_stage": "stage8837_from_stage8831_capture_preflight_design",
            "source_row_ref": {"row_id": row.get("row_id"), "split": row.get("split")},
            "split": row.get("split"),
            "objective_family": "future_model_output_capture_runner_static_design",
            "route": "RUNNER_STATIC_DESIGN_ONLY",
            "runner_interface": {
                "runner_name": "capture_model_output_packets.py",
                "required_flags": REQUIRED_RUNNER_FLAGS,
                "required_assertions": REQUIRED_RUNNER_ASSERTIONS,
                "required_artifact_paths": REQUIRED_ARTIFACT_PATHS,
                "default_mode": "dry_run_no_model_execution",
                "authority_ticket_schema": "missing_next_recovery_target",
            },
            "runner_contract": {
                "loads_checkpoint_now": False,
                "runs_model_forward_now": False,
                "decodes_tokens_now": False,
                "writes_model_output_artifact_now": False,
                "computes_decoder_ce_now": False,
                "runs_runtime_now": False,
                "calls_gemma_now": False,
                "opens_scoring_now": False,
            },
            "authority": dict(AUTHORITY_CLOSED),
            "loss_mask": dict(LOSS_MASK_CLOSED),
            "anti_cheat": {
                "contains_model_output": False,
                "contains_target_text": False,
                "contains_runtime_result": False,
                "contains_gemma_score": False,
                "contains_source_body_text": False,
            },
            "hard_blockers": [
                "authority_ticket_schema_missing",
                "runner_implementation_missing",
                "explicit_model_execution_authorization_missing",
                "decoder_ce_loss_not_authorized",
            ],
        })
    return rows


def build_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_flag_rows = 0
    missing_assertion_rows = 0
    missing_artifact_path_rows = 0
    authority_open_rows = 0
    loss_open_rows = 0
    execution_open_rows = 0
    model_output_rows = 0
    bad_route_rows = 0
    for row in rows:
        iface = row.get("runner_interface") or {}
        contract = row.get("runner_contract") or {}
        if set(REQUIRED_RUNNER_FLAGS) - set(iface.get("required_flags", [])):
            missing_flag_rows += 1
        if set(REQUIRED_RUNNER_ASSERTIONS) - set(iface.get("required_assertions", [])):
            missing_assertion_rows += 1
        if set(REQUIRED_ARTIFACT_PATHS) - set(iface.get("required_artifact_paths", [])):
            missing_artifact_path_rows += 1
        if any((row.get("authority") or {}).values()):
            authority_open_rows += 1
        if any((row.get("loss_mask") or {}).values()):
            loss_open_rows += 1
        if any(contract.get(key) is True for key in [
            "loads_checkpoint_now",
            "runs_model_forward_now",
            "decodes_tokens_now",
            "writes_model_output_artifact_now",
            "computes_decoder_ce_now",
            "runs_runtime_now",
            "calls_gemma_now",
            "opens_scoring_now",
        ]):
            execution_open_rows += 1
        if (row.get("anti_cheat") or {}).get("contains_model_output") is True:
            model_output_rows += 1
        if row.get("route") != "RUNNER_STATIC_DESIGN_ONLY":
            bad_route_rows += 1
    failing = {
        "missing_flag_rows": missing_flag_rows,
        "missing_assertion_rows": missing_assertion_rows,
        "missing_artifact_path_rows": missing_artifact_path_rows,
        "authority_open_rows": authority_open_rows,
        "loss_open_rows": loss_open_rows,
        "execution_open_rows": execution_open_rows,
        "model_output_rows": model_output_rows,
        "bad_route_rows": bad_route_rows,
    }
    return {
        "rows": len(rows),
        "split_counts": dict(sorted(Counter(row.get("split") for row in rows).items())),
        **failing,
        "runner_static_design_ready_rows": len(rows) if rows and all(value == 0 for value in failing.values()) else 0,
        "ready_for_model_execution": False,
        "ready_for_decoder_ce": False,
        "passed": bool(rows) and all(value == 0 for value in failing.values()),
    }

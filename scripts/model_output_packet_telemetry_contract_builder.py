from __future__ import annotations

import hashlib
from collections import Counter
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

LOSS_MASK_CLOSED = {
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
    "heldout_eval_metric": False,
}

REQUIRED_PACKET_FIELDS = [
    "packet_id",
    "eval_design_row_id",
    "split",
    "objective_family",
    "prompt_packet_ref",
    "generated_text_ref",
    "surface_type",
    "bounded_argument_type",
    "decode_budget",
    "checks",
    "telemetry",
    "authority",
]

REQUIRED_CHECKS = [
    "schema_parse_check",
    "internal_token_leak_check",
    "surface_contract_check",
    "budget_length_check",
    "grounded_argument_type_check",
    "no_target_text_similarity_check",
    "locked_eval_exclusion_check",
    "cluster_near_duplicate_check",
]

REQUIRED_TELEMETRY = [
    "input_ids_shape",
    "encoder_hidden_shape",
    "decoder_hidden_shape",
    "logits_shape",
    "attention_mask_shape",
    "decode_step_count",
    "eos_stop_reason",
    "token_entropy_summary",
    "topk_margin_summary",
    "internal_token_logit_summary",
    "short_output_signal",
    "repetition_signal",
]

FORBIDDEN_PACKET_FIELDS = [
    "decoder_target_text",
    "clean_target_text",
    "runtime_result",
    "gemma_score",
    "hidden_locked_eval_answer",
    "source_body_text",
]


def stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]


def build_contract_rows(design_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in design_rows:
        clean = row.get("clean_state") or {}
        corrupted = row.get("corrupted_state") or {}
        if clean.get("requires_future_model_output_packet") is not True:
            continue
        sid = stable_id(str(row.get("row_id")), str(row.get("split")), str(corrupted.get("bounded_argument_type")))
        rows.append({
            "row_id": f"stage8823_packet_contract_{sid}",
            "semantic_key": f"{row.get('split')}:future_model_output_packet_schema:{sid}",
            "source_stage": "stage8823_from_stage8820_heldout_non_ce_decoder_eval_design",
            "source_row_ref": {
                "stage": row.get("source_stage"),
                "row_id": row.get("row_id"),
                "split": row.get("split"),
            },
            "objective_family": "future_model_output_packet_schema",
            "split": row.get("split"),
            "route": "PACKET_SCHEMA_TELEMETRY_CONTRACT_ONLY",
            "corrupted_state": {
                "task_family": "future_model_output_packet_schema",
                "language": corrupted.get("language"),
                "file_extension": corrupted.get("file_extension"),
                "argument_signal": corrupted.get("argument_signal"),
                "bounded_argument_type": corrupted.get("bounded_argument_type"),
                "heldout_eval_design_ready": True,
                "future_packet_missing": True,
            },
            "clean_state": {
                "packet_contract": "model_output_packet_telemetry_v1",
                "required_packet_fields": REQUIRED_PACKET_FIELDS,
                "required_checks": REQUIRED_CHECKS,
                "required_telemetry": REQUIRED_TELEMETRY,
                "forbidden_packet_fields": FORBIDDEN_PACKET_FIELDS,
                "probe_ready": False,
                "decoder_ce_eligible_now": False,
                "requires_future_probe_runner": True,
            },
            "packet_schema": {
                "packet_id": "string opaque future identifier",
                "eval_design_row_id": "string reference to heldout design row",
                "prompt_packet_ref": "artifact reference only; not raw target text",
                "generated_text_ref": "future artifact reference; absent until execution is explicitly authorized",
                "checks": {name: "not_run" for name in REQUIRED_CHECKS},
                "telemetry": {name: "not_recorded" for name in REQUIRED_TELEMETRY},
            },
            "authority": dict(AUTHORITY_CLOSED),
            "loss_mask": dict(LOSS_MASK_CLOSED),
            "anti_cheat": {
                "target_text_in_packet": False,
                "target_text_in_model_input": False,
                "runtime_result_in_packet": False,
                "gemma_score_in_packet": False,
                "hidden_eval_answer_in_packet": False,
                "source_body_text_in_packet": False,
            },
            "hard_blockers": [
                "future_probe_runner_missing",
                "model_execution_not_authorized",
                "decoder_ce_loss_not_authorized",
                "runtime_not_authorized",
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
        "decoder_ce_eligible_now_rows": sum(int((row.get("clean_state") or {}).get("decoder_ce_eligible_now") is True) for row in rows),
        "missing_required_field_rows": sum(int(bool(set(REQUIRED_PACKET_FIELDS) - set((row.get("clean_state") or {}).get("required_packet_fields", [])))) for row in rows),
        "missing_required_check_rows": sum(int(bool(set(REQUIRED_CHECKS) - set((row.get("clean_state") or {}).get("required_checks", [])))) for row in rows),
        "missing_required_telemetry_rows": sum(int(bool(set(REQUIRED_TELEMETRY) - set((row.get("clean_state") or {}).get("required_telemetry", [])))) for row in rows),
        "forbidden_visible_rows": sum(int(any((row.get("anti_cheat") or {}).get(key) for key in [
            "target_text_in_packet",
            "target_text_in_model_input",
            "runtime_result_in_packet",
            "gemma_score_in_packet",
            "hidden_eval_answer_in_packet",
            "source_body_text_in_packet",
        ])) for row in rows),
    }

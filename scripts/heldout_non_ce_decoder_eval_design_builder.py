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


def stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]


def build_design_rows(gap_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for gap in gap_rows:
        split = str(gap.get("split"))
        if split not in {"eval", "strict", "strict_eval"}:
            continue
        sid = stable_id(gap.get("row_id", "missing"), split)
        rows.append({
            "row_id": f"stage8820_heldout_non_ce_eval_{sid}",
            "semantic_key": f"{split}:heldout_non_ce_decoder_eval:{sid}",
            "source_stage": "stage8820_from_stage8817_eval_strict_unique_target_gap",
            "source_row_ref": gap.get("source_row_ref", {}),
            "objective_family": "heldout_non_ce_decoder_evaluation_design",
            "split": split,
            "route": "HELDOUT_NON_CE_EVAL_DESIGN_ONLY",
            "corrupted_state": {
                "task_family": "heldout_non_ce_decoder_evaluation_design",
                "language": (gap.get("corrupted_state") or {}).get("language"),
                "file_extension": (gap.get("corrupted_state") or {}).get("file_extension"),
                "argument_signal": (gap.get("corrupted_state") or {}).get("argument_signal"),
                "bounded_argument_type": (gap.get("corrupted_state") or {}).get("bounded_argument_type"),
                "duplicate_target_hash_present": True,
                "ce_target_available_for_eval": False,
            },
            "clean_state": {
                "eval_design": "non_ce_behavioral_decoder_eval",
                "allowed_eval_checks": REQUIRED_CHECKS,
                "forbidden_eval_signals": [
                    "decoder_target_text_ce",
                    "target_text_similarity_against_duplicate_hash",
                    "runtime_execution_result",
                    "gemma_score",
                    "hidden_locked_eval_answer",
                ],
                "probe_ready": False,
                "decoder_ce_eligible_now": False,
                "requires_future_model_output_packet": True,
            },
            "authority": dict(AUTHORITY_CLOSED),
            "loss_mask": dict(LOSS_MASK_CLOSED),
            "anti_cheat": {
                "target_text_in_manifest": False,
                "target_text_in_model_input": False,
                "target_hash_used_for_scoring": False,
                "runtime_result_used_for_scoring": False,
                "gemma_output_used_for_scoring": False,
                "source_row_id_in_model_input": False,
            },
            "hard_blockers": [
                "future_model_output_packet_missing",
                "heldout_eval_metrics_not_executed",
                "decoder_ce_loss_not_authorized",
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
        "decoder_ce_eligible_now_rows": sum(int((row.get("clean_state") or {}).get("decoder_ce_eligible_now") is True) for row in rows),
        "probe_ready_rows": sum(int((row.get("clean_state") or {}).get("probe_ready") is True) for row in rows),
        "raw_or_forbidden_visible_rows": sum(int(any((row.get("anti_cheat") or {}).get(k) for k in ["target_text_in_manifest", "target_text_in_model_input", "target_hash_used_for_scoring", "runtime_result_used_for_scoring", "gemma_output_used_for_scoring", "source_row_id_in_model_input"])) for row in rows),
    }

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
    "eval_metric": False,
    "target_materialization_ce": False,
}

REQUIRED_GATE_KEYS = [
    "source_inventory_lineage",
    "source_provenance",
    "contamination_leakage_detector",
    "golden_locked_eval_suite",
    "drift_canary_regression_monitor",
    "cluster_slice_near_duplicate_detector",
    "dataset_junk_ood_ranker_v1",
    "schema_drift_detector",
]


def stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]


def build_gap_rows(selection_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in selection_rows:
        if row.get("route") != "CE_BLOCK_SPLIT_DUPLICATE_TARGET_HASH":
            continue
        split = str(row.get("split"))
        if split not in {"eval", "strict", "strict_eval"}:
            continue
        clean = row.get("clean_state") or {}
        selection = row.get("selection_status") or {}
        sid = stable_id(row.get("row_id", "missing"), split, str(selection.get("target_hash")))
        out.append({
            "row_id": f"stage8817_eval_strict_target_gap_{sid}",
            "semantic_key": f"{split}:eval_strict_target_gap:{sid}",
            "source_stage": "stage8817_from_stage8810_split_deduped_closed_ce_candidate_selection",
            "source_row_ref": row.get("source_row_ref", {}),
            "objective_family": "eval_strict_unique_target_materialization_gap",
            "split": split,
            "route": "REQUIRES_UNIQUE_EVAL_STRICT_TARGET_MATERIALIZATION",
            "corrupted_state": {
                "task_family": "eval_strict_unique_target_materialization_gap",
                "language": (row.get("corrupted_state") or {}).get("language"),
                "file_extension": (row.get("corrupted_state") or {}).get("file_extension"),
                "argument_signal": (row.get("corrupted_state") or {}).get("argument_signal"),
                "bounded_argument_type": clean.get("bounded_argument_type"),
                "duplicate_target_hash_present": True,
                "selected_by_split_dedup": False,
                "probe_ready": False,
            },
            "clean_state": {
                "gap_type": "eval_strict_duplicate_target_hash",
                "required_resolution": "materialize_semantically_unique_eval_strict_targets_or_use_heldout_non_ce_eval_design",
                "decoder_ce_candidate_after_resolution": False,
                "decoder_ce_eligible_now": False,
                "blocked_target_hash": selection.get("target_hash"),
                "blocked_split": split,
            },
            "gate_status": {key: True for key in REQUIRED_GATE_KEYS},
            "authority": dict(AUTHORITY_CLOSED),
            "loss_mask": dict(LOSS_MASK_CLOSED),
            "anti_cheat": {
                "target_text_in_manifest": False,
                "target_text_in_model_input": False,
                "target_hash_in_model_input": False,
                "raw_source_included": False,
                "raw_decoder_text_included": False,
                "source_row_id_in_model_input": False,
                "requires_locked_eval_guard": True,
                "requires_cluster_near_duplicate_guard": True,
            },
            "hard_blockers": [
                "eval_strict_duplicate_target_hash",
                "probe_not_ready",
                "decoder_ce_loss_not_authorized",
                "unique_eval_strict_target_materialization_missing",
            ],
        })
    return out


def build_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "split_counts": dict(sorted(Counter(row.get("split") for row in rows).items())),
        "argument_counts": dict(sorted(Counter((row.get("corrupted_state") or {}).get("bounded_argument_type") for row in rows).items())),
        "authority_rows": sum(int(any((row.get("authority") or {}).values())) for row in rows),
        "loss_rows": sum(int(any((row.get("loss_mask") or {}).values())) for row in rows),
        "decoder_ce_eligible_now_rows": sum(int((row.get("clean_state") or {}).get("decoder_ce_eligible_now") is True) for row in rows),
        "raw_or_target_visible_rows": sum(int(any((row.get("anti_cheat") or {}).get(k) for k in ["target_text_in_manifest", "target_text_in_model_input", "target_hash_in_model_input", "raw_source_included", "raw_decoder_text_included", "source_row_id_in_model_input"])) for row in rows),
        "complete_gate_status_rows": sum(int(all((row.get("gate_status") or {}).get(k) is True for k in REQUIRED_GATE_KEYS)) for row in rows),
    }

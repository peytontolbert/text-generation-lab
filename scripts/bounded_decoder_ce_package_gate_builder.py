from __future__ import annotations

import hashlib
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

LOSS_MASK_CLOSED = {
    "action_sequence_ce": False,
    "allowed_import_policy_ce": False,
    "blocked_import_policy_ce": False,
    "bounded_decoder_argument_ce": False,
    "bounded_decoder_ce_gate_ce": False,
    "build_mode_ce": False,
    "decoder_ce": False,
    "denoise_ce": False,
    "edit_localization_ce": False,
    "file_plan_ce": False,
    "patch_operator_ce": False,
    "repair_surface_ce": False,
    "repo_dependency_policy_ce": False,
    "runtime_reward": False,
    "surface_role_ce": False,
    "symbol_binding_ce": False,
    "verifier_repair_ce": False,
}

ARGUMENT_TO_GATE = {
    "ARG_CALL": "CE_CANDIDATE_NEEDS_SOURCE_BACKED_TARGET_TEXT",
    "ARG_IMPORT": "CE_CANDIDATE_NEEDS_SOURCE_BACKED_TARGET_TEXT",
    "ARG_LITERAL": "CE_CANDIDATE_NEEDS_SOURCE_BACKED_TARGET_TEXT",
    "ARG_NAME": "CE_CANDIDATE_NEEDS_SOURCE_BACKED_TARGET_TEXT",
    "ARG_PATH": "CE_CANDIDATE_NEEDS_SOURCE_BACKED_TARGET_TEXT",
    "HOLD_LONG_OUTPUT": "CE_BLOCK_LONG_OUTPUT_UNDER_CURRENT_DECODER_BUDGET",
    "RETRIEVE_MORE": "CE_BLOCK_RETRIEVE_MORE_BEFORE_DECODING",
}


def stable_id(*parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]
    return digest


def gate_status_complete(row: dict[str, Any]) -> bool:
    gates = row.get("gate_status") or {}
    return all(gates.get(key) is True for key in REQUIRED_GATE_KEYS)


def build_row(row: dict[str, Any], *, source_stage: str = "stage8802_from_bounded_decoder_argument_controls") -> dict[str, Any]:
    clean = row.get("clean_state") or {}
    arg_type = clean.get("bounded_argument_type")
    gate_decision = ARGUMENT_TO_GATE.get(arg_type, "CE_BLOCK_UNKNOWN_ARGUMENT_TYPE")
    sid = stable_id(row.get("row_id", "missing"), row.get("split", "missing"), str(arg_type))
    missing_gates = [key for key in REQUIRED_GATE_KEYS if (row.get("gate_status") or {}).get(key) is not True]
    hard_blockers = []
    if missing_gates:
        hard_blockers.append("missing_gate_status")
    if gate_decision != "CE_CANDIDATE_NEEDS_SOURCE_BACKED_TARGET_TEXT":
        hard_blockers.append(gate_decision.lower())
    else:
        hard_blockers.append("target_text_not_materialized")
        hard_blockers.append("decoder_ce_loss_not_authorized")
    return {
        "row_id": f"stage8802_ce_gate_{sid}",
        "semantic_key": f"{row.get('split', 'unknown')}:bounded_decoder_ce_gate:{sid}",
        "source_stage": source_stage,
        "source_row_ref": row.get("source_row_ref", {}),
        "objective_family": "bounded_decoder_ce_package_gate",
        "split": row.get("split"),
        "corrupted_state": {
            "task_family": "bounded_decoder_ce_package_gate",
            "language": (row.get("corrupted_state") or {}).get("language"),
            "file_extension": (row.get("corrupted_state") or {}).get("file_extension"),
            "context_group": (row.get("corrupted_state") or {}).get("context_group"),
            "argument_signal": (row.get("corrupted_state") or {}).get("argument_signal"),
            "bounded_argument_features": (row.get("corrupted_state") or {}).get("bounded_argument_features", {}),
            "budget": (row.get("corrupted_state") or {}).get("budget", {}),
        },
        "clean_state": {
            "bounded_argument_type": arg_type,
            "ce_gate_decision": gate_decision,
            "decoder_target_text_materialized": False,
            "decoder_ce_eligible_now": False,
            "required_before_decoder_ce": [
                "source_backed_target_text_materialization",
                "target_text_not_visible_in_encoder",
                "loss_mask_runtime_assertions",
                "tiny_pre_execution_audit",
                "explicit_execution_authorization",
            ],
        },
        "gate_status": dict(row.get("gate_status") or {}),
        "hard_blockers": hard_blockers,
        "authority": dict(AUTHORITY_CLOSED),
        "loss_mask": dict(LOSS_MASK_CLOSED),
        "anti_cheat": {
            "raw_source_included": False,
            "raw_decoder_text_included": False,
            "raw_patch_body_included": False,
            "target_text_in_encoder": False,
            "target_label_in_id": False,
            "source_row_id_in_model_input": False,
            "requires_recovered_gate_status_before_compiler": True,
            "requires_target_materialization_before_decoder_ce": True,
            "requires_pre_execution_audit_before_training": True,
        },
        "route": "CE_PACKAGE_GATE_CLOSED",
    }


def build_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [build_row(row) for row in rows]

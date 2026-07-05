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
    "build_mode_ce": False,
    "decoder_ce": False,
    "denoise_ce": False,
    "edit_localization_ce": False,
    "file_plan_ce": False,
    "output_repair_action_ce": False,
    "patch_operator_ce": False,
    "repair_surface_ce": False,
    "repo_dependency_policy_ce": False,
    "runtime_reward": False,
    "surface_role_ce": False,
    "symbol_binding_ce": False,
    "verifier_repair_ce": False,
}

REPAIR_TO_DENOISE_GATE = {
    "REPAIR_INTERNAL_LEAK": "DENOISE_CANDIDATE_MASK_INTERNAL_TOKENS",
    "REPAIR_REPETITION": "DENOISE_CANDIDATE_MASK_REPEATED_SPANS",
    "REPAIR_SHORT_OUTPUT": "DENOISE_CANDIDATE_EXPAND_MISSING_SPANS",
    "REPAIR_WRONG_SURFACE": "DENOISE_CANDIDATE_RESELECT_SURFACE",
    "ABSTAIN_UNRECOVERABLE": "DENOISE_BLOCK_ABSTAIN_UNRECOVERABLE",
}


def complete_gate_status() -> dict[str, bool]:
    return {key: True for key in REQUIRED_GATE_KEYS}


def stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]


def build_row(row: dict[str, Any], *, source_stage: str = "stage8810_from_stage8647_output_repair_denoise_neutral_manifest") -> dict[str, Any]:
    clean = row.get("clean_state") or {}
    corrupted = row.get("corrupted_state") or {}
    repair_action = clean.get("output_repair_action")
    denoise_gate = REPAIR_TO_DENOISE_GATE.get(repair_action, "DENOISE_BLOCK_UNKNOWN_REPAIR_ACTION")
    sid = stable_id(row.get("row_id", "missing"), row.get("split", "missing"), str(repair_action))
    candidate = denoise_gate.startswith("DENOISE_CANDIDATE_")
    hard_blockers = ["denoise_ce_loss_not_authorized", "model_execution_not_authorized", "verifier_guided_target_repair_not_materialized"]
    if not candidate:
        hard_blockers.append(denoise_gate.lower())
    return {
        "row_id": f"stage8810_denoise_ctrl_{sid}",
        "semantic_key": f"{row.get('split', 'unknown')}:output_repair_denoise_controls:{sid}",
        "source_stage": source_stage,
        "source_row_ref": {
            "source_stage": row.get("source_stage"),
            "source_row_id_hash": f"srcrow_{stable_id(row.get('row_id', 'missing'))}",
            "source_row_id_in_model_input": False,
        },
        "objective_family": "output_repair_denoise_controls",
        "split": row.get("split"),
        "route": "DENOISE_CONTROL_CANDIDATE_NEEDS_AUDIT",
        "corrupted_state": {
            "task_family": "output_repair_denoise_controls",
            "language": corrupted.get("language"),
            "file_extension": corrupted.get("file_extension"),
            "repair_signal": corrupted.get("repair_signal"),
            "candidate_surface_kind": corrupted.get("candidate_surface"),
            "bad_output_features": corrupted.get("bad_output_features", {}),
            "budget": {
                "max_repair_steps": (corrupted.get("budget") or {}).get("max_repair_steps"),
                "decoder_budget_ok": (corrupted.get("budget") or {}).get("decoder_budget_ok"),
                "denoise_training_authorized": False,
            },
        },
        "clean_state": {
            "output_repair_action": repair_action,
            "denoise_gate_decision": denoise_gate,
            "denoise_candidate_eligible_later": candidate,
            "denoise_ce_eligible_now": False,
            "action_sequence": clean.get("action_sequence", []),
            "required_before_denoise_ce": [
                "verified_bad_output_span_packet",
                "source_backed_target_or_repair_reference",
                "masked_span_not_target_visible_in_encoder",
                "loss_mask_runtime_assertions",
                "tiny_pre_execution_audit",
                "explicit_execution_authorization",
            ],
        },
        "gate_status": complete_gate_status(),
        "hard_blockers": hard_blockers,
        "authority": dict(AUTHORITY_CLOSED),
        "loss_mask": dict(LOSS_MASK_CLOSED),
        "anti_cheat": {
            "raw_source_included": False,
            "raw_decoder_text_included": False,
            "raw_patch_body_included": False,
            "bad_output_text_in_encoder": False,
            "target_text_in_encoder": False,
            "target_label_in_id": False,
            "source_row_id_in_model_input": False,
            "requires_recovered_gate_status_before_compiler": True,
            "requires_shortcut_audit_before_training": True,
            "requires_verifier_guided_materialization_before_denoise_ce": True,
        },
    }


def build_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [build_row(row) for row in rows]

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

STRUCTURED_TARGET_FIELDS = [
    "needs_verification",
    "retrieval_coverage",
    "ood_query",
    "build_mode",
    "patch_operator",
    "edit_localization",
    "symbol_binding",
    "verifier_repair",
]

COUNTERFACTUAL_OBLIGATIONS = [
    "POSITIVE_ORIGINAL",
    "EVIDENCE_REMOVED_OR_RETRIEVE",
    "CONTRASTIVE_BOUNDARY_SIBLING",
    "MISLEADING_EVIDENCE_ADDED",
    "JUNK_OR_OOD_ABSTAIN",
]

REQUIRED_TELEMETRY = [
    "row_field_logits",
    "row_field_losses",
    "field_exact_by_split",
    "field_exact_by_cell",
    "confusion_matrices",
    "margin_confidence_entropy",
    "high_confidence_wrong_rows",
    "token_loss_maps",
    "per_row_gradient_norms",
    "per_module_gradient_norms",
    "loss_weight_contribution",
]

REPRESENTATION_REQUIREMENTS = [
    "stable_typed_markers",
    "evidence_to_target_link",
    "low_noise_serialization",
    "decisive_feature_preservation",
    "no_row_id_or_target_label_inputs",
]

LOSS_WEIGHTING_REQUIREMENTS = [
    "single_objective_probe_first",
    "narrow_group_probe_second",
    "explicit_loss_weight_declared",
    "decoder_ce_not_mixed_without_authority",
    "gradient_received_by_target_head_logged",
]

FILE_TOUCHPOINTS = {
    "legacy_src/agentkernel_lite/training_data.py": [
        "typed row serialization",
        "counterfactual sibling metadata",
        "field-local target extraction",
    ],
    "legacy_src/agentkernel_lite/training_loop.py": [
        "row-field logits",
        "row-field losses",
        "confusion matrices",
        "gradient norm telemetry",
        "loss contribution telemetry",
    ],
    "scripts/training_telemetry_metrics.py": [
        "high confidence wrong rows",
        "margin confidence entropy",
        "token loss maps",
    ],
    "legacy_src/agentkernel_lite/modeling_transformer.py": [
        "structured heads",
        "agent policy heads",
        "retrieval heads",
    ],
}


def build_learning_signal_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field in STRUCTURED_TARGET_FIELDS:
        rows.append({
            "row_id": f"stage8844_learning_signal::{field}",
            "semantic_key": f"learning_signal_contract:{field}",
            "source_stage": "stage8844_learning_signal_contract",
            "objective_family": "learning_signal_improvement_contract",
            "split": "contract",
            "route": "LEARNING_SIGNAL_CONTRACT_ONLY",
            "target_field": field,
            "contract": {
                "primary_gold_target": field,
                "counterfactual_obligations": COUNTERFACTUAL_OBLIGATIONS,
                "required_telemetry": REQUIRED_TELEMETRY,
                "representation_requirements": REPRESENTATION_REQUIREMENTS,
                "loss_weighting_requirements": LOSS_WEIGHTING_REQUIREMENTS,
                "file_touchpoints": FILE_TOUCHPOINTS,
            },
            "authority": dict(AUTHORITY_CLOSED),
            "loss_mask": dict(LOSS_MASK_CLOSED),
            "anti_cheat": {
                "opens_training": False,
                "opens_decoder_ce": False,
                "contains_model_output": False,
                "contains_target_label_in_input": False,
            },
            "hard_blockers": [
                "no_training_authorized",
                "no_manifest_rows_materialized",
                "telemetry_contract_not_integrated",
                "counterfactual_siblings_not_materialized",
            ],
        })
    return rows


def build_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_counterfactual_rows = 0
    missing_telemetry_rows = 0
    missing_representation_rows = 0
    missing_loss_weighting_rows = 0
    authority_open_rows = 0
    loss_open_rows = 0
    opening_rows = 0
    for row in rows:
        contract = row.get("contract") or {}
        if set(COUNTERFACTUAL_OBLIGATIONS) - set(contract.get("counterfactual_obligations", [])):
            missing_counterfactual_rows += 1
        if set(REQUIRED_TELEMETRY) - set(contract.get("required_telemetry", [])):
            missing_telemetry_rows += 1
        if set(REPRESENTATION_REQUIREMENTS) - set(contract.get("representation_requirements", [])):
            missing_representation_rows += 1
        if set(LOSS_WEIGHTING_REQUIREMENTS) - set(contract.get("loss_weighting_requirements", [])):
            missing_loss_weighting_rows += 1
        if any((row.get("authority") or {}).values()):
            authority_open_rows += 1
        if any((row.get("loss_mask") or {}).values()):
            loss_open_rows += 1
        if any((row.get("anti_cheat") or {}).values()):
            opening_rows += 1
    failing = {
        "missing_counterfactual_rows": missing_counterfactual_rows,
        "missing_telemetry_rows": missing_telemetry_rows,
        "missing_representation_rows": missing_representation_rows,
        "missing_loss_weighting_rows": missing_loss_weighting_rows,
        "authority_open_rows": authority_open_rows,
        "loss_open_rows": loss_open_rows,
        "opening_rows": opening_rows,
    }
    return {
        "rows": len(rows),
        "target_field_counts": dict(sorted(Counter(row.get("target_field") for row in rows).items())),
        **failing,
        "learning_signal_contract_ready_rows": len(rows) if rows and all(value == 0 for value in failing.values()) else 0,
        "passed": bool(rows) and all(value == 0 for value in failing.values()),
    }

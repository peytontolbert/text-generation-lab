from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from gradient_activation_interpretability import (
    activation_cache_summary,
    activation_patch_recovery_card,
    feature_ablation_attribution,
    interpretability_bundle_card,
    module_delta_norms,
    row_gradient_norm_card,
)


def test_row_gradient_norm_card_groups_by_module() -> None:
    card = row_gradient_norm_card("r1", {"encoder.layer.weight": [3.0, 4.0], "decoder.block.weight": [0.0, 12.0]})
    assert card["total_grad_norm"] == 13.0
    assert card["grad_norm_by_module"]["encoder"] == 5.0
    assert card["decoder_grad_norm"] == 12.0


def test_module_delta_norms_detects_changed_modules_without_training_authority() -> None:
    card = module_delta_norms({"encoder.w": [1.0, 2.0], "decoder.w": [4.0]}, {"encoder.w": [2.0, 2.0], "decoder.w": [4.0]})
    assert card["delta_norm_by_module"]["encoder"] == 1.0
    assert card["decoder_delta_norm"] == 0.0
    assert card["missing_before"] == []
    assert card["missing_after"] == []


def test_activation_cache_summary_reports_layer_stats() -> None:
    card = activation_cache_summary("r1", {"encoder.0": [1.0, -1.0], "field_head_input": [0.5]})
    assert card["activation_cache_present"] is True
    assert card["layer_count"] == 2
    assert card["layers"]["encoder.0"]["max_abs"] == 1.0


def test_feature_ablation_attribution_ranks_gold_probability_drop() -> None:
    card = feature_ablation_attribution(
        "r1",
        "build_mode",
        [0.0, 3.0, 0.0],
        {"intent_features": [0.0, 0.5, 0.0], "language_features": [0.0, 2.9, 0.0]},
        ["SCRATCH", "IMPORT", "WRAP"],
        "IMPORT",
    )
    assert card["top_feature_group"] == "intent_features"
    assert card["feature_attribution"][0]["gold_prob_drop"] > 0.0


def test_activation_patch_recovery_card_measures_logit_recovery() -> None:
    card = activation_patch_recovery_card("r1", "build_mode", [0.0, 4.0], [3.0, 0.0], [0.0, 3.0], ["SCRATCH", "IMPORT"], "IMPORT", patched_layer="encoder.final")
    assert card["recovered_prediction"] is True
    assert card["logit_recovery_fraction"] == 0.75


def test_interpretability_bundle_card_requires_all_components() -> None:
    row_grad = row_gradient_norm_card("r1", {"encoder.w": [1.0]})
    delta = module_delta_norms({"encoder.w": [0.0]}, {"encoder.w": [0.1]})
    activation = activation_cache_summary("r1", {"encoder.0": [1.0]})
    ablation = feature_ablation_attribution("r1", "action", [2.0, 0.0], {"evidence": [0.0, 0.0]}, ["RETRIEVE", "DECODE"], "RETRIEVE")
    patch = activation_patch_recovery_card("r1", "action", [2.0, 0.0], [0.0, 2.0], [1.0, 0.5], ["RETRIEVE", "DECODE"], "RETRIEVE", patched_layer="encoder.mid")
    card = interpretability_bundle_card(row_gradient=row_grad, module_delta=delta, activation_summary=activation, feature_ablation=ablation, activation_patch=patch)
    assert card["passed"] is True
    assert card["authority"]["training"] is False

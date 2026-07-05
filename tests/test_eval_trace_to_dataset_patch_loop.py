from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from eval_trace_to_dataset_patch_loop import build_patch_card, classify_trace


def test_long_output_routes_holdout() -> None:
    patch = classify_trace({"row_id": "long", "target_over_decoder_budget": True})
    assert patch["dataset_patch_action"] == "HOLDOUT_LONG_OUTPUT"
    assert patch["recommended_route"] == "HOLD_LONG_OUTPUT"


def test_internal_leak_routes_verifier_repair() -> None:
    patch = classify_trace({"row_id": "leak", "leak_detected": True})
    assert patch["dataset_patch_action"] == "ADD_VERIFIER_REPAIR_ROW"
    assert patch["recommended_route"] == "USE_FOR_DENOISE_REPAIR"


def test_missing_evidence_requests_source_evidence() -> None:
    patch = classify_trace({"row_id": "missing", "evidence_state": "insufficient"})
    assert patch["dataset_patch_action"] == "REQUEST_SOURCE_EVIDENCE"
    assert patch["recommended_route"] == "NEEDS_RETRIEVAL"


def test_high_confidence_wrong_routes_review() -> None:
    patch = classify_trace({"row_id": "hcw", "high_confidence_wrong": True})
    assert patch["dataset_patch_action"] == "RELABEL_OR_REVIEW"
    assert patch["recommended_route"] == "NEEDS_HUMAN_REVIEW"


def test_safe_unsafe_confusion_adds_counterfactual_neighbor() -> None:
    patch = classify_trace({"row_id": "polarity", "prediction": "SAFE", "target": "UNSAFE"})
    assert patch["dataset_patch_action"] == "ADD_COUNTERFACTUAL_NEIGHBOR"
    assert "safe_unsafe_boundary_confusion" in patch["reasons"]


def test_duplicate_or_harmful_neighbor_routes_prune() -> None:
    patch = classify_trace({"row_id": "dup", "duplicate_semantic_key": True})
    assert patch["dataset_patch_action"] == "DOWNWEIGHT_OR_PRUNE"
    assert patch["recommended_route"] == "DROP_DUPLICATE"


def test_patch_card_counts_actions_and_keeps_authority_closed() -> None:
    card = build_patch_card([
        {"row_id": "long", "target_over_decoder_budget": True},
        {"row_id": "missing", "evidence_state": "missing"},
        {"row_id": "polarity", "prediction": "SAFE", "target": "UNSAFE"},
    ])
    assert card["metrics"]["patches"] == 3
    assert card["metrics"]["valid_patch_actions"] == 3
    assert card["metrics"]["action_counts"]["HOLDOUT_LONG_OUTPUT"] == 1
    assert card["authority"]["training_authorized_next"] is False

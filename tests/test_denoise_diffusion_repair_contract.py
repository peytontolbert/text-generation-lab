from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from denoise_diffusion_repair_contract import build_repair_plan, detect_bad_output_features, repair_contract_card


def test_internal_leak_masks_control_tokens_without_authorizing_denoise_ce() -> None:
    plan = build_repair_plan({"row_id": "leak", "bad_output": "<SEM_SLOT_X> POLICY_CONTINUE"})
    assert plan["route"] == "REPAIR_INTERNAL_LEAK"
    assert plan["mask_spans"]
    assert plan["denoise_candidate_eligible"] is True
    assert plan["denoise_ce_authorized"] is False


def test_short_output_routes_expand_missing_semantic_spans() -> None:
    plan = build_repair_plan({"row_id": "short", "bad_output": "def f("})
    assert plan["route"] == "REPAIR_SHORT_OUTPUT"
    assert plan["mask_spans"][0]["reason"] == "missing_semantic_content"


def test_repetition_routes_repetition_repair() -> None:
    plan = build_repair_plan({"row_id": "rep", "bad_output": "hello hello hello hello hello"})
    assert plan["route"] == "REPAIR_REPETITION"
    assert plan["mask_spans"][0]["reason"] == "degenerate_repetition"


def test_authority_true_forces_abstain() -> None:
    plan = build_repair_plan({"row_id": "auth", "bad_output": "safe text", "authority": {"runtime": True}})
    assert plan["route"] == "ABSTAIN_UNRECOVERABLE"
    assert plan["denoise_candidate_eligible"] is False
    assert plan["model_execution_authorized"] is False


def test_repair_contract_card_counts_routes_and_keeps_losses_closed() -> None:
    card = repair_contract_card([
        {"row_id": "leak", "bad_output": "<CTRL_X>"},
        {"row_id": "short", "bad_output": "return"},
        {"row_id": "rep", "bad_output": "value value value value"},
        {"row_id": "bad", "bad_output": "x", "authority": {"decoder_ce": True}},
    ])
    assert card["rows"] == 4
    assert card["denoise_candidate_rows"] == 3
    assert card["denoise_ce_rows"] == 0
    assert card["decoder_ce_rows"] == 0
    assert card["unsafe_authority_rows"] == 0
    assert card["authority"]["training"] is False


def test_feature_detector_marks_wrong_surface_traceback() -> None:
    features = detect_bad_output_features("Traceback (most recent call last): boom")
    assert features["looks_like_wrong_surface"] is True

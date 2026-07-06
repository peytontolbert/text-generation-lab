from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9026_row_sample_judge_reason_code_taxonomy_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    REASON_CODE_TAXONOMY,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9026_covers_stage9023_reject_reason_codes() -> None:
    card = build_contract(registry())
    assert card["metrics"]["reason_codes"] == 10
    for code in [
        "locked_eval_overlap",
        "target_leakage",
        "shortcut_proxy",
        "near_duplicate_cluster",
        "junk_or_ood",
        "missing_source_provenance",
        "incomplete_gate_status",
        "unsafe_loss_mask",
        "requires_row_body_text",
        "requires_source_body_text",
    ]:
        assert code in card["reason_code_taxonomy"]


def test_stage9026_critical_reasons_block_all_losses() -> None:
    card = build_contract(registry())
    for code in ["locked_eval_overlap", "target_leakage", "unsafe_loss_mask", "requires_row_body_text", "requires_source_body_text"]:
        spec = card["reason_code_taxonomy"][code]
        assert spec["severity"] == "critical"
        assert spec["compiler_action"] == "reject"
        assert spec["training_action"] == "block_all_losses"


def test_stage9026_noncritical_reasons_have_bounded_actions() -> None:
    card = build_contract(registry())
    assert card["reason_code_taxonomy"]["shortcut_proxy"]["training_action"] == "block_until_counterfactual"
    assert card["reason_code_taxonomy"]["near_duplicate_cluster"]["compiler_action"] == "dedupe_or_downsample"
    assert card["reason_code_taxonomy"]["junk_or_ood"]["training_action"] == "route_to_abstain_or_ood_only"
    assert validate_contract(card) == []


def test_stage9026_keeps_execution_manifest_and_training_closed() -> None:
    card = build_contract(registry())
    assert card["metrics"]["taxonomy_contract_only"] is True
    assert card["metrics"]["judge_executed_now"] is False
    assert card["metrics"]["judge_outputs_materialized_now"] is False
    assert card["metrics"]["manifest_compile_authorized_now"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["decoder_ce_authorized"] is False
    assert card["metrics"]["denoise_ce_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9026_validation_rejects_open_authority_or_unblocked_critical_code() -> None:
    opened = build_contract(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(opened)
    unsafe = build_contract(registry())
    unsafe["reason_code_taxonomy"] = dict(REASON_CODE_TAXONOMY)
    unsafe["reason_code_taxonomy"]["target_leakage"] = dict(REASON_CODE_TAXONOMY["target_leakage"])
    unsafe["reason_code_taxonomy"]["target_leakage"]["training_action"] = "allow_structured_aux_only"
    assert "critical_code_not_blocking:target_leakage" in validate_contract(unsafe)

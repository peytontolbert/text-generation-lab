from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8997_locked_tiny_manifest_compile_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    LOSS_MASK_FIELDS,
    REQUIRED_OUTPUTS,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8997_defaults_all_loss_masks_false() -> None:
    card = build_contract(registry())
    assert len(LOSS_MASK_FIELDS) >= 7
    assert all(value is False for value in card["loss_mask_defaults"].values())
    assert "loss_mask_card.json" in REQUIRED_OUTPUTS
    assert card["metrics"]["manifest_emitted_now"] is False


def test_stage8997_keeps_manifest_compile_and_training_closed() -> None:
    card = build_contract(registry())
    assert validate_contract(card) == []
    assert card["metrics"]["manifest_compile_authorized_now"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["decoder_ce_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage8997_validation_rejects_open_loss_or_unjudged_rows() -> None:
    bad = build_contract(registry())
    bad["loss_mask_defaults"]["train_decoder_ce"] = True
    assert "loss_mask_defaults_not_false" in validate_contract(bad)
    unjudged = build_contract(registry())
    unjudged["metrics"]["unjudged_rows_allowed"] = True
    assert "unjudged_rows_allowed" in validate_contract(unjudged)
    opened = build_contract(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(opened)

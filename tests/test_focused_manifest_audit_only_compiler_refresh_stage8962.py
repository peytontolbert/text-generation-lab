from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8962_focused_manifest_audit_only_compiler_refresh import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_refresh,
    validate_refresh,
)


def registry(latest: int = 8961) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8962_compiles_focused_manifest_audit_only_outputs() -> None:
    card = build_refresh(registry())
    assert card["metrics"]["manifest_rows"] == 3
    assert card["metrics"]["output_files_written"] == card["metrics"]["output_files_expected"]
    assert card["metrics"]["objective_files"] >= 1
    assert card["checks"]["manifest_under_focused_root"] is True
    assert card["checks"]["manifest_authority_closed"] is True


def test_stage8962_keeps_losses_execution_mining_and_training_closed() -> None:
    card = build_refresh(registry())
    assert card["metrics"]["decoder_ce_loss_rows"] == 0
    assert card["metrics"]["denoise_ce_loss_rows"] == 0
    assert card["metrics"]["runtime_reward_rows"] == 0
    assert card["metrics"]["data_mining_authorized"] is False
    assert card["metrics"]["training_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage8962_validation_rejects_authority_or_loss_reopen() -> None:
    card = build_refresh(registry())
    assert validate_refresh(card, registry()) == []
    bad = build_refresh(registry())
    bad["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_refresh(bad, registry())
    bad_loss = build_refresh(registry())
    bad_loss["metrics"]["decoder_ce_loss_rows"] = 1
    assert "decoder_ce_loss_rows" in validate_refresh(bad_loss, registry())
    assert "unexpected_registry_frontier:9999" in validate_refresh(card, registry(latest=9999))

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8964_focused_manifest_counterbalance_design_no_mining import (  # noqa: E402
    AUTHORITY_CLOSED,
    COUNTERBALANCE_CELLS,
    NEUTRAL_EVIDENCE_FEATURES,
    build_design,
    validate_design,
)


def registry(latest: int = 8963) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8964_records_counterbalance_cells_for_both_combo_shortcuts() -> None:
    card = build_design(registry())
    combos = {row["breaks_combo"] for row in COUNTERBALANCE_CELLS}
    assert "decode_allowed+evidence_state" in combos
    assert "decoder_budget_ok+evidence_state" in combos
    assert card["metrics"]["counterbalance_cells"] >= 4
    assert card["checks"]["each_shortcut_combo_has_counterbalance"] is True


def test_stage8964_templates_are_non_trainable_and_require_neutral_evidence() -> None:
    card = build_design(registry())
    assert len(NEUTRAL_EVIDENCE_FEATURES) >= 6
    assert card["metrics"]["template_rows"] == len(COUNTERBALANCE_CELLS)
    assert card["metrics"]["trainable_rows"] == 0
    assert card["checks"]["template_rows_non_trainable"] is True
    assert card["checks"]["template_rows_authority_closed"] is True


def test_stage8964_validation_rejects_authority_or_training_reopen() -> None:
    card = build_design(registry())
    assert validate_design(card, registry()) == []
    bad = build_design(registry())
    bad["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_design(bad, registry())
    bad_train = build_design(registry())
    bad_train["metrics"]["trainable_rows"] = 1
    assert "trainable_rows" in validate_design(bad_train, registry())
    assert "unexpected_registry_frontier:9999" in validate_design(card, registry(latest=9999))

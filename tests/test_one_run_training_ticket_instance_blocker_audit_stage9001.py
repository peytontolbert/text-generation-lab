from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9001_one_run_training_ticket_instance_blocker_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_DRY_RUN_ARTIFACTS,
    build_audit,
    validate_audit,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9001_blocks_ticket_instance_without_dry_run_artifacts() -> None:
    card = build_audit(registry())
    assert len(REQUIRED_DRY_RUN_ARTIFACTS) == 6
    assert card["metrics"]["ticket_instance_ready"] is False
    assert card["metrics"]["training_ticket_authorized_now"] is False
    assert card["metrics"]["missing_prerequisites"] > 0


def test_stage9001_validation_requires_blocker_and_closed_authority() -> None:
    card = build_audit(registry())
    assert validate_audit(card) == []
    noblock = build_audit(registry())
    noblock["metrics"]["missing_prerequisites"] = 0
    assert "missing_prerequisites_not_recorded" in validate_audit(noblock)
    opened = build_audit(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(opened)


def test_stage9001_rejects_training_side_effects() -> None:
    card = build_audit(registry())
    card["metrics"]["training_executed_now"] = True
    assert "training_executed_now" in validate_audit(card)
    ckpt = build_audit(registry())
    ckpt["metrics"]["checkpoint_written"] = True
    assert "checkpoint_written" in validate_audit(ckpt)

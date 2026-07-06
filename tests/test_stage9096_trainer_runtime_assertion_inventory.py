from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9096_trainer_runtime_assertion_inventory import (  # noqa: E402
    ASSERTION_FAMILIES,
    AUTHORITY_CLOSED,
    REQUIRED_TELEMETRY_ARTIFACTS,
    build_inventory,
    validate_inventory,
)


def registry(latest: int = 9095) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9096_inventory_finds_all_assertion_terms() -> None:
    card = build_inventory(registry())
    assert card["checks"]["trainer_exists"] is True
    assert card["checks"]["assertion_families_complete"] is True
    assert card["checks"]["telemetry_artifacts_declared"] is True
    assert card["metrics"]["missing_assertion_terms"] == 0
    assert card["metrics"]["missing_telemetry_artifacts"] == 0
    assert len(ASSERTION_FAMILIES) >= 10
    assert len(REQUIRED_TELEMETRY_ARTIFACTS) >= 17


def test_stage9096_records_specific_runtime_guard_families() -> None:
    card = build_inventory(registry())
    for family in [
        "manifest_and_repo_path",
        "loss_mask_enforcement",
        "authority_closure",
        "decoder_budget_and_targets",
        "execution_gates",
        "cleanup_guards",
        "implementation_and_tokenizer_guards",
    ]:
        assert family in card["assertion_families"]
        assert card["missing_by_family"][family] == []


def test_stage9096_keeps_inventory_static_only() -> None:
    card = build_inventory(registry())
    metrics = card["metrics"]
    assert metrics["trainer_static_inspection_only"] is True
    assert metrics["trainer_executed_now"] is False
    assert metrics["contract_only_invoked_now"] is False
    assert metrics["runtime_assertions_executed_now"] is False
    assert metrics["model_input_rows_now"] == 0
    assert metrics["candidate_rows_materialized"] == 0
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert not any(card["authority"].values())


def test_stage9096_validation_rejects_execution_or_bad_frontier() -> None:
    card = build_inventory(registry())
    assert validate_inventory(card, registry()) == []
    bad = build_inventory(registry())
    bad["metrics"]["runtime_assertions_executed_now"] = True
    assert "runtime_assertions_executed_now" in validate_inventory(bad, registry())
    bad_rows = build_inventory(registry())
    bad_rows["metrics"]["model_input_rows_now"] = 1
    assert "model_input_rows_now" in validate_inventory(bad_rows, registry())
    bad_authority = build_inventory(registry())
    bad_authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_inventory(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_inventory(card, registry(latest=9999))

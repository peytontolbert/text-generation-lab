from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8957_no_mining_compiler_readiness_refresh_after_decoder_gates import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORCED_CLOSED_PATHS,
    PIPELINE_STEPS,
    build_card,
    validate_card,
)


def registry(latest: int = 8956) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8957_records_compiler_pipeline_and_required_modules() -> None:
    card = build_card(registry())
    assert card["metrics"]["source_summaries_passed"] == card["metrics"]["source_summaries"]
    assert card["metrics"]["required_modules_present"] == card["metrics"]["required_modules"]
    assert card["metrics"]["required_tests_present"] == card["metrics"]["required_tests"]
    assert "objective_row_judge" in PIPELINE_STEPS
    assert "dataset_junk_ood_ranker_v1" in PIPELINE_STEPS
    assert "curriculum_compiler" in PIPELINE_STEPS
    assert "loss_mask_card" in PIPELINE_STEPS


def test_stage8957_keeps_mining_decoder_runtime_and_training_closed() -> None:
    card = build_card(registry())
    for path in ["data_mining", "model_execution", "decoder_ce", "denoise_ce", "runtime", "training"]:
        assert path in FORCED_CLOSED_PATHS
    assert card["metrics"]["data_mining_authorized"] is False
    assert card["metrics"]["decoder_ce_authorized"] is False
    assert card["metrics"]["denoise_ce_authorized"] is False
    assert card["metrics"]["training_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage8957_validation_rejects_authority_or_bad_frontier() -> None:
    card = build_card(registry())
    assert validate_card(card, registry()) == []
    bad = build_card(registry())
    bad["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_card(bad, registry())
    bad_mining = build_card(registry())
    bad_mining["metrics"]["data_mining_authorized"] = True
    assert "data_mining_authorized" in validate_card(bad_mining, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(card, registry(latest=9999))

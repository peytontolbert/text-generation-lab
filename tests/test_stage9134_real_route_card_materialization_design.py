from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9124_route_card_schema_recovery_design import ROUTE_ENUM  # noqa: E402
from scripts.build_stage9134_real_route_card_materialization_design import (  # noqa: E402
    BLOCKERS,
    JOIN_KEYS,
    REQUIRED_INPUTS,
    REQUIRED_OUTPUTS,
    ROUTE_SOURCE_RULES,
    build_design,
    validate_design,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402


def registry(latest: int = 9133) -> dict:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9134_design_passes_with_closed_authority() -> None:
    design = build_design(registry())

    assert validate_design(design, registry()) == []
    assert all(design["checks"].values())
    assert not any(design["authority"].values())


def test_stage9134_records_required_inputs_outputs_and_join_keys() -> None:
    design = build_design(registry())

    assert set(REQUIRED_INPUTS).issubset(set(design["required_inputs"]))
    assert set(REQUIRED_OUTPUTS).issubset(set(design["required_outputs"]))
    assert set(JOIN_KEYS).issubset(set(design["join_keys"]))
    assert "judge_rows_jsonl" in design["required_inputs"]
    assert "junk_ranker_rows_jsonl" in design["required_inputs"]
    assert "route_cards.jsonl" in design["required_outputs"]
    assert "route_to_loss_ready_blocker_card.json" in design["required_outputs"]


def test_stage9134_records_every_route_source_rule_and_blocker() -> None:
    design = build_design(registry())

    assert set(ROUTE_SOURCE_RULES) == set(ROUTE_ENUM)
    assert set(ROUTE_ENUM).issubset(set(design["route_source_rules"]))
    assert set(BLOCKERS).issubset(set(design["blockers"]))
    for blocker in [
        "shortcut_dominance",
        "counterfactual_obligation_incomplete",
        "label_leak_detected",
        "split_overlap_detected",
        "authority_open",
        "target_in_input",
        "unknown_route",
    ]:
        assert blocker in design["blockers"]


def test_stage9134_does_not_materialize_or_execute() -> None:
    design = build_design(registry())
    metrics = design["metrics"]

    assert metrics["route_cards_materialized_now"] is False
    assert metrics["route_to_loss_translation_ready_now"] is False
    assert metrics["loss_mask_cards_materialized_now"] is False
    assert metrics["compiler_handoff_ready_now"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["repository_source_bodies_loaded"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["network_upload_performed"] is False
    assert metrics["cleanup_authorized_now"] is False


def test_stage9134_rejects_open_authority_missing_route_rule_and_bad_frontier() -> None:
    design = build_design(registry())
    design["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_design(design, registry())

    design = build_design(registry())
    design["route_source_rules"].pop("KEEP_BOUNDED_DECODER")
    assert "missing_route_source_rule:KEEP_BOUNDED_DECODER" in validate_design(design, registry())

    design = build_design(registry())
    assert "unexpected_registry_frontier:9999" in validate_design(design, registry(latest=9999))

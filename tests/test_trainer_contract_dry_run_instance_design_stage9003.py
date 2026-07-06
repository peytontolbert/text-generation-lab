from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9003_trainer_contract_dry_run_instance_design import (  # noqa: E402
    AUTHORITY_CLOSED,
    DRY_RUN_FLAGS,
    NO_EXECUTION_METRICS,
    REQUIRED_ASSERTIONS,
    REQUIRED_OUTPUTS,
    build_design,
    validate_design,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9003_records_exact_dry_run_interface_and_outputs() -> None:
    card = build_design(registry())
    for flag in ["--manifest", "--mode", "--max-train-rows", "--require-loss-mask-enforcement-audit", "--cleanup-checkpoints-after-probe"]:
        assert flag in DRY_RUN_FLAGS
    for output in ["no_model_forward_proof.json", "no_training_execution_proof.json", "next_one_run_training_ticket_input.json", "loss_mask_enforcement_audit.json"]:
        assert output in REQUIRED_OUTPUTS
    assert card["metrics"]["required_outputs"] >= 10


def test_stage9003_requires_no_execution_assertions() -> None:
    card = build_design(registry())
    for assertion in ["dry_run_stops_before_model_forward", "no_model_weights_loaded", "no_optimizer_created", "no_backward_called", "no_dataset_row_body_loaded"]:
        assert assertion in REQUIRED_ASSERTIONS
    assert card["metrics"]["dry_run_instance_ready_to_execute"] is False
    assert card["metrics"]["dry_run_command_materialized_now"] is False
    assert all(card["metrics"][key] is False for key in NO_EXECUTION_METRICS)


def test_stage9003_validation_rejects_execution_or_authority() -> None:
    assert validate_design(build_design(registry())) == []
    opened = build_design(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_design(opened)
    unsafe = build_design(registry())
    unsafe["metrics"]["trainer_dry_run_executed_now"] = True
    assert "trainer_dry_run_executed_now" in validate_design(unsafe)
    unsafe_forward = build_design(registry())
    unsafe_forward["metrics"]["model_forward_attempted"] = True
    assert "model_forward_attempted" in validate_design(unsafe_forward)

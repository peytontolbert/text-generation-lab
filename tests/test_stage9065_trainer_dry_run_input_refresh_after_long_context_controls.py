from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9065_trainer_dry_run_input_refresh_after_long_context_controls import (  # noqa: E402
    ADDITIONAL_ASSERTIONS,
    AUTHORITY_CLOSED,
    REQUIRED_LONG_CONTEXT_INPUTS,
    build_design,
    validate_design,
)


def registry(latest: int = 9064) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9065_adds_long_context_inputs_and_assertions() -> None:
    design = build_design(registry())
    assert design["checks"]["future_inputs_include_long_context_controls"] is True
    assert set(REQUIRED_LONG_CONTEXT_INPUTS).issubset(set(design["future_required_inputs"]))
    assert set(ADDITIONAL_ASSERTIONS).issubset(set(design["required_assertions"]))
    assert design["metrics"]["dry_run_instance_ready_to_execute"] is False


def test_stage9065_keeps_trainer_execution_closed() -> None:
    design = build_design(registry())
    assert design["metrics"]["trainer_dry_run_executed_now"] is False
    assert design["metrics"]["model_forward_attempted"] is False
    assert design["metrics"]["model_weights_loaded"] is False
    assert all(value is False for value in design["authority"].values())


def test_stage9065_validation_rejects_missing_inputs_or_execution() -> None:
    design = build_design(registry())
    assert validate_design(design, registry()) == []
    missing = build_design(registry())
    missing["future_required_inputs"].remove("long_context_loss_mask_compiler_preflight.json")
    assert "missing_long_context_input:long_context_loss_mask_compiler_preflight.json" in validate_design(missing, registry())
    executed = build_design(registry())
    executed["metrics"]["model_forward_attempted"] = True
    assert "model_forward_attempted" in validate_design(executed, registry())

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9006_active_frontier_routing_audit import (  # noqa: E402
    ACTIVE_IMMEDIATE_INPUTS,
    AUTHORITY_CLOSED,
    CURRENTLY_BLOCKED_OPERATIONS,
    EXECUTION_ORDER,
    build_audit,
    validate_audit,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9006_routes_future_guardrail_away_from_active_frontier() -> None:
    card = build_audit(registry())
    assert card["indexed_frontier"]["stage"] == 9005
    assert card["indexed_frontier"]["role"] == "future_post_training_diagnostics_blocker"
    assert card["active_immediate_frontier"]["stage"] == 9003
    assert "materialize_locked_manifest_loss_mask_schema_and_leakage_artifacts_without_training" == card["active_immediate_frontier"]["next_required_action"]


def test_stage9006_records_required_inputs_and_order() -> None:
    card = build_audit(registry())
    for required in ["locked_tiny_training_manifest.jsonl", "loss_mask_card.json", "manifest_schema_lock.json", "contamination_and_leakage_proof.json"]:
        assert required in ACTIVE_IMMEDIATE_INPUTS
    assert EXECUTION_ORDER[0] == "materialize_locked_manifest_artifacts_no_training"
    assert EXECUTION_ORDER[-1] == "run_post_training_diagnostics_only_after_training_telemetry_exists"
    assert card["metrics"]["active_immediate_inputs"] >= 5


def test_stage9006_keeps_all_execution_paths_blocked() -> None:
    card = build_audit(registry())
    assert "trainer_dry_run_execution" in CURRENTLY_BLOCKED_OPERATIONS
    assert "model_forward" in CURRENTLY_BLOCKED_OPERATIONS
    assert "arxiv_write" in CURRENTLY_BLOCKED_OPERATIONS
    assert validate_audit(card) == []
    unsafe = build_audit(registry())
    unsafe["metrics"]["trainer_dry_run_execution_authorized_now"] = True
    assert "trainer_dry_run_execution_authorized_now" in validate_audit(unsafe)
    opened = build_audit(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(opened)

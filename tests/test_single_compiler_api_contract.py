from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8929_single_compiler_api_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"latest_stage": 8928, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_contract_defines_full_compiler_pipeline() -> None:
    contract = build_contract(registry())
    steps = [row["step"] for row in contract["pipeline_steps"]]
    assert steps[0] == "ingest_manifest"
    assert "objective_row_judge" in steps
    assert "junk_ood_rank" in steps
    assert "shortcut_baseline_audit" in steps
    assert "counterfactual_obligation_audit" in steps
    assert "compile_objective_manifests" in steps
    assert "emit_patch_queue" in steps
    assert contract["checks"]["all_step_modules_present"] is True


def test_contract_records_hard_gates_and_outputs() -> None:
    contract = build_contract(registry())
    assert "loss_mask_card.json" in contract["required_outputs"]
    assert "dataset_patch_queue.jsonl" in contract["required_outputs"]
    assert any("locked_eval_source" in gate for gate in contract["hard_gates"])
    assert any("target_over_budget" in gate for gate in contract["hard_gates"])
    assert contract["checks"]["hard_gates_present"] is True


def test_contract_keeps_training_mining_and_runtime_blocked() -> None:
    contract = build_contract(registry())
    assert contract["api_signature"]["config"]["allow_decoder_ce"] is False
    assert contract["api_signature"]["config"]["allow_denoise_ce"] is False
    assert contract["api_signature"]["config"]["allow_runtime"] is False
    assert contract["checks"]["training_remains_blocked"] is True
    assert contract["checks"]["data_mining_remains_blocked"] is True
    assert contract["checks"]["runtime_remains_blocked"] is True
    assert all(value is False for value in contract["authority"].values())


def test_validation_rejects_bad_frontier_or_open_authority() -> None:
    assert validate_contract(build_contract(registry()), registry()) == []
    bad_registry = registry()
    bad_registry["metrics"]["latest_stage"] = 9999  # type: ignore[index]
    assert "unexpected_registry_frontier:9999" in validate_contract(build_contract(registry()), bad_registry)
    bad_contract = build_contract(registry())
    bad_contract["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(bad_contract, registry())

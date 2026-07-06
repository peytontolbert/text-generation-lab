from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8932_no_mining_compiler_cli_wrapper_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"latest_stage": 8931, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_contract_records_wrapper_cli_surface() -> None:
    contract = build_contract(registry())
    assert contract["cli_name"] == "compile_software_maintenance_curriculum_v1"
    assert "--input" in contract["allowed_flags"]
    assert "--output-dir" in contract["allowed_flags"]
    assert "synthetic_dry_run" in contract["required_mode_values"]
    assert "manifest_no_mining_audit_only" in contract["required_mode_values"]
    assert contract["checks"]["allowed_flags_present"] is True


def test_contract_forbids_training_mining_runtime_and_model_execution() -> None:
    contract = build_contract(registry())
    assert "--mine" in contract["forbidden_flags"]
    assert "--train" in contract["forbidden_flags"]
    assert "--allow-runtime" in contract["forbidden_flags"]
    assert "--allow-decoder-ce" in contract["forbidden_flags"]
    assert "--allow-denoise-ce" in contract["forbidden_flags"]
    assert "--load-model" in contract["forbidden_flags"]
    assert contract["checks"]["mining_forbidden_by_default"] is True
    assert contract["checks"]["model_execution_forbidden_by_default"] is True
    assert all(value is False for value in contract["authority"].values())


def test_contract_requires_expected_outputs() -> None:
    contract = build_contract(registry())
    assert "judged_rows.jsonl" in contract["required_outputs"]
    assert "ranked_rows.jsonl" in contract["required_outputs"]
    assert "compile_card.json" in contract["required_outputs"]
    assert "dataset_patch_queue.jsonl" in contract["required_outputs"]


def test_validation_rejects_bad_frontier_or_open_authority() -> None:
    assert validate_contract(build_contract(registry()), registry()) == []
    bad_registry = registry()
    bad_registry["metrics"]["latest_stage"] = 9999  # type: ignore[index]
    assert "unexpected_registry_frontier:9999" in validate_contract(build_contract(registry()), bad_registry)
    bad_contract = build_contract(registry())
    bad_contract["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(bad_contract, registry())

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8934_real_manifest_audit_only_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"latest_stage": 8933, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_contract_records_allowed_and_forbidden_manifest_roots() -> None:
    contract = build_contract(registry())
    assert "runs/local/artifacts" in contract["allowed_input_roots"]
    assert "datasets/recovered" in contract["allowed_input_roots"]
    assert "/arxiv" in contract["forbidden_input_roots"]
    assert "/data" in contract["forbidden_input_roots"]
    assert contract["checks"]["allowed_input_roots_recorded"] is True


def test_contract_blocks_mining_training_and_mutation() -> None:
    contract = build_contract(registry())
    assert "glob_discovery_mining" in contract["forbidden_operations"]
    assert "recursive_dataset_scan" in contract["forbidden_operations"]
    assert "mutate_input_manifest" in contract["forbidden_operations"]
    assert contract["checks"]["training_remains_blocked"] is True
    assert contract["checks"]["data_mining_remains_blocked"] is True
    assert all(value is False for value in contract["authority"].values())


def test_contract_requires_manifest_quality_properties() -> None:
    contract = build_contract(registry())
    assert "jsonl_objects_only" in contract["required_manifest_properties"]
    assert "authority_absent_or_all_false" in contract["required_manifest_properties"]
    assert "source_lineage_present_for_source_backed_rows" in contract["required_manifest_properties"]
    assert "compiler_audit_card.json" in contract["audit_only_allowed_outputs"]


def test_validation_rejects_bad_frontier_or_open_authority() -> None:
    assert validate_contract(build_contract(registry()), registry()) == []
    bad_registry = registry()
    bad_registry["metrics"]["latest_stage"] = 9999  # type: ignore[index]
    assert "unexpected_registry_frontier:9999" in validate_contract(build_contract(registry()), bad_registry)
    bad_contract = build_contract(registry())
    bad_contract["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(bad_contract, registry())

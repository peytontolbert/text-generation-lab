from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8922_cleanup_proof_no_overwrite_finalization import (  # noqa: E402
    ALLOWED_CLEANUP_SCOPE,
    AUTHORITY_CLOSED,
    REQUIRED_CLEANUP_PROOF_FIELDS,
    audit_cleanup_contract,
    build_cleanup_contract,
    negative_mutation_results,
)


def test_cleanup_contract_requires_fresh_no_overwrite_probe_root() -> None:
    contract = build_cleanup_contract()
    assert contract["allowed_output_root_must_not_exist_before_run"] is True
    assert contract["no_overwrite_existing"] is True
    assert contract["cleanup_scope"] == ALLOWED_CLEANUP_SCOPE
    assert contract["required_marker_file"] == ".agentkernel_probe_output"


def test_cleanup_contract_requires_proof_fields_and_kept_artifacts() -> None:
    contract = build_cleanup_contract()
    assert set(contract["required_cleanup_proof_fields"]) == set(REQUIRED_CLEANUP_PROOF_FIELDS)
    assert "cleanup_proof.json" in contract["required_kept_artifacts"]
    assert "row_field_logits.jsonl" in contract["required_kept_artifacts"]


def test_cleanup_contract_forbids_roots_and_authority() -> None:
    contract = build_cleanup_contract()
    assert "/arxiv" in contract["forbidden_cleanup_targets"]
    assert "/data" in contract["forbidden_cleanup_targets"]
    assert contract["repo_root_delete_forbidden"] is True
    assert contract["parent_delete_forbidden"] is True
    assert contract["output_dir_itself_delete_forbidden"] is True
    assert all(value is False for value in contract["authority"].values())


def test_cleanup_contract_accepts_clean_registry_and_rejects_mutations() -> None:
    registry = {"metrics": {"latest_stage": 8921, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
    source_summary = {"passed": True, "authority": AUTHORITY_CLOSED}
    audit = audit_cleanup_contract(build_cleanup_contract(), source_summary=source_summary, registry=registry)
    assert audit["passed"] is True
    results = negative_mutation_results(build_cleanup_contract())
    assert results
    assert all(result["rejected"] for result in results.values())

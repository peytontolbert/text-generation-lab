from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12575_provenance_only_protected_root_quarantine_proposal.py"
SPEC = importlib.util.spec_from_file_location("stage12575", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


@pytest.fixture(scope="module")
def sources():
    return M.read_json(M.SOURCE12573), M.read_json(M.SOURCE12574)


def build(source73, source74, digest73=M.PINNED_STAGE12573_FILE_SHA256,
          digest74=M.PINNED_STAGE12574_FILE_SHA256):
    return M.build_proposal(
        source73, source74, source12573_file_sha256=digest73,
        source12574_file_sha256=digest74,
    )


def assert_blocked(result, reason):
    assert result["decision"] == "blocked"
    assert reason in result["blocking_reasons"]
    assert result["proposal_rows"] == []
    assert result["proposal_row_count"] == 0
    assert result["retained_verified_lineage_count"] == 0
    assert result["quarantined_unrecoverable_historical_provenance_count"] == 0
    assert all(result[field] is False for field in M.DENY_FIELDS)


def test_exact_25_row_provenance_only_partition_and_no_authority():
    result = M.build()
    assert result["decision"] == "proposal_verified_deny_only"
    assert result["artifact_kind"] == "proposal_control_only"
    assert result["authorization_effect"] == "none"
    assert result["blocking_reasons"] == []
    assert result["non_authorizing_blockers"] == ["legacy_metrics_reference_missing"]
    assert (
        result["proposal_row_count"], result["retained_verified_lineage_count"],
        result["quarantined_unrecoverable_historical_provenance_count"],
    ) == (25, 17, 8)
    statuses = [row["proposed_disposition"] for row in result["proposal_rows"]]
    assert statuses.count("retained_verified_lineage") == 17
    assert statuses.count("quarantined_unrecoverable_historical_provenance") == 8
    assert all(result[field] is False for field in M.DENY_FIELDS)
    assert result["quarantine_applied"] is False
    for row in result["proposal_rows"]:
        assert row["proposal_only"] is True
        assert row["quarantine_applied"] is False
        assert all(row[field] is False for field in M.DENY_FIELDS)
        assert M._digest(row["proposal_row_sha256"])


def test_predicate_is_source_era_provenance_only_and_outcome_independent():
    result = M.build()
    assert result["quarantine_predicate_fields"] == list(M.PROVENANCE_PREDICATE_FIELDS)
    assert result["quarantine_predicate_outcome_independent"] is True
    assert not set(M.PROVENANCE_PREDICATE_FIELDS) & M.OUTCOME_CONDITIONED_KEYS
    for row in result["proposal_rows"]:
        expected_complete = row["proposed_disposition"] == "retained_verified_lineage"
        assert row["source_era_provenance_complete"] is expected_complete
        assert row["quarantine_predicate_id"] == "source_era_provenance_completeness_v1"


def test_legacy_metrics_and_replacement_sealed_root_requirement_are_explicit():
    result = M.build()
    assert result["original_25_root_metrics_status"] == (
        "legacy_metrics_reference_missing_non_comparable"
    )
    assert result["legacy_metrics_reference"] is None
    assert result["legacy_metrics_file_sha256"] is None
    assert result["legacy_metrics_reference_present"] is False
    assert result["legacy_metrics_claim_preserved"] is False
    assert "legacy_metrics_reference_missing" in result["non_authorizing_blockers"]
    assert result["retained_17_root_eval_claim_allowed"] is False
    assert result["required_replacement_root_count"] == 8
    assert result["replacement_sealed_roots_required_before_17_root_eval_claim"] is True
    requirement = result["replacement_manifest_requirement"]
    assert requirement == {
        "status": "required_not_supplied",
        "reference": None,
        "file_sha256": None,
        "required_root_count": 8,
        "must_be_pre_outcome_sealed": True,
        "must_be_disjoint_from_legacy_25_roots": True,
        "identity_placeholders_allowed": False,
        "root_identities_emitted": False,
    }
    assert "replacement_sealed_roots_required_before_any_17_root_eval_claim" in result["non_authorizing_conditions"]


@pytest.mark.parametrize("which", ["stage12573", "stage12574"])
def test_missing_or_mutated_source_file_pins_fail_closed(sources, which):
    source73, source74 = sources
    kwargs = {"digest73": M.PINNED_STAGE12573_FILE_SHA256, "digest74": M.PINNED_STAGE12574_FILE_SHA256}
    kwargs["digest73" if which == "stage12573" else "digest74"] = "0" * 64
    assert_blocked(build(source73, source74, **kwargs), f"{which}_file_pin_mismatch")


@pytest.mark.parametrize("operation", ["duplicate", "missing", "unknown"])
def test_stage12573_root_mutations_fail_closed(sources, operation):
    source73, source74 = copy.deepcopy(sources)
    if operation == "duplicate":
        source73["mapping_rows"][-1] = copy.deepcopy(source73["mapping_rows"][0])
    elif operation == "missing":
        source73["mapping_rows"].pop()
    else:
        source73["mapping_rows"][-1]["opaque_root_identity_sha256"] = "f" * 64
    assert_blocked(build(source73, source74), "stage12573_roots_missing_extra_duplicate_unknown_or_unsorted")


@pytest.mark.parametrize("operation", ["duplicate", "missing", "unknown"])
def test_stage12574_root_mutations_fail_closed(sources, operation):
    source73, source74 = copy.deepcopy(sources)
    if operation == "duplicate":
        source74["acquisition_rows"][-1] = copy.deepcopy(source74["acquisition_rows"][0])
    elif operation == "missing":
        source74["acquisition_rows"].pop()
    else:
        source74["acquisition_rows"][-1]["opaque_root_identity_sha256"] = "f" * 64
    assert_blocked(build(source73, source74), "stage12574_roots_missing_extra_duplicate_unknown_or_unsorted")


def test_row_digest_and_partition_mutations_fail_closed(sources):
    source73, source74 = copy.deepcopy(sources)
    source73["mapping_rows"][0]["resolution_basis_sha256"] = "0" * 64
    assert_blocked(build(source73, source74), "stage12573_row_digest_mismatch")

    source73, source74 = copy.deepcopy(sources)
    source74["acquisition_rows"][0]["stage12573_ledger_row_sha256"] = "0" * 64
    assert_blocked(build(source73, source74), "source_era_provenance_partition_or_completeness_mismatch")

    source73, source74 = copy.deepcopy(sources)
    source73["source_native_lineage_verified_count"] = 18
    assert_blocked(build(source73, source74), "pinned_partition_counts_mutated")


@pytest.mark.parametrize("field", [
    "model_prediction", "label", "gold", "score", "outcome", "reward",
])
def test_any_outcome_conditioned_field_fails_closed_and_is_not_echoed(sources, field):
    source73, source74 = copy.deepcopy(sources)
    source74["acquisition_rows"][0][field] = "secret"
    result = build(source73, source74)
    assert_blocked(result, "outcome_conditioned_field_detected")
    assert "secret" not in json.dumps(result, sort_keys=True)


def test_protected_content_and_authority_injection_fail_closed(sources):
    source73, source74 = copy.deepcopy(sources)
    source73["mapping_rows"][0]["protected_content"] = "secret"
    result = build(source73, source74)
    assert_blocked(result, "protected_content_detected")
    assert "secret" not in json.dumps(result, sort_keys=True)

    source73, source74 = copy.deepcopy(sources)
    source74["acquisition_rows"][0]["training_allowed"] = True
    assert_blocked(build(source73, source74), "stage12574_row_deny_boundary_violated")


def test_stage12572_through_stage12574_compatibility_and_exact_pins():
    stage12572 = M.read_json(ROOT / "runs/summaries/stage12572_source_native_protected_root_preimage_reconstruction_census.json")
    stage12573 = M.read_json(M.SOURCE12573)
    stage12574 = M.read_json(M.SOURCE12574)
    result = M.build()
    assert stage12572["canonical_protected_root_hash_set_sha256"] == M.CANONICAL_ROOT_SET_SHA256
    assert stage12573["canonical_root_set_sha256"] == M.CANONICAL_ROOT_SET_SHA256
    assert stage12573["source_native_lineage_verified_count"] == 17
    assert stage12574["unresolved_historical_binding_count"] == 8
    assert stage12574["source_native_lineage_verified_count"] == 0
    assert all(
        row["independent_authority_status_sha256"] is None
        and all(row[slot] is None for slot in M.SOURCE_NATIVE_PROOF_SLOTS)
        for row in stage12574["acquisition_rows"]
    )
    assert result["retained_verified_lineage_count"] == 17
    assert result["quarantined_unrecoverable_historical_provenance_count"] == 8
    assert M.file_sha256(M.SOURCE12573) == M.PINNED_STAGE12573_FILE_SHA256
    assert M.file_sha256(M.SOURCE12574) == M.PINNED_STAGE12574_FILE_SHA256
    for value in (stage12572, stage12573, stage12574, result):
        assert value["authorization_allowed"] is False

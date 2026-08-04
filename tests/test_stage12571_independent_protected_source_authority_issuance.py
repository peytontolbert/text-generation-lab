from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12571_independent_protected_source_authority_issuance.py"
SPEC = importlib.util.spec_from_file_location("stage12571", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


@pytest.fixture(scope="module")
def predecessor():
    return M.read_json(M.SOURCES["stage12570_candidates"])


@pytest.fixture(scope="module")
def registry():
    return M.read_json(M.SOURCES["stage8663_registry"])


@pytest.fixture(scope="module")
def result():
    return M.build()


def plausible_record(root_hash: str) -> dict:
    issuer = "external-source-authority-v1"
    source_id = "src_abcdef0123456789"
    revision = "2" * 40
    return {
        "record_type": "independent_protected_source_authority_issuance_v1",
        "opaque_stage12105_root_identity_sha256": root_hash,
        "issued_source_id": source_id,
        "source_id_assignment_attestation_sha256": "3" * 64,
        "identity_kind": "git",
        "canonical_repo": "owner/repository",
        "non_git_identity": None,
        "immutable_revision": revision,
        "registry_extension_record": {
            "source_id": source_id,
            "path": "https://authority.example/source?commit=" + revision,
            "kind": "directory",
            "content_hash_prefix": "4" * 64,
            "lineage_hash": "5" * 64,
            "canonical_repo": "owner/repository",
            "immutable_revision": revision,
            "issuer_id": issuer,
        },
        "independent_evidence_chain": [
            {"role": "issuer_authority_attestation", "immutable_uri": "urn:sha256:" + "6" * 64, "sha256": "6" * 64},
            {"role": "same_source_binding_manifest", "immutable_uri": "urn:sha256:" + "7" * 64, "sha256": "7" * 64},
            {"role": "immutable_source_snapshot", "immutable_uri": "urn:sha256:" + "8" * 64, "sha256": "8" * 64},
        ],
        "issuer_id": issuer,
        "issuer_anchor_sha256": "1" * 64,
    }


def row_with_input(result):
    return next(row for row in result["mapping_rows"] if row["issuance_record_count"])


def test_repository_build_emits_exact_25_root_zero_resolution_worklist(result):
    assert result["canonical_protected_root_count"] == 25
    assert result["canonical_protected_root_hash_set_sha256"] == (
        "e85fc0827bfcd9e5819fbc862f060afe35617d00b2c67b77a7effbc811541deb"
    )
    assert (result["resolved_count"], result["unresolved_count"]) == (0, 25)
    assert result["issuance_worklist_count"] == 25
    assert result["decision"] == "issuance_worklist_emitted_no_false_resolution"
    assert result["mapping_status_count_integrity_valid"] is True


def test_each_root_has_concrete_missing_proof_slots(result):
    assert len(result["issuance_worklist"]) == 25
    for item in result["issuance_worklist"]:
        assert item["issuance_status"] == "awaiting_independent_evidence"
        assert "preexisting_independent_upstream_identity" in item["missing_proof_slots"]
        assert "pretrusted_independent_issuer_anchor" in item["missing_proof_slots"]
        assert "deterministic_source_native_bridge_from_stage12105_root_preimage" in item["missing_proof_slots"]
        assert "same_source_binding_manifest" in item["missing_proof_slots"]
        assert "immutable_full_revision" in item["missing_proof_slots"]
        assert "registry_extension_record" in item["missing_proof_slots"]
        assert set(item["forbidden_authority_shortcuts"]) == {
            "artifact_copresence", "copied_root_field", "cross_file_observer_join",
            "current_mutable_checkout", "deterministic_source_id",
            "label_derived_repo_or_commit", "repo_revision_equality", "self_hash",
        }


def test_plausible_record_cannot_bootstrap_authority(predecessor, registry):
    root_hash = predecessor["mapping_rows"][0]["opaque_stage12105_root_identity_sha256"]
    result = M.build_registry_extension_candidate(predecessor, registry, [plausible_record(root_hash)])
    assert (result["resolved_count"], result["unresolved_count"]) == (0, 25)
    blockers = row_with_input(result)["blocking_reasons"]
    assert "issuer_not_pretrusted" in blockers
    assert "source_native_root_preimage_bridge_not_materialized" in blockers
    assert "repo_revision_equality_not_authority" in blockers


@pytest.mark.parametrize("mutation, blocker", [
    ("deterministic_id", "deterministic_root_derived_source_id_forbidden"),
    ("mutable_checkout", "registry_extension_identity_or_lineage_invalid"),
    ("label_revision", "immutable_git_revision_invalid"),
    ("copresence", "artifact_copresence_or_self_hash_chain_forbidden"),
])
def test_authority_shortcuts_fail_closed(predecessor, registry, mutation, blocker):
    root_hash = predecessor["mapping_rows"][0]["opaque_stage12105_root_identity_sha256"]
    record = plausible_record(root_hash)
    if mutation == "deterministic_id":
        source_id = next(iter(M._forbidden_derived_source_ids(root_hash)))
        record["issued_source_id"] = source_id
        record["registry_extension_record"]["source_id"] = source_id
    elif mutation == "mutable_checkout":
        record["registry_extension_record"]["path"] = "/workspace/current-checkout"
    elif mutation == "label_revision":
        record["immutable_revision"] = "repo_label_main"
        record["registry_extension_record"]["immutable_revision"] = "repo_label_main"
    elif mutation == "copresence":
        record["independent_evidence_chain"][1]["sha256"] = record["independent_evidence_chain"][0]["sha256"]
    result = M.build_registry_extension_candidate(predecessor, registry, [record])
    assert result["resolved_count"] == 0
    assert blocker in row_with_input(result)["blocking_reasons"]


def test_stage12571_self_issuer_and_fabricated_anchor_fail(predecessor, registry):
    root_hash = predecessor["mapping_rows"][0]["opaque_stage12105_root_identity_sha256"]
    record = plausible_record(root_hash)
    record["issuer_id"] = "stage12571"
    record["registry_extension_record"]["issuer_id"] = "stage12571"
    record["issuer_anchor_sha256"] = "a" * 64
    result = M.build_registry_extension_candidate(predecessor, registry, [record])
    blockers = row_with_input(result)["blocking_reasons"]
    assert "stage12571_self_issuance_forbidden" in blockers
    assert "issuer_not_pretrusted" in blockers
    assert result["resolved_count"] == 0


def test_repo_revision_substitution_and_swapped_rows_fail(predecessor, registry):
    roots = [row["opaque_stage12105_root_identity_sha256"] for row in predecessor["mapping_rows"][:2]]
    first, second = plausible_record(roots[0]), plausible_record(roots[1])
    first["canonical_repo"] = "substitute/one"
    first["registry_extension_record"]["canonical_repo"] = "substitute/one"
    second["canonical_repo"] = "substitute/two"
    second["registry_extension_record"]["canonical_repo"] = "substitute/two"
    first["opaque_stage12105_root_identity_sha256"], second["opaque_stage12105_root_identity_sha256"] = roots[1], roots[0]
    result = M.build_registry_extension_candidate(predecessor, registry, [first, second])
    assert result["resolved_count"] == 0
    assert all(
        "copied_root_field_not_source_native_bridge" in row["blocking_reasons"]
        for row in result["mapping_rows"] if row["issuance_record_count"]
    )


def test_unknown_and_duplicate_roots_fail_closed(predecessor, registry):
    root_hash = predecessor["mapping_rows"][0]["opaque_stage12105_root_identity_sha256"]
    unknown = plausible_record("f" * 64)
    duplicate = plausible_record(root_hash)
    result = M.build_registry_extension_candidate(predecessor, registry, [unknown, duplicate, dict(duplicate)])
    assert result["unknown_issuance_record_count"] == 1
    assert result["duplicate_issuance_record_count"] == 1
    assert result["issuance_record_count_reconciliation_valid"] is True
    assert "unknown_issuance_record_root" in result["blocking_reasons"]
    assert "duplicate_issuance_records" in result["blocking_reasons"]
    assert result["resolved_count"] == 0


def test_self_hash_and_existing_registry_id_are_not_authority(predecessor, registry):
    root_hash = predecessor["mapping_rows"][0]["opaque_stage12105_root_identity_sha256"]
    record = plausible_record(root_hash)
    existing = registry["records"][0]["source_id"]
    record["issued_source_id"] = existing
    record["registry_extension_record"]["source_id"] = existing
    record["independent_evidence_chain"][0]["sha256"] = root_hash
    result = M.build_registry_extension_candidate(predecessor, registry, [record])
    blockers = row_with_input(result)["blocking_reasons"]
    assert "issued_source_id_already_registered" in blockers
    assert "self_hash_not_authority" in blockers
    assert result["resolved_count"] == 0


def test_registry_mutation_and_dirty_checkout_fail(predecessor, registry):
    mutated = json.loads(json.dumps(registry))
    mutated["records"][0]["path"] = "/workspace/dirty-checkout"
    root_hash = predecessor["mapping_rows"][0]["opaque_stage12105_root_identity_sha256"]
    record = plausible_record(root_hash)
    record["registry_extension_record"]["path"] = "/workspace/dirty-checkout"
    result = M.build_registry_extension_candidate(predecessor, mutated, [record])
    assert "stage8663_registry_mutation_detected" in result["blocking_reasons"]
    assert "registry_extension_identity_or_lineage_invalid" in row_with_input(result)["blocking_reasons"]
    assert result["resolved_count"] == 0


def test_outcome_field_injection_is_schema_error(predecessor, registry):
    root_hash = predecessor["mapping_rows"][0]["opaque_stage12105_root_identity_sha256"]
    record = plausible_record(root_hash)
    record["verifier_outcome"] = "PASS"
    result = M.build_registry_extension_candidate(predecessor, registry, [record])
    assert "issuance_schema_not_exact" in row_with_input(result)["blocking_reasons"]
    assert result["resolved_count"] == 0


def test_stage8663_remains_byte_identical_when_stage12571_writes(tmp_path):
    before = M.SOURCES["stage8663_registry"].read_bytes()
    old_out, old_summary = M.OUT, M.SUMMARY
    try:
        M.OUT, M.SUMMARY = tmp_path / "out", tmp_path / "summary.json"
        assert M.main() == 0
    finally:
        M.OUT, M.SUMMARY = old_out, old_summary
    assert M.SOURCES["stage8663_registry"].read_bytes() == before


def test_digests_and_exact_accounting(result):
    assert result["mapping_row_set_sha256"] == M.stable_hash(sorted(
        row["mapping_row_sha256"] for row in result["mapping_rows"]
    ))
    assert result["issuance_worklist_set_sha256"] == M.stable_hash(sorted(
        M.stable_hash(row) for row in result["issuance_worklist"]
    ))
    assert result["unknown_issuance_record_set_sha256"] == M.stable_hash([])
    assert result["issuance_record_input_count"] == (
        result["known_issuance_record_count"] + result["unknown_issuance_record_count"]
    )


def test_no_protected_or_outcome_content_and_all_authority_false(result):
    forbidden = {
        "prompt", "prompt_text", "target", "target_text", "gold", "gold_label",
        "verifier_output", "verifier_outcome",
    }

    def keys(value):
        if isinstance(value, dict):
            yield from value
            for child in value.values():
                yield from keys(child)
        elif isinstance(value, list):
            for child in value:
                yield from keys(child)

    assert forbidden.isdisjoint(keys(result))
    assert result["protected_content_emitted"] is False
    assert all(result[field] is False for field in M.AUTHORITY_FIELDS)
    assert all(
        all(row[field] is False for field in M.AUTHORITY_FIELDS)
        for row in result["mapping_rows"]
    )
    assert "PROTECTED_PROMPT" not in json.dumps(result, sort_keys=True)

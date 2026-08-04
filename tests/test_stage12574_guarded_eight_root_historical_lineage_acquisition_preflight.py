from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12574_guarded_eight_root_historical_lineage_acquisition_preflight.py"
SPEC = importlib.util.spec_from_file_location("stage12574", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


@pytest.fixture(scope="module")
def source():
    return M.read_json(M.SOURCE)


def build(source, *, source_digest=M.PINNED_STAGE12573_FILE_SHA256,
          era_digests=None, evidence_rows=()):
    return M.build_preflight(
        source,
        source_file_sha256=source_digest,
        source_era_file_sha256=(
            M.PINNED_SOURCE_ERA_FILE_SHA256 if era_digests is None else era_digests
        ),
        evidence_rows=evidence_rows,
    )


def assert_blocked(result, reason):
    assert result["decision"] == "blocked"
    assert reason in result["blocking_reasons"]
    assert result["acquisition_rows"] == []
    assert result["acquisition_row_count"] == 0
    assert result["source_native_lineage_verified_count"] == 0
    assert result["unresolved_historical_binding_count"] == 0
    assert all(result[field] is False for field in M.DENY_FIELDS)


def evidence_for(row, **overrides):
    evidence = {
        "opaque_root_identity_sha256": row["opaque_root_identity_sha256"],
        "stage12573_ledger_row_sha256": row["stage12573_ledger_row_sha256"],
        "source_era_artifact_set_sha256": row["source_era_artifact_set_sha256"],
        **{slot: None for slot in M.ALL_PROOF_SLOTS},
    }
    evidence[M.AUTHORITY_PROOF_SLOT] = row[M.AUTHORITY_PROOF_SLOT]
    evidence.update(overrides)
    evidence["evidence_row_sha256"] = M.stable_hash(evidence)
    return evidence


def complete_evidence(row):
    values = {
        slot: M.stable_hash({"slot": slot, "root": row["opaque_root_identity_sha256"]})
        for slot in M.SOURCE_NATIVE_PROOF_SLOTS[:-1]
    }
    evidence = evidence_for(row, **values)
    evidence["constructor_commitment_join_sha256"] = M._constructor_join(evidence)
    evidence[M.AUTHORITY_PROOF_SLOT] = M.stable_hash({"fabricated_authority": True})
    evidence["evidence_row_sha256"] = M.stable_hash(
        M._body(evidence, "evidence_row_sha256")
    )
    return evidence


def test_exact_eight_hash_only_unresolved_acquisition_rows():
    result = M.build()
    assert result["decision"] == "verified_deny_only"
    assert result["blocking_reasons"] == []
    assert (
        result["acquisition_row_count"],
        result["source_native_lineage_verified_count"],
        result["unresolved_historical_binding_count"],
        result["independently_authorized_count"],
    ) == (8, 0, 8, 0)
    assert result["unresolved_root_set_sha256"] == M.UNRESOLVED_ROOT_SET_SHA256
    assert result["runtime_source_era_records_read"] is False
    assert result["current_checkout_can_promote"] is False
    assert (
        "current_checkout_similarity_and_later_copies_are_diagnostic_only"
        in result["non_authorizing_conditions"]
    )
    roots = [row["opaque_root_identity_sha256"] for row in result["acquisition_rows"]]
    assert roots == sorted(roots) and len(set(roots)) == 8
    for row in result["acquisition_rows"]:
        assert row["lineage_status"] == "unresolved_historical_binding"
        assert row["missing_proof_slots"] == list(M.ALL_PROOF_SLOTS)
        assert all(row[slot] is None for slot in M.ALL_PROOF_SLOTS)
        assert all(row[field] is False for field in M.DENY_FIELDS)
        for key, value in row.items():
            if key.endswith("_sha256") and value is not None:
                assert M._digest(value), key


def test_source_era_files_are_pinned_without_parsing_protected_records():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "read_json(SOURCE)" in text
    assert "read_json(SOURCE_ERA" not in text
    assert "runtime_source_era_records_read\": False" in text
    assert {
        key: M.file_sha256(path) for key, path in M.SOURCE_ERA_FILES.items()
    } == M.PINNED_SOURCE_ERA_FILE_SHA256


def test_checkout_is_diagnostic_and_complete_proof_cannot_promote(source):
    baseline = build(source)
    row = baseline["acquisition_rows"][0]
    diagnostic_hash = M.stable_hash({"diagnostic": True})
    diagnostic = evidence_for(
        row, current_checkout_observation_sha256=diagnostic_hash
    )
    result = build(source, evidence_rows=[diagnostic])
    assert (
        result["source_native_lineage_verified_count"],
        result["unresolved_historical_binding_count"],
    ) == (0, 8)
    observed = result["acquisition_rows"][0]
    assert observed[M.DIAGNOSTIC_PROOF_SLOT] == diagnostic_hash
    assert M.DIAGNOSTIC_PROOF_SLOT not in observed["missing_proof_slots"]
    assert all(observed[slot] is None for slot in M.SOURCE_NATIVE_PROOF_SLOTS)
    assert observed[M.AUTHORITY_PROOF_SLOT] is None

    result = build(source, evidence_rows=[complete_evidence(row)])
    assert (
        result["acquisition_row_count"],
        result["source_native_lineage_verified_count"],
        result["unresolved_historical_binding_count"],
    ) == (8, 0, 8)
    unresolved = result["acquisition_rows"][0]
    assert unresolved["lineage_status"] == "unresolved_historical_binding"
    assert all(unresolved[slot] is None for slot in M.ALL_PROOF_SLOTS)
    assert unresolved["missing_proof_slots"] == list(M.ALL_PROOF_SLOTS)
    assert all(unresolved[field] is False for field in M.DENY_FIELDS)


def test_fabricated_64hex_proof_is_not_retained_or_promoted(source):
    row = build(source)["acquisition_rows"][0]
    evidence = evidence_for(
        row, **{slot: "a" * 64 for slot in M.SOURCE_NATIVE_PROOF_SLOTS[:-1]}
    )
    evidence["constructor_commitment_join_sha256"] = M._constructor_join(evidence)
    evidence[M.DIAGNOSTIC_PROOF_SLOT] = "a" * 64
    evidence[M.AUTHORITY_PROOF_SLOT] = "a" * 64
    evidence["evidence_row_sha256"] = M.stable_hash(
        M._body(evidence, "evidence_row_sha256")
    )
    result = build(source, evidence_rows=[evidence])
    assert (
        result["acquisition_row_count"],
        result["source_native_lineage_verified_count"],
        result["unresolved_historical_binding_count"],
    ) == (8, 0, 8)
    unresolved = result["acquisition_rows"][0]
    assert unresolved["lineage_status"] == "unresolved_historical_binding"
    assert all(unresolved[slot] is None for slot in M.SOURCE_NATIVE_PROOF_SLOTS)
    assert unresolved[M.AUTHORITY_PROOF_SLOT] is None
    assert unresolved[M.DIAGNOSTIC_PROOF_SLOT] == "a" * 64


@pytest.mark.parametrize("source_digest", [None, "0" * 64])
def test_missing_or_mutated_stage12573_pin_fails_closed(source, source_digest):
    assert_blocked(build(source, source_digest=source_digest), "stage12573_file_pin_mismatch")


def test_source_era_pin_schema_and_digest_mutations_fail_closed(source):
    missing = dict(M.PINNED_SOURCE_ERA_FILE_SHA256)
    missing.pop("stage11576_atlas")
    assert_blocked(build(source, era_digests=missing), "source_era_file_pin_set_mismatch")
    mutated = dict(M.PINNED_SOURCE_ERA_FILE_SHA256)
    mutated["stage11576_root_records"] = "0" * 64
    assert_blocked(build(source, era_digests=mutated), "source_era_file_pin_set_mismatch")


@pytest.mark.parametrize("operation", ["duplicate", "missing", "unknown"])
def test_duplicate_missing_or_unknown_stage12573_roots_fail_closed(source, operation):
    mutated = copy.deepcopy(source)
    if operation == "duplicate":
        mutated["mapping_rows"][-1] = copy.deepcopy(mutated["mapping_rows"][0])
    elif operation == "missing":
        mutated["mapping_rows"].pop()
    else:
        mutated["mapping_rows"][-1]["opaque_root_identity_sha256"] = "f" * 64
    result = build(mutated)
    assert_blocked(result, ("unresolved_root_set_missing_extra_duplicate_or_unknown" if operation == "unknown" else "stage12573_roots_missing_extra_duplicate_or_unsorted"))
    assert "stage12573_summary_digest_mismatch" in result["blocking_reasons"]


def test_schema_row_digest_and_join_mutations_fail_closed(source):
    mutated = copy.deepcopy(source)
    mutated["unexpected"] = False
    assert_blocked(build(mutated), "stage12573_schema_not_exact")
    mutated = copy.deepcopy(source)
    mutated["mapping_rows"][0]["resolution_basis_sha256"] = "0" * 64
    assert_blocked(build(mutated), "stage12573_ledger_row_digest_mismatch")

    baseline = build(source)
    first, second = baseline["acquisition_rows"][:2]
    evidence = complete_evidence(first)
    assert_blocked(build(source, evidence_rows=[evidence, evidence]), "duplicate_source_era_evidence_root")
    crossed = complete_evidence(first)
    crossed["stage12573_ledger_row_sha256"] = second["stage12573_ledger_row_sha256"]
    crossed["evidence_row_sha256"] = M.stable_hash(M._body(crossed, "evidence_row_sha256"))
    assert_blocked(build(source, evidence_rows=[crossed]), "cross_root_stage12573_join")
    crossed = complete_evidence(first)
    crossed["source_era_artifact_set_sha256"] = "0" * 64
    crossed["evidence_row_sha256"] = M.stable_hash(M._body(crossed, "evidence_row_sha256"))
    assert_blocked(build(source, evidence_rows=[crossed]), "source_era_artifact_join_mismatch")
    crossed = complete_evidence(first)
    crossed["constructor_commitment_join_sha256"] = "0" * 64
    crossed["evidence_row_sha256"] = M.stable_hash(M._body(crossed, "evidence_row_sha256"))
    assert_blocked(build(source, evidence_rows=[crossed]), "cross_root_or_source_constructor_join")


def test_labels_preimages_and_protected_content_are_rejected(source):
    row = build(source)["acquisition_rows"][0]
    evidence = complete_evidence(row)
    evidence["label"] = "secret"
    result = build(source, evidence_rows=[evidence])
    assert_blocked(result, "protected_or_preimage_content_detected")
    assert "secret" not in json.dumps(result, sort_keys=True)


def test_stage12572_and_stage12573_compatibility():
    stage12572 = M.read_json(
        ROOT / "runs/summaries/stage12572_source_native_protected_root_preimage_reconstruction_census.json"
    )
    stage12573 = M.read_json(M.SOURCE)
    result = M.build()
    assert stage12572["historical_binding_missing_count"] == 8
    assert stage12573["unresolved_historical_binding_count"] == 8
    assert result["acquisition_row_count"] == 8
    assert M.file_sha256(M.SOURCE) == M.PINNED_STAGE12573_FILE_SHA256
    assert stage12573["summary_record_sha256"] == M.PINNED_STAGE12573_SUMMARY_RECORD_SHA256
    assert stage12572["authorization_allowed"] is False
    assert stage12573["authorization_allowed"] is False
    assert result["authorization_allowed"] is False

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12573_source_native_lineage_resolution_ledger.py"
SPEC = importlib.util.spec_from_file_location("stage12573", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


@pytest.fixture(scope="module")
def source():
    return M.read_json(M.SOURCE)


def build(source, digest=M.PINNED_STAGE12572_FILE_SHA256):
    return M.build_ledger(source, source_file_sha256=digest)


def assert_blocked(result, reason):
    assert result["decision"] == "blocked"
    assert reason in result["blocking_reasons"]
    assert result["mapping_rows"] == []
    assert result["mapping_row_count"] == 0
    assert result["source_native_lineage_verified_count"] == 0
    assert result["unresolved_historical_binding_count"] == 0
    assert all(result[field] is False for field in M.DENY_FIELDS)


def test_exact_25_row_hash_only_ledger_and_root_digest():
    result = M.build()
    assert result["decision"] == "verified_deny_only"
    assert result["blocking_reasons"] == []
    assert (
        result["mapping_row_count"],
        result["source_native_lineage_verified_count"],
        result["unresolved_historical_binding_count"],
        result["independently_authorized_count"],
    ) == (25, 17, 8, 0)
    assert result["canonical_root_set_sha256"] == (
        "e85fc0827bfcd9e5819fbc862f060afe35617d00b2c67b77a7effbc811541deb"
    )
    assert result["non_authorizing_conditions"] == [
        "stage12572_independent_source_authority_absent"
    ]
    assert all(result[field] is False for field in M.DENY_FIELDS)
    statuses = [row["resolution_status"] for row in result["mapping_rows"]]
    assert statuses.count("source_native_lineage_verified") == 17
    assert statuses.count("unresolved_historical_binding") == 8
    allowed_non_hash = {
        "resolution_status", "source_native_lineage_evidence_sha256",
        *M.DENY_FIELDS,
    }
    for row in result["mapping_rows"]:
        assert all(row[field] is False for field in M.DENY_FIELDS)
        if row["resolution_status"] == "source_native_lineage_verified":
            assert M._digest(row["source_native_lineage_evidence_sha256"])
        else:
            assert row["source_native_lineage_evidence_sha256"] is None
        for key, value in row.items():
            if key not in allowed_non_hash:
                assert M._digest(value), key


def test_clearance_guards_are_immutable_false():
    result = M.build()
    for field in M.CLEARANCE_FIELDS:
        assert result[field] is False
        assert all(row[field] is False for row in result["mapping_rows"])


def test_private_preimage_pin_mutation_is_never_echoed(source):
    mutated = copy.deepcopy(source)
    mutated["summary_record_sha256"] = "PRIVATE PREIMAGE"
    result = build(mutated, "PRIVATE PREIMAGE")
    assert_blocked(result, "stage12572_file_pin_mismatch")
    assert "stage12572_summary_digest_mismatch" in result["blocking_reasons"]
    assert result["source_file_sha256"] is None
    assert result["source_summary_record_sha256"] is None
    assert "PRIVATE PREIMAGE" not in json.dumps(result, sort_keys=True)


def test_consumes_only_pinned_stage12572_v5():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "stage12569_" not in text
    assert "stage12570_" not in text
    assert "stage12571_" not in text
    assert "stage12572_source_native_committed_root_identity_census_v5" in text
    assert M.file_sha256(M.SOURCE) == M.PINNED_STAGE12572_FILE_SHA256


@pytest.mark.parametrize("digest", [None, "0" * 64])
def test_missing_or_mismatched_source_pin_fails_closed(source, digest):
    assert_blocked(build(source, digest), "stage12572_file_pin_mismatch")


def test_stage12572_blockers_and_non_authorizing_condition_fail_closed(source):
    mutated = copy.deepcopy(source)
    mutated["decision"] = "blocked"
    mutated["blocking_reasons"] = ["upstream_failure"]
    assert_blocked(build(mutated), "stage12572_blocked_or_unaccepted")
    mutated = copy.deepcopy(source)
    mutated["non_authorizing_conditions"] = []
    assert_blocked(build(mutated), "stage12572_non_authorizing_condition_mismatch")


@pytest.mark.parametrize("operation", ["duplicate", "missing", "unknown"])
def test_duplicate_missing_or_unknown_roots_fail_closed(source, operation):
    mutated = copy.deepcopy(source)
    rows = mutated["census_rows"]
    if operation == "duplicate":
        rows[-1] = copy.deepcopy(rows[0])
    elif operation == "missing":
        rows.pop()
    else:
        rows[-1]["opaque_stage12105_root_identity_sha256"] = "f" * 64
    assert_blocked(build(mutated), "canonical_root_set_digest_mismatch")


def test_altered_bridge_split_and_source_join_fail_closed(source):
    mutated = copy.deepcopy(source)
    row = next(item for item in mutated["census_rows"] if item["immutable_source_bridge"])
    row["immutable_source_bridge"] = False
    row["proof_status"] = "preimage_commitment_historical_binding_missing"
    row["bridge_kind"] = None
    row["source_join_sha256"] = None
    row_body = {key: value for key, value in row.items() if key != "census_row_sha256"}
    row["census_row_sha256"] = M.stable_hash(row_body)
    assert_blocked(build(mutated), "verified_root_set_digest_or_bridge_split_mismatch")

    mutated = copy.deepcopy(source)
    row = next(item for item in mutated["census_rows"] if item["immutable_source_bridge"])
    row["source_join_sha256"] = "0" * 64
    assert_blocked(build(mutated), "stage12572_census_row_digest_mismatch")


def test_schema_label_injection_and_protected_content_fail_closed(source):
    mutated = copy.deepcopy(source)
    mutated["census_rows"][0]["label"] = "source_native_lineage_verified"
    assert_blocked(build(mutated), "stage12572_row_schema_not_exact")
    mutated = copy.deepcopy(source)
    mutated["census_rows"][0]["gold"] = "secret"
    assert_blocked(build(mutated), "protected_content_detected")


def test_authority_injection_and_self_digest_tampering_fail_closed(source):
    mutated = copy.deepcopy(source)
    mutated["census_rows"][0]["authorization_allowed"] = True
    assert_blocked(build(mutated), "stage12572_row_deny_boundary_violated")
    mutated = copy.deepcopy(source)
    mutated["summary_record_sha256"] = "0" * 64
    assert_blocked(build(mutated), "stage12572_summary_digest_mismatch")


def test_bounded_stage12569_through_12572_compatibility():
    summaries = {
        stage: next((ROOT / "runs/summaries").glob(f"stage{stage}_*.json"))
        for stage in range(12569, 12573)
    }
    values = {
        stage: json.loads(path.read_text(encoding="utf-8"))
        for stage, path in summaries.items()
    }
    expected_root = M.CANONICAL_ROOT_SET_SHA256
    assert values[12569]["blocking_reasons"] == ["protected_legacy_lineage_unresolved"]
    assert values[12570]["canonical_protected_root_hash_set_sha256"] == expected_root
    assert values[12571]["canonical_protected_root_hash_set_sha256"] == expected_root
    assert values[12572]["canonical_protected_root_hash_set_sha256"] == expected_root
    assert values[12570]["authorization_allowed"] is False
    assert values[12571]["authorization_allowed"] is False
    assert values[12572]["independently_authorized_count"] == 0
    assert values[12572]["record_type"].endswith("_v5")

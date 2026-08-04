from __future__ import annotations

import copy
import importlib.util
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12580_identity_stratum_preoutcome_commitment.py"
SPEC = importlib.util.spec_from_file_location("stage12580", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def canonical():
    return json.loads(M.STAGE12579.read_bytes())


def detached(record, digest=M.STAGE12579_FILE_SHA256):
    return M.build_from_record(record, digest)


def test_production_reads_and_binds_one_byte_snapshot():
    result = M.build_stage()
    audit = result["audit_only_stage12579_validation"]
    assert result["local_identity_preimage_constructed"] is True
    assert audit["stage12579_bytes_read_once"] is True
    assert audit["sha256_and_json_parse_share_same_bytes"] is True
    assert audit["stage12579_file_pin_valid"] is True
    assert audit["request_hashes_valid"] is True


def test_unpublished_chronology_is_explicitly_blocked_and_all_authority_is_false():
    result = M.build_stage()
    assert result["decision"] == "local_identity_preimage_constructed_unpublished_zero_credit"
    assert result["commitment_valid"] is False
    assert result["preoutcome_chronology_proven"] is False
    assert result["externally_published"] is False
    assert result["trusted_timestamp"] is False
    assert set(M.CHRONOLOGY_BLOCKERS) <= set(result["blocking_reasons"])
    assert all(result[field] is False for field in M.DENY_FIELDS)


def test_each_identity_binds_full_ordered_four_stratum_tuple():
    result = M.build_stage()
    assert len(result["ordered_manifest"]) == 8
    assert all(row["required_transition_strata"] == list(M.STRATA) for row in result["ordered_manifest"])
    assert all(set(row) == M.ROW_KEYS for row in result["ordered_manifest"])


def test_primary_routing_is_balanced_but_uncommitted_and_nonauthoritative():
    result = M.build_stage()
    routing = result["primary_stratum_routing_metadata"]
    by_id = {row["opaque_candidate_id"]: row["language"] for row in result["ordered_manifest"]}
    for language in M.quota():
        counts = Counter(row["primary_stratum"] for row in routing if by_id[row["opaque_candidate_id"]] == language)
        assert counts == Counter(dict.fromkeys(M.STRATA, 1))
    assert all(row["authoritative"] is False and row["committed"] is False for row in routing)
    assert "primary_stratum" not in json.dumps(result["commitment_preimage"], sort_keys=True)


def test_path_relocation_does_not_change_manifest_or_commitment_root():
    original = canonical()["requests"]
    relocated = copy.deepcopy(original)
    for index, row in enumerate(relocated):
        row["checkout"] = f"/relocated/{index}"
    left_manifest, left_root = M.construct_preimages(original)
    right_manifest, right_root = M.construct_preimages(relocated)
    assert M.stable_hash(left_manifest) == M.stable_hash(right_manifest)
    assert M.stable_hash(left_root) == M.stable_hash(right_root)
    assert "checkout" not in json.dumps(left_root, sort_keys=True)
    assert "path" not in json.dumps(left_root, sort_keys=True)


def test_git_oids_request_hashes_and_audit_hash_are_not_in_preimage():
    result = M.build_stage()
    audit = result["audit_only_stage12579_validation"]
    serialized = json.dumps(result["commitment_preimage"], sort_keys=True)
    assert audit["rust_diagnostic_commit_oids_explicitly_excluded"] is True
    assert audit["requested_commit_tree_blob_commands_reason_codes_path_absent"] is True
    assert audit["commitment_preimage_forbidden_paths"] == []
    assert M.STAGE12579_FILE_SHA256 not in serialized
    assert not any(value in serialized for value in M.EXPECTED_REQUEST_HASHES)
    assert not any(row["requested_commit"] in serialized for row in canonical()["requests"][:4])


def test_detached_record_forgery_never_constructs_even_with_claimed_pin():
    forged = canonical()
    forged["requests"][0].update({
        "candidate": True,
        "preoutcome_authority": True,
        "root_credit": True,
        "nested": {"verifier_result": "pass", "model_score": 1.0},
    })
    result = detached(forged)
    assert result["local_identity_preimage_constructed"] is False
    assert result["commitment_root_sha256"] is None
    assert "detached_record_noncanonical" in result["blocking_reasons"]
    assert "outcome_field_present" in result["blocking_reasons"]
    assert "nonzero_candidate_or_authority:0" in result["blocking_reasons"]


def test_even_exact_detached_record_and_digest_are_noncanonical():
    result = detached(canonical())
    assert result["local_identity_preimage_constructed"] is False
    assert result["commitment_valid"] is False
    assert "detached_record_noncanonical" in result["blocking_reasons"]


def test_caller_issuance_nonce_salt_and_record_overrides_are_noncanonical():
    for kwargs in (
        {"issuance": {"issuer": "forged"}},
        {"nonce": "0" * 64},
        {"salt": "0" * 64},
        {"request_artifact": canonical(), "observed_file_sha256": M.STAGE12579_FILE_SHA256},
    ):
        result = M.build_stage(**kwargs)
        assert result["local_identity_preimage_constructed"] is False
        assert "caller_override_noncanonical" in result["blocking_reasons"]


def test_mutating_returned_metadata_cannot_change_fresh_build():
    first = M.build_stage()
    first["commitment_preimage"]["domain_separation"]["salt_hex"] = "forged"
    first["ordered_manifest"][0]["required_transition_strata"].reverse()
    second = M.build_stage()
    assert second["commitment_preimage"]["domain_separation"]["salt_hex"] == M.DOMAIN_SEPARATION_SALT
    assert second["ordered_manifest"][0]["required_transition_strata"] == list(M.STRATA)


def test_reorder_quota_alias_outcome_and_pin_hostility_fail_closed():
    cases = []
    reordered = canonical()
    reordered["requests"][0], reordered["requests"][1] = reordered["requests"][1], reordered["requests"][0]
    cases.append(reordered)
    missing_quota = canonical()
    del missing_quota["request_quota_by_language"]
    cases.append(missing_quota)
    alias = canonical()
    alias["requests"][1]["source_id"] = alias["requests"][0]["source_id"]
    alias["requests"][1]["canonical_remote"] = alias["requests"][0]["canonical_remote"]
    cases.append(alias)
    outcome = canonical()
    outcome["requests"][0]["test_outcome"] = "pass"
    cases.append(outcome)
    for record in cases:
        assert detached(record)["local_identity_preimage_constructed"] is False
    assert "stage12579_file_pin_mismatch" in M.build_from_record(canonical(), "0" * 64)["blocking_reasons"]

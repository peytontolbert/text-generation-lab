from __future__ import annotations

import ast
import copy
import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12570_protected_universe_authority_candidates.py"
SPEC = importlib.util.spec_from_file_location("stage12570", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


@pytest.fixture(scope="module")
def result():
    return M.build()


def test_exact_canonical_25_root_identity_and_17_8_partition(result):
    assert result["canonical_protected_root_count"] == 25
    assert result["mapping_row_count"] == 25
    assert result["canonical_protected_root_hash_set_sha256"] == (
        "e85fc0827bfcd9e5819fbc862f060afe35617d00b2c67b77a7effbc811541deb"
    )
    assert (
        result["resolved_count"],
        result["evidence_candidate_count"],
        result["unresolved_count"],
    ) == (0, 17, 8)
    assert result["mapping_status_count_integrity_valid"] is True
    assert {
        row["opaque_stage12105_root_identity_sha256"]
        for row in result["mapping_rows"]
        if row["mapping_status"] == "candidate"
    } == M.CANDIDATE_ROOT_HASHES


def test_canonical_root_digest_hashes_sorted_opaque_root_hashes(result):
    root_hashes = sorted(
        row["opaque_stage12105_root_identity_sha256"]
        for row in result["mapping_rows"]
    )
    assert result["canonical_protected_root_hash_set_sha256"] == M.stable_hash(
        root_hashes
    )
    assert result["digest_definitions"][
        "canonical_protected_root_hash_set_sha256"
    ] == (
        "sha256(canonical_json(sorted("
        "opaque_stage12105_root_identity_sha256)))"
    )
    assert result["mapping_row_set_sha256"] != result[
        "canonical_protected_root_hash_set_sha256"
    ]


def test_real_stage8663_registry_schema_is_accepted_without_mutation(result):
    registry = M.read_json(M.REGISTRY)
    records, blockers = M.registry_records(registry)
    assert len(records) == 36
    assert blockers == []
    assert all(M.REGISTRY_REQUIRED_FIELDS.issubset(row) for row in records.values())
    assert "artifact_sha256" not in M.REGISTRY_REQUIRED_FIELDS
    assert "issuer" not in M.REGISTRY_REQUIRED_FIELDS
    assert result["authority_adapter_schema"]["stage8663_mutated"] is False
    assert all(
        row["authority_adapter_record"]["registered_parent_source_id"] is None
        for row in result["mapping_rows"]
        if row["mapping_status"] == "candidate"
    )


def test_observer_exact_sources_materialize_17_candidates(result):
    candidates = [
        row["authority_adapter_record"]
        for row in result["mapping_rows"]
        if row["mapping_status"] == "candidate"
    ]
    assert Counter(row["issuer"] for row in candidates) == {
        "stage11354": 1,
        "stage11364": 1,
        "stage11537": 2,
        "stage11545": 1,
        "stage11576": 11,
        "stage11811": 1,
    }
    stage11537 = [row for row in candidates if row["issuer"] == "stage11537"]
    assert all(
        row["same_source_proof_status"] == "cross_file_root_join_unanchored"
        and len(row["evidence_artifacts"]) == 2
        for row in stage11537
    )


def test_candidates_report_missing_fields_instead_of_fabricating_them(result):
    candidates = [
        row["authority_adapter_record"]
        for row in result["mapping_rows"]
        if row["mapping_status"] == "candidate"
    ]
    for adapter in candidates:
        assert adapter["canonical_repo"] is None
        assert adapter["registered_parent_source_id"] is None
        assert adapter["independent_issuer_anchor_sha256"] is None
        assert adapter["resolution_eligible"] is False
        assert "registered_parent_source_id" in adapter["missing_required_fields"]
        assert (
            "same_source_proof_independently_anchored"
            in adapter["missing_required_fields"]
        )
    stage11576 = [row for row in candidates if row["issuer"] == "stage11576"]
    assert all(row["immutable_full_revision"] is None for row in stage11576)
    assert all(
        "immutable_full_revision" in row["missing_required_fields"]
        for row in stage11576
    )


def test_no_candidate_can_be_promoted_by_caller_assertion():
    registry = M.read_json(M.REGISTRY)
    adapters = M.observer_adapter_records()
    adapters[0] = {
        **adapters[0],
        "resolution_eligible": True,
        "same_source_proof_status": "independently_anchored",
        "independent_issuer_anchor_sha256": "a" * 64,
    }
    result = M.build_candidates(M.read_jsonl(M.SEALED), registry, adapters)
    row_hash = adapters[0]["opaque_stage12105_root_identity_sha256"]
    row = next(
        item for item in result["mapping_rows"]
        if item["opaque_stage12105_root_identity_sha256"] == row_hash
    )
    assert row["mapping_status"] == "candidate"
    assert result["resolved_count"] == 0
    assert result["invalid_authority_adapter_record_count"] == 1
    assert "invalid_authority_adapter_records" in result["blocking_reasons"]


def test_unknown_root_evidence_is_blocked_and_count_reconciled():
    registry = M.read_json(M.REGISTRY)
    adapters = M.observer_adapter_records()
    unknown = copy.deepcopy(adapters[0])
    unknown["opaque_stage12105_root_identity_sha256"] = "f" * 64
    adapters.append(unknown)
    result = M.build_candidates(M.read_jsonl(M.SEALED), registry, adapters)
    assert result["authority_adapter_input_record_count"] == 18
    assert result["known_authority_adapter_record_count"] == 17
    assert result["unknown_authority_adapter_record_count"] == 1
    assert result["authority_adapter_count_reconciliation_valid"] is True
    assert "unknown_authority_adapter_root_hash" in result["blocking_reasons"]
    assert result["evidence_candidate_count"] == 17
    assert result["unresolved_count"] == 8


def test_all_named_set_digests_match_their_declared_inputs(result):
    assert result["authority_adapter_record_set_sha256"] == M.stable_hash(sorted(
        M.stable_hash(M.adapter_projection(
            row["authority_adapter_record"]
        ))
        for row in result["mapping_rows"]
        if row["authority_adapter_record"] is not None
    ))
    assert result["mapping_row_set_sha256"] == M.stable_hash(sorted(
        row["mapping_row_sha256"] for row in result["mapping_rows"]
    ))
    assert result["unknown_adapter_record_hash_set_sha256"] == M.stable_hash([])
    assert set(result["digest_definitions"]) == {
        "canonical_protected_root_hash_set_sha256",
        "authority_adapter_record_set_sha256",
        "mapping_row_set_sha256",
        "unknown_adapter_record_hash_set_sha256",
    }


def test_no_stage12563_sha_looking_root_inference(result):
    source = SCRIPT.read_text(encoding="utf-8")
    assert "certified_git_identity" not in source
    assert 'split("::")' not in source
    stage11576 = [
        row["authority_adapter_record"]
        for row in result["mapping_rows"]
        if row["mapping_status"] == "candidate"
        and row["authority_adapter_record"]["issuer"] == "stage11576"
    ]
    assert len(stage11576) == 11
    assert all(row["immutable_full_revision"] is None for row in stage11576)


def test_no_duplicate_literal_dict_keys():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = [
            key.value for key in node.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        ]
        assert len(keys) == len(set(keys))


def test_protected_content_excluded_and_all_authority_false(result):
    forbidden = {
        "prompt_text", "target_text", "input_text", "decoder_text", "target",
        "target_label", "gold", "gold_label", "verifier_outcome",
        "verifier_execution", "opaque_options",
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
    assert all(result[name] is False for name in M.AUTHORITY_FIELDS)
    assert all(
        all(row[name] is False for name in M.AUTHORITY_FIELDS)
        for row in result["mapping_rows"]
    )
    encoded = json.dumps(result, sort_keys=True)
    assert "PROTECTED_PROMPT" not in encoded
    assert "PROTECTED_TARGET" not in encoded

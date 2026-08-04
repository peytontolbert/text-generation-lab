from __future__ import annotations

import copy
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "stage12565", ROOT / "scripts/build_stage12565_paired_pre_outcome_candidate_commitment_v2.py"
)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def inputs():
    return {
        "ready_rows": M.read_jsonl(M.SOURCES["stage12556_ready_rows"]),
        "authority_rows": M.read_jsonl(M.SOURCES["stage12555_exact_authority_bindings"]),
        "checkout_summary": M.read_json(M.SOURCES["stage12556_summary"]),
        "authority_summary": M.read_json(M.SOURCES["stage12555_summary"]),
        "runtime_bundle": M.read_json(M.SOURCES["stage11507_runtime_bundle"]),
        "frontier_decision": M.read_json(M.SOURCES["stage11509_frontier_decision"]),
        "source_hashes": dict(M.PINNED_SOURCE_SHA256),
    }


def test_current_sources_produce_exactly_eight_atomic_fail_closed_records():
    result = M.build(**inputs())
    assert result["pre_outcome_commitment_valid"] is True
    assert result["atomic_record_count"] == 8
    assert M.verify_envelope(result) == []
    assert all(result[key] is False for key in M.ZERO)


def test_candidate_task_swap_is_rejected():
    values = inputs()
    values["ready_rows"][0]["task_key"], values["ready_rows"][1]["task_key"] = (
        values["ready_rows"][1]["task_key"], values["ready_rows"][0]["task_key"]
    )
    result = M.build(**values)
    assert "candidate_task_key_join_mismatch" in result["blocking_reasons"]


def test_duplicate_ids_are_rejected_in_either_source():
    for source in ("ready_rows", "authority_rows"):
        values = inputs()
        values[source][1]["candidate_id"] = values[source][0]["candidate_id"]
        assert M.build(**values)["pre_outcome_commitment_valid"] is False


def test_task_key_identity_mismatch_is_rejected():
    values = inputs()
    candidate = values["ready_rows"][0]["candidate_id"]
    authority = next(row for row in values["authority_rows"] if row["candidate_id"] == candidate)
    authority["task_key"][3] = "wrong-instance"
    result = M.build(**values)
    assert "candidate_task_key_join_mismatch" in result["blocking_reasons"]
    assert "full_task_key_identity_mismatch" in result["blocking_reasons"]


def test_repo_or_commit_mutation_is_rejected_even_with_rehashed_identity():
    for field, value in (("canonical_repo", "mutated/repo"), ("base_commit", "0" * 40)):
        values = inputs()
        candidate = values["ready_rows"][0]["candidate_id"]
        authority = next(row for row in values["authority_rows"] if row["candidate_id"] == candidate)
        authority["task_identity"][field] = value
        authority["task_identity_sha256"] = M.stable_hash(authority["task_identity"])
        result = M.build(**values)
        assert result["pre_outcome_commitment_valid"] is False


def test_source_rewrite_with_rehashed_envelope_cannot_replace_pinned_anchor():
    result = M.build(**inputs())
    result["contract"]["authoritative_source_sha256"]["stage12556_ready_rows"] = "0" * 64
    result["commitment_sha256"] = M.stable_hash({
        "contract": result["contract"], "atomic_records": result["atomic_records"]
    })
    assert "authoritative_source_anchor_mismatch" in M.verify_envelope(result)


def test_nested_forbidden_candidate_source_fields_are_rejected():
    for source, field in (("ready_rows", "verifier_exit"), ("authority_rows", "reward"), ("ready_rows", "test_output")):
        values = inputs()
        candidate = values["ready_rows"][0]["candidate_id"]
        row = next(item for item in values[source] if item["candidate_id"] == candidate)
        row.setdefault("harmless_wrapper", {})["nested"] = {field: "must-not-be-read"}
        result = M.build(**values)
        assert "forbidden_candidate_source_field_present" in result["blocking_reasons"]
        assert result["pre_outcome_commitment_valid"] is False


def test_non_allowlisted_metadata_does_not_change_atomic_commitment():
    baseline = M.build(**inputs())
    values = inputs()
    values["ready_rows"][0]["harmless_metadata"] = {"note": "ignored", "version": 2}
    values["authority_rows"][0]["harmless_metadata"] = ["also", "ignored"]
    assert M.build(**values) == baseline


def test_rehashed_selected_model_tampering_is_rejected():
    original = M.build(**inputs())
    for location, field, value in (
        ("contract", "runtime_stage", 11508),
        ("contract", "scorer", "other_scorer"),
        ("atomic", "weights_sha256", "0" * 64),
    ):
        changed = copy.deepcopy(original)
        if location == "contract":
            changed["contract"]["selected_model"][field] = value
        else:
            record = changed["atomic_records"][0]
            record["selected_model"][field] = value
            body = {key: item for key, item in record.items() if key != "atomic_record_sha256"}
            record["atomic_record_sha256"] = M.stable_hash(body)
        changed["commitment_sha256"] = M.stable_hash({
            "contract": changed["contract"], "atomic_records": changed["atomic_records"]
        })
        blockers = M.verify_envelope(changed)
        expected = "contract_selected_model_mismatch" if location == "contract" else "atomic_selected_model_mismatch"
        assert expected in blockers


def test_rehashed_authorization_policy_tampering_is_rejected():
    changed = M.build(**inputs())
    changed["contract"]["authorization_policy"] = "authorize"
    changed["commitment_sha256"] = M.stable_hash({
        "contract": changed["contract"], "atomic_records": changed["atomic_records"]
    })
    assert "authorization_policy_changed" in M.verify_envelope(changed)


def test_record_removal_or_addition_is_rejected_even_after_rehashing():
    original = M.build(**inputs())
    for records in (original["atomic_records"][:-1], original["atomic_records"] + [copy.deepcopy(original["atomic_records"][0])]):
        changed = copy.deepcopy(original)
        changed["atomic_records"] = records
        changed["commitment_sha256"] = M.stable_hash({"contract": changed["contract"], "atomic_records": records})
        assert "atomic_record_count_not_exactly_eight" in M.verify_envelope(changed)


def test_output_is_deterministic_under_source_row_reordering():
    left_values = inputs()
    right_values = inputs()
    right_values["ready_rows"].reverse()
    right_values["authority_rows"].reverse()
    left = M.build(**left_values)
    right = M.build(**right_values)
    assert left == right
    assert left["commitment_sha256"] == right["commitment_sha256"]

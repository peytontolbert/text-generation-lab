from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12572_source_native_protected_root_preimage_reconstruction_census.py"
SPEC = importlib.util.spec_from_file_location("stage12572_v4", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


@pytest.fixture(scope="module")
def inputs():
    return (
        M.read_json(M.SOURCES["commitment_projection"]),
        M.read_json(M.SOURCES["source_projection"]),
        M.read_json(M.SOURCES["observer_matrix"]),
    )


def build(values, source_pins=None, evidence_pins=None, runner=M._run_git):
    return M.build_census(
        *values,
        source_file_sha256=(
            M.PINNED_SOURCE_FILE_SHA256 if source_pins is None else source_pins
        ),
        evidence_file_sha256=(
            M.PINNED_EVIDENCE_FILE_SHA256 if evidence_pins is None else evidence_pins
        ),
        runner=runner,
    )


def test_commitment_only_projection_and_no_rich_stage12105_runtime_input(inputs):
    commitment, source, observer = inputs
    assert set(commitment) == {
        "record_type", "protected_root_count", "protected_root_hashes",
        "protected_root_hash_set_sha256",
    }
    assert len(commitment["protected_root_hashes"]) == 25
    encoded = json.dumps([commitment, source, observer], sort_keys=True)
    assert "stage12105_root_key" not in encoded
    runtime = SCRIPT.read_text()
    assert "sealed_transition_candidate_rows.jsonl" not in runtime
    assert "stage12570" not in runtime and "stage12571" not in runtime
    generator_path = ROOT / "scripts/build_stage12572_guarded_projections.py"
    generator_text = generator_path.read_text()
    assert M.file_sha256(generator_path) == M.PINNED_GENERATOR["file_sha256"]
    assert "OLD_OBSERVER" not in generator_text
    assert "read_json(OLD_OBSERVER" not in generator_text


def test_exact_counts_root_digests_and_authority_boundary():
    result = M.build()
    assert (
        result["committed_root_identity_verified_count"],
        result["immutable_source_bridge_count"],
        result["historical_binding_missing_count"],
        result["independently_authorized_count"],
        result["invalid_observer_record_count"],
    ) == (25, 17, 8, 0, 0)
    assert result["canonical_protected_root_hash_set_sha256"] == (
        "e85fc0827bfcd9e5819fbc862f060afe35617d00b2c67b77a7effbc811541deb"
    )
    assert result["immutable_source_bridge_root_set_sha256"] == (
        "d7866db7e54ccb58a4146275c25e31dd68100496823747e8d0870f64d99b5b65"
    )
    assert all(result[name] is False for name in M.AUTHORITY_FIELDS)
    assert result["runtime_plaintext_preimages_read"] is False
    assert "preimage_reproduced_count" not in result
    assert "plaintext_preimages_read_or_emitted" not in result
    assert result["decision"] == "verified"
    assert result["blocking_reasons"] == []
    assert result["non_authorizing_conditions"] == [
        "independent_source_authority_absent"
    ]


def test_observer_has_no_authority_and_source_pins_are_exact(inputs):
    _, source, observer = inputs
    assert source["pinned_original_source_sha256"] == M.PINNED_ORIGINAL_SOURCE_SHA256
    encoded = json.dumps(observer, sort_keys=True)
    assert "authorized" not in encoded and "authority" not in encoded
    assert len(source["rows"]) == len(observer["rows"]) == 17
    assert source["generator"] == M.PINNED_GENERATOR
    assert all(set(row) == M.OBSERVER_ROW_FIELDS for row in observer["rows"])
    for row in observer["rows"]:
        source_row = next(
            item for item in source["rows"]
            if item["bridge_id"] == row["bridge_id"]
        )
        assert M.verify_git_observation(row, source_row) == []


@pytest.mark.parametrize("source_pins,evidence_pins", [
    (None, M.PINNED_EVIDENCE_FILE_SHA256),
    ({}, M.PINNED_EVIDENCE_FILE_SHA256),
    ({**M.PINNED_SOURCE_FILE_SHA256, "extra": "0" * 64}, M.PINNED_EVIDENCE_FILE_SHA256),
    (M.PINNED_SOURCE_FILE_SHA256, None),
    (M.PINNED_SOURCE_FILE_SHA256, {}),
    (M.PINNED_SOURCE_FILE_SHA256, {**M.PINNED_EVIDENCE_FILE_SHA256, "extra": "0" * 64}),
])
def test_missing_extra_or_null_pins_fail_closed(inputs, source_pins, evidence_pins):
    result = M.build_census(
        *inputs, source_file_sha256=source_pins, evidence_file_sha256=evidence_pins
    )
    assert result["immutable_source_bridge_count"] == 0


@pytest.mark.parametrize("collection,operation", [
    ("commitment", "duplicate"), ("commitment", "missing"), ("commitment", "extra"),
    ("source", "duplicate"), ("source", "missing"), ("observer", "duplicate"),
    ("observer", "missing"),
])
def test_missing_extra_duplicate_roots_fail_closed(inputs, collection, operation):
    values = [copy.deepcopy(value) for value in inputs]
    index = {"commitment": 0, "source": 1, "observer": 2}[collection]
    key = "protected_root_hashes" if collection == "commitment" else "rows"
    rows = values[index][key]
    if operation == "duplicate":
        rows.append(copy.deepcopy(rows[0]))
    elif operation == "missing":
        rows.pop()
    else:
        rows.append("f" * 64)
    result = build(values)
    assert result["immutable_source_bridge_count"] == 0


def same_commit_pair(source, observer):
    for first in source["rows"]:
        for second in source["rows"]:
            if (
                first is not second and first["commit_oid"] == second["commit_oid"]
                and first["protected_root_hash"] != second["protected_root_hash"]
            ):
                observer_first = next(
                    row for row in source["rows"]
                    if row["bridge_id"] == first["bridge_id"]
                )
                observer_first = next(
                    row for row in observer["rows"]
                    if row["bridge_id"] == first["bridge_id"]
                )
                return observer_first, first, second
    raise AssertionError("same-commit pair unavailable")


def test_same_commit_file_set_swap_rejected(inputs):
    _, source, observer = inputs
    observer_first, source_first, source_second = same_commit_pair(source, observer)
    mutated = copy.deepcopy(source_first)
    mutated["files"] = copy.deepcopy(source_second["files"])
    reasons = M.verify_git_observation(observer_first, mutated)
    assert "source_bridge_id_mismatch" in reasons


def test_cross_repo_swap_rejected(inputs):
    _, source, observer = inputs
    first = observer["rows"][0]
    second = next(
        row for row in observer["rows"]
        if row["repo_path"] != first["repo_path"]
    )
    source_first = next(
        row for row in source["rows"]
        if row["bridge_id"] == first["bridge_id"]
    )
    mutated = copy.deepcopy(first)
    mutated["repo_path"] = second["repo_path"]
    reasons = M.verify_git_observation(mutated, source_first)
    assert {"source_repo_not_within_observer_repo", "remote_origin_consistency_mismatch"} & set(reasons)


def test_commit_tree_path_blob_and_byte_swaps_rejected(inputs):
    _, source, observer = inputs
    row = observer["rows"][0]
    source_row = next(
        item for item in source["rows"]
        if item["bridge_id"] == row["bridge_id"]
    )
    mutated_source = copy.deepcopy(source_row)
    mutated_source["commit_oid"] = "0" * 40
    assert "source_bridge_id_mismatch" in M.verify_git_observation(row, mutated_source)
    mutated_observer = copy.deepcopy(row)
    mutated_observer["tree_oid"] = "0" * 40
    assert "commit_tree_binding_mismatch" in M.verify_git_observation(
        mutated_observer, source_row
    )
    for field, value in (("blob_oid", "0" * 40), ("content_sha256", "0" * 64)):
        mutated_source = copy.deepcopy(source_row)
        mutated_source["files"][0][field] = value
        assert "source_bridge_id_mismatch" in M.verify_git_observation(
            row, mutated_source
        )


def test_partial_clone_and_alternates_fail_closed(inputs, monkeypatch):
    _, source, observer = inputs
    row = observer["rows"][0]
    source_row = next(
        item for item in source["rows"]
        if item["bridge_id"] == row["bridge_id"]
    )
    def partial(repo, args):
        if args == ["config", "--local", "--get", "extensions.partialClone"]:
            return 0, b"origin\n", b""
        return M._run_git(repo, args)
    assert "partial_clone_forbidden" in M.verify_git_observation(
        row, source_row, runner=partial
    )
    original_is_file = Path.is_file
    original_read_bytes = Path.read_bytes
    monkeypatch.setattr(Path, "is_file", lambda path: (
        True if str(path).endswith("objects/info/alternates")
        else original_is_file(path)
    ))
    monkeypatch.setattr(Path, "read_bytes", lambda path: (
        b"/alternate/objects\n"
        if str(path).endswith("objects/info/alternates")
        else original_read_bytes(path)
    ))
    assert "object_alternates_forbidden" in M.verify_git_observation(row, source_row)


def test_ls_tree_is_nul_delimited_and_lazy_fetch_disabled(inputs, monkeypatch):
    _, source, observer = inputs
    row = observer["rows"][0]
    source_row = next(
        item for item in source["rows"]
        if item["bridge_id"] == row["bridge_id"]
    )
    calls = []
    def recording(repo, args):
        calls.append(list(args))
        return M._run_git(repo, args)
    assert M.verify_git_observation(row, source_row, runner=recording) == []
    assert any(call[:2] == ["ls-tree", "-z"] for call in calls)
    captured = {}
    class Result:
        returncode, stdout, stderr = 1, b"", b""
    def fake_run(*args, **kwargs):
        captured.update(kwargs["env"])
        return Result()
    monkeypatch.setattr(M.subprocess, "run", fake_run)
    M._run_git(Path("/tmp"), ["status"])
    assert captured["GIT_NO_LAZY_FETCH"] == "1"
    assert captured["GIT_ALTERNATE_OBJECT_DIRECTORIES"] == ""


def test_nested_leakage_and_unexpected_schema_fail_closed(inputs):
    values = [copy.deepcopy(value) for value in inputs]
    values[1]["rows"][0]["nested"] = {"gold": "PASS"}
    result = build(values)
    assert result["immutable_source_bridge_count"] == 0
    values = [copy.deepcopy(value) for value in inputs]
    values[2]["rows"][0]["record_schema"] = "unexpected"
    result = build(values)
    assert result["immutable_source_bridge_count"] == 0


def test_in_memory_digest_and_observer_authority_injection_fail_closed(inputs):
    values = [copy.deepcopy(value) for value in inputs]
    values[1]["rows"][0]["constructor_arguments_sha256"] = "0" * 64
    result = build(values)
    assert result["decision"] == "blocked"
    assert "source_projection_content_digest_mismatch" in result["blocking_reasons"]
    assert result["immutable_source_bridge_count"] == 0

    values = [copy.deepcopy(value) for value in inputs]
    values[2]["rows"][0]["independently_authorized"] = True
    result = build(values)
    assert result["decision"] == "blocked"
    assert "forbidden_projection_leakage" in result["blocking_reasons"]
    assert result["independently_authorized_count"] == 0

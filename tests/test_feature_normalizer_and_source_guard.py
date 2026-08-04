from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from feature_normalizer import normalize_features
from source_lineage_guard import (
    assert_future_eval_identity_allowed,
    canonicalize_manifest_split,
    canonicalize_row_split,
    evaluate_row_source_lineage,
    extract_future_eval_identities,
    load_future_eval_identity_denylist,
    locked_source_ids,
    source_ids_from_row,
    train_eligible_source_ids,
)


def test_feature_normalizer_extracts_nested_and_array_aliases() -> None:
    row = {
        "row_id": "r",
        "graph_input": {
            "query_kind": "callsite",
            "nodes": [
                {"node_type": "file", "features": {"call_count_bucket": "low"}},
                {"node_type": "function", "features": {"call_count_bucket": "high"}},
            ],
        },
    }
    aliases = {
        "query_kind": ["graph_input.query_kind"],
        "call_count_bucket": ["graph_input.nodes[].features.call_count_bucket"],
    }
    normalized = normalize_features(row, aliases)
    assert normalized["query_kind"] == "callsite"
    assert normalized["call_count_bucket"] == ["low", "high"]


def test_source_guard_blocks_locked_source() -> None:
    registry = {
        "src_locked": {"source_id": "src_locked", "locked_eval": True, "train_eligible": False},
    }
    row = {"row_id": "r", "source_lineage": {"graph_nodes_source_id": "src_locked"}}
    result = evaluate_row_source_lineage(row, registry)
    assert result["train_eligible_lineage"] is False
    assert result["blocked_training_reason"] == "locked_eval_source"
    assert locked_source_ids(registry) == {"src_locked"}


def test_source_guard_blocks_unknown_source() -> None:
    result = evaluate_row_source_lineage({"source_lineage": {"source_id": "missing"}}, {})
    assert result["train_eligible_lineage"] is False
    assert result["blocked_training_reason"] == "unknown_source_id"


def test_source_guard_accepts_train_eligible_source() -> None:
    registry = {
        "src_ok": {"source_id": "src_ok", "locked_eval": False, "hidden_final": False, "train_eligible": True},
    }
    row = {"source_lineage": {"graph_nodes_source_id": "src_ok", "graph_spans_source_id": "src_ok"}}
    result = evaluate_row_source_lineage(row, registry)
    assert result["train_eligible_lineage"] is True
    assert train_eligible_source_ids(registry) == {"src_ok"}


def test_source_guard_recurses_through_mixed_parent_containers() -> None:
    row = {"parents": [{"projection": {"source_ids": ["src_a", "src_b"]}}, ({"nested_source_id": "src_c"},)]}
    assert source_ids_from_row(row) == {"src_a", "src_b", "src_c"}



def test_source_guard_recurses_beneath_recognized_container_key() -> None:
    row = {"source_ids": [{"parent": {"source_id": "src_locked"}}]}
    assert source_ids_from_row(row) == {"src_locked"}


def test_source_guard_does_not_treat_hashes_as_source_ids() -> None:
    row = {"source_lineage": {"lineage_hash": "src_locked", "artifact_hash": "src_locked"}}
    assert source_ids_from_row(row) == set()


def test_source_guard_is_cycle_safe() -> None:
    row: dict = {"source_id": "src_a"}
    row["self"] = row
    assert source_ids_from_row(row) == {"src_a"}

@pytest.mark.parametrize(
    "alias",
    ["canonical_repo", "repository_family", "repo_families", "nested_repo_family"],
)
def test_future_eval_repo_aliases_cannot_bypass_denylist(alias: str) -> None:
    value: object = ["safe-repo", " Unsloth.git "] if alias == "repo_families" else " Unsloth.git "
    row = {"parents": [{"projection": {alias: value}}]}
    with pytest.raises(ValueError, match="denied future-eval identity"):
        assert_future_eval_identity_allowed(
            row,
            "eval",
            load_future_eval_identity_denylist(),
        )


@pytest.mark.parametrize(
    "alias",
    ["canonical_source_path", "upstream_source_path", "source_paths"],
)
def test_future_eval_source_path_aliases_normalize_and_deny(alias: str) -> None:
    denied_path = r"\ARXIV\\repositories\.\other\..\unsloth\\"
    value: object = ["/safe/repository", denied_path] if alias == "source_paths" else denied_path
    row = {"lineage": ({"nested": {alias: value}},)}
    with pytest.raises(ValueError, match="denied future-eval identity"):
        assert_future_eval_identity_allowed(
            row,
            "strict_eval",
            load_future_eval_identity_denylist(),
        )


@pytest.mark.parametrize(
    "alias",
    ["root_id", "root_lineage_key", "stage12105_root_key", "parent_root_ids"],
)
def test_future_eval_root_aliases_cannot_bypass_denylist(alias: str) -> None:
    denied_root = "420799b61ef35d6cfd87c4f4b02c98152fdf6599"
    value: object = ["safe-root", denied_root] if alias == "parent_root_ids" else denied_root
    row = {"nested": [{"identity": {alias: value}}]}
    with pytest.raises(ValueError, match="denied future-eval identity"):
        assert_future_eval_identity_allowed(
            row,
            "eval",
            load_future_eval_identity_denylist(),
        )


def test_future_eval_identity_namespaces_have_distinct_normalization() -> None:
    extraction = extract_future_eval_identities(
        {
            "canonical_repo": r" Example\\Repo.git ",
            "canonical_source_path": r"\DATA\\repos\.\parent\..\Repo\\",
            "root_identity": " Opaque-Root-ID ",
        }
    )
    assert extraction.identities == {
        "repo_family": frozenset({"example/repo"}),
        "source_path": frozenset({"/data/repos/repo"}),
        "root_identity": frozenset({"opaque-root-id"}),
    }


def test_future_eval_root_identity_is_case_normalized() -> None:
    denylist = load_future_eval_identity_denylist()
    with pytest.raises(ValueError, match="denied future-eval identity"):
        assert_future_eval_identity_allowed(
            {"ROOT_ID": "STAGE12583_CAUSAL_EPISODE_MICROFACTORY"},
            "eval",
            denylist,
        )


@pytest.mark.parametrize(
    "row",
    [
        {"repository_family": 7, "root_identity": "safe"},
        {"repo_families": ["safe", None], "root_identity": "safe"},
        {"source_paths": [], "root_identity": "safe"},
        {"root_lineage_keys": ["safe", {}], "repo_family": "safe"},
    ],
)
def test_future_eval_malformed_alias_values_fail_heldout(row: dict[str, object]) -> None:
    extraction = extract_future_eval_identities(row)
    assert extraction.malformed_paths
    with pytest.raises(ValueError, match="malformed recognized identities"):
        assert_future_eval_identity_allowed(
            row,
            "eval",
            load_future_eval_identity_denylist(),
        )


def test_future_eval_generic_nonidentity_path_and_hash_fields_are_ignored() -> None:
    extraction = extract_future_eval_identities(
        {
            "path": "/arxiv/repositories/unsloth",
            "artifact_path": "/arxiv/repositories/unsloth",
            "identity_hash": "stage12583_causal_episode_microfactory",
        }
    )
    assert extraction.has_identity is False
    assert extraction.malformed_paths == ()


@pytest.mark.parametrize("alias", ["commit", "commit_sha", "commit_hash", "revision"])
def test_future_eval_common_commit_aliases_are_root_identities(alias: str) -> None:
    row = {alias.swapcase(): "420799B61EF35D6CFD87C4F4B02C98152FDF6599"}
    extraction = extract_future_eval_identities(row)
    assert extraction.identities["root_identity"] == frozenset(
        {"420799b61ef35d6cfd87c4f4b02c98152fdf6599"}
    )
    with pytest.raises(ValueError, match="denied future-eval identity"):
        assert_future_eval_identity_allowed(row, "eval", load_future_eval_identity_denylist())


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ({"source_heldout": True}, "strict_eval"),
        ({"strict_eval_eligible": True}, "strict_eval"),
        ({"strict-eval-eligibility": True}, "strict_eval"),
        ({"authority": {"evaluation_allowed": True}}, "eval"),
        ({"split": "eval", "nested": {"source_heldout": True}}, "strict_eval"),
        ({"legacy_payload": "train"}, "train"),
    ],
)
def test_row_split_enforces_boolean_heldout_markers(row: dict[str, object], expected: str) -> None:
    assert canonicalize_row_split(row) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("train", "train"),
        ("training", "train"),
        ("train-support", "train"),
        ("train_only", "train"),
        ("heldout", "strict_eval"),
        ("hidden_final", "strict_eval"),
        ("sealed", "strict_eval"),
        ("locked-eval", "strict_eval"),
    ],
)
def test_split_role_aliases_are_canonicalized(value: str, expected: str) -> None:
    assert canonicalize_row_split({"split_role": value}) == expected


@pytest.mark.parametrize(
    "row",
    [
        {"split": "train", "split_role": "heldout"},
        {"package_split": "sealed", "split_role": "train"},
        {"split": "eval", "package_split": "eval", "split_role": "hidden_final"},
    ],
)
def test_split_role_conflicts_fail_closed(row: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="conflicting explicit manifest splits"):
        canonicalize_row_split(row)


@pytest.mark.parametrize(
    "row",
    [
        {"split": "train", "source_heldout": True},
        {"package_split": "train", "authority": {"eval_authority": True}},
        {"source_heldout": "false"},
        {"strict_eval_eligible": None},
        {"evaluation_allowed": False},
        {"source_heldout": True, "nested": {"locked_eval": False}},
    ],
)
def test_row_split_rejects_conflicting_or_ambiguous_heldout_markers(row: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        canonicalize_row_split(row)


@pytest.mark.parametrize(
    "row",
    [
        {"RePoSiToRy": "UNSLOTH"},
        {"SOURCE_REPOSITORY": r"\ARXIV\repositories\UnSlOtH"},
        {"source": "/ARXIV/repositories/UNSLOTH"},
        {"Repository_Path": "/ARXIV/repositories/UNSLOTH/"},
        {"Before_Commit": "420799B61EF35D6CFD87C4F4B02C98152FDF6599"},
        {"source": {"AFTER": "76A2B9EDF160D68208DC30C02C6523BC6551F950"}},
    ],
)
def test_future_eval_case_normalized_repository_and_commit_aliases_are_denied(row: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="denied future-eval identity"):
        assert_future_eval_identity_allowed(row, "strict_eval", load_future_eval_identity_denylist())

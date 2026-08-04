from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12576_legacy_metrics_and_sealed_replacement_readiness_atlas.py"
SPEC = importlib.util.spec_from_file_location("stage12576", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


@pytest.fixture(scope="module")
def inputs():
    return (
        M.read_json(M.SOURCE12574), M.read_json(M.SOURCE12575),
        [M.read_json(path) for path, _ in M.SPINE_SOURCES.values()],
        {name: digest for name, (_, digest) in M.SPINE_SOURCES.items()},
    )


def build(inputs, *, spine=None):
    source74, source75, base_spine, pins = inputs
    return M.build_atlas(
        source74, source75, spine if spine is not None else base_spine,
        source12574_file_sha256=M.PINNED_STAGE12574_FILE_SHA256,
        source12575_file_sha256=M.PINNED_STAGE12575_FILE_SHA256,
        spine_file_sha256=pins,
    )


def digest(seed: str) -> str:
    return M.stable_hash(seed)


def legacy_record(reference: str) -> dict:
    body = {
        "record_type": M.LEGACY_RECORD_TYPE,
        "canonical_root_count": 25,
        "canonical_root_set_sha256": M.CANONICAL_ROOT_SET_SHA256,
        "metrics_artifact_reference": reference,
        "metrics_file_sha256": digest("metrics-file"),
        "metric_payload_sha256": digest("metrics-payload"),
        "source_revision_sha256": digest("metrics-revision"),
    }
    return {**body, "metrics_record_sha256": M.stable_hash(body)}


def candidate(language="rust", task="transition_candidate_selection") -> dict:
    body = {
        "record_type": M.REPLACEMENT_RECORD_TYPE,
        "candidate_identity_sha256": digest("candidate"),
        "source_native_lineage_record_sha256": digest("lineage"),
        "canonical_repo_sha256": digest("repo"),
        "repo_family_sha256": digest("family"),
        "immutable_revision_sha256": digest("revision"),
        "tree_sha256": digest("tree"),
        "blob_sha256": digest("blob"),
        "split_name": "prospective_replacement_eval",
        "split_disjoint_from_legacy_25_roots": True,
        "root_disjoint_from_legacy_25_roots": True,
        "repo_family_disjoint_from_legacy_25_roots": True,
        "language_stratum": language,
        "task_stratum": task,
        "split_disjointness_evidence_sha256": digest("split"),
        "root_disjointness_evidence_sha256": digest("root-disjoint"),
        "repo_family_disjointness_evidence_sha256": digest("family-disjoint"),
        "stratum_binding_evidence_sha256": digest("stratum"),
        "pre_execution_seal_sha256": digest("seal"),
        "pre_execution_seal_ready": True,
        "selection_basis": "source_native_lineage_and_stratum_only",
        "outcome_fields_read": False,
    }
    return {**body, "candidate_record_sha256": M.stable_hash(body)}


def assert_deny(result):
    assert all(result[field] is False for field in M.DENY_FIELDS)
    assert result["replacement_manifest_sealed"] is False
    assert result["prospective_replacement_candidate_count"] == 0


def test_current_workspace_is_blocked_and_scans_12564_12568():
    result = M.build()
    assert result["decision"] == "blocked_readiness_atlas"
    assert result["legacy_metrics_status"] == "missing_no_values_invented"
    evaluations = {row["source_stage"]: row for row in result["explicit_candidate_source_evaluations"]}
    assert evaluations["stage12564_authoritative_protected_lineage_preflight"]["eligible_candidate_count"] == 0
    assert "protected_legacy_lineage_unresolved" in evaluations["stage12564_authoritative_protected_lineage_preflight"]["reason_codes"]
    assert evaluations["stage12568_open_swe_source_lineage_adapter"]["candidate_record_count"] == 8
    assert result["required_language_strata"] == ["rust", "web_js_ts_html"]
    assert_deny(result)


@pytest.mark.parametrize("reference", [
    "immutable://historical/canonical-25/metrics.json",
    "https://example.invalid/metrics.json",
    "runs/local/artifacts/not-allowlisted.json",
])
def test_placeholder_or_unallowlisted_metric_reference_rejects(inputs, reference):
    result = build(inputs, spine=copy.deepcopy(inputs[2]) + [{"legacy": legacy_record(reference)}])
    assert "legacy_metrics_reference_not_allowlisted_openable_local_artifact" in result["fatal_validation_blockers"]
    assert result["legacy_metrics_reference"] is None
    assert_deny(result)


def test_fabricated_positive_candidate_record_rejects(inputs):
    result = build(inputs, spine=copy.deepcopy(inputs[2]) + [{"candidate": candidate()}])
    for reason in (
        "replacement_candidate_unopened_caller_record_rejected",
        "replacement_candidate_source_native_git_verifier_not_invoked",
        "replacement_candidate_full_universe_overlap_not_verified",
        "replacement_candidate_pre_outcome_source_artifact_missing",
    ):
        assert reason in result["fatal_validation_blockers"]
    assert_deny(result)


def test_false_or_free_string_strata_reject(inputs):
    result = build(inputs, spine=copy.deepcopy(inputs[2]) + [{"candidate": candidate("anything", "free-form") }])
    assert "replacement_candidate_required_strata_not_pinned" in result["fatal_validation_blockers"]
    assert_deny(result)


def test_outcome_field_rejects_without_echo(inputs):
    row = candidate()
    row["score"] = "secret-score"
    result = build(inputs, spine=copy.deepcopy(inputs[2]) + [{"candidate": row}])
    assert "replacement_candidate_outcome_conditioned_selection_detected" in result["fatal_validation_blockers"]
    assert "secret-score" not in str(result)
    assert_deny(result)

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12577_concrete_legacy_metrics_and_replacement_candidate_materialization.py"
SPEC = importlib.util.spec_from_file_location("stage12577", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


@pytest.fixture(scope="module")
def inputs():
    records = {name: M.read_json(M.SOURCES[name]) for name in (
        "stage12564", "stage12568", "stage12574", "stage12575", "stage12576",
        "gemma_summary", "route_summary", "historical_package",
    )}
    rows = {name: M.read_jsonl(M.SOURCES[name]) for name in (
        "stage12568_rows", "manifest", "gemma_rows", "protected_rows",
        "rust_inventory", "reserved12107", "reserved12118",
    )}
    return records, rows, dict(M.PINS)


def fabricated_observer(_repo: Path, source_path: str):
    return {
        "canonical_repo": "https://example.invalid/fabricated.git",
        "commit_oid": "1" * 40, "tree_oid": "2" * 40,
        "source_path": source_path, "blob_oid": "3" * 40, "blob_sha256": "4" * 64,
    }


def assert_deny(result):
    assert all(result[field] is False for field in M.DENY_FIELDS)
    assert result["sealed_candidate_count"] == 0
    assert result["replacement_candidate_count"] == 0
    assert result["replacement_candidates"] == []
    assert result["replacement_admission_performed"] is False
    assert result["evaluation_performed"] is False
    assert result["training_performed"] is False
    assert result["clearance_granted"] is False


def test_current_workspace_retains_noncanonical_metrics_and_diagnostic_candidates():
    result = M.build()
    assert result["stage12574_12576_compatible"] is True
    assert result["legacy_metrics_materialized"] is False
    assert result["diagnostic_candidate_count"] == 2
    assert "observed_40_root_values_are_noncanonical_summary_only" in result["blocking_reasons"]
    assert "routed_metric_row_level_semantic_binding_unavailable" in result["blocking_reasons"]
    assert any(reason.startswith("predecessor_unresolved:") for reason in result["blocking_reasons"])
    assert_deny(result)


def test_observed_values_are_exact_but_not_readiness_or_preservation_claims():
    finding = M.build()["historical_metric_artifact_findings"][0]
    assert finding["canonical_25_root_binding"] is False
    assert finding["observed_manifest_root_count"] == 40
    assert finding["selected_transition"] == {"correct": 364, "rows": 640, "accuracy": 0.56875}
    assert finding["routed_transition"] == {"correct": 375, "rows": 640, "accuracy": 0.5859375}
    assert finding["gemma3_12b_same_manifest"] == {"correct": 386, "rows": 640, "accuracy": 0.603125}
    assert finding["row_level_correctness_recomputed"] == {"selected_transition": 364, "gemma3_12b": 386}
    assert finding["metrics_recomputed"] is False
    assert finding["semantic_binding_complete"] is False
    assert finding["readiness_claim_allowed"] is False
    assert finding["preservation_claim_allowed"] is False


def test_arbitrary_25_root_manifest_is_not_canonical(inputs):
    records, rows, _ = inputs
    mutated = copy.deepcopy(rows["manifest"])
    for index, row in enumerate(mutated):
        row["root_id"] = f"arbitrary-root-{index % 25:02d}"
    blockers = []
    metric, finding = M.materialize_legacy_metrics(
        mutated, rows["gemma_rows"], records["gemma_summary"], records["route_summary"], blockers,
    )
    assert metric is None
    assert finding["observed_manifest_root_count"] == 25
    assert finding["canonical_25_root_binding"] is False
    assert finding["manifest_root_identity_set_sha256"] != M.CANONICAL_ROOT_SET_SHA256
    assert "canonical_25_root_identity_set_mismatch" in blockers


def test_false_canary_source_value_is_preserved_and_blocked(inputs):
    records, rows, _ = inputs
    route_summary = copy.deepcopy(records["route_summary"])
    field = "protected_filtered_strict_preserved_for_candidate_runtime"
    route_summary["gates"][field] = False
    blockers = []
    metric, finding = M.materialize_legacy_metrics(
        rows["manifest"], rows["gemma_rows"], records["gemma_summary"], route_summary, blockers,
    )
    assert metric is None
    assert finding["observed_canary_gate_summary_values"][field] is False
    assert f"historical_canary_gate_false:{field}" in blockers
    assert "historical_canary_gate_metrics_mismatch" in blockers


@pytest.mark.parametrize("malformed_gates", [None, ["not", "an", "object"]])
def test_malformed_canary_gates_emit_nulls_and_block(inputs, malformed_gates):
    records, rows, _ = inputs
    route_summary = copy.deepcopy(records["route_summary"])
    route_summary["gates"] = malformed_gates
    blockers = []
    metric, finding = M.materialize_legacy_metrics(
        rows["manifest"], rows["gemma_rows"], records["gemma_summary"], route_summary, blockers,
    )
    assert metric is None
    assert set(finding["observed_canary_gate_summary_values"].values()) == {None}
    assert "historical_canary_gates_malformed_non_object" in blockers
    assert "historical_canary_gate_metrics_mismatch" in blockers


def test_missing_canary_gates_emit_nulls_and_block(inputs):
    records, rows, _ = inputs
    route_summary = copy.deepcopy(records["route_summary"])
    del route_summary["gates"]
    blockers = []
    _, finding = M.materialize_legacy_metrics(
        rows["manifest"], rows["gemma_rows"], records["gemma_summary"], route_summary, blockers,
    )
    assert set(finding["observed_canary_gate_summary_values"].values()) == {None}
    assert "historical_canary_gates_missing" in blockers


def test_fabricated_source_metric_is_observed_verbatim_and_blocked(inputs):
    records, rows, _ = inputs
    gemma_summary = copy.deepcopy(records["gemma_summary"])
    gemma_summary["hundred_m"]["overall"]["correct"] = 999
    blockers = []
    metric, finding = M.materialize_legacy_metrics(
        rows["manifest"], rows["gemma_rows"], gemma_summary, records["route_summary"], blockers,
    )
    assert metric is None
    assert finding["selected_transition"]["correct"] == 999
    assert finding["expected_reference_metric_values"]["selected_transition"]["correct"] == 364
    assert "selected_transition_metrics_mismatch" in blockers


def test_findings_schema_alias_is_equal():
    result = M.build()
    assert result["legacy_metric_findings"] == result["historical_metric_artifact_findings"]
    assert result["legacy_metric_findings"] is result["historical_metric_artifact_findings"]


def test_row_correctness_mutation_blocks_semantic_binding(inputs):
    records, rows, _ = inputs
    mutated = copy.deepcopy(rows["gemma_rows"])
    mutated[0]["hundred_m_correct"] = not mutated[0]["hundred_m_correct"]
    blockers = []
    metric, finding = M.materialize_legacy_metrics(
        rows["manifest"], mutated, records["gemma_summary"], records["route_summary"], blockers,
    )
    assert metric is None
    assert "row_level_correctness_recomputation_mismatch" in blockers
    assert finding["semantic_binding_complete"] is False


def test_fabricated_observer_is_called_but_cannot_promote(inputs):
    _, rows, _ = inputs
    calls = []

    def observer(repo: Path, source_path: str):
        calls.append((repo, source_path))
        return fabricated_observer(repo, source_path)

    candidates, diagnostics = M.materialize_candidates(
        rows["rust_inventory"], set(), set(), observer, [],
    )
    assert len(calls) == len(M.CANDIDATE_REPOS) == 4
    assert candidates == []
    assert diagnostics
    assert all(row["diagnostic_only"] is True for row in diagnostics)
    assert all("injected_observer_claims_diagnostic_only_not_promotion_authority" in row["reason_codes"] for row in diagnostics)
    assert all("pre_execution_seal_source_artifact_missing" in row["reason_codes"] for row in diagnostics)
    assert all("example.invalid" not in str(row) for row in diagnostics)

def test_overlap_and_reserved_universes_reject(inputs):
    records, rows, _ = inputs
    families, roots = M._exclusion_sets(
        rows["protected_rows"], rows["manifest"], rows["reserved12107"],
        rows["reserved12118"], records["historical_package"],
    )
    assert M.normalize_family("candle") in families
    assert M.normalize_family("tokenizers") in families
    candidates, diagnostics = M.materialize_candidates(rows["rust_inventory"], families, roots, fabricated_observer, [])
    assert candidates == []
    overlap_rows = [row for row in diagnostics if "repo_family_in_protected_train_or_reserved_set" in row["reason_codes"]]
    assert len(overlap_rows) == 2


def test_false_strata_cannot_create_sealed_candidate(inputs):
    _, rows, _ = inputs
    inventory = copy.deepcopy(rows["rust_inventory"])
    inventory[0]["language_stratum"] = "made-up"
    inventory[0]["pre_execution_seal_ready"] = True
    candidates, diagnostics = M.materialize_candidates(inventory, set(), set(), fabricated_observer, [])
    assert candidates == []
    assert diagnostics
    assert all("pre_outcome_stratum_binding_source_artifact_missing" in row["reason_codes"] for row in diagnostics)


def test_source_pin_mismatch_and_deny_boundary_fail_closed(inputs):
    records, rows, pins = inputs
    pins["stage12576"] = M.stable_hash("mutation")
    result = M.build_materialization(records, rows, file_digests=pins, observer=fabricated_observer)
    assert "source_file_pin_mismatch:stage12576" in result["blocking_reasons"]
    assert_deny(result)

    mutated = copy.deepcopy(records)
    mutated["stage12574"]["training_allowed"] = True
    result = M.build_materialization(mutated, rows, file_digests=inputs[2], observer=fabricated_observer)
    assert "stage12574_deny_boundary_violated" in result["blocking_reasons"]
    assert_deny(result)

from __future__ import annotations

import copy
import importlib.util
import inspect
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "stage12569", ROOT / "scripts/build_stage12569_acyclic_attestation.py"
)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def temp_paths(tmp_path: Path) -> dict[str, Path]:
    paths = {}
    for name, source in M.SOURCES.items():
        path = tmp_path / f"{name}{source.suffix}"
        path.write_bytes(source.read_bytes())
        paths[name] = path
    return paths


def mutate_json(path: Path, mutate) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    mutate(value)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_current_contract_is_computed_acyclic_deny_only(tmp_path):
    result = M.build(temp_paths(tmp_path))
    graph = result["phase_contract"]["graph_analysis"]
    precondition = result["successor_precondition"]
    assert graph["valid"] is True
    assert graph["acyclic"] is True
    assert len(graph["topological_order"]) == len(result["phase_contract"]["declared_nodes"])
    assert graph["stage12557_dependency_count"] == 0
    assert precondition["unresolved_protected_root_count"] == 25
    assert result["blocking_reasons"] == ["protected_legacy_lineage_unresolved"]
    assert all(result[name] is False for name in M.AUTH_FIELDS)


def test_public_builder_accepts_paths_not_detached_objects_or_hashes():
    parameters = inspect.signature(M.build).parameters
    assert set(parameters) == {"paths", "graph_nodes", "graph_edges"}
    assert not {"ready", "mapping", "source_hashes", "stage12557_output"}.intersection(parameters)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("protected_clearance", True),
        ("control_plane_blocker", "arbitrary-clearance-change"),
        ("clearance_blocking_reasons", []),
    ],
)
def test_stage12568_clearance_fields_are_semantically_noninterfering(tmp_path, field, value):
    paths = temp_paths(tmp_path)
    before = M.build(paths)
    mutate_json(paths["mapping"], lambda mapping: mapping.__setitem__(field, value))
    after = M.build(paths)
    assert before == after


@pytest.mark.parametrize(
    "mutation",
    [
        lambda mapping: mapping["bindings"][0]["evidence"].__setitem__("trajectory_shard_sha256", "0" * 64),
        lambda mapping: mapping["bindings"][0].__setitem__("source_ids", ["src_substituted"]),
        lambda mapping: mapping["bindings"][0]["authority_hashes"].__setitem__(
            "stage12565_paired_commitment", "0" * 64
        ),
        lambda mapping: mapping["bindings"][0].__setitem__("provenance_refs", []),
        lambda mapping: mapping["bindings"][0].__setitem__("training_allowed", True),
    ],
)
def test_mapping_projection_mutation_denies(tmp_path, mutation):
    paths = temp_paths(tmp_path)
    mutate_json(paths["mapping"], mutation)
    blockers = M.build(paths)["blocking_reasons"]
    assert "stage12568_mapping_projection_hash_mismatch" in blockers
    assert "stage12568_mapping_binding_invalid" in blockers


def test_candidate_pair_swap_and_stale_bytes_deny(tmp_path):
    paths = temp_paths(tmp_path)

    def swap(rows):
        rows[0]["task_key"], rows[1]["task_key"] = rows[1]["task_key"], rows[0]["task_key"]

    lines = [json.loads(line) for line in paths["ready"].read_text().splitlines() if line.strip()]
    swap(lines)
    paths["ready"].write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in lines))
    blockers = M.build(paths)["blocking_reasons"]
    assert "ready_byte_hash_stale" in blockers
    assert "candidate_atomic_pair_binding_changed" in blockers


def test_cycle_injection_is_detected_with_no_topological_order(tmp_path):
    paths = temp_paths(tmp_path)
    baseline = M.build(paths)
    nodes = baseline["phase_contract"]["declared_nodes"]
    edges = baseline["phase_contract"]["declared_edges"] + [
        ["protected_candidate_precondition", "mapping"]
    ]
    result = M.build(paths, graph_nodes=nodes, graph_edges=edges)
    graph = result["phase_contract"]["graph_analysis"]
    assert graph["acyclic"] is False
    assert graph["topological_order"] == []
    assert "dependency_cycle_detected" in result["blocking_reasons"]


def test_stage12557_output_perturbation_is_a_non_input(tmp_path):
    paths = temp_paths(tmp_path)
    output = tmp_path / "stage12557_private_train_replay_pilot.json"
    output.write_text('{"arbitrary": 1}')
    before = M.build(paths)
    output.write_text('{"arbitrary": 999, "training_allowed": true}')
    after = M.build(paths)
    assert before == after


def test_declared_stage12557_path_is_derived_and_denied(tmp_path):
    paths = temp_paths(tmp_path)
    substituted = tmp_path / "stage12557_private_train_replay_pilot_mapping.json"
    substituted.write_bytes(paths["mapping"].read_bytes())
    paths["mapping"] = substituted
    result = M.build(paths)
    graph = result["phase_contract"]["graph_analysis"]
    assert graph["stage12557_dependency_count"] == 1
    assert graph["stage12557_dependencies"] == [str(substituted)]
    assert "stage12557_output_present_in_dependencies" in result["blocking_reasons"]


def test_future_hook_record_makes_no_attestation_claim(tmp_path):
    future = M.build(temp_paths(tmp_path))["future_requirements"]
    assert future["non_authorizing_unattested_requirements_only"] is True
    assert future["observed_code_or_test_hashes"] == {}
    assert all(future[name] is False for name in M.AUTH_FIELDS)

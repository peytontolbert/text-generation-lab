from __future__ import annotations

import copy
import importlib.util
import inspect
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "stage12568", ROOT / "scripts/build_stage12568_open_swe_source_lineage_adapter.py"
)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def current_inputs():
    ready = M.read_jsonl(M.READY)
    ready_ids = {row["candidate_id"] for row in ready}
    tasks = [row for row in M.read_jsonl(M.TASKS) if row.get("candidate_id") in ready_ids]
    trajectories = [row for row in M.read_jsonl(M.TRAJECTORIES) if row.get("candidate_id") in ready_ids]
    hashes = {name: M.file_sha256(path) for name, path in M.AUTHORITY_NAMES.items()}
    return trajectories, tasks, ready, hashes


def run_adapter(trajectories=None, tasks=None, ready=None, hashes=None, **kwargs):
    current = current_inputs()
    return M.build_adapter(
        trajectories if trajectories is not None else current[0],
        tasks if tasks is not None else current[1],
        ready if ready is not None else current[2],
        authority_hashes=hashes if hashes is not None else current[3],
        open_swe_revision=M.PINNED_OPEN_SWE_REVISION,
        shard_hasher=lambda _path: M.PINNED_SHARD_SHA256,
        **kwargs,
    )


def write_json(tmp_path, name, value):
    path = tmp_path / name
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return path


def test_exact_eight_bindings_map_only_to_canonical_source_id():
    result = run_adapter()
    assert result["reference_mapping_valid"] is True
    assert len(result["bindings"]) == 8
    assert {tuple(binding["source_ids"]) for binding in result["bindings"]} == {
        (M.CANONICAL_SOURCE_ID,)
    }
    assert result["source_known"] is True
    assert result["source_train_eligible"] is True
    assert result["effective_train_eligible"] is False


def test_stale_authority_hash_denies():
    values = current_inputs()
    hashes = dict(values[3])
    hashes["stage12555_exact_authority_bindings"] = "f" * 64
    result = run_adapter(hashes=hashes)
    assert result["reference_mapping_valid"] is False
    assert "authoritative_artifact_hash_stale" in result["blocking_reasons"]


def test_unknown_shard_denies():
    trajectories = copy.deepcopy(current_inputs()[0])
    trajectories[0]["resolved_fields"]["trajectory_shard_id"]["value"] = "train-00019-of-00020.parquet"
    result = run_adapter(trajectories=trajectories)
    assert result["reference_mapping_valid"] is False
    assert "trajectory_shard_path_unknown_or_mismatched" in result["blocking_reasons"]


def test_stale_or_tampered_shard_denies():
    result = M.build_adapter(
        *current_inputs()[:3],
        authority_hashes=current_inputs()[3],
        open_swe_revision=M.PINNED_OPEN_SWE_REVISION,
        shard_hasher=lambda _path: "0" * 64,
    )
    assert result["reference_mapping_valid"] is False
    assert "trajectory_shard_stale_or_tampered" in result["blocking_reasons"]


def test_registry_hash_tamper_and_substituted_source_id_deny(tmp_path):
    registry = M.read_json(M.REGISTRY)
    record = next(row for row in registry["records"] if row.get("source_id") == M.CANONICAL_SOURCE_ID)
    record["source_id"] = "src_substituted"
    path = write_json(tmp_path, "registry.json", registry)
    result = run_adapter(registry_path=path)
    assert result["reference_mapping_valid"] is False
    assert "base_registry_hash_mismatch" in result["blocking_reasons"]
    assert "canonical_open_swe_source_id_substituted" in result["blocking_reasons"]


def test_rehashed_registry_still_denies(tmp_path):
    registry = M.read_json(M.REGISTRY)
    record = next(row for row in registry["records"] if row.get("source_id") == M.CANONICAL_SOURCE_ID)
    record["train_eligible"] = False
    path = write_json(tmp_path, "registry.json", registry)
    result = run_adapter(registry_path=path)
    assert result["reference_mapping_valid"] is False
    assert result["source_train_eligible"] is False
    assert "base_registry_hash_mismatch" in result["blocking_reasons"]
    assert M.file_sha256(M.REGISTRY) == "98b50df0083fea7be08ccf513b361e78669a2d1be03db7948a2f0a3a90bab807"


def test_duplicate_conflicting_source_id_denies(tmp_path, monkeypatch):
    registry = M.read_json(M.REGISTRY)
    duplicate = copy.deepcopy(registry["records"][0])
    duplicate["source_id"] = M.CANONICAL_SOURCE_ID
    registry["records"].append(duplicate)
    path = write_json(tmp_path, "registry.json", registry)
    monkeypatch.setattr(M, "PINNED_REGISTRY_SHA256", M.file_sha256(path))
    result = run_adapter(registry_path=path)
    assert result["reference_mapping_valid"] is False
    assert "duplicate_or_conflicting_source_id" in result["blocking_reasons"]


def test_full_commitment_model_tamper_denies_even_when_rehashed(tmp_path, monkeypatch):
    commitment = M.read_json(M.COMMITMENT)
    commitment["contract"]["selected_model"]["scorer"] = "substituted"
    commitment["atomic_records"][0]["selected_model"]["scorer"] = "substituted"
    for row in commitment["atomic_records"]:
        body = {key: value for key, value in row.items() if key != "atomic_record_sha256"}
        row["atomic_record_sha256"] = M.STAGE12565.stable_hash(body)
    committed = {"contract": commitment["contract"], "atomic_records": commitment["atomic_records"]}
    commitment["commitment_sha256"] = M.STAGE12565.stable_hash(committed)
    path = write_json(tmp_path, "commitment.json", commitment)
    monkeypatch.setattr(M, "PINNED_COMMITMENT_ARTIFACT_SHA256", M.file_sha256(path))
    result = run_adapter(commitment_path=path)
    assert result["reference_mapping_valid"] is False
    assert "stage12565_contract_selected_model_mismatch" in result["blocking_reasons"]
    assert "stage12565_commitment_hash_mismatch" in result["blocking_reasons"]


def test_non_eight_set_denies():
    trajectories, tasks, ready, _hashes = current_inputs()
    result = run_adapter(trajectories=trajectories[:-1], tasks=tasks[:-1], ready=ready[:-1])
    assert result["reference_mapping_valid"] is False
    assert "ready_task_trajectory_count_not_exactly_eight" in result["blocking_reasons"]
    assert "candidate_task_atomic_count_not_exactly_eight" in result["blocking_reasons"]


def test_stale_stage12564_is_reported_without_mapping_clearance(tmp_path):
    state = M.read_json(M.STAGE12564)
    state["blocking_reasons"].append("stage12562_to_stage12557_summary_binding_stale")
    path = write_json(tmp_path, "stage12564.json", state)
    result = run_adapter(stage12564_path=path)
    assert result["reference_mapping_valid"] is True
    assert result["protected_clearance"] is False
    assert result["effective_train_eligible"] is False
    assert "reported_stale" in result["stage12564_live_rebuild_report"]
    assert "stage12564_artifact_hash_stale" in result["clearance_blocking_reasons"]


def test_mapping_valid_never_implies_stage12557_authorization():
    result = run_adapter()
    assert result["reference_mapping_valid"] is True
    assert "protected_legacy_lineage_unresolved" in result["clearance_blocking_reasons"]
    assert result["protected_clearance"] is False
    assert result["admission_allowed"] is False
    assert result["training_allowed"] is False
    assert result["replay_allowed"] is False
    assert result["gpu_allowed"] is False


def test_base_registry_is_byte_identical_after_build():
    before = M.file_sha256(M.REGISTRY)
    result = run_adapter()
    after = M.file_sha256(M.REGISTRY)
    assert before == after == M.PINNED_REGISTRY_SHA256
    assert result["base_registry_mutated"] is False


def test_no_authorization_input_and_hashes_are_not_source_ids():
    assert not {"authorized", "clearance", "allow", "training_allowed"}.intersection(
        inspect.signature(M.build_adapter).parameters
    )
    result = run_adapter()
    guard_spec = importlib.util.spec_from_file_location("guard12568", ROOT / "scripts/source_lineage_guard.py")
    assert guard_spec and guard_spec.loader
    guard = importlib.util.module_from_spec(guard_spec)
    sys.modules[guard_spec.name] = guard
    guard_spec.loader.exec_module(guard)
    assert guard.source_ids_from_row(result["bindings"][0]) == {M.CANONICAL_SOURCE_ID}
    assert result["caller_authorization_input_accepted"] is False
    assert result["model_patch_read"] is False
    assert result["verifier_output_read"] is False


def test_candidate_id_swap_denies_cross_artifact_identity_join():
    trajectories = copy.deepcopy(current_inputs()[0])
    trajectories[0]["candidate_id"], trajectories[1]["candidate_id"] = (
        trajectories[1]["candidate_id"], trajectories[0]["candidate_id"]
    )
    result = run_adapter(trajectories=trajectories)
    assert result["reference_mapping_valid"] is False
    assert {
        "trajectory_task_atomic_instance_mismatch",
        "trajectory_task_atomic_repo_mismatch",
    }.intersection(result["blocking_reasons"])


def test_jointly_rewritten_stage12554_metadata_and_runtime_hash_denies(tmp_path, monkeypatch):
    trajectories, _tasks, _ready, hashes = current_inputs()
    rewritten = copy.deepcopy(trajectories)
    rewritten[0]["overall_disposition"] = "jointly-rewritten"
    path = tmp_path / "stage12554_rewritten.jsonl"
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rewritten),
        encoding="utf-8",
    )
    monkeypatch.setitem(M.AUTHORITY_NAMES, "stage12554_resolved_trajectory_bindings", path)
    hashes = dict(hashes)
    hashes["stage12554_resolved_trajectory_bindings"] = M.file_sha256(path)
    result = run_adapter(trajectories=rewritten, hashes=hashes)
    assert result["reference_mapping_valid"] is False
    assert "stage12554_trajectory_binding_artifact_hash_mismatch" in result["blocking_reasons"]


def test_control_plane_dependency_cycle_is_explicit_and_fail_closed():
    result = run_adapter()
    assert result["control_plane_blocker"] == "stage12564_stage12557_attestation_dependency_cycle"
    assert result["control_plane_blocker"] in result["clearance_blocking_reasons"]
    assert result["protected_clearance"] is False

from __future__ import annotations

import copy
import importlib.util
import inspect
import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "stage12567", ROOT / "scripts/build_or_run_stage12557_private_train_replay_pilot.py"
)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def current_inputs():
    ready = M.read_jsonl(M.READY)
    ready_ids = {row["candidate_id"] for row in ready}
    trajectories = [row for row in M.read_jsonl(M.TRAJECTORIES) if row.get("candidate_id") in ready_ids]
    tasks = [row for row in M.read_jsonl(M.TASKS) if row.get("candidate_id") in ready_ids]
    return ready, trajectories, tasks


def allowed_registry(ready, trajectories, tasks, extra=()):
    pairs, blockers = M._identity_pairs(ready, tasks, trajectories)
    assert blockers == []
    assert M._commitment_blockers(M.read_json(M.ATOMIC_COMMITMENT), pairs, M.ATOMIC_COMMITMENT) == []
    source_ids = set().union(*(M._GUARD.source_ids_from_row(pair) for pair in pairs))
    source_ids.update(extra)
    return {
        source_id: {
            "source_id": source_id, "locked_eval": False,
            "hidden_final": False, "train_eligible": True,
        }
        for source_id in source_ids
    }


def run_public(monkeypatch, ready, trajectories, tasks, *, commitment_path=None, source_adapter_path=None, registry=None):
    if registry is None:
        registry = allowed_registry(ready, trajectories, tasks)
    monkeypatch.setattr(M, "load_source_registry", lambda: registry)
    kwargs = {}
    if commitment_path is not None:
        kwargs["commitment_path"] = commitment_path
    if source_adapter_path is not None:
        kwargs["source_adapter_path"] = source_adapter_path
    return M.build(ready, trajectories, tasks, Path("never-read.parquet"), "0" * 64, **kwargs)


def test_no_sensitive_bypass_and_no_caller_boolean_authority():
    for name in (
        "_build_post_gate", "sensitive_after_guard", "parquet_rows",
        "exact_trajectory_patch", "task_authority_by_instance", "execute_canary",
    ):
        assert not hasattr(M, name)
    parameters = inspect.signature(M.build).parameters
    assert not {"lineage_allowed", "commitment_valid", "guard_allowed"}.intersection(parameters)


def test_current_path_has_non_empty_reconstructed_source_ids(monkeypatch):
    ready, trajectories, tasks = current_inputs()
    result = run_public(monkeypatch, ready, trajectories, tasks)
    decisions = result["summary"]["recursive_lineage_decisions"]
    assert not any(reason.startswith("stage12568_") for reason in result["summary"]["blocking_reasons"])
    assert len(decisions) == 8
    assert all(row["source_ids"] == [M.CANONICAL_OPEN_SWE_SOURCE_ID] for row in decisions)
    assert result["summary"]["pre_read_guard_denied_count"] == 8


def test_trajectory_protected_ancestry_is_seen_recursively(monkeypatch):
    ready, trajectories, tasks = current_inputs()
    trajectories = copy.deepcopy(trajectories)
    candidate = ready[0]["candidate_id"]
    trajectory = next(row for row in trajectories if row.get("candidate_id") == candidate)
    trajectory["parents"] = [{"derived": [{"source_id": "protected:trajectory-parent"}]}]
    registry = allowed_registry(ready, trajectories, tasks, ["protected:trajectory-parent"])
    registry["protected:trajectory-parent"].update({"locked_eval": True, "train_eligible": False})
    result = run_public(monkeypatch, ready, trajectories, tasks, registry=registry)
    decision = next(row for row in result["summary"]["recursive_lineage_decisions"] if "protected:trajectory-parent" in row["source_ids"])
    assert decision["locked_source_ids"] == ["protected:trajectory-parent"]
    assert "recursive_source_lineage_guard_denied" in result["summary"]["blocking_reasons"]


@pytest.mark.parametrize("field", ["certificate_sha256", "mirror_path"])
def test_ready_certificate_or_mirror_tampering_denies(monkeypatch, field):
    ready, trajectories, tasks = current_inputs()
    ready = copy.deepcopy(ready)
    if field == "certificate_sha256":
        ready[0][field] = "0" * 64
    else:
        ready[0]["checkout_object_certificate"][field] = "/tmp/substituted-mirror"
    result = run_public(monkeypatch, ready, trajectories, tasks, registry={})
    assert "stage12565_atomic_binding_reconstruction_mismatch" in result["summary"]["blocking_reasons"]


def test_trajectory_source_binding_tampering_denies(monkeypatch):
    ready, trajectories, tasks = current_inputs()
    trajectories = copy.deepcopy(trajectories)
    trajectories[0]["resolved_fields"]["model_patch_sha256"]["source"] = "/tmp/substituted.parquet"
    result = run_public(monkeypatch, ready, trajectories, tasks, registry={})
    assert "trajectory_exact_source_binding_mismatch" in result["summary"]["blocking_reasons"]


def write_rehashed_commitment(tmp_path, mutate):
    commitment = copy.deepcopy(M.read_json(M.ATOMIC_COMMITMENT))
    mutate(commitment)
    for row in commitment["atomic_records"]:
        body = {key: value for key, value in row.items() if key != "atomic_record_sha256"}
        row["atomic_record_sha256"] = M._COMMITMENT.stable_hash(body)
    committed = {"contract": commitment["contract"], "atomic_records": commitment["atomic_records"]}
    commitment["commitment_sha256"] = M._COMMITMENT.stable_hash(committed)
    path = tmp_path / "commitment.json"
    path.write_text(json.dumps(commitment), encoding="utf-8")
    return path


def test_atomic_source_row_tampering_denies(tmp_path, monkeypatch):
    ready, trajectories, tasks = current_inputs()
    path = write_rehashed_commitment(
        tmp_path,
        lambda commitment: commitment["atomic_records"][0]["source_row_sha256"].__setitem__(
            "stage12556_ready_row", "0" * 64
        ),
    )
    monkeypatch.setattr(M, "ATOMIC_COMMITMENT_SHA256", M.file_sha256(path))
    result = run_public(monkeypatch, ready, trajectories, tasks, commitment_path=path, registry={})
    assert "stage12565_atomic_binding_reconstruction_mismatch" in result["summary"]["blocking_reasons"]


def test_atomic_source_artifact_tampering_denies(tmp_path, monkeypatch):
    ready, trajectories, tasks = current_inputs()
    path = write_rehashed_commitment(
        tmp_path,
        lambda commitment: commitment["atomic_records"][0]["source_artifact_sha256"].__setitem__(
            "stage12556_ready_rows", "0" * 64
        ),
    )
    monkeypatch.setattr(M, "ATOMIC_COMMITMENT_SHA256", M.file_sha256(path))
    result = run_public(monkeypatch, ready, trajectories, tasks, commitment_path=path, registry={})
    assert "stage12565_atomic_binding_reconstruction_mismatch" in result["summary"]["blocking_reasons"]


def test_selected_model_tampering_denies_even_when_rehashed(tmp_path, monkeypatch):
    ready, trajectories, tasks = current_inputs()

    def mutate(commitment):
        commitment["contract"]["selected_model"]["scorer"] = "substituted_scorer"
        commitment["atomic_records"][0]["selected_model"]["scorer"] = "substituted_scorer"

    path = write_rehashed_commitment(tmp_path, mutate)
    monkeypatch.setattr(M, "ATOMIC_COMMITMENT_SHA256", M.file_sha256(path))
    result = run_public(monkeypatch, ready, trajectories, tasks, commitment_path=path, registry={})
    blockers = result["summary"]["blocking_reasons"]
    assert "stage12565_selected_model_binding_mismatch" in blockers
    assert "stage12565_atomic_binding_reconstruction_mismatch" in blockers


def test_denial_precedes_parquet_patch_and_subprocess_seams(monkeypatch):
    ready, trajectories, tasks = current_inputs()
    registry = allowed_registry(ready, trajectories, tasks)
    events = []
    original_evaluate = M.evaluate_row_source_lineage
    original_sha = M.file_sha256

    def evaluate(row, supplied_registry):
        events.append("lineage:" + row["candidate_id"])
        return original_evaluate(row, supplied_registry)

    def guarded_sha(path):
        if Path(path).suffix == ".parquet":
            events.append("trajectory-patch")
            raise AssertionError("trajectory patch source touched after denial")
        return original_sha(path)

    monkeypatch.setattr(M, "load_source_registry", lambda: registry)
    monkeypatch.setattr(M, "evaluate_row_source_lineage", evaluate)
    monkeypatch.setattr(M, "file_sha256", guarded_sha)
    monkeypatch.setattr(pq, "ParquetFile", lambda *_: events.append("parquet") or (_ for _ in ()).throw(AssertionError("parquet touched")))
    monkeypatch.setattr(M.subprocess, "run", lambda *_args, **_kwargs: events.append("subprocess") or (_ for _ in ()).throw(AssertionError("subprocess touched")))
    result = M.build(ready, trajectories, tasks, Path("never-read.parquet"), "0" * 64)
    assert result["summary"]["pre_read_guard_denied_count"] == 8
    assert len(events) == 8
    assert all(event.startswith("lineage:") for event in events)


@pytest.mark.parametrize("kind", ["task", "trajectory"])
def test_duplicate_candidate_rows_deny_exact_set(kind):
    ready, trajectories, tasks = current_inputs()
    selected = tasks if kind == "task" else trajectories
    selected[1] = copy.deepcopy(selected[0])
    _pairs, blockers = M._identity_pairs(ready, tasks, trajectories)
    assert f"{kind}_candidate_ids_missing_or_duplicate" in blockers
    assert f"{kind}_candidate_set_not_exactly_ready" in blockers


@pytest.mark.parametrize("kind", ["task", "trajectory"])
def test_extra_candidate_rows_deny_exact_set(kind):
    ready, trajectories, tasks = current_inputs()
    selected = tasks if kind == "task" else trajectories
    extra = copy.deepcopy(selected[0])
    extra["candidate_id"] = "extra-candidate"
    selected.append(extra)
    _pairs, blockers = M._identity_pairs(ready, tasks, trajectories)
    assert f"{kind}_candidate_count_not_exactly_eight" in blockers
    assert f"{kind}_candidate_set_not_exactly_ready" in blockers


def test_pure_projection_join_accepts_reordered_rows():
    identities = [
        {"instance_id": "a", "repo": "one"},
        {"instance_id": "b", "repo": "two"},
    ]
    verifiers = [
        {"instance_id": "b", "install_config": {"test_cmd": "b"}},
        {"instance_id": "a", "install_config": {"test_cmd": "a"}},
    ]
    joined, blockers = M._join_task_projections(identities, verifiers)
    assert blockers == []
    assert joined["a"][0]["repo"] == "one"
    assert joined["a"][0]["install_config"]["test_cmd"] == "a"
    assert joined["b"][0]["install_config"]["test_cmd"] == "b"


def test_pure_projection_join_denies_missing_instance_id():
    joined, blockers = M._join_task_projections(
        [{"instance_id": "a", "repo": "one"}],
        [{"install_config": {"test_cmd": "a"}}],
    )
    assert joined == {}
    assert blockers == ["task_verifier_instance_id_missing"]


def test_pure_projection_join_denies_duplicate_instance_id():
    joined, blockers = M._join_task_projections(
        [{"instance_id": "a"}, {"instance_id": "a"}],
        [{"instance_id": "a"}, {"instance_id": "a"}],
    )
    assert joined == {}
    assert blockers == ["task_identity_verifier_join_key_not_unique"]


def test_verifier_projection_uses_explicit_shared_instance_join_key():
    assert "instance_id" in M.TASK_IDENTITY_COLUMNS
    assert "instance_id" in M.TASK_VERIFIER_COLUMNS
    assert set(M.TASK_IDENTITY_COLUMNS).intersection(M.TASK_VERIFIER_COLUMNS) == {"instance_id"}


def test_missing_stage12568_adapter_denies_before_sensitive_reads(tmp_path, monkeypatch):
    ready, trajectories, tasks = current_inputs()
    result = run_public(
        monkeypatch, ready, trajectories, tasks,
        source_adapter_path=tmp_path / "missing-adapter.json",
    )
    summary = result["summary"]
    assert "stage12568_adapter_missing_or_invalid" in summary["blocking_reasons"]
    assert "recursive_source_lineage_guard_denied" in summary["blocking_reasons"]
    assert summary["trajectory_model_patch_read"] is False
    assert summary["verifier_bearing_parquet_read"] is False
    assert summary["subprocess_invoked"] is False


def test_stale_rehashed_stage12568_adapter_denies_before_sensitive_reads(tmp_path, monkeypatch):
    ready, trajectories, tasks = current_inputs()
    adapter = copy.deepcopy(M.read_json(M.SOURCE_ADAPTER))
    adapter["bindings"][0]["source_ids"] = ["src_substituted"]
    body = {key: value for key, value in adapter.items() if key != "adapter_sha256"}
    adapter["adapter_sha256"] = M.stable_hash(body)
    path = tmp_path / "adapter.json"
    path.write_text(json.dumps(adapter), encoding="utf-8")
    result = run_public(monkeypatch, ready, trajectories, tasks, source_adapter_path=path)
    blockers = result["summary"]["blocking_reasons"]
    assert "stage12568_adapter_artifact_hash_mismatch" in blockers
    assert "stage12568_adapter_semantic_hash_mismatch" in blockers
    assert "stage12568_adapter_binding_semantics_invalid" in blockers
    assert result["summary"]["trajectory_model_patch_read"] is False
    assert result["summary"]["subprocess_invoked"] is False


def test_base_registry_hash_is_checked_before_registry_load(tmp_path, monkeypatch):
    ready, trajectories, tasks = current_inputs()
    path = tmp_path / "registry.json"
    path.write_text('{"records": []}', encoding="utf-8")
    monkeypatch.setattr(M._GUARD, "DEFAULT_LINEAGE", path)
    result = run_public(monkeypatch, ready, trajectories, tasks)
    assert "base_source_registry_artifact_hash_mismatch" in result["summary"]["blocking_reasons"]
    assert result["summary"]["verifier_bearing_parquet_read"] is False

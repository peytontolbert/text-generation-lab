from __future__ import annotations

import copy
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "stage12557", ROOT / "scripts/build_or_run_stage12557_private_train_replay_pilot.py"
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


def test_exact_current_identity_and_atomic_reconstruction_is_complete():
    ready, trajectories, tasks = current_inputs()
    pairs, blockers = M._identity_pairs(ready, tasks, trajectories)
    commitment_blockers = M._commitment_blockers(M.read_json(M.ATOMIC_COMMITMENT), pairs, M.ATOMIC_COMMITMENT)
    assert blockers == []
    assert commitment_blockers == []
    assert len(pairs) == 8
    expected_provenance_refs = {
        "trajectory:nvidia/Open-SWE-Traces@"
        "f6689f56f1af2e2082861738071d4c4278b1922a:openhands:minimax_m25:"
        "train-00000-of-00020.parquet:"
        "5befb7356a4bce7c13bc5a8313fdd42df0488c567eeaf42a668dcf307642320e",
        "stage12555_exact_authority_bindings:sha256:"
        "b423a417dc2f0a65c808a4edd2b3e4b7cdd8f90c0f3af8de8a92e8a5575bbeae",
        "stage12556_ready_rows:sha256:"
        "ad7f205b0b757437c073ca88e014bdd0140083bbbeb5b93b6e088e1f55b91511",
        "stage12565_commitment:sha256:"
        "d9ae7fcc9865f811cf3355d8f3f9e597ad930f4d2184939e3a4d53ccf6c97e71",
    }
    for pair in pairs:
        assert pair["source_ids"] == [M.CANONICAL_OPEN_SWE_SOURCE_ID]
        assert len(pair["provenance_refs"]) == 4
        assert set(pair["provenance_refs"]) == expected_provenance_refs
        assert set(pair["authority_hashes"]) == {
            "stage12555_exact_authority_bindings", "stage12556_ready_rows"
        }
        assert M._GUARD.source_ids_from_row(pair) == {M.CANONICAL_OPEN_SWE_SOURCE_ID}

def test_protected_split_stops_in_non_sensitive_pair_reconstruction():
    ready, trajectories, tasks = current_inputs()
    tasks = copy.deepcopy(tasks)
    candidate = ready[0]["candidate_id"]
    task = next(row for row in tasks if row.get("candidate_id") == candidate)
    task["policy_split"] = "sealed_eval"
    task["protected_from_training"] = True
    _pairs, blockers = M._identity_pairs(ready, tasks, trajectories)
    assert "ready_task_exact_identity_pair_mismatch" in blockers


def test_trajectory_source_binding_tamper_fails_non_sensitive_reconstruction():
    ready, trajectories, tasks = current_inputs()
    trajectories = copy.deepcopy(trajectories)
    candidate = ready[0]["candidate_id"]
    trajectory = next(row for row in trajectories if row.get("candidate_id") == candidate)
    trajectory["resolved_fields"]["trajectory_ordinal"]["source"] = "/tmp/wrong.parquet"
    pairs, blockers = M._identity_pairs(ready, tasks, trajectories)
    assert "trajectory_exact_source_binding_mismatch" in blockers
    pair = next(row for row in pairs if row["candidate_id"] == candidate)
    assert pair["source_ids"] == []


def test_current_public_path_stops_all_candidates_without_sensitive_access(monkeypatch):
    ready, trajectories, tasks = current_inputs()
    original_sha = M.file_sha256

    def guarded_sha(path: Path):
        if path.suffix == ".parquet":
            raise AssertionError("sensitive parquet touched")
        return original_sha(path)

    monkeypatch.setattr(M, "file_sha256", guarded_sha)
    result = M.build(ready, trajectories, tasks, Path("never-read.parquet"), "0" * 64)
    assert len(result["records"]) == 8
    assert result["summary"]["pre_read_guard_denied_count"] == 8
    assert all(row["stop_continue"]["decision"] == "stop" for row in result["records"])


def test_no_module_level_sensitive_bypass_exists():
    for name in (
        "_build_post_gate", "sensitive_after_guard", "parquet_rows",
        "exact_trajectory_patch", "task_authority_by_instance", "execute_canary",
    ):
        assert not hasattr(M, name)

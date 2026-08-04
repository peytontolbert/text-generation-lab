from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12585_same_source_observed_trajectory_root_miner.py"
SPEC = importlib.util.spec_from_file_location("stage12585", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)
ARTIFACTS = ROOT / "runs/local/artifacts/stage12585_same_source_observed_trajectory_root_miner"


def protected_payload(*, repo: str | None = None, root: str | None = None) -> dict[str, object]:
    return {
        "schema_version": 1,
        "record_type": "future_eval_identity_denylist_v1",
        "deny": {
            "repo_family": [repo] if repo else [],
            "source_path": [],
            "root_identity": [root] if root else [],
        },
    }


def window(*, task: str = "window-1", source: str = "source-1") -> dict[str, object]:
    return {
        "task_window_id": task,
        "source_file_hash_compat": source,
        "has_user_signal": True,
        "has_assistant_signal": True,
        "has_command_observation": True,
        "has_patch_ref": True,
        "has_verifier_like_ref": True,
        "paired_tool_call_count": 4,
        "patch_pair_count": 1,
        "verifier_like_pair_count": 1,
        "start_line": 10,
        "end_line": 30,
        "terminal_status": "task_complete",
    }


def join(
    *,
    join_id: str = "join-1",
    task: str = "window-1",
    source: str = "source-1",
    session: str = "session-1",
    root: str = "root-1",
) -> dict[str, object]:
    return {
        "join_record_id": join_id,
        "task_window_id": task,
        "canonical_root_id": root,
        "source_refs": {
            "source_file_hash_compat": source,
            "session_id_hash": session,
        },
        "window_evidence_shape": {
            "has_command_observation": True,
            "has_verifier_like_ref": True,
            "paired_tool_call_count": 4,
        },
    }


def recovery(
    *,
    recovery_id: str = "recovery-1",
    join_id: str = "join-1",
    task: str = "window-1",
    root: str = "root-1",
    repo: str = "example-repo",
) -> dict[str, object]:
    return {
        "recovery_record_id": recovery_id,
        "source_join_record_id": join_id,
        "task_window_id": task,
        "identity_recovery": {
            "root_id_candidate": root,
            "repo_family_candidate": repo,
            "language_candidate": "python",
        },
        "transition_recovery": {
            "command_result_candidate": {
                "patch_event_count": 1,
                "verifier_event_count": 1,
            },
            "verifier_transition_candidate": {
                "verifier_status_class": "VERIFIER_PASS_OBSERVED",
            },
            "state_update_candidate": {
                "review_required": True,
                "state_update_codes": ["PATCH_EVENT_OBSERVED"],
            },
            "stop_decision_candidate": {
                "review_required": True,
                "stop_continue_label": "STOP_SIGNAL_OBSERVED",
            },
        },
    }


def complete_candidate(*, decision_states: int = 1, patch: bool = True) -> dict[str, object]:
    return {
        "source_kind": "same_session_observed_trace",
        "provenance_stage": "synthetic_observed_source",
        "protected_overlap": {"overlap": False, "matched_identity_kinds": []},
        "evidence": {
            "observed_task": True,
            "ordered_action": True,
            "command_tool_observation": True,
            "verifier_result": True,
            "state_after": True,
            "stop_continue": True,
            "patch_trace": patch,
            "explicit_no_patch_reason": not patch,
            "patch_context": patch,
            "verifier_intent": True,
            "historical_candidate_set": True,
            "candidate_set_committed_pre_outcome": True,
            "candidate_set_derived_from_after_diff": False,
            "candidate_action_count": 5,
            "decision_state_count": decision_states,
        },
    }


def replay83() -> dict[str, object]:
    return {
        "episode_id": "stage12583_causal_episode_microfactory_deadbeef",
        "source": {"repository": "/arxiv/repositories/unsloth"},
    }


def replay84() -> dict[str, object]:
    return {
        "candidate_identity_sha256": "a" * 64,
        "source_identity_sha256": "b" * 64,
    }


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def all_keys(value: object):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from all_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_keys(child)


def test_classifier_accepts_only_complete_observed_trajectories() -> None:
    assert mod.classify_candidate(complete_candidate())[0] == "observed_level3"
    assert mod.classify_candidate(complete_candidate(decision_states=2))[0] == "observed_level4"
    no_patch = complete_candidate(patch=False)
    assert mod.classify_candidate(no_patch)[0] == "observed_level3"


def test_classifier_rejects_after_diff_and_absent_historical_candidates() -> None:
    leaked = complete_candidate()
    leaked["evidence"]["candidate_set_derived_from_after_diff"] = True
    classification, blockers = mod.classify_candidate(leaked)
    assert classification == "blocked"
    assert "candidate_set_after_diff_leakage_or_unknown" in blockers

    absent = complete_candidate()
    absent["evidence"]["historical_candidate_set"] = False
    absent["evidence"]["candidate_set_committed_pre_outcome"] = False
    absent["evidence"]["candidate_action_count"] = 0
    classification, blockers = mod.classify_candidate(absent)
    assert classification == "blocked"
    assert "historical_candidate_set_missing" in blockers
    assert "candidate_set_not_committed_pre_outcome" in blockers
    assert "candidate_action_set_empty" in blockers


def test_level2_requires_pre_outcome_candidates_and_no_command_observation() -> None:
    candidate = complete_candidate()
    candidate["evidence"]["command_tool_observation"] = False
    candidate["evidence"]["verifier_result"] = False
    candidate["evidence"]["state_after"] = False
    candidate["evidence"]["stop_continue"] = False
    candidate["evidence"]["patch_trace"] = False
    assert mod.classify_candidate(candidate)[0] == "level2_patch_context"

    candidate["evidence"]["historical_candidate_set"] = False
    candidate["evidence"]["candidate_action_count"] = 0
    assert mod.classify_candidate(candidate)[0] == "blocked"


def test_stage12388_normalization_never_promotes_observed_order_or_status_only_patch() -> None:
    row = recovery()
    row["candidate_actions"] = [{"invented_from": "after_diff"}]
    candidate = mod.normalize_same_session_candidate(
        row,
        join(),
        window(),
        mod.load_protected_identities(protected_payload()),
    )
    assert candidate["exact_same_source_join"] is True
    assert candidate["evidence"]["observed_task"] is True
    assert candidate["evidence"]["ordered_action"] is True
    assert candidate["evidence"]["command_tool_observation"] is True
    assert candidate["evidence"]["verifier_result"] is True
    assert candidate["evidence"]["stop_continue"] is True
    assert candidate["evidence"]["state_after"] is False
    assert candidate["evidence"]["patch_trace"] is False
    assert candidate["evidence"]["historical_candidate_set"] is False
    assert candidate["classification_preview"] == "blocked"
    assert "historical_candidate_set_missing" in candidate["blockers"]
    assert "candidate_actions" not in set(all_keys(candidate))


def test_cross_source_or_session_window_join_is_blocked() -> None:
    candidate = mod.normalize_same_session_candidate(
        recovery(),
        join(source="source-A"),
        window(source="source-B"),
        mod.load_protected_identities(protected_payload()),
    )
    assert candidate["exact_same_source_join"] is False
    assert candidate["classification_preview"] == "blocked"
    assert "exact_source_session_window_join_missing_or_mismatched" in candidate["blockers"]


def test_protected_overlap_blocks_observed_candidates() -> None:
    candidate = complete_candidate()
    candidate["protected_overlap"] = {"overlap": True, "matched_identity_kinds": ["repo_family"]}
    classification, blockers = mod.classify_candidate(candidate)
    assert classification == "blocked"
    assert "protected_identity_overlap" in blockers


def test_replays_are_forced_replay_only_and_never_counted() -> None:
    candidates, classifications = mod.build_ledgers(
        recovery_rows=[],
        join_rows=[],
        window_rows=[],
        replay12583_rows=[replay83()],
        replay12584_rows=[replay84()],
        protected_payload=protected_payload(repo="Unsloth"),
    )
    assert {row["classification"] for row in classifications} == {"patch_effect_replay_only"}
    assert all(row["counts_toward_level3_plus_floor"] is False for row in classifications)
    assert all(row["counts_toward_patch_trace_floor"] is False for row in classifications)
    stage83 = next(row for row in candidates if row["provenance_stage"].startswith("stage12583"))
    assert stage83["protected_overlap"]["overlap"] is True


def test_deduplication_is_exact_source_session_root_window() -> None:
    first = recovery(recovery_id="recovery-A")
    second = recovery(recovery_id="recovery-B")
    candidates, classifications = mod.build_ledgers(
        recovery_rows=[second, first],
        join_rows=[join()],
        window_rows=[window()],
        replay12583_rows=[],
        replay12584_rows=[],
        protected_payload=protected_payload(),
    )
    assert len(candidates) == 2
    assert sum(row["canonical_for_dedupe_key"] for row in candidates) == 1
    duplicate = next(row for row in classifications if row["duplicate_of"] is not None)
    assert duplicate["classification"] == "blocked"
    assert "duplicate_source_session_root_window" in duplicate["blockers"]


def test_forbidden_artifact_shapes_are_rejected_recursively() -> None:
    for key in mod.FORBIDDEN_OUTPUT_KEYS:
        with pytest.raises(mod.GateError, match="forbidden_output_key"):
            mod.assert_no_forbidden_output_keys({"nested": [{key: []}]})


def test_execute_is_deterministic_and_emits_only_ledgers_and_summary(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    paths = {
        "recovery": inputs / "recovery.jsonl",
        "join": inputs / "join.jsonl",
        "windows": inputs / "windows.jsonl",
        "stage12583": inputs / "stage12583.jsonl",
        "stage12584": inputs / "stage12584.jsonl",
        "denylist": inputs / "denylist.json",
    }
    write_jsonl(paths["recovery"], [recovery()])
    write_jsonl(paths["join"], [join()])
    write_jsonl(paths["windows"], [window()])
    write_jsonl(paths["stage12583"], [replay83()])
    write_jsonl(paths["stage12584"], [replay84()])
    write_json(paths["denylist"], protected_payload(repo="Unsloth"))
    out = tmp_path / "out"
    external = tmp_path / "summary.json"

    kwargs = {
        "out": out,
        "summary_path": external,
        "recovery_path": paths["recovery"],
        "join_path": paths["join"],
        "windows_path": paths["windows"],
        "stage12583_path": paths["stage12583"],
        "stage12584_path": paths["stage12584"],
        "denylist_path": paths["denylist"],
    }
    first = mod.execute(**kwargs)
    first_bytes = {path.name: path.read_bytes() for path in out.iterdir()}
    second = mod.execute(**kwargs)
    second_bytes = {path.name: path.read_bytes() for path in out.iterdir()}

    assert first == second
    assert first_bytes == second_bytes
    assert set(first_bytes) == {"candidate_ledger.jsonl", "classification_ledger.jsonl", "summary.json"}
    assert json.loads((out / "summary.json").read_text()) == json.loads(external.read_text())
    assert first["status"] == "TRAJECTORY_FLOORS_UNMET"
    assert first["counts"]["classifications"] == {
        "blocked": 1,
        "level2_patch_context": 0,
        "observed_level3": 0,
        "observed_level4": 0,
        "patch_effect_replay_only": 2,
    }
    assert all(not item["met"] for item in first["floor_status"].values())
    assert not mod.FORBIDDEN_OUTPUT_KEYS.intersection(all_keys(first))


def test_materialized_artifacts_are_audit_only_and_honest() -> None:
    summary = json.loads((ARTIFACTS / "summary.json").read_text(encoding="utf-8"))
    external = json.loads(
        (ROOT / "runs/summaries/stage12585_same_source_observed_trajectory_root_miner.json").read_text(
            encoding="utf-8"
        )
    )
    candidates = [
        json.loads(line)
        for line in (ARTIFACTS / "candidate_ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    classifications = [
        json.loads(line)
        for line in (ARTIFACTS / "classification_ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert summary == external
    assert summary["training_allowed"] is False
    assert summary["training_executed"] is False
    assert summary["counts"]["input_candidates"] == len(candidates) == len(classifications)
    assert summary["counts"]["stage12583_stage12584_floor_contribution"] == 0
    assert all(not item["met"] for item in summary["floor_status"].values())
    assert set(summary["artifact_contract"].values()).isdisjoint({True})
    for record in [*candidates, *classifications, summary]:
        assert record["training_allowed"] is False
        assert not mod.FORBIDDEN_OUTPUT_KEYS.intersection(all_keys(record))

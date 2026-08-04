from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12587_trajectory_vs_ranking_gate_correction.py"
SPEC = importlib.util.spec_from_file_location("stage12587", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def valid_record() -> dict[str, object]:
    action = {
        "action_id": "action-1",
        "sequence": 1,
        "call_line_number": 20,
        "authoritative_pair_present": True,
    }
    observation = {
        "action_id": "action-1",
        "output_line_number": 21,
        "status": "passed",
    }
    return {
        "hydration_record_id": "hydration-1",
        "upstream_candidate_id": "candidate-1",
        "source_identity": {"same_source_join_validated": True},
        "source_validation": {"content_hash_match": True},
        "ordered_tool_actions": [action],
        "paired_observations": [observation],
        "verifier_observations": [{
            "action_id": "action-1",
            "command_sha256": "a" * 64,
            "output_line_number": 21,
            "status": "passed",
            "completed": True,
            "relevant_to_observed_edit": True,
            "observed_order_relative_to_edits": "after_last_edit",
        }],
        "transition_local_facts": {
            "first_transition_line": 20,
            "last_transition_line": 20,
            "pre_transition_facts": [{"fact_type": "turn_context", "line_number": 10, "payload_sha256": "b" * 64}],
            "post_transition_facts": [{
                "fact_type": "git_status",
                "action_id": "action-1",
                "call_line_number": 22,
                "status": "passed",
            }],
        },
        "terminal_observation": {"present": True, "lifecycle_event": "task_complete"},
        "edit_evidence": {"observed_edits": [{"payload_observed": True, "payload_sha256": "c" * 64}]},
    }


def provenance(provenance_type: str, identity: str) -> dict[str, object]:
    base: dict[str, object] = {
        "candidate_id": identity,
        "provenance_type": provenance_type,
        "visibility": mod.visibility_for(provenance_type),
        "derived_from_after_diff": False,
    }
    if provenance_type == "observed_executed_action":
        base.update(same_source_observed=True, executed=True)
    elif provenance_type == "prospective_pre_outcome_commitment":
        base.update(sealed_before_outcome=True, outcome_visible_at_commitment=False)
    else:
        base.update(
            independently_validated=True,
            derived_from_observed_outcome=False,
            same_source_execution_claim=False,
        )
    return base


def test_contract_separates_trajectory_from_ranking_and_preserves_5_3_preference() -> None:
    contract = mod.corrected_gate_contract()
    assert contract["observed_trajectory_gate"]["candidate_alternatives_required"] is False
    assert "candidate_alternatives" in contract["observed_trajectory_gate"]["not_requirements"]
    requirements = contract["observed_trajectory_gate"]["requirements"]
    assert "ordered_post_transition_probe" in requirements
    assert "literal_terminal_observation" in requirements
    assert "reviewed_state_update" not in requirements
    assert "stop_or_continue" not in requirements
    assert contract["authority"]["positive_stop_target_allowed"] is False
    ranking = contract["candidate_ranking_listwise_gate"]
    assert ranking["minimum_geometry"] == {
        "distinct_candidates": 2,
        "independently_validated_semantic_negatives": 1,
    }
    assert ranking["preferred_full_geometry"]["short_name"] == "5/3"


def test_valid_observed_trajectory_without_candidates_is_cardinality_only() -> None:
    result = mod.audit_record(valid_record())
    assert result["observed_trajectory_gate"]["valid"] is True
    assert result["candidate_ranking_listwise_gate"]["eligible"] is False
    assert result["blocker_partition"] == {
        "classification": "candidate_cardinality_only",
        "substantive_evidence_blocked": False,
        "candidate_cardinality_only": True,
    }


def test_ranking_minimum_requires_distinct_candidate_and_independent_negative() -> None:
    positive = provenance("observed_executed_action", "positive")
    negative = provenance("independent_counterfactual_negative", "negative")
    result = mod.audit_candidate_ranking([positive, negative])
    assert result["eligible"] is True
    assert result["minimum_geometry"]["met"] is True
    assert result["preferred_full_geometry"]["met"] is False

    duplicate = copy.deepcopy(negative)
    duplicate["candidate_id"] = "positive"
    duplicate["semantic_identity_sha256"] = "positive"
    positive["semantic_identity_sha256"] = "positive"
    result = mod.audit_candidate_ranking([positive, duplicate])
    assert result["eligible"] is False
    assert "distinct_candidate_count_below_minimum" in result["blockers"]


def test_preferred_geometry_is_five_distinct_with_three_independent_negatives() -> None:
    candidates = [
        provenance("observed_executed_action", "positive"),
        provenance("prospective_pre_outcome_commitment", "prospective"),
        provenance("independent_counterfactual_negative", "negative-1"),
        provenance("independent_counterfactual_negative", "negative-2"),
        provenance("independent_counterfactual_negative", "negative-3"),
    ]
    result = mod.audit_candidate_ranking(candidates)
    assert result["eligible"] is True
    assert result["preferred_full_geometry"]["met"] is True


def test_provenance_visibility_and_independence_fail_closed() -> None:
    observed = provenance("observed_executed_action", "positive")
    observed["visibility"]["historical_pre_outcome_context"] = True
    assert mod.validate_provenance_record(observed) == ["strict_visibility_value_mismatch"]

    negative = provenance("independent_counterfactual_negative", "negative")
    negative["independently_validated"] = False
    blockers = mod.validate_provenance_record(negative)
    assert blockers == ["counterfactual_negative_independent_validation_missing"]

    assert mod.visibility_for("prospective_pre_outcome_commitment")["historical_pre_outcome_context"] is True
    with pytest.raises(mod.GateError, match="unknown_provenance_type"):
        mod.visibility_for("invented")


@pytest.mark.parametrize(
    ("mutator", "blocker"),
    [
        (lambda row: row["source_validation"].update(content_hash_match=False), "same_source_frozen_pre_state"),
        (lambda row: row.update(ordered_tool_actions=[]), "observed_executed_action"),
        (lambda row: row.update(paired_observations=[]), "bound_observation"),
        (lambda row: row.update(verifier_observations=[]), "completed_relevant_post_edit_verifier"),
        (lambda row: row["transition_local_facts"].update(post_transition_facts=[]), "ordered_post_transition_probe"),
        (lambda row: row["terminal_observation"].update(present=False), "literal_terminal_observation"),
        (lambda row: row.update(edit_evidence={"observed_edits": [], "explicit_no_edit_reason": None}), "patch_trace_or_explicit_no_patch"),
    ],
)
def test_each_substantive_requirement_fails_independently(mutator, blocker: str) -> None:
    row = valid_record()
    mutator(row)
    result = mod.audit_observed_trajectory(row)
    assert result["valid"] is False
    assert blocker in result["substantive_blockers"]


def test_explicit_no_patch_is_valid_and_unknown_verifier_is_not() -> None:
    row = valid_record()
    row["edit_evidence"] = {
        "observed_edits": [],
        "explicit_no_edit_reason": {"reason_code": "no_changes_needed", "evidence_content_sha256": "d" * 64},
    }
    assert mod.audit_observed_trajectory(row)["valid"] is True
    row["verifier_observations"][0]["status"] = "unknown"
    assert "completed_relevant_post_edit_verifier" in mod.audit_observed_trajectory(row)["substantive_blockers"]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda verifier: verifier.update(completed=False),
        lambda verifier: verifier.update(relevant_to_observed_edit=False),
        lambda verifier: verifier.update(observed_order_relative_to_edits="between_edits"),
        lambda verifier: verifier.update(status="running", completed=False),
    ],
)
def test_substantive_verifier_requires_completed_relevant_post_edit_terminal_result(mutation) -> None:
    row = valid_record()
    mutation(row["verifier_observations"][0])
    result = mod.audit_observed_trajectory(row)
    assert "completed_relevant_post_edit_verifier" in result["substantive_blockers"]


@pytest.mark.parametrize("status", ["failed", "passed"])
def test_terminal_task_complete_is_valid_observation_without_normative_stop(status: str) -> None:
    row = valid_record()
    row["verifier_observations"][0]["status"] = status
    result = mod.audit_record(row)
    assert result["observed_trajectory_gate"]["valid"] is True
    terminal = result["observed_trajectory_gate"]["requirements"]["literal_terminal_observation"]
    assert terminal == {
        "passed": True,
        "evidence": {"observed_lifecycle_event": "task_complete"},
    }
    assert result["authority"]["policy_correctness_evaluated"] is False
    assert result["authority"]["positive_stop_target_allowed"] is False
    assert "reviewed_decision" not in json.dumps(result, sort_keys=True)
    assert "stop_complete" not in json.dumps(result, sort_keys=True)


def test_turn_aborted_is_only_a_literal_terminal_observation() -> None:
    row = valid_record()
    row["terminal_observation"]["lifecycle_event"] = "turn_aborted"
    result = mod.audit_record(row)
    assert result["observed_trajectory_gate"]["valid"] is True
    evidence = result["observed_trajectory_gate"]["requirements"]["literal_terminal_observation"]["evidence"]
    assert evidence == {"observed_lifecycle_event": "turn_aborted"}
    assert result["authority"]["positive_stop_target_allowed"] is False
    assert "stop_aborted" not in json.dumps(result, sort_keys=True)


def test_post_transition_probe_does_not_claim_semantic_state_update() -> None:
    result = mod.audit_record(valid_record())
    probe = result["observed_trajectory_gate"]["requirements"]["ordered_post_transition_probe"]
    assert probe["passed"] is True
    assert probe["evidence"]["probe_present"] is True
    assert result["authority"]["semantic_state_update_claim_emitted"] is False
    assert "reviewed_state_update" not in json.dumps(result, sort_keys=True)


def test_audit_only_shape_rejects_policy_targets_but_allows_descriptive_prose() -> None:
    mod.assert_audit_only_shape({"note": "The audit discusses why STOP supervision is prohibited."})
    with pytest.raises(mod.GateError, match="forbidden_policy_target_key:policy_target"):
        mod.assert_audit_only_shape({"policy_target": "continue"})
    with pytest.raises(mod.GateError, match="forbidden_stop_derived_value:stop_complete"):
        mod.assert_audit_only_shape({"literal": "stop_complete"})


def test_execute_is_audit_only_and_deterministic(tmp_path: Path) -> None:
    input_path = tmp_path / "input.jsonl"
    input_path.write_text(json.dumps(valid_record(), sort_keys=True) + "\n", encoding="utf-8")
    out = tmp_path / "out"
    summary_path = tmp_path / "summary.json"
    first = mod.execute(input_path=input_path, out=out, summary_path=summary_path, expected_record_count=1)
    first_bytes = {path.name: path.read_bytes() for path in sorted(out.iterdir())}
    second = mod.execute(input_path=input_path, out=out, summary_path=summary_path, expected_record_count=1)
    second_bytes = {path.name: path.read_bytes() for path in sorted(out.iterdir())}
    assert first == second
    assert first_bytes == second_bytes
    assert first["counts"]["candidate_cardinality_only"] == 1
    assert "ordered_post_transition_probe" not in first["substantive_blocker_counts"]
    assert "literal_terminal_observation" not in first["substantive_blocker_counts"]

    blocked = valid_record()
    blocked["transition_local_facts"]["post_transition_facts"] = []
    blocked["terminal_observation"]["present"] = False
    input_path.write_text(json.dumps(blocked, sort_keys=True) + "\n", encoding="utf-8")
    blocked_summary = mod.execute(
        input_path=input_path,
        out=tmp_path / "blocked-out",
        summary_path=tmp_path / "blocked-summary.json",
        expected_record_count=1,
    )
    assert blocked_summary["substantive_blocker_counts"] == {
        "literal_terminal_observation": 1,
        "ordered_post_transition_probe": 1,
    }
    serialized = json.dumps(first, sort_keys=True)
    for forbidden in mod.FORBIDDEN_OUTPUT_KEYS:
        assert f'"{forbidden}"' not in serialized
    assert set(first_bytes) == {
        "corrected_gate_contract.json",
        "stage12586_corrected_gate_audit.jsonl",
        "summary.json",
    }


def test_current_stage12586_partition_and_artifact_guardrails() -> None:
    rows = mod.read_jsonl(mod.STAGE12586)
    audits = [mod.audit_record(row) for row in rows]
    independently_valid = {
        row["hydration_record_id"]
        for row in rows
        if row["source_identity"].get("same_source_join_validated") is True
        and row["source_validation"].get("content_hash_match") is True
        and row["transition_local_facts"].get("first_transition_line") is not None
        and row["transition_local_facts"].get("pre_transition_facts")
        and row["transition_local_facts"].get("post_transition_facts")
        and row["ordered_tool_actions"]
        and row["paired_observations"]
        and row["verifier_observations"]
        and row["terminal_observation"].get("present") is True
        and (
            row["edit_evidence"].get("observed_edits")
            or row["edit_evidence"].get("explicit_no_edit_reason")
        )
    }
    audited_valid = {
        item["upstream_hydration_record_id"]
        for item in audits
        if item["observed_trajectory_gate"]["valid"] is True
    }
    assert len(audits) == 30
    assert audited_valid == independently_valid
    assert sum(item["blocker_partition"]["substantive_evidence_blocked"] for item in audits) == len(rows) - len(independently_valid)
    assert sum(item["blocker_partition"]["candidate_cardinality_only"] for item in audits) == len(independently_valid)
    assert all(item["authority"]["training_allowed"] is False for item in audits)
    assert all(item["candidate_ranking_listwise_gate"]["distinct_candidate_count"] == 0 for item in audits)
    mod.assert_audit_only_shape(audits)

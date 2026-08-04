#!/usr/bin/env python3
"""Separate observed-trajectory validity from candidate-ranking geometry."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12587_trajectory_vs_ranking_gate_correction"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
STAGE12586 = (
    ROOT
    / "runs/local/artifacts/stage12586_raw_private_observed_window_hydrator"
    / "raw_private_observed_windows.jsonl"
)

PROVENANCE_TYPES = (
    "observed_executed_action",
    "prospective_pre_outcome_commitment",
    "independent_counterfactual_negative",
)
VISIBILITY_SURFACES = (
    "private_audit_evidence",
    "historical_pre_outcome_context",
    "trajectory_model_input",
    "trajectory_supervision_target",
    "ranking_option_input",
    "ranking_negative_role",
    "trajectory_validity_credit",
)
VISIBILITY_MATRIX: dict[str, dict[str, bool]] = {
    "observed_executed_action": {
        "private_audit_evidence": True,
        "historical_pre_outcome_context": False,
        "trajectory_model_input": False,
        "trajectory_supervision_target": True,
        "ranking_option_input": True,
        "ranking_negative_role": False,
        "trajectory_validity_credit": True,
    },
    "prospective_pre_outcome_commitment": {
        "private_audit_evidence": True,
        "historical_pre_outcome_context": True,
        "trajectory_model_input": True,
        "trajectory_supervision_target": False,
        "ranking_option_input": True,
        "ranking_negative_role": False,
        "trajectory_validity_credit": False,
    },
    "independent_counterfactual_negative": {
        "private_audit_evidence": True,
        "historical_pre_outcome_context": False,
        "trajectory_model_input": False,
        "trajectory_supervision_target": False,
        "ranking_option_input": True,
        "ranking_negative_role": True,
        "trajectory_validity_credit": False,
    },
}

MINIMUM_DISTINCT_CANDIDATES = 2
MINIMUM_INDEPENDENT_NEGATIVES = 1
PREFERRED_DISTINCT_CANDIDATES = 5
PREFERRED_INDEPENDENT_NEGATIVES = 3
EXPLICIT_VERIFIER_RESULTS = {"passed", "failed"}
LITERAL_TERMINAL_EVENTS = {"task_complete", "turn_aborted"}

FORBIDDEN_OUTPUT_KEYS = {
    "admission",
    "admissions",
    "admitted_episodes",
    "admitted_training_projections",
    "candidate_actions",
    "model_input",
    "model_inputs",
    "projection",
    "projections",
    "trainer_manifest",
    "trainer_manifests",
    "training_rows",
}
FORBIDDEN_POLICY_TARGET_KEYS = {
    "normative_policy_target",
    "policy_target",
    "reviewed_decision",
    "supervision_target",
    "target_action",
    "target_decision",
}
FORBIDDEN_STOP_DERIVED_VALUES = {"stop_complete", "stop_aborted"}


class GateError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    return f"{prefix}_{stable_hash(parts)[:20]}"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise GateError(f"required_input_missing:{path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GateError(f"malformed_jsonl:{path}:{line_number}") from exc
            if not isinstance(row, dict):
                raise GateError(f"non_object_jsonl_row:{path}:{line_number}")
            rows.append(row)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    os.replace(temporary, path)


def assert_audit_only_shape(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in FORBIDDEN_OUTPUT_KEYS:
                raise GateError(f"forbidden_output_key:{key}")
            if str(key) in FORBIDDEN_POLICY_TARGET_KEYS:
                raise GateError(f"forbidden_policy_target_key:{key}")
            assert_audit_only_shape(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            assert_audit_only_shape(child)
    elif isinstance(value, str) and value in FORBIDDEN_STOP_DERIVED_VALUES:
        raise GateError(f"forbidden_stop_derived_value:{value}")


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _fact_line(fact: Mapping[str, Any]) -> int | None:
    for key in ("line_number", "call_line_number"):
        value = fact.get(key)
        if isinstance(value, int):
            return value
    return None


def visibility_for(provenance_type: str) -> dict[str, bool]:
    if provenance_type not in VISIBILITY_MATRIX:
        raise GateError(f"unknown_provenance_type:{provenance_type}")
    return dict(VISIBILITY_MATRIX[provenance_type])


def validate_provenance_record(record: Mapping[str, Any]) -> list[str]:
    provenance_type = str(record.get("provenance_type") or "")
    if provenance_type not in VISIBILITY_MATRIX:
        return ["provenance_type_unknown"]
    blockers: list[str] = []
    visibility = record.get("visibility")
    if not isinstance(visibility, Mapping):
        blockers.append("strict_visibility_missing")
    elif set(visibility) != set(VISIBILITY_SURFACES):
        blockers.append("strict_visibility_surface_set_mismatch")
    elif any(visibility.get(key) is not expected for key, expected in VISIBILITY_MATRIX[provenance_type].items()):
        blockers.append("strict_visibility_value_mismatch")

    if provenance_type == "observed_executed_action":
        if record.get("same_source_observed") is not True:
            blockers.append("observed_action_same_source_proof_missing")
        if record.get("executed") is not True:
            blockers.append("observed_action_execution_proof_missing")
        if record.get("derived_from_after_diff") is not False:
            blockers.append("observed_action_after_diff_derivation_unknown_or_true")
    elif provenance_type == "prospective_pre_outcome_commitment":
        if record.get("sealed_before_outcome") is not True:
            blockers.append("prospective_commitment_not_sealed_before_outcome")
        if record.get("outcome_visible_at_commitment") is not False:
            blockers.append("prospective_commitment_outcome_visibility_unknown_or_true")
        if record.get("derived_from_after_diff") is not False:
            blockers.append("prospective_commitment_after_diff_derivation_unknown_or_true")
    else:
        if record.get("independently_validated") is not True:
            blockers.append("counterfactual_negative_independent_validation_missing")
        if record.get("derived_from_observed_outcome") is not False:
            blockers.append("counterfactual_negative_outcome_derivation_unknown_or_true")
        if record.get("derived_from_after_diff") is not False:
            blockers.append("counterfactual_negative_after_diff_derivation_unknown_or_true")
        if record.get("same_source_execution_claim") is not False:
            blockers.append("counterfactual_negative_execution_claim_unknown_or_true")
    return sorted(set(blockers))


def corrected_gate_contract() -> dict[str, Any]:
    contract = {
        "stage": STAGE,
        "record_type": "stage12587_corrected_gate_contract_v1",
        "decision": "trajectory_validity_decoupled_from_candidate_ranking_geometry",
        "audit_only": True,
        "authority": {
            "admission_allowed": False,
            "training_allowed": False,
            "projection_allowed": False,
            "trainer_execution_allowed": False,
            "policy_correctness_evaluated": False,
            "positive_stop_target_allowed": False,
            "semantic_state_update_claim_emitted": False,
        },
        "observed_trajectory_gate": {
            "candidate_alternatives_required": False,
            "requirements": [
                "same_source_frozen_pre_state",
                "observed_executed_action",
                "bound_observation",
                "completed_relevant_post_edit_verifier",
                "ordered_post_transition_probe",
                "literal_terminal_observation",
                "patch_trace_or_explicit_no_patch",
            ],
            "post_transition_probe_rule": (
                "The post-transition probe is deterministic and digest-only: at least one same-record post-transition "
                "fact must be ordered after the last transition and, when action-backed, bind to an observed action/output. "
                "This ordering probe does not evaluate policy correctness or claim a semantic state update."
            ),
            "terminal_observation_rule": (
                "task_complete and turn_aborted are retained only as literal observed lifecycle events and never emit "
                "normative STOP supervision."
            ),
            "verifier_result_classes": sorted(EXPLICIT_VERIFIER_RESULTS),
            "verifier_rule": (
                "A substantive verifier must be bound to an observed action/output, completed=true, "
                "relevant_to_observed_edit=true, ordered after the last edit, and terminally passed or failed; "
                "running never qualifies."
            ),
            "not_requirements": [
                "candidate_alternatives",
                "candidate_cardinality",
                "semantic_negative_count",
                "preferred_candidate_geometry",
            ],
        },
        "candidate_ranking_listwise_gate": {
            "separate_from_observed_trajectory_validity": True,
            "minimum_geometry": {
                "distinct_candidates": MINIMUM_DISTINCT_CANDIDATES,
                "independently_validated_semantic_negatives": MINIMUM_INDEPENDENT_NEGATIVES,
            },
            "preferred_full_geometry": {
                "distinct_candidates": PREFERRED_DISTINCT_CANDIDATES,
                "independently_validated_semantic_negatives": PREFERRED_INDEPENDENT_NEGATIVES,
                "short_name": "5/3",
            },
            "minimum_is_loss_applicability_not_trajectory_validity": True,
        },
        "provenance_types": {
            provenance_type: {
                "visibility": visibility_for(provenance_type),
                "trajectory_validity_credit": VISIBILITY_MATRIX[provenance_type]["trajectory_validity_credit"],
            }
            for provenance_type in PROVENANCE_TYPES
        },
        "strict_visibility_rules": [
            "Observed execution is target/audit evidence, never historical pre-outcome context or a negative.",
            "Prospective commitments are visible only when sealed before outcome with outcome and after-diff data absent.",
            "Independent counterfactual negatives may be ranking options only after independent semantic validation and may not claim execution.",
            "Ranking target labels and all observation/verifier/post-transition/outcome fields remain target-side and are not ranking-option inputs.",
            "A post-hoc ranking option may carry observed_executed_action provenance but must never be relabeled as a prospective commitment.",
        ],
        "current_contract_basis": [
            {
                "path": "legacy_src/agentkernel_lite/training_loop.py",
                "fact": "same-role and verifier-value listwise losses skip candidate subsets with fewer than two options",
            },
            {
                "path": "scripts/build_or_run_stage12583_causal_episode_microfactory.py",
                "fact": "the preferred causal candidate geometry is at least five candidates and three semantic hard negatives",
            },
            {
                "path": "runs/local/artifacts/stage12586_raw_private_observed_window_hydrator/raw_private_observed_windows.jsonl",
                "fact": "Stage12586 emits observed digest-bound trajectory evidence and explicitly emits no candidate alternatives",
            },
        ],
    }
    assert_audit_only_shape(contract)
    return contract


def audit_candidate_ranking(candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    provenance_blockers: list[str] = []
    distinct: set[str] = set()
    independent_negatives: set[str] = set()
    for index, candidate in enumerate(candidates):
        identity = str(candidate.get("semantic_identity_sha256") or candidate.get("candidate_id") or "")
        if not identity:
            provenance_blockers.append(f"candidate_identity_missing:{index}")
            continue
        distinct.add(identity)
        blockers = validate_provenance_record(candidate)
        provenance_blockers.extend(f"candidate_{index}:{blocker}" for blocker in blockers)
        if not blockers and candidate.get("provenance_type") == "independent_counterfactual_negative":
            independent_negatives.add(identity)

    minimum_blockers: list[str] = []
    if len(distinct) < MINIMUM_DISTINCT_CANDIDATES:
        minimum_blockers.append("distinct_candidate_count_below_minimum")
    if len(independent_negatives) < MINIMUM_INDEPENDENT_NEGATIVES:
        minimum_blockers.append("independent_counterfactual_negative_count_below_minimum")
    blockers = sorted(set(minimum_blockers + provenance_blockers))
    return {
        "eligible": not blockers,
        "distinct_candidate_count": len(distinct),
        "independently_validated_semantic_negative_count": len(independent_negatives),
        "minimum_geometry": {
            "distinct_candidates": MINIMUM_DISTINCT_CANDIDATES,
            "independently_validated_semantic_negatives": MINIMUM_INDEPENDENT_NEGATIVES,
            "met": not minimum_blockers,
        },
        "preferred_full_geometry": {
            "distinct_candidates": PREFERRED_DISTINCT_CANDIDATES,
            "independently_validated_semantic_negatives": PREFERRED_INDEPENDENT_NEGATIVES,
            "met": (
                len(distinct) >= PREFERRED_DISTINCT_CANDIDATES
                and len(independent_negatives) >= PREFERRED_INDEPENDENT_NEGATIVES
            ),
        },
        "blockers": blockers,
    }


def _requirement(passed: bool, evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {"passed": bool(passed), "evidence": dict(evidence)}


def audit_observed_trajectory(record: Mapping[str, Any]) -> dict[str, Any]:
    source_identity = _dict(record.get("source_identity"))
    source_validation = _dict(record.get("source_validation"))
    transition = _dict(record.get("transition_local_facts"))
    pre_facts = [item for item in _list(transition.get("pre_transition_facts")) if isinstance(item, dict)]
    post_facts = [item for item in _list(transition.get("post_transition_facts")) if isinstance(item, dict)]
    first_transition = transition.get("first_transition_line")
    last_transition = transition.get("last_transition_line")

    frozen_pre_state = bool(
        source_identity.get("same_source_join_validated") is True
        and source_validation.get("content_hash_match") is True
        and isinstance(first_transition, int)
        and pre_facts
        and all((_fact_line(fact) or first_transition) < first_transition for fact in pre_facts)
    )

    actions = [item for item in _list(record.get("ordered_tool_actions")) if isinstance(item, dict)]
    action_ids = [str(item.get("action_id") or "") for item in actions]
    action_lines = [item.get("call_line_number") for item in actions]
    executed_action = bool(
        actions
        and all(action_ids)
        and len(set(action_ids)) == len(action_ids)
        and all(item.get("authoritative_pair_present") is True for item in actions)
        and all(isinstance(line, int) for line in action_lines)
        and action_lines == sorted(action_lines)
    )

    observations = [item for item in _list(record.get("paired_observations")) if isinstance(item, dict)]
    observation_action_ids = [str(item.get("action_id") or "") for item in observations]
    bound_observation = bool(
        observations
        and all(observation_action_ids)
        and len(set(observation_action_ids)) == len(observation_action_ids)
        and set(observation_action_ids) == set(action_ids)
        and all(isinstance(item.get("output_line_number"), int) for item in observations)
    )

    action_id_set = set(action_ids)
    observation_id_set = set(observation_action_ids)
    verifiers = [item for item in _list(record.get("verifier_observations")) if isinstance(item, dict)]
    bound_verifiers = [
        item
        for item in verifiers
        if str(item.get("action_id") or "") in action_id_set & observation_id_set
        and isinstance(item.get("command_sha256"), str)
        and len(str(item.get("command_sha256"))) == 64
        and item.get("completed") is True
        and item.get("relevant_to_observed_edit") is True
        and item.get("observed_order_relative_to_edits") == "after_last_edit"
        and item.get("status") in EXPLICIT_VERIFIER_RESULTS
        and isinstance(item.get("output_line_number"), int)
    ]
    verifier_binding = bool(bound_verifiers)

    valid_post_facts: list[dict[str, Any]] = []
    if isinstance(last_transition, int):
        for fact in post_facts:
            line = _fact_line(fact)
            if line is None or line <= last_transition:
                continue
            action_id = str(fact.get("action_id") or "")
            if action_id:
                if action_id not in action_id_set & observation_id_set or fact.get("status") == "unknown":
                    continue
            elif not isinstance(fact.get("payload_sha256"), str):
                continue
            valid_post_facts.append(fact)
    ordered_post_transition_probe = bool(valid_post_facts)

    terminal = _dict(record.get("terminal_observation"))
    lifecycle = str(terminal.get("lifecycle_event") or "")
    literal_terminal_observation = bool(
        terminal.get("present") is True and lifecycle in LITERAL_TERMINAL_EVENTS
    )

    edits = [item for item in _list(_dict(record.get("edit_evidence")).get("observed_edits")) if isinstance(item, dict)]
    no_edit = _dict(_dict(record.get("edit_evidence")).get("explicit_no_edit_reason"))
    patch_trace = bool(
        edits
        and all(
            item.get("payload_observed") is True
            and isinstance(item.get("payload_sha256"), str)
            and len(str(item.get("payload_sha256"))) == 64
            for item in edits
        )
    )
    explicit_no_patch = bool(
        not edits
        and no_edit.get("reason_code")
        and isinstance(no_edit.get("evidence_content_sha256"), str)
        and len(str(no_edit.get("evidence_content_sha256"))) == 64
    )

    requirements = {
        "same_source_frozen_pre_state": _requirement(
            frozen_pre_state,
            {
                "same_source_join_validated": source_identity.get("same_source_join_validated") is True,
                "immutable_content_hash_validated": source_validation.get("content_hash_match") is True,
                "pre_transition_fact_count": len(pre_facts),
                "first_transition_line": first_transition,
            },
        ),
        "observed_executed_action": _requirement(
            executed_action,
            {"action_count": len(actions), "all_authoritatively_paired": all(item.get("authoritative_pair_present") is True for item in actions)},
        ),
        "bound_observation": _requirement(
            bound_observation,
            {"observation_count": len(observations), "covers_all_observed_actions": set(observation_action_ids) == set(action_ids)},
        ),
        "completed_relevant_post_edit_verifier": _requirement(
            verifier_binding,
            {
                "verifier_observation_count": len(verifiers),
                "completed_relevant_post_edit_result_count": len(bound_verifiers),
                "result_status_counts": dict(sorted(Counter(str(item.get("status")) for item in bound_verifiers).items())),
            },
        ),
        "ordered_post_transition_probe": _requirement(
            ordered_post_transition_probe,
            {
                "probe_present": ordered_post_transition_probe,
                "ordered_bound_post_transition_fact_count": len(valid_post_facts),
                "last_transition_line": last_transition,
            },
        ),
        "literal_terminal_observation": _requirement(
            literal_terminal_observation,
            {"observed_lifecycle_event": lifecycle or None},
        ),
        "patch_trace_or_explicit_no_patch": _requirement(
            patch_trace or explicit_no_patch,
            {
                "observed_patch_trace_count": len(edits) if patch_trace else 0,
                "explicit_no_patch": explicit_no_patch,
                "no_patch_reason_code": no_edit.get("reason_code") if explicit_no_patch else None,
            },
        ),
    }
    blockers = sorted(key for key, value in requirements.items() if value["passed"] is not True)
    return {
        "valid": not blockers,
        "candidate_alternatives_required": False,
        "requirements": requirements,
        "substantive_blockers": blockers,
    }


def audit_record(record: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    trajectory = audit_observed_trajectory(record)
    ranking = audit_candidate_ranking(candidates)
    substantive = not trajectory["valid"]
    geometry_only = bool(trajectory["valid"] and not ranking["eligible"])
    if substantive:
        classification = "substantive_evidence_blocked"
    elif geometry_only:
        classification = "candidate_cardinality_only"
    else:
        classification = "both_gates_satisfied"
    hydration_id = str(record.get("hydration_record_id") or "")
    result = {
        "audit_record_id": stable_id("stage12587_audit", hydration_id),
        "record_type": "stage12587_stage12586_corrected_gate_audit_v1",
        "upstream_hydration_record_id": hydration_id,
        "upstream_candidate_id": record.get("upstream_candidate_id"),
        "audit_scope": "stage12586_digest_only_no_private_payload_reopen",
        "observed_trajectory_gate": trajectory,
        "candidate_ranking_listwise_gate": ranking,
        "blocker_partition": {
            "classification": classification,
            "substantive_evidence_blocked": substantive,
            "candidate_cardinality_only": geometry_only,
        },
        "authority": {
            "admission_allowed": False,
            "training_allowed": False,
            "projection_allowed": False,
            "policy_correctness_evaluated": False,
            "positive_stop_target_allowed": False,
            "semantic_state_update_claim_emitted": False,
        },
    }
    assert_audit_only_shape(result)
    return result


def execute(
    *,
    input_path: Path = STAGE12586,
    out: Path = OUT,
    summary_path: Path = SUMMARY,
    expected_record_count: int | None = 30,
) -> dict[str, Any]:
    rows = read_jsonl(input_path)
    if expected_record_count is not None and len(rows) != expected_record_count:
        raise GateError(f"stage12586_record_count_mismatch:{len(rows)}:{expected_record_count}")
    hydration_ids = [str(row.get("hydration_record_id") or "") for row in rows]
    if not all(hydration_ids) or len(set(hydration_ids)) != len(hydration_ids):
        raise GateError("stage12586_hydration_identity_missing_or_duplicate")

    contract = corrected_gate_contract()
    audits = [audit_record(row) for row in sorted(rows, key=lambda item: str(item.get("hydration_record_id") or ""))]
    partition_counts = Counter(item["blocker_partition"]["classification"] for item in audits)
    substantive_blockers = Counter(
        blocker
        for item in audits
        for blocker in item["observed_trajectory_gate"]["substantive_blockers"]
    )
    ranking_blockers = Counter(
        blocker
        for item in audits
        for blocker in item["candidate_ranking_listwise_gate"]["blockers"]
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12587_trajectory_vs_ranking_gate_correction_summary_v1",
        "status": "AUDIT_ONLY_CORRECTED_GATE_APPLIED",
        "decision": "trajectory_gate_corrected_candidate_geometry_remains_separate",
        "claim_boundary": (
            "Digest-only audit of Stage12586 records. Candidate absence does not invalidate an observed trajectory. "
            "No private payloads were reopened and no admissions, training rows, projections, or trainer execution were produced."
        ),
        "counts": {
            "stage12586_records_audited": len(audits),
            "observed_trajectory_valid": sum(item["observed_trajectory_gate"]["valid"] for item in audits),
            "substantive_evidence_blocked": partition_counts["substantive_evidence_blocked"],
            "candidate_cardinality_only": partition_counts["candidate_cardinality_only"],
            "both_gates_satisfied": partition_counts["both_gates_satisfied"],
            "candidate_ranking_minimum_eligible": sum(item["candidate_ranking_listwise_gate"]["eligible"] for item in audits),
            "preferred_5_3_geometry_met": sum(item["candidate_ranking_listwise_gate"]["preferred_full_geometry"]["met"] for item in audits),
        },
        "substantive_blocker_counts": dict(sorted(substantive_blockers.items())),
        "candidate_ranking_blocker_counts": dict(sorted(ranking_blockers.items())),
        "gate_contract": {
            "observed_trajectory_requires_candidate_alternatives": False,
            "ranking_minimum": "2 distinct candidates / 1 independently validated semantic negative",
            "preferred_full_geometry": "5 distinct candidates / 3 independently validated semantic negatives",
            "provenance_types": list(PROVENANCE_TYPES),
        },
        "input": {
            "path": str(input_path.relative_to(ROOT)) if input_path.is_relative_to(ROOT) else str(input_path),
            "sha256": file_sha256(input_path),
        },
        "artifacts": {
            "corrected_gate_contract": "corrected_gate_contract.json",
            "stage12586_audit_records": "stage12586_corrected_gate_audit.jsonl",
            "summary": "summary.json",
        },
        "execution_contract": {
            "conda_environment": "ai",
            "cpu_only": True,
            "private_payloads_reopened": False,
            "candidate_alternatives_emitted": False,
            "admission_allowed": False,
            "training_allowed": False,
            "projection_allowed": False,
            "trainer_execution_allowed": False,
            "policy_correctness_evaluated": False,
            "positive_stop_target_allowed": False,
            "semantic_state_update_claim_emitted": False,
        },
    }
    assert_audit_only_shape(summary)
    write_json(out / "corrected_gate_contract.json", contract)
    write_jsonl(out / "stage12586_corrected_gate_audit.jsonl", audits)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage12586-records", type=Path, default=STAGE12586)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    parser.add_argument("--expected-record-count", type=int, default=30)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = execute(
        input_path=args.stage12586_records,
        out=args.out,
        summary_path=args.summary,
        expected_record_count=args.expected_record_count,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

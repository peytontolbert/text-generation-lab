#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12308_h1_semantic_rule_feasibility_audit"
INPUT = (
    ROOT
    / "runs/local/artifacts/stage12303_semantic_transition_function_reconstruction/"
    / "semantic_transition_reconstruction_work_items.jsonl"
)
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STATE_CODES = [
    "source_evidence_present",
    "failure_localized",
    "patch_exists",
    "verifier_selected",
    "verifier_run_status",
    "requirement_covered",
    "env_blocked",
    "open_question",
]

# Conservative reconstruction of the Stage12302 H1 semantic vocabulary as a
# deterministic pre-action state-code rule table. Matching requires explicit
# code values in the item; refs/digests never satisfy a predicate.
TF_H1_RULES = [
    {
        "rule_id": "TF-H1-001",
        "semantic_action": "RETRIEVE_EVIDENCE",
        "requires": {"source_evidence_present": False, "env_blocked": False},
    },
    {
        "rule_id": "TF-H1-002",
        "semantic_action": "LOCALIZE_FAILURE",
        "requires": {"source_evidence_present": True, "failure_localized": False},
    },
    {
        "rule_id": "TF-H1-003",
        "semantic_action": "PLAN_PATCH",
        "requires": {"failure_localized": True, "patch_exists": False, "env_blocked": False},
    },
    {
        "rule_id": "TF-H1-004",
        "semantic_action": "APPLY_PATCH",
        "requires": {"patch_exists": True, "env_blocked": False},
    },
    {
        "rule_id": "TF-H1-005",
        "semantic_action": "SELECT_TEST",
        "requires": {"patch_exists": True, "verifier_selected": False, "env_blocked": False},
    },
    {
        "rule_id": "TF-H1-006",
        "semantic_action": "RUN_VERIFIER",
        "requires": {
            "patch_exists": True,
            "verifier_selected": True,
            "verifier_run_status": "not_run",
            "env_blocked": False,
        },
    },
    {
        "rule_id": "TF-H1-007",
        "semantic_action": "INTERPRET_VERIFIER",
        "requires": {"verifier_run_status": ["passed", "failed"]},
    },
    {
        "rule_id": "TF-H1-008",
        "semantic_action": "REPAIR_AFTER_FAILURE",
        "requires": {"verifier_run_status": "failed", "requirement_covered": False},
    },
    {
        "rule_id": "TF-H1-009",
        "semantic_action": "ROLLBACK_OR_ABSTAIN",
        "requires": {"env_blocked": True},
    },
    {
        "rule_id": "TF-H1-010",
        "semantic_action": "FINISH",
        "requires": {"verifier_run_status": "passed", "requirement_covered": True, "open_question": False},
    },
]


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if line:
                row = json.loads(line)
                row["_input_line_number"] = line_number
                yield row


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> int:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)


def explicit_state_codes(item: dict[str, Any]) -> dict[str, Any]:
    """Extract only concrete pre-action state-code values, never refs/digests."""

    candidates = [
        item.get("pre_action_state_codes"),
        item.get("state_codes"),
        item.get("state_code_evidence"),
        (item.get("pre_action_fields") or {}).get("state_codes"),
        (item.get("pre_action_fields") or {}).get("state_before_codes"),
    ]
    found: dict[str, Any] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        for code in STATE_CODES:
            if code in candidate and not isinstance(candidate[code], (dict, list)):
                found[code] = candidate[code]
    return found


def value_matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return actual in expected
    return actual == expected


def rule_missing_codes(rule: dict[str, Any], state: dict[str, Any]) -> list[str]:
    return [code for code in rule["requires"] if code not in state]


def matching_rules(state: dict[str, Any]) -> list[dict[str, Any]]:
    matches = []
    for rule in TF_H1_RULES:
        required = rule["requires"]
        if all(code in state and value_matches(state[code], expected) for code, expected in required.items()):
            matches.append(rule)
    return matches


def audit_item(item: dict[str, Any]) -> dict[str, Any]:
    state = explicit_state_codes(item)
    matches = matching_rules(state)
    required_codes = (item.get("semantic_reconstruction_needed") or {}).get("required_state_codes") or STATE_CODES
    missing_state_codes = sorted(code for code in required_codes if code not in state)
    candidate_count = (item.get("candidate_set_audit") or {}).get("candidate_count")

    hard_reject_reasons = []
    if not state:
        hard_reject_reasons.append("pre_action_state_codes_absent_only_refs_available")
    if missing_state_codes:
        hard_reject_reasons.append("required_pre_action_state_codes_missing")
    if len(matches) == 0:
        hard_reject_reasons.append("no_tf_h1_rule_matches_explicit_state")
    if len(matches) > 1:
        hard_reject_reasons.append("multiple_tf_h1_rules_match_state_not_deterministic")
    if candidate_count is None or candidate_count < 3:
        hard_reject_reasons.append("candidate_count_below_training_floor")

    train_support_allowed = len(matches) == 1 and not hard_reject_reasons
    if not train_support_allowed:
        hard_reject_reasons.append("training_disallowed_fail_closed")

    return {
        "schema_version": "stage12308_h1_semantic_rule_feasibility_record_v1",
        "stage": STAGE,
        "input_line_number": item.get("_input_line_number"),
        "work_item_id": item.get("work_item_id"),
        "source_transition_id": item.get("source_transition_id"),
        "source_horizon_slice_id": item.get("source_horizon_slice_id"),
        "language_family": item.get("language_family"),
        "repo_family_label": item.get("repo_family_label"),
        "repo_family_digest": item.get("repo_family_digest"),
        "candidate_count": candidate_count,
        "possible_rule_ids": [rule["rule_id"] for rule in matches],
        "possible_semantic_actions": [rule["semantic_action"] for rule in matches],
        "missing_state_codes": missing_state_codes,
        "explicit_state_codes_present": sorted(state),
        "hard_reject_reasons": sorted(set(hard_reject_reasons)),
        "raw_action_ignored_for_assignment": True,
        "raw_action_fields_seen_but_not_used": sorted(
            key
            for key in (item.get("candidate_set_audit") or {})
            if key.startswith("raw_")
        ),
        "admission": {
            "candidate_only": True,
            "training_allowed": train_support_allowed,
            "train_support_allowed": train_support_allowed,
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
        },
        "claim_boundary": (
            "Rule feasibility is assigned only from explicit deterministic pre-action state-code "
            "values. State refs, observed raw actions, target observations, and state updates are "
            "not admissible evidence."
        ),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    items = list(iter_jsonl(INPUT) or [])
    records = [audit_item(item) for item in items]
    write_jsonl(OUT / "h1_semantic_rule_feasibility_records.jsonl", records)

    reason_counts: Counter[str] = Counter()
    missing_code_counts: Counter[str] = Counter()
    possible_rule_counts: Counter[str] = Counter()
    for record in records:
        reason_counts.update(record["hard_reject_reasons"])
        missing_code_counts.update(record["missing_state_codes"])
        possible_rule_counts.update(record["possible_rule_ids"])

    admitted_records = [record for record in records if record["admission"]["training_allowed"]]
    summary = {
        "stage": STAGE,
        "decision": "blocked_no_deterministic_h1_semantic_rule_assignments",
        "input": str(INPUT.relative_to(ROOT)),
        "work_items_inspected": len(items),
        "feasibility_records": len(records),
        "records_with_possible_rule": sum(1 for record in records if record["possible_rule_ids"]),
        "records_with_deterministic_single_rule": sum(1 for record in records if len(record["possible_rule_ids"]) == 1),
        "records_training_allowed": len(admitted_records),
        "training_rows_emitted": 0,
        "training_allowed": False,
        "strict_eval_eligible": 0,
        "source_heldout_admissible": 0,
        "language_counts": dict(Counter(record["language_family"] for record in records)),
        "repo_family_counts": dict(Counter(record["repo_family_label"] for record in records)),
        "candidate_count_counts": dict(Counter(str(record["candidate_count"]) for record in records)),
        "possible_rule_id_counts": dict(possible_rule_counts),
        "missing_state_code_counts": dict(missing_code_counts),
        "hard_reject_reason_counts": dict(reason_counts),
        "tf_h1_rule_table": TF_H1_RULES,
        "rule_assignment_policy": {
            "observed_raw_action_used": False,
            "target_only_refs_used": False,
            "state_refs_count_as_evidence": False,
            "requires_explicit_pre_action_state_codes": True,
            "fail_closed_default_training_allowed": False,
        },
        "claim_boundary": (
            "Stage12308 emits audit records only. No training row is admitted unless a work item "
            "contains explicit deterministic pre-action state-code evidence that selects exactly "
            "one TF-H1 rule without using observed raw action."
        ),
    }
    (OUT / "h1_semantic_rule_feasibility_audit.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "H1_SEMANTIC_RULE_FEASIBILITY_AUDIT_STAGE12308.md").write_text(
        "# Stage12308 H1 Semantic Rule Feasibility Audit\n\n"
        "No training rows emitted. Rule assignment fails closed unless explicit pre-action "
        "state-code evidence selects exactly one TF-H1 rule.\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

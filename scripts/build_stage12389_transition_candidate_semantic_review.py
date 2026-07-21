#!/usr/bin/env python3
"""Stage12389 fail-closed semantic review for Stage12388 candidates.

Audit-only stage. It reads Stage12388 recovery records and writes reviewed
records plus counts. It never emits training rows.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12389_transition_candidate_semantic_review"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12388_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12388_transition_local_candidate_recovery/transition_local_candidate_recovery_records.jsonl"
)
STAGE12388_SUMMARY = ROOT / "runs/summaries/stage12388_transition_local_candidate_recovery.json"

SELF_REPO_FAMILIES = {"agentkernel-seq2seq-text-lab"}
GENERIC_REPO_LABELS = {"", "unknown", "clone", "repo", "src", "worktree"}

RULES = {
    "GLOBAL_NO_TRAINING": "STAGE12389_GLOBAL_NO_TRAINING_ALLOWED",
    "ROW_NO_TRAINING": "STAGE12389_ROW_TRAINING_ALLOWED_FALSE",
    "STRICT_SOURCE_HELDOUT": "STAGE12389_STRICT_OR_SOURCE_HELDOUT_NEVER_ADMIT",
    "MIXED_PATCH_REJECT": "STAGE12389_MIXED_PATCH_STATUS_REPAIR_TRANSITION_REJECT",
    "PATCH_FAILED_REJECT": "STAGE12389_PATCH_FAILED_REPAIR_TRANSITION_REJECT",
    "VERIFIER_NONPASS_REJECT": "STAGE12389_VERIFIER_NONPASS_REPAIR_TRANSITION_REJECT",
    "REPO_IDENTITY_REVIEW": "STAGE12389_REPO_IDENTITY_SEMANTIC_REVIEW_REQUIRED",
    "POLICY_LABEL_REVIEW": "STAGE12389_POLICY_LABEL_REVIEW_REQUIRED",
    "VERIFIER_RELEVANCE_REVIEW": "STAGE12389_VERIFIER_RELEVANCE_REVIEW_REQUIRED",
    "STATE_DELTA_REVIEW": "STAGE12389_STATE_DELTA_REVIEW_REQUIRED",
    "SELF_REPO_SCALE_BLOCK": "STAGE12389_SELF_REPO_DOMINATED_SCALE_CLAIM_BLOCK",
    "LEVEL3_CONTRACT_BLOCK": "STAGE12389_LEVEL3_CONTROL_CONTRACT_STILL_BLOCKED",
}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def stable_id(prefix: str, *parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def dig(row: dict[str, Any], *path: str) -> Any:
    value: Any = row
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def review_repo_identity(row: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    identity = row.get("identity_recovery") if isinstance(row.get("identity_recovery"), dict) else {}
    repo = str(identity.get("repo_family_candidate") or "")
    confidence = str(identity.get("repo_family_confidence") or "")
    root_id = identity.get("root_id_candidate")
    language = identity.get("language_candidate")
    blockers: list[str] = []
    rules = [RULES["REPO_IDENTITY_REVIEW"]]

    if not root_id or not language or not repo:
        status = "failed_missing_repo_root_or_language"
        blockers.append("repo_identity_missing_required_component")
    elif repo in GENERIC_REPO_LABELS or confidence != "basename_hint":
        status = "manual_required_low_confidence_repo_identity"
        blockers.append("repo_identity_semantic_review_required")
    else:
        status = "metadata_present_review_required"
        blockers.append("repo_identity_semantic_review_required")

    if repo in SELF_REPO_FAMILIES:
        rules.append(RULES["SELF_REPO_SCALE_BLOCK"])
        blockers.append("self_repo_dominated_scale_claim_blocked")

    return (
        {
            "status": status,
            "repo_family_candidate": repo or None,
            "repo_family_confidence": confidence or None,
            "root_id_candidate_present": bool(root_id),
            "language_candidate_present": bool(language),
            "self_repo_family": repo in SELF_REPO_FAMILIES,
            "raw_path_or_source_text_emitted": False,
        },
        blockers,
        rules,
    )


def review_policy_label(row: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    blockers = set(row.get("blocked_reasons") or [])
    if "policy_label_not_admitted" in blockers or "observed_action_only_not_policy_gold" in blockers:
        status = "blocked_observed_action_is_not_policy_gold"
        remaining = ["policy_label_not_admitted", "observed_action_only_not_policy_gold"]
    else:
        status = "manual_required_policy_label_not_proven"
        remaining = ["policy_label_semantic_review_required"]
    return (
        {
            "status": status,
            "chosen_action_policy_gold_proven": False,
            "observed_action_order_only": "observed_action_only_not_policy_gold" in blockers,
            "raw_command_text_emitted": False,
        },
        remaining,
        [RULES["POLICY_LABEL_REVIEW"]],
    )


def review_verifier(row: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    transition = row.get("transition_recovery") if isinstance(row.get("transition_recovery"), dict) else {}
    command = transition.get("command_result_candidate") if isinstance(transition.get("command_result_candidate"), dict) else {}
    verifier = transition.get("verifier_transition_candidate") if isinstance(transition.get("verifier_transition_candidate"), dict) else {}
    verifier_status = str(verifier.get("verifier_status_class") or "")
    verifier_count = int(command.get("verifier_event_count") or 0)
    blockers: list[str] = []
    rules = [RULES["VERIFIER_RELEVANCE_REVIEW"]]

    if verifier_status == "VERIFIER_PASS_OBSERVED" and verifier_count > 0:
        status = "metadata_present_manual_relevance_review_required"
        blockers.append("verifier_relevance_semantic_review_required")
    elif verifier_status:
        status = "failed_verifier_status_not_pass"
        blockers.append("verifier_status_not_training_grade")
        rules.append(RULES["VERIFIER_NONPASS_REJECT"])
    else:
        status = "failed_verifier_status_missing"
        blockers.append("verifier_status_missing")
        rules.append(RULES["VERIFIER_NONPASS_REJECT"])

    return (
        {
            "status": status,
            "verifier_status_class": verifier_status or None,
            "verifier_event_count": verifier_count,
            "verifier_relevance_proven": False,
            "raw_command_text_emitted": False,
            "raw_tool_output_emitted": False,
        },
        blockers,
        rules,
    )


def review_state_delta(row: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    transition = row.get("transition_recovery") if isinstance(row.get("transition_recovery"), dict) else {}
    state = transition.get("state_update_candidate") if isinstance(transition.get("state_update_candidate"), dict) else {}
    codes = state.get("state_update_codes") if isinstance(state.get("state_update_codes"), list) else []
    if codes:
        status = "metadata_present_manual_delta_review_required"
        blockers = ["state_delta_semantic_review_required"]
    else:
        status = "failed_state_delta_missing"
        blockers = ["state_delta_missing"]
    return (
        {
            "status": status,
            "state_update_codes": sorted(str(code) for code in codes),
            "state_delta_semantics_proven": False,
            "raw_patch_body_emitted": False,
            "raw_source_text_emitted": False,
        },
        blockers,
        [RULES["STATE_DELTA_REVIEW"]],
    )


def transition_hard_rule_review(row: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str], bool]:
    boundary = row.get("review_boundary") if isinstance(row.get("review_boundary"), dict) else {}
    transition = row.get("transition_recovery") if isinstance(row.get("transition_recovery"), dict) else {}
    verifier = transition.get("verifier_transition_candidate") if isinstance(transition.get("verifier_transition_candidate"), dict) else {}
    patch_status = str(verifier.get("patch_apply_status") or "")
    verifier_status = str(verifier.get("verifier_status_class") or "")
    candidate = str(verifier.get("candidate_label") or "")
    blockers: list[str] = []
    rules = [RULES["STRICT_SOURCE_HELDOUT"]]
    hard_reject = False

    if boundary.get("strict_eval_eligible") or boundary.get("source_heldout_admissible"):
        hard_reject = True
        blockers.append("strict_or_source_heldout_candidate_rejected")
    if patch_status == "MIXED_PATCH_APPLIED_AND_FAILED":
        hard_reject = True
        blockers.append("mixed_patch_status_repair_transition_rejected")
        rules.append(RULES["MIXED_PATCH_REJECT"])
    if patch_status == "PATCH_FAILED":
        hard_reject = True
        blockers.append("patch_failed_repair_transition_rejected")
        rules.append(RULES["PATCH_FAILED_REJECT"])
    if verifier_status != "VERIFIER_PASS_OBSERVED":
        hard_reject = True
        blockers.append("verifier_nonpass_repair_transition_rejected")
        rules.append(RULES["VERIFIER_NONPASS_REJECT"])

    return (
        {
            "transition_candidate": candidate or None,
            "patch_apply_status": patch_status or None,
            "verifier_status_class": verifier_status or None,
            "strict_eval_eligible_input": bool(boundary.get("strict_eval_eligible")),
            "source_heldout_admissible_input": bool(boundary.get("source_heldout_admissible")),
            "hard_reject_for_stage12390": hard_reject,
        },
        blockers,
        rules,
        hard_reject,
    )


def next_actions(recommendation: str, blockers: list[str]) -> list[str]:
    actions = ["do_not_emit_training_rows", "preserve_training_allowed_false"]
    if recommendation == "rejected_for_stage12390":
        actions.append("exclude_from_stage12390_repair_transition_materialization")
    elif recommendation == "needs_manual_review":
        actions.append("build_manual_semantic_review_packet_before_stage12390")
        if "repo_identity_semantic_review_required" in blockers:
            actions.append("manual_repo_identity_review")
        if "policy_label_not_admitted" in blockers or "observed_action_only_not_policy_gold" in blockers:
            actions.append("manual_policy_label_review")
        if "verifier_relevance_semantic_review_required" in blockers:
            actions.append("manual_verifier_relevance_review")
        if "state_delta_semantic_review_required" in blockers:
            actions.append("manual_state_delta_review")
    else:
        actions.append("materialize_level3_candidate_after_review_with_training_gate_closed")
    return sorted(dict.fromkeys(actions))


def review_row(row: dict[str, Any]) -> dict[str, Any]:
    transition_review, transition_blockers, transition_rules, hard_reject = transition_hard_rule_review(row)
    repo_review, repo_blockers, repo_rules = review_repo_identity(row)
    policy_review, policy_blockers, policy_rules = review_policy_label(row)
    verifier_review, verifier_blockers, verifier_rules = review_verifier(row)
    state_review, state_blockers, state_rules = review_state_delta(row)

    remaining = sorted(
        set(row.get("blocked_reasons") or [])
        | set(transition_blockers)
        | set(repo_blockers)
        | set(policy_blockers)
        | set(verifier_blockers)
        | set(state_blockers)
        | {"level3_control_contract_missing"}
    )
    rules = sorted(
        set(
            [RULES["GLOBAL_NO_TRAINING"], RULES["ROW_NO_TRAINING"], RULES["LEVEL3_CONTRACT_BLOCK"]]
            + transition_rules
            + repo_rules
            + policy_rules
            + verifier_rules
            + state_rules
        )
    )

    if hard_reject:
        recommendation = "rejected_for_stage12390"
        review_status = "reviewed_rejected"
        review_status_class = "hard_rule_rejected"
    elif remaining:
        recommendation = "needs_manual_review"
        review_status = "reviewed_blocked"
        review_status_class = "manual_semantic_review_required"
    else:
        recommendation = "level3_candidate_after_review"
        review_status = "reviewed_candidate"
        review_status_class = "level3_candidate_after_review_nontraining"

    materialization_actions = next_actions(recommendation, remaining)
    identity = row.get("identity_recovery") if isinstance(row.get("identity_recovery"), dict) else {}
    return {
        "stage": STAGE,
        "semantic_review_record_id": stable_id("stage12389", row.get("recovery_record_id")),
        "source_recovery_record_id": row.get("recovery_record_id"),
        "source_stage12316_id": row.get("source_stage12316_id"),
        "source_join_record_id": row.get("source_join_record_id"),
        "task_window_id": row.get("task_window_id"),
        "repo_family": identity.get("repo_family_candidate") or "missing",
        "transition_candidate": transition_review["transition_candidate"] or "missing",
        "review_status": review_status,
        "review_status_class": review_status_class,
        "rule_ids": rules,
        "semantic_reviews": {
            "transition_hard_rules": transition_review,
            "repo_identity_review": repo_review,
            "policy_label_review": policy_review,
            "verifier_relevance_review": verifier_review,
            "state_delta_review": state_review,
        },
        "remaining_blockers": remaining,
        "recommendation": recommendation,
        "next_materialization_actions": materialization_actions,
        "admission": {
            "training_allowed": False,
            "train_support_allowed": False,
            "level3_admitted": False,
            "patch_trace_admitted": False,
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
            "repair_transition_admitted_for_stage12390": False,
            "scale_progress_claim_allowed": False,
            "new_training_row_emitted": False,
        },
        "raw_visibility": {
            "raw_source_path_emitted": False,
            "raw_cwd_path_emitted": False,
            "raw_workspace_path_emitted": False,
            "raw_command_text_emitted": False,
            "raw_tool_output_emitted": False,
            "raw_patch_body_emitted": False,
            "raw_source_text_emitted": False,
        },
    }


def nested_counts(rows: list[dict[str, Any]], group_key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(group_key) or "missing")].append(row)
    out: dict[str, Any] = {}
    for key, group in sorted(grouped.items()):
        out[key] = {
            "total": len(group),
            "recommendation_counts": dict(Counter(str(row["recommendation"]) for row in group)),
            "review_status_counts": dict(Counter(str(row["review_status"]) for row in group)),
            "review_status_class_counts": dict(Counter(str(row["review_status_class"]) for row in group)),
        }
    return out


def write_markdown(summary: dict[str, Any]) -> None:
    lines = [
        "# Stage12389 Transition Candidate Semantic Review",
        "",
        "Fail-closed semantic review audit only. No training rows are emitted.",
        "",
        f"Records reviewed: {summary['records_reviewed']}",
        f"Decision: `{summary['decision']}`",
        f"Training allowed: `{summary['training_allowed']}`",
        "",
        "## Recommendations",
        "",
    ]
    for key, count in sorted(summary["recommendation_counts"].items()):
        lines.append(f"- `{key}`: {count}")
    lines.extend(
        [
            "",
            "## Hard Rule Effects",
            "",
            f"- Mixed patch-status rows rejected for Stage12390: {summary['hard_rule_counts'].get('mixed_patch_status_repair_transition_rejected', 0)}",
            f"- Patch-failed rows rejected for Stage12390: {summary['hard_rule_counts'].get('patch_failed_repair_transition_rejected', 0)}",
            f"- Verifier non-pass rows rejected for Stage12390: {summary['hard_rule_counts'].get('verifier_nonpass_repair_transition_rejected', 0)}",
            f"- Self-repo scale-claim blocked rows: {summary['hard_rule_counts'].get('self_repo_dominated_scale_claim_blocked', 0)}",
            "",
            "Rows requiring manual review must resolve repo identity, policy label, verifier relevance, and state delta semantics before any later materializer may reconsider them.",
        ]
    )
    (OUT / "TRANSITION_CANDIDATE_SEMANTIC_REVIEW_STAGE12389.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    source_rows = read_jsonl(STAGE12388_RECORDS)
    source_summary = read_json(STAGE12388_SUMMARY)
    reviewed = [review_row(row) for row in source_rows]

    recommendation_counts = Counter(str(row["recommendation"]) for row in reviewed)
    review_status_counts = Counter(str(row["review_status"]) for row in reviewed)
    review_status_class_counts = Counter(str(row["review_status_class"]) for row in reviewed)
    remaining_blocker_counts: Counter[str] = Counter()
    rule_id_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    hard_rule_counts: Counter[str] = Counter()
    for row in reviewed:
        remaining_blocker_counts.update(row["remaining_blockers"])
        rule_id_counts.update(row["rule_ids"])
        action_counts.update(row["next_materialization_actions"])
        for blocker in row["remaining_blockers"]:
            if blocker in {
                "mixed_patch_status_repair_transition_rejected",
                "patch_failed_repair_transition_rejected",
                "verifier_nonpass_repair_transition_rejected",
                "self_repo_dominated_scale_claim_blocked",
                "strict_or_source_heldout_candidate_rejected",
            }:
                hard_rule_counts[blocker] += 1

    counts_by_transition = nested_counts(reviewed, "transition_candidate")
    counts_by_repo = nested_counts(reviewed, "repo_family")
    next_actions_payload = {
        "stage": STAGE,
        "training_allowed": False,
        "action_counts": dict(action_counts),
        "recommendation_to_actions": {
            recommendation: sorted(
                {
                    action
                    for row in reviewed
                    if row["recommendation"] == recommendation
                    for action in row["next_materialization_actions"]
                }
            )
            for recommendation in sorted(recommendation_counts)
        },
    }
    summary = {
        "stage": STAGE,
        "decision": "fail_closed_semantic_review_complete_no_training_rows",
        "claim_boundary": (
            "Audit-only semantic review of Stage12388 recovered transition candidates. "
            "No Level-3 admission, no patch-trace admission, no strict/source-heldout admission, "
            "no scale-progress claim, and no training rows."
        ),
        "source_stage": source_summary.get("stage") or "stage12388_transition_local_candidate_recovery",
        "source_records": len(source_rows),
        "records_reviewed": len(reviewed),
        "training_allowed": False,
        "new_training_rows_emitted": 0,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "strict_eval_eligible": 0,
        "source_heldout_admissible": 0,
        "scale_progress_claim_allowed": False,
        "source_diversity_claim_allowed": False,
        "self_repo_dominated_qc_scaffold": bool(source_summary.get("self_repo_dominated_qc_scaffold")),
        "global_admission_boundary": {
            "training_allowed": False,
            "per_row_training_allowed_required": False,
            "emit_training_rows": False,
            "strict_eval_admission_allowed": False,
            "source_heldout_admission_allowed": False,
            "stage12390_repair_transition_auto_admission_allowed": False,
        },
        "recommendation_counts": dict(recommendation_counts),
        "review_status_counts": dict(review_status_counts),
        "review_status_class_counts": dict(review_status_class_counts),
        "transition_candidate_counts": {
            key: value["total"] for key, value in counts_by_transition.items()
        },
        "repo_family_counts": {key: value["total"] for key, value in counts_by_repo.items()},
        "counts_by_transition_candidate": counts_by_transition,
        "counts_by_repo_family": counts_by_repo,
        "remaining_blocker_counts": dict(remaining_blocker_counts),
        "rule_id_counts": dict(rule_id_counts),
        "hard_rule_counts": dict(hard_rule_counts),
        "next_materialization_action_counts": dict(action_counts),
        "next_stage": {
            "stage": "stage12390",
            "allowed_input_from_stage12389": "reviewed audit records only",
            "training_allowed": False,
            "auto_admission_allowed": False,
            "required_before_materialization": [
                "resolve_repo_identity_semantic_review",
                "resolve_policy_label_review",
                "resolve_verifier_relevance_review",
                "resolve_state_delta_review",
                "exclude_mixed_patch_status_rows",
                "exclude_patch_failed_or_verifier_nonpass_rows",
                "block_self_repo_rows_from_scale_claims",
            ],
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "transition_candidate_semantic_review_records.jsonl", reviewed)
    write_json(OUT / "transition_candidate_semantic_review_summary.json", summary)
    write_json(OUT / "counts_by_transition_candidate.json", counts_by_transition)
    write_json(OUT / "counts_by_repo_family.json", counts_by_repo)
    write_json(OUT / "next_materialization_actions.json", next_actions_payload)
    write_markdown(summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()

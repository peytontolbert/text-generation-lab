#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12539_targeted_command_output_source_expansion_planner"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12538_SUMMARY = ROOT / "runs/summaries/stage12538_stage12537_semantic_review_admission_rollup.json"
STAGE12538_WORKLIST = (
    ROOT
    / "runs/local/artifacts/stage12538_stage12537_semantic_review_admission_rollup"
    / "remaining_gap_source_expansion_worklist.jsonl"
)
STAGE12537_SUMMARY = ROOT / "runs/summaries/stage12537_command_output_verifier_observation_materialization_preflight.json"
STAGE12537_CANDIDATES = (
    ROOT
    / "runs/local/artifacts/stage12537_command_output_verifier_observation_materialization_preflight"
    / "real_command_output_verifier_observation_candidate_rows.jsonl"
)
STAGE12537_BLOCKERS = (
    ROOT
    / "runs/local/artifacts/stage12537_command_output_verifier_observation_materialization_preflight"
    / "real_command_output_verifier_observation_blocker_worklist.jsonl"
)

PREFLIGHT_ROWS_NAME = "stage12539_gate_ready_preflight_candidate_rows.jsonl"
BLOCKED_GATE_ROWS_NAME = "stage12539_existing_candidate_gate_blocked_rows.jsonl"
WORKLIST_NAME = "stage12539_prioritized_source_expansion_worklist.jsonl"
GATE_AUDIT_NAME = "stage12539_materialization_gate_audit.json"

DIRECT_VERIFIER_STATUSES = {"PASS_CURRENT_STATE", "FAIL_CURRENT_STATE", "INSUFFICIENT_EVIDENCE"}
ALLOWED_TARGET_BINDING = "target_semantic_value_from_observed_verifier_result_status"
MAX_TARGET_SHARE = 0.50
MIN_TARGET_CLASSES = 3
MIN_TARGET_CLASS_COUNT = 2

SAFE_CANDIDATE_FIELDS = (
    "candidate_ref_hash",
    "source_stage",
    "source_line_hash",
    "root_lineage_key_hash",
    "repo_family_hash",
    "language_family",
    "task_projection",
    "target_semantic_value",
    "verifier_status",
    "actual_verifier_command_output_observation_provenance",
    "verifier_command_ref_hash",
    "command_result_id_hash",
    "verifier_exit_status_class",
    "verifier_stdout_hash",
    "verifier_stderr_hash",
    "verifier_output_hash",
    "verifier_observation_hash",
    "target_binding_class",
    "target_binding_rule_id_hash",
    "source_lineage_checked",
    "hydratable_verifier_observation_candidate",
    "controlled_fixture_like",
)
REQUIRED_FIELDS = (
    "candidate_ref_hash",
    "source_stage",
    "source_line_hash",
    "root_lineage_key_hash",
    "repo_family_hash",
    "language_family",
    "task_projection",
    "target_semantic_value",
    "verifier_status",
    "actual_verifier_command_output_observation_provenance",
    "verifier_command_ref_hash",
    "command_result_id_hash",
    "verifier_stdout_hash",
    "verifier_stderr_hash",
    "verifier_output_hash",
    "verifier_observation_hash",
    "target_binding_class",
    "target_binding_rule_id_hash",
)


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                value["__line_no"] = line_no
                rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def selected_test_scope_policy(row: dict[str, Any]) -> tuple[str, bool]:
    source_stage = str(row.get("source_stage") or "").lower()
    if "selected" in source_stage:
        return "selected_test_scope_requires_explicit_non_countable_policy_before_materialization", False
    return "non_selected_test_source_scope", True


def candidate_issues(row: dict[str, Any]) -> list[str]:
    issues = [f"missing_{field}" for field in REQUIRED_FIELDS if field not in row]
    if row.get("actual_verifier_command_output_observation_provenance") is not True:
        issues.append("actual_command_output_observation_provenance_not_true")
    if row.get("target_binding_class") != ALLOWED_TARGET_BINDING:
        issues.append("target_binding_not_observed_verifier_status")
    if row.get("target_semantic_value") != row.get("verifier_status"):
        issues.append("target_not_bound_to_observed_verifier_status")
    if row.get("target_semantic_value") not in DIRECT_VERIFIER_STATUSES:
        issues.append("target_status_not_stage12538_direct_verifier_status")
    if row.get("training_allowed") not in (None, False):
        issues.append("training_allowed_true_or_nonfalse")
    if row.get("countable_train_support") not in (None, False):
        issues.append("countable_train_support_true_or_nonfalse")
    return sorted(set(issues))


def with_join_and_scope(row: dict[str, Any]) -> dict[str, Any]:
    scoped_policy, scope_allowed = selected_test_scope_policy(row)
    out = {field: row[field] for field in SAFE_CANDIDATE_FIELDS if field in row}
    out.update(
        {
            "stage": STAGE,
            "record_type": "stage12539_gate_prepared_command_output_candidate_preflight_v1",
            "stage12537_candidate_ref_hash": row.get("candidate_ref_hash"),
            "candidate_ref_hash": stable_hash(
                {
                    "stage12537_candidate_ref_hash": row.get("candidate_ref_hash"),
                    "join": row.get("command_result_id_hash"),
                    "observation": row.get("verifier_observation_hash"),
                }
            ),
            "command_observation_join_hash": stable_hash(
                {
                    "command_result_id_hash": row.get("command_result_id_hash"),
                    "verifier_command_ref_hash": row.get("verifier_command_ref_hash"),
                    "verifier_observation_hash": row.get("verifier_observation_hash"),
                    "verifier_output_hash": row.get("verifier_output_hash"),
                    "target_binding_rule_id_hash": row.get("target_binding_rule_id_hash"),
                }
            ),
            "selected_test_scope_policy": scoped_policy,
            "selected_test_scope_materialization_allowed": scope_allowed,
            "duplicate_output_policy": "unique_output_required_or_same_target_collapse",
            "materialization_scope": "stage12539_preflight_only",
            "training_allowed": False,
            "countable_train_support": False,
        }
    )
    return out


def blocked_row(row: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "record_type": "stage12539_existing_candidate_gate_blocker_v1",
        "stage12537_candidate_ref_hash": row.get("candidate_ref_hash") or row.get("stage12537_candidate_ref_hash"),
        "source_stage_hash": stable_hash(row.get("source_stage")),
        "source_line_hash": row.get("source_line_hash") or stable_hash(row.get("__line_no")),
        "blocked_reasons": sorted(set(reasons)),
        "candidate_row_emitted": False,
        "training_allowed": False,
        "countable_train_support": False,
    }


def collapse_duplicate_outputs(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get("verifier_output_hash") or "")].append(row)

    accepted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    same_target_collapsed = 0
    conflicting_output_groups = 0
    for output_hash, group in groups.items():
        if not output_hash:
            blocked.extend(blocked_row(row, ["missing_verifier_output_hash"]) for row in group)
            continue
        targets = {str(row.get("target_semantic_value") or "unknown") for row in group}
        ordered = sorted(group, key=lambda row: str(row.get("candidate_ref_hash") or ""))
        if len(group) == 1:
            accepted.append(ordered[0])
        elif len(targets) == 1:
            accepted.append(ordered[0])
            same_target_collapsed += len(ordered) - 1
            blocked.extend(blocked_row(row, ["duplicate_verifier_output_hash_collapsed_same_target"]) for row in ordered[1:])
        else:
            conflicting_output_groups += 1
            blocked.extend(blocked_row(row, ["duplicate_verifier_output_hash_conflicting_target_blocked"]) for row in ordered)
    return accepted, blocked, {
        "duplicate_same_target_output_rows_collapsed": same_target_collapsed,
        "duplicate_conflicting_output_groups": conflicting_output_groups,
    }


def target_balance_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(row.get("target_semantic_value") or "unknown") for row in rows)
    total = sum(counts.values())
    max_share = max(counts.values()) / total if total else 0.0
    min_count = min(counts.values()) if counts else 0
    missing_classes = sorted(DIRECT_VERIFIER_STATUSES - set(counts))
    passed = (
        bool(rows)
        and max_share <= MAX_TARGET_SHARE
        and len(counts) >= MIN_TARGET_CLASSES
        and min_count >= MIN_TARGET_CLASS_COUNT
    )
    return {
        "passed": passed,
        "row_count": total,
        "target_counts": dict(sorted(counts.items())),
        "missing_target_classes": missing_classes,
        "max_target_share": round(max_share, 6),
        "target_class_count": len(counts),
        "min_target_class_count": min_count,
        "required_max_target_share": MAX_TARGET_SHARE,
        "required_target_class_count": MIN_TARGET_CLASSES,
        "required_min_target_class_count": MIN_TARGET_CLASS_COUNT,
    }


def materialize_gate_ready_preflight(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for row in candidates:
        issues = candidate_issues(row)
        prepared_row = with_join_and_scope(row)
        if not prepared_row["selected_test_scope_materialization_allowed"]:
            issues.append("selected_test_scope_policy_unresolved")
        if issues:
            blocked.append(blocked_row(row, issues))
        else:
            prepared.append(prepared_row)

    collapsed, collapse_blocked, collapse_audit = collapse_duplicate_outputs(prepared)
    blocked.extend(collapse_blocked)
    balance = target_balance_audit(collapsed)
    batch_block_reasons = []
    if not balance["passed"]:
        batch_block_reasons.append("target_balance_failed_after_join_scope_and_duplicate_collapse")
    if collapse_audit["duplicate_conflicting_output_groups"]:
        batch_block_reasons.append("duplicate_output_conflict_present")
    if batch_block_reasons:
        blocked.extend(blocked_row(row, batch_block_reasons) for row in collapsed)
        collapsed = []

    gate_audit = {
        "input_candidate_rows": len(candidates),
        "candidate_rows_after_join_and_scope": len(prepared),
        "candidate_rows_after_duplicate_collapse": len(collapsed),
        "blocked_existing_candidate_rows": len(blocked),
        "target_balance_audit": balance,
        "duplicate_output_audit": collapse_audit,
        "selected_test_scope_blocked_rows": sum(
            1 for row in blocked if "selected_test_scope_policy_unresolved" in row.get("blocked_reasons", [])
        ),
        "command_observation_join_hash_present_on_all_prepared_rows": all(
            bool(row.get("command_observation_join_hash")) for row in prepared
        ),
        "batch_block_reasons": sorted(set(batch_block_reasons)),
    }
    return collapsed, blocked, gate_audit


def target_shortfall(balance: dict[str, Any]) -> dict[str, int]:
    counts = {target: int(balance.get("target_counts", {}).get(target, 0)) for target in sorted(DIRECT_VERIFIER_STATUSES)}
    if not any(counts.values()):
        return {target: MIN_TARGET_CLASS_COUNT for target in sorted(DIRECT_VERIFIER_STATUSES)}

    best: dict[str, int] | None = None
    targets = sorted(DIRECT_VERIFIER_STATUSES)
    # This search is intentionally small: admission batches here are tiny control packets.
    for pass_add in range(0, 25):
        for fail_add in range(0, 25):
            for insufficient_add in range(0, 25):
                additions = {
                    "PASS_CURRENT_STATE": pass_add,
                    "FAIL_CURRENT_STATE": fail_add,
                    "INSUFFICIENT_EVIDENCE": insufficient_add,
                }
                candidate = {target: counts[target] + additions[target] for target in targets}
                total = sum(candidate.values())
                if not total:
                    continue
                max_share = max(candidate.values()) / total
                if (
                    max_share <= MAX_TARGET_SHARE
                    and sum(1 for value in candidate.values() if value > 0) >= MIN_TARGET_CLASSES
                    and min(candidate.values()) >= MIN_TARGET_CLASS_COUNT
                ):
                    if best is None or sum(additions.values()) < sum(best.values()):
                        best = additions
    if best is None:
        return {target: max(0, MIN_TARGET_CLASS_COUNT - counts[target]) for target in targets}
    return {target: count for target, count in best.items() if count > 0}


def planned_action(reason: str) -> str:
    actions = {
        "stage12538_command_observation_join_hash_missing": (
            "Re-run the command-output candidate materializer with a stable join hash over command-result, command, "
            "observation, output, and target-binding hashes."
        ),
        "stage12538_duplicate_output_hash_requires_collapse_or_block": (
            "Collapse same-target duplicate verifier-output hashes to one representative and block conflicting-target "
            "duplicates before semantic review."
        ),
        "stage12538_selected_test_scope_not_countable_without_explicit_policy": (
            "Either exclude selected-test scoped rows from the next gate batch or attach an explicit preflight-only "
            "selected-test scope policy before materialization."
        ),
        "stage12538_target_balance_failed": (
            "Materialize direct real command-output observations for missing or underrepresented verifier-status "
            "targets before any review batch."
        ),
        "unsupported_or_forbidden_target_status_for_stage12537_preflight": (
            "Do not convert verifier-transition labels into direct verifier-status rows; execute or mine direct "
            "current-state verifier observations instead."
        ),
        "missing_actual_verifier_command_output_observation_provenance": (
            "Acquire command_result_id, command hash, exit class, stdout/stderr digests, output hash, and observation "
            "hash before candidate materialization."
        ),
        "controlled_fixture_like_not_materialized": (
            "Replace fixture-like examples with public/local non-fixture verifier command-output observations."
        ),
        "derived_sanitized_projection_lacks_independent_command_output_hash_provenance": (
            "Return to the raw command-output source behind the projection rows and materialize digest-backed "
            "observations."
        ),
        "projection_rows_lack_stdout_stderr_digest_fields_required_by_stage12537": (
            "Mine or execute rows with stdout and stderr digest fields rather than projection-only rows."
        ),
    }
    return actions.get(reason, "Materialize only real command-output verifier-observation rows with hash-only lineage.")


def build_worklist(
    stage12538_summary: dict[str, Any],
    stage12538_worklist: list[dict[str, Any]],
    stage12537_blockers: list[dict[str, Any]],
    gate_audit: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    priority = 1
    for target, missing in target_shortfall(gate_audit["target_balance_audit"]).items():
        rows.append(
            {
                "stage": STAGE,
                "record_type": "stage12539_source_expansion_work_item_v1",
                "priority": priority,
                "work_item_id": stable_hash({"target_shortfall": target, "missing": missing}),
                "blocker_reason": "target_status_shortfall_after_stage12538_gates",
                "target_status": target,
                "minimum_new_rows_needed": missing,
                "shortfall_computed_against_post_gate_target_counts": True,
                "recommended_next_action": planned_action("stage12538_target_balance_failed"),
                "training_allowed": False,
                "countable_train_support": False,
            }
        )
        priority += 1

    blocker_counts = Counter(reason for row in stage12537_blockers for reason in row.get("blocked_reasons", []))
    combined: dict[str, int] = {}
    for reason, count in blocker_counts.items():
        combined[str(reason)] = max(combined.get(str(reason), 0), int(count))
    for row in stage12538_worklist:
        reason = str(row.get("blocker_reason") or "")
        if reason:
            combined[reason] = max(combined.get(reason, 0), int(row.get("blocked_row_count") or 0))
    for reason in stage12538_summary.get("batch_block_reasons", []):
        reason = str(reason)
        combined[reason] = max(combined.get(reason, 0), 1)
    for reason, count in sorted(combined.items(), key=lambda item: (-item[1], item[0])):
        if not reason:
            continue
        rows.append(
            {
                "stage": STAGE,
                "record_type": "stage12539_source_expansion_work_item_v1",
                "priority": priority,
                "work_item_id": stable_hash({"reason": reason, "count": count}),
                "blocker_reason": reason,
                "blocked_row_count": count,
                "recommended_next_action": planned_action(reason),
                "training_allowed": False,
                "countable_train_support": False,
            }
        )
        priority += 1
    return rows


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12538_summary = read_json(STAGE12538_SUMMARY)
    stage12537_summary = read_json(STAGE12537_SUMMARY)
    stage12538_worklist = read_jsonl(STAGE12538_WORKLIST)
    stage12537_candidates = read_jsonl(STAGE12537_CANDIDATES)
    stage12537_blockers = read_jsonl(STAGE12537_BLOCKERS)

    preflight_rows, blocked_rows, gate_audit = materialize_gate_ready_preflight(stage12537_candidates)
    worklist = build_worklist(stage12538_summary, stage12538_worklist, stage12537_blockers, gate_audit)

    preflight_path = OUT / PREFLIGHT_ROWS_NAME
    blocked_path = OUT / BLOCKED_GATE_ROWS_NAME
    worklist_path = OUT / WORKLIST_NAME
    audit_path = OUT / GATE_AUDIT_NAME
    write_jsonl(preflight_path, preflight_rows)
    write_jsonl(blocked_path, blocked_rows)
    write_jsonl(worklist_path, worklist)

    audit = {
        "stage": STAGE,
        "record_type": "stage12539_materialization_gate_audit_v1",
        "gate_audit": gate_audit,
        "stage12538_remaining_gap_to_500": stage12538_summary.get("remaining_gap_to_500"),
        "stage12538_batch_block_reasons": stage12538_summary.get("batch_block_reasons", []),
        "stage12537_candidate_status_counts": stage12537_summary.get("candidate_status_counts", {}),
        "input_hashes": {
            "stage12538_summary": file_hash(STAGE12538_SUMMARY),
            "stage12538_worklist": file_hash(STAGE12538_WORKLIST),
            "stage12537_summary": file_hash(STAGE12537_SUMMARY),
            "stage12537_candidates": file_hash(STAGE12537_CANDIDATES),
            "stage12537_blockers": file_hash(STAGE12537_BLOCKERS),
        },
    }
    write_json(audit_path, audit)

    decision = (
        "gate_ready_preflight_rows_materialized_training_blocked"
        if preflight_rows
        else "fail_closed_prioritized_source_expansion_worklist_emitted_no_preflight_rows"
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12539_targeted_source_expansion_planner_summary_v1",
        "decision": decision,
        "claim_boundary": (
            "Stage12539 only plans or preflights source expansion for real command-output verifier observations. "
            "It does not admit training rows or count support."
        ),
        "stage12538_remaining_gap_to_500": stage12538_summary.get("remaining_gap_to_500"),
        "stage12538_batch_block_reasons": stage12538_summary.get("batch_block_reasons", []),
        "stage12537_candidate_rows_scanned": len(stage12537_candidates),
        "gate_ready_preflight_candidate_rows": len(preflight_rows),
        "existing_candidate_gate_blocked_rows": len(blocked_rows),
        "prioritized_worklist_rows": len(worklist),
        "target_balance_audit": gate_audit["target_balance_audit"],
        "target_status_shortfall": target_shortfall(gate_audit["target_balance_audit"]),
        "duplicate_output_audit": gate_audit["duplicate_output_audit"],
        "selected_test_scope_blocked_rows": gate_audit["selected_test_scope_blocked_rows"],
        "command_observation_join_hash_present_on_all_prepared_rows": gate_audit[
            "command_observation_join_hash_present_on_all_prepared_rows"
        ],
        "training_allowed": False,
        "countable_train_support": False,
        "new_countable_train_support_count": 0,
        "artifact_refs": {
            "preflight_candidate_rows": str(preflight_path.relative_to(ROOT)),
            "blocked_existing_candidate_gates": str(blocked_path.relative_to(ROOT)),
            "prioritized_source_expansion_worklist": str(worklist_path.relative_to(ROOT)),
            "gate_audit": str(audit_path.relative_to(ROOT)),
            "summary": str(SUMMARY.relative_to(ROOT)),
        },
        "input_hashes": audit["input_hashes"],
        "next_safe_action": "execute_or_mine_underrepresented_direct_verifier_status_command_outputs_then_rerun_join_collapse_scope_materializer",
    }
    write_json(SUMMARY, summary)
    return summary


def main() -> None:
    build()


if __name__ == "__main__":
    main()

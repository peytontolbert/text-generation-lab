#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12540_command_output_verifier_observation_preflight_rows"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12539_WORKLIST = (
    ROOT
    / "runs/local/artifacts/stage12539_targeted_command_output_source_expansion_planner"
    / "stage12539_prioritized_source_expansion_worklist.jsonl"
)
STAGE12539_SUMMARY = ROOT / "runs/summaries/stage12539_targeted_command_output_source_expansion_planner.json"
STAGE12537_CANDIDATES = (
    ROOT
    / "runs/local/artifacts/stage12537_command_output_verifier_observation_materialization_preflight"
    / "real_command_output_verifier_observation_candidate_rows.jsonl"
)

STAGE12204_COMMAND_RESULTS = (
    ROOT / "runs/local/artifacts/stage12204_hydratable_verifier_replay_batch/command_results.jsonl"
)
STAGE12204_OBSERVATIONS = ROOT / "runs/local/artifacts/stage12204_hydratable_verifier_replay_batch/observations.jsonl"
STAGE12204_TRANSITIONS = (
    ROOT / "runs/local/artifacts/stage12204_hydratable_verifier_replay_batch/verifier_transitions.jsonl"
)
STAGE12204_SUMMARY = ROOT / "runs/local/artifacts/stage12204_hydratable_verifier_replay_batch/summary.json"

STAGE12223_RECORDS = (
    ROOT / "runs/local/artifacts/stage12223_targeted_patch_replay_smoke/targeted_patch_replay_records.jsonl"
)

PREFLIGHT_ROWS_NAME = "stage12540_real_command_output_verifier_observation_preflight_rows.jsonl"
BLOCKED_ROWS_NAME = "stage12540_blocked_candidate_rows.jsonl"
WORKLIST_NAME = "stage12540_remaining_materialization_worklist.jsonl"
AUDIT_NAME = "stage12540_materialization_audit.json"

DIRECT_TARGETS = {"PASS_CURRENT_STATE", "FAIL_CURRENT_STATE", "INSUFFICIENT_EVIDENCE"}
TARGET_BINDING_CLASS = "target_semantic_value_from_same_source_observed_verifier_status"
DEFAULT_SHORTFALL = {"FAIL_CURRENT_STATE": 1, "INSUFFICIENT_EVIDENCE": 2}


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def sha256_text(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8", errors="replace")).hexdigest()


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


def exit_status_class(returncode: Any) -> str:
    try:
        code = int(returncode)
    except (TypeError, ValueError):
        return "exit_unknown"
    return "exit_zero" if code == 0 else "exit_nonzero"


def target_shortfall(worklist: list[dict[str, Any]]) -> dict[str, int]:
    shortfall: dict[str, int] = {}
    for row in worklist:
        if row.get("blocker_reason") != "target_status_shortfall_after_stage12538_gates":
            continue
        target = str(row.get("target_status") or "")
        if target in DIRECT_TARGETS:
            shortfall[target] = max(shortfall.get(target, 0), int(row.get("minimum_new_rows_needed") or 0))
    return shortfall or dict(DEFAULT_SHORTFALL)


def command_result_hash(result: dict[str, Any]) -> str:
    return stable_hash(
        {
            "command_result_id": result.get("command_result_id"),
            "command": result.get("observed_command") or result.get("command"),
            "argv": result.get("argv"),
            "cwd": result.get("cwd"),
            "returncode": result.get("returncode"),
        }
    )


def output_hash(result: dict[str, Any]) -> str:
    return stable_hash(
        {
            "returncode": result.get("returncode"),
            "stdout_sha256": result.get("stdout_sha256"),
            "stderr_sha256": result.get("stderr_sha256"),
            "stdout_tail_sha256": sha256_text(result.get("stdout_tail")) if "stdout_tail" in result else None,
            "stderr_tail_sha256": sha256_text(result.get("stderr_tail")) if "stderr_tail" in result else None,
        }
    )


def same_source_join_hash(source_stage: str, result: dict[str, Any], status_payload: dict[str, Any]) -> str:
    return stable_hash(
        {
            "source_stage": source_stage,
            "command_result_id": result.get("command_result_id"),
            "command": result.get("observed_command") or result.get("command"),
            "argv": result.get("argv"),
            "cwd": result.get("cwd"),
            "returncode": result.get("returncode"),
            "stdout_sha256": result.get("stdout_sha256"),
            "stderr_sha256": result.get("stderr_sha256"),
            "stdout_tail_sha256": sha256_text(result.get("stdout_tail")) if "stdout_tail" in result else None,
            "stderr_tail_sha256": sha256_text(result.get("stderr_tail")) if "stderr_tail" in result else None,
            "status": status_payload,
        }
    )


def explicitly_non_countable_selected_scope(source_stage: str, row: dict[str, Any]) -> tuple[str, bool]:
    selected_markers = (
        "selected" in source_stage.lower()
        or bool(row.get("selected_tests"))
        or bool(row.get("selected_target"))
        or bool(row.get("selected_test_anchor"))
    )
    if not selected_markers:
        return "non_selected_test_source_scope", True
    return "selected_test_scope_blocked_for_stage12540_source_expansion", False

def risky_claims_false() -> dict[str, Any]:
    return {
        "training_allowed": False,
        "countable_train_support": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "level3_admitted": False,
        "level4_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
    }


def candidate_base(
    *,
    source_stage: str,
    source_path: Path,
    source_line: Any,
    result: dict[str, Any],
    target: str,
    status_payload: dict[str, Any],
    repo_family: Any,
    root_id: Any,
    language_family: Any,
    observation_id: Any,
    source_scope_row: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    issues = []
    if target not in DIRECT_TARGETS:
        issues.append("target_status_not_allowed_direct_preflight_status")
    if not result.get("command_result_id"):
        issues.append("missing_command_result_id")
    if not (result.get("observed_command") or result.get("command") or result.get("argv")):
        issues.append("missing_command_or_argv")
    if "returncode" not in result:
        issues.append("missing_returncode")
    if not (result.get("stdout_sha256") or "stdout_tail" in result):
        issues.append("missing_stdout_output_digest_or_tail")
    if not (result.get("stderr_sha256") or "stderr_tail" in result):
        issues.append("missing_stderr_output_digest_or_tail")
    scoped_policy, scope_allowed = explicitly_non_countable_selected_scope(source_stage, source_scope_row)
    if not scope_allowed:
        issues.append("selected_test_scope_not_countable_for_stage12540_source_expansion")
    if bool(source_scope_row.get("controlled_fixture_like")):
        issues.append("controlled_fixture_like_source_not_stage12540_materializable")
    if bool(source_scope_row.get("projection_only")):
        issues.append("projection_only_source_not_stage12540_materializable")

    join = same_source_join_hash(source_stage, result, status_payload)
    out_hash = output_hash(result)
    row_id_material = {
        "source_stage": source_stage,
        "command_result_id": result.get("command_result_id"),
        "target": target,
        "join": join,
    }
    row = {
        "stage": STAGE,
        "record_type": "stage12540_real_command_output_verifier_observation_preflight_row_v1",
        "candidate_ref_hash": stable_hash(row_id_material),
        "source_stage": source_stage,
        "source_artifact_hash": file_hash(source_path),
        "source_line_hash": stable_hash({"path": str(source_path.relative_to(ROOT)), "line": source_line}),
        "root_lineage_key_hash": stable_hash({"source_stage": source_stage, "root_id": root_id, "repo": repo_family}),
        "repo_family_hash": stable_hash({"repo_family": repo_family}),
        "language_family": str(language_family or "unknown"),
        "task_projection": "transition_verifier_transition",
        "target_semantic_value": target,
        "verifier_status": target,
        "actual_verifier_command_output_observation_provenance": True,
        "verifier_command_ref_hash": command_result_hash(result),
        "command_result_id_hash": stable_hash(result.get("command_result_id")),
        "verifier_exit_status_class": exit_status_class(result.get("returncode")),
        "verifier_stdout_hash": str(result.get("stdout_sha256") or sha256_text(result.get("stdout_tail"))),
        "verifier_stderr_hash": str(result.get("stderr_sha256") or sha256_text(result.get("stderr_tail"))),
        "verifier_output_hash": out_hash,
        "verifier_observation_hash": stable_hash(
            {
                "observation_id": observation_id,
                "command_result_id": result.get("command_result_id"),
                "target": target,
                "status_payload": status_payload,
            }
        ),
        "command_observation_join_hash": join,
        "command_observation_join_hash_rule": (
            "sha256_stage12540_same_source_command_result_output_status_fields_sanitized_to_24hex"
        ),
        "target_binding_class": TARGET_BINDING_CLASS,
        "target_binding_rule_id_hash": stable_hash({"rule": TARGET_BINDING_CLASS, "target": target, "status": status_payload}),
        "source_lineage_checked": True,
        "hydratable_verifier_observation_candidate": True,
        "controlled_fixture_like": bool(source_scope_row.get("controlled_fixture_like", False)),
        "selected_test_scope_policy": scoped_policy,
        "selected_test_scope_materialization_allowed": scope_allowed,
        "duplicate_output_policy": "unique_output_hash_required_collapsing_same_target_duplicates",
        "materialization_scope": "stage12540_preflight_only",
        **risky_claims_false(),
    }
    if issues:
        return None, blocked_row(row, issues)
    return row, None


def blocked_row(row: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "record_type": "stage12540_blocked_candidate_row_v1",
        "candidate_ref_hash": row.get("candidate_ref_hash") or stable_hash(row),
        "source_stage_hash": stable_hash(row.get("source_stage")),
        "source_line_hash": row.get("source_line_hash") or stable_hash(row),
        "verifier_output_hash": row.get("verifier_output_hash"),
        "target_semantic_value": row.get("target_semantic_value"),
        "blocked_reasons": sorted(set(reasons)),
        "candidate_row_emitted": False,
        **risky_claims_false(),
    }


def stage12204_candidates() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    results = {row.get("command_result_id"): row for row in read_jsonl(STAGE12204_COMMAND_RESULTS)}
    observations = {row.get("command_result_id"): row for row in read_jsonl(STAGE12204_OBSERVATIONS)}
    transitions = read_jsonl(STAGE12204_TRANSITIONS)
    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for transition in transitions:
        target = str(transition.get("transition") or transition.get("status") or "")
        if target != "INSUFFICIENT_EVIDENCE":
            continue
        result = results.get(transition.get("command_result_id")) or {}
        observation = observations.get(transition.get("command_result_id")) or {}
        scope_row = {
            "selected_tests": transition.get("selected_tests"),
            "training_allowed": False,
            "countable_train_support": False,
            "controlled_fixture_like": True,
        }
        row, blocker = candidate_base(
            source_stage="stage12204_hydratable_verifier_replay_batch",
            source_path=STAGE12204_TRANSITIONS,
            source_line=transition.get("__line_no"),
            result=result,
            target=target,
            status_payload={
                "transition": transition.get("transition"),
                "status": transition.get("status"),
                "observation_status": observation.get("verifier_status"),
                "verifier_transition_id": transition.get("verifier_transition_id"),
            },
            repo_family=result.get("repo_family"),
            root_id=result.get("root_id"),
            language_family="python",
            observation_id=observation.get("observation_id"),
            source_scope_row=scope_row,
        )
        if row is not None:
            candidates.append(row)
        if blocker is not None:
            blocked.append(blocker)
    return candidates, blocked


def stage12223_candidates() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for record in read_jsonl(STAGE12223_RECORDS):
        verifier_result = record.get("verifier_result") if isinstance(record.get("verifier_result"), dict) else {}
        before = verifier_result.get("before") if isinstance(verifier_result.get("before"), dict) else {}
        status = "FAIL_CURRENT_STATE"
        ordered_events = record.get("ordered_events") if isinstance(record.get("ordered_events"), list) else []
        before_status_seen = any(
            isinstance(event, dict)
            and event.get("event_type") == "COMMAND_RESULT"
            and event.get("phase") == "before"
            and event.get("status") == status
            for event in ordered_events
        )
        if not before_status_seen:
            continue
        result = dict(before)
        result["command_result_id"] = stable_hash(
            {
                "episode_id": record.get("episode_id"),
                "phase": "before",
                "command": before.get("command"),
                "cwd": before.get("cwd"),
                "returncode": before.get("returncode"),
            }
        )
        scope_row = {"selected_target": True, "training_allowed": False, "countable_train_support": False}
        row, blocker = candidate_base(
            source_stage="stage12223_targeted_patch_replay_smoke_before_phase_only",
            source_path=STAGE12223_RECORDS,
            source_line=record.get("__line_no"),
            result=result,
            target=status,
            status_payload={
                "phase": "before",
                "command_result_status": status,
                "record_verifier_transition": record.get("verifier_transition"),
            },
            repo_family=record.get("repo_family"),
            root_id=record.get("root_id"),
            language_family=record.get("language_family"),
            observation_id=stable_hash({"episode_id": record.get("episode_id"), "phase": "before", "status": status}),
            source_scope_row=scope_row,
        )
        if row is not None:
            candidates.append(row)
        if blocker is not None:
            blocked.append(blocker)
    return candidates, blocked


def collapse_duplicate_outputs(
    rows: list[dict[str, Any]], prior_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    prior_outputs = {str(row.get("verifier_output_hash")) for row in prior_rows if row.get("verifier_output_hash")}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get("verifier_output_hash") or "")].append(row)
    accepted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    same_target_collapsed = 0
    conflicting_groups = 0
    prior_duplicate_rows = 0
    for out_hash, group in sorted(groups.items()):
        ordered = sorted(group, key=lambda row: str(row.get("candidate_ref_hash") or ""))
        if not out_hash:
            blocked.extend(blocked_row(row, ["missing_verifier_output_hash"]) for row in ordered)
            continue
        if out_hash in prior_outputs:
            prior_duplicate_rows += len(ordered)
            blocked.extend(blocked_row(row, ["duplicate_output_hash_matches_prior_candidate_blocked"]) for row in ordered)
            continue
        targets = {str(row.get("target_semantic_value") or "") for row in ordered}
        if len(targets) > 1:
            conflicting_groups += 1
            blocked.extend(blocked_row(row, ["duplicate_output_hash_conflicting_target_blocked"]) for row in ordered)
            continue
        accepted.append(ordered[0])
        if len(ordered) > 1:
            same_target_collapsed += len(ordered) - 1
            blocked.extend(blocked_row(row, ["duplicate_output_hash_collapsed_same_target"]) for row in ordered[1:])
    return accepted, blocked, {
        "duplicate_same_target_output_rows_collapsed": same_target_collapsed,
        "duplicate_conflicting_output_groups": conflicting_groups,
        "duplicate_output_rows_matching_prior_candidates_blocked": prior_duplicate_rows,
    }


def select_to_shortfall(
    rows: list[dict[str, Any]], shortfall: dict[str, int]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for row in sorted(rows, key=lambda item: (str(item.get("target_semantic_value")), str(item.get("candidate_ref_hash")))):
        target = str(row.get("target_semantic_value") or "")
        if counts[target] < shortfall.get(target, 0):
            selected.append(row)
            counts[target] += 1
        else:
            blocked.append(blocked_row(row, ["above_stage12539_target_shortfall_not_materialized"]))
    remaining = {target: max(0, needed - counts[target]) for target, needed in shortfall.items() if needed - counts[target] > 0}
    return selected, blocked, {"selected_target_counts": dict(sorted(counts.items())), "remaining_shortfall": remaining}


def build_worklist(shortfall: dict[str, int], selection_audit: dict[str, Any], blocked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    priority = 1
    for target, missing in sorted(selection_audit.get("remaining_shortfall", {}).items()):
        rows.append(
            {
                "stage": STAGE,
                "record_type": "stage12540_remaining_materialization_work_item_v1",
                "priority": priority,
                "blocker_reason": "target_status_shortfall_after_stage12540_materialization",
                "target_status": target,
                "minimum_new_rows_needed": missing,
                "recommended_next_action": "Mine or execute same-source command/result/output/status verifier observations for this direct status.",
                **risky_claims_false(),
            }
        )
        priority += 1
    blocker_counts = Counter(
        reason
        for row in blocked
        for reason in row.get("blocked_reasons", [])
        if reason != "above_stage12539_target_shortfall_not_materialized"
    )
    for reason, count in sorted(blocker_counts.items(), key=lambda item: (-item[1], item[0])):
        rows.append(
            {
                "stage": STAGE,
                "record_type": "stage12540_remaining_materialization_work_item_v1",
                "priority": priority,
                "blocker_reason": reason,
                "blocked_row_count": count,
                "recommended_next_action": "Keep the row out of preflight rows unless same-source evidence and scope gates can be satisfied.",
                **risky_claims_false(),
            }
        )
        priority += 1
    if not rows and not all(selection_audit["selected_target_counts"].get(target, 0) >= needed for target, needed in shortfall.items()):
        rows.append(
            {
                "stage": STAGE,
                "record_type": "stage12540_remaining_materialization_work_item_v1",
                "priority": priority,
                "blocker_reason": "insufficient_evidence_no_candidate_rows_materialized",
                "recommended_next_action": "Emit worklist only until direct same-source command-output evidence is available.",
                **risky_claims_false(),
            }
        )
    return rows


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    worklist12539 = read_jsonl(STAGE12539_WORKLIST)
    shortfall = target_shortfall(worklist12539)
    prior_rows = read_jsonl(STAGE12537_CANDIDATES)

    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for producer in (stage12204_candidates, stage12223_candidates):
        produced, producer_blocked = producer()
        candidates.extend(produced)
        blocked.extend(producer_blocked)

    needed_targets = set(shortfall)
    candidates = [row for row in candidates if row.get("target_semantic_value") in needed_targets]
    collapsed, collapse_blocked, duplicate_audit = collapse_duplicate_outputs(candidates, prior_rows)
    blocked.extend(collapse_blocked)
    selected, excess_blocked, selection_audit = select_to_shortfall(collapsed, shortfall)
    blocked.extend(excess_blocked)
    worklist = build_worklist(shortfall, selection_audit, blocked)

    rows_path = OUT / PREFLIGHT_ROWS_NAME
    blocked_path = OUT / BLOCKED_ROWS_NAME
    worklist_path = OUT / WORKLIST_NAME
    audit_path = OUT / AUDIT_NAME
    write_jsonl(rows_path, selected)
    write_jsonl(blocked_path, blocked)
    write_jsonl(worklist_path, worklist)

    status_counts = Counter(str(row.get("target_semantic_value") or "unknown") for row in selected)
    blocked_counts = Counter(reason for row in blocked for reason in row.get("blocked_reasons", []))
    input_hashes = {
        "stage12539_worklist": file_hash(STAGE12539_WORKLIST),
        "stage12539_summary": file_hash(STAGE12539_SUMMARY),
        "stage12537_candidates": file_hash(STAGE12537_CANDIDATES),
        "stage12204_command_results": file_hash(STAGE12204_COMMAND_RESULTS),
        "stage12204_observations": file_hash(STAGE12204_OBSERVATIONS),
        "stage12204_transitions": file_hash(STAGE12204_TRANSITIONS),
        "stage12204_summary": file_hash(STAGE12204_SUMMARY),
        "stage12223_records": file_hash(STAGE12223_RECORDS),
    }
    audit = {
        "stage": STAGE,
        "record_type": "stage12540_materialization_audit_v1",
        "input_hashes": input_hashes,
        "stage12539_target_shortfall": shortfall,
        "raw_candidate_rows_before_duplicate_collapse": len(candidates),
        "candidate_rows_after_duplicate_collapse": len(collapsed),
        "selected_preflight_rows": len(selected),
        "blocked_candidate_rows": len(blocked),
        "duplicate_output_audit": duplicate_audit,
        "selection_audit": selection_audit,
        "blocked_reason_counts": dict(sorted(blocked_counts.items())),
        **risky_claims_false(),
    }
    write_json(audit_path, audit)

    shortfall_satisfied = all(status_counts.get(target, 0) >= needed for target, needed in shortfall.items())
    decision = (
        "preflight_rows_materialized_training_blocked_non_countable"
        if selected and shortfall_satisfied
        else "insufficient_evidence_worklist_only_or_partial_preflight_no_countable_support"
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12540_command_output_preflight_summary_v1",
        "decision": decision,
        "claim_boundary": (
            "Stage12540 emits only sanitized preflight command-output verifier-observation rows or a worklist. "
            "It admits no countable support and makes no training, Level3, patch, repair, strict-eval, "
            "source-heldout, or model progress claim."
        ),
        "stage12539_target_shortfall": shortfall,
        "preflight_row_count": len(selected),
        "preflight_status_counts": dict(sorted(status_counts.items())),
        "shortfall_satisfied_by_preflight_rows": shortfall_satisfied,
        "worklist_row_count": len(worklist),
        "blocked_candidate_row_count": len(blocked),
        "duplicate_output_audit": duplicate_audit,
        "command_observation_join_hash_present_on_all_rows": all(
            bool(row.get("command_observation_join_hash")) for row in selected
        ),
        "selected_test_scope_rows": sum(
            1 for row in selected if str(row.get("selected_test_scope_policy", "")).startswith("selected_test")
        ),
        "controlled_fixture_like_rows": sum(1 for row in selected if row.get("controlled_fixture_like") is True),
        **risky_claims_false(),
        "new_countable_train_support_count": 0,
        "artifact_refs": {
            "preflight_rows": str(rows_path.relative_to(ROOT)),
            "blocked_candidate_rows": str(blocked_path.relative_to(ROOT)),
            "worklist": str(worklist_path.relative_to(ROOT)),
            "audit": str(audit_path.relative_to(ROOT)),
            "summary": str(SUMMARY.relative_to(ROOT)),
        },
        "input_hashes": input_hashes,
    }
    write_json(SUMMARY, summary)
    return summary


def main() -> None:
    build()


if __name__ == "__main__":
    main()

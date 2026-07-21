#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12311_task_window_state_code_hydrator"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

EPISODE_CANDIDATES = ROOT / "runs/local/artifacts/stage12306_session_episode_graph_candidate_materializer/stage12306_session_episode_graph_candidate_materializer.jsonl"
TASK_WINDOWS = ROOT / "runs/local/artifacts/stage12260_codex_chat_task_boundary_miner/codex_task_windows.jsonl"


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Path, rows: list[dict]) -> int:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)


def load_windows() -> dict[str, dict]:
    return {row.get("task_window_id"): row for row in iter_jsonl(TASK_WINDOWS) or [] if row.get("task_window_id")}


def hydrate_codes(window: dict) -> tuple[dict, dict, list[str]]:
    families = window.get("command_family_counts") or {}
    tools = window.get("tool_name_counts") or {}
    paired = int(window.get("paired_tool_call_count") or 0)
    patch_pairs = int(window.get("patch_pair_count") or 0)
    verifier_pairs = int(window.get("verifier_like_pair_count") or 0)

    codes = {
        "source_evidence_present": bool(families.get("read_or_search") or paired > 0),
        "patch_ref_present_in_window": patch_pairs > 0,
        "patch_plan_exists": "unknown",
        "patch_applied": "unknown",
        "patch_ref_is_not_patch_plan_or_apply_proof": patch_pairs > 0,
        "verifier_selected": verifier_pairs > 0 or bool(families.get("verifier_or_execution")),
        "verifier_run_status": "unknown",
        "failure_localized": "unknown",
        "requirement_covered": "unknown",
        "open_question": "unknown",
        "env_blocked": "unknown",
    }
    evidence = {
        "task_window_id": window.get("task_window_id"),
        "event_count": window.get("event_count"),
        "paired_tool_call_count": paired,
        "patch_pair_count": patch_pairs,
        "verifier_like_pair_count": verifier_pairs,
        "command_family_counts": {
            key: families.get(key)
            for key in ["read_or_search", "verifier_or_execution", "python_execution", "version_control", "other_command"]
            if key in families
        },
        "tool_name_counts": {key: tools.get(key) for key in ["apply_patch", "exec_command", "write_stdin"] if key in tools},
        "raw_content_emitted": False,
    }
    blockers = [
        "exact_semantic_rule_not_assignable_from_window_aggregate_metadata",
        "verifier_run_status_unknown_without_structured_output_class",
        "failure_localized_unknown_without_state_ledger",
        "requirement_covered_unknown_without_requirement_mapping",
        "open_question_unknown_without_hypothesis_ledger",
    ]
    if patch_pairs:
        blockers.append("patch_ref_present_but_not_plan_or_apply_proof")
    return codes, evidence, blockers


def coarse_lifecycle_code(codes: dict) -> tuple[str | None, list[str]]:
    if codes["env_blocked"] is True:
        return "S9_BLOCKED_OR_UNSAFE", []
    if not codes["source_evidence_present"]:
        return "S0_NEED_CONTEXT", []
    blockers = []
    if codes["failure_localized"] == "unknown":
        blockers.append("cannot_distinguish_S1_from_later_states_without_failure_localization")
    if codes["patch_plan_exists"] == "unknown" or codes["patch_applied"] == "unknown":
        blockers.append("cannot_distinguish_patch_plan_or_patch_applied_states")
    if codes["verifier_run_status"] == "unknown":
        blockers.append("cannot_distinguish_verifier_not_run_passed_failed")
    # S1 is a safe coarse lower-bound only, not a train label.
    return "S1_CONTEXT_GATHERED_FAILURE_UNLOCALIZED_COARSE", blockers


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    windows = load_windows()
    records = []
    missing_window = 0
    for candidate in iter_jsonl(EPISODE_CANDIDATES) or []:
        refs = candidate.get("source_refs") or {}
        task_window_id = refs.get("task_window_id") or candidate.get("task_window_id")
        window = windows.get(task_window_id)
        if not window:
            missing_window += 1
            records.append(
                {
                    "schema_version": "state_code_hydration_candidate_v1",
                    "stage": STAGE,
                    "candidate_id": candidate.get("candidate_id"),
                    "task_window_id": task_window_id,
                    "hydration_status": "blocked_missing_task_window",
                    "train_support_allowed": False,
                    "training_allowed": False,
                }
            )
            continue
        codes, evidence, blockers = hydrate_codes(window)
        lifecycle, lifecycle_blockers = coarse_lifecycle_code(codes)
        blockers.extend(lifecycle_blockers)
        records.append(
            {
                "schema_version": "state_code_hydration_candidate_v1",
                "stage": STAGE,
                "candidate_id": candidate.get("candidate_id"),
                "canonical_root_id": candidate.get("canonical_root_id"),
                "root_lineage_key": candidate.get("root_lineage_key"),
                "split_group_id": candidate.get("split_group_id"),
                "task_window_id": task_window_id,
                "language_family": candidate.get("language_family"),
                "repo_family": candidate.get("repo_family"),
                "hydration_status": "coarse_state_codes_hydrated_training_blocked",
                "state_codes": codes,
                "coarse_lifecycle_state": lifecycle,
                "state_evidence": evidence,
                "semantic_rule_id": None,
                "transition_function_key": None,
                "admission": {
                    "candidate_only": True,
                    "train_support_allowed": False,
                    "strict_eval_eligible": False,
                    "source_heldout_admissible": False,
                    "level_3_countable": False,
                    "training_allowed": False,
                },
                "blocked_reasons": sorted(set(blockers + [
                    "semantic_rule_id_missing",
                    "transition_function_key_missing",
                    "coarse_window_metadata_not_transition_local_proof",
                ])),
                "guardrails": {
                    "raw_message_text_emitted": False,
                    "raw_tool_arguments_emitted": False,
                    "raw_tool_output_emitted": False,
                    "raw_patch_body_emitted": False,
                    "raw_source_path_emitted": False,
                    "full_command_text_emitted": False,
                },
            }
        )

    write_jsonl(OUT / "state_code_hydration_candidates.jsonl", records)
    status_counts = Counter(r.get("hydration_status") for r in records)
    language_counts = Counter(r.get("language_family") for r in records)
    lifecycle_counts = Counter(r.get("coarse_lifecycle_state") for r in records)
    blocked_counts: Counter[str] = Counter()
    for row in records:
        blocked_counts.update(row.get("blocked_reasons") or [])
    summary = {
        "stage": STAGE,
        "decision": "coarse_state_code_hydration_complete_training_blocked",
        "claim_boundary": "Coarse state-code hydration only. No exact semantic rules, transition-function keys, training rows, or eval claims emitted.",
        "input_episode_candidates": len(records),
        "missing_task_window_records": missing_window,
        "hydration_status_counts": dict(status_counts),
        "language_counts": dict(language_counts),
        "coarse_lifecycle_counts": dict(lifecycle_counts),
        "blocked_reason_counts": dict(blocked_counts),
        "training_rows_emitted": 0,
        "training_allowed": False,
        "next_stage": "stage12312_transition_local_state_joiner_or_semantic_rule_assigner",
    }
    (OUT / "state_code_hydration_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

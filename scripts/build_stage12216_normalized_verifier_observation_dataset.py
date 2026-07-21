#!/usr/bin/env python3
"""Normalize Stage12206 verifier-observation support under Stage12213 QC.

This does not promote rows to patch-trace or full unbounded maintainer episodes.
It adds explicit causal single-step fields and separates raw/effective admission.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12216_normalized_verifier_observation_dataset"
SRC = ROOT / "runs/local/artifacts/stage12206_level3_passfail_training_rollup/level3_passfail_train_support_repo_capped.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

RUNNABLE_PASS = {"PASS_CURRENT_STATE", "PASS_TO_PASS", "PASS_CURRENT_BUILD_AND_RUN"}
FAIL = {"FAIL_CURRENT_STATE", "FAIL_TO_FAIL", "FAIL_TO_PASS"}
BUILD_ONLY = {"PASS_CURRENT_BUILD"}


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if line:
                yield line_no, json.loads(line)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def strip_candidates(candidate_action_set: Any) -> list[dict[str, Any]]:
    if isinstance(candidate_action_set, dict):
        raw = candidate_action_set.get("candidate_actions") or candidate_action_set.get("candidates") or candidate_action_set.get("actions") or []
    elif isinstance(candidate_action_set, list):
        raw = candidate_action_set
    else:
        raw = []
    out = []
    for idx, c in enumerate(raw):
        if not isinstance(c, dict):
            continue
        role = c.get("role") or c.get("semantic_role") or c.get("value") or c.get("canonical_value") or "unknown"
        values = {str(role), str(c.get("value")), str(c.get("canonical_value")), str(c.get("semantic_role")), str(c.get("text"))}
        if "ENV_BLOCKED" in values or "environment or dependency prevented trustworthy verifier interpretation" in values:
            continue
        action_type = "VERIFY"
        out.append({
            "action_id": str(c.get("action_id") or c.get("label") or f"C{idx}"),
            "action_type": action_type,
            "role": str(role),
            "description": c.get("description") or c.get("text") or str(role),
            "label": c.get("label"),
            "artifact_type": c.get("artifact_type"),
            "is_chosen": bool(c.get("is_chosen")),
            "negative_kind": c.get("negative_kind"),
        })
    return out


def chosen_action(row: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    observed = row.get("observed_action") or {}
    chosen_id = observed.get("action_id")
    for c in candidates:
        if c.get("is_chosen") or c.get("action_id") == chosen_id:
            return dict(c)
    transition = row.get("verifier_transition") or row.get("verifier_status")
    return {
        "action_id": str(chosen_id or stable_id("chosen", row.get("episode_id"))),
        "action_type": "VERIFY",
        "role": str(transition),
        "description": f"Observed verifier transition {transition}",
        "is_chosen": True,
    }


def normalize(row: dict[str, Any], line_no: int) -> dict[str, Any]:
    transition = str(row.get("verifier_transition") or row.get("verifier_status") or "")
    if row.get("verifier_transition") and row.get("verifier_status") and row.get("verifier_transition") != row.get("verifier_status"):
        # Stage12205 rows sometimes preserve original PASS_CURRENT_STATE status while the transition is PASS_TO_PASS.
        # For normalized verifier-transition training, make the canonical status equal the transition.
        row = dict(row)
        row["stage12216_original_verifier_status"] = row.get("verifier_status")
        row["verifier_status"] = transition
    command_result = row.get("command_result") or {}
    state_update = row.get("state_update") or {}
    stop_decision = row.get("stop_decision") or {}
    candidates = strip_candidates(row.get("candidate_action_set"))
    chosen = chosen_action(row, candidates)
    language_family = row.get("language_family") or row.get("language") or "unknown"
    root_id = row.get("root_id") or command_result.get("cwd") or row.get("episode_id")
    source_stage = row.get("source_stage") or row.get("rollup_source_stage") or "unknown"
    source_ref = row.get("rollup_source_ref") or row.get("source_log_path") or row.get("source_bundle_id")
    split = "train_support"
    is_build_only = transition in BUILD_ONLY
    is_runnable_verifier = transition in RUNNABLE_PASS and not is_build_only
    is_failure = transition in FAIL
    no_patch_reason = "verifier_observation_only_no_edit_or_patch_action_in_source_record"
    command_text = command_result.get("command") or ""
    if not str(command_text).strip():
        normalized = dict(row)
        normalized["stage12216_blocker"] = "missing_command_text"
        normalized["stage12216_source_line"] = line_no
        return normalized
    event_ids = {
        "state_before": stable_id("stage12216_state_before", root_id, row.get("episode_id")),
        "action": stable_id("stage12216_action", row.get("episode_id"), chosen),
        "observation": command_result.get("command_result_id") or stable_id("stage12216_command", row.get("episode_id"), command_result),
        "verifier": stable_id("stage12216_verifier", row.get("episode_id"), transition),
        "state_after": state_update.get("state_update_id") or stable_id("stage12216_state_after", row.get("episode_id"), state_update),
        "stop": stop_decision.get("stop_decision_id") or stable_id("stage12216_stop", row.get("episode_id"), stop_decision),
    }
    ordered_events = [
        {"event_id": event_ids["state_before"], "event_type": "STATE_BEFORE", "visible_facts": ["root/repo identity known", "selected verifier candidate available"], "root_id": root_id},
        {"event_id": event_ids["action"], "event_type": "CHOSEN_ACTION", "action": chosen},
        {"event_id": event_ids["observation"], "event_type": "COMMAND_OBSERVATION", "command_result": command_result},
        {"event_id": event_ids["verifier"], "event_type": "VERIFIER_RESULT", "verifier_result": {"verifier_status": transition, "build_only": is_build_only, "runnable_verifier_proof": is_runnable_verifier}},
        {"event_id": event_ids["state_after"], "event_type": "STATE_AFTER", "state_update": state_update},
        {"event_id": event_ids["stop"], "event_type": "STOP_CONTINUE_DECISION", "stop_decision": stop_decision},
    ]
    state_before = {
        "state_id": event_ids["state_before"],
        "root_id": root_id,
        "repo_family": row.get("repo_family"),
        "language_family": language_family,
        "split": split,
        "known_facts": [
            "source root or authoritative prior log is available",
            "a selected verifier/build command is available",
        ],
        "open_questions": ["what verifier transition does this command observation support?"],
        "available_actions": [c.get("action_type") for c in candidates] or ["RUN_SELECTED_VERIFIER"],
        "selected_test_anchor": row.get("selected_test_anchor"),
        "verifier_anchor": row.get("verifier_anchor"),
    }
    state_after = {
        "state_id": event_ids["state_after"],
        "root_id": root_id,
        "verifier_transition": transition,
        "build_only": is_build_only,
        "runnable_verifier_proof": is_runnable_verifier,
        "failure_observed": is_failure,
        "new_facts": state_update.get("new_facts") or [f"verifier transition observed: {transition}"],
        "invalidated_claims": state_update.get("invalidated_claims") or [],
        "remaining_blockers": state_update.get("remaining_blockers") or [],
        "continue_or_stop": stop_decision.get("continue_or_stop") or "CONTINUE",
    }
    patch_trace = {
        "has_patch_trace": False,
        "patch_diff": None,
        "patch_apply_evidence": None,
        "patch_minimality": None,
        "no_patch_reason": no_patch_reason,
        "counts_toward_patch_trace_floor": False,
    }
    normalized = dict(row)
    filtered_candidate_action_set = {
        "candidate_set_id": stable_id("stage12216_candidates", row.get("episode_id"), candidates),
        "chosen_action_id": chosen.get("action_id"),
        "candidate_actions": candidates,
    }
    normalized.update({
        "stage12216_source_line": line_no,
        "admission_level_raw": row.get("admission_level") or "verifier_observation_support",
        "admission_level_effective": "level_3_single_step_closed_loop_no_patch_verifier_observation",
        "counts_toward_unbounded_patch_trace_floor": False,
        "counts_toward_runnable_verifier_proof": is_runnable_verifier,
        "counts_toward_build_only_floor": is_build_only,
        "controlled_fixture_like": str(row.get("repo_family") or "").startswith("stage") or "controlled" in str(source_stage),
        "language_family": language_family,
        "split": split,
        "source_stage": source_stage,
        "source_ref": source_ref,
        "ordered_events": ordered_events,
        "events": ordered_events,
        "state_before": state_before,
        "state_after": state_after,
        "candidate_action_set": filtered_candidate_action_set,
        "chosen_action": chosen,
        "candidate_action_count": len(candidates),
        "verifier_result": {
            "verifier_status": transition,
            "verifier_transition": transition,
            "command_text": command_text,
            "cwd": command_result.get("cwd"),
            "exit_code": command_result.get("returncode"),
            "stdout_excerpt": command_result.get("stdout_tail"),
            "stderr_excerpt": command_result.get("stderr_tail"),
            "stdout_sha256": command_result.get("stdout_sha256"),
            "stderr_sha256": command_result.get("stderr_sha256"),
            "build_only": is_build_only,
            "runnable_verifier_proof": is_runnable_verifier,
        },
        "patch_trace": patch_trace,
        "patch_diff": None,
        "no_patch_reason": no_patch_reason,
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
    })
    return normalized


def audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    required = ["language_family", "split", "ordered_events", "state_before", "state_after", "chosen_action", "verifier_result", "patch_trace", "no_patch_reason"]
    missing = Counter()
    blockers = Counter()
    bad_action_grammar = 0
    bad_status_consistency = 0
    env_distractors = 0
    bad_build = 0
    env_blocked = 0
    singleton = 0
    patch_floor_false = 0
    for r in rows:
        if r.get("stage12216_blocker"):
            blockers[r.get("stage12216_blocker")] += 1
            continue
        for k in required:
            if k not in r or r.get(k) in (None, "", []):
                missing[k] += 1
        if (r.get("chosen_action") or {}).get("action_type") not in {"INSPECT", "SEARCH", "RUN", "EDIT", "PATCH", "VERIFY", "ABSTAIN", "STOP"}:
            bad_action_grammar += 1
        if r.get("verifier_status") != r.get("verifier_transition") or (r.get("verifier_result") or {}).get("verifier_status") != r.get("verifier_transition"):
            bad_status_consistency += 1
        if r.get("verifier_transition") == "PASS_CURRENT_BUILD" and r.get("counts_toward_runnable_verifier_proof"):
            bad_build += 1
        if str(r.get("verifier_transition")) == "ENV_BLOCKED":
            env_blocked += 1
        cs = r.get("candidate_action_set") or {}
        actions = cs.get("candidate_actions") if isinstance(cs, dict) else cs
        if not isinstance(actions, list) or len(actions) < 2:
            singleton += 1
        elif any(isinstance(a, dict) and a.get("role") == "ENV_BLOCKED" for a in actions):
            env_distractors += 1
        if r.get("patch_trace", {}).get("counts_toward_patch_trace_floor") is False:
            patch_floor_false += 1
    return {
        "blocked_rows": dict(blockers),
        "missing_required_fields": dict(missing),
        "bad_action_grammar_count": bad_action_grammar,
        "bad_status_consistency_count": bad_status_consistency,
        "env_blocked_distractor_candidate_sets": env_distractors,
        "bad_pass_current_build_runnable_count": bad_build,
        "env_blocked_count": env_blocked,
        "singleton_candidate_sets": singleton,
        "patch_trace_floor_false_count": patch_floor_false,
        "language_family_counts": dict(Counter(r.get("language_family") for r in rows)),
        "split_counts": dict(Counter(r.get("split") for r in rows)),
        "effective_admission_counts": dict(Counter(r.get("admission_level_effective") for r in rows)),
        "transition_counts": dict(Counter(r.get("verifier_transition") for r in rows)),
        "runnable_verifier_proof_count": sum(1 for r in rows if r.get("counts_toward_runnable_verifier_proof")),
        "build_only_count": sum(1 for r in rows if r.get("counts_toward_build_only_floor")),
        "controlled_fixture_like_count": sum(1 for r in rows if r.get("controlled_fixture_like")),
        "repo_family_counts_top20": Counter(str(r.get("repo_family")) for r in rows).most_common(20),
    }


def main() -> int:
    all_rows = [normalize(row, line_no) for line_no, row in iter_jsonl(SRC)]
    blocked_rows = [r for r in all_rows if r.get("stage12216_blocker")]
    rows = [r for r in all_rows if not r.get("stage12216_blocker")]
    rows.sort(key=lambda r: (str(r.get("language_family")), str(r.get("repo_family")), str(r.get("episode_id"))))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT_DIR / "normalized_verifier_observation_records.jsonl", rows)
    write_jsonl(OUT_DIR / "blocked_normalization_rows.jsonl", blocked_rows)
    report = audit(rows)
    summary = {
        "stage": STAGE,
        "decision": "normalized_verifier_observation_dataset_ready" if not report["missing_required_fields"] and report["env_blocked_count"] == 0 and report["bad_pass_current_build_runnable_count"] == 0 else "normalization_has_blockers",
        "source_rollup": str(SRC),
        "input_row_count": len(all_rows),
        "row_count": len(rows),
        "blocked_row_count": len(blocked_rows),
        "quality_control_reference": "runs/local/artifacts/stage12213_level3_dataset_quality_control/LEVEL3_DATASET_QUALITY_CONTROL_STAGE12213.md",
        "training_allowed": False,
        "claim_boundary": "Normalized verifier-observation support only. Patch-trace and full closed-loop maintainer training remain blocked until same-source patch/verifier rows exist.",
        "audit": report,
        "artifact_paths": {"records": str(OUT_DIR / "normalized_verifier_observation_records.jsonl"), "blocked": str(OUT_DIR / "blocked_normalization_rows.jsonl"), "summary": str(OUT_DIR / "summary.json")},
    }
    write_json(OUT_DIR / "summary.json", summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["decision"] == "normalized_verifier_observation_dataset_ready" else 2

if __name__ == "__main__":
    raise SystemExit(main())

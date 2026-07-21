#!/usr/bin/env python3
"""Run a tiny CPU-only verifier rehydration smoke for Stage12217 top queue.

This stage does not mutate repos intentionally and does not train. It captures
same-root command observations for a small set of patch-context candidates.
"""
from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12219_patch_trace_rehydration_smoke"
QUEUE = ROOT / "runs/local/artifacts/stage12217_patch_trace_verifier_rehydration_queue/top10_patch_trace_verifier_rehydration_queue.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
MAX_RUNS = 5
TIMEOUT = 120

ENV_BLOCK_PATTERNS = [
    "modulenotfounderror", "importerror", "no module named", "not found", "could not find", "missing", "requires", "not installed", "failed to import", "cannot import", "network", "connection", "api key", "permission denied"
]


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, 1):
            if line.strip():
                yield line_no, json.loads(line)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def sanitize_argv(item: dict[str, Any]) -> list[str] | None:
    argv = item.get("proposed_command_argv")
    if not argv:
        return None
    argv = list(argv)
    if len(argv) >= 4 and argv[:3] == ["python", "-m", "pytest"]:
        if "-q" not in argv:
            argv.insert(3, "-q")
        argv.extend(["-o", "cache_dir=/data/tmp/stage12219_pytest_cache"])
    return argv


def classify(rc: int | None, stdout: str, stderr: str) -> str:
    combined = f"{stdout}\n{stderr}".lower()
    if rc == 0:
        return "PASS_CURRENT_STATE"
    if any(p in combined for p in ENV_BLOCK_PATTERNS):
        return "ENV_BLOCKED"
    return "FAIL_CURRENT_STATE"


def run_one(item: dict[str, Any]) -> dict[str, Any]:
    cwd = Path(item.get("proposed_cwd") or item.get("root_id") or "")
    argv = sanitize_argv(item)
    if not argv:
        return {"queue_item": item, "skipped": True, "skip_reason": "missing_command"}
    if not cwd.exists():
        return {"queue_item": item, "skipped": True, "skip_reason": "cwd_missing"}
    env = os.environ.copy()
    env.update({
        "CUDA_VISIBLE_DEVICES": "",
        "PYTHONDONTWRITEBYTECODE": "1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "WANDB_DISABLED": "true",
        "OPENAI_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
    })
    start = time.time()
    try:
        proc = subprocess.run(argv, cwd=str(cwd), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=TIMEOUT)
        return {"queue_item": item, "argv": argv, "cwd": str(cwd), "returncode": proc.returncode, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-4000:], "duration_sec": round(time.time()-start, 3)}
    except subprocess.TimeoutExpired as e:
        return {"queue_item": item, "argv": argv, "cwd": str(cwd), "returncode": 124, "stdout": str(e.stdout or "")[-4000:], "stderr": (str(e.stderr or "") + "\nTIMEOUT")[-4000:], "duration_sec": round(time.time()-start, 3)}


def record(obs: dict[str, Any]) -> dict[str, Any] | None:
    if obs.get("skipped"):
        return None
    item = obs["queue_item"]
    transition = classify(obs.get("returncode"), obs.get("stdout") or "", obs.get("stderr") or "")
    if transition == "ENV_BLOCKED":
        return None
    eid = stable_id("stage12219_episode", item.get("episode_id"), obs.get("argv"), obs.get("returncode"), obs.get("stdout"), obs.get("stderr"))
    cmd_id = stable_id("stage12219_command", eid)
    chosen = "A" if transition == "PASS_CURRENT_STATE" else "B"
    candidates = [
        {"action_id":"A", "action_type":"VERIFY", "role":"PASS_CURRENT_STATE", "description":"same-root verifier command passed", "is_chosen": transition == "PASS_CURRENT_STATE"},
        {"action_id":"B", "action_type":"VERIFY", "role":"FAIL_CURRENT_STATE", "description":"same-root verifier command failed due source/test behavior", "is_chosen": transition == "FAIL_CURRENT_STATE"},
        {"action_id":"C", "action_type":"VERIFY", "role":"PASS_CURRENT_BUILD", "description":"build/collection only; runnable verifier not proven", "is_chosen": False},
        {"action_id":"D", "action_type":"ABSTAIN", "role":"INSUFFICIENT_EVIDENCE", "description":"observation is not enough to judge verifier transition", "is_chosen": False},
    ]
    return {
        "episode_id": eid,
        "source_stage": STAGE,
        "source_stage12201_episode_id": item.get("episode_id"),
        "admission_level_raw": "level_2_patch_context_no_execution_plus_rehydrated_verifier_observation",
        "admission_level_effective": "level_3_single_step_closed_loop_with_patch_context_verifier_observation",
        "root_id": item.get("root_id"),
        "repo_family": item.get("repo_family"),
        "language_family": item.get("language_family"),
        "split": "train_support",
        "repo_commit_before": item.get("repo_commit_before"),
        "repo_commit_after": item.get("repo_commit_after"),
        "patch_trace": {"has_patch_trace": True, "patch_diff": item.get("patch_diff_ref"), "patch_diff_digest": item.get("patch_diff_digest"), "patch_apply_evidence": "not_applied_by_stage12219_readonly_smoke", "counts_toward_patch_trace_floor": False},
        "selected_test_anchor": item.get("selected_test_candidate"),
        "candidate_action_set": {"candidate_set_id": stable_id("stage12219_candidates", eid), "chosen_action_id": chosen, "candidate_actions": candidates},
        "candidate_action_count": len(candidates),
        "chosen_action": next(c for c in candidates if c["action_id"] == chosen),
        "command_result": {"command_result_id": cmd_id, "command": " ".join(shlex.quote(x) for x in obs.get("argv", [])), "cwd": obs.get("cwd"), "returncode": obs.get("returncode"), "duration_sec": obs.get("duration_sec"), "stdout_tail": obs.get("stdout"), "stderr_tail": obs.get("stderr"), "source_kind":"stage12219_guarded_rehydration_smoke"},
        "verifier_status": transition,
        "verifier_transition": transition,
        "verifier_result": {"verifier_status": transition, "verifier_transition": transition, "command_text": " ".join(shlex.quote(x) for x in obs.get("argv", [])), "cwd": obs.get("cwd"), "exit_code": obs.get("returncode"), "stdout_excerpt": obs.get("stdout"), "stderr_excerpt": obs.get("stderr"), "build_only": False, "runnable_verifier_proof": transition == "PASS_CURRENT_STATE"},
        "state_before": {"root_id": item.get("root_id"), "repo_family": item.get("repo_family"), "language_family": item.get("language_family"), "known_facts":["same-source patch diff exists", "selected verifier candidate exists"], "open_questions":["does the local same-root verifier command execute successfully?"]},
        "state_after": {"root_id": item.get("root_id"), "verifier_transition": transition, "failure_observed": transition == "FAIL_CURRENT_STATE", "new_facts":[f"same-root verifier rehydration observed {transition}"], "remaining_blockers": [] if transition == "PASS_CURRENT_STATE" else ["repair or diagnose current-state verifier failure"]},
        "ordered_events": ["STATE_BEFORE", "VERIFY", "COMMAND_OBSERVATION", "VERIFIER_RESULT", "STATE_AFTER", "STOP_CONTINUE_DECISION"],
        "stop_decision": {"continue_or_stop":"CONTINUE", "reason":"rehydration smoke is evidence, not full clean replay acceptance"},
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "training_allowed": False,
    }


def main() -> int:
    items = [r for _, r in iter_jsonl(QUEUE)][:MAX_RUNS]
    observations = [run_one(i) for i in items]
    records = []
    diagnostics = []
    for o in observations:
        r = record(o)
        if r is None:
            diagnostics.append(o)
        else:
            records.append(r)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT_DIR / "rehydration_observations.jsonl", observations)
    write_jsonl(OUT_DIR / "rehydrated_patch_verifier_records.jsonl", records)
    write_jsonl(OUT_DIR / "diagnostic_blocked_rehydration.jsonl", diagnostics)
    summary = {
        "stage": STAGE,
        "decision": "rehydration_smoke_records_materialized" if records else "blocked_no_rehydrated_records",
        "candidate_count": len(items),
        "record_count": len(records),
        "diagnostic_count": len(diagnostics),
        "transition_counts": dict(Counter(r.get("verifier_transition") for r in records)),
        "diagnostic_transition_counts": dict(Counter(classify(o.get("returncode"), o.get("stdout") or "", o.get("stderr") or "") if not o.get("skipped") else o.get("skip_reason") for o in diagnostics)),
        "language_counts": dict(Counter(r.get("language_family") for r in records)),
        "tests_executed": True,
        "training_allowed": False,
        "gpu_policy": "CUDA_VISIBLE_DEVICES empty; CPU-only commands",
        "claim_boundary": "Smoke rehydration only. Patch diff was not applied/replayed by this stage, so records do not yet count toward strict patch-trace floor.",
        "artifact_paths": {"records": str(OUT_DIR / "rehydrated_patch_verifier_records.jsonl"), "observations": str(OUT_DIR / "rehydration_observations.jsonl"), "diagnostics": str(OUT_DIR / "diagnostic_blocked_rehydration.jsonl")},
    }
    write_json(OUT_DIR / "summary.json", summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

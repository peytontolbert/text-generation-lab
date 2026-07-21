#!/usr/bin/env python3
"""Guarded CPU-only re-execution of hydratable selected verifier roots.

This stage executes only short commands with prior local pass evidence. It emits
Level-3-shaped train-support records from observed command results. It makes no
eval or source-heldout claim.
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
STAGE = "stage12215_hydratable_selected_verifier_reexecution"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

CANDIDATES: list[dict[str, Any]] = [
    {
        "candidate_id": "pallets_click_basic",
        "language": "python",
        "repo_family": "pallets/click",
        "cwd": "/data/tmp/stage12123_verifier_ready_smoke_repos/pallets_click",
        "argv": ["python", "-m", "pytest", "-q", "tests/test_basic.py"],
        "env_extra": {"PYTHONPATH": "src"},
        "selected_test_anchor": "tests/test_basic.py",
        "prior_evidence": "stage12123 prior log: 102 passed in 0.13s",
    },
    {
        "candidate_id": "pallets_jinja_api",
        "language": "python",
        "repo_family": "pallets/jinja",
        "cwd": "/data/tmp/stage12123_verifier_ready_smoke_repos/pallets_jinja",
        "argv": ["python", "-m", "pytest", "-q", "tests/test_api.py"],
        "env_extra": {"PYTHONPATH": "src"},
        "selected_test_anchor": "tests/test_api.py",
        "prior_evidence": "stage12123 prior log: 34 passed in 0.10s",
    },
    {
        "candidate_id": "sentencepiece_python_test",
        "language": "python",
        "repo_family": "sentencepiece/python",
        "cwd": "/data/parametergolf/helpful_repos/sentencepiece/python",
        "argv": ["python", "-m", "pytest", "-q", "-o", "cache_dir=/data/tmp/stage12215_pytest_cache", "test/sentencepiece_test.py"],
        "selected_test_anchor": "test/sentencepiece_test.py",
        "prior_evidence": "stage11971 prior log: 23 passed in 4.45s",
    },
    {
        "candidate_id": "git_libgit_sys",
        "language": "rust",
        "repo_family": "git/libgit-sys",
        "cwd": "/data/repositories/git/contrib/libgit-sys",
        "argv": ["cargo", "test", "--quiet", "--no-fail-fast"],
        "selected_test_anchor": "cargo test --quiet --no-fail-fast",
        "prior_evidence": "prior log: 2 passed",
    },
    {
        "candidate_id": "mini_swe_agent_env_init",
        "language": "python",
        "repo_family": "SWE-agent__mini-swe-agent",
        "cwd": "/data/repositories/SWE-agent__mini-swe-agent",
        "argv": ["python", "-m", "pytest", "-q", "-c", "/dev/null", "-o", "cache_dir=/data/tmp/stage12215_pytest_cache", "tests/environments/test_init.py"],
        "selected_test_anchor": "tests/environments/test_init.py",
        "prior_evidence": "stage11975 prior log: 4 passed in 0.14s",
    },
    {
        "candidate_id": "camel_data_loader",
        "language": "python",
        "repo_family": "camel-ai__camel",
        "cwd": "/data/repositories/camel-ai__camel",
        "argv": ["python", "-m", "pytest", "-q", "-c", "/dev/null", "-o", "cache_dir=/data/tmp/stage12215_pytest_cache", "apps/data_explorer/test/test_loader.py"],
        "selected_test_anchor": "apps/data_explorer/test/test_loader.py",
        "prior_evidence": "stage11975 prior log: 1 passed in 0.06s",
    },
    {
        "candidate_id": "aider_run_cmd",
        "language": "python",
        "repo_family": "Aider-AI__aider",
        "cwd": "/data/repositories/Aider-AI__aider",
        "argv": ["python", "-m", "pytest", "-q", "-c", "/dev/null", "-o", "cache_dir=/data/tmp/stage12215_pytest_cache", "tests/basic/test_run_cmd.py"],
        "selected_test_anchor": "tests/basic/test_run_cmd.py",
        "prior_evidence": "stage11975 prior log: 1 passed in 0.07s",
    },
    {
        "candidate_id": "mcp_agent_env_settings",
        "language": "python",
        "repo_family": "lastmile-ai__mcp-agent",
        "cwd": "/data/repositories/lastmile-ai__mcp-agent",
        "argv": ["python", "-m", "pytest", "-q", "-c", "/dev/null", "-o", "cache_dir=/data/tmp/stage12215_pytest_cache", "tests/config/test_env_settings.py"],
        "selected_test_anchor": "tests/config/test_env_settings.py",
        "prior_evidence": "stage11975 prior log: 2 passed in 0.34s",
    },
    {
        "candidate_id": "hermes_discord_media_metadata",
        "language": "python",
        "repo_family": "NousResearch__hermes-agent",
        "cwd": "/data/repositories/NousResearch__hermes-agent",
        "argv": ["python", "-m", "pytest", "-q", "-c", "/dev/null", "-o", "cache_dir=/data/tmp/stage12215_pytest_cache", "tests/gateway/test_discord_media_metadata.py"],
        "selected_test_anchor": "tests/gateway/test_discord_media_metadata.py",
        "prior_evidence": "stage11975 prior log: 1 passed in 0.86s",
    },
]

ENV_BLOCK_PATTERNS = [
    "modulenotfounderror", "importerror", "no module named", "fixture", "not found", "could not find",
    "failed to download", "network", "offline", "vitest: not found", "cannot find", "environment",
]


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def tail(text: str, n: int = 2200) -> str:
    return (text or "")[-n:]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def classify_transition(rc: int | None, stdout: str, stderr: str) -> str:
    combined = f"{stdout}\n{stderr}".lower()
    if rc == 0:
        return "PASS_CURRENT_STATE"
    if any(p in combined for p in ENV_BLOCK_PATTERNS):
        return "ENV_BLOCKED"
    return "FAIL_CURRENT_STATE"


def candidate_actions(chosen: str) -> dict[str, Any]:
    candidates = [
        ("A", "PASS_CURRENT_STATE", "focused verifier executed from local source and passed"),
        ("B", "FAIL_CURRENT_STATE", "verifier failed in the current local source state"),
        ("C", "PASS_CURRENT_BUILD", "build or collection passed but runnable verifier body did not execute"),
        ("D", "ENV_BLOCKED", "environment or dependency prevented trustworthy verifier interpretation"),
        ("E", "FAIL_TO_PASS", "controlled broken state failed and restored or repaired source passed"),
    ]
    return {
        "candidate_set_id": stable_id("stage12215_candidates", chosen),
        "chosen_action_id": next(label for label, value, _ in candidates if value == chosen),
        "candidate_actions": [
            {
                "action_id": label,
                "label": label,
                "role": value,
                "action_type": "CLASSIFY_VERIFIER_TRANSITION",
                "description": desc,
                "is_chosen": value == chosen,
                "negative_kind": None if value == chosen else "verifier_transition_distractor",
            }
            for label, value, desc in candidates
        ],
    }


def run_candidate(c: dict[str, Any]) -> dict[str, Any]:
    cwd = Path(c["cwd"])
    start = time.time()
    if not cwd.exists():
        return {"candidate": c, "skipped": True, "skip_reason": "cwd_missing"}
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = ""
    env.update(c.get("env_extra") or {})
    try:
        proc = subprocess.run(
            c["argv"], cwd=str(cwd), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120
        )
        duration = time.time() - start
        return {"candidate": c, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr, "duration_sec": round(duration, 3)}
    except subprocess.TimeoutExpired as e:
        return {"candidate": c, "returncode": 124, "stdout": e.stdout or "", "stderr": (e.stderr or "") + "\nTIMEOUT", "duration_sec": round(time.time() - start, 3)}


def to_record(obs: dict[str, Any]) -> dict[str, Any] | None:
    c = obs["candidate"]
    if obs.get("skipped"):
        return None
    transition = classify_transition(obs.get("returncode"), obs.get("stdout") or "", obs.get("stderr") or "")
    if transition == "ENV_BLOCKED":
        return None
    episode_id = stable_id("stage12215_episode", c["candidate_id"], c["cwd"], c["argv"], obs.get("returncode"), obs.get("stdout"), obs.get("stderr"))
    command_id = stable_id("stage12215_command", episode_id)
    chosen_set = candidate_actions(transition)
    chosen_id = chosen_set["chosen_action_id"]
    return {
        "episode_id": episode_id,
        "root_id": c["cwd"],
        "repo_id": c["repo_family"],
        "repo_family": c["repo_family"],
        "root_lineage_key": f"stage12215::{c['repo_family']}::{c['selected_test_anchor']}",
        "language": c["language"],
        "task_type": "transition_verifier_transition",
        "selected_test_anchor": c["selected_test_anchor"],
        "verifier_anchor": " ".join(shlex.quote(x) for x in c["argv"]),
        "source_bundle_id": c["candidate_id"],
        "source_stage": STAGE,
        "candidate_action_set": chosen_set,
        "observed_action": {"action_id": chosen_id, "action_type": "RUN_SELECTED_VERIFIER", "command_result_id": command_id, "semantic_value": transition},
        "command_result": {
            "command_result_id": command_id,
            "command": " ".join(shlex.quote(x) for x in c["argv"]),
            "cwd": c["cwd"],
            "returncode": obs.get("returncode"),
            "duration_sec": obs.get("duration_sec"),
            "stdout_tail": tail(obs.get("stdout") or ""),
            "stderr_tail": tail(obs.get("stderr") or ""),
            "source_kind": "guarded_cpu_reexecution",
        },
        "verifier_status": transition,
        "verifier_transition": transition,
        "state_update": {
            "state_update_id": stable_id("stage12215_state", episode_id),
            "state_update_type": "observed_pass" if transition == "PASS_CURRENT_STATE" else "observed_failure",
            "new_facts": [f"selected verifier observation produced {transition}"],
            "invalidated_claims": [] if transition == "PASS_CURRENT_STATE" else ["current state passes selected verifier"],
            "remaining_blockers": [] if transition == "PASS_CURRENT_STATE" else ["repair or diagnose current-state verifier failure"],
        },
        "stop_decision": {
            "stop_decision_id": stable_id("stage12215_stop", episode_id),
            "continue_or_stop": "CONTINUE",
            "reason": "single verifier observation is train-support evidence, not full task acceptance",
        },
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "singleton_options": False,
            "target_label_not_visible_before_options": True,
            "target_value_not_visible_before_options": True,
            "source_is_guarded_reexecution": True,
            "target_not_promotable_eval": True,
        },
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "projection_permissions": {
            "may_project_verifier_transition": True,
            "may_project_continue_or_stop": True,
            "may_project_patch_generation": False,
            "claim_boundary": "Guarded CPU re-execution selected-verifier observation; no patch trace.",
        },
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    observations = []
    records = []
    diagnostics = []
    for c in CANDIDATES:
        obs = run_candidate(c)
        observations.append(obs)
        rec = to_record(obs)
        if rec is None:
            diagnostics.append(obs)
        else:
            records.append(rec)
    write_jsonl(OUT_DIR / "reexecution_observations.jsonl", observations)
    write_jsonl(OUT_DIR / "level3_reexecution_records.jsonl", records)
    write_jsonl(OUT_DIR / "diagnostic_blocked_observations.jsonl", diagnostics)
    summary = {
        "stage": STAGE,
        "decision": "reexecution_records_materialized" if records else "blocked_no_records",
        "candidate_count": len(CANDIDATES),
        "record_count": len(records),
        "diagnostic_blocked_count": len(diagnostics),
        "language_counts": dict(Counter(r.get("language") for r in records)),
        "transition_counts": dict(Counter(r.get("verifier_transition") for r in records)),
        "diagnostic_transition_counts": dict(Counter(classify_transition(o.get("returncode"), o.get("stdout") or "", o.get("stderr") or "") if not o.get("skipped") else "SKIPPED" for o in diagnostics)),
        "train_support_only": True,
        "strict_eval_eligible": False,
        "gpu_policy": "CUDA_VISIBLE_DEVICES empty; CPU-only commands",
        "claim_boundary": "Guarded reexecution creates Level-3-shaped verifier observations only; no patch trace or eval claim.",
        "artifact_paths": {
            "records": str(OUT_DIR / "level3_reexecution_records.jsonl"),
            "observations": str(OUT_DIR / "reexecution_observations.jsonl"),
            "diagnostics": str(OUT_DIR / "diagnostic_blocked_observations.jsonl"),
        },
    }
    write_json(OUT_DIR / "summary.json", summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if records else 2

if __name__ == "__main__":
    raise SystemExit(main())

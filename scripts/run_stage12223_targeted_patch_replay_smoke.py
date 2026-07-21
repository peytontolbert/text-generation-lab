#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12223_targeted_patch_replay_smoke"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
TIMEOUT = 160

CANDIDATES = [
    {
        "episode_id": "stage12201_episode_5d3be5dbb55491ad",
        "repo_family": "mem0",
        "language_family": "python",
        "repo": "/arxiv/repositories/mem0",
        "before": "7a9f03af3f7a292bcf937c8d9e64ba1a5e9fa46b",
        "after": "2ac3f3956ae581ac327da8b9832835f50bcffdea",
        "patch": str(ROOT / "runs/local/artifacts/stage12201_patch_evidence_recovery/diffs/02373d63dbfba76926cd82e1347f9c7fbdf5a135158984fdc1ce23cac86a504b.patch"),
        "subdir": "cli/python",
        "pythonpath_rel": ["cli/python/src"],
        "argv": ["python", "-m", "pytest", "-q", "-c", "/dev/null", "-o", "cache_dir={cache}", "tests/test_telemetry.py"],
        "reason": "changed files include mem0_cli telemetry implementation and telemetry tests",
    },
    {
        "episode_id": "stage12201_episode_b7a09c7d7b84627d",
        "repo_family": "unsloth",
        "language_family": "python",
        "repo": "/arxiv/repositories/unsloth",
        "before": "420799b61ef35d6cfd87c4f4b02c98152fdf6599",
        "after": "76a2b9edf160d68208dc30c02c6523bc6551f950",
        "patch": str(ROOT / "runs/local/artifacts/stage12201_patch_evidence_recovery/diffs/4553f23571709ebbb9886a3685b5857440fa100d13b977cddc17e3bc017fb389.patch"),
        "subdir": "studio/backend",
        "pythonpath_rel": ["studio/backend"],
        "argv": [
            "python",
            "-m",
            "pytest",
            "-q",
            "-c",
            "/dev/null",
            "-o",
            "cache_dir={cache}",
            "tests/test_llama_cpp_mtp_detection.py",
            "tests/test_inference_model_validation.py",
        ],
        "reason": "changed files include inference implementation and matching tests",
    },
]

ENV_BLOCK = ["modulenotfounderror", "importerror", "no module named", "not installed", "network", "connection", "api key"]


def sid(prefix: str, *parts: Any) -> str:
    raw = "\n".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return prefix + "_" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def run_cmd(argv: list[str], cwd: Path | None = None, env_extra: dict[str, str] | None = None, timeout: int = TIMEOUT) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(
        {
            "CUDA_VISIBLE_DEVICES": "",
            "PYTHONDONTWRITEBYTECODE": "1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "WANDB_DISABLED": "true",
            "OPENAI_API_KEY": "",
            "ANTHROPIC_API_KEY": "",
        }
    )
    if env_extra:
        env.update(env_extra)
    start = time.time()
    try:
        proc = subprocess.run(argv, cwd=str(cwd) if cwd else None, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return {
            "argv": argv,
            "command": " ".join(shlex.quote(x) for x in argv),
            "cwd": str(cwd) if cwd else None,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-6000:],
            "stderr_tail": proc.stderr[-6000:],
            "duration_sec": round(time.time() - start, 3),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "argv": argv,
            "command": " ".join(shlex.quote(x) for x in argv),
            "cwd": str(cwd) if cwd else None,
            "returncode": 124,
            "stdout_tail": str(exc.stdout or "")[-6000:],
            "stderr_tail": (str(exc.stderr or "") + "\nTIMEOUT")[-6000:],
            "duration_sec": round(time.time() - start, 3),
        }


def clone_at(cand: dict[str, Any], work_root: Path, label: str, commit: str) -> tuple[Path, list[dict[str, Any]]]:
    dst = work_root / f"{cand['repo_family']}_{label}"
    return dst, [
        run_cmd(["git", "clone", "--shared", cand["repo"], str(dst)], timeout=180),
        run_cmd(["git", "-C", str(dst), "checkout", "--detach", commit], timeout=120),
    ]


def classify(obs: dict[str, Any]) -> str:
    if obs.get("returncode") == 0:
        return "PASS_CURRENT_STATE"
    combined = (str(obs.get("stdout_tail", "")) + "\n" + str(obs.get("stderr_tail", ""))).lower()
    if any(token in combined for token in ENV_BLOCK):
        return "ENV_BLOCKED"
    return "FAIL_CURRENT_STATE"


def render_argv(cand: dict[str, Any], cache_name: str) -> list[str]:
    return [str(x).format(cache=f"/data/tmp/{cache_name}") for x in cand["argv"]]


def verify(cand: dict[str, Any], clone: Path, phase: str) -> dict[str, Any]:
    cwd = clone / cand["subdir"]
    pythonpath = ":".join(str(clone / rel) for rel in cand["pythonpath_rel"])
    obs = run_cmd(render_argv(cand, f"stage12223_{cand['repo_family']}_{phase}_cache"), cwd=cwd, env_extra={"PYTHONPATH": pythonpath}, timeout=TIMEOUT)
    obs["pythonpath"] = pythonpath
    return obs


def replay_candidate(cand: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    work_root = Path(tempfile.mkdtemp(prefix=f"stage12223_{cand['repo_family']}_", dir="/data/tmp"))
    setup_logs: list[dict[str, Any]] = []
    before_dir, logs = clone_at(cand, work_root, "before", cand["before"])
    setup_logs.extend(logs)
    after_dir, logs = clone_at(cand, work_root, "after", cand["after"])
    setup_logs.extend(logs)
    patched_dir, logs = clone_at(cand, work_root, "before_plus_patch", cand["before"])
    setup_logs.extend(logs)

    apply_check = run_cmd(["git", "-C", str(patched_dir), "apply", "--check", cand["patch"]], timeout=120)
    apply_patch = run_cmd(["git", "-C", str(patched_dir), "apply", cand["patch"]], timeout=120) if apply_check["returncode"] == 0 else None

    before_obs = verify(cand, before_dir, "before")
    after_obs = verify(cand, after_dir, "after")
    patched_obs = verify(cand, patched_dir, "patched") if apply_patch and apply_patch["returncode"] == 0 else None
    statuses = {
        "before": classify(before_obs),
        "after": classify(after_obs),
        "before_plus_patch": classify(patched_obs) if patched_obs else "NOT_RUN",
    }
    diagnostic = {
        "candidate": cand,
        "work_root": str(work_root),
        "setup_logs": setup_logs,
        "apply_check": apply_check,
        "apply_patch": apply_patch,
        "observations": {"before": before_obs, "after": after_obs, "before_plus_patch": patched_obs},
        "statuses": statuses,
    }
    if any(log["returncode"] != 0 for log in setup_logs) or not (apply_patch and apply_patch["returncode"] == 0):
        diagnostic["blocker"] = "setup_or_patch_apply_failed"
        return None, diagnostic
    if any(v in {"ENV_BLOCKED", "NOT_RUN"} for v in statuses.values()):
        diagnostic["blocker"] = "env_blocked_or_not_run"
        return None, diagnostic
    if statuses["before"] == "FAIL_CURRENT_STATE" and statuses["before_plus_patch"] == "PASS_CURRENT_STATE" and statuses["after"] == "PASS_CURRENT_STATE":
        transition = "FAIL_TO_PASS"
        fail_floor = True
    elif statuses["before"] == "PASS_CURRENT_STATE" and statuses["before_plus_patch"] == "PASS_CURRENT_STATE" and statuses["after"] == "PASS_CURRENT_STATE":
        transition = "PASS_TO_PASS"
        fail_floor = False
    else:
        transition = "PATCH_REPLAY_OBSERVED_NONPASS"
        fail_floor = False
    episode_id = sid("stage12223_episode", cand["episode_id"], statuses, transition)
    record = {
        "episode_id": episode_id,
        "source_stage": STAGE,
        "source_stage12201_episode_id": cand["episode_id"],
        "admission_level_effective": "level_3_patch_trace_replay_verifier_observation",
        "root_id": cand["repo"],
        "repo_family": cand["repo_family"],
        "language_family": cand["language_family"],
        "split": "train_support",
        "work_root": str(work_root),
        "repo_commit_before": cand["before"],
        "repo_commit_after": cand["after"],
        "patch_trace": {
            "has_patch_trace": True,
            "patch_diff": cand["patch"],
            "patch_apply_check": apply_check,
            "patch_apply_result": apply_patch,
            "counts_toward_patch_trace_floor": True,
            "counts_toward_fail_to_pass_floor": fail_floor,
            "semantic_patch_validation_strength": "direct_selected_verifier_tied_to_changed_paths",
        },
        "candidate_action_set": {
            "candidate_set_id": sid("stage12223_candidates", episode_id),
            "chosen_action_id": "A",
            "candidate_actions": [
                {"action_id": "A", "action_type": "APPLY_PATCH_AND_VERIFY", "role": transition, "is_chosen": True},
                {"action_id": "B", "action_type": "VERIFY_ONLY", "role": statuses["before"], "is_chosen": False},
                {"action_id": "C", "action_type": "ABSTAIN", "role": "INSUFFICIENT_PATCH_VERIFIER_EVIDENCE", "is_chosen": False},
            ],
        },
        "candidate_action_count": 3,
        "chosen_action": {"action_type": "APPLY_PATCH_AND_VERIFY", "role": transition},
        "ordered_events": [
            {"event_type": "STATE_BEFORE", "commit": cand["before"], "phase": "before"},
            {"event_type": "COMMAND", "phase": "before", "command": before_obs["command"], "cwd": before_obs["cwd"]},
            {"event_type": "COMMAND_RESULT", "phase": "before", "returncode": before_obs["returncode"], "status": statuses["before"]},
            {"event_type": "PATCH_APPLY_CHECK", "returncode": apply_check["returncode"]},
            {"event_type": "PATCH_APPLY", "returncode": apply_patch["returncode"] if apply_patch else None},
            {"event_type": "COMMAND", "phase": "before_plus_patch", "command": patched_obs["command"] if patched_obs else None, "cwd": patched_obs["cwd"] if patched_obs else None},
            {"event_type": "COMMAND_RESULT", "phase": "before_plus_patch", "returncode": patched_obs["returncode"] if patched_obs else None, "status": statuses["before_plus_patch"]},
            {"event_type": "COMMAND", "phase": "after", "command": after_obs["command"], "cwd": after_obs["cwd"]},
            {"event_type": "COMMAND_RESULT", "phase": "after", "returncode": after_obs["returncode"], "status": statuses["after"]},
            {"event_type": "VERIFIER_RESULT", "verifier_transition": transition},
            {"event_type": "STATE_AFTER", "commit": cand["after"], "verifier_transition": transition},
            {"event_type": "STOP_CONTINUE_DECISION", "continue_or_stop": "STOP" if transition == "FAIL_TO_PASS" else "CONTINUE"},
        ],
        "state_before": {"root_id": cand["repo"], "commit": cand["before"], "known_facts": [cand["reason"]]},
        "state_after": {"root_id": cand["repo"], "commit": cand["after"], "verifier_transition": transition, "new_facts": [f"{k}:{v}" for k, v in statuses.items()]},
        "verifier_transition": transition,
        "verifier_result": {"before": before_obs, "before_plus_patch": patched_obs, "after": after_obs, "verifier_transition": transition, "runnable_verifier_proof": True},
        "stop_decision": {"continue_or_stop": "STOP" if transition == "FAIL_TO_PASS" else "CONTINUE", "reason": "guarded patch replay verifier observation"},
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "training_allowed": False,
    }
    return record, diagnostic


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for cand in CANDIDATES:
        record, diagnostic = replay_candidate(cand)
        diagnostics.append(diagnostic)
        if record:
            records.append(record)

    write_jsonl(OUT / "targeted_patch_replay_records.jsonl", records)
    write_jsonl(OUT / "targeted_patch_replay_diagnostics.jsonl", diagnostics)
    summary = {
        "stage": STAGE,
        "decision": "targeted_patch_replay_records_admitted" if records else "blocked_no_targeted_patch_replay_records",
        "candidate_count": len(CANDIDATES),
        "record_count": len(records),
        "diagnostic_count": len(diagnostics) - len(records),
        "transition_counts": {k: sum(1 for r in records if r["verifier_transition"] == k) for k in sorted({r["verifier_transition"] for r in records})},
        "language_counts": {k: sum(1 for r in records if r["language_family"] == k) for k in sorted({r["language_family"] for r in records})},
        "repo_family_counts": {k: sum(1 for r in records if r["repo_family"] == k) for k in sorted({r["repo_family"] for r in records})},
        "patch_trace_floor_count": sum(1 for r in records if r["patch_trace"]["counts_toward_patch_trace_floor"]),
        "fail_to_pass_floor_count": sum(1 for r in records if r["patch_trace"]["counts_toward_fail_to_pass_floor"]),
        "training_allowed": False,
        "tests_executed": True,
        "gpu_policy": "CUDA_VISIBLE_DEVICES empty; CPU-only commands",
        "claim_boundary": "Targeted patch replay smoke. Train-support only; no strict/source-heldout claim.",
        "artifact_paths": {
            "records": str(OUT / "targeted_patch_replay_records.jsonl"),
            "diagnostics": str(OUT / "targeted_patch_replay_diagnostics.jsonl"),
        },
    }
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if records else 2


if __name__ == "__main__":
    raise SystemExit(main())

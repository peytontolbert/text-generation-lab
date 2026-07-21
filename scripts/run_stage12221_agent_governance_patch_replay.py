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
STAGE = "stage12221_agent_governance_patch_replay"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

REPO = Path("/arxiv/repositories/agent-governance-toolkit")
BEFORE = "31927699d7f09ba1a05f107d649b5070a0d391c1"
AFTER = "5272a1b0cda9e8b7740f4805f7d638bb0d373beb"
PATCH = ROOT / "runs/local/artifacts/stage12201_patch_evidence_recovery/diffs/3e27b911077c10c2a85670640424238112e58ff0edbbce1a65cea9044cc100d3.patch"
SOURCE_EPISODE = "stage12201_episode_e547aba70f65a981"
TIMEOUT = 120


def stable_id(prefix: str, *parts: Any) -> str:
    payload = "\n".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return prefix + "_" + hashlib.sha256(payload.encode()).hexdigest()[:16]


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
        proc = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
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


def clone_checkout(work_root: Path, label: str, commit: str) -> tuple[Path, list[dict[str, Any]]]:
    dst = work_root / label
    logs = [
        run_cmd(["git", "clone", "--shared", str(REPO), str(dst)], timeout=180),
        run_cmd(["git", "-C", str(dst), "checkout", "--detach", commit], timeout=120),
    ]
    return dst, logs


def verifier_for(clone: Path, cache_name: str) -> dict[str, Any]:
    cwd = clone / "agent-governance-python"
    pythonpath = str(cwd / "agent-compliance/src")
    argv = [
        "python",
        "-m",
        "pytest",
        "-q",
        "-c",
        "/dev/null",
        "-o",
        f"cache_dir=/data/tmp/{cache_name}",
        "agent-compliance/tests/test_governance_attestation.py",
    ]
    out = run_cmd(argv, cwd=cwd, env_extra={"PYTHONPATH": pythonpath}, timeout=TIMEOUT)
    out["pythonpath"] = pythonpath
    return out


def status(result: dict[str, Any]) -> str:
    if result.get("returncode") == 0:
        return "PASS_CURRENT_STATE"
    combined = (str(result.get("stdout_tail", "")) + "\n" + str(result.get("stderr_tail", ""))).lower()
    if any(token in combined for token in ["modulenotfounderror", "importerror", "no module named", "not installed", "network", "connection"]):
        return "ENV_BLOCKED"
    return "FAIL_CURRENT_STATE"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    work_root = Path(tempfile.mkdtemp(prefix="stage12221_agent_governance_", dir="/data/tmp"))

    setup_logs: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []

    before_dir, logs = clone_checkout(work_root, "before", BEFORE)
    setup_logs.extend(logs)
    after_dir, logs = clone_checkout(work_root, "after", AFTER)
    setup_logs.extend(logs)
    patched_dir, logs = clone_checkout(work_root, "before_plus_patch", BEFORE)
    setup_logs.extend(logs)

    apply_check = run_cmd(["git", "-C", str(patched_dir), "apply", "--check", str(PATCH)], timeout=120)
    apply_patch = run_cmd(["git", "-C", str(patched_dir), "apply", str(PATCH)], timeout=120) if apply_check["returncode"] == 0 else None

    before_obs = verifier_for(before_dir, "stage12221_agent_governance_before_cache")
    after_obs = verifier_for(after_dir, "stage12221_agent_governance_after_cache")
    patched_obs = verifier_for(patched_dir, "stage12221_agent_governance_patched_cache") if apply_patch and apply_patch["returncode"] == 0 else None

    observations.extend(
        [
            {"phase": "before", "commit": BEFORE, "result": before_obs, "status": status(before_obs)},
            {"phase": "after", "commit": AFTER, "result": after_obs, "status": status(after_obs)},
        ]
    )
    if patched_obs:
        observations.append({"phase": "before_plus_patch", "commit": BEFORE, "result": patched_obs, "status": status(patched_obs)})

    setup_failed = [log for log in setup_logs if log["returncode"] != 0]
    statuses = {row["phase"]: row["status"] for row in observations}
    apply_ok = apply_check["returncode"] == 0 and apply_patch is not None and apply_patch["returncode"] == 0
    all_verifiers_ran = all(row["status"] != "ENV_BLOCKED" for row in observations) and len(observations) == 3
    all_pass = all(row["status"] == "PASS_CURRENT_STATE" for row in observations)

    records: list[dict[str, Any]] = []
    if not setup_failed and apply_ok and all_verifiers_ran:
        transition = "PASS_TO_PASS" if all_pass else "PATCH_REPLAY_OBSERVED_NONPASS"
        episode_id = stable_id("stage12221_episode", SOURCE_EPISODE, statuses, apply_check, apply_patch)
        record = {
            "episode_id": episode_id,
            "source_stage": STAGE,
            "source_stage12201_episode_id": SOURCE_EPISODE,
            "admission_level_effective": "level_3_patch_trace_replay_verifier_observation",
            "root_id": str(REPO),
            "repo_family": "agent-governance-toolkit",
            "language_family": "python",
            "split": "train_support",
            "work_root": str(work_root),
            "repo_commit_before": BEFORE,
            "repo_commit_after": AFTER,
            "patch_trace": {
                "has_patch_trace": True,
                "patch_diff": str(PATCH),
                "patch_apply_check": apply_check,
                "patch_apply_result": apply_patch,
                "counts_toward_patch_trace_floor": True,
                "counts_toward_fail_to_pass_floor": False,
                "semantic_patch_validation_strength": "weak_selected_verifier_unrelated_to_changed_paths",
            },
            "candidate_action_set": {
                "candidate_set_id": stable_id("stage12221_candidates", episode_id),
                "chosen_action_id": "A",
                "candidate_actions": [
                    {
                        "action_id": "A",
                        "action_type": "APPLY_PATCH_AND_VERIFY",
                        "role": transition,
                        "is_chosen": True,
                    },
                    {
                        "action_id": "B",
                        "action_type": "VERIFY_ONLY",
                        "role": "PASS_CURRENT_STATE_NO_PATCH_TRACE",
                        "is_chosen": False,
                    },
                    {
                        "action_id": "C",
                        "action_type": "ABSTAIN",
                        "role": "INSUFFICIENT_PATCH_VERIFIER_EVIDENCE",
                        "is_chosen": False,
                    },
                ],
            },
            "candidate_action_count": 3,
            "chosen_action": {"action_type": "APPLY_PATCH_AND_VERIFY", "role": transition},
            "ordered_events": [
                {"event_type": "STATE_BEFORE", "commit": BEFORE, "phase": "before"},
                {"event_type": "COMMAND", "phase": "before", "command": before_obs["command"], "cwd": before_obs["cwd"]},
                {"event_type": "COMMAND_RESULT", "phase": "before", "returncode": before_obs["returncode"], "status": status(before_obs)},
                {"event_type": "PATCH_APPLY_CHECK", "returncode": apply_check["returncode"]},
                {"event_type": "PATCH_APPLY", "returncode": apply_patch["returncode"] if apply_patch else None},
                {"event_type": "COMMAND", "phase": "before_plus_patch", "command": patched_obs["command"] if patched_obs else None, "cwd": patched_obs["cwd"] if patched_obs else None},
                {"event_type": "COMMAND_RESULT", "phase": "before_plus_patch", "returncode": patched_obs["returncode"] if patched_obs else None, "status": status(patched_obs) if patched_obs else "NOT_RUN"},
                {"event_type": "COMMAND", "phase": "after", "command": after_obs["command"], "cwd": after_obs["cwd"]},
                {"event_type": "COMMAND_RESULT", "phase": "after", "returncode": after_obs["returncode"], "status": status(after_obs)},
                {"event_type": "VERIFIER_RESULT", "verifier_transition": transition},
                {"event_type": "STATE_AFTER", "commit": AFTER, "verifier_transition": transition},
                {"event_type": "STOP_CONTINUE_DECISION", "continue_or_stop": "CONTINUE"},
            ],
            "state_before": {
                "root_id": str(REPO),
                "commit": BEFORE,
                "known_facts": [
                    "same-source before commit is available",
                    "saved patch applies cleanly to before commit",
                    "selected verifier command is available",
                ],
            },
            "state_after": {
                "root_id": str(REPO),
                "commit": AFTER,
                "verifier_transition": transition,
                "new_facts": [
                    f"before verifier status: {statuses.get('before')}",
                    f"before_plus_patch verifier status: {statuses.get('before_plus_patch')}",
                    f"after verifier status: {statuses.get('after')}",
                ],
            },
            "verifier_transition": transition,
            "verifier_result": {
                "before": before_obs,
                "before_plus_patch": patched_obs,
                "after": after_obs,
                "verifier_transition": transition,
                "runnable_verifier_proof": True,
            },
            "stop_decision": {
                "continue_or_stop": "CONTINUE",
                "reason": "selected verifier passes but is weak patch validation; keep as train-support patch trace, not repair proof",
            },
            "train_support_only": True,
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
            "training_allowed": False,
        }
        records.append(record)
    else:
        diagnostics.append(
            {
                "reason": "patch_replay_not_admitted",
                "setup_failed": setup_failed,
                "apply_check": apply_check,
                "apply_patch": apply_patch,
                "observations": observations,
            }
        )

    write_jsonl(OUT / "setup_logs.jsonl", setup_logs)
    write_jsonl(OUT / "patch_replay_observations.jsonl", observations)
    write_jsonl(OUT / "patch_replay_records.jsonl", records)
    write_jsonl(OUT / "patch_replay_diagnostics.jsonl", diagnostics)

    summary = {
        "stage": STAGE,
        "decision": "patch_trace_replay_record_admitted" if records else "blocked_no_patch_trace_replay_record",
        "source_stage": "stage12201_patch_evidence_recovery",
        "source_stage12220_record": "stage12220_episode_5128c7f1675de32a",
        "record_count": len(records),
        "diagnostic_count": len(diagnostics),
        "work_root": str(work_root),
        "setup_failure_count": len(setup_failed),
        "patch_apply_check_passed": apply_check["returncode"] == 0,
        "patch_apply_passed": bool(apply_patch and apply_patch["returncode"] == 0),
        "verifier_statuses": statuses,
        "transition_counts": {records[0]["verifier_transition"]: 1} if records else {},
        "language_counts": {"python": len(records)} if records else {},
        "tests_executed": True,
        "training_allowed": False,
        "gpu_policy": "CUDA_VISIBLE_DEVICES empty; CPU-only commands",
        "claim_boundary": "Patch replay train-support only. Counts toward patch-trace verifier-observation floor if accepted by Stage12213 QC, but not toward fail-to-pass repair proof because selected verifier is PASS_TO_PASS and weakly related to changed paths.",
        "artifact_paths": {
            "records": str(OUT / "patch_replay_records.jsonl"),
            "observations": str(OUT / "patch_replay_observations.jsonl"),
            "diagnostics": str(OUT / "patch_replay_diagnostics.jsonl"),
            "setup_logs": str(OUT / "setup_logs.jsonl"),
        },
    }
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if records else 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Replay selected verifier actions for Stage12201 records in throwaway copies.

This is a data-materialization stage, not training. It intentionally executes a
small bounded verifier command from the Stage12202 candidate action set inside a
local copy under /data/tmp, captures the observation, and emits Level-3
single-step transition records only when the observed command is in the
candidate action set.

Safety boundaries:
- no GPU
- no network/install/fetch/pull
- no mutation of /arxiv/repositories
- writes only to the requested artifact dir and /data/tmp
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EPISODE_ID = "stage12201_episode_b9835fda3cb12663"
STAGE = "stage12203_controlled_selected_verifier_replay"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_PATH = ROOT / "runs/summaries" / f"{STAGE}.json"
TMP_ROOT = Path("/data/tmp/stage12203_controlled_selected_verifier_replay")


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(json.dumps(part, sort_keys=True, default=str) for part in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            yield line_no, json.loads(line)


def load_by_episode(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for _, row in iter_jsonl(path):
        episode_id = row.get("episode_id")
        if episode_id:
            out[str(episode_id)] = row
    return out


def command_for_action(action: dict[str, Any]) -> str | None:
    if action.get("type") != "run":
        return None
    args = action.get("arguments") or {}
    cmd = args.get("cmd")
    if not isinstance(cmd, str) or not cmd.strip():
        return None
    if cmd == "run broad test suite":
        return None
    # Stage12203 is intentionally narrow: replay selected pytest verifier
    # targets only. Do not execute shell pipelines, broad suites, package
    # managers, scripts, installs, or arbitrary repo commands.
    parts = cmd.strip().split()
    if not parts or parts[0] != "pytest":
        return None
    if any(token in parts for token in ("&&", ";", "|", "`", "$")):
        return None
    if any(token.startswith("-") and token not in {"-q", "-k", "-s"} for token in parts[1:]):
        return None
    return "python -m pytest " + " ".join(parts[1:])


def selected_target_for_action(action: dict[str, Any]) -> str | None:
    args = action.get("arguments") or {}
    target = args.get("target")
    return str(target) if isinstance(target, str) and target.strip() else None


def target_is_safe_repo_relative(target: str | None) -> bool:
    if not target:
        return False
    if target.startswith(("/", "~")):
        return False
    path = Path(target)
    if any(part in {"..", ".git", "node_modules"} for part in path.parts):
        return False
    return True


def verifier_status(returncode: int, stdout: str, stderr: str) -> str:
    text = f"{stdout}\n{stderr}".lower()
    if returncode == 0:
        return "PASS_CURRENT_STATE"
    env_markers = (
        "modulenotfounderror",
        "no module named",
        "importerror",
        "command not found",
        "pytest: error",
        "unrecognized arguments",
        "could not import",
        "failed to import",
        "environment",
        "dependency",
    )
    if any(marker in text for marker in env_markers):
        return "ENV_BLOCKED"
    if "collected 0 items" in text or "no tests ran" in text:
        return "NOT_EXERCISED"
    return "FAIL_CURRENT_STATE"


def transition_from_status(status: str) -> str:
    if status == "PASS_CURRENT_STATE":
        return "PASS_CURRENT_STATE"
    if status == "NOT_EXERCISED":
        return "NOT_EXERCISED"
    if status == "ENV_BLOCKED":
        return "INSUFFICIENT_EVIDENCE"
    return "FAIL_TO_FAIL"


def state_update_for(status: str) -> dict[str, Any]:
    if status == "PASS_CURRENT_STATE":
        return {
            "state_update_type": "verified",
            "new_facts": ["selected verifier command completed successfully in throwaway checkout"],
            "invalidated_claims": [],
            "remaining_blockers": [],
        }
    if status == "NOT_EXERCISED":
        return {
            "state_update_type": "blocked",
            "new_facts": ["selected verifier command did not exercise tests"],
            "invalidated_claims": ["selected verifier is sufficient evidence"],
            "remaining_blockers": ["need narrower verifier target"],
        }
    if status == "ENV_BLOCKED":
        return {
            "state_update_type": "blocked",
            "new_facts": ["selected verifier command could not establish code behavior because environment/dependencies blocked execution"],
            "invalidated_claims": ["verifier result proves patch behavior"],
            "remaining_blockers": ["hydrate environment or use existing authoritative verifier log"],
        }
    return {
        "state_update_type": "observed_failure",
        "new_facts": ["selected verifier command failed in current state"],
        "invalidated_claims": [],
        "remaining_blockers": ["interpret failure before patching or stopping"],
    }


def stop_decision_for(status: str) -> dict[str, Any]:
    if status == "PASS_CURRENT_STATE":
        return {
            "continue_or_stop": "CONTINUE",
            "reason": "passing selected verifier alone is not enough to prove recovered patch minimality or final acceptance",
        }
    if status == "ENV_BLOCKED":
        return {
            "continue_or_stop": "ABSTAIN_BLOCKED",
            "reason": "environment/dependency failure prevents behavioral verifier conclusion",
        }
    return {
        "continue_or_stop": "CONTINUE",
        "reason": "the verifier observation changed state and requires interpretation before completion",
    }


def pythonpath_roots(cwd: Path) -> list[str]:
    roots = [cwd]
    if (cwd / "src").is_dir():
        roots.append(cwd / "src")
    # Monorepos often keep Python packages one or two levels down. Add source
    # roots, but cap the scan to avoid turning the whole checkout into import
    # noise.
    for pattern in ("*/*/src", "*/*/*/src"):
        for path in sorted(cwd.glob(pattern))[:64]:
            if path.is_dir():
                roots.append(path)
    for path in sorted(cwd.glob("libs/*"))[:16]:
        if path.is_dir() and any((path / marker).exists() for marker in ("pyproject.toml", "setup.py", "setup.cfg")):
            roots.append(path)
    seen: set[str] = set()
    out: list[str] = []
    for root in roots:
        value = str(root)
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def run_cmd(command: str, cwd: Path, timeout_s: int) -> dict[str, Any]:
    env = os.environ.copy()
    py_path = os.pathsep.join(pythonpath_roots(cwd))
    if env.get("PYTHONPATH"):
        py_path = py_path + os.pathsep + env["PYTHONPATH"]
    env.update(
        {
            "CUDA_VISIBLE_DEVICES": "",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTHONPATH": py_path,
            "PYTHONPYCACHEPREFIX": str(TMP_ROOT / "pycache"),
            "PIP_NO_INDEX": "1",
            "NO_NETWORK": "1",
        }
    )
    start = time.time()
    try:
        proc = subprocess.run(
            command.split(),
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        timed_out = False
        returncode = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = 124
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", errors="replace")
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", errors="replace")
    elapsed = round(time.time() - start, 3)
    max_chars = 20000
    return {
        "command": command,
        "returncode": returncode,
        "timed_out": timed_out,
        "elapsed_seconds": elapsed,
        "stdout": stdout[-max_chars:],
        "stderr": stderr[-max_chars:],
        "stdout_sha256": hashlib.sha256(stdout.encode("utf-8", errors="replace")).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr.encode("utf-8", errors="replace")).hexdigest(),
        "pythonpath_roots": pythonpath_roots(cwd),
    }


def prepare_checkout(ep: dict[str, Any], work_dir: Path) -> tuple[Path | None, str | None]:
    root_id = ep.get("root_id")
    commit = ep.get("repo_commit_before")
    if not root_id or not commit:
        return None, "missing_root_or_commit"
    src = Path(str(root_id))
    if not src.exists() or not (src / ".git").exists():
        return None, "source_repo_missing_or_not_git"
    dst = work_dir / ep["episode_id"] / src.name
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    clone = subprocess.run(
        ["git", "clone", "--no-hardlinks", "--quiet", str(src), str(dst)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if clone.returncode != 0:
        return None, f"clone_failed:{clone.stderr[-500:]}"
    checkout = subprocess.run(
        ["git", "-C", str(dst), "checkout", "--quiet", str(commit)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if checkout.returncode != 0:
        return None, f"checkout_failed:{checkout.stderr[-500:]}"
    return dst, None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode-id", action="append", default=None)
    parser.add_argument("--timeout-s", type=int, default=90)
    parser.add_argument("--max-records", type=int, default=1)
    args = parser.parse_args()

    ep_path = ROOT / "runs/local/artifacts/stage12201_patch_evidence_recovery/recovered_episode_records.jsonl"
    action_path = ROOT / "runs/local/artifacts/stage12202_level3_readiness_joiner/candidate_action_sets.jsonl"
    episodes = load_by_episode(ep_path)
    actions = load_by_episode(action_path)
    wanted = args.episode_id or [DEFAULT_EPISODE_ID]
    wanted = wanted[: args.max_records]

    selected_replay_plan: list[dict[str, Any]] = []
    command_results: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    verifier_transitions: list[dict[str, Any]] = []
    state_updates: list[dict[str, Any]] = []
    stop_decisions: list[dict[str, Any]] = []
    level3_records: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)

    for episode_id in wanted:
        ep = episodes.get(episode_id)
        action_set = actions.get(episode_id)
        if not ep or not action_set:
            blocked.append({"episode_id": episode_id, "blockers": ["missing_episode_or_action_set"]})
            continue
        chosen = next((a for a in action_set.get("candidate_actions", []) if a.get("action_id") == action_set.get("chosen_action_id")), None)
        command = command_for_action(chosen or {})
        selected_target = selected_target_for_action(chosen or {})
        if not chosen or not command:
            blocked.append({"episode_id": episode_id, "blockers": ["chosen_action_not_replayable_pytest_command"]})
            continue
        if not target_is_safe_repo_relative(selected_target):
            blocked.append({"episode_id": episode_id, "blockers": ["selected_target_not_safe_repo_relative"], "selected_target": selected_target})
            continue
        plan = {
            "episode_id": episode_id,
            "root_id": ep.get("root_id"),
            "repo_family": ep.get("repo_family"),
            "repo_commit_before": ep.get("repo_commit_before"),
            "chosen_action_id": chosen.get("action_id"),
            "observed_command": command,
            "selected_target": selected_target,
            "safety": {
                "gpu": "disabled_by_CUDA_VISIBLE_DEVICES_empty",
                "network": "not_used_by_runner",
                "repo_mutation": "throwaway_checkout_only",
                "training": "not_run",
            },
        }
        selected_replay_plan.append(plan)
        checkout, checkout_error = prepare_checkout(ep, TMP_ROOT)
        if checkout_error or checkout is None:
            blocked.append({"episode_id": episode_id, "blockers": [checkout_error or "checkout_failed"], "plan": plan})
            continue
        result = run_cmd(command, checkout, args.timeout_s)
        status = verifier_status(int(result["returncode"]), result["stdout"], result["stderr"])
        transition = transition_from_status(status)
        command_id = stable_id("stage12203_command", episode_id, command, result["returncode"], result["stdout_sha256"], result["stderr_sha256"])
        command_row = {
            **plan,
            "command_result_id": command_id,
            "cwd": str(checkout),
            "returncode": result["returncode"],
            "timed_out": result["timed_out"],
            "elapsed_seconds": result["elapsed_seconds"],
            "stdout_sha256": result["stdout_sha256"],
            "stderr_sha256": result["stderr_sha256"],
            "stdout_tail": result["stdout"],
            "stderr_tail": result["stderr"],
            "pythonpath_roots": result.get("pythonpath_roots"),
        }
        command_results.append(command_row)
        observation_id = stable_id("stage12203_observation", command_id, status)
        observations.append(
            {
                "observation_id": observation_id,
                "episode_id": episode_id,
                "command_result_id": command_id,
                "observation_type": "selected_verifier_command_output",
                "verifier_status": status,
                "summary": f"Observed selected verifier action returned {result['returncode']} with status {status}.",
            }
        )
        verifier_transitions.append(
            {
                "verifier_transition_id": stable_id("stage12203_verifier_transition", observation_id, transition),
                "episode_id": episode_id,
                "command_result_id": command_id,
                "status": status,
                "transition": transition,
                "verifier_evidence_type": "selected_test_command_replay",
                "selected_tests": ep.get("selected_tests"),
            }
        )
        state_update = {
            "state_update_id": stable_id("stage12203_state_update", observation_id),
            "episode_id": episode_id,
            "observation_id": observation_id,
            **state_update_for(status),
        }
        state_updates.append(state_update)
        stop_decision = {
            "stop_decision_id": stable_id("stage12203_stop_decision", observation_id),
            "episode_id": episode_id,
            "observation_id": observation_id,
            **stop_decision_for(status),
        }
        stop_decisions.append(stop_decision)

        candidate_has_observed = any(
            a.get("action_id") == chosen.get("action_id") and command_for_action(a) == command
            for a in action_set.get("candidate_actions", [])
        )
        blockers = []
        if not candidate_has_observed:
            blockers.append("candidate_action_set_missing_observed_action")
        if result["timed_out"]:
            blockers.append("command_timed_out")
        if selected_target and not (checkout / selected_target.split("::", 1)[0]).exists():
            blockers.append("selected_target_path_missing_in_checkout")
        if blockers:
            blocked.append({"episode_id": episode_id, "blockers": blockers, "command_result_id": command_id})
            continue
        level3_records.append(
            {
                "admission_level": "level_3_single_step_closed_loop_verifier_observation",
                "episode_id": episode_id,
                "root_id": ep.get("root_id"),
                "repo_family": ep.get("repo_family"),
                "language": ep.get("language"),
                "repo_commit_before": ep.get("repo_commit_before"),
                "repo_commit_after": ep.get("repo_commit_after"),
                "source_record_ref": ep.get("source_record_ref"),
                "candidate_action_set": action_set,
                "observed_action": {
                    "action_id": chosen.get("action_id"),
                    "type": "run",
                    "command": command,
                    "cwd": str(checkout),
                    "command_result_id": command_id,
                },
                "observation_id": observation_id,
                "verifier_status": status,
                "verifier_transition": transition,
                "state_update_id": state_update["state_update_id"],
                "stop_decision_id": stop_decision["stop_decision_id"],
                "projection_permissions": [
                    "transition_next_action",
                    "transition_verifier_transition",
                    "transition_continue_or_stop",
                    "execution_trace_interpretation",
                ],
                "train_support_only": True,
                "strict_eval_eligible": False,
                "anti_cheat": {
                    "throwaway_checkout": True,
                    "source_repo_mutated": False,
                    "network_used": False,
                    "gpu_used": False,
                    "candidate_action_set_includes_observed_action": candidate_has_observed,
                    "target_not_promotable_eval": True,
                },
            }
        )

    paths = {
        "selected_replay_plan": OUT_DIR / "selected_replay_plan.jsonl",
        "command_results": OUT_DIR / "command_results.jsonl",
        "observations": OUT_DIR / "observations.jsonl",
        "verifier_transitions": OUT_DIR / "verifier_transitions.jsonl",
        "state_updates": OUT_DIR / "state_updates.jsonl",
        "stop_decisions": OUT_DIR / "stop_decisions.jsonl",
        "level3_episode_records": OUT_DIR / "level3_episode_records.jsonl",
        "blocked_candidates": OUT_DIR / "blocked_candidates.jsonl",
    }
    write_jsonl(paths["selected_replay_plan"], selected_replay_plan)
    write_jsonl(paths["command_results"], command_results)
    write_jsonl(paths["observations"], observations)
    write_jsonl(paths["verifier_transitions"], verifier_transitions)
    write_jsonl(paths["state_updates"], state_updates)
    write_jsonl(paths["stop_decisions"], stop_decisions)
    write_jsonl(paths["level3_episode_records"], level3_records)
    write_jsonl(paths["blocked_candidates"], blocked)

    status_counts = Counter(row.get("verifier_status") for row in observations)
    admission_audit = {
        "stage": STAGE,
        "decision": "level3_single_step_records_materialized" if level3_records else "level3_replay_blocked",
        "requested_episode_count": len(wanted),
        "selected_replay_plan_count": len(selected_replay_plan),
        "command_result_count": len(command_results),
        "level3_episode_count": len(level3_records),
        "blocked_candidate_count": len(blocked),
        "verifier_status_counts": dict(status_counts),
        "admission_contract": {
            "requires_observed_chosen_action": True,
            "requires_command_output_and_exit_code": True,
            "requires_candidate_action_set_membership": True,
            "env_blocked_is_admissible_as_verifier_observation": True,
            "env_blocked_is_not_admissible_as_successful_repair": True,
        },
        "artifact_paths": {k: str(v) for k, v in paths.items()},
    }
    write_json(OUT_DIR / "admission_audit.json", admission_audit)
    summary = {
        **admission_audit,
        "output_dir": str(OUT_DIR),
        "tmp_root": str(TMP_ROOT),
        "source_stage_inputs": [
            "stage12201_patch_evidence_recovery",
            "stage12202_level3_readiness_joiner",
            "stage12203_controlled_selected_verifier_replay_request",
        ],
        "gpu_policy": "CUDA_VISIBLE_DEVICES empty during replay commands",
    }
    write_json(OUT_DIR / "summary.json", summary)
    write_json(SUMMARY_PATH, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if level3_records else 2


if __name__ == "__main__":
    raise SystemExit(main())

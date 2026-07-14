#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11399
NAME = "stage11399_disjoint_web_runtime_feasibility_and_queue"
OUT = ART / NAME
SUMMARY = OUT / "disjoint_web_runtime_feasibility_and_queue.json"
QUEUE_OUT = OUT / "disjoint_web_runtime_recovery_queue.jsonl"
LOG_DIR = OUT / "logs"

SOURCE_QUEUE = ART / "stage11346_web_source_verifier_review_queue/web_source_verifier_first_wave_review_queue.jsonl"

USED_WEB_FAMILIES = {
    "openhands_openhands",
    "OpenHands__OpenHands",
    "sourcebot",
    "modelcontextprotocol_typescript_sdk",
    "modelcontextprotocol_modelcontextprotocol",
    "llama_stack",
}

ATTEMPTS = [
    {
        "attempt_id": "openclaw_qa_lab_pnpm_version",
        "repo_family": "openclaw_openclaw",
        "cmd": ["pnpm", "--version"],
        "cwd": Path("/data/repositories/openclaw__openclaw"),
        "timeout": 30,
    },
    {
        "attempt_id": "openclaw_qa_lab_vitest_focused",
        "repo_family": "openclaw_openclaw",
        "cmd": ["npm", "exec", "--", "vitest", "run", "src/model-switch-eval.test.ts"],
        "cwd": Path("/data/repositories/openclaw__openclaw/extensions/qa-lab"),
        "timeout": 90,
    },
    {
        "attempt_id": "openclaw_clawhub_bun_version",
        "repo_family": "openclaw_clawhub",
        "cmd": ["bun", "--version"],
        "cwd": Path("/data/repositories/openclaw__clawhub"),
        "timeout": 30,
    },
    {
        "attempt_id": "openclaw_clawhub_vitest_focused",
        "repo_family": "openclaw_clawhub",
        "cmd": ["npm", "exec", "--", "vitest", "run", "convex/skills.versions.public.test.ts"],
        "cwd": Path("/data/repositories/openclaw__clawhub"),
        "timeout": 90,
    },
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def run_capture(attempt: dict[str, Any]) -> dict[str, Any]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{attempt['attempt_id']}.log"
    cwd = Path(str(attempt["cwd"]))
    if not cwd.exists():
        log_path.write_text(f"missing cwd: {cwd}\n")
        return {
            "attempt_id": attempt["attempt_id"],
            "cmd": attempt["cmd"],
            "cwd": str(cwd),
            "returncode": None,
            "status": "blocked_missing_workdir",
            "log": rel(log_path),
        }
    try:
        proc = subprocess.run(
            list(attempt["cmd"]),
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=int(attempt["timeout"]),
        )
    except FileNotFoundError as exc:
        log_path.write_text(str(exc) + "\n")
        return {
            "attempt_id": attempt["attempt_id"],
            "cmd": attempt["cmd"],
            "cwd": str(cwd),
            "returncode": None,
            "status": "blocked_missing_executable",
            "log": rel(log_path),
            "error": str(exc),
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        log_path.write_text(stdout + ("\n[stderr]\n" + stderr if stderr else ""))
        return {
            "attempt_id": attempt["attempt_id"],
            "cmd": attempt["cmd"],
            "cwd": str(cwd),
            "returncode": None,
            "status": "blocked_timeout",
            "log": rel(log_path),
        }
    log_path.write_text((proc.stdout or "") + ("\n[stderr]\n" + proc.stderr if proc.stderr else ""))
    return {
        "attempt_id": attempt["attempt_id"],
        "cmd": attempt["cmd"],
        "cwd": str(cwd),
        "returncode": proc.returncode,
        "status": "passed" if proc.returncode == 0 else "failed",
        "log": rel(log_path),
        "stdout_tail": (proc.stdout or "")[-1600:],
        "stderr_tail": (proc.stderr or "")[-1600:],
    }


def classify_blocker(result: dict[str, Any]) -> str:
    text = f"{result.get('stdout_tail') or ''}\n{result.get('stderr_tail') or ''}\n{result.get('error') or ''}".lower()
    if result.get("status") == "blocked_missing_executable":
        return "missing_executable"
    if "err_vm_dynamic_import_callback_missing" in text:
        return "pnpm_corepack_dynamic_import_failure"
    if "enotempty" in text and "_npx" in text:
        return "npm_exec_cache_corruption_or_partial_install"
    if "cannot find package 'vitest'" in text or "could not resolve 'vitest/config'" in text:
        return "repo_dependencies_not_installed"
    if result.get("returncode") == 0:
        return "none"
    return "verifier_execution_failed"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    queue = read_jsonl(SOURCE_QUEUE)
    fresh = [
        item
        for item in queue
        if str(item.get("git_repo_family") or "") not in USED_WEB_FAMILIES
        and str(item.get("review_item_id") or "").strip()
    ]
    priority = [
        item
        for item in fresh
        if str(item.get("git_repo_family") or "") in {"openclaw_openclaw", "openclaw_clawhub"}
    ]
    results = [run_capture(attempt) for attempt in ATTEMPTS]
    blockers = [
        {
            "attempt_id": result["attempt_id"],
            "repo_family": next((a["repo_family"] for a in ATTEMPTS if a["attempt_id"] == result["attempt_id"]), None),
            "blocker": classify_blocker(result),
            "status": result.get("status"),
            "returncode": result.get("returncode"),
            "log": result.get("log"),
        }
        for result in results
        if classify_blocker(result) != "none"
    ]

    recovery_queue = []
    for item in priority:
        recovery_queue.append(
            {
                "review_item_id": item.get("review_item_id"),
                "git_repo_family": item.get("git_repo_family"),
                "repo_family": item.get("repo_family"),
                "repo_path": item.get("repo_path"),
                "git_head": item.get("git_head"),
                "selected_candidate_source_paths": item.get("candidate_change_surface_paths") or [],
                "selected_verifier_paths": item.get("verifier_and_test_constraint_paths") or [],
                "runtime_recovery_required": True,
                "required_before_rows": [
                    "hydrate package dependencies or repair package manager for this repo family",
                    "execute one focused verifier command and store raw log",
                    "select one changed/source path and one verifier/test path with non-aliased visible evidence",
                    "fill maintainer gold for six perspectives",
                    "run prompt-target leak and root-overlap audits",
                ],
            }
        )
    write_jsonl(QUEUE_OUT, recovery_queue)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "disjoint_web_runtime_recovery_required_before_materialization",
        "counts": {
            "stage11346_queue_items": len(queue),
            "fresh_disjoint_queue_items": len(fresh),
            "priority_openclaw_items": len(priority),
            "execution_attempts": len(results),
            "blocking_attempts": len(blockers),
            "recovery_queue_items": len(recovery_queue),
        },
        "used_web_families_excluded": sorted(USED_WEB_FAMILIES),
        "execution_results": results,
        "runtime_blockers": blockers,
        "recovery_queue": recovery_queue,
        "admissibility": {
            "trainable_now": False,
            "scoreable_now": False,
            "why": (
                "The best disjoint Web candidates have source and verifier paths, but local JS runtime/dependency state "
                "does not yet execute focused verifiers. No rows are emitted until raw verifier output exists."
            ),
        },
        "source_artifacts": {"stage11346_review_queue": rel(SOURCE_QUEUE)},
        "outputs": {"summary": rel(SUMMARY), "recovery_queue": rel(QUEUE_OUT), "logs": rel(LOG_DIR)},
        "recommended_next_action": (
            "Repair JS package runtime for openclaw_openclaw and openclaw_clawhub, then rerun focused Vitest/Bun "
            "commands and project only roots with passed verifier logs."
        ),
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "counts": summary["counts"], "runtime_blockers": blockers}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11579
NAME = "stage11579_web_focused_verifier_execution"
OUT = ART / NAME
SUMMARY = OUT / "web_focused_verifier_execution.json"
RESULTS = OUT / "web_focused_verifier_results.jsonl"
LOG_DIR = OUT / "logs"

STAGE11576 = ART / "stage11576_web_fresh_source_candidate_atlas/web_fresh_source_candidate_roots.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def command_for(candidate: dict[str, Any]) -> list[str] | None:
    repo = str(candidate.get("repo_path") or "")
    test = str(candidate.get("selected_verifier_path_proposal") or "")
    if not repo or not test:
        return None
    if "OpenHands__OpenHands/frontend" in repo:
        return ["npm", "test", "--", "--run", test, "--reporter=verbose"]
    if "llama-stack/src/llama_stack_ui" in repo:
        return ["npm", "test", "--", "--runTestsByPath", test, "--runInBand"]
    return None


def run_one(candidate: dict[str, Any], index: int) -> dict[str, Any]:
    repo = Path(str(candidate.get("repo_path") or ""))
    cmd = command_for(candidate)
    log_path = LOG_DIR / f"{index:03d}_{candidate['root_id'].replace('/', '_').replace(':', '_')}.log"
    if cmd is None:
        return {
            "root_id": candidate.get("root_id"),
            "lane": candidate.get("lane"),
            "repo_family": candidate.get("repo_family"),
            "selected_verifier_path": candidate.get("selected_verifier_path_proposal"),
            "status": "unsupported_verifier_command",
            "returncode": None,
            "command": None,
            "log_path": None,
            "verifier_transition": "NOT_EXECUTED",
        }
    started = time.time()
    proc = subprocess.run(
        cmd,
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        env={**dict(__import__("os").environ), "CI": "1"},
    )
    elapsed = time.time() - started
    output = proc.stdout or ""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(output, encoding="utf-8")
    passed = proc.returncode == 0
    return {
        "root_id": candidate.get("root_id"),
        "lane": candidate.get("lane"),
        "repo_family": candidate.get("repo_family"),
        "git_repo_family": candidate.get("git_repo_family"),
        "selected_verifier_path": candidate.get("selected_verifier_path_proposal"),
        "status": "verifier_executed_passed" if passed else "verifier_executed_failed",
        "returncode": proc.returncode,
        "command": cmd,
        "elapsed_seconds": round(elapsed, 3),
        "log_path": rel(log_path),
        "output_preview": output[:1200],
        "verifier_transition": "PASS_TO_PASS" if passed else "FAIL_CURRENT_STATE",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    candidates = load_jsonl(STAGE11576)
    executable = [
        row for row in candidates
        if row.get("selected_verifier_path_proposal") and command_for(row) is not None
    ]
    results: list[dict[str, Any]] = []
    for index, candidate in enumerate(executable):
        try:
            results.append(run_one(candidate, index))
        except subprocess.TimeoutExpired as exc:
            results.append(
                {
                    "root_id": candidate.get("root_id"),
                    "lane": candidate.get("lane"),
                    "repo_family": candidate.get("repo_family"),
                    "selected_verifier_path": candidate.get("selected_verifier_path_proposal"),
                    "status": "verifier_timeout",
                    "returncode": None,
                    "command": command_for(candidate),
                    "elapsed_seconds": 60,
                    "log_path": None,
                    "output_preview": str(exc)[:1200],
                    "verifier_transition": "NOT_EXECUTED_TIMEOUT",
                }
            )
    metrics = {
        "candidate_roots": len(candidates),
        "executable_roots": len(executable),
        "executed_roots": len(results),
        "passed_roots": sum(1 for row in results if row["status"] == "verifier_executed_passed"),
        "failed_roots": sum(1 for row in results if row["status"] == "verifier_executed_failed"),
        "timeout_roots": sum(1 for row in results if row["status"] == "verifier_timeout"),
        "by_lane": dict(Counter(str(row.get("lane")) for row in results)),
        "by_status": dict(Counter(str(row.get("status")) for row in results)),
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "focused_web_verifier_execution_complete",
        "metrics": metrics,
        "claim_boundary": [
            "This executes current-state focused verifiers for source candidates.",
            "PASS_TO_PASS is verifier evidence, not proof that a bug/fix transition exists.",
            "Rows still need gold adjudication and prompt-target leak review before training admission.",
        ],
        "source_artifacts": {"stage11576_candidates": rel(STAGE11576)},
        "outputs": {"summary": rel(SUMMARY), "results": rel(RESULTS), "logs": rel(LOG_DIR)},
    }
    write_jsonl(RESULTS, results)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "metrics": metrics}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

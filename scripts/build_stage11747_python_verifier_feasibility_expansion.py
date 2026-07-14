#!/usr/bin/env python3
"""Run a second focused pytest feasibility batch for Python support candidates."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11747
NAME = "stage11747_python_verifier_feasibility_expansion"
OUT = ART / NAME
LOGS = OUT / "logs"
SUMMARY = OUT / "python_verifier_feasibility_expansion.json"
RESULTS = OUT / "python_verifier_feasibility_expansion_results.jsonl"

ATLAS = ART / "stage11743_source_heldout_support_candidate_atlas/source_heldout_support_candidates.jsonl"
PREVIOUS = ART / "stage11744_python_verifier_feasibility_probe/python_verifier_feasibility_results.jsonl"

# Keep this bounded. The goal is to discover more executable roots, not to run
# every large ML repo in the inventory.
SELECTED_REPOS = [
    "Digital-World-Model",
    "model-stack",
    "torchscale",
    "pytorch",
    "tokenizers",
    "peft",
    "transformers",
    "statespace_101",
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
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def choose_tests(candidate: dict[str, Any]) -> list[str]:
    tests = list(candidate.get("sample_tests") or [])
    preferred = [test for test in tests if test.startswith("tests/") or "/tests/" in f"/{test}"]
    # For very large repos, two tests is enough to prove verifier availability
    # while keeping this stage bounded.
    return (preferred or tests)[:2]


def run_pytest(repo: Path, tests: list[str], repo_family: str) -> dict[str, Any]:
    command = ["conda", "run", "-n", "trellis", "pytest", "-q", "-o", "addopts=", *tests]
    env = os.environ.copy()
    env.update(
        {
            "CUDA_VISIBLE_DEVICES": "2",
            "NVIDIA_VISIBLE_DEVICES": "2",
            "AGENTKERNEL_EVAL_DEVICE": "cuda:0",
            "PYTHONPATH": str(repo),
            "TMPDIR": "/data/tmp",
            "TEMP": "/data/tmp",
            "TMP": "/data/tmp",
        }
    )
    started = now()
    try:
        proc = subprocess.run(
            command,
            cwd=str(repo),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
        )
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        proc = subprocess.CompletedProcess(command, returncode=124, stdout=exc.stdout or "", stderr=exc.stderr or "")
        timed_out = True

    stdout = str(proc.stdout or "")
    stderr = str(proc.stderr or "")
    safe_name = repo_family.replace("/", "__")
    stdout_path = LOGS / f"{safe_name}.stdout.log"
    stderr_path = LOGS / f"{safe_name}.stderr.log"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text(stdout, encoding="utf-8", errors="replace")
    stderr_path.write_text(stderr, encoding="utf-8", errors="replace")
    return {
        "repo_family": repo_family,
        "repo_path": str(repo),
        "command": command,
        "selected_tests": tests,
        "started_at_utc": started,
        "finished_at_utc": now(),
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "timed_out": timed_out,
        "stdout_log": rel(stdout_path),
        "stderr_log": rel(stderr_path),
        "stdout_sha256": sha(stdout),
        "stderr_sha256": sha(stderr),
        "stdout_tail": stdout[-1800:],
        "stderr_tail": stderr[-1800:],
    }


def main() -> None:
    previous_repos = {row.get("repo_family") for row in read_jsonl(PREVIOUS)}
    candidates = [
        row
        for row in read_jsonl(ATLAS)
        if row.get("language_family") == "python"
        and row.get("repo_family") in SELECTED_REPOS
        and row.get("repo_family") not in previous_repos
        and row.get("readiness") == "needs_pytest_execution"
        and row.get("admit_role") == "execution_candidate"
    ]

    results = []
    for candidate in candidates:
        tests = choose_tests(candidate)
        if len(tests) < 2:
            result = {
                "candidate_id": candidate.get("candidate_id"),
                "repo_family": candidate.get("repo_family"),
                "repo_path": candidate.get("repo_path"),
                "selected_tests": tests,
                "passed": False,
                "timed_out": False,
                "returncode": None,
                "blocker": "fewer_than_two_candidate_tests",
            }
        else:
            result = run_pytest(Path(str(candidate["repo_path"])), tests, str(candidate["repo_family"]))
            if not result["passed"]:
                result["blocker"] = "pytest_execution_failed_or_timed_out"
        result["candidate_id"] = candidate.get("candidate_id")
        result["source_snapshot_id"] = candidate.get("source_snapshot_id")
        result["sample_sources"] = candidate.get("sample_sources")
        result["support_lane"] = "python_verifier_outcome_selected_test_support"
        result["admit_recommendation"] = (
            "candidate_for_row_materialization" if result.get("passed") and len(tests) >= 2 else "blocked"
        )
        results.append(result)

    passed = [row for row in results if row.get("passed")]
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "python_verifier_feasibility_expansion_complete",
        "passed": True,
        "candidate_count": len(results),
        "passing_candidate_count": len(passed),
        "blocked_candidate_count": len(results) - len(passed),
        "passing_repo_families": [row["repo_family"] for row in passed],
        "selected_repo_families": SELECTED_REPOS,
        "excluded_previous_repo_families": sorted(previous_repos),
        "interpretation": [
            "This stage expands executable Python verifier-root supply beyond Stage11744.",
            "Passing repos are candidates for train-support row materialization only after anti-cheat rendering and admission audits.",
            "No strict source-heldout rows are used or admitted here.",
        ],
        "claim_boundary": [
            "No model score changes in this stage.",
            "No row becomes trainable until a materialization and admission audit stage passes.",
        ],
        "source_artifacts": {"atlas": rel(ATLAS), "previous_feasibility": rel(PREVIOUS)},
        "outputs": {"summary": rel(SUMMARY), "results": rel(RESULTS), "logs_dir": rel(LOGS)},
    }
    write_json(SUMMARY, artifact)
    write_jsonl(RESULTS, results)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": artifact["decision"],
                "candidate_count": len(results),
                "passing_candidate_count": len(passed),
                "passing_repo_families": artifact["passing_repo_families"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

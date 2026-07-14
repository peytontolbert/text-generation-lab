#!/usr/bin/env python3
"""Run focused pytest feasibility probes for Python source-heldout support candidates."""

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
STAGE = 11744
NAME = "stage11744_python_verifier_feasibility_probe"
OUT = ART / NAME
LOGS = OUT / "logs"
SUMMARY = OUT / "python_verifier_feasibility_probe.json"
RESULTS = OUT / "python_verifier_feasibility_results.jsonl"

ATLAS = ART / "stage11743_source_heldout_support_candidate_atlas/source_heldout_support_candidates.jsonl"

SELECTED_REPOS = [
    "Griffin",
    "llm_memory_modules_at_scale",
    "pytorch_basics_library",
    "neural_network_building_blocks",
    "genetic-algorithm-pytorch",
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
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
    # Prefer package-level unit tests over huge integration/example suites.
    preferred = [test for test in tests if "/tests/" in f"/{test}" or test.startswith("tests/")]
    selected = preferred[:2] or tests[:2]
    return selected


def run_pytest(repo: Path, tests: list[str], repo_family: str) -> dict[str, Any]:
    command = ["conda", "run", "-n", "trellis", "pytest", "-q", "-o", "addopts=", *tests]
    env = os.environ.copy()
    env.update(
        {
            "CUDA_VISIBLE_DEVICES": "",
            "NVIDIA_VISIBLE_DEVICES": "",
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
            timeout=90,
            check=False,
        )
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        proc = subprocess.CompletedProcess(command, returncode=124, stdout=exc.stdout or "", stderr=exc.stderr or "")
        timed_out = True
    stdout = str(proc.stdout or "")
    stderr = str(proc.stderr or "")
    stdout_path = LOGS / f"{repo_family}.stdout.log"
    stderr_path = LOGS / f"{repo_family}.stderr.log"
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
        "stdout_tail": stdout[-1500:],
        "stderr_tail": stderr[-1500:],
    }


def main() -> None:
    candidates = [
        row
        for row in read_jsonl(ATLAS)
        if row.get("language_family") == "python"
        and row.get("repo_family") in SELECTED_REPOS
        and row.get("readiness") == "needs_pytest_execution"
    ]
    results = []
    for candidate in candidates:
        repo = Path(str(candidate["repo_path"]))
        tests = choose_tests(candidate)
        result = run_pytest(repo, tests, str(candidate["repo_family"]))
        result["candidate_id"] = candidate.get("candidate_id")
        result["source_snapshot_id"] = candidate.get("source_snapshot_id")
        result["sample_sources"] = candidate.get("sample_sources")
        result["support_lane"] = "python_verifier_outcome_selected_test_support"
        result["admit_recommendation"] = "candidate_for_row_materialization" if result["passed"] and len(tests) >= 2 else "blocked"
        if not result["passed"]:
            result["blocker"] = "pytest_execution_failed_or_timed_out"
        results.append(result)

    passed = [row for row in results if row.get("passed")]
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "python_verifier_feasibility_probe_complete",
        "passed": True,
        "candidate_count": len(results),
        "passing_candidate_count": len(passed),
        "blocked_candidate_count": len(results) - len(passed),
        "passing_repo_families": [row["repo_family"] for row in passed],
        "interpretation": [
            "This stage probes execution feasibility only; it does not admit train rows.",
            "Passing repos can be used to build disjoint verifier_outcome selected-test support analogues.",
            "Failed repos remain useful inventory but need dependency/environment repair before row materialization.",
        ],
        "next_actions": [
            "Materialize verifier_outcome rows from passing Python repos with selected test, nearby test distractor, integration distractor, and implementation-only options.",
            "Keep bigram_language_model strict smoke rows out of train/support materialization.",
            "Run equivalent targeted feasibility probes for C/C++ build candidates and Rust selected-test geometry.",
        ],
        "claim_boundary": [
            "No model score changes in this stage.",
            "No support rows are admitted until anti-cheat rendering and root split checks pass.",
        ],
        "source_artifacts": {"atlas": rel(ATLAS)},
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

#!/usr/bin/env python3
"""Probe individual Python tests to recover verifier support roots."""

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
STAGE = 11761
NAME = "stage11761_python_individual_test_repair_feasibility"
OUT = ART / NAME
LOGS = OUT / "logs"
SUMMARY = OUT / "python_individual_test_repair_feasibility.json"
RESULTS = OUT / "python_individual_test_repair_feasibility_results.jsonl"

ATLAS = ART / "stage11743_source_heldout_support_candidate_atlas/source_heldout_support_candidates.jsonl"
ADMITTED = ART / "stage11750_python_verifier_support_combined_audit/python_verifier_support_combined_audit.json"

SELECTED_REPOS = [
    "Digital-World-Model",
    "Griffin",
    "bitsandbytes",
    "faiss",
    "mamba",
    "neural_network_building_blocks",
    "peft",
    "pytorch_basics_library",
    "torchscale",
]

MAX_TESTS_PER_REPO = 6
NEEDED_PASSING_TESTS = 2


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def safe_name(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in text)[:180]


def run_pytest(repo: Path, repo_family: str, test_path: str) -> dict[str, Any]:
    command = ["conda", "run", "-n", "trellis", "pytest", "-q", "-o", "addopts=", test_path]
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
            timeout=75,
            check=False,
        )
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        proc = subprocess.CompletedProcess(command, returncode=124, stdout=exc.stdout or "", stderr=exc.stderr or "")
        timed_out = True
    stdout = str(proc.stdout or "")
    stderr = str(proc.stderr or "")
    stem = f"{safe_name(repo_family)}__{safe_name(test_path)}"
    stdout_path = LOGS / f"{stem}.stdout.log"
    stderr_path = LOGS / f"{stem}.stderr.log"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text(stdout, encoding="utf-8", errors="replace")
    stderr_path.write_text(stderr, encoding="utf-8", errors="replace")
    return {
        "test_path": test_path,
        "command": command,
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
        "stderr_tail": stderr[-1200:],
    }


def main() -> None:
    admitted = read_json(ADMITTED)
    admitted_repos = set()
    for root in admitted.get("admitted_roots", []):
        if "llm_memory_modules_at_scale" in root:
            admitted_repos.add("llm_memory_modules_at_scale")
        if "model_stack" in root:
            admitted_repos.add("model-stack")

    candidates = [
        row
        for row in read_jsonl(ATLAS)
        if row.get("language_family") == "python"
        and row.get("repo_family") in SELECTED_REPOS
        and row.get("repo_family") not in admitted_repos
        and row.get("readiness") == "needs_pytest_execution"
        and row.get("admit_role") == "execution_candidate"
    ]

    results = []
    for candidate in candidates:
        repo = Path(str(candidate["repo_path"]))
        passing_tests = []
        attempted = []
        for test_path in list(candidate.get("sample_tests") or [])[:MAX_TESTS_PER_REPO]:
            result = run_pytest(repo, str(candidate["repo_family"]), str(test_path))
            attempted.append(result)
            if result["passed"]:
                passing_tests.append(result)
            if len(passing_tests) >= NEEDED_PASSING_TESTS:
                break
        materializable = len(passing_tests) >= NEEDED_PASSING_TESTS
        results.append(
            {
                "candidate_id": candidate.get("candidate_id"),
                "repo_family": candidate.get("repo_family"),
                "repo_path": candidate.get("repo_path"),
                "source_snapshot_id": candidate.get("source_snapshot_id"),
                "sample_sources": candidate.get("sample_sources"),
                "support_lane": "python_verifier_outcome_selected_test_support",
                "attempted_count": len(attempted),
                "passing_count": len(passing_tests),
                "attempted_tests": attempted,
                "passing_tests": passing_tests,
                "passed": materializable,
                "admit_recommendation": "candidate_for_row_materialization" if materializable else "blocked",
                "blocker": None if materializable else "fewer_than_two_individual_tests_passed",
            }
        )

    materializable = [row for row in results if row["passed"]]
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "python_individual_test_repair_feasibility_complete",
        "passed": True,
        "candidate_count": len(results),
        "materializable_candidate_count": len(materializable),
        "materializable_repo_families": [row["repo_family"] for row in materializable],
        "selected_repo_families": SELECTED_REPOS,
        "max_tests_per_repo": MAX_TESTS_PER_REPO,
        "needed_passing_tests": NEEDED_PASSING_TESTS,
        "interpretation": [
            "This stage recovers Python verifier support roots by probing individual tests rather than broad two-file bundles.",
            "A repo is materializable only when at least two individual tests pass, enabling selected-test plus sibling-test support geometry.",
        ],
        "claim_boundary": [
            "This is verifier feasibility only.",
            "No rows are trainable until materialization and admission audit pass.",
            "No strict source-heldout rows are used.",
        ],
        "source_artifacts": {"atlas": rel(ATLAS), "existing_python_admission": rel(ADMITTED)},
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
                "candidate_count": artifact["candidate_count"],
                "materializable_candidate_count": artifact["materializable_candidate_count"],
                "materializable_repo_families": artifact["materializable_repo_families"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

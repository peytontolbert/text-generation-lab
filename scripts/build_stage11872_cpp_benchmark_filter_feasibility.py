#!/usr/bin/env python3
"""Capture google/benchmark filter test build/run feasibility."""

from __future__ import annotations

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
STAGE = 11872
NAME = "stage11872_cpp_benchmark_filter_feasibility"
OUT = ART / NAME
LOGS = OUT / "logs"
SUMMARY = OUT / "cpp_benchmark_filter_feasibility.json"
RESULTS = OUT / "cpp_benchmark_filter_feasibility_results.jsonl"
REPO = Path("/data/repositories/benchmark")
BUILD = Path("/data/tmp/stage11872_benchmark_build")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def run_cmd(command: list[str], name: str, cwd: Path = ROOT, timeout: int = 240) -> dict[str, Any]:
    LOGS.mkdir(parents=True, exist_ok=True)
    stdout_log = LOGS / f"{name}.stdout.txt"
    stderr_log = LOGS / f"{name}.stderr.txt"
    env = os.environ.copy()
    env.update(
        {
            "CUDA_VISIBLE_DEVICES": "2",
            "NVIDIA_VISIBLE_DEVICES": "2",
            "AGENTKERNEL_EVAL_DEVICE": "cuda:0",
            "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
            "TMPDIR": "/data/tmp",
            "TEMP": "/data/tmp",
            "TMP": "/data/tmp",
        }
    )
    proc = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, timeout=timeout)
    stdout_log.write_text(proc.stdout, encoding="utf-8", errors="replace")
    stderr_log.write_text(proc.stderr, encoding="utf-8", errors="replace")
    return {
        "command": command,
        "cwd": str(cwd),
        "passed": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout_log": rel(stdout_log),
        "stderr_log": rel(stderr_log),
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def main() -> None:
    if BUILD.exists():
        shutil.rmtree(BUILD)
    configure = run_cmd(
        [
            "cmake",
            "-S",
            str(REPO),
            "-B",
            str(BUILD),
            "-DCMAKE_BUILD_TYPE=Release",
            "-DBENCHMARK_ENABLE_TESTING=ON",
            "-DBENCHMARK_ENABLE_GTEST_TESTS=OFF",
            "-DBENCHMARK_ENABLE_WERROR=OFF",
            "-DBENCHMARK_ENABLE_INSTALL=OFF",
        ],
        "configure",
        timeout=180,
    )
    build = run_cmd(
        ["cmake", "--build", str(BUILD), "--target", "benchmark_test", "filter_test", "options_test", "-j2"],
        "build",
        timeout=360,
    )
    execute = run_cmd(
        [
            "ctest",
            "--test-dir",
            str(BUILD),
            "-R",
            "^(benchmark|filter_simple|filter_regex_all|options_benchmarks)$",
            "--output-on-failure",
        ],
        "execute",
        timeout=120,
    )
    passed = bool(configure["passed"] and build["passed"] and execute["passed"])
    row = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "repo_family": "google_benchmark",
        "repo_path": str(REPO),
        "language_family": "c_cpp",
        "support_lane": "cpp_abstain_attractor_build_verifier_support",
        "source_path": "src/benchmark_register.cc",
        "selected_test": "test/filter_test.cc::filter_simple/filter_regex_all",
        "distractor_source_path": "src/benchmark_runner.cc",
        "build_dir": str(BUILD),
        "configure": configure,
        "build": build,
        "execute": execute,
        "passed": passed,
        "claim_boundary": "Feasibility only; no model score changed.",
    }
    write_jsonl(RESULTS, [row])
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "cpp_benchmark_filter_feasibility_recorded",
        "passed": passed,
        "passing_candidate_count": 1 if passed else 0,
        "outputs": {"summary": rel(SUMMARY), "results": rel(RESULTS)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "passing_candidate_count": artifact["passing_candidate_count"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Capture additional google/benchmark test build/run feasibility."""

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
STAGE = 11876
NAME = "stage11876_cpp_benchmark_extra_feasibility"
OUT = ART / NAME
LOGS = OUT / "logs"
SUMMARY = OUT / "cpp_benchmark_extra_feasibility.json"
RESULTS = OUT / "cpp_benchmark_extra_feasibility_results.jsonl"
REPO = Path("/data/repositories/benchmark")
BUILD = Path("/data/tmp/stage11876_benchmark_extra_build")

ROOT_SPECS = [
    {"root_key": "cxx11", "target": "cxx11_test", "ctest": "cxx11_test", "test_source": "test/cxx11_test.cc", "candidate_source": "include/benchmark/benchmark.h", "distractor_source": "src/benchmark_runner.cc"},
    {"root_key": "basic", "target": "basic_test", "ctest": "basic_benchmark", "test_source": "test/basic_test.cc", "candidate_source": "src/benchmark.cc", "distractor_source": "src/statistics.cc"},
    {"root_key": "repetitions", "target": "repetitions_test", "ctest": "repetitions_benchmark", "test_source": "test/repetitions_test.cc", "candidate_source": "src/statistics.cc", "distractor_source": "src/benchmark_register.cc"},
    {"root_key": "diagnostics", "target": "diagnostics_test", "ctest": "diagnostics_test", "test_source": "test/diagnostics_test.cc", "candidate_source": "src/check.cc", "distractor_source": "src/counter.cc"},
    {"root_key": "fixture", "target": "fixture_test", "ctest": "fixture_test", "test_source": "test/fixture_test.cc", "candidate_source": "include/benchmark/benchmark.h", "distractor_source": "src/json_reporter.cc"},
    {"root_key": "skip_with_error", "target": "skip_with_error_test", "ctest": "skip_with_error_test", "test_source": "test/skip_with_error_test.cc", "candidate_source": "src/benchmark_runner.cc", "distractor_source": "src/csv_reporter.cc"},
    {"root_key": "spec_arg", "target": "spec_arg_test", "ctest": "spec_arg", "test_source": "test/args_product_test.cc", "candidate_source": "src/benchmark_register.cc", "distractor_source": "src/console_reporter.cc"},
    {"root_key": "min_time_flag", "target": "benchmark_min_time_flag_time_test", "ctest": "min_time_flag_time", "test_source": "test/benchmark_min_time_flag_time_test.cc", "candidate_source": "src/commandlineflags.cc", "distractor_source": "src/string_util.cc"},
]


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
    targets = [spec["target"] for spec in ROOT_SPECS]
    build = run_cmd(["cmake", "--build", str(BUILD), "--target", *targets, "-j2"], "build", timeout=420)
    test_regex = "^(" + "|".join(spec["ctest"] for spec in ROOT_SPECS) + ")$"
    execute = run_cmd(["ctest", "--test-dir", str(BUILD), "-R", test_regex, "--output-on-failure"], "execute", timeout=180)
    passed = bool(configure["passed"] and build["passed"] and execute["passed"])
    rows = []
    for spec in ROOT_SPECS:
        rows.append(
            {
                "stage": STAGE,
                "stage_name": NAME,
                "created_at_utc": now(),
                "repo_family": "google_benchmark",
                "repo_path": str(REPO),
                "language_family": "c_cpp",
                "support_lane": "cpp_abstain_attractor_build_verifier_support",
                "root_key": spec["root_key"],
                "source_path": spec["candidate_source"],
                "selected_test": f"{spec['test_source']}::{spec['ctest']}",
                "test_source": spec["test_source"],
                "distractor_source_path": spec["distractor_source"],
                "build_dir": str(BUILD),
                "configure": configure,
                "build": build,
                "execute": execute,
                "passed": passed,
                "claim_boundary": "Feasibility only; no model score changed.",
            }
        )
    write_jsonl(RESULTS, rows)
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "cpp_benchmark_extra_feasibility_recorded",
        "passed": passed,
        "passing_candidate_count": len(rows) if passed else 0,
        "root_keys": [spec["root_key"] for spec in ROOT_SPECS],
        "outputs": {"summary": rel(SUMMARY), "results": rel(RESULTS)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "passing_candidate_count": artifact["passing_candidate_count"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

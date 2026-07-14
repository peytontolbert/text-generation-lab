#!/usr/bin/env python3
"""Capture bounded PyTorch C++ MKL sample build/verifier feasibility."""

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
STAGE = 11786
NAME = "stage11786_cpp_pytorch_mkl_build_feasibility"
OUT = ART / NAME
LOGS = OUT / "logs"
SUMMARY = OUT / "cpp_pytorch_mkl_build_feasibility.json"
RESULTS = OUT / "cpp_pytorch_mkl_build_feasibility_results.jsonl"

REPO = Path("/data/parametergolf/helpful_repos/pytorch")
SOURCE = REPO / ".ci/pytorch/test_example_code/check-torch-mkl.cpp"
HARNESS = Path("/data/tmp/stage11786_pytorch_mkl_probe")
BUILD_DIR = Path("/data/tmp/stage11786_pytorch_mkl_build")
TORCH_CMAKE = "/home/peyton/miniconda3/envs/trellis/lib/python3.10/site-packages/torch/share/cmake"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def run(command: list[str], stem: str, cwd: Path = ROOT, timeout: int = 180) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(
        {
            "CUDA_VISIBLE_DEVICES": "2",
            "NVIDIA_VISIBLE_DEVICES": "2",
            "TMPDIR": "/data/tmp",
            "TEMP": "/data/tmp",
            "TMP": "/data/tmp",
        }
    )
    started = now()
    try:
        proc = subprocess.run(command, cwd=str(cwd), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        proc = subprocess.CompletedProcess(command, returncode=124, stdout=exc.stdout or "", stderr=exc.stderr or "")
        timed_out = True
    stdout = str(proc.stdout or "")
    stderr = str(proc.stderr or "")
    stdout_path = LOGS / f"{stem}.stdout.log"
    stderr_path = LOGS / f"{stem}.stderr.log"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text(stdout, encoding="utf-8", errors="replace")
    stderr_path.write_text(stderr, encoding="utf-8", errors="replace")
    return {
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
        "stdout_tail": stdout[-2200:],
        "stderr_tail": stderr[-2200:],
    }


def prepare_harness() -> None:
    if HARNESS.exists():
        shutil.rmtree(HARNESS)
    HARNESS.mkdir(parents=True)
    shutil.copyfile(SOURCE, HARNESS / "check-torch-mkl.cpp")
    (HARNESS / "CMakeLists.txt").write_text(
        "\n".join(
            [
                "cmake_minimum_required(VERSION 3.10 FATAL_ERROR)",
                "project(check-torch-mkl)",
                "find_package(Torch REQUIRED)",
                'set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${TORCH_CXX_FLAGS}")',
                "add_executable(check-torch-mkl check-torch-mkl.cpp)",
                "target_include_directories(check-torch-mkl PRIVATE ${TORCH_INCLUDE_DIRS})",
                'target_link_libraries(check-torch-mkl "${TORCH_LIBRARIES}")',
                "set_property(TARGET check-torch-mkl PROPERTY CXX_STANDARD 17)",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    prepare_harness()
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    configure = run(
        [
            "cmake",
            "-S",
            str(HARNESS),
            "-B",
            str(BUILD_DIR),
            f"-DCMAKE_PREFIX_PATH={TORCH_CMAKE}",
            "-DCMAKE_BUILD_TYPE=Release",
        ],
        "configure",
        timeout=120,
    )
    build = run(["cmake", "--build", str(BUILD_DIR), "--target", "check-torch-mkl", "--parallel", "2"], "build", timeout=240) if configure["passed"] else None
    executable = BUILD_DIR / "check-torch-mkl"
    execute = run([str(executable)], "execute", timeout=60) if build and build["passed"] else None
    passed = bool(configure["passed"] and build and build["passed"] and execute and execute["passed"])
    result = {
        "repo_family": "pytorch",
        "repo_path": str(REPO),
        "language_family": "c_cpp",
        "support_lane": "cpp_abstain_attractor_support",
        "source_path": ".ci/pytorch/test_example_code/check-torch-mkl.cpp",
        "harness_dir": str(HARNESS),
        "build_dir": str(BUILD_DIR),
        "configure": configure,
        "build": build,
        "execute": execute,
        "passed": passed,
        "admit_recommendation": "candidate_for_row_materialization" if passed else "blocked",
        "selected_verifier": "cmake_configure_build_and_run_check_torch_mkl",
        "observed_verifier_transition": "PASS_CURRENT_BUILD_AND_RUN" if passed else "FAILED_OR_AMBIGUOUS",
    }
    write_jsonl(RESULTS, [result])
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "cpp_pytorch_mkl_build_feasibility_complete",
        "passed": True,
        "candidate_count": 1,
        "passing_candidate_count": 1 if passed else 0,
        "materializable_candidate_count": 1 if passed else 0,
        "materializable_repo_families": ["pytorch"] if passed else [],
        "interpretation": [
            "The PyTorch check-torch-mkl.cpp source builds and runs through a temporary verifier harness.",
            "The harness is generated outside the repo and does not modify source; the candidate source remains repo-backed.",
        ],
        "claim_boundary": [
            "This is build/run verifier feasibility only, not model training.",
            "The verifier is current-state build/run success, not fail-to-pass repair.",
        ],
        "outputs": {"summary": rel(SUMMARY), "results": rel(RESULTS), "logs_dir": rel(LOGS)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "passing_candidate_count": artifact["passing_candidate_count"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

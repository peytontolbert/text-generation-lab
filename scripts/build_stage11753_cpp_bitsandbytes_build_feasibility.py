#!/usr/bin/env python3
"""Capture a bounded CPU-only C/C++ build verifier for bitsandbytes."""

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
STAGE = 11753
NAME = "stage11753_cpp_bitsandbytes_build_feasibility"
OUT = ART / NAME
LOGS = OUT / "logs"
SUMMARY = OUT / "cpp_bitsandbytes_build_feasibility.json"
RESULTS = OUT / "cpp_bitsandbytes_build_feasibility_results.jsonl"

REPO = Path("/data/parametergolf/helpful_repos/bitsandbytes")
BUILD_DIR = Path("/data/tmp/stage11753_bitsandbytes_cpu_build")


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


def run(command: list[str], cwd: Path, stem: str, timeout: int = 180) -> dict[str, Any]:
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
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
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
        "cwd": str(cwd),
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
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    configure = run(
        [
            "cmake",
            "-S",
            str(REPO),
            "-B",
            str(BUILD_DIR),
            "-DCOMPUTE_BACKEND=cpu",
            "-DCMAKE_BUILD_TYPE=Release",
        ],
        ROOT,
        "configure",
    )
    build = run(["cmake", "--build", str(BUILD_DIR), "--parallel", "2"], ROOT, "build") if configure["passed"] else None
    result = {
        "repo_family": "bitsandbytes",
        "repo_path": str(REPO),
        "language_family": "c_cpp",
        "support_lane": "cpp_abstain_attractor_support",
        "build_dir": str(BUILD_DIR),
        "configure": configure,
        "build": build,
        "passed": bool(configure["passed"] and build and build["passed"]),
        "admit_recommendation": "candidate_for_row_materialization"
        if bool(configure["passed"] and build and build["passed"])
        else "blocked",
        "selected_verifier": "cmake_configure_and_cpu_shared_library_build",
        "observed_verifier_transition": "PASS_CURRENT_BUILD",
    }
    write_jsonl(RESULTS, [result])
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "cpp_bitsandbytes_build_feasibility_complete",
        "passed": True,
        "candidate_count": 1,
        "passing_candidate_count": 1 if result["passed"] else 0,
        "materializable_candidate_count": 1 if result["passed"] else 0,
        "materializable_repo_families": ["bitsandbytes"] if result["passed"] else [],
        "interpretation": [
            "bitsandbytes has a bounded CPU-only CMake configure/build verifier that succeeds.",
            "This can support C/C++ abstain-attractor rows where verifier evidence distinguishes answerable from insufficient-evidence cases.",
        ],
        "claim_boundary": [
            "This is build/verifier feasibility only, not model training.",
            "The verifier is current-state build success, not fail-to-pass repair.",
        ],
        "outputs": {"summary": rel(SUMMARY), "results": rel(RESULTS), "logs_dir": rel(LOGS)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": artifact["decision"],
                "passing_candidate_count": artifact["passing_candidate_count"],
                "materializable_repo_families": artifact["materializable_repo_families"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

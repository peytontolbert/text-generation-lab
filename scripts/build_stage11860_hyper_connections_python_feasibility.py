#!/usr/bin/env python3
"""Capture hyper-connections Python verifier feasibility."""

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
STAGE = 11860
NAME = "stage11860_hyper_connections_python_feasibility"
OUT = ART / NAME
LOGS = OUT / "logs"
SUMMARY = OUT / "hyper_connections_python_feasibility.json"
RESULTS = OUT / "hyper_connections_python_feasibility_results.jsonl"
REPO = Path("/data/repositories/hyper-connections")
SELECTED_TEST = "tests/test_hyper_connections.py::test_manual"
SIBLING_TEST = "tests/test_hyper_connections.py::test_residual_transform"


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


def run_pytest(test_id: str, name: str) -> dict[str, Any]:
    LOGS.mkdir(parents=True, exist_ok=True)
    stdout_log = LOGS / f"{name}.stdout.txt"
    stderr_log = LOGS / f"{name}.stderr.txt"
    command = ["conda", "run", "-n", "trellis", "pytest", "-q", test_id, "--tb=short"]
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
            "PYTHONPATH": str(REPO),
        }
    )
    proc = subprocess.run(command, cwd=REPO, env=env, text=True, capture_output=True, timeout=240)
    stdout_log.write_text(proc.stdout, encoding="utf-8", errors="replace")
    stderr_log.write_text(proc.stderr, encoding="utf-8", errors="replace")
    return {
        "test_filter": test_id,
        "command": command,
        "passed": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout_log": rel(stdout_log),
        "stderr_log": rel(stderr_log),
        "stdout_tail": proc.stdout[-1600:],
        "stderr_tail": proc.stderr[-1600:],
    }


def main() -> None:
    selected = run_pytest(SELECTED_TEST, "selected_manual")
    sibling = run_pytest(SIBLING_TEST, "sibling_residual_transform")
    passed = bool(selected["passed"] and sibling["passed"])
    row = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "repo_family": "hyper_connections",
        "repo_path": str(REPO),
        "language_family": "python",
        "support_lane": "python_verifier_outcome_selected_function_test_support",
        "selected_test": SELECTED_TEST,
        "sibling_test": SIBLING_TEST,
        "selected_result": selected,
        "sibling_result": sibling,
        "source_path": "hyper_connections/hyper_connections.py",
        "selected_test_path": "tests/test_hyper_connections.py",
        "distractor_source_path": "hyper_connections/hyper_connections_channel_first.py",
        "passed": passed,
        "admit_recommendation": "candidate_for_row_materialization" if passed else "blocked_feasibility_failed",
        "claim_boundary": "Feasibility only; no model score changed.",
    }
    write_jsonl(RESULTS, [row])
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "hyper_connections_python_feasibility_recorded",
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

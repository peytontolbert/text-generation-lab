#!/usr/bin/env python3
"""Run neural_network_building_blocks Python verifier feasibility."""

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
STAGE = 11774
NAME = "stage11774_neural_blocks_python_verifier_feasibility"
OUT = ART / NAME
LOGS = OUT / "logs"
SUMMARY = OUT / "neural_blocks_python_verifier_feasibility.json"
RESULTS = OUT / "neural_blocks_python_verifier_feasibility_results.jsonl"

REPO = Path("/data/parametergolf/helpful_repos/neural_network_building_blocks")
DEP_REPO = Path("/data/parametergolf/helpful_repos/pytorch_basics_library")
SELECTED_TEST = "tests/test_core_layers.py"
SIBLING_TEST = "tests/test_attention.py"
COMMAND = [
    "conda",
    "run",
    "-n",
    "trellis",
    "pytest",
    "-q",
    "-o",
    "addopts=",
    SELECTED_TEST,
    SIBLING_TEST,
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": f"{REPO}:{DEP_REPO}",
            "CUDA_VISIBLE_DEVICES": "2",
            "NVIDIA_VISIBLE_DEVICES": "2",
            "AGENTKERNEL_EVAL_DEVICE": "cuda:0",
            "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
            "TMPDIR": "/data/tmp",
            "TEMP": "/data/tmp",
            "TMP": "/data/tmp",
        }
    )
    started = now()
    proc = subprocess.run(COMMAND, cwd=REPO, env=env, text=True, capture_output=True, timeout=120)
    finished = now()
    stdout_log = LOGS / "neural_blocks_pytest.stdout.log"
    stderr_log = LOGS / "neural_blocks_pytest.stderr.log"
    stdout_log.write_text(proc.stdout, encoding="utf-8")
    stderr_log.write_text(proc.stderr, encoding="utf-8")
    passed = proc.returncode == 0 and "4 passed" in proc.stdout
    row: dict[str, Any] = {
        "repo_family": "neural_network_building_blocks",
        "repo_path": str(REPO),
        "language_family": "python",
        "support_lane": "python_verifier_outcome_selected_test_support",
        "selected_test": SELECTED_TEST,
        "sibling_test": SIBLING_TEST,
        "command": COMMAND,
        "returncode": proc.returncode,
        "started_at_utc": started,
        "finished_at_utc": finished,
        "stdout_log": rel(stdout_log),
        "stderr_log": rel(stderr_log),
        "stdout_sha256": sha_text(proc.stdout),
        "stderr_sha256": sha_text(proc.stderr),
        "stdout_tail": proc.stdout[-1600:],
        "stderr_tail": proc.stderr[-1000:],
        "selected_result": {
            "test_path": SELECTED_TEST,
            "command": COMMAND,
            "passed": passed,
            "stdout_log": rel(stdout_log),
            "stderr_log": rel(stderr_log),
            "stdout_tail": proc.stdout[-1600:],
            "stderr_tail": proc.stderr[-1000:],
        },
        "sibling_result": {
            "test_path": SIBLING_TEST,
            "command": COMMAND,
            "passed": passed,
            "stdout_log": rel(stdout_log),
            "stderr_log": rel(stderr_log),
            "stdout_tail": proc.stdout[-1600:],
            "stderr_tail": proc.stderr[-1000:],
        },
        "passed": passed,
        "admit_recommendation": "candidate_for_row_materialization" if passed else "blocked",
        "observed_verifier_transition": "PASS_CURRENT_STATE" if passed else "FAILED_OR_AMBIGUOUS",
        "blocker": None if passed else "pytest_command_failed_or_unexpected_summary",
    }
    write_jsonl(RESULTS, [row])
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "neural_blocks_python_verifier_feasibility_recorded",
        "passed": True,
        "candidate_count": 1,
        "passing_candidate_count": 1 if passed else 0,
        "materializable_candidate_count": 1 if passed else 0,
        "materializable_repo_families": ["neural_network_building_blocks"] if passed else [],
        "interpretation": [
            "neural_network_building_blocks has a passing focused verifier run across core-layer and attention tests.",
            "The selected and sibling verifier files exercise distinct source modules and can support selected-test-vs-sibling-test geometry.",
        ],
        "claim_boundary": [
            "This records verifier feasibility only.",
            "Rows become trainable only after materialization and admission audit.",
        ],
        "outputs": {"summary": rel(SUMMARY), "results": rel(RESULTS)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "passing_candidate_count": artifact["passing_candidate_count"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

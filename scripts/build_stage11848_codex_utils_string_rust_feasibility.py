#!/usr/bin/env python3
"""Capture codex-utils-string Rust verifier feasibility."""

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
STAGE = 11848
NAME = "stage11848_codex_utils_string_rust_feasibility"
OUT = ART / NAME
LOGS = OUT / "logs"
SUMMARY = OUT / "codex_utils_string_rust_feasibility.json"
RESULTS = OUT / "codex_utils_string_rust_feasibility_results.jsonl"
REPO = Path("/data/agentkernel/other_repos/codex/codex-rs")
SELECTED_TEST = "find_uuids_finds_multiple"
SIBLING_TEST = "find_uuids_ignores_invalid"


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


def run_cargo(test_filter: str, name: str) -> dict[str, Any]:
    LOGS.mkdir(parents=True, exist_ok=True)
    stdout_log = LOGS / f"{name}.stdout.txt"
    stderr_log = LOGS / f"{name}.stderr.txt"
    command = ["cargo", "test", "-p", "codex-utils-string", test_filter, "--", "--nocapture"]
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
    proc = subprocess.run(command, cwd=REPO, env=env, text=True, capture_output=True, timeout=180)
    stdout_log.write_text(proc.stdout, encoding="utf-8", errors="replace")
    stderr_log.write_text(proc.stderr, encoding="utf-8", errors="replace")
    return {
        "test_filter": test_filter,
        "command": command,
        "passed": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout_log": rel(stdout_log),
        "stderr_log": rel(stderr_log),
        "stdout_tail": proc.stdout[-1600:],
        "stderr_tail": proc.stderr[-1600:],
    }


def main() -> None:
    selected = run_cargo(SELECTED_TEST, "selected_find_uuids_multiple")
    sibling = run_cargo(SIBLING_TEST, "sibling_find_uuids_invalid")
    passed = bool(selected["passed"] and sibling["passed"])
    row = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "repo_family": "codex_utils_string",
        "repo_path": str(REPO),
        "language_family": "rust",
        "support_lane": "rust_verifier_outcome_selected_inline_test_support",
        "selected_test": SELECTED_TEST,
        "sibling_test": SIBLING_TEST,
        "selected_result": selected,
        "sibling_result": sibling,
        "source_path": "utils/string/src/lib.rs",
        "distractor_source_path": "utils/string/src/truncate.rs",
        "passed": passed,
        "admit_recommendation": "candidate_for_row_materialization" if passed else "blocked_feasibility_failed",
        "claim_boundary": "Feasibility only; no model score changed.",
    }
    write_jsonl(RESULTS, [row])
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "codex_utils_string_rust_feasibility_recorded",
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

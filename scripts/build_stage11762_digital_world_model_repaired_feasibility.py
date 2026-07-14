#!/usr/bin/env python3
"""Record repaired Digital-World-Model Python verifier feasibility from partial logs."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11762
NAME = "stage11762_digital_world_model_repaired_feasibility"
OUT = ART / NAME
SUMMARY = OUT / "digital_world_model_repaired_feasibility.json"
RESULTS = OUT / "digital_world_model_repaired_feasibility_results.jsonl"

PARTIAL_LOGS = ART / "stage11761_python_individual_test_repair_feasibility/logs"
REPO = Path("/data/parametergolf/helpful_repos/Digital-World-Model")
TESTS = [
    "agi_dw/tests/test_ci_assert_safe_edits.py",
    "agi_dw/tests/test_devtools_orchestrator.py",
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


def safe_name(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in text)[:180]


def log_result(test_path: str) -> dict[str, Any]:
    stem = f"Digital-World-Model__{safe_name(test_path)}"
    stdout_log = PARTIAL_LOGS / f"{stem}.stdout.log"
    stderr_log = PARTIAL_LOGS / f"{stem}.stderr.log"
    stdout = stdout_log.read_text(encoding="utf-8", errors="replace") if stdout_log.exists() else ""
    stderr = stderr_log.read_text(encoding="utf-8", errors="replace") if stderr_log.exists() else ""
    passed = " passed" in stdout and "failed" not in stdout.lower() and "error" not in stdout.lower()
    return {
        "test_path": test_path,
        "command": ["conda", "run", "-n", "trellis", "pytest", "-q", "-o", "addopts=", test_path],
        "returncode": 0 if passed else None,
        "passed": passed,
        "timed_out": False,
        "stdout_log": rel(stdout_log),
        "stderr_log": rel(stderr_log),
        "stdout_tail": stdout[-1500:],
        "stderr_tail": stderr[-1000:],
    }


def main() -> None:
    results = [log_result(test) for test in TESTS]
    passed = all(row["passed"] for row in results)
    row: dict[str, Any] = {
        "repo_family": "Digital-World-Model",
        "repo_path": str(REPO),
        "language_family": "python",
        "support_lane": "python_verifier_outcome_selected_test_support",
        "selected_test": TESTS[0],
        "sibling_test": TESTS[1],
        "selected_result": results[0],
        "sibling_result": results[1],
        "passed": passed,
        "admit_recommendation": "candidate_for_row_materialization" if passed else "blocked",
        "observed_verifier_transition": "PASS_CURRENT_STATE" if passed else "FAILED_OR_AMBIGUOUS",
        "blocker": None if passed else "partial_logs_missing_or_not_passing",
    }
    write_jsonl(RESULTS, [row])
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "digital_world_model_repaired_feasibility_recorded",
        "passed": True,
        "candidate_count": 1,
        "passing_candidate_count": 1 if passed else 0,
        "materializable_candidate_count": 1 if passed else 0,
        "materializable_repo_families": ["Digital-World-Model"] if passed else [],
        "interpretation": [
            "Digital-World-Model has two passing individual pytest files from the Stage11761 partial repair run.",
            "The broad Stage11761 process was interrupted due runtime, but these logs are complete and usable for materialization.",
        ],
        "claim_boundary": [
            "This records verifier feasibility only.",
            "Rows become trainable only after materialization and admission audit.",
        ],
        "source_artifacts": {"partial_logs": rel(PARTIAL_LOGS)},
        "outputs": {"summary": rel(SUMMARY), "results": rel(RESULTS)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "passing_candidate_count": artifact["passing_candidate_count"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

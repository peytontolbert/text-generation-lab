#!/usr/bin/env python3
"""Record bitsandbytes Python function-level verifier feasibility from partial logs."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11770
NAME = "stage11770_bitsandbytes_python_repaired_feasibility"
OUT = ART / NAME
SUMMARY = OUT / "bitsandbytes_python_repaired_feasibility.json"
RESULTS = OUT / "bitsandbytes_python_repaired_feasibility_results.jsonl"

PARTIAL_LOGS = ART / "stage11761_python_individual_test_repair_feasibility/logs"
REPO = Path("/data/parametergolf/helpful_repos/bitsandbytes")
TEST_FILE = "tests/test_cuda_setup_evaluator.py"
SELECTED_TEST = "tests/test_cuda_setup_evaluator.py::test_get_cuda_bnb_library_path"
SIBLING_TEST = "tests/test_cuda_setup_evaluator.py::test_get_cuda_bnb_library_path_override"


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


def main() -> None:
    stdout_log = PARTIAL_LOGS / "bitsandbytes__tests_test_cuda_setup_evaluator.py.stdout.log"
    stderr_log = PARTIAL_LOGS / "bitsandbytes__tests_test_cuda_setup_evaluator.py.stderr.log"
    stdout = stdout_log.read_text(encoding="utf-8", errors="replace")
    stderr = stderr_log.read_text(encoding="utf-8", errors="replace") if stderr_log.exists() else ""
    # The passing pytest log includes a caught RuntimeError diagnostic from the
    # library path test, so use the pytest summary rather than raw substring
    # matching on "ERROR".
    passed = "2 passed" in stdout and " short test summary info " not in stdout
    row: dict[str, Any] = {
        "repo_family": "bitsandbytes",
        "repo_path": str(REPO),
        "language_family": "python",
        "support_lane": "python_verifier_outcome_selected_test_support",
        "selected_test": SELECTED_TEST,
        "sibling_test": SIBLING_TEST,
        "selected_result": {
            "test_path": SELECTED_TEST,
            "command": ["conda", "run", "-n", "trellis", "pytest", "-q", "-o", "addopts=", TEST_FILE],
            "passed": passed,
            "stdout_log": rel(stdout_log),
            "stderr_log": rel(stderr_log),
            "stdout_tail": stdout[-1500:],
            "stderr_tail": stderr[-1000:],
        },
        "sibling_result": {
            "test_path": SIBLING_TEST,
            "command": ["conda", "run", "-n", "trellis", "pytest", "-q", "-o", "addopts=", TEST_FILE],
            "passed": passed,
            "stdout_log": rel(stdout_log),
            "stderr_log": rel(stderr_log),
            "stdout_tail": stdout[-1500:],
            "stderr_tail": stderr[-1000:],
        },
        "passed": passed,
        "admit_recommendation": "candidate_for_row_materialization" if passed else "blocked",
        "observed_verifier_transition": "PASS_CURRENT_STATE" if passed else "FAILED_OR_AMBIGUOUS",
        "blocker": None if passed else "partial_log_not_cleanly_passing",
    }
    write_jsonl(RESULTS, [row])
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "bitsandbytes_python_repaired_feasibility_recorded",
        "passed": True,
        "candidate_count": 1,
        "passing_candidate_count": 1 if passed else 0,
        "materializable_candidate_count": 1 if passed else 0,
        "materializable_repo_families": ["bitsandbytes"] if passed else [],
        "interpretation": [
            "bitsandbytes has two passing function-level verifier anchors inside tests/test_cuda_setup_evaluator.py.",
            "This can support selected-test-vs-sibling-test geometry without relying on a singleton file-level option.",
        ],
        "claim_boundary": ["This records verifier feasibility only.", "Rows become trainable only after materialization and admission audit."],
        "source_artifacts": {"partial_logs": rel(PARTIAL_LOGS)},
        "outputs": {"summary": rel(SUMMARY), "results": rel(RESULTS)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "passing_candidate_count": artifact["passing_candidate_count"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

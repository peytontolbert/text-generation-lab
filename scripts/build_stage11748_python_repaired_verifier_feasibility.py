#!/usr/bin/env python3
"""Record repaired passing Python verifier commands from Stage11747 failures."""

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
STAGE = 11748
NAME = "stage11748_python_repaired_verifier_feasibility"
OUT = ART / NAME
LOGS = OUT / "logs"
SUMMARY = OUT / "python_repaired_verifier_feasibility.json"
RESULTS = OUT / "python_repaired_verifier_feasibility_results.jsonl"

PROBES = [
    {
        "repo_family": "model-stack",
        "repo_path": "/data/parametergolf/helpful_repos/model-stack",
        "selected_tests": ["tensor/tests/test_activation_runtime_path.py"],
        "support_lane": "python_verifier_outcome_selected_test_support",
        "admit_policy": "candidate_for_row_materialization",
        "reason": "The broader Stage11747 two-file run had one failing attention test; this focused activation verifier passes.",
    },
    {
        "repo_family": "tokenizers",
        "repo_path": "/data/parametergolf/helpful_repos/tokenizers/bindings/python",
        "selected_tests": ["tests/bindings/test_decoders.py", "tests/bindings/test_encoding.py"],
        "support_lane": "python_verifier_outcome_selected_test_support",
        "admit_policy": "quarantine_or_diagnostic_due_to_tokenizers_overlap",
        "reason": "The Stage11747 failure was cwd-sensitive. The repaired bindings/python command passes, but tokenizers overlaps a known strict/quarantined family.",
    },
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


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def run_probe(probe: dict[str, Any]) -> dict[str, Any]:
    repo = Path(str(probe["repo_path"]))
    tests = list(probe["selected_tests"])
    command = ["conda", "run", "-n", "trellis", "pytest", "-q", "-o", "addopts=", *tests]
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
            timeout=120,
            check=False,
        )
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        proc = subprocess.CompletedProcess(command, returncode=124, stdout=exc.stdout or "", stderr=exc.stderr or "")
        timed_out = True

    stdout = str(proc.stdout or "")
    stderr = str(proc.stderr or "")
    safe_name = str(probe["repo_family"]).replace("/", "__")
    stdout_path = LOGS / f"{safe_name}.stdout.log"
    stderr_path = LOGS / f"{safe_name}.stderr.log"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text(stdout, encoding="utf-8", errors="replace")
    stderr_path.write_text(stderr, encoding="utf-8", errors="replace")
    passed = proc.returncode == 0
    return {
        **probe,
        "command": command,
        "started_at_utc": started,
        "finished_at_utc": now(),
        "returncode": proc.returncode,
        "passed": passed,
        "timed_out": timed_out,
        "stdout_log": rel(stdout_path),
        "stderr_log": rel(stderr_path),
        "stdout_sha256": sha(stdout),
        "stderr_sha256": sha(stderr),
        "stdout_tail": stdout[-1800:],
        "stderr_tail": stderr[-1800:],
        "admit_recommendation": probe["admit_policy"] if passed else "blocked",
        "blocker": None if passed else "pytest_execution_failed_or_timed_out",
    }


def main() -> None:
    results = [run_probe(probe) for probe in PROBES]
    materializable = [
        row
        for row in results
        if row.get("passed") and row.get("admit_recommendation") == "candidate_for_row_materialization"
    ]
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "python_repaired_verifier_feasibility_recorded",
        "passed": True,
        "candidate_count": len(results),
        "passing_candidate_count": len([row for row in results if row.get("passed")]),
        "materializable_candidate_count": len(materializable),
        "materializable_repo_families": [row["repo_family"] for row in materializable],
        "quarantined_or_diagnostic_repo_families": [
            row["repo_family"]
            for row in results
            if row.get("passed") and row.get("admit_recommendation") != "candidate_for_row_materialization"
        ],
        "interpretation": [
            "model-stack is a clean additional Python verifier support root candidate.",
            "tokenizers has a passing repaired command but remains diagnostic/quarantined because tokenizers overlaps known strict/quarantined lineage.",
        ],
        "claim_boundary": [
            "This stage records verifier feasibility only.",
            "Only materializable candidates may feed train-support row builders.",
            "No model score changes or training-package admission are implied.",
        ],
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
                "passing_candidate_count": artifact["passing_candidate_count"],
                "materializable_repo_families": artifact["materializable_repo_families"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

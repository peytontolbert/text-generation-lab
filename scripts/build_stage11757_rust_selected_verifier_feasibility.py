#!/usr/bin/env python3
"""Capture non-tokenizers Rust selected-inline-test verifier feasibility."""

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
STAGE = 11757
NAME = "stage11757_rust_selected_verifier_feasibility"
OUT = ART / NAME
LOGS = OUT / "logs"
SUMMARY = OUT / "rust_selected_verifier_feasibility.json"
RESULTS = OUT / "rust_selected_verifier_feasibility_results.jsonl"

PROBES = [
    {
        "repo_family": "agent_kernel_rust_wasm",
        "repo_path": "/data/agentkernel/agent_kernel_rust_wasm",
        "manifest_path": "/data/agentkernel/agent_kernel_rust_wasm/Cargo.toml",
        "selected_test": "policy::tests::parses_json_decision_with_code_execute",
        "sibling_test": "policy::tests::plain_code_mode_falls_back_to_propose_code",
        "source_path": "src/policy.rs",
        "distractor_source_path": "src/context.rs",
    },
    {
        "repo_family": "agent_kernel_rust_wasm",
        "repo_path": "/data/agentkernel/agent_kernel_rust_wasm",
        "manifest_path": "/data/agentkernel/agent_kernel_rust_wasm/Cargo.toml",
        "selected_test": "context::tests::ranks_title_and_context_matches",
        "sibling_test": "context::tests::compiles_python_shaped_context_packet",
        "source_path": "src/context.rs",
        "distractor_source_path": "src/policy.rs",
    },
]


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


def run_test(probe: dict[str, Any], test_name: str, stem: str) -> dict[str, Any]:
    command = ["cargo", "test", "--manifest-path", probe["manifest_path"], test_name, "--lib"]
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
            cwd=str(ROOT),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=90,
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
        "test_name": test_name,
        "command": command,
        "started_at_utc": started,
        "finished_at_utc": now(),
        "returncode": proc.returncode,
        "passed": proc.returncode == 0 and "running 1 test" in stdout + stderr,
        "timed_out": timed_out,
        "stdout_log": rel(stdout_path),
        "stderr_log": rel(stderr_path),
        "stdout_sha256": sha(stdout),
        "stderr_sha256": sha(stderr),
        "stdout_tail": stdout[-1600:],
        "stderr_tail": stderr[-1600:],
    }


def main() -> None:
    results = []
    for index, probe in enumerate(PROBES, start=1):
        selected = run_test(probe, probe["selected_test"], f"probe{index}_selected")
        sibling = run_test(probe, probe["sibling_test"], f"probe{index}_sibling")
        passed = bool(selected["passed"] and sibling["passed"])
        results.append(
            {
                **probe,
                "probe_id": f"stage11757::agent_kernel_rust_wasm::{index}",
                "language_family": "rust",
                "support_lane": "rust_verifier_outcome_selected_test_support",
                "selected_result": selected,
                "sibling_result": sibling,
                "passed": passed,
                "admit_recommendation": "candidate_for_row_materialization" if passed else "blocked",
                "observed_verifier_transition": "PASS_CURRENT_STATE" if passed else "FAILED_OR_AMBIGUOUS",
                "blocker": None if passed else "selected_or_sibling_cargo_test_failed",
            }
        )

    materializable = [row for row in results if row.get("passed")]
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "rust_selected_verifier_feasibility_complete",
        "passed": True,
        "candidate_count": len(results),
        "passing_candidate_count": len(materializable),
        "materializable_candidate_count": len(materializable),
        "materializable_repo_families": sorted({row["repo_family"] for row in materializable}),
        "interpretation": [
            "agent_kernel_rust_wasm provides non-tokenizers selected-inline-test Rust verifier support candidates.",
            "Each materializable probe has both a selected test and a sibling distractor test that execute as exactly one cargo test.",
        ],
        "claim_boundary": [
            "This stage records verifier feasibility only.",
            "Rows become trainable only after materialization and admission audit.",
            "This is current-state verifier support, not fail-to-pass repair.",
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

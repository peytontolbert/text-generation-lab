#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12336_bears_local_hydration_blocker_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
REQUESTS = ROOT / "runs/local/artifacts/stage12333_bears_hydration_request/bears_priority_hydration_requests.jsonl"
REPAIR_THEM_ALL = Path("/arxiv/repositories/RepairThemAll")
BEARS_SUBMODULE = REPAIR_THEM_ALL / "benchmarks/bears"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_readonly(args: list[str], cwd: Path | None = None) -> dict[str, Any]:
    try:
        proc = subprocess.run(args, cwd=str(cwd) if cwd else None, text=True, capture_output=True, timeout=30, check=False)
        return {
            "args": args,
            "exit_code": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except Exception as exc:  # pragma: no cover - diagnostic artifact
        return {"args": args, "exit_code": None, "stdout": "", "stderr": repr(exc)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    requests = read_jsonl(REQUESTS)
    probe_results = {
        "repair_them_all_exists": REPAIR_THEM_ALL.exists(),
        "bears_submodule_path_exists": BEARS_SUBMODULE.exists(),
        "bears_dot_git_exists": (BEARS_SUBMODULE / ".git").exists(),
        "submodule_status": run_readonly(["git", "submodule", "status", "--recursive"], cwd=REPAIR_THEM_ALL)
        if REPAIR_THEM_ALL.exists()
        else None,
        "bears_tree_entry": run_readonly(["git", "ls-tree", "HEAD", "benchmarks/bears"], cwd=REPAIR_THEM_ALL)
        if REPAIR_THEM_ALL.exists()
        else None,
        "bears_revparse": run_readonly(["git", "-C", str(BEARS_SUBMODULE), "rev-parse", "--show-toplevel"])
        if BEARS_SUBMODULE.exists()
        else None,
    }
    requested_branches = [
        {
            "bug_id": row.get("bug_id"),
            "branch_id": row.get("branch_id"),
            "buggy_commit_sha": row.get("buggy_commit_sha"),
            "fixer_commit_sha": row.get("fixer_commit_sha"),
        }
        for row in requests
    ]
    blockers = []
    if not REPAIR_THEM_ALL.exists():
        blockers.append("repair_them_all_repo_missing")
    if not BEARS_SUBMODULE.exists():
        blockers.append("bears_submodule_path_missing")
    if not (BEARS_SUBMODULE / ".git").exists():
        blockers.append("bears_submodule_uninitialized_no_local_git")
    revparse = probe_results.get("bears_revparse") or {}
    if revparse.get("stdout") == str(REPAIR_THEM_ALL):
        blockers.append("bears_git_commands_fall_back_to_parent_repo")
    if not requests:
        blockers.append("stage12333_priority_requests_missing")
    decision = (
        "bears_local_hydration_blocked_fail_closed"
        if blockers
        else "bears_local_hydration_preflight_clear_but_execution_still_not_run"
    )
    summary = {
        "stage": STAGE,
        "decision": decision,
        "training_allowed": False,
        "claim_boundary": (
            "Fail-closed local preflight only. No Bears checkout, verifier command, train-support row, "
            "Level-3 row, patch-trace row, repair row, or sealed eval row is admitted."
        ),
        "source_stage": "stage12333_bears_hydration_request",
        "requested_candidate_count": len(requested_branches),
        "requested_branches": requested_branches,
        "probe_results": probe_results,
        "blocked_reasons": blockers,
        "hard_rejects": [
            "run RepairThemAll checkout.py while Bears submodule is uninitialized",
            "treat parent RepairThemAll refs as Bears refs",
            "admit metadata-only Bears rows",
            "admit rows without buggy failure reproduction and fixed selected-test pass",
            "emit raw diff or raw verifier output into model-facing rows",
        ],
        "requirements_before_next_execution_attempt": [
            "benchmarks/bears is an initialized Bears repository",
            "requested branch IDs resolve inside the Bears repository",
            "buggy and fixed checkout SHAs match metadata",
            "buggy selected test fails with command output captured",
            "fixed selected test passes with command output captured",
            "same-source patch-verifier causality audit passes",
        ],
        "next_stage": "stage123xx_bears_hydration_executor_only_after_submodule_initialization",
    }
    write_json(OUT / "bears_local_hydration_blocker_audit.json", summary)
    (OUT / "BEARS_LOCAL_HYDRATION_BLOCKER_AUDIT_STAGE12336.md").write_text(
        "# Stage12336 Bears Local Hydration Blocker Audit\n\n"
        "Bears remains fail-closed locally because the benchmark submodule is not initialized. "
        "This stage admits zero rows and exists to prevent metadata-only repair claims.\n",
        encoding="utf-8",
    )
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()

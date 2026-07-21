#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12335_dspy_web_focused_verifier_executor"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
REPO = Path("/data/repositories/dspy/inspect-app/react-app")
COMMAND = ["npm", "test", "--", "--watchAll=false", "src/App.test.js"]


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    logs = OUT / "logs"
    logs.mkdir(exist_ok=True)
    blockers = []
    if not REPO.exists():
        blockers.append("repo_missing")
    if not (REPO / "node_modules" / ".bin" / "react-scripts").exists():
        blockers.append("react_scripts_missing")
    commit = ""
    if not blockers:
        commit = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
        env = os.environ.copy()
        env.update({"CI": "true", "NO_UPDATE_NOTIFIER": "1"})
        proc = subprocess.run(
            COMMAND,
            cwd=REPO,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180,
        )
        (logs / "dspy_react_app_focused_stdout.log").write_text(proc.stdout, encoding="utf-8", errors="replace")
        (logs / "dspy_react_app_focused_stderr.log").write_text(proc.stderr, encoding="utf-8", errors="replace")
        returncode = proc.returncode
    else:
        returncode = None
        (logs / "dspy_react_app_focused_stdout.log").write_text("", encoding="utf-8")
        (logs / "dspy_react_app_focused_stderr.log").write_text("blocked before execution: " + ",".join(blockers), encoding="utf-8")
    source_files = ["src/App.js", "src/index.js", "src/App.css", "src/reportWebVitals.js"]
    test_files = ["src/App.test.js", "src/setupTests.js"]
    source_hash_refs = [f"{p}@{sha_file(REPO / p)[:12]}" for p in source_files if (REPO / p).exists()]
    test_hash_refs = [f"{p}@{sha_file(REPO / p)}" for p in test_files if (REPO / p).exists()]
    stdout_hash = sha_file(logs / "dspy_react_app_focused_stdout.log")
    stderr_hash = sha_file(logs / "dspy_react_app_focused_stderr.log")
    passed = returncode == 0
    if not source_hash_refs:
        blockers.append("source_hash_refs_missing")
    if not test_hash_refs:
        blockers.append("test_hash_refs_missing")
    if returncode != 0:
        blockers.append("focused_verifier_nonzero_or_not_run")
    record = {
        "stage": STAGE,
        "decision": "dspy_web_focused_verifier_executed" if returncode is not None else "dspy_web_focused_verifier_blocked_before_execution",
        "training_allowed": False,
        "claim_boundary": "Verifier execution evidence only. No train-support rows admitted in this stage.",
        "repo_family": "dspy",
        "subrepo_family": "react_app",
        "repo_path": str(REPO),
        "commit_sha": commit,
        "focused_verifier_command": "CI=true npm test -- --watchAll=false src/App.test.js",
        "focused_verifier_exit_code": returncode,
        "focused_verifier_passed": passed,
        "stdout_log": str(logs / "dspy_react_app_focused_stdout.log"),
        "stderr_log": str(logs / "dspy_react_app_focused_stderr.log"),
        "stdout_sha256": stdout_hash,
        "stderr_sha256": stderr_hash,
        "source_hash_refs": source_hash_refs,
        "test_hash_refs": test_hash_refs,
        "admission": {
            "training_allowed": False,
            "train_support_allowed": False,
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
            "level3_admitted": False,
            "patch_trace_admitted": False,
            "repair_claim_admitted": False,
            "admission_status": "verifier_evidence_only",
        },
        "blocked_reasons_before_row_admission": blockers + [
            "needs_gold_perspective_answers",
            "needs_selected_changed_path",
            "needs_selected_symptom_or_call_path_evidence",
            "needs_anti_cheat_renderer",
            "needs_lineage_audit",
        ],
        "raw_content_policy": {
            "raw_source_emitted": False,
            "raw_verifier_log_emitted_to_model_row": False,
        },
    }
    (OUT / "dspy_web_focused_verifier_execution.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

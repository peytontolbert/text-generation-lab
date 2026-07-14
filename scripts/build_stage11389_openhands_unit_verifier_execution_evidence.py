#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11389
NAME = "stage11389_openhands_unit_verifier_execution_evidence"
OUT = ART / NAME
SUMMARY = OUT / "openhands_unit_verifier_execution_evidence.json"
LOG_DIR = OUT / "logs"
OPENHANDS = Path("/data/tmp/stage11360_openhands_frontend")

COMMANDS = [
    {
        "root_id": "openhands_websocket_url",
        "cmd": ["npm", "run", "test", "--", "__tests__/utils/websocket-url.test.ts"],
        "log": "openhands_websocket_url.log",
        "expected": "passed",
    },
    {
        "root_id": "openhands_parse_pr_url",
        "cmd": ["npm", "run", "test", "--", "__tests__/parse-pr-url.test.ts"],
        "log": "openhands_parse_pr_url.log",
        "expected": "passed",
    },
    {
        "root_id": "openhands_input_validation",
        "cmd": ["npm", "run", "test", "--", "__tests__/utils/input-validation.test.ts"],
        "log": "openhands_input_validation.log",
        "expected": "passed",
    },
    {
        "root_id": "openhands_avatar_menu_browser_blocker",
        "cmd": ["npm", "run", "test:e2e", "--", "tests/avatar-menu.spec.ts"],
        "log": "openhands_avatar_menu_browser_blocker.log",
        "expected": "blocked_missing_browser",
    },
]


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for item in COMMANDS:
        proc = subprocess.run(
            item["cmd"],
            cwd=OPENHANDS,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        log_path = LOG_DIR / item["log"]
        log_path.write_text(
            "$ " + " ".join(item["cmd"]) + "\n\n[stdout]\n" + proc.stdout + "\n[stderr]\n" + proc.stderr,
            encoding="utf-8",
        )
        passed = proc.returncode == 0
        expected = item["expected"]
        status = "verifier_executed_passed" if passed else "verifier_blocked_or_failed"
        if expected == "blocked_missing_browser" and "Executable doesn't exist" in (proc.stdout + proc.stderr):
            status = "blocked_missing_playwright_browser_binaries"
        results.append(
            {
                "root_id": item["root_id"],
                "command": item["cmd"],
                "workdir": str(OPENHANDS),
                "returncode": proc.returncode,
                "passed": passed,
                "expected": expected,
                "execution_status": status,
                "log": rel(log_path),
                "stdout_tail": proc.stdout[-1600:],
                "stderr_tail": proc.stderr[-1600:],
            }
        )
    scoreable = [r for r in results if r["execution_status"] == "verifier_executed_passed"]
    blocked = [r for r in results if r["execution_status"] != "verifier_executed_passed"]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": len(scoreable) >= 3,
        "decision": "openhands_unit_verifier_roots_ready" if len(scoreable) >= 3 else "openhands_unit_verifier_roots_blocked",
        "counts": {
            "commands": len(results),
            "scoreable_roots": len(scoreable),
            "blocked_roots": len(blocked),
            "passed_commands": sum(1 for r in results if r["passed"]),
            "failed_commands": sum(1 for r in results if not r["passed"]),
        },
        "results": results,
        "scoreable_root_ids": [r["root_id"] for r in scoreable],
        "blocked_root_ids": [r["root_id"] for r in blocked],
        "outputs": {"summary": rel(SUMMARY), "logs": rel(LOG_DIR)},
        "recommended_next_action": "Project the three passed OpenHands unit-verifier roots into heldout-candidate Web maintainer rows; keep avatar-menu blocked until Playwright browsers are installed.",
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"passed": summary["passed"], "counts": summary["counts"], "outputs": summary["outputs"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

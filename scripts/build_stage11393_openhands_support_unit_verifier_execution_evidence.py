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
STAGE = 11393
NAME = "stage11393_openhands_support_unit_verifier_execution_evidence"
OUT = ART / NAME
SUMMARY = OUT / "openhands_support_unit_verifier_execution_evidence.json"
LOG_DIR = OUT / "logs"
OPENHANDS = Path("/data/tmp/stage11360_openhands_frontend")

COMMANDS = [
    {
        "root_id": "openhands_shell_tokenize",
        "cmd": ["npm", "run", "test", "--", "__tests__/utils/shell-tokenize.test.ts"],
        "log": "openhands_shell_tokenize.log",
    },
    {
        "root_id": "openhands_format_time_delta",
        "cmd": ["npm", "run", "test", "--", "__tests__/utils/format-time-delta.test.ts"],
        "log": "openhands_format_time_delta.log",
    },
    {
        "root_id": "openhands_extract_next_page",
        "cmd": ["npm", "run", "test", "--", "__tests__/utils/extract-next-page-from-link.test.ts"],
        "log": "openhands_extract_next_page.log",
    },
    {
        "root_id": "openhands_vscode_url_helper",
        "cmd": ["npm", "run", "test", "--", "__tests__/utils/vscode-url-helper.test.ts"],
        "log": "openhands_vscode_url_helper.log",
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
        results.append(
            {
                "root_id": item["root_id"],
                "command": item["cmd"],
                "workdir": str(OPENHANDS),
                "returncode": proc.returncode,
                "passed": proc.returncode == 0,
                "execution_status": "verifier_executed_passed" if proc.returncode == 0 else "verifier_blocked_or_failed",
                "log": rel(log_path),
                "stdout_tail": proc.stdout[-1600:],
                "stderr_tail": proc.stderr[-1600:],
            }
        )
    scoreable = [r for r in results if r["passed"]]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": len(scoreable) == len(COMMANDS),
        "decision": "openhands_support_unit_verifier_roots_ready" if len(scoreable) == len(COMMANDS) else "openhands_support_unit_verifier_roots_partial",
        "counts": {
            "commands": len(results),
            "scoreable_roots": len(scoreable),
            "passed_commands": sum(1 for r in results if r["passed"]),
            "failed_commands": sum(1 for r in results if not r["passed"]),
        },
        "results": results,
        "scoreable_root_ids": [r["root_id"] for r in scoreable],
        "outputs": {"summary": rel(SUMMARY), "logs": rel(LOG_DIR)},
        "recommended_next_action": "Project these roots into train-support rows while keeping Stage11390 heldout rows sealed.",
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"passed": summary["passed"], "counts": summary["counts"], "outputs": summary["outputs"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

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
STAGE = 11387
NAME = "stage11387_mcp_fresh_web_verifier_execution_evidence"
OUT = ART / NAME
SUMMARY = OUT / "mcp_fresh_web_verifier_execution_evidence.json"
LOG_DIR = OUT / "logs"
MCP = Path("/data/tmp/stage11353_mcp_typescript_sdk")

COMMANDS = [
    {
        "root_id": "mcp_tool_name_validation",
        "workdir": MCP,
        "cmd": ["pnpm", "--filter", "@modelcontextprotocol/core", "test", "--", "test/shared/toolNameValidation.test.ts"],
        "log": "mcp_tool_name_validation.log",
    },
    {
        "root_id": "mcp_fetch_init_header_merge",
        "workdir": MCP,
        "cmd": ["pnpm", "--filter", "@modelcontextprotocol/core", "test", "--", "test/shared/transport.test.ts"],
        "log": "mcp_fetch_init_header_merge.log",
    },
    {
        "root_id": "mcp_server_initialize_protocol",
        "workdir": MCP,
        "cmd": ["pnpm", "--filter", "@modelcontextprotocol/server", "test", "--", "test/server/server.test.ts"],
        "log": "mcp_server_initialize_protocol.log",
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
            cwd=item["workdir"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )
        log_path = LOG_DIR / item["log"]
        log_path.write_text(
            "$ " + " ".join(item["cmd"]) + "\n\n[stdout]\n" + proc.stdout + "\n[stderr]\n" + proc.stderr,
            encoding="utf-8",
        )
        results.append(
            {
                "root_id": item["root_id"],
                "workdir": str(item["workdir"]),
                "command": item["cmd"],
                "returncode": proc.returncode,
                "passed": proc.returncode == 0,
                "log": rel(log_path),
                "stdout_tail": proc.stdout[-1200:],
                "stderr_tail": proc.stderr[-1200:],
            }
        )
    passed = all(r["passed"] for r in results)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": passed,
        "decision": "mcp_fresh_web_verifier_execution_evidence_ready" if passed else "mcp_fresh_web_verifier_execution_failed",
        "counts": {
            "commands": len(results),
            "passed_commands": sum(1 for r in results if r["passed"]),
            "failed_commands": sum(1 for r in results if not r["passed"]),
        },
        "results": results,
        "outputs": {"summary": rel(SUMMARY), "logs": rel(LOG_DIR)},
        "recommended_next_action": "Project these three executed MCP roots into Web maintainer rows if all commands passed.",
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"passed": passed, "counts": summary["counts"], "outputs": summary["outputs"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

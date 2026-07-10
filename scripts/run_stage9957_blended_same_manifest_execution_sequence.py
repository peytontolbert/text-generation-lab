#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "runs/local/artifacts/stage9957_blended_same_manifest_execution_runbook/blended_same_manifest_execution_runbook.json"
EXECUTABLE_STEP_KINDS = {"model_execution", "gemma_execution"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_runbook(path: Path = RUNBOOK) -> dict[str, Any]:
    data = load_json(path)
    if not isinstance(data, dict) or data.get("passed") is not True:
        raise ValueError(f"runbook not passed or missing: {path}")
    return data


def step_index(runbook: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = runbook.get("steps") if isinstance(runbook.get("steps"), list) else []
    return {str(row.get("step_id") or ""): row for row in rows if isinstance(row, dict)}


def executable_step_ids(runbook: dict[str, Any]) -> list[str]:
    return [
        str(row.get("step_id") or "")
        for row in (runbook.get("steps") or [])
        if isinstance(row, dict) and str(row.get("kind") or "") in EXECUTABLE_STEP_KINDS
    ]


def command_for_step(runbook: dict[str, Any], step_id: str) -> list[str]:
    rows = step_index(runbook)
    row = rows.get(step_id)
    if not isinstance(row, dict):
        raise KeyError(f"unknown step_id: {step_id}")
    if str(row.get("kind") or "") not in EXECUTABLE_STEP_KINDS:
        raise ValueError(f"step is not executable: {step_id}")
    command = row.get("command")
    if not isinstance(command, list) or not command:
        raise ValueError(f"missing command for step: {step_id}")
    return [str(item) for item in command]


def execute_step(runbook: dict[str, Any], step_id: str) -> subprocess.CompletedProcess[str]:
    command = command_for_step(runbook, step_id)
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runbook", type=Path, default=RUNBOOK)
    parser.add_argument("--step-id")
    parser.add_argument("--print-command", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-execution", action="store_true")
    parser.add_argument("--list-steps", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    runbook = load_runbook(args.runbook)
    rows = runbook.get("steps") if isinstance(runbook.get("steps"), list) else []

    if args.list_steps:
        print(json.dumps({
            "step_ids": [str(row.get("step_id") or "") for row in rows if isinstance(row, dict)],
            "executable_step_ids": executable_step_ids(runbook),
        }, indent=2, sort_keys=True))
        return

    if args.step_id and args.print_command:
        print(json.dumps({
            "step_id": args.step_id,
            "command": command_for_step(runbook, args.step_id),
        }, indent=2, sort_keys=True))
        return

    if args.step_id and args.execute:
        if not args.allow_execution:
            raise SystemExit("refusing execution without --allow-execution")
        completed = execute_step(runbook, args.step_id)
        print(json.dumps({
            "step_id": args.step_id,
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }, indent=2, sort_keys=True))
        raise SystemExit(completed.returncode)

    print(json.dumps({
        "runbook": str(args.runbook.relative_to(ROOT)) if args.runbook.is_relative_to(ROOT) else str(args.runbook),
        "claim_rule": runbook.get("claim_rule"),
        "step_ids": [str(row.get("step_id") or "") for row in rows if isinstance(row, dict)],
        "executable_step_ids": executable_step_ids(runbook),
        "execution_requires_allow_execution": True,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

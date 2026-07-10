#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "runs/local/artifacts/stage9971_blended_weak_language_same_manifest_execution_runbook/blended_weak_language_same_manifest_execution_runbook.json"
EXECUTABLE_STEP_KINDS = {"model_execution", "gemma_execution"}
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
FALLBACK_PYTHONS = [
    Path("/home/peyton/miniconda3/envs/code_assist_runtime/bin/python"),
    Path("/home/peyton/miniconda3/envs/ai/bin/python"),
    Path("/home/peyton/miniconda3/envs/hunyuan_part/bin/python"),
    Path("/home/peyton/miniconda3/envs/trellis/bin/python"),
]


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


def _python_runtime_ok(python_exe: str) -> bool:
    probe = (
        "import torch; import torch.nn; "
        "from tokenizers import Tokenizer; "
        f"Tokenizer.from_file({str(TOKENIZER_JSON)!r}); "
        "print('ok')"
    )
    completed = subprocess.run(
        [python_exe, "-c", probe],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def resolve_command_for_execution(command: list[str], step_id: str) -> list[str]:
    if step_id != "run_stage9965_hundred_m":
        return command
    env_override = os.environ.get("AGENTKERNEL_STAGE9965_PYTHON")
    candidates: list[Path] = []
    if env_override:
        candidates.append(Path(env_override))
    candidates.append(Path(command[0]))
    candidates.append(Path(sys.executable))
    candidates.extend(FALLBACK_PYTHONS)
    seen: set[str] = set()
    for candidate in candidates:
        text = str(candidate)
        if text in seen or not candidate.exists():
            continue
        seen.add(text)
        if _python_runtime_ok(text):
            resolved = list(command)
            resolved[0] = text
            return resolved
    raise RuntimeError("no working python runtime found for stage9965 model execution")


def execute_step(runbook: dict[str, Any], step_id: str) -> subprocess.CompletedProcess[str]:
    command = resolve_command_for_execution(command_for_step(runbook, step_id), step_id)
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
        raw = command_for_step(runbook, args.step_id)
        resolved = resolve_command_for_execution(raw, args.step_id) if args.step_id == "run_stage9965_hundred_m" else raw
        print(json.dumps({
            "step_id": args.step_id,
            "command": raw,
            "resolved_command": resolved,
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

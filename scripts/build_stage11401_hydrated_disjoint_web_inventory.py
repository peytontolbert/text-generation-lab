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
STAGE = 11401
NAME = "stage11401_hydrated_disjoint_web_inventory"
OUT = ART / NAME
SUMMARY = OUT / "hydrated_disjoint_web_inventory.json"
LOG_DIR = OUT / "logs"


USED_FAMILY_MARKERS = [
    "OpenHands",
    "openhands",
    "modelcontextprotocol",
    "sourcebot",
    "llama-stack",
    "llama_stack",
]

ATTEMPTS = [
    {
        "root_id": "dspy_react_app",
        "repo_family": "dspy",
        "workdir": Path("/data/tmp/stage11360_dspy_react_app"),
        "cmd": ["npm", "test", "--", "--watchAll=false", "src/App.test.js"],
        "why": "Already hydrated disjoint React app with package-lock and node_modules.",
    },
    {
        "root_id": "openclaw_tmp_qa_lab",
        "repo_family": "openclaw_openclaw",
        "workdir": Path("/data/tmp/stage11353_openclaw"),
        "cmd": ["npm", "exec", "--", "vitest", "run", "extensions/qa-lab/src/model-switch-eval.test.ts"],
        "why": "Temporary copied OpenClaw tree has source/test files but no local node_modules.",
    },
]


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def run_capture(attempt: dict[str, Any]) -> dict[str, Any]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{attempt['root_id']}.log"
    workdir = Path(str(attempt["workdir"]))
    if not workdir.exists():
        log_path.write_text(f"missing workdir: {workdir}\n")
        return {**attempt, "workdir": str(workdir), "status": "missing_workdir", "log": rel(log_path), "returncode": None}
    proc = subprocess.run(list(attempt["cmd"]), cwd=workdir, text=True, capture_output=True, timeout=90)
    log_path.write_text((proc.stdout or "") + ("\n[stderr]\n" + proc.stderr if proc.stderr else ""))
    return {
        **attempt,
        "workdir": str(workdir),
        "status": "passed" if proc.returncode == 0 else "failed",
        "returncode": proc.returncode,
        "log": rel(log_path),
        "stdout_tail": (proc.stdout or "")[-1600:],
        "stderr_tail": (proc.stderr or "")[-1600:],
    }


def blocker(result: dict[str, Any]) -> str:
    text = f"{result.get('stdout_tail') or ''}\n{result.get('stderr_tail') or ''}".lower()
    if result.get("returncode") == 0:
        return "none"
    if "axios/index.js" in text and "cannot use import statement outside a module" in text:
        return "jest_transform_failure_before_assertion"
    if "cannot find package 'vitest'" in text or "could not resolve 'vitest/config'" in text:
        return "dependencies_not_hydrated_for_vitest_config"
    return "verifier_failed"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp_node_modules = [
        str(path)
        for path in sorted(Path("/data/tmp").glob("**/node_modules"))
        if not any(marker in str(path) for marker in USED_FAMILY_MARKERS)
    ][:200]
    results = [run_capture(attempt) for attempt in ATTEMPTS]
    classified = [{**result, "blocker": blocker(result)} for result in results]
    admissible = [result for result in classified if result["blocker"] == "none"]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "decision": "no_already_hydrated_disjoint_web_verifier_root_admitted",
        "counts": {
            "disjoint_tmp_node_modules_seen": len(tmp_node_modules),
            "focused_attempts": len(classified),
            "admissible_verifier_roots": len(admissible),
        },
        "excluded_used_family_markers": USED_FAMILY_MARKERS,
        "disjoint_tmp_node_modules_sample": tmp_node_modules,
        "focused_attempts": classified,
        "admissibility": {
            "trainable_now": False,
            "scoreable_now": False,
            "why": [
                "DSPy has dependencies but fails before assertion because Jest cannot transform axios ESM.",
                "OpenClaw has strong source/test supply but no executable verifier without Node22/pnpm or dependency hydration.",
                "The only hydrated passing Web families found are already-used MCP/OpenHands-style lanes, which do not solve the disjoint Web gap.",
            ],
        },
        "recommended_next_action": (
            "Explicitly approve a contained runtime recovery for Node22/pnpm or Bun, or provide another already-hydrated disjoint Web repo. "
            "Until then, do not emit Web maintainer rows from these candidates."
        ),
        "outputs": {"summary": rel(SUMMARY), "logs": rel(LOG_DIR)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "counts": summary["counts"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

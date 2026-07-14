#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11360
NAME = "stage11360_web_disjoint_heldout_verifier_evidence"
OUT = ART / NAME
SUMMARY = OUT / "web_disjoint_heldout_verifier_evidence.json"
LOG_DIR = OUT / "logs"
QUEUE = ART / "stage11346_web_source_verifier_review_queue/web_source_verifier_first_wave_review_queue.jsonl"

TMP_OPENHANDS = Path("/data/tmp/stage11360_openhands_frontend")
TMP_DSPY = Path("/data/tmp/stage11360_dspy_react_app")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def run_capture(name: str, cmd: list[str], cwd: Path, timeout: int = 120) -> dict[str, Any]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{name}.log"
    if not cwd.exists():
        log_path.write_text(f"missing workdir: {cwd}\n")
        return {
            "name": name,
            "cmd": cmd,
            "cwd": str(cwd),
            "returncode": None,
            "status": "blocked_missing_workdir",
            "log": rel(log_path),
        }
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    log_path.write_text((proc.stdout or "") + ("\n[stderr]\n" + proc.stderr if proc.stderr else ""))
    return {
        "name": name,
        "cmd": cmd,
        "cwd": str(cwd),
        "returncode": proc.returncode,
        "status": "passed" if proc.returncode == 0 else "failed",
        "log": rel(log_path),
        "stdout_tail": (proc.stdout or "")[-1600:],
        "stderr_tail": (proc.stderr or "")[-1600:],
    }


def queue_item_by_repo(queue: list[dict[str, Any]], repo_family: str) -> dict[str, Any]:
    for item in queue:
        if item.get("repo_family") == repo_family:
            return item
    return {}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    queue = read_jsonl(QUEUE)

    openhands_e2e = run_capture(
        "openhands_frontend_placeholder_playwright",
        ["npm", "run", "test:e2e", "--", "tests/placeholder.spec.ts"],
        TMP_OPENHANDS,
        timeout=180,
    )
    openhands_vitest = run_capture(
        "openhands_frontend_placeholder_vitest",
        ["npm", "run", "test", "--", "tests/placeholder.spec.ts"],
        TMP_OPENHANDS,
        timeout=60,
    )
    dspy_react = run_capture(
        "dspy_react_app_app_test",
        ["npm", "test", "--", "--watchAll=false", "src/App.test.js"],
        TMP_DSPY,
        timeout=120,
    )

    by_root = {
        "openhands_frontend_placeholder": {
            "source_candidate": queue_item_by_repo(queue, "frontend"),
            "repo_family": "frontend",
            "git_repo_family": "OpenHands__OpenHands",
            "execution_status": "verifier_executed_passed_trivial"
            if openhands_e2e["returncode"] == 0
            else "verifier_execution_failed",
            "admissibility": "diagnostic_heldout_only",
            "why_not_promotable": "The only executed verifier is a placeholder Playwright test; it proves environment executability but not maintainer-grade behavior.",
            "attempts": {
                "playwright_e2e": openhands_e2e,
                "vitest_unit_route": openhands_vitest,
            },
        },
        "dspy_react_app_transform_blocker": {
            "source_candidate": queue_item_by_repo(queue, "react_app"),
            "repo_family": "react_app",
            "git_repo_family": "dspy",
            "execution_status": "verifier_executed_failed_environment_or_transform",
            "admissibility": "diagnostic_heldout_only",
            "why_not_promotable": "The test fails before the expected assertion because axios ESM is not transformed by the current Jest setup.",
            "attempts": {
                "react_app_test": dspy_react,
            },
        },
    }

    scoreable = []
    blocked = []
    for root_id, card in by_root.items():
        if card["execution_status"] == "verifier_executed_passed_trivial":
            blocked.append({"root_id": root_id, "reason": "trivial_placeholder_verifier"})
        elif card["execution_status"] == "verifier_executed_failed_environment_or_transform":
            blocked.append({"root_id": root_id, "reason": "environment_transform_failure_before_maintainer_assertion"})
        else:
            blocked.append({"root_id": root_id, "reason": "not_admitted"})

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "disjoint_web_verifier_evidence_packaged_no_promotable_rows",
        "counts": {
            "queue_items_read": len(queue),
            "candidate_roots_attempted": len(by_root),
            "scoreable_roots": len(scoreable),
            "blocked_roots": len(blocked),
        },
        "by_root": by_root,
        "scoreable_roots": scoreable,
        "blocked_roots": blocked,
        "source_artifacts": {"stage11346_review_queue": rel(QUEUE)},
        "outputs": {"summary": rel(SUMMARY), "logs": rel(LOG_DIR)},
        "recommended_next_action": "Do not train or promote from these roots. Continue source acquisition for non-trivial pure-Web verifier roots, or repair a queue item with a real selected test and maintainer assertion.",
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

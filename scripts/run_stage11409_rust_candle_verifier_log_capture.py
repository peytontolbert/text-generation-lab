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
STAGE = 11409
NAME = "stage11409_rust_candle_verifier_log_capture"
OUT = ART / NAME
SUMMARY = OUT / "rust_candle_verifier_log_capture.json"
QUEUE = ART / "stage11408_rust_verifier_grounding_materialization_audit/rust_verifier_grounding_materialization_queue.jsonl"
TIMEOUT_SECONDS = 240


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def run_command(item: dict[str, Any]) -> dict[str, Any]:
    root_id = str(item["root_id"])
    safe_root = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in root_id)
    log_path = OUT / f"{safe_root}.log"
    command = str(item["inferred_verifier_command"]).split()
    started = time.time()
    try:
        proc = subprocess.run(
            command,
            cwd=str(Path(item["crate_dir"])),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
        duration = time.time() - started
        output = proc.stdout or ""
        status = "passed" if proc.returncode == 0 else "failed"
        timeout = False
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        duration = time.time() - started
        output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        output += "\n[TIMEOUT]\n"
        status = "timeout"
        timeout = True
        returncode = None

    log_path.write_text(output)
    return {
        "root_id": root_id,
        "repo_family": item.get("repo_family"),
        "crate_dir": item.get("crate_dir"),
        "command": item.get("inferred_verifier_command"),
        "candidate_change_surface_path": item.get("candidate_change_surface_path"),
        "verifier_or_test_constraint_path": item.get("verifier_or_test_constraint_path"),
        "status": status,
        "returncode": returncode,
        "timed_out": timeout,
        "duration_seconds": round(duration, 3),
        "log_path": rel(log_path),
        "log_head": "\n".join(output.splitlines()[:40]),
        "actual_verifier_log_present": bool(output.strip()),
        "materialization_allowed_after_log": status in {"passed", "failed"} and bool(output.strip()),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    queue = [
        item
        for item in read_jsonl(QUEUE)
        if item.get("can_materialize_after_verifier_log") is True
    ]
    results = [run_command(item) for item in queue]
    passed = sum(1 for row in results if row["status"] == "passed")
    failed = sum(1 for row in results if row["status"] == "failed")
    timed_out = sum(1 for row in results if row["status"] == "timeout")
    materializable = [row for row in results if row["materialization_allowed_after_log"]]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "rust_candle_verifier_logs_captured",
        "counts": {
            "commands_attempted": len(results),
            "passed": passed,
            "failed": failed,
            "timed_out": timed_out,
            "materializable_after_log": len(materializable),
            "minimum_clean_roots_required_before_probe": 10,
        },
        "quality_gate": {
            "actual_verifier_logs_present": len(materializable) > 0,
            "enough_roots_for_probe": len(materializable) >= 10,
            "enough_repo_breadth_for_probe": len({row["repo_family"] for row in materializable}) >= 3,
            "probe_ready": False,
        },
        "results": results,
        "interpretation": (
            "These logs can support future Rust train-support materialization only as partial Candle-family supply. "
            "They are not sufficient for a Rust probe or claim because the root and repo-family thresholds remain unmet."
        ),
        "recommended_next_action": (
            "Use successful or failed verifier logs to materialize role-distinct Candle support rows, then acquire additional "
            "non-candle Rust roots with verifier logs before launching any training probe."
        ),
        "source_artifacts": {"stage11408_queue": rel(QUEUE)},
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))
    print(json.dumps(summary["quality_gate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

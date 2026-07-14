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
STAGE = 11412
NAME = "stage11412_non_candle_rust_verifier_log_capture"
OUT = ART / NAME
SUMMARY = OUT / "non_candle_rust_verifier_log_capture.json"
QUEUE = ART / "stage11411_non_candle_inline_rust_verifier_atlas/non_candle_inline_rust_verifier_queue.jsonl"
TIMEOUT_SECONDS = 180


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


def run_one(item: dict[str, Any]) -> dict[str, Any]:
    root_id = str(item["root_id"])
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in root_id)
    log_path = OUT / f"{safe}.log"
    cmd = str(item["inferred_verifier_command"]).split()
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(Path(item["crate_dir"])),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
        output = proc.stdout or ""
        status = "passed" if proc.returncode == 0 else "failed"
        returncode = proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout if isinstance(exc.stdout, str) else ""
        output += "\n[TIMEOUT]\n"
        status = "timeout"
        returncode = None
        timed_out = True
    duration = time.time() - started
    log_path.write_text(output)
    return {
        "root_id": root_id,
        "repo_family": item.get("repo_family"),
        "crate_dir": item.get("crate_dir"),
        "command": item.get("inferred_verifier_command"),
        "candidate_change_surface_path": item.get("candidate_change_surface_path"),
        "inline_test_anchor_path": item.get("inline_test_anchor_path"),
        "status": status,
        "returncode": returncode,
        "timed_out": timed_out,
        "duration_seconds": round(duration, 3),
        "log_path": rel(log_path),
        "log_head": "\n".join(output.splitlines()[:40]),
        "actual_verifier_log_present": bool(output.strip()),
        "materialization_allowed_after_log": status in {"passed", "failed"} and bool(output.strip()),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    candidates = [row for row in read_jsonl(QUEUE) if row.get("can_attempt_verifier_log_capture") is True]
    results = [run_one(row) for row in candidates]
    materializable = [row for row in results if row["materialization_allowed_after_log"]]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "non_candle_rust_verifier_logs_captured",
        "counts": {
            "commands_attempted": len(results),
            "passed": sum(1 for row in results if row["status"] == "passed"),
            "failed": sum(1 for row in results if row["status"] == "failed"),
            "timed_out": sum(1 for row in results if row["status"] == "timeout"),
            "materializable_after_log": len(materializable),
            "unique_repo_families": len({row["repo_family"] for row in materializable}),
        },
        "quality_gate": {
            "actual_verifier_logs_present": bool(materializable),
            "enough_roots_for_probe": len(materializable) >= 10,
            "enough_repo_breadth_for_probe": len({row["repo_family"] for row in materializable}) >= 3,
            "probe_ready": False,
        },
        "results": results,
        "recommended_next_action": "Materialize non-Candle verifier-log-backed support rows, then combine with Candle partial support and rerun the Rust admission gate.",
        "source_artifacts": {"stage11411_queue": rel(QUEUE)},
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))
    print(json.dumps(summary["quality_gate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

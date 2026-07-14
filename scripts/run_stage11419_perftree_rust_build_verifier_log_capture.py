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
STAGE = 11419
NAME = "stage11419_perftree_rust_build_verifier_log_capture"
OUT = ART / NAME
SUMMARY = OUT / "perftree_rust_build_verifier_log_capture.json"
TIMEOUT_SECONDS = 180

CANDIDATES = [
    {
        "root_id": "local_build_verifier_rust::data_repositories_perftree",
        "repo_family": "perftree",
        "crate_dir": "/data/repositories/perftree",
        "cargo_toml": "/data/repositories/perftree/Cargo.toml",
        "candidate_change_surface_path": "/data/repositories/perftree/perftree/src/lib.rs",
        "verifier_anchor_path": "/data/repositories/perftree/Cargo.toml",
        "inferred_verifier_command": "cargo test --manifest-path /data/repositories/perftree/Cargo.toml",
    },
    {
        "root_id": "local_build_verifier_rust::data_repositories_perftree_perftree",
        "repo_family": "perftree",
        "crate_dir": "/data/repositories/perftree/perftree",
        "cargo_toml": "/data/repositories/perftree/perftree/Cargo.toml",
        "candidate_change_surface_path": "/data/repositories/perftree/perftree/src/lib.rs",
        "verifier_anchor_path": "/data/repositories/perftree/perftree/Cargo.toml",
        "inferred_verifier_command": "cargo test --manifest-path /data/repositories/perftree/perftree/Cargo.toml",
    },
    {
        "root_id": "local_build_verifier_rust::data_repositories_perftree_perftree_cli",
        "repo_family": "perftree",
        "crate_dir": "/data/repositories/perftree/perftree-cli",
        "cargo_toml": "/data/repositories/perftree/perftree-cli/Cargo.toml",
        "candidate_change_surface_path": "/data/repositories/perftree/perftree-cli/src/bin/perftree.rs",
        "verifier_anchor_path": "/data/repositories/perftree/perftree-cli/Cargo.toml",
        "inferred_verifier_command": "cargo test --manifest-path /data/repositories/perftree/perftree-cli/Cargo.toml",
    },
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)


def run_one(item: dict[str, Any]) -> dict[str, Any]:
    root_id = str(item["root_id"])
    log_path = OUT / f"{safe_name(root_id)}.log"
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
        **item,
        "command": item["inferred_verifier_command"],
        "status": status,
        "returncode": returncode,
        "timed_out": timed_out,
        "duration_seconds": round(duration, 3),
        "log_path": rel(log_path),
        "log_head": "\n".join(output.splitlines()[:60]),
        "actual_verifier_log_present": bool(output.strip()),
        "materialization_allowed_after_log": status in {"passed", "failed"} and bool(output.strip()),
        "selected_test_anchor_present": False,
        "build_verifier_anchor_present": True,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    results = [run_one(row) for row in CANDIDATES]
    materializable = [row for row in results if row["materialization_allowed_after_log"]]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "perftree_rust_build_verifier_logs_captured",
        "counts": {
            "commands_attempted": len(results),
            "passed": sum(1 for row in results if row["status"] == "passed"),
            "failed": sum(1 for row in results if row["status"] == "failed"),
            "timed_out": sum(1 for row in results if row["status"] == "timeout"),
            "materializable_after_log": len(materializable),
            "unique_roots": len({row["root_id"] for row in materializable}),
            "unique_repo_families": len({row["repo_family"] for row in materializable}),
        },
        "quality_gate": {
            "actual_verifier_logs_present": bool(materializable),
            "selected_test_anchor_present": False,
            "build_verifier_anchor_present": bool(materializable),
            "train_rows_emitted": False,
            "probe_ready": False,
        },
        "limitations": [
            "Perftree has no selected-test source anchors; these are build-verifier support roots, not selected-test verifier-transition roots.",
            "Rows materialized from this stage must be tagged build_verifier_only and train_support_only.",
        ],
        "results": results,
        "recommended_next_action": "Materialize build-verifier-backed Perftree support rows with explicit build_verifier_only tags, then rerun the Rust support gate.",
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))
    print(json.dumps(summary["quality_gate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import time
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12291_commit_pair_after_pass_prefilter"
READY = ROOT / "runs/local/artifacts/stage12284_external_repair_commit_pair_preflight/replay_ready_targets.jsonl"
ORIGINAL = ROOT / "runs/local/artifacts/stage12244_external_repair_commit_pair_replay_request/replay_targets.jsonl"
WORK = Path("/data/tmp/stage12291_commit_pair_after_pass_prefilter")
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
TIMEOUT = 120


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def run(cmd: list[str], cwd: Path, timeout: int = TIMEOUT, env: dict[str, str] | None = None) -> dict:
    started = time.time()
    try:
        cp = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=env,
        )
        return {
            "returncode": cp.returncode,
            "timed_out": False,
            "duration_sec": round(time.time() - started, 3),
            "stdout_digest": digest(cp.stdout),
            "stderr_digest": digest(cp.stderr),
            "stdout_bytes": len(cp.stdout),
            "stderr_bytes": len(cp.stderr),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": None,
            "timed_out": True,
            "duration_sec": round(time.time() - started, 3),
            "stdout_digest": digest(exc.stdout or b""),
            "stderr_digest": digest(exc.stderr or b""),
            "stdout_bytes": len(exc.stdout or b""),
            "stderr_bytes": len(exc.stderr or b""),
        }


def status(result: dict) -> str:
    if result.get("timed_out"):
        return "TIMEOUT"
    return "PASS" if result.get("returncode") == 0 else "FAIL"


def git(repo: Path, args: list[str], timeout: int = 60) -> dict:
    return run(["git", *args], repo, timeout=timeout)


def checkout(repo: Path, revision: str) -> dict:
    git(repo, ["reset", "--hard"], timeout=60)
    git(repo, ["clean", "-fdx"], timeout=60)
    return git(repo, ["checkout", "--force", revision], timeout=60)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = ""
    env["PIP_NO_INDEX"] = "1"
    env["HF_HUB_OFFLINE"] = "1"

    rows = []
    executable_targets = {row["request_id"]: row for row in (iter_jsonl(ORIGINAL) or [])}
    ready_targets = list(iter_jsonl(READY) or [])
    for target in ready_targets:
        request_id = target["request_id"]
        executable = executable_targets.get(request_id)
        if not executable:
            rows.append(
                {
                    "request_id": request_id,
                    "repo_family": target.get("repo_family"),
                    "language_family": target.get("language_family"),
                    "after_status": "UNKNOWN_ORIGINAL_TARGET_MISSING",
                    "after_pass_prefilter_eligible": False,
                    "raw_output_emitted": False,
                }
            )
            continue
        repo_src = Path(executable["repo_path"])
        work = WORK / request_id
        if work.exists():
            shutil.rmtree(work)

        clone = run(
            ["git", "clone", "--quiet", "--no-hardlinks", "--no-checkout", str(repo_src), str(work)],
            ROOT,
            timeout=120,
            env=env,
        )
        if status(clone) != "PASS":
            rows.append(
                {
                    "request_id": request_id,
                    "repo_family": target.get("repo_family"),
                    "language_family": target.get("language_family"),
                    "after_status": "UNKNOWN_CLONE_FAILED",
                    "after_pass_prefilter_eligible": False,
                    "raw_output_emitted": False,
                }
            )
            continue

        checkout(work, executable["commit_after"])
        verifier = shlex.split(executable["verifier_command"])
        result = run(verifier, work, timeout=TIMEOUT, env=env)
        after_status = status(result)
        rows.append(
            {
                "request_id": request_id,
                "repo_family": target.get("repo_family"),
                "language_family": target.get("language_family"),
                "after_status": after_status,
                "after_result": result,
                "after_pass_prefilter_eligible": after_status == "PASS",
                "raw_output_emitted": False,
            }
        )

    eligible = [row for row in rows if row["after_pass_prefilter_eligible"]]
    blocked = [row for row in rows if not row["after_pass_prefilter_eligible"]]

    with (OUT / "after_pass_prefilter_records.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    with (OUT / "after_pass_prefilter_eligible_targets.jsonl").open("w", encoding="utf-8") as handle:
        for row in eligible:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    with (OUT / "after_pass_prefilter_blocked_targets.jsonl").open("w", encoding="utf-8") as handle:
        for row in blocked:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    summary = {
        "stage": STAGE,
        "decision": "after_pass_prefilter_complete",
        "targets_checked": len(rows),
        "eligible_for_before_and_before_plus_patch_replay": len(eligible),
        "blocked_before_patch_replay": len(blocked),
        "after_status_counts": dict(Counter(row["after_status"] for row in rows)),
        "eligible_by_language": dict(Counter(row["language_family"] for row in eligible)),
        "eligible_by_repo_family": dict(Counter(row["repo_family"] for row in eligible)),
        "blocked_by_language": dict(Counter(row["language_family"] for row in blocked)),
        "training_rows_emitted": 0,
        "admitted_rows": 0,
        "raw_output_emitted": False,
        "next_stage": "stage12292_after_pass_eligible_before_fail_patch_effect_replay",
        "interpretation": (
            "Only after-pass eligible targets may proceed to before FAIL and before+patch PASS replay. "
            "Targets failing at commit_after are not patch-effect proof candidates under this local environment."
        ),
    }
    (OUT / "after_pass_prefilter_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUT / "COMMIT_PAIR_AFTER_PASS_PREFILTER_STAGE12291.md").write_text(
        "# Stage12291 Commit Pair After-Pass Prefilter\n\n"
        + "This stage emits no training rows. It gates replay targets by exact verifier pass at commit_after.\n\n"
        + "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

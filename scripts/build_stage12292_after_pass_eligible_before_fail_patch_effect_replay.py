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
STAGE = "stage12292_after_pass_eligible_before_fail_patch_effect_replay"
ELIGIBLE = ROOT / "runs/local/artifacts/stage12291_commit_pair_after_pass_prefilter/after_pass_prefilter_eligible_targets.jsonl"
ORIGINAL = ROOT / "runs/local/artifacts/stage12244_external_repair_commit_pair_replay_request/replay_targets.jsonl"
WORK_ROOT = Path("/data/tmp/stage12292_after_pass_eligible_replay")
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
TIMEOUT = 120


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_ref(prefix: str, *parts) -> str:
    return prefix + "_" + hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:20]


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
        cp = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, env=env)
        return {
            "returncode": cp.returncode,
            "timed_out": False,
            "duration_sec": round(time.time() - started, 3),
            "stdout_digest": digest_bytes(cp.stdout),
            "stderr_digest": digest_bytes(cp.stderr),
            "stdout_bytes": len(cp.stdout),
            "stderr_bytes": len(cp.stderr),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": None,
            "timed_out": True,
            "duration_sec": round(time.time() - started, 3),
            "stdout_digest": digest_bytes(exc.stdout or b""),
            "stderr_digest": digest_bytes(exc.stderr or b""),
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


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    original = {row["request_id"]: row for row in (iter_jsonl(ORIGINAL) or [])}
    eligible = list(iter_jsonl(ELIGIBLE) or [])
    phase_records: list[dict] = []
    candidates: list[dict] = []
    rejects: list[dict] = []

    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = ""
    env["PIP_NO_INDEX"] = "1"
    env["HF_HUB_OFFLINE"] = "1"

    for safe_target in eligible:
        request_id = safe_target["request_id"]
        target = original.get(request_id)
        if not target:
            rejects.append({"request_id": request_id, "hard_reject": "original_target_missing"})
            continue

        repo_src = Path(target["repo_path"])
        work = WORK_ROOT / request_id
        if work.exists():
            shutil.rmtree(work)

        clone = run(
            ["git", "clone", "--quiet", "--no-hardlinks", "--no-checkout", str(repo_src), str(work)],
            ROOT,
            timeout=120,
            env=env,
        )
        if status(clone) != "PASS":
            rejects.append({"request_id": request_id, "hard_reject": "repo_clone_failed", "clone_result": clone})
            continue

        before = target["commit_before"]
        after = target["commit_after"]
        verifier = shlex.split(target["verifier_command"])

        checkout(work, before)
        before_result = run(verifier, work, timeout=TIMEOUT, env=env)
        before_status = status(before_result)
        phase_records.append(
            {
                "request_id": request_id,
                "phase": "before_fail_behavior",
                "status": before_status,
                "result": before_result,
                "raw_output_emitted": False,
            }
        )
        if before_status != "FAIL":
            rejects.append({"request_id": request_id, "hard_reject": "before_did_not_fail", "before_status": before_status})
            continue

        diff_cp = subprocess.run(
            ["git", "-C", str(work), "diff", "--binary", before, after],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        patch_digest = digest_bytes(diff_cp.stdout)
        if diff_cp.returncode != 0 or not diff_cp.stdout:
            rejects.append(
                {
                    "request_id": request_id,
                    "hard_reject": "diff_materialization_failed",
                    "patch_digest": patch_digest,
                    "diff_stderr_digest": digest_bytes(diff_cp.stderr),
                }
            )
            continue

        apply_cp = subprocess.run(
            ["git", "apply"],
            cwd=work,
            input=diff_cp.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        if apply_cp.returncode != 0:
            rejects.append(
                {
                    "request_id": request_id,
                    "hard_reject": "patch_apply_failed",
                    "patch_digest": patch_digest,
                    "apply_stderr_digest": digest_bytes(apply_cp.stderr),
                }
            )
            continue

        patched_result = run(verifier, work, timeout=TIMEOUT, env=env)
        patched_status = status(patched_result)
        phase_records.append(
            {
                "request_id": request_id,
                "phase": "before_plus_patch_pass",
                "status": patched_status,
                "result": patched_result,
                "raw_output_emitted": False,
            }
        )
        if patched_status != "PASS":
            rejects.append(
                {
                    "request_id": request_id,
                    "hard_reject": "before_plus_patch_did_not_pass",
                    "patched_status": patched_status,
                    "patch_digest": patch_digest,
                }
            )
            continue

        # Stage12291 already proved after PASS; rerun here only to keep the PE2 tuple self-contained.
        checkout(work, after)
        after_result = run(verifier, work, timeout=TIMEOUT, env=env)
        after_status = status(after_result)
        phase_records.append(
            {
                "request_id": request_id,
                "phase": "after_pass",
                "status": after_status,
                "result": after_result,
                "raw_output_emitted": False,
            }
        )
        if after_status != "PASS":
            rejects.append(
                {
                    "request_id": request_id,
                    "hard_reject": "after_did_not_pass_on_rerun",
                    "after_status": after_status,
                    "patch_digest": patch_digest,
                }
            )
            continue

        candidates.append(
            {
                "schema_version": "patch_effect_PE2_candidate_v2",
                "stage": STAGE,
                "request_id": request_id,
                "repo_family": target["repo_family"],
                "language_family": target["language_family"],
                "patch_digest": patch_digest,
                "verifier_command_digest": hash_ref("verifier_command", target["repo_family"], target["verifier_command"]),
                "phase_statuses": {
                    "before_fail_behavior": "FAIL",
                    "before_plus_patch_pass": "PASS",
                    "after_pass": "PASS",
                },
                "admission_level": "PE2_EXECUTED_PHASES_AFTER_PREFILTERED",
                "semantic_audit_required": True,
                "admission": {
                    "train_support_allowed": False,
                    "external_comparable_patch_trace_countable": False,
                    "external_fail_to_pass_countable": False,
                    "strict_eval_eligible": False,
                },
                "guardrails": {
                    "raw_output_emitted": False,
                    "raw_patch_body_emitted": False,
                    "raw_tool_arguments_emitted": False,
                    "raw_source_path_emitted": False,
                },
            }
        )

    write_jsonl(OUT / "phase_status_records.jsonl", phase_records)
    write_jsonl(OUT / "patch_effect_PE2_candidates.jsonl", candidates)
    write_jsonl(OUT / "replay_rejects.jsonl", rejects)

    summary = {
        "stage": STAGE,
        "decision": "after_pass_eligible_replay_complete_PE2_candidates_ready_for_semantic_audit"
        if candidates
        else "after_pass_eligible_replay_complete_zero_PE2",
        "targets_attempted": len(eligible),
        "phase_records": len(phase_records),
        "PE2_candidates": len(candidates),
        "rejects": len(rejects),
        "candidate_by_language": dict(Counter(row["language_family"] for row in candidates)),
        "candidate_by_repo": dict(Counter(row["repo_family"] for row in candidates)),
        "reject_counts": dict(Counter(row["hard_reject"] for row in rejects)),
        "training_rows_emitted": 0,
        "external_comparable_patch_trace_rows": 0,
        "external_fail_to_pass_rows": 0,
        "raw_output_emitted": False,
        "next_stage": "stage12293_PE2_semantic_patch_effect_audit",
    }
    (OUT / "after_pass_eligible_replay_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUT / "AFTER_PASS_ELIGIBLE_BEFORE_FAIL_PATCH_EFFECT_REPLAY_STAGE12292.md").write_text(
        "# Stage12292 After-Pass Eligible Patch-Effect Replay\n\n"
        + "This stage emits no training rows. PE2 candidates still require semantic audit.\n\n"
        + "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

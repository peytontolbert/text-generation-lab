#!/usr/bin/env python3
"""Run bounded local probes for Stage11970 transition-root materialization candidates.

This stage attaches observed build/test evidence to candidate roots. It does not
train and does not admit rows into a train package; emitted transition records
are review/materialization outputs only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11971
NAME = "stage11971_transition_root_250_materialization_probe_runner"
OUT = ART / NAME
SUMMARY = OUT / "transition_root_250_materialization_probe_summary.json"
RECORDS = OUT / "verified_transition_records_review_queue.jsonl"
QUEUE = ART / "stage11970_transition_root_250_materialization_plan/transition_root_250_materialization_queue.jsonl"
PLAN = ART / "stage11970_transition_root_250_materialization_plan/transition_root_250_materialization_plan.json"
TMP = Path(os.environ.get("TMPDIR") or "/data/tmp") / NAME

PRUNE = {".git", "node_modules", "target", "build", "dist", "__pycache__", ".pytest_cache", ".mypy_cache"}
LABELS = list("ABCDEFGH")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def footprint(path: Path) -> dict[str, int]:
    counts = Counter()
    for root, dirs, files in os.walk(path):
        rp = Path(root)
        if set(rp.parts) & PRUNE:
            dirs[:] = []
            continue
        depth = len(rp.relative_to(path).parts) if rp != path else 0
        if depth > 4:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in PRUNE]
        for f in files:
            counts["files"] += 1
            lf = f.lower()
            if lf.endswith(".py"):
                counts["py_files"] += 1
            if lf.endswith((".c", ".cc", ".cpp", ".h", ".hpp")):
                counts["cpp_files"] += 1
            if lf.endswith((".rs",)):
                counts["rust_files"] += 1
            if "test" in str(rp).lower() or lf.startswith("test_") or lf.endswith(("_test.py", "_test.cc", "_test.cpp", ".spec.ts", ".test.ts")):
                counts["test_files"] += 1
    return dict(counts)


def find_test_targets(path: Path, max_targets: int = 3) -> list[str]:
    candidates: list[tuple[int, str]] = []
    for root, dirs, files in os.walk(path):
        rp = Path(root)
        if set(rp.parts) & PRUNE:
            dirs[:] = []
            continue
        depth = len(rp.relative_to(path).parts) if rp != path else 0
        if depth > 4:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in PRUNE]
        for f in files:
            lf = f.lower()
            is_pytest = lf.startswith("test_") and lf.endswith(".py") or lf.endswith("_test.py")
            if not is_pytest:
                continue
            full = rp / f
            try:
                size = full.stat().st_size
                text = full.read_text(encoding="utf-8", errors="replace")[:4000]
            except OSError:
                size = 999999
                text = ""
            skip_penalty = 100000 if "skipif" in text or "pytest.mark.skip" in text else 0
            candidates.append((skip_penalty + size, str(full.relative_to(path))))
    return [value for _, value in sorted(candidates)[:max_targets]]


def run_cmd(cmd: list[str], cwd: Path, timeout: int, log_name: str) -> dict[str, Any]:
    log_dir = OUT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "CUDA_VISIBLE_DEVICES": "",
            "NVIDIA_VISIBLE_DEVICES": "",
            "PYTHONPATH": os.pathsep.join([str(cwd), str(cwd / "src"), env.get("PYTHONPATH", "")]),
            "PYTHONPYCACHEPREFIX": str(TMP / "pycache"),
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "TMPDIR": str(TMP),
            "TEMP": str(TMP),
            "TMP": str(TMP),
        }
    )
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), env=env, text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=timeout, check=False)
        timed_out = False
        rc = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        rc = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
    duration = round(time.time() - started, 3)
    log_path = log_dir / f"{log_name}.json"
    payload = {
        "command": cmd,
        "cwd": str(cwd),
        "returncode": rc,
        "timed_out": timed_out,
        "duration_sec": duration,
        "stdout_tail": stdout[-4000:],
        "stderr_tail": stderr[-4000:],
    }
    write_json(log_path, payload)
    return {**payload, "log_path": rel(log_path)}


def shuffle_options(row_id: str, values: list[str]) -> list[dict[str, str]]:
    keyed = []
    for i, value in enumerate(values):
        digest = hashlib.sha256(f"{row_id}::{i}::{value}".encode()).hexdigest()
        keyed.append((digest, value))
    return [{"label": label, "value": value} for label, (_, value) in zip(LABELS, sorted(keyed))]


def transition_for_probe(kind: str, result: dict[str, Any]) -> str:
    if result["returncode"] == 0 and not result.get("timed_out"):
        if kind == "pytest_run":
            return "PASS_TO_PASS"
        return "PASS_CURRENT_BUILD"
    combined = f"{result.get('stdout_tail') or ''}\n{result.get('stderr_tail') or ''}"
    hydration_markers = [
        "ModuleNotFoundError",
        "No module named",
        "Unknown config option",
        "unrecognized arguments",
        "could not find",
        "Could not find",
        "OpenCV",
        "not been installed",
        "No package",
    ]
    if result.get("timed_out") or any(marker in combined for marker in hydration_markers):
        return "INSUFFICIENT_EVIDENCE"
    return "NOT_EXERCISED"


def make_record(candidate: dict[str, Any], probe_kind: str, probe_target: str, result: dict[str, Any]) -> dict[str, Any]:
    transition = transition_for_probe(probe_kind, result)
    source_path = candidate["source_path"]
    root_id = f"stage11971::{candidate['repo_family_key']}::{candidate['materialization_id']}::{probe_kind}"
    record_id = f"{root_id}::{hashlib.sha1((probe_target + str(result['returncode'])).encode()).hexdigest()[:12]}"
    target_value = f"{probe_kind} | {transition} | {probe_target}"
    options = shuffle_options(
        record_id,
        [
            target_value,
            f"{probe_kind} | NOT_EXERCISED | sibling verifier not run",
            "continue_or_stop | CONTINUE | more evidence required before completion",
            "abstain | INSUFFICIENT_EVIDENCE | no observed verifier result is available",
        ],
    )
    target_label = next(opt["label"] for opt in options if opt["value"] == target_value)
    return {
        "record_id": record_id,
        "root_id": root_id,
        "root_lineage_key": root_id,
        "repo_id": candidate["repo_family_key"],
        "repo_family": candidate["repo_family_key"],
        "language_family": candidate.get("language_guess", ["unknown"])[0],
        "source_snapshot_or_commit": "local_worktree_snapshot_uncommitted_unknown",
        "source_path": source_path,
        "split_component": "review_queue_only",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "transition_record_kind": "verified_transition_record_v1_review_queue",
        "state_before": {
            "task": "materialize a fresh executable transition root from local source",
            "known_evidence": ["manifest present", "test marker present"],
            "candidate_source_path": source_path,
        },
        "candidate_actions_or_options": options,
        "selected_verifier_path": probe_target,
        "observed_verifier_transition": transition,
        "tool_or_verifier_observation": result,
        "state_after_or_state_delta": {
            "probe_kind": probe_kind,
            "returncode": result["returncode"],
            "timed_out": result.get("timed_out", False),
            "transition": transition,
        },
        "continue_stop_label": "CONTINUE" if transition != "PASS_TO_PASS" else "CONTINUE_NEEDS_ADDITIONAL_REGRESSION_CHECK",
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "target_label_not_visible_before_options": True,
            "target_value_not_visible_before_options": False,
            "target_value_visible_as_observed_verifier_result": True,
            "singleton_options": False,
            "review_queue_only": True,
            "not_merged_into_train": True,
        },
        "training_projection_targets": {
            "verifier_transition": transition,
            "continue_or_stop": "CONTINUE",
            "candidate_selection": target_label,
            "semantic_target_value": target_value,
        },
    }


def probe_candidate(candidate: dict[str, Any], index: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = Path(candidate["source_path"])
    fp = footprint(path)
    records: list[dict[str, Any]] = []
    probe_results: list[dict[str, Any]] = []
    test_targets = find_test_targets(path, max_targets=1)
    if test_targets:
        target = test_targets[0]
        collect = run_cmd(
            ["python", "-m", "pytest", "--collect-only", "-q", "-o", f"cache_dir={TMP / 'pytest_cache'}", target],
            cwd=path,
            timeout=45,
            log_name=f"{candidate['materialization_id']}_pytest_collect",
        )
        probe_results.append({"kind": "pytest_collect", "target": target, "result": collect})
        records.append(make_record(candidate, "pytest_collect", target, collect))
        if collect["returncode"] == 0 and fp.get("files", 999999) <= 150:
            run = run_cmd(
                ["python", "-m", "pytest", "-q", "-o", f"cache_dir={TMP / 'pytest_cache'}", target],
                cwd=path,
                timeout=90,
                log_name=f"{candidate['materialization_id']}_pytest_run",
            )
            probe_results.append({"kind": "pytest_run", "target": target, "result": run})
            records.append(make_record(candidate, "pytest_run", target, run))
    elif "CMakeLists.txt" in candidate.get("manifests", []) and fp.get("files", 999999) <= 150:
        build_dir = TMP / candidate["materialization_id"] / "cmake_build"
        configure = run_cmd(
            ["cmake", "-S", ".", "-B", str(build_dir), "-DCMAKE_BUILD_TYPE=Release"],
            cwd=path,
            timeout=90,
            log_name=f"{candidate['materialization_id']}_cmake_configure",
        )
        probe_results.append({"kind": "cmake_configure", "target": "CMakeLists.txt", "result": configure})
        records.append(make_record(candidate, "cmake_configure", "CMakeLists.txt", configure))
    return records, {"candidate": candidate, "footprint": fp, "probe_results": probe_results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    plan = read_json(PLAN)
    queue = read_jsonl(QUEUE)
    ranked = sorted(queue, key=lambda row: (footprint(Path(row["source_path"])).get("files", 999999), row["source_path"]))
    all_records: list[dict[str, Any]] = []
    probe_cards: list[dict[str, Any]] = []
    for idx, candidate in enumerate(ranked[: args.limit], start=1):
        records, card = probe_candidate(candidate, idx)
        all_records.extend(records)
        probe_cards.append(card)
    write_jsonl(RECORDS, all_records)
    counts = Counter(record["observed_verifier_transition"] for record in all_records)
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "materialization_probe_complete_review_queue_only",
        "source_artifacts": {
            "stage11970_plan": rel(PLAN),
            "stage11970_queue": rel(QUEUE),
        },
        "plan_decision": plan.get("decision"),
        "probe_policy": {
            "limit": args.limit,
            "ranked_by": "low file footprint first",
            "no_training": True,
            "network_install": False,
            "gpu_visible": False,
            "timeouts_sec": {"pytest_collect": 45, "pytest_run": 90, "cmake_configure": 90},
        },
        "summary": {
            "candidates_probed": len(probe_cards),
            "records_emitted_review_only": len(all_records),
            "observed_transition_counts": dict(counts),
            "pass_to_pass_records": counts.get("PASS_TO_PASS", 0),
            "pass_current_build_records": counts.get("PASS_CURRENT_BUILD", 0),
        },
        "probe_cards": probe_cards,
        "admission_decision": "do_not_train_yet",
        "admission_blockers_remaining": [
            "review queue records need root-lineage audit against protected eval roots",
            "target values are visible as observed verifier results and need row renderer review before bounded training",
            "FAIL_TO_PASS roots still require controlled mutation or real failing baseline materialization",
            "fresh Rust root deficit remains unresolved",
        ],
        "outputs": {"summary": rel(SUMMARY), "records": rel(RECORDS), "logs": rel(OUT / "logs")},
        "next_stage_recommendation": {
            "stage": "stage11972_transition_root_250_probe_admission_audit",
            "action": "Review Stage11971 records, complete anti-cheat rendering, and admit only records with clean lineage and non-leaky candidate geometry.",
        },
    }
    write_json(SUMMARY, artifact)
    print(json.dumps({"decision": artifact["decision"], "summary": artifact["summary"], "next": artifact["next_stage_recommendation"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

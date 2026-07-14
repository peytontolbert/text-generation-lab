#!/usr/bin/env python3
"""Materialize controlled FAIL_TO_PASS transition records from local roots.

This stage operates on temporary repository copies only. It verifies:
  baseline passes -> controlled source mutation fails -> restored source passes.
Rows remain review-only until a later package admission stage.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11973
NAME = "stage11973_transition_root_250_controlled_mutation_probe"
OUT = ART / NAME
SUMMARY = OUT / "transition_root_250_controlled_mutation_probe.json"
RECORDS = OUT / "controlled_fail_to_pass_transition_records_review_queue.jsonl"
TMP_ROOT = Path(os.environ.get("TMPDIR") or "/data/tmp") / NAME
LABELS = list("ABCDEFGH")

MUTATION_CANDIDATES = [
    {
        "mutation_id": "einx_invalid_backend_deferred_error",
        "repo_family": "einx",
        "language_family": "python",
        "source_root": "/data/repositories/einx",
        "test_target": "test/test_invalid_backend.py",
        "source_file": "einx/backend/register.py",
        "find": """            except Exception as e:\n                backend = InvalidBackend(\n                    module_name,\n                    f\"Failed to import backend {module_name} due to the following error:\\n{e}\",\n                )\n            register(backend)\n""",
        "replace": """            except Exception as e:\n                raise\n            register(backend)\n""",
        "mutation_rationale": "Disable deferred InvalidBackend wrapping when an already-imported backend module is invalid; the focused test expects import to survive and later raise InvalidBackendException only when jax backend is used.",
    }
]

PRUNE = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "build", "dist", "target", "node_modules"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def ignore(dirpath: str, names: list[str]) -> set[str]:
    return {name for name in names if name in PRUNE}


def copy_repo(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=ignore)


def run_pytest(cwd: Path, target: str, log_name: str) -> dict[str, Any]:
    log_dir = OUT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "CUDA_VISIBLE_DEVICES": "",
            "NVIDIA_VISIBLE_DEVICES": "",
            "PYTHONPATH": str(cwd),
            "PYTHONPYCACHEPREFIX": str(TMP_ROOT / "pycache"),
            "TMPDIR": str(TMP_ROOT),
            "TEMP": str(TMP_ROOT),
            "TMP": str(TMP_ROOT),
        }
    )
    cmd = ["python", "-m", "pytest", "-q", "-o", f"cache_dir={TMP_ROOT / 'pytest_cache'}", target]
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), env=env, text=True, capture_output=True, timeout=90, check=False)
        timed_out = False
        rc = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        rc = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
    payload = {
        "command": cmd,
        "cwd": str(cwd),
        "returncode": rc,
        "timed_out": timed_out,
        "duration_sec": round(time.time() - started, 3),
        "stdout_tail": stdout[-4000:],
        "stderr_tail": stderr[-4000:],
    }
    log_path = log_dir / f"{log_name}.json"
    write_json(log_path, payload)
    return {**payload, "log_path": rel(log_path)}


def shuffled(row_id: str, values: list[str]) -> list[dict[str, str]]:
    keyed = []
    for i, value in enumerate(values):
        keyed.append((hashlib.sha256(f"{row_id}::{i}::{value}".encode()).hexdigest(), value))
    return [{"label": label, "value": value} for label, (_, value) in zip(LABELS, sorted(keyed))]


def make_record(candidate: dict[str, Any], baseline: dict[str, Any], mutant: dict[str, Any], restored: dict[str, Any]) -> dict[str, Any]:
    root_id = f"stage11973::{candidate['repo_family']}::{candidate['mutation_id']}"
    record_id = f"{root_id}::{hashlib.sha1(candidate['mutation_rationale'].encode()).hexdigest()[:12]}"
    target_value = "controlled source mutation changed focused verifier from PASS to FAIL, and restoring the source returned it to PASS"
    options = shuffled(
        record_id,
        [
            target_value,
            "focused verifier passed under mutation, so no fail-to-pass transition was observed",
            "focused verifier failed before mutation, so the root is not a clean baseline",
            "evidence is insufficient because restore was not verified",
        ],
    )
    target_label = next(option["label"] for option in options if option["value"] == target_value)
    return {
        "record_id": record_id,
        "root_id": root_id,
        "root_lineage_key": root_id,
        "repo_id": candidate["repo_family"],
        "repo_family": candidate["repo_family"],
        "language_family": candidate["language_family"],
        "source_snapshot_or_commit": "temp_copy_from_local_worktree",
        "source_path": candidate["source_root"],
        "split_component": "review_queue_only",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "transition_record_kind": "controlled_fail_to_pass_verified_transition_record_v1_review_queue",
        "state_before": {
            "task": "verify a controlled fail-to-pass transition on a temporary repo copy",
            "source_file": candidate["source_file"],
            "selected_verifier_path": candidate["test_target"],
            "mutation_rationale": candidate["mutation_rationale"],
        },
        "candidate_actions_or_options": options,
        "selected_verifier_path": candidate["test_target"],
        "observed_verifier_transition": "FAIL_TO_PASS",
        "tool_or_verifier_observation": {
            "baseline": baseline,
            "mutant": mutant,
            "restored": restored,
        },
        "state_after_or_state_delta": {
            "baseline_returncode": baseline["returncode"],
            "mutant_returncode": mutant["returncode"],
            "restored_returncode": restored["returncode"],
            "transition": "FAIL_TO_PASS",
        },
        "continue_stop_label": "CONTINUE_NEEDS_ADDITIONAL_REGRESSION_CHECK",
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "target_label_not_visible_before_options": True,
            "target_value_not_visible_before_options": True,
            "singleton_options": False,
            "temporary_copy_only": True,
            "source_repo_not_modified": True,
            "baseline_mutant_restore_all_observed": True,
            "review_queue_only": True,
            "not_merged_into_train": True,
        },
        "training_projection_targets": {
            "verifier_transition": "FAIL_TO_PASS",
            "continue_or_stop": "CONTINUE",
            "candidate_selection": target_label,
            "semantic_target_value": target_value,
        },
    }


def run_candidate(candidate: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    src = Path(candidate["source_root"])
    work = TMP_ROOT / candidate["mutation_id"] / "repo"
    copy_repo(src, work)
    baseline = run_pytest(work, candidate["test_target"], f"{candidate['mutation_id']}_baseline")
    mutation_result: dict[str, Any] = {"applied": False}
    record = None
    mutant = {"returncode": None, "timed_out": False, "stdout_tail": "", "stderr_tail": "mutation_not_run"}
    restored = {"returncode": None, "timed_out": False, "stdout_tail": "", "stderr_tail": "restore_not_run"}
    source_file = work / candidate["source_file"]
    original = source_file.read_text(encoding="utf-8")
    if candidate["find"] in original:
        source_file.write_text(original.replace(candidate["find"], candidate["replace"], 1), encoding="utf-8")
        mutation_result = {"applied": True, "source_file": str(source_file), "mutation": candidate["mutation_rationale"]}
        mutant = run_pytest(work, candidate["test_target"], f"{candidate['mutation_id']}_mutant")
        source_file.write_text(original, encoding="utf-8")
        restored = run_pytest(work, candidate["test_target"], f"{candidate['mutation_id']}_restored")
        if baseline["returncode"] == 0 and mutant["returncode"] != 0 and restored["returncode"] == 0:
            record = make_record(candidate, baseline, mutant, restored)
    card = {
        "candidate": candidate,
        "work_copy": str(work),
        "mutation_result": mutation_result,
        "baseline": baseline,
        "mutant": mutant,
        "restored": restored,
        "admitted_record": record is not None,
    }
    return record, card


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []
    for candidate in MUTATION_CANDIDATES:
        record, card = run_candidate(candidate)
        cards.append(card)
        if record:
            records.append(record)
    write_jsonl(RECORDS, records)
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "controlled_mutation_probe_complete_review_queue_only",
        "summary": {
            "candidates": len(MUTATION_CANDIDATES),
            "admitted_fail_to_pass_records": len(records),
            "review_only": True,
        },
        "probe_cards": cards,
        "outputs": {"summary": rel(SUMMARY), "records": rel(RECORDS), "logs": rel(OUT / "logs")},
        "admission_blockers_remaining": [
            "records are controlled-mutation train-support candidates, not strict eval rows",
            "need more independent FAIL_TO_PASS roots across languages",
            "fresh Rust root supply remains unresolved",
        ],
        "next_stage_recommendation": {
            "stage": "stage11974_transition_root_250_materialization_rollup",
            "action": "Combine Stage11972 positive PASS rows with Stage11973 controlled FAIL_TO_PASS records into a review-only supply rollup and update Stage11967 deficits.",
        },
    }
    write_json(SUMMARY, artifact)
    print(json.dumps({"decision": artifact["decision"], "summary": artifact["summary"], "next": artifact["next_stage_recommendation"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

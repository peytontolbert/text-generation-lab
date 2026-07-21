#!/usr/bin/env python3
"""Wrap no-install selected-test command logs as Level-3 train-support records."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12207_no_install_selected_test_log_level3_joiner"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

spec = importlib.util.spec_from_file_location("stage12205", ROOT / "scripts/build_stage12205_authoritative_verifier_log_level3_joiner.py")
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def row_from_log(source_stage: str, rel: str, language: str, repo_family: str | None = None, selected_target: str | None = None, line_no: int = 1) -> dict[str, Any] | None:
    path = ROOT / rel
    if not path.exists():
        return None
    log = read_json(path)
    rc = log.get("exit_code", log.get("returncode"))
    if rc != 0 or log.get("timeout") is True:
        return None
    command = log.get("command_text") or log.get("command")
    stdout = log.get("stdout_tail") if "stdout_tail" in log else log.get("stdout", "")
    stderr = log.get("stderr_tail") if "stderr_tail" in log else log.get("stderr", "")
    repo = repo_family or log.get("repo_family") or log.get("candidate_id") or "unknown"
    target = selected_target or log.get("label") or log.get("command_text") or str(command)
    return mod.pass_record_common(
        source_stage=source_stage,
        source_path=path,
        line_no=line_no,
        root_id=str(log.get("cwd") or repo),
        repo_family=str(repo),
        language=language,
        command=command,
        cwd=str(log.get("cwd") or ""),
        returncode=int(rc),
        selected_target=str(target),
        stdout_tail=str(stdout or ""),
        stderr_tail=str(stderr or ""),
        verifier_transition="PASS_CURRENT_STATE",
        verifier_status="PASS_CURRENT_STATE",
        extra={
            "log_path": rel,
            "queue_id": log.get("queue_id"),
            "hydration_detected": log.get("hydration_detected"),
            "no_install_selected_test_log": True,
        },
    )


def main() -> int:
    specs = [
        ("stage12143_no_install_selected_test_expansion", "runs/local/artifacts/stage12143_no_install_selected_test_expansion/command_logs/stage12143__python__PyCQA_flake8__selected_normalize_pypi_name.json", "python", "PyCQA/flake8", "tests/unit/test_utils.py::test_normalize_pypi_name[my_plugin-my-plugin]"),
        ("stage12143_no_install_selected_test_expansion", "runs/local/artifacts/stage12143_no_install_selected_test_expansion/command_logs/stage12143__python__PyCQA_flake8__selected_inline_noqa.json", "python", "PyCQA/flake8", "tests/unit/test_violation.py::test_is_inline_ignored[E111-a = 1  # noqa: E111,W123,F821-True]"),
        ("stage12125_exact_selected_test_refinement", "runs/local/artifacts/stage12125_exact_selected_test_refinement/command_logs/stage12118__python__034__pytest_dev_pluggy__pytest_run_refined.json", "python", "pytest-dev/pluggy", "testing/test_details.py"),
        ("stage12125_exact_selected_test_refinement", "runs/local/artifacts/stage12125_exact_selected_test_refinement/command_logs/stage12118__c_cpp__002__Neargye_magic_enum__exact_selected_ctest.json", "c_cpp", "Neargye/magic_enum", "test-cpp17"),
        ("stage12125_exact_selected_test_refinement", "runs/local/artifacts/stage12125_exact_selected_test_refinement/command_logs/stage12118__c_cpp__019__fastfloat_fast_float__exact_selected_ctest.json", "c_cpp", "fastfloat/fast_float", "basictest"),
    ]
    rows = []
    blocked = []
    for i, args in enumerate(specs, 1):
        row = row_from_log(*args, line_no=i)
        if row is None:
            blocked.append({"spec": args, "blocker": "missing_or_nonzero_or_timeout"})
        else:
            rows.append(row)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT_DIR / "no_install_selected_test_level3_records.jsonl", rows)
    write_jsonl(OUT_DIR / "blocked_candidates.jsonl", blocked)
    summary = {
        "stage": STAGE,
        "decision": "no_install_selected_test_level3_records_materialized" if rows else "blocked_no_records",
        "level3_episode_count": len(rows),
        "blocked_count": len(blocked),
        "language_counts": dict(__import__('collections').Counter(r.get('language') for r in rows)),
        "verifier_transition_counts": dict(__import__('collections').Counter(r.get('verifier_transition') for r in rows)),
        "strict_eval_eligible": False,
        "train_support_only": True,
        "artifact_paths": {
            "records": str(OUT_DIR / "no_install_selected_test_level3_records.jsonl"),
            "blocked": str(OUT_DIR / "blocked_candidates.jsonl"),
        },
        "claim_boundary": "No-install selected-test logs wrapped as train-support Level-3 records only; no eval claim.",
    }
    write_json(OUT_DIR / "summary.json", summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if rows else 2


if __name__ == "__main__":
    raise SystemExit(main())

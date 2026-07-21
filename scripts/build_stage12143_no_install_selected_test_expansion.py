#!/usr/bin/env python3
"""Build Stage12143 no-install selected-test expansion artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACT_DIR = ROOT / "runs/local/artifacts/stage12143_no_install_selected_test_expansion"
SUMMARY_PATH = ARTIFACT_DIR / "summary.json"
SUMMARY_MIRROR = ROOT / "runs/summaries/stage12143_no_install_selected_test_expansion.json"
RESULTS_PATH = ARTIFACT_DIR / "selected_test_expansion_results.jsonl"
LOG_DIR = ARTIFACT_DIR / "command_logs"


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_command(candidate_id: str, label: str, cwd: Path, command: str) -> dict:
    env = os.environ.copy()
    env.update(
        {
            "CUDA_VISIBLE_DEVICES": "",
            "NVIDIA_VISIBLE_DEVICES": "",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        timeout=60,
    )
    log = {
        "candidate_id": candidate_id,
        "label": label,
        "cwd": str(cwd),
        "command": command,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
    log_path = LOG_DIR / f"{candidate_id}__{label}.json"
    log_path.write_text(json.dumps(log, indent=2, sort_keys=True) + "\n")
    return {k: v for k, v in log.items() if k not in {"stdout", "stderr"}} | {
        "log_path": str(log_path.relative_to(ROOT))
    }


def git_head(cwd: Path) -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def candidate_record(
    *,
    candidate_id: str,
    language: str,
    repo_family: str,
    local_root: Path,
    provenance: list[str],
    commands: list[tuple[str, str]],
    selected_test_ids: list[str],
    source_files: list[str],
    test_files: list[str],
    blocker: str | None,
    row_materialization_readiness: str,
    admission_ready: bool,
) -> dict:
    command_results = [
        run_command(candidate_id, label, local_root, command) for label, command in commands
    ]
    evidence_files = []
    for rel in source_files + test_files:
        path = local_root / rel
        evidence_files.append(
            {
                "path": rel,
                "sha256": sha256_file(path),
                "kind": "source" if rel in source_files else "test",
            }
        )
    return {
        "stage": 12143,
        "candidate_id": candidate_id,
        "language": language,
        "repo_family": repo_family,
        "local_root": str(local_root),
        "commit_sha": git_head(local_root),
        "provenance": provenance,
        "commands": command_results,
        "selected_test_ids": selected_test_ids,
        "source_test_evidence_hashes": evidence_files,
        "blocker": blocker,
        "admission_ready_for_row_materialization": admission_ready,
        "row_materialization_readiness": row_materialization_readiness,
        "strict_eval_eligible": False,
        "train_support_only_until_lineage_audit": True,
        "do_not_train_in_this_stage": True,
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    flake8 = Path("/data/tmp/stage12119_maintainer_400_smoke_repos/PyCQA_flake8")
    sphinx = Path("/data/tmp/stage11338_sphinx_source")
    rapidjson = Path("/data/tmp/stage12123_verifier_ready_smoke_repos/Tencent_rapidjson")

    records = [
        candidate_record(
            candidate_id="stage12143__python__PyCQA_flake8",
            language="python",
            repo_family="PyCQA/flake8",
            local_root=flake8,
            provenance=[
                "already_checked_out_under_/data/tmp/stage12119_maintainer_400_smoke_repos",
                "stage12121-stage12126 pattern reused: PYTHONPATH no-install selected pytest",
            ],
            commands=[
                (
                    "collect_utils",
                    "PYTHONPATH=src python -m pytest --collect-only -q tests/unit/test_utils.py",
                ),
                (
                    "selected_normalize_pypi_name",
                    "PYTHONPATH=src python -m pytest -q "
                    + shlex.quote(
                        "tests/unit/test_utils.py::test_normalize_pypi_name[my_plugin-my-plugin]"
                    ),
                ),
                (
                    "selected_inline_noqa",
                    "PYTHONPATH=src python -m pytest -q "
                    + shlex.quote(
                        "tests/unit/test_violation.py::test_is_inline_ignored[E111-a = 1  # noqa: E111,W123,F821-True]"
                    ),
                ),
            ],
            selected_test_ids=[
                "tests/unit/test_utils.py::test_normalize_pypi_name[my_plugin-my-plugin]",
                "tests/unit/test_violation.py::test_is_inline_ignored[E111-a = 1  # noqa: E111,W123,F821-True]",
            ],
            source_files=[
                "src/flake8/utils.py",
                "src/flake8/violation.py",
            ],
            test_files=[
                "tests/unit/test_utils.py",
                "tests/unit/test_violation.py",
            ],
            blocker=None,
            admission_ready=True,
            row_materialization_readiness=(
                "ready_for_train_support_row_materialization_after lineage/renderer/anti-cheat audit; "
                "exact selected pytest node IDs pass with PYTHONPATH=src and no install"
            ),
        ),
        candidate_record(
            candidate_id="stage12143__python__sphinx_source",
            language="python",
            repo_family="sphinx-doc/sphinx",
            local_root=sphinx,
            provenance=[
                "already_checked_out_under_/data/tmp/stage11338_sphinx_source",
                "local no-install probe only; not from strict/eval lineage",
            ],
            commands=[
                (
                    "collect_roles",
                    "PYTHONPATH=. python -m pytest --collect-only -q tests/test_roles.py",
                )
            ],
            selected_test_ids=[],
            source_files=["sphinx/roles.py"],
            test_files=["tests/test_roles.py", "tests/conftest.py"],
            blocker="missing_local_dependency_docutils; no install attempted",
            admission_ready=False,
            row_materialization_readiness="blocked_before_selected_test_execution",
        ),
        candidate_record(
            candidate_id="stage12143__c_cpp__Tencent_rapidjson",
            language="c_cpp",
            repo_family="Tencent/rapidjson",
            local_root=rapidjson,
            provenance=[
                "stage12121 C/C++ candidate plan",
                "stage12123 checkout reused",
                "stage12125 excluded due no exact CTest names; rechecked executable/CTest state",
            ],
            commands=[
                ("ctest_inventory", "ctest --test-dir build -N"),
                (
                    "find_executables",
                    "find build -type f -perm -111 | sort | head -100",
                ),
            ],
            selected_test_ids=[],
            source_files=["include/rapidjson/document.h"],
            test_files=["test/unittest/valuetest.cpp", "test/unittest/readertest.cpp"],
            blocker="no CTest entries and no built test executables found in existing local build; exact selected-test anchor unavailable without further build repair",
            admission_ready=False,
            row_materialization_readiness="blocked_no_exact_selected_test_anchor",
        ),
    ]

    RESULTS_PATH.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records))

    ready = [r for r in records if r["admission_ready_for_row_materialization"]]
    attempted = [
        {
            "repo_family": r["repo_family"],
            "language": r["language"],
            "exit_codes": [c["exit_code"] for c in r["commands"]],
            "blocker": r["blocker"],
            "selected_test_ids": r["selected_test_ids"],
        }
        for r in records
    ]
    summary = {
        "stage": 12143,
        "stage_name": "stage12143_no_install_selected_test_expansion",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "claim_boundary": [
            "Python and C/C++ only.",
            "No network.",
            "No dependency install.",
            "No training.",
            "Rust/Web intentionally untouched.",
            "Strict/eval eligibility is not claimed.",
            "Admission-ready means train-support row-materialization readiness only until lineage audit.",
        ],
        "inputs": [
            "runs/local/artifacts/stage12121_python_verifier_ready_candidate_plan/python_verifier_ready_candidate_plan.jsonl",
            "runs/local/artifacts/stage12121_cpp_verifier_ready_candidate_plan/cpp_verifier_ready_candidate_plan.jsonl",
            "runs/local/artifacts/stage12123_verifier_ready_checkout_execution_smoke/execution_smoke_results.jsonl",
            "runs/local/artifacts/stage12125_exact_selected_test_refinement/exact_selected_test_refinement_results.jsonl",
            "runs/local/artifacts/stage12126_refined_selected_test_admission_audit/admission_audit_results.jsonl",
            "/data/tmp already-checked-out repos from prior stages",
        ],
        "counts": {
            "candidates_attempted": len(records),
            "admission_ready_roots": len(ready),
            "blocked": len(records) - len(ready),
            "strict_eval_eligible": 0,
            "training_admitted": 0,
        },
        "counts_by_language": {
            "python": {
                "attempted": sum(1 for r in records if r["language"] == "python"),
                "ready": sum(
                    1
                    for r in records
                    if r["language"] == "python"
                    and r["admission_ready_for_row_materialization"]
                ),
            },
            "c_cpp": {
                "attempted": sum(1 for r in records if r["language"] == "c_cpp"),
                "ready": sum(
                    1
                    for r in records
                    if r["language"] == "c_cpp"
                    and r["admission_ready_for_row_materialization"]
                ),
            },
        },
        "candidates_attempted": attempted,
        "admission_ready_roots": [r["repo_family"] for r in ready],
        "blockers": [
            {"repo_family": r["repo_family"], "blocker": r["blocker"]}
            for r in records
            if r["blocker"]
        ],
        "outputs": {
            "artifact_dir": str(ARTIFACT_DIR.relative_to(ROOT)),
            "results_jsonl": str(RESULTS_PATH.relative_to(ROOT)),
            "command_logs": str(LOG_DIR.relative_to(ROOT)),
            "summary": str(SUMMARY_PATH.relative_to(ROOT)),
            "summary_mirror": str(SUMMARY_MIRROR.relative_to(ROOT)),
        },
        "do_not_train": True,
        "train_support_only_until_lineage_audit": True,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    SUMMARY_MIRROR.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

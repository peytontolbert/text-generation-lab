#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12358_mixed_selected_test_admissions"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
TASKS = [
    "transition_candidate_selection",
    "transition_continue_or_stop",
    "transition_evidence_citation",
    "transition_next_action",
    "transition_verifier_transition",
]
ROOT_CONFIGS = [
    {
        "root_id": "stage12358::web_js_ts_html::openhands_frontend_websocket_url",
        "repo_family": "OpenHands/OpenHands",
        "language_family": "web_js_ts_html",
        "repo": Path("/data/repositories/OpenHands__OpenHands/frontend"),
        "command": "./node_modules/.bin/vitest run __tests__/build-websocket-url.test.ts",
        "stdout": ROOT / "runs/local/artifacts/stage12356_openhands_websocket_verifier_executor/logs/openhands_websocket_stdout.log",
        "stderr": ROOT / "runs/local/artifacts/stage12356_openhands_websocket_verifier_executor/logs/openhands_websocket_stderr.log",
        "source_files": ["src/utils/websocket-url.ts", "vite.config.ts", "package.json"],
        "test_files": ["__tests__/build-websocket-url.test.ts"],
        "selected_summary": "__tests__/build-websocket-url.test.ts focused verifier; 1 test file passed; 14 tests passed.",
    },
    {
        "root_id": "stage12358::python::einops_parsing",
        "repo_family": "einops/einops",
        "language_family": "python",
        "repo": Path("/data/repositories/einops"),
        "command": "python -m pytest -q einops/tests/test_parsing.py",
        "stdout": ROOT / "runs/local/artifacts/stage12357_einops_python_verifier_executor/logs/einops_test_parsing_stdout.log",
        "stderr": ROOT / "runs/local/artifacts/stage12357_einops_python_verifier_executor/logs/einops_test_parsing_stderr.log",
        "source_files": ["einops/parsing.py", "einops/__init__.py", "pyproject.toml"],
        "test_files": ["einops/tests/test_parsing.py"],
        "selected_summary": "einops/tests/test_parsing.py focused verifier; 4 tests passed.",
    },
]
LABELS = {
    "transition_candidate_selection": ["JA4", "UP8", "LZ1"],
    "transition_continue_or_stop": ["KR3", "QD9", "NV5"],
    "transition_evidence_citation": ["WQ6", "LE2", "PM7"],
    "transition_next_action": ["HN1", "UC8", "TY4"],
    "transition_verifier_transition": ["ZS9", "GB3", "FK6"],
}
ROTATIONS = {
    "transition_candidate_selection": [1, 0, 2],
    "transition_continue_or_stop": [0, 2, 1],
    "transition_evidence_citation": [2, 1, 0],
    "transition_next_action": [1, 0, 2],
    "transition_verifier_transition": [2, 0, 1],
}
EXCLUDED_PATH_PARTS = {"node_modules", ".venv", "venv", "target", "dist", "build", "__pycache__"}


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_output(repo: Path, args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def has_excluded_part(path: str) -> bool:
    return any(part in EXCLUDED_PATH_PARTS for part in Path(path).parts)


def hash_refs(repo: Path, paths: list[str], full: bool = False) -> tuple[list[str], list[str]]:
    refs = []
    blockers = []
    for rel in paths:
        if has_excluded_part(rel):
            blockers.append(f"excluded_path_configured::{rel}")
            continue
        path = repo / rel
        if not path.exists():
            blockers.append(f"missing_configured_file::{rel}")
            continue
        digest = sha_file(path)
        refs.append(f"{rel}@{digest if full else digest[:12]}")
    return refs, blockers


def parse_pass_counts(output: str) -> dict[str, int | None]:
    file_match = re.search(r"Test Files\s+(\d+)\s+passed", output)
    suite_match = re.search(r"Test Suites:\s+(\d+)\s+passed", output)
    vitest_tests = re.search(r"Tests\s+(\d+)\s+passed", output)
    pytest_tests = re.search(r"(\d+)\s+passed", output)
    return {
        "test_files_passed": int(file_match.group(1)) if file_match else None,
        "test_suites_passed": int(suite_match.group(1)) if suite_match else None,
        "tests_passed": int((vitest_tests or pytest_tests).group(1)) if (vitest_tests or pytest_tests) else None,
    }


def make_options(task: str, root_index: int) -> tuple[list[dict[str, Any]], str]:
    values = [
        "same_repo_unselected_surface_candidate [candidate_1; adjacent but not focused-verifier-backed]",
        "selected_test_backed_verifier_candidate [candidate_0; focused test and source hash refs align]",
        "abstain_or_insufficient_evidence_control [candidate_2; conservative control option]",
    ]
    rotation = ROTATIONS[task][root_index % 3 :] + ROTATIONS[task][: root_index % 3]
    options = []
    target = ""
    for pos, value_index in enumerate(rotation):
        semantic_id = ["candidate_1", "candidate_0", "candidate_2"][value_index]
        label = LABELS[task][pos]
        options.append({"deterministic_position": pos, "label": label, "semantic_id": semantic_id, "value": values[value_index]})
        if semantic_id == "candidate_0":
            target = label
    return options, target


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    admitted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    root_summaries = []
    for root_index, cfg in enumerate(ROOT_CONFIGS):
        stdout = cfg["stdout"].read_text(encoding="utf-8", errors="replace") if cfg["stdout"].exists() else ""
        stderr = cfg["stderr"].read_text(encoding="utf-8", errors="replace") if cfg["stderr"].exists() else ""
        counts = parse_pass_counts(f"{stdout}\n{stderr}")
        focused_passed = bool(counts.get("tests_passed") and (counts.get("test_files_passed") or counts.get("test_suites_passed") or cfg["language_family"] == "python") and not stderr.strip())
        source_refs, source_blockers = hash_refs(cfg["repo"], cfg["source_files"])
        test_refs, test_blockers = hash_refs(cfg["repo"], cfg["test_files"], full=True)
        blockers = []
        if not focused_passed:
            blockers.append("focused_verifier_pass_missing")
        if not git_output(cfg["repo"], ["rev-parse", "HEAD"]):
            blockers.append("commit_sha_missing")
        if not source_refs:
            blockers.append("source_hash_refs_missing")
        if not test_refs:
            blockers.append("test_hash_refs_missing")
        blockers.extend(source_blockers)
        blockers.extend(test_blockers)
        exec_summary = {
            "root_id": cfg["root_id"],
            "repo_family": cfg["repo_family"],
            "language_family": cfg["language_family"],
            "commit_sha": git_output(cfg["repo"], ["rev-parse", "HEAD"]),
            "git_status_short_sha256": sha_text(git_output(cfg["repo"], ["status", "--short"])),
            "focused_verifier_command": cfg["command"],
            "focused_verifier_cwd": str(cfg["repo"]),
            "focused_verifier_passed": focused_passed,
            "verifier_result_summary": counts,
            "stdout_sha256": sha_text(stdout) if stdout else None,
            "stderr_sha256": sha_text(stderr) if stderr else None,
            "source_hash_refs": source_refs,
            "test_hash_refs": test_refs,
            "blocked_reasons": blockers,
        }
        root_summaries.append(exec_summary)
        evidence_refs = [
            f"{STAGE}::{cfg['root_id']}::focused_verifier_pass",
        ]
        if exec_summary["stdout_sha256"]:
            evidence_refs.append(f"stdout_sha256::{exec_summary['stdout_sha256']}")
        if exec_summary["stderr_sha256"]:
            evidence_refs.append(f"stderr_sha256::{exec_summary['stderr_sha256']}")
        evidence_refs.extend([f"source_hash::{ref}" for ref in source_refs[:5]])
        evidence_refs.extend([f"test_hash::{ref}" for ref in test_refs[:2]])
        for task in TASKS:
            options, target_label = make_options(task, root_index)
            input_text = (
                f"Task family: {task.replace('transition_', '')}\n"
                f"Repository: {cfg['repo_family']}\n"
                f"Language: {cfg['language_family']}\n"
                f"Commit: {exec_summary['commit_sha']}\n"
                f"Selected-test evidence: {cfg['selected_summary']}\n"
                f"Verifier command class: focused local verifier; exit_code=0; command_ref={sha_text(cfg['command'])[:16]}\n"
                f"Source hash summary: {', '.join(source_refs[:5])}\n"
                f"Test hash summary: {', '.join(test_refs[:2])}\n"
                f"Evidence ledger refs: {json.dumps(evidence_refs[:10], sort_keys=True)}\n"
                "Choose the single option whose internally-audited evidence role is best supported by the compact verifier/source/test record. "
                "Use only the opaque labels below; do not infer from label names.\n"
                "Options:\n" + "\n".join(f"- {opt['label']}: Option {opt['label']}" for opt in options) + "\nAnswer:"
            )
            row = {
                "stage": STAGE,
                "record_type": "selected_test_train_support_row",
                "row_id": f"{STAGE}::{cfg['root_id']}::{task}",
                "root_id": cfg["root_id"],
                "repo_family": cfg["repo_family"],
                "language_family": cfg["language_family"],
                "task_family": task,
                "input_text": input_text,
                "opaque_options": options,
                "bounded_choice_target_label": target_label,
                "decoder_text": target_label,
                "loss_mask": {"decoder_ce": True, "bounded_choice_aux": True, "structured_aux": True, "transition_projection": True},
                "source_refs": {
                    "commit_sha": exec_summary["commit_sha"],
                    "root_lineage_key": f"{STAGE}::{cfg['repo_family'].replace('/', '__')}::{cfg['root_id']}",
                    "source_root_id": cfg["root_id"],
                    "selected_test_command_ref": f"command_sha256::{sha_text(cfg['command'])}",
                    "raw_source_emitted": False,
                    "raw_verifier_log_emitted": False,
                    "dependency_paths_excluded": True,
                },
                "admission": {
                    "training_allowed": not blockers,
                    "train_support_allowed": not blockers,
                    "strict_eval_eligible": False,
                    "source_heldout_admissible": False,
                    "level3_admitted": False,
                    "patch_trace_admitted": False,
                    "repair_claim_admitted": False,
                    "reason": "selected-test train-support only; no strict/source-heldout/Level-3/patch/repair claim",
                },
                "blocked_reasons": list(blockers),
            }
            (admitted if not blockers else blocked).append(row)
    with (OUT / "mixed_selected_test_train_support_rows.jsonl").open("w", encoding="utf-8") as handle:
        for row in admitted:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    with (OUT / "mixed_selected_test_blocked_rows.jsonl").open("w", encoding="utf-8") as handle:
        for row in blocked:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "decision": "mixed_selected_test_admissions_complete" if admitted else "mixed_selected_test_admissions_blocked",
        "training_allowed": bool(admitted),
        "claim_boundary": "Train-support-only selected-test rows. No strict eval, source-heldout, Level-3, patch-trace, or repair claim.",
        "admitted_train_support_rows": len(admitted),
        "blocked_rows": len(blocked),
        "root_count": len(root_summaries),
        "root_summaries": root_summaries,
        "repo_counts": dict(Counter(row["repo_family"] for row in admitted)),
        "language_counts": dict(Counter(row["language_family"] for row in admitted)),
        "task_family_counts": dict(Counter(row["task_family"] for row in admitted)),
        "blocked_reason_counts": dict(Counter(reason for row in blocked for reason in row.get("blocked_reasons", []))),
    }
    (OUT / "mixed_selected_test_admissions_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

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
STAGE = "stage12351_web_fallback_selected_test_admissions"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
TASKS = [
    "transition_candidate_selection",
    "transition_continue_or_stop",
    "transition_evidence_citation",
    "transition_next_action",
    "transition_verifier_transition",
]
ROOTS = [
    {
        "root_id": "stage12351::web_js_ts_html::mcp_typescript_sdk_server",
        "repo_family": "modelcontextprotocol/typescript-sdk",
        "repo": Path("/data/repositories/modelcontextprotocol__typescript-sdk/packages/server"),
        "command": "./node_modules/.bin/vitest run test/server/server.test.ts",
        "stdout": ROOT / "runs/local/artifacts/stage12345_mcp_ts_server_verifier_executor/logs/mcp_ts_server_test_stdout.log",
        "stderr": ROOT / "runs/local/artifacts/stage12345_mcp_ts_server_verifier_executor/logs/mcp_ts_server_test_stderr.log",
        "source_files": ["src/server/server.ts", "vitest.config.js", "package.json"],
        "test_files": ["test/server/server.test.ts"],
        "selected_summary": "test/server/server.test.ts focused verifier; 1 test file passed; 1 test passed.",
    },
    {
        "root_id": "stage12351::web_js_ts_html::mcp_sep_automation_transition",
        "repo_family": "modelcontextprotocol/sep-automation",
        "repo": Path("/data/repositories/modelcontextprotocol__modelcontextprotocol/tools/sep-automation"),
        "command": "./node_modules/.bin/vitest run test/unit/transition.test.ts",
        "stdout": ROOT / "runs/local/artifacts/stage12347_sep_automation_verifier_executor/logs/sep_transition_test_stdout.log",
        "stderr": ROOT / "runs/local/artifacts/stage12347_sep_automation_verifier_executor/logs/sep_transition_test_stderr.log",
        "source_files": ["src/actions/transition.ts", "src/config.ts", "test/mocks.ts", "package-lock.json"],
        "test_files": ["test/unit/transition.test.ts"],
        "selected_summary": "test/unit/transition.test.ts focused verifier; 1 test file passed; 6 tests passed.",
    },
    {
        "root_id": "stage12351::web_js_ts_html::llama_stack_ui_format_message",
        "repo_family": "llama-stack/llama-stack-ui",
        "repo": Path("/data/repositories/llama-stack/src/llama_stack_ui"),
        "command": "./node_modules/.bin/jest lib/format-message-content.test.ts",
        "stdout": ROOT / "runs/local/artifacts/stage12349_llama_stack_ui_verifier_executor/logs/llama_format_message_stdout.log",
        "stderr": ROOT / "runs/local/artifacts/stage12349_llama_stack_ui_verifier_executor/logs/llama_format_message_stderr.log",
        "source_files": ["lib/format-message-content.ts", "lib/types.ts", "package-lock.json"],
        "test_files": ["lib/format-message-content.test.ts"],
        "selected_summary": "lib/format-message-content.test.ts focused verifier; 1 test suite passed; 17 tests passed.",
    },
]
LABELS = {
    "transition_candidate_selection": ["AA4", "PU8", "ZW1"],
    "transition_continue_or_stop": ["RA3", "DD9", "VV5"],
    "transition_evidence_citation": ["QE6", "EF2", "MM7"],
    "transition_next_action": ["NN1", "CC8", "YY4"],
    "transition_verifier_transition": ["SS9", "BB3", "KK6"],
}
ROTATIONS = {
    "transition_candidate_selection": [1, 0, 2],
    "transition_continue_or_stop": [0, 2, 1],
    "transition_evidence_citation": [2, 1, 0],
    "transition_next_action": [1, 0, 2],
    "transition_verifier_transition": [2, 0, 1],
}


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_output(repo: Path, args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def count_passes(combined: str) -> dict[str, int | None]:
    file_match = re.search(r"Test Files\s+(\d+)\s+passed", combined)
    tests_match = re.search(r"Tests\s+(\d+)\s+passed", combined)
    suite_match = re.search(r"Test Suites:\s+(\d+)\s+passed", combined)
    jest_tests_match = re.search(r"Tests:\s+(\d+)\s+passed", combined)
    return {
        "test_files_passed": int(file_match.group(1)) if file_match else None,
        "test_suites_passed": int(suite_match.group(1)) if suite_match else None,
        "tests_passed": int((tests_match or jest_tests_match).group(1)) if (tests_match or jest_tests_match) else None,
    }


def refs(repo: Path, paths: list[str], full: bool = False) -> list[str]:
    out = []
    for rel in paths:
        path = repo / rel
        if path.exists() and "node_modules" not in rel:
            digest = sha_file(path)
            out.append(f"{rel}@{digest if full else digest[:12]}")
    return out


def make_options(task: str, root_index: int) -> tuple[list[dict[str, Any]], str]:
    values = [
        "same_repo_unselected_web_surface_candidate [candidate_1; adjacent but not focused-verifier-backed]",
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
    executor_summaries = []
    rows = []
    blocked_rows = []
    for root_index, cfg in enumerate(ROOTS):
        stdout = cfg["stdout"].read_text(encoding="utf-8", errors="replace") if cfg["stdout"].exists() else ""
        stderr = cfg["stderr"].read_text(encoding="utf-8", errors="replace") if cfg["stderr"].exists() else ""
        combined = f"{stdout}\n{stderr}"
        counts = count_passes(combined)
        passed = bool((counts.get("test_files_passed") or counts.get("test_suites_passed")) and counts.get("tests_passed"))
        source_refs = refs(cfg["repo"], cfg["source_files"])
        test_refs = refs(cfg["repo"], cfg["test_files"], full=True)
        blockers = []
        if not passed:
            blockers.append("focused_verifier_pass_missing")
        if not source_refs:
            blockers.append("source_hash_refs_missing")
        if not test_refs:
            blockers.append("test_hash_refs_missing")
        if any("node_modules" in ref for ref in source_refs + test_refs):
            blockers.append("dependency_path_leaked_in_hash_refs")
        exec_summary = {
            "root_id": cfg["root_id"],
            "repo_family": cfg["repo_family"],
            "language_family": "web_js_ts_html",
            "commit_sha": git_output(cfg["repo"], ["rev-parse", "HEAD"]),
            "git_status_short_sha256": sha_text(git_output(cfg["repo"], ["status", "--short"])),
            "focused_verifier_command": cfg["command"],
            "focused_verifier_cwd": str(cfg["repo"]),
            "focused_verifier_passed": passed,
            "verifier_result_summary": counts,
            "stdout_sha256": sha_text(stdout) if stdout else None,
            "stderr_sha256": sha_text(stderr) if stderr else None,
            "source_hash_refs": source_refs,
            "test_hash_refs": test_refs,
            "blocked_reasons_before_row_admission": blockers + [
                "needs_task_specific_gold_rendering",
                "needs_anti_cheat_renderer",
            ],
        }
        executor_summaries.append(exec_summary)
        evidence_refs = [
            f"{STAGE}::{cfg['root_id']}::focused_verifier_pass",
            f"stdout_sha256::{exec_summary['stdout_sha256']}",
            f"stderr_sha256::{exec_summary['stderr_sha256']}",
        ] + [f"source_hash::{ref}" for ref in source_refs[:5]] + [f"test_hash::{ref}" for ref in test_refs[:2]]
        for task in TASKS:
            options, target_label = make_options(task, root_index)
            input_text = (
                f"Task family: {task.replace('transition_', '')}\n"
                f"Repository: {cfg['repo_family']}\nLanguage: web_js_ts_html\nCommit: {exec_summary['commit_sha']}\n"
                f"Selected-test evidence: {cfg['selected_summary']}\n"
                f"Verifier command class: focused local JS/TS verifier; exit_code=0; command={cfg['command']}\n"
                f"Source hash summary: {', '.join(source_refs[:5])}\n"
                f"Test hash summary: {', '.join(test_refs[:2])}\n"
                f"Evidence ledger refs: {json.dumps(evidence_refs[:10], sort_keys=True)}\n"
                "Choose the single option whose internally-audited evidence role is best supported by the compact verifier/source/test record. "
                "Use only the opaque labels below; do not infer from label names.\n"
                "Options:\n" + "\n".join(f"- {opt['label']}: Option {opt['label']}" for opt in options) + "\nAnswer:"
            )
            row = {
                "stage": STAGE,
                "record_type": "web_selected_test_train_support_row",
                "row_id": f"{STAGE}::{cfg['root_id']}::{task}",
                "root_id": cfg["root_id"],
                "repo_family": cfg["repo_family"],
                "language_family": "web_js_ts_html",
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
                    "selected_test_command_ref": f"{STAGE}::{cfg['root_id']}::command_hash_only",
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
                    "reason": "web selected-test train-support only; no strict/source-heldout/Level-3/patch/repair claim",
                },
                "blocked_reasons": list(blockers),
            }
            (rows if not blockers else blocked_rows).append(row)
    write_path = OUT / "web_fallback_selected_test_train_support_rows.jsonl"
    blocked_path = OUT / "web_fallback_selected_test_blocked_rows.jsonl"
    with write_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    with blocked_path.open("w", encoding="utf-8") as handle:
        for row in blocked_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "decision": "web_fallback_selected_test_admissions_complete" if rows else "web_fallback_selected_test_admissions_blocked",
        "training_allowed": bool(rows),
        "claim_boundary": "Train-support-only web selected-test rows. No strict eval, source-heldout, Level-3, patch-trace, or repair claim.",
        "admitted_train_support_rows": len(rows),
        "blocked_rows": len(blocked_rows),
        "root_count": len(executor_summaries),
        "executor_summaries": executor_summaries,
        "repo_counts": dict(Counter(row["repo_family"] for row in rows)),
        "task_family_counts": dict(Counter(row["task_family"] for row in rows)),
        "blocked_reason_counts": dict(Counter(reason for row in blocked_rows for reason in row.get("blocked_reasons", []))),
    }
    (OUT / "web_fallback_selected_test_admissions_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

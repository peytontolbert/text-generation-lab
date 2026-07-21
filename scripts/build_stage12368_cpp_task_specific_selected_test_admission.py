#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12368_cpp_task_specific_selected_test_admission"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
LOG_DIR = ROOT / "runs/local/artifacts/stage12367_cpp_selected_test_verifier_executor/logs"
TASKS = [
    "transition_candidate_selection",
    "transition_next_action",
    "transition_continue_or_stop",
    "transition_verifier_transition",
    "transition_evidence_citation",
]
ROOTS = [
    {
        "root_id": "stage12368::c_cpp::magic_enum_cpp17",
        "repo_family": "Neargye/magic_enum",
        "repo": Path("/data/tmp/stage12123_verifier_ready_smoke_repos/Neargye_magic_enum"),
        "language_family": "c_cpp",
        "command": "ctest --test-dir build --output-on-failure -R ^test-cpp17$",
        "stdout": LOG_DIR / "magic_enum_stdout.log",
        "stderr": LOG_DIR / "magic_enum_stderr.log",
        "source_files": ["include/magic_enum/magic_enum.hpp", "include/magic_enum/magic_enum_flags.hpp", "CMakeLists.txt"],
        "test_files": ["test/test.cpp", "test/test_helpers.hpp", "test/CMakeLists.txt"],
        "selected_test_id": "test-cpp17",
        "domain": "enum reflection C++ focused test",
    },
    {
        "root_id": "stage12368::c_cpp::fast_float_basictest",
        "repo_family": "fastfloat/fast_float",
        "repo": Path("/data/tmp/stage12123_verifier_ready_smoke_repos/fastfloat_fast_float"),
        "language_family": "c_cpp",
        "command": "ctest --test-dir build --output-on-failure -R ^basictest$",
        "stdout": LOG_DIR / "fast_float_stdout.log",
        "stderr": LOG_DIR / "fast_float_stderr.log",
        "source_files": ["include/fast_float/fast_float.h", "include/fast_float/parse_number.h", "CMakeLists.txt"],
        "test_files": ["tests/basictest.cpp", "tests/CMakeLists.txt"],
        "selected_test_id": "basictest",
        "domain": "floating-point parser focused test",
    },
]


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_output(repo: Path, args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def rel_refs(repo: Path, rels: list[str], full: bool = False) -> list[str]:
    refs: list[str] = []
    for rel in rels:
        path = repo / rel
        if path.exists() and not any(part in {"node_modules", "vendor", "third_party"} for part in path.parts):
            digest = sha_file(path)
            refs.append(f"{rel}@{digest if full else digest[:12]}")
    return refs


def pass_observed(stdout: str) -> bool:
    return "100% tests passed" in stdout and re.search(r"0 tests failed out of 1", stdout) is not None


def task_options(task: str, root: dict) -> tuple[list[dict], str]:
    selected = root["selected_test_id"]
    if task == "transition_candidate_selection":
        specs = [
            ("candidate_implementation_surface", "implementation/source surface only; no selected-test result"),
            ("candidate_selected_test_backed", f"candidate supported by selected focused verifier {selected}"),
            ("candidate_insufficient_evidence", "abstain/control because verifier evidence is absent"),
        ]
        target = "candidate_selected_test_backed"
    elif task == "transition_next_action":
        specs = [
            ("action_patch_now", "patch immediately before validating selected verifier"),
            ("action_run_selected_verifier", f"run the focused verifier {selected} before claiming support"),
            ("action_finish_without_verifier", "finish without selected verifier evidence"),
        ]
        target = "action_run_selected_verifier"
    elif task == "transition_continue_or_stop":
        specs = [
            ("policy_continue_missing_selected_test", "continue because selected verifier has not been observed"),
            ("policy_stop_selected_verifier_passed", "stop/support is allowed after selected verifier pass is observed"),
            ("policy_stop_on_source_surface_only", "stop using source surface alone"),
        ]
        target = "policy_stop_selected_verifier_passed"
    elif task == "transition_verifier_transition":
        specs = [
            ("status_not_exercised", "the verifier did not exercise the selected test"),
            ("status_pass_current_state", "the selected verifier passed on the current state"),
            ("status_env_blocked", "the verifier was blocked by environment/dependency setup"),
        ]
        target = "status_pass_current_state"
    elif task == "transition_evidence_citation":
        specs = [
            ("evidence_source_hash_only", "source hash reference without command result"),
            ("evidence_selected_verifier_log", "focused verifier log showing one selected test passed"),
            ("evidence_dependency_or_vendor", "dependency/vendor evidence not admissible"),
        ]
        target = "evidence_selected_verifier_log"
    else:
        raise ValueError(task)
    labels = ["K7P", "M2Q", "R9T"] if root["repo_family"].startswith("Neargye") else ["B4L", "Q8N", "X3V"]
    rotation = {
        "transition_candidate_selection": [1, 0, 2],
        "transition_next_action": [2, 1, 0],
        "transition_continue_or_stop": [0, 2, 1],
        "transition_verifier_transition": [2, 0, 1],
        "transition_evidence_citation": [1, 2, 0],
    }[task]
    options: list[dict] = []
    target_label = ""
    for pos, index in enumerate(rotation):
        semantic_id, value = specs[index]
        label = f"{labels[pos]}{pos}"
        options.append({"deterministic_position": pos, "label": label, "semantic_id": semantic_id, "value": value})
        if semantic_id == target:
            target_label = label
    return options, target_label


def make_input(root: dict, task: str, options: list[dict], source_refs: list[str], test_refs: list[str], evidence_refs: list[str]) -> str:
    task_prompt = {
        "transition_candidate_selection": "Select the candidate whose support is grounded by the focused selected-test record.",
        "transition_next_action": "Choose the next maintainer action before making a support claim.",
        "transition_continue_or_stop": "Decide whether the current compact state justifies stopping or requires more action.",
        "transition_verifier_transition": "Classify what the focused verifier observation proves about the current state.",
        "transition_evidence_citation": "Choose the decisive evidence class for the selected-test support claim.",
    }[task]
    return (
        f"Task family: {task.replace('transition_', '')}\n"
        f"Repository: {root['repo_family']}\n"
        f"Language: {root['language_family']}\n"
        f"Commit: {git_output(root['repo'], ['rev-parse', 'HEAD'])}\n"
        f"Domain: {root['domain']}\n"
        f"Selected verifier id: {root['selected_test_id']}\n"
        "Verifier observation summary: one focused CTest test passed; zero failed; output is referenced by hash only.\n"
        f"Command ref: command_sha256::{sha_text(root['command'])[:16]}\n"
        f"Source hash summary: {', '.join(source_refs)}\n"
        f"Test hash summary: {', '.join(test_refs)}\n"
        f"Evidence refs: {json.dumps(evidence_refs[:10], sort_keys=True)}\n"
        f"Question: {task_prompt}\n"
        "Options:\n"
        + "\n".join(f"- {opt['label']}: Option {opt['label']}" for opt in options)
        + "\nAnswer:"
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    admitted: list[dict] = []
    blocked: list[dict] = []
    for root in ROOTS:
        stdout = root["stdout"].read_text(encoding="utf-8", errors="replace") if root["stdout"].exists() else ""
        stderr = root["stderr"].read_text(encoding="utf-8", errors="replace") if root["stderr"].exists() else ""
        source_refs = rel_refs(root["repo"], root["source_files"])
        test_refs = rel_refs(root["repo"], root["test_files"], full=True)
        blockers: list[str] = []
        if not pass_observed(stdout):
            blockers.append("focused_ctest_pass_not_observed")
        if not git_output(root["repo"], ["rev-parse", "HEAD"]):
            blockers.append("commit_sha_missing")
        if len(source_refs) < 2:
            blockers.append("source_hash_refs_insufficient")
        if not test_refs:
            blockers.append("test_hash_refs_missing")
        evidence_refs = [
            f"stdout_sha256::{sha_text(stdout)}" if stdout else "",
            f"stderr_sha256::{sha_text(stderr)}" if stderr else "",
            f"command_sha256::{sha_text(root['command'])}",
        ] + [f"source_hash::{ref}" for ref in source_refs] + [f"test_hash::{ref}" for ref in test_refs]
        evidence_refs = [ref for ref in evidence_refs if ref]
        target_semantics_by_task: dict[str, str] = {}
        rows_for_root: list[dict] = []
        for task in TASKS:
            options, target_label = task_options(task, root)
            target_semantic = next(option["semantic_id"] for option in options if option["label"] == target_label)
            target_semantics_by_task[task] = target_semantic
            row = {
                "stage": STAGE,
                "record_type": "task_specific_selected_test_train_support_row",
                "row_id": f"{STAGE}::{root['root_id']}::{task}",
                "root_id": root["root_id"],
                "repo_family": root["repo_family"],
                "language_family": root["language_family"],
                "task_family": task,
                "input_text": make_input(root, task, options, source_refs, test_refs, evidence_refs),
                "opaque_options": options,
                "bounded_choice_target_label": target_label,
                "decoder_text": target_label,
                "target_semantic_id": target_semantic,
                "loss_mask": {"decoder_ce": True, "bounded_choice_aux": True, "structured_aux": True, "transition_projection": True},
                "source_refs": {
                    "commit_sha": git_output(root["repo"], ["rev-parse", "HEAD"]),
                    "root_lineage_key": f"{STAGE}::{root['repo_family'].replace('/', '__')}::{root['root_id']}",
                    "source_root_id": root["root_id"],
                    "selected_test_id": root["selected_test_id"],
                    "selected_test_command_ref": f"command_sha256::{sha_text(root['command'])}",
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
                    "reason": "Task-specific C/C++ selected-test train-support only; no strict/source-heldout/Level-3/patch/repair claim.",
                },
                "blocked_reasons": list(blockers),
            }
            rows_for_root.append(row)
        if len(set(target_semantics_by_task.values())) != len(TASKS):
            for row in rows_for_root:
                row["blocked_reasons"] = sorted(set(row.get("blocked_reasons", []) + ["target_semantics_not_task_distinct"]))
                row["admission"]["training_allowed"] = False
                row["admission"]["train_support_allowed"] = False
        (admitted if not any(row["blocked_reasons"] for row in rows_for_root) else blocked).extend(rows_for_root)
    with (OUT / "cpp_task_specific_selected_test_train_support_rows.jsonl").open("w", encoding="utf-8") as handle:
        for row in admitted:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    with (OUT / "cpp_task_specific_selected_test_blocked_rows.jsonl").open("w", encoding="utf-8") as handle:
        for row in blocked:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "decision": "cpp_task_specific_selected_test_admission_complete" if admitted else "cpp_task_specific_selected_test_admission_blocked",
        "training_allowed": bool(admitted),
        "claim_boundary": "Train-support-only C/C++ task-specific selected-test rows. No strict/source-heldout/Level-3/patch/repair claim.",
        "admitted_train_support_rows": len(admitted),
        "blocked_rows": len(blocked),
        "repo_families": sorted(set(row["repo_family"] for row in admitted)),
        "language_family_counts": dict(Counter(row["language_family"] for row in admitted)),
        "task_family_counts": dict(Counter(row["task_family"] for row in admitted)),
        "target_semantic_counts": dict(Counter(row["target_semantic_id"] for row in admitted)),
        "blocked_reason_counts": dict(Counter(reason for row in blocked for reason in row.get("blocked_reasons", []))),
    }
    (OUT / "cpp_task_specific_selected_test_admission_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

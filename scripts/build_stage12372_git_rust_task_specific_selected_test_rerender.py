#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12372_git_rust_task_specific_selected_test_rerender"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
REPO = Path("/data/repositories/git")
STDOUT = ROOT / "runs/local/artifacts/stage12361_git_rust_varint_verifier_executor/logs/git_varint_stdout.log"
STDERR = ROOT / "runs/local/artifacts/stage12361_git_rust_varint_verifier_executor/logs/git_varint_stderr.log"
ROOT_ID = "stage12362::rust::gitcore_varint_decode"
REPO_FAMILY = "git/gitcore-rust"
LANG = "rust"
COMMAND = "cargo test varint::tests::test_decode_varint -- --exact"
TASKS = [
    "transition_candidate_selection",
    "transition_next_action",
    "transition_continue_or_stop",
    "transition_verifier_transition",
    "transition_evidence_citation",
]


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_output(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(REPO), *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def rel_refs(rels: list[str], full: bool = False) -> list[str]:
    refs: list[str] = []
    for rel in rels:
        path = REPO / rel
        if path.exists():
            digest = sha_file(path)
            refs.append(f"{rel}@{digest if full else digest[:12]}")
    return refs


def pass_observed(stdout: str) -> bool:
    return bool(re.search(r"test result:\s+ok\.\s+1 passed;\s+0 failed", stdout))


def task_options(task: str) -> tuple[list[dict], str]:
    specs_by_task = {
        "transition_candidate_selection": [
            ("candidate_rust_source_surface", "Rust varint source surface without selected test result"),
            ("candidate_selected_test_backed", "varint focused test and source/test hash refs align"),
            ("candidate_insufficient_evidence", "abstain because verifier proof is missing"),
        ],
        "transition_next_action": [
            ("action_patch_now", "patch varint before checking the focused unit test"),
            ("action_run_selected_verifier", "run varint::tests::test_decode_varint as the next evidence-producing action"),
            ("action_finish_without_verifier", "finish without selected-test evidence"),
        ],
        "transition_continue_or_stop": [
            ("policy_continue_missing_selected_test", "continue because no selected-test result has been observed"),
            ("policy_stop_selected_verifier_passed", "stop/support is justified after the selected Rust unit test passed"),
            ("policy_stop_on_source_surface_only", "stop using source surface alone"),
        ],
        "transition_verifier_transition": [
            ("status_not_exercised", "the command did not execute the selected unit test"),
            ("status_pass_current_state", "the selected Rust verifier passed in the current state"),
            ("status_env_blocked", "the Rust verifier was blocked by environment/dependency setup"),
        ],
        "transition_evidence_citation": [
            ("evidence_source_hash_only", "source hash reference without verifier outcome"),
            ("evidence_selected_verifier_log", "focused cargo test log showing one selected unit test passed"),
            ("evidence_unselected_neighbor", "nearby Rust artifact not selected by the verifier"),
        ],
    }
    targets = {
        "transition_candidate_selection": "candidate_selected_test_backed",
        "transition_next_action": "action_run_selected_verifier",
        "transition_continue_or_stop": "policy_stop_selected_verifier_passed",
        "transition_verifier_transition": "status_pass_current_state",
        "transition_evidence_citation": "evidence_selected_verifier_log",
    }
    rotations = {
        "transition_candidate_selection": [1, 0, 2],
        "transition_next_action": [2, 1, 0],
        "transition_continue_or_stop": [0, 2, 1],
        "transition_verifier_transition": [2, 0, 1],
        "transition_evidence_citation": [1, 2, 0],
    }
    labels = ["G4R", "N8K", "V2M"]
    specs = specs_by_task[task]
    options: list[dict] = []
    target_label = ""
    for pos, index in enumerate(rotations[task]):
        semantic_id, value = specs[index]
        label = f"{labels[pos]}{pos}"
        options.append({"deterministic_position": pos, "label": label, "semantic_id": semantic_id, "value": value})
        if semantic_id == targets[task]:
            target_label = label
    return options, target_label


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stdout = STDOUT.read_text(encoding="utf-8", errors="replace") if STDOUT.exists() else ""
    stderr = STDERR.read_text(encoding="utf-8", errors="replace") if STDERR.exists() else ""
    source_refs = rel_refs(["src/varint.rs", "src/lib.rs", "Cargo.toml"])
    test_refs = rel_refs(["src/varint.rs"], full=True)
    blockers: list[str] = []
    if not pass_observed(stdout):
        blockers.append("focused_verifier_pass_missing")
    if not git_output(["rev-parse", "HEAD"]):
        blockers.append("commit_sha_missing")
    if not source_refs:
        blockers.append("source_hash_refs_missing")
    if not test_refs:
        blockers.append("test_hash_refs_missing")
    evidence_refs = [
        f"stdout_sha256::{sha_text(stdout)}" if stdout else "",
        f"stderr_sha256::{sha_text(stderr)}" if stderr else "",
        f"command_sha256::{sha_text(COMMAND)}",
    ] + [f"source_hash::{ref}" for ref in source_refs] + [f"test_hash::{ref}" for ref in test_refs]
    evidence_refs = [ref for ref in evidence_refs if ref]
    rows: list[dict] = []
    blocked: list[dict] = []
    target_semantics: set[str] = set()
    for task in TASKS:
        options, target_label = task_options(task)
        target_semantic = next(opt["semantic_id"] for opt in options if opt["label"] == target_label)
        target_semantics.add(target_semantic)
        input_text = (
            f"Task family: {task.replace('transition_', '')}\n"
            f"Repository: {REPO_FAMILY}\n"
            f"Language: {LANG}\n"
            f"Commit: {git_output(['rev-parse', 'HEAD'])}\n"
            "Selected verifier id: varint::tests::test_decode_varint\n"
            "Verifier observation summary: one focused cargo unit test passed; zero failed; output is referenced by hash only.\n"
            f"Command ref: command_sha256::{sha_text(COMMAND)[:16]}\n"
            f"Source hash summary: {', '.join(source_refs)}\n"
            f"Test hash summary: {', '.join(test_refs)}\n"
            f"Evidence refs: {json.dumps(evidence_refs[:10], sort_keys=True)}\n"
            "Choose the task-specific option. Labels are opaque.\n"
            "Options:\n" + "\n".join(f"- {opt['label']}: Option {opt['label']}" for opt in options) + "\nAnswer:"
        )
        row = {
            "stage": STAGE,
            "record_type": "task_specific_selected_test_train_support_row",
            "row_id": f"{STAGE}::{ROOT_ID}::{task}",
            "root_id": ROOT_ID,
            "supersedes_row_prefix": f"stage12362_git_rust_selected_test_admission::{ROOT_ID}",
            "repo_family": REPO_FAMILY,
            "language_family": LANG,
            "task_family": task,
            "input_text": input_text,
            "opaque_options": options,
            "bounded_choice_target_label": target_label,
            "decoder_text": target_label,
            "target_semantic_id": target_semantic,
            "loss_mask": {"decoder_ce": True, "bounded_choice_aux": True, "structured_aux": True, "transition_projection": True},
            "source_refs": {
                "commit_sha": git_output(["rev-parse", "HEAD"]),
                "root_lineage_key": f"{STAGE}::{REPO_FAMILY.replace('/', '__')}::{ROOT_ID}",
                "source_root_id": ROOT_ID,
                "selected_test_id": "varint::tests::test_decode_varint",
                "selected_test_command_ref": f"command_sha256::{sha_text(COMMAND)}",
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
                "reason": "Task-specific Rust selected-test train-support only; no strict/source-heldout/Level-3/patch/repair claim.",
            },
            "blocked_reasons": list(blockers),
        }
        (rows if not blockers else blocked).append(row)
    if len(target_semantics) != len(TASKS):
        for row in rows:
            row["blocked_reasons"] = ["target_semantics_not_task_distinct"]
            row["admission"]["training_allowed"] = False
            row["admission"]["train_support_allowed"] = False
        blocked.extend(rows)
        rows = []
    with (OUT / "git_rust_task_specific_selected_test_rows.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    with (OUT / "git_rust_task_specific_selected_test_blocked_rows.jsonl").open("w", encoding="utf-8") as handle:
        for row in blocked:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "decision": "git_rust_task_specific_selected_test_rerender_complete" if rows else "git_rust_task_specific_selected_test_rerender_blocked",
        "training_allowed": bool(rows),
        "claim_boundary": "Train-support-only Rust task-specific selected-test re-render. Supersedes collapsed Stage12362 projections for this root.",
        "admitted_train_support_rows": len(rows),
        "blocked_rows": len(blocked),
        "repo_family": REPO_FAMILY,
        "language_family_counts": dict(Counter(row["language_family"] for row in rows)),
        "task_family_counts": dict(Counter(row["task_family"] for row in rows)),
        "target_semantic_counts": dict(Counter(row["target_semantic_id"] for row in rows)),
        "blocked_reason_counts": dict(Counter(reason for row in blocked for reason in row.get("blocked_reasons", []))),
    }
    (OUT / "git_rust_task_specific_selected_test_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

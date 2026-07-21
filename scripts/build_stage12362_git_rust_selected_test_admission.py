#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12362_git_rust_selected_test_admission"
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
    "transition_continue_or_stop",
    "transition_evidence_citation",
    "transition_next_action",
    "transition_verifier_transition",
]
LABELS = {
    "transition_candidate_selection": ["RJA4", "RUP8", "RLZ1"],
    "transition_continue_or_stop": ["RKR3", "RQD9", "RNV5"],
    "transition_evidence_citation": ["RWQ6", "RLE2", "RPM7"],
    "transition_next_action": ["RHN1", "RUC8", "RTY4"],
    "transition_verifier_transition": ["RZS9", "RGB3", "RFK6"],
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


def git_output(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(REPO), *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def parse_pass(output: str) -> bool:
    return bool(re.search(r"test result:\s+ok\.\s+1 passed;\s+0 failed", output))


def refs(paths: list[str], full: bool = False) -> list[str]:
    out = []
    for rel in paths:
        path = REPO / rel
        if path.exists():
            digest = sha_file(path)
            out.append(f"{rel}@{digest if full else digest[:12]}")
    return out


def make_options(task: str) -> tuple[list[dict], str]:
    values = [
        "same_repo_unselected_rust_surface_candidate [candidate_1; adjacent Rust source but not focused-verifier-backed]",
        "selected_test_backed_verifier_candidate [candidate_0; varint focused test and source hash refs align]",
        "abstain_or_insufficient_evidence_control [candidate_2; conservative control option]",
    ]
    options = []
    target = ""
    for pos, value_index in enumerate(ROTATIONS[task]):
        semantic_id = ["candidate_1", "candidate_0", "candidate_2"][value_index]
        label = LABELS[task][pos]
        options.append({"deterministic_position": pos, "label": label, "semantic_id": semantic_id, "value": values[value_index]})
        if semantic_id == "candidate_0":
            target = label
    return options, target


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stdout = STDOUT.read_text(encoding="utf-8", errors="replace") if STDOUT.exists() else ""
    stderr = STDERR.read_text(encoding="utf-8", errors="replace") if STDERR.exists() else ""
    focused_passed = parse_pass(stdout)
    source_refs = refs(["src/varint.rs", "src/lib.rs", "Cargo.toml"])
    test_refs = refs(["src/varint.rs"], full=True)
    blockers = []
    if not focused_passed:
        blockers.append("focused_verifier_pass_missing")
    if not git_output(["rev-parse", "HEAD"]):
        blockers.append("commit_sha_missing")
    if not source_refs:
        blockers.append("source_hash_refs_missing")
    if not test_refs:
        blockers.append("test_hash_refs_missing")
    evidence_refs = [
        f"{STAGE}::focused_verifier_pass",
        f"stdout_sha256::{sha_text(stdout)}" if stdout else "",
        f"stderr_sha256::{sha_text(stderr)}" if stderr else "",
    ] + [f"source_hash::{ref}" for ref in source_refs] + [f"test_hash::{ref}" for ref in test_refs]
    evidence_refs = [ref for ref in evidence_refs if ref]
    rows = []
    blocked_rows = []
    for task in TASKS:
        options, target_label = make_options(task)
        input_text = (
            f"Task family: {task.replace('transition_', '')}\n"
            f"Repository: {REPO_FAMILY}\n"
            f"Language: {LANG}\n"
            f"Commit: {git_output(['rev-parse', 'HEAD'])}\n"
            "Selected-test evidence: Rust unit test varint::tests::test_decode_varint; 1 test passed; exact filter used.\n"
            f"Verifier command class: focused cargo unit test; exit_code=0; command_ref={sha_text(COMMAND)[:16]}\n"
            f"Source hash summary: {', '.join(source_refs)}\n"
            f"Test hash summary: {', '.join(test_refs)}\n"
            f"Evidence ledger refs: {json.dumps(evidence_refs[:10], sort_keys=True)}\n"
            "Choose the single option whose internally-audited evidence role is best supported by the compact verifier/source/test record. "
            "Use only the opaque labels below; do not infer from label names.\n"
            "Options:\n" + "\n".join(f"- {opt['label']}: Option {opt['label']}" for opt in options) + "\nAnswer:"
        )
        row = {
            "stage": STAGE,
            "record_type": "selected_test_train_support_row",
            "row_id": f"{STAGE}::{ROOT_ID}::{task}",
            "root_id": ROOT_ID,
            "repo_family": REPO_FAMILY,
            "language_family": LANG,
            "task_family": task,
            "input_text": input_text,
            "opaque_options": options,
            "bounded_choice_target_label": target_label,
            "decoder_text": target_label,
            "loss_mask": {"decoder_ce": True, "bounded_choice_aux": True, "structured_aux": True, "transition_projection": True},
            "source_refs": {
                "commit_sha": git_output(["rev-parse", "HEAD"]),
                "root_lineage_key": f"{STAGE}::{REPO_FAMILY.replace('/', '__')}::{ROOT_ID}",
                "source_root_id": ROOT_ID,
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
                "reason": "Rust selected-test train-support only; no strict/source-heldout/Level-3/patch/repair claim",
            },
            "blocked_reasons": list(blockers),
        }
        (rows if not blockers else blocked_rows).append(row)
    with (OUT / "git_rust_selected_test_train_support_rows.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    with (OUT / "git_rust_selected_test_blocked_rows.jsonl").open("w", encoding="utf-8") as handle:
        for row in blocked_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "decision": "git_rust_selected_test_admission_complete" if rows else "git_rust_selected_test_admission_blocked",
        "training_allowed": bool(rows),
        "claim_boundary": "Train-support-only Rust selected-test rows. No strict eval, source-heldout, Level-3, patch-trace, or repair claim.",
        "admitted_train_support_rows": len(rows),
        "blocked_rows": len(blocked_rows),
        "repo_family": REPO_FAMILY,
        "language_family": LANG,
        "source_hash_ref_count": len(source_refs),
        "test_hash_ref_count": len(test_refs),
        "task_family_counts": dict(Counter(row["task_family"] for row in rows)),
        "blocked_reason_counts": dict(Counter(reason for row in blocked_rows for reason in row.get("blocked_reasons", []))),
    }
    (OUT / "git_rust_selected_test_admission_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

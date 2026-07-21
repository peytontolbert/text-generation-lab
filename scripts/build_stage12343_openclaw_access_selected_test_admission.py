#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12343_openclaw_access_selected_test_admission"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SOURCE = ROOT / "runs/summaries/stage12342_openclaw_access_verifier_executor.json"
ROOT_ID = "stage12343::web_js_ts_html::openclaw_clawhub::convex_access"
REPO = "openclaw/clawhub"
LANG = "web_js_ts_html"
TASKS = [
    "transition_candidate_selection",
    "transition_continue_or_stop",
    "transition_evidence_citation",
    "transition_next_action",
    "transition_verifier_transition",
]
LABELS = {
    "transition_candidate_selection": ["G4", "U8", "Z1"],
    "transition_continue_or_stop": ["A2", "J7", "T9"],
    "transition_evidence_citation": ["F5", "H3", "R8"],
    "transition_next_action": ["C6", "P1", "X4"],
    "transition_verifier_transition": ["D8", "K2", "Y6"],
}
ROTATIONS = {
    "transition_candidate_selection": [1, 2, 0],
    "transition_continue_or_stop": [2, 0, 1],
    "transition_evidence_citation": [0, 1, 2],
    "transition_next_action": [1, 0, 2],
    "transition_verifier_transition": [2, 1, 0],
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def make_options(task: str) -> tuple[list[dict[str, Any]], str]:
    values = [
        "same_repo_unselected_web_surface_candidate [candidate_1; access-adjacent but not focused-verifier-backed]",
        "selected_test_backed_verifier_candidate [candidate_0; access-focused test and source hash refs align]",
        "abstain_or_insufficient_evidence_control [candidate_2; conservative control option]",
    ]
    rows = []
    target = ""
    for pos, value_index in enumerate(ROTATIONS[task]):
        semantic_id = ["candidate_1", "candidate_0", "candidate_2"][value_index]
        label = LABELS[task][pos]
        rows.append({"deterministic_position": pos, "label": label, "semantic_id": semantic_id, "value": values[value_index]})
        if semantic_id == "candidate_0":
            target = label
    return rows, target


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source = read_json(SOURCE)
    blockers = []
    if not source.get("focused_verifier_passed"):
        blockers.append("focused_verifier_pass_missing")
    if not source.get("commit_sha"):
        blockers.append("commit_sha_missing")
    source_refs = source.get("source_hash_refs") or []
    test_refs = source.get("test_hash_refs") or []
    if not source_refs:
        blockers.append("source_hash_refs_missing")
    if not test_refs:
        blockers.append("test_hash_refs_missing")
    if any("node_modules" in ref for ref in source_refs + test_refs):
        blockers.append("dependency_path_leaked_in_hash_refs")
    rows, blocked = [], []
    evidence_refs = [
        "stage12342_openclaw_access_verifier_executor::focused_verifier_pass",
        f"stdout_sha256::{source.get('stdout_sha256')}",
        f"stderr_sha256::{source.get('stderr_sha256')}",
    ] + [f"source_hash::{ref}" for ref in source_refs[:5]] + [f"test_hash::{ref}" for ref in test_refs[:2]]
    for task in TASKS:
        options, target_label = make_options(task)
        input_text = (
            f"Task family: {task.replace('transition_', '')}\n"
            f"Repository: {REPO}\nLanguage: {LANG}\nCommit: {source.get('commit_sha')}\n"
            "Selected-test evidence: convex/lib/access.test.ts focused verifier; 1 test file passed; 10 tests passed.\n"
            f"Verifier command class: local vitest focused file; exit_code=0; command={source.get('focused_verifier_command')}\n"
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
            "row_id": f"{STAGE}::{ROOT_ID}::{task}",
            "root_id": ROOT_ID,
            "repo_family": REPO,
            "language_family": LANG,
            "task_family": task,
            "input_text": input_text,
            "opaque_options": options,
            "bounded_choice_target_label": target_label,
            "decoder_text": target_label,
            "loss_mask": {"decoder_ce": True, "bounded_choice_aux": True, "structured_aux": True, "transition_projection": True},
            "source_refs": {
                "commit_sha": source.get("commit_sha"),
                "root_lineage_key": f"{STAGE}::{REPO.replace('/', '__')}::{ROOT_ID}",
                "source_root_id": ROOT_ID,
                "selected_test_command_ref": "stage12342_openclaw_access_verifier_executor::command_hash_only",
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
        (rows if not blockers else blocked).append(row)
    write_jsonl(OUT / "openclaw_access_selected_test_train_support_rows.jsonl", rows)
    write_jsonl(OUT / "openclaw_access_selected_test_blocked_rows.jsonl", blocked)
    summary = {
        "stage": STAGE,
        "decision": "openclaw_access_selected_test_admission_complete" if rows else "openclaw_access_selected_test_admission_blocked",
        "training_allowed": bool(rows),
        "claim_boundary": "Train-support-only web selected-test rows. No strict eval, source-heldout, Level-3, patch-trace, or repair claim.",
        "admitted_train_support_rows": len(rows),
        "blocked_rows": len(blocked),
        "repo_family": REPO,
        "language_family": LANG,
        "task_family_counts": dict(Counter(row.get("task_family") for row in rows)),
        "blocked_reason_counts": dict(Counter(reason for row in blocked for reason in row.get("blocked_reasons", []))),
    }
    (OUT / "openclaw_access_selected_test_admission_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

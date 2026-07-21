#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12374_python_task_specific_selected_test_rerender"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12326_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12326_direct_python_selected_test_admission"
    / "direct_python_selected_test_train_support_rows.jsonl"
)

TASKS = [
    "transition_candidate_selection",
    "transition_next_action",
    "transition_continue_or_stop",
    "transition_verifier_transition",
    "transition_evidence_citation",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def stable_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def field_from_input(input_text: str, prefix: str) -> str:
    for line in input_text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def evidence_refs_from_input(input_text: str) -> list[str]:
    line = field_from_input(input_text, "Evidence ledger refs:")
    if not line:
        return []
    try:
        refs = json.loads(line)
        return [ref for ref in refs if isinstance(ref, str)]
    except json.JSONDecodeError:
        return [line]


def compact_source_refs(row: dict[str, Any]) -> dict[str, Any]:
    source_refs = row.get("source_refs") or {}
    return {
        "commit_sha": source_refs.get("commit_sha") or field_from_input(row.get("input_text") or "", "Commit:"),
        "root_lineage_key": source_refs.get("root_lineage_key"),
        "source_root_id": source_refs.get("source_root_id"),
        "source_bundle_id": source_refs.get("source_bundle_id"),
        "source_stage": row.get("source_stage"),
        "source_row_id": row.get("source_row_id"),
        "supersedes_row_id": row.get("row_id"),
        "raw_source_emitted": False,
        "raw_verifier_log_emitted": False,
        "dependency_paths_excluded": True,
    }


def task_specs(task: str, selected_summary: str) -> tuple[list[tuple[str, str]], str, str]:
    if task == "transition_candidate_selection":
        return (
            [
                ("candidate_selected_test_backed", "candidate is supported by the compact selected-test evidence"),
                ("candidate_source_surface_only", "candidate relies on Python source hashes without selected-test support"),
                ("candidate_insufficient_evidence", "candidate must abstain because selected-test evidence is unavailable"),
            ],
            "candidate_selected_test_backed",
            "Select the candidate whose support is grounded by the selected-test record.",
        )
    if task == "transition_next_action":
        return (
            [
                ("action_run_selected_verifier", "run or rely on the selected Python verifier before claiming support"),
                ("action_patch_now", "patch before checking the selected verifier evidence"),
                ("action_finish_without_verifier", "finish without selected-test evidence"),
            ],
            "action_run_selected_verifier",
            "Choose the next task action before making a support claim.",
        )
    if task == "transition_continue_or_stop":
        return (
            [
                ("policy_stop_selected_verifier_passed", f"stop/support is justified after selected-test evidence is present: {selected_summary}"),
                ("policy_continue_missing_selected_test", "continue because selected-test evidence has not been observed"),
                ("policy_stop_on_source_surface_only", "stop using source hashes alone"),
            ],
            "policy_stop_selected_verifier_passed",
            "Decide whether the compact state justifies stopping or needs more evidence.",
        )
    if task == "transition_verifier_transition":
        return (
            [
                ("status_pass_current_state", "selected Python verifier evidence supports the current state"),
                ("status_not_exercised", "the selected verifier was not exercised"),
                ("status_env_blocked", "the selected verifier was blocked by environment setup"),
            ],
            "status_pass_current_state",
            "Classify what the selected-verifier observation proves about the current state.",
        )
    if task == "transition_evidence_citation":
        return (
            [
                ("evidence_selected_verifier_log", "compact selected-verifier ledger refs and test hashes are decisive"),
                ("evidence_source_hash_only", "source hash references alone are decisive"),
                ("evidence_unselected_neighbor", "nearby unselected Python artifacts are decisive"),
            ],
            "evidence_selected_verifier_log",
            "Choose the decisive evidence class for the selected-test support claim.",
        )
    raise ValueError(task)


def task_options(task: str, root_id: str, selected_summary: str) -> tuple[list[dict[str, Any]], str]:
    specs, target, _ = task_specs(task, selected_summary)
    rotations = {
        "transition_candidate_selection": [0, 1, 2],
        "transition_next_action": [2, 0, 1],
        "transition_continue_or_stop": [1, 2, 0],
        "transition_verifier_transition": [2, 1, 0],
        "transition_evidence_citation": [0, 2, 1],
    }
    labels = ["P6A", "H3N", "R8K", "V5Q", "L2M", "C9T"]
    offset = int(stable_digest(f"{root_id}::{task}")[:2], 16) % len(labels)
    options: list[dict[str, Any]] = []
    target_label = ""
    for pos, index in enumerate(rotations[task]):
        semantic_id, value = specs[index]
        label = f"{labels[(offset + pos) % len(labels)]}{pos}"
        options.append(
            {
                "deterministic_position": pos,
                "label": label,
                "semantic_id": semantic_id,
                "value": value,
            }
        )
        if semantic_id == target:
            target_label = label
    return options, target_label


def make_input(row: dict[str, Any], task: str, options: list[dict[str, Any]], evidence_refs: list[str]) -> str:
    input_text = row.get("input_text") or ""
    repo = row.get("repo_family") or field_from_input(input_text, "Repository:")
    language = row.get("language_family") or field_from_input(input_text, "Language:")
    commit = field_from_input(input_text, "Commit:")
    selected_summary = field_from_input(input_text, "Selected-test evidence:")
    source_summary = field_from_input(input_text, "Source hash summary:")
    _, _, question = task_specs(task, selected_summary)
    return (
        f"Task family: {task.replace('transition_', '')}\n"
        f"Repository: {repo}\n"
        f"Language: {language}\n"
        f"Commit: {commit}\n"
        f"Root id: {row.get('root_id')}\n"
        f"Selected-test evidence summary: {selected_summary}\n"
        f"Source hash summary: {source_summary}\n"
        f"Evidence refs: {json.dumps(evidence_refs[:10], sort_keys=True)}\n"
        f"Question: {question}\n"
        "Choose the task-specific option. Labels are opaque.\n"
        "Options:\n"
        + "\n".join(f"- {opt['label']}: Option {opt['label']}" for opt in options)
        + "\nAnswer:"
    )


def blockers_for_source(row: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    admission = row.get("admission") or {}
    if admission.get("train_support_allowed") is not True or admission.get("training_allowed") is not True:
        blockers.append("stage12326_source_not_train_support_allowed")
    if row.get("language_family") != "python":
        blockers.append("source_row_not_python")
    if row.get("task_family") not in TASKS:
        blockers.append("unsupported_task_family")
    if not row.get("root_id"):
        blockers.append("root_id_missing")
    if not row.get("repo_family"):
        blockers.append("repo_family_missing")
    input_text = row.get("input_text") or ""
    if "source_hash" not in input_text and "Source hash summary:" not in input_text:
        blockers.append("source_hash_summary_missing")
    if "test_hash" not in input_text and "Selected-test evidence:" not in input_text:
        blockers.append("selected_test_summary_missing")
    if admission.get("strict_eval_eligible") is True or admission.get("source_heldout_admissible") is True:
        blockers.append("unexpected_eval_claim")
    return blockers


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    admitted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    source_rows = read_jsonl(STAGE12326_ROWS)

    rows_by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        rows_by_root[row.get("root_id") or ""].append(row)

    for source_row in source_rows:
        task = source_row.get("task_family")
        input_text = source_row.get("input_text") or ""
        selected_summary = field_from_input(input_text, "Selected-test evidence:")
        options, target_label = task_options(task, source_row.get("root_id") or "", selected_summary)
        target_semantic = next(option["semantic_id"] for option in options if option["label"] == target_label)
        evidence_refs = evidence_refs_from_input(input_text)
        row_blockers = blockers_for_source(source_row)
        root_tasks = {row.get("task_family") for row in rows_by_root.get(source_row.get("root_id") or "", [])}
        if not set(TASKS).issubset(root_tasks):
            row_blockers.append("root_missing_full_task_set")
        rendered = {
            "stage": STAGE,
            "record_type": "task_specific_selected_test_train_support_row",
            "row_id": f"{STAGE}::{source_row.get('root_id')}::{task}",
            "root_id": source_row.get("root_id"),
            "supersedes_row_id": source_row.get("row_id"),
            "supersedes_row_prefix": f"stage12326::{source_row.get('source_stage')}::{source_row.get('root_id')}",
            "source_stage": "stage12326_direct_python_selected_test_admission",
            "repo_family": source_row.get("repo_family"),
            "language_family": "python",
            "task_family": task,
            "input_text": make_input(source_row, task, options, evidence_refs),
            "opaque_options": options,
            "bounded_choice_target_label": target_label,
            "decoder_text": target_label,
            "target_semantic_id": target_semantic,
            "loss_mask": {
                "decoder_ce": True,
                "bounded_choice_aux": True,
                "structured_aux": True,
                "transition_projection": True,
            },
            "source_refs": compact_source_refs(source_row),
            "admission": {
                "training_allowed": not row_blockers,
                "train_support_allowed": not row_blockers,
                "strict_eval_eligible": False,
                "source_heldout_admissible": False,
                "level3_admitted": False,
                "patch_trace_admitted": False,
                "repair_claim_admitted": False,
                "reason": "Task-specific Python selected-test train-support only; no strict/source-heldout/Level-3/patch/repair claim.",
            },
            "blocked_reasons": sorted(set(row_blockers)),
        }
        (admitted if not row_blockers else blocked).append(rendered)

    root_target_sets: dict[str, set[str]] = defaultdict(set)
    for row in admitted:
        root_target_sets[row["root_id"]].add(row["target_semantic_id"])
    collapsed_roots = [root for root, targets in root_target_sets.items() if len(targets) != len(TASKS)]
    if collapsed_roots:
        still_admitted: list[dict[str, Any]] = []
        for row in admitted:
            if row["root_id"] in collapsed_roots:
                row["blocked_reasons"] = ["target_semantics_not_task_distinct"]
                row["admission"]["training_allowed"] = False
                row["admission"]["train_support_allowed"] = False
                blocked.append(row)
            else:
                still_admitted.append(row)
        admitted = still_admitted

    write_jsonl(OUT / "python_task_specific_selected_test_rows.jsonl", admitted)
    write_jsonl(OUT / "python_task_specific_selected_test_blocked_rows.jsonl", blocked)
    summary = {
        "stage": STAGE,
        "decision": "python_task_specific_selected_test_rerender_complete" if admitted else "python_task_specific_selected_test_rerender_blocked",
        "training_allowed": bool(admitted),
        "claim_boundary": "Train-support-only Python task-specific selected-test re-render. Supersedes collapsed Stage12326 roots where source rows are complete.",
        "source_stage": "stage12326_direct_python_selected_test_admission",
        "source_rows_seen": len(source_rows),
        "admitted_train_support_rows": len(admitted),
        "blocked_rows": len(blocked),
        "superseded_stage12326_rows": len({row["supersedes_row_id"] for row in admitted}),
        "superseded_roots": sorted({row["root_id"] for row in admitted}),
        "repo_families": sorted({row["repo_family"] for row in admitted}),
        "language_family_counts": dict(Counter(row["language_family"] for row in admitted)),
        "root_counts": dict(Counter(row["root_id"] for row in admitted)),
        "task_family_counts": dict(Counter(row["task_family"] for row in admitted)),
        "target_semantic_counts": dict(Counter(row["target_semantic_id"] for row in admitted)),
        "blocked_reason_counts": dict(Counter(reason for row in blocked for reason in row.get("blocked_reasons", []))),
        "raw_source_or_verifier_output_emitted": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "level3_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
    }
    (OUT / "python_task_specific_selected_test_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12380_openclaw_task_specific_selected_test_rerender"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SOURCES = [
    ROOT / "runs/local/artifacts/stage12339_openclaw_web_selected_test_admission/openclaw_web_selected_test_train_support_rows.jsonl",
    ROOT / "runs/local/artifacts/stage12343_openclaw_access_selected_test_admission/openclaw_access_selected_test_train_support_rows.jsonl",
]
TASKS = [
    "transition_candidate_selection",
    "transition_next_action",
    "transition_continue_or_stop",
    "transition_verifier_transition",
    "transition_evidence_citation",
]
RISKY_FIELDS = ["strict_eval_eligible", "source_heldout_admissible", "level3_admitted", "patch_trace_admitted", "repair_claim_admitted"]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def field(input_text: str, prefix: str) -> str:
    for line in input_text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def safe_refs(input_text: str) -> list[str]:
    raw = field(input_text, "Evidence ledger refs:")
    if not raw:
        return []
    try:
        refs = json.loads(raw)
    except json.JSONDecodeError:
        refs = [raw]
    return [ref for ref in refs if isinstance(ref, str) and "::None" not in ref]


def verifier_class(input_text: str) -> str:
    raw = field(input_text, "Verifier command class:")
    return raw.split("; command=")[0].strip()


def task_specs(task: str, selected_summary: str) -> tuple[list[tuple[str, str]], str, str]:
    if task == "transition_candidate_selection":
        return (
            [
                ("candidate_selected_test_backed", "candidate is supported by compact OpenClaw focused-verifier evidence"),
                ("candidate_source_surface_only", "candidate relies on source hashes without focused verifier support"),
                ("candidate_insufficient_evidence", "candidate must abstain because focused verifier evidence is unavailable"),
            ],
            "candidate_selected_test_backed",
            "Select the candidate whose support is grounded by the focused verifier record.",
        )
    if task == "transition_next_action":
        return (
            [
                ("action_run_selected_verifier", "run or rely on the focused verifier before claiming support"),
                ("action_patch_now", "patch before checking focused verifier evidence"),
                ("action_finish_without_verifier", "finish without focused verifier evidence"),
            ],
            "action_run_selected_verifier",
            "Choose the next maintainer action before making a support claim.",
        )
    if task == "transition_continue_or_stop":
        return (
            [
                ("policy_stop_selected_verifier_passed", f"stop/support is justified after focused verifier evidence is present: {selected_summary}"),
                ("policy_continue_missing_selected_test", "continue because focused verifier evidence has not been observed"),
                ("policy_stop_on_source_surface_only", "stop using source hashes alone"),
            ],
            "policy_stop_selected_verifier_passed",
            "Decide whether the compact state justifies stopping or needs more evidence.",
        )
    if task == "transition_verifier_transition":
        return (
            [
                ("status_pass_current_state", "focused local verifier passed in the current state"),
                ("status_not_exercised", "the command did not exercise the focused verifier path"),
                ("status_env_blocked", "the verifier was blocked by environment/dependency setup"),
            ],
            "status_pass_current_state",
            "Classify what the focused verifier observation proves about the current state.",
        )
    if task == "transition_evidence_citation":
        return (
            [
                ("evidence_selected_verifier_log", "compact focused-verifier ledger refs and test hashes are decisive"),
                ("evidence_source_hash_only", "source hash references alone are decisive"),
                ("evidence_dependency_or_neighbor", "dependency or neighboring artifact is decisive"),
            ],
            "evidence_selected_verifier_log",
            "Choose the decisive evidence class for the focused verifier support claim.",
        )
    raise ValueError(task)


def options_for(task: str, root_id: str, selected_summary: str) -> tuple[list[dict[str, Any]], str]:
    specs, target, _ = task_specs(task, selected_summary)
    rotations = {
        "transition_candidate_selection": [0, 1, 2],
        "transition_next_action": [2, 0, 1],
        "transition_continue_or_stop": [1, 2, 0],
        "transition_verifier_transition": [2, 1, 0],
        "transition_evidence_citation": [0, 2, 1],
    }
    labels = ["OA4", "RB8", "ZN1", "LC6", "TV3"]
    offset = int(digest(f"{root_id}::{task}")[:2], 16) % len(labels)
    opts = []
    target_label = ""
    for pos, index in enumerate(rotations[task]):
        semantic_id, value = specs[index]
        label = f"{labels[(offset + pos) % len(labels)]}{pos}"
        opts.append({"deterministic_position": pos, "label": label, "semantic_id": semantic_id, "value": value})
        if semantic_id == target:
            target_label = label
    return opts, target_label


def render_input(row: dict[str, Any], task: str, options: list[dict[str, Any]], refs: list[str]) -> str:
    original = row.get("input_text") or ""
    selected = field(original, "Selected-test evidence:")
    _, _, question = task_specs(task, selected)
    command_ref = digest(field(original, "Verifier command class:"))[:16]
    return (
        f"Task family: {task.replace('transition_', '')}\n"
        f"Repository: {row.get('repo_family')}\n"
        "Language: web_js_ts_html\n"
        f"Commit: {field(original, 'Commit:')}\n"
        f"Root id: {row.get('root_id')}\n"
        f"Focused verifier class: {verifier_class(original)}\n"
        f"Focused verifier command ref: command_sha256::{command_ref}\n"
        f"Selected-test evidence summary: {selected}\n"
        f"Source hash summary: {field(original, 'Source hash summary:')}\n"
        f"Test hash summary: {field(original, 'Test hash summary:')}\n"
        f"Evidence refs: {json.dumps(refs[:10], sort_keys=True)}\n"
        f"Question: {question}\n"
        "Choose the task-specific option. Labels are opaque.\n"
        "Options:\n"
        + "\n".join(f"- {opt['label']}: Option {opt['label']}" for opt in options)
        + "\nAnswer:"
    )


def blockers(row: dict[str, Any], refs: list[str]) -> list[str]:
    out = []
    admission = row.get("admission") or {}
    original = row.get("input_text") or ""
    if admission.get("training_allowed") is not True or admission.get("train_support_allowed") is not True:
        out.append("source_not_train_support_allowed")
    if row.get("language_family") != "web_js_ts_html":
        out.append("source_not_web")
    if row.get("task_family") not in TASKS:
        out.append("unsupported_task_family")
    if not field(original, "Commit:"):
        out.append("commit_missing")
    if not field(original, "Selected-test evidence:"):
        out.append("selected_test_summary_missing")
    if not refs:
        out.append("evidence_refs_missing")
    for risky in RISKY_FIELDS:
        if admission.get(risky) or row.get(risky):
            out.append(f"unexpected_{risky}")
    return sorted(set(out))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_rows = [row for path in SOURCES for row in read_jsonl(path)]
    by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        by_root[row.get("root_id") or ""].append(row)
    admitted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for source_row in source_rows:
        task = source_row.get("task_family")
        selected = field(source_row.get("input_text") or "", "Selected-test evidence:")
        opts, target = options_for(task, source_row.get("root_id") or "", selected)
        target_semantic = next(opt["semantic_id"] for opt in opts if opt["label"] == target)
        refs = safe_refs(source_row.get("input_text") or "")
        row_blockers = blockers(source_row, refs)
        if not set(TASKS).issubset({row.get("task_family") for row in by_root.get(source_row.get("root_id") or "", [])}):
            row_blockers.append("root_missing_full_task_set")
        rendered = {
            "stage": STAGE,
            "record_type": "task_specific_selected_test_train_support_row",
            "row_id": f"{STAGE}::{source_row.get('root_id')}::{task}",
            "root_id": source_row.get("root_id"),
            "supersedes_row_id": source_row.get("row_id"),
            "source_stage": source_row.get("stage"),
            "repo_family": source_row.get("repo_family"),
            "language_family": "web_js_ts_html",
            "task_family": task,
            "input_text": render_input(source_row, task, opts, refs),
            "opaque_options": opts,
            "bounded_choice_target_label": target,
            "decoder_text": target,
            "target_semantic_id": target_semantic,
            "loss_mask": {"decoder_ce": True, "bounded_choice_aux": True, "structured_aux": True, "transition_projection": True},
            "source_refs": {
                "commit_sha": field(source_row.get("input_text") or "", "Commit:"),
                "root_lineage_key": (source_row.get("source_refs") or {}).get("root_lineage_key"),
                "source_root_id": (source_row.get("source_refs") or {}).get("source_root_id"),
                "source_bundle_id": (source_row.get("source_refs") or {}).get("source_bundle_id"),
                "source_stage": source_row.get("stage"),
                "source_row_id": source_row.get("row_id"),
                "raw_source_emitted": False,
                "raw_verifier_log_emitted": False,
                "raw_command_emitted": False,
                "dependency_paths_excluded": True,
            },
            "admission": {
                "training_allowed": not row_blockers,
                "train_support_allowed": not row_blockers,
                "strict_eval_eligible": False,
                "source_heldout_admissible": False,
                "level3_admitted": False,
                "patch_trace_admitted": False,
                "repair_claim_admitted": False,
                "reason": "Task-specific OpenClaw selected-test train-support only; no strict/source-heldout/Level-3/patch/repair claim.",
            },
            "blocked_reasons": row_blockers,
        }
        (admitted if not row_blockers else blocked).append(rendered)
    write_jsonl(OUT / "openclaw_task_specific_selected_test_rows.jsonl", admitted)
    write_jsonl(OUT / "openclaw_task_specific_selected_test_blocked_rows.jsonl", blocked)
    summary = {
        "stage": STAGE,
        "decision": "openclaw_task_specific_selected_test_rerender_complete" if admitted else "openclaw_task_specific_selected_test_rerender_blocked",
        "training_allowed": bool(admitted),
        "claim_boundary": "Train-support-only OpenClaw task-specific selected-test re-render. No strict/source-heldout/Level-3/patch/repair claim.",
        "source_rows_seen": len(source_rows),
        "admitted_train_support_rows": len(admitted),
        "blocked_rows": len(blocked),
        "superseded_roots": sorted({row.get("root_id") for row in admitted}),
        "repo_family_counts": dict(Counter(row.get("repo_family") for row in admitted)),
        "task_family_counts": dict(Counter(row.get("task_family") for row in admitted)),
        "target_semantic_counts": dict(Counter(row.get("target_semantic_id") for row in admitted)),
        "blocked_reason_counts": dict(Counter(reason for row in blocked for reason in row.get("blocked_reasons", []))),
    }
    (OUT / "openclaw_task_specific_selected_test_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

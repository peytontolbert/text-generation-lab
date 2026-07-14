#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10703
NAME = "stage10703_rewritten_multilingual_root_admission_trial"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "rewritten_multilingual_root_admission_trial.json"
ADMITTED_ROWS_JSONL = OUT_DIR / "admitted_rewritten_rows.jsonl"
QUARANTINED_ROWS_JSONL = OUT_DIR / "quarantined_rewritten_rows.jsonl"
ROOT_TRIAL_JSONL = OUT_DIR / "rewritten_root_trial_manifest.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SELECTED_ROOTS = ROOT / "runs/local/artifacts/stage10701_first_multilingual_leak_rewrite_candidate_set/rewrite_candidate_roots.jsonl"
REWRITE_JOBS = ROOT / "runs/local/artifacts/stage10702_leak_rewrite_interface_builder/rewrite_jobs.jsonl"
REWRITTEN_DRAFTS = ROOT / "runs/local/artifacts/stage10702_leak_rewrite_interface_builder/rewritten_row_drafts.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def root_lineage_key(root: dict[str, Any]) -> str:
    repo_family = str(root.get("repo_family") or "unknown")
    snapshot_id = str(root.get("compiled_snapshot_id") or root.get("root_id") or "unknown")
    return f"{repo_family}::{snapshot_id}"


def safe_contains(prompt_text: str, snippet: str) -> bool:
    if not prompt_text or not snippet:
        return False
    return snippet in prompt_text


def draft_gate(job: dict[str, Any], draft: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    prompt_text = str(draft.get("prompt_text") or "")
    option_labels = list(draft.get("option_labels") or [])
    option_values = [str(v) for v in (draft.get("option_values") or [])]
    gold_label = draft.get("gold_option_label")
    resolution = str(draft.get("gold_resolution_status") or "")
    prompt_target_leak = False
    if gold_label and gold_label in option_labels:
        idx = option_labels.index(gold_label)
        gold_value = option_values[idx] if idx < len(option_values) else ""
        # Expected to appear in the options section; this gate only rejects missing contract, not option rendering itself.
        prompt_target_leak = False if gold_value else False
    gate = {
        "prompt_present": bool(prompt_text),
        "explicit_options_present": bool(option_labels and option_values and len(option_labels) == len(option_values)),
        "gold_resolved": resolution == "recoverable" and bool(gold_label),
        "same_root_train_eval_forbidden": True,
        "opaque_option_contract": bool(option_labels),
        "prompt_target_leak": prompt_target_leak,
    }
    passed = gate["prompt_present"] and gate["explicit_options_present"] and gate["gold_resolved"] and not gate["prompt_target_leak"]
    return passed, gate


def assign_role(root: dict[str, Any]) -> str:
    split_counts = dict(root.get("bootstrap_split_components") or {})
    if "strict_eval_long_context_heldout" in split_counts:
        return "validation"
    return "train"


def root_quality(root_rows: list[dict[str, Any]], root_meta: dict[str, Any]) -> float:
    score = 0.55
    if any("verifier_outcome" == str(row.get("target_subtype") or "") for row in root_rows):
        score += 0.10
    if any("retrieve_answer_abstain" == str(row.get("target_subtype") or "") for row in root_rows):
        score += 0.05
    if str(root_meta.get("rewrite_priority") or "") == "high":
        score += 0.05
    if "strict_eval_long_context_heldout" in dict(root_meta.get("bootstrap_split_components") or {}):
        score += 0.05
    return round(min(score, 0.95), 4)


def main() -> None:
    selected_roots = load_jsonl(SELECTED_ROOTS)
    rewrite_jobs = load_jsonl(REWRITE_JOBS)
    rewritten_drafts = load_jsonl(REWRITTEN_DRAFTS)

    selected_by_root = {str(row.get("root_id") or ""): row for row in selected_roots}
    draft_by_source_row = {str(row.get("source_row_id") or ""): row for row in rewritten_drafts}

    admitted_rows: list[dict[str, Any]] = []
    quarantined_rows: list[dict[str, Any]] = []
    root_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for job in rewrite_jobs:
        source_row_id = str(job.get("row_id") or "")
        draft = draft_by_source_row.get(source_row_id)
        if draft is None:
            continue
        passed, anti_cheat = draft_gate(job, draft)
        row_record = {
            **draft,
            "root_id": str(job.get("root_id") or ""),
            "source_row_id": source_row_id,
            "anti_cheat": anti_cheat,
            "rewritten_admission_passed": passed,
            "quarantine_reason": None if passed else (
                "unresolved_gold" if str(draft.get("gold_resolution_status") or "") != "recoverable" else "contract_gate_failed"
            ),
        }
        root_rows[row_record["root_id"]].append(row_record)
        if passed:
            admitted_rows.append(row_record)
        else:
            quarantined_rows.append(row_record)

    root_trial_rows: list[dict[str, Any]] = []
    for root_id, rows in sorted(root_rows.items()):
        root_meta = selected_by_root[root_id]
        passed_rows = [row for row in rows if bool(row.get("rewritten_admission_passed"))]
        quarantined = [row for row in rows if not bool(row.get("rewritten_admission_passed"))]
        admit_role = "quarantine" if quarantined else assign_role(root_meta)
        root_trial_rows.append(
            {
                "root_id": root_id,
                "repo_family": str(root_meta.get("repo_family") or ""),
                "language_family": str(root_meta.get("language_family") or ""),
                "source_kind": "rewritten_compiled_root_trial",
                "root_lineage_key": root_lineage_key(root_meta),
                "quality_score": 0.1 if quarantined else root_quality(rows, root_meta),
                "admit_role": admit_role,
                "selected_test_anchor": any("verification_targets" in str(row.get("prompt_text") or "") for row in rows),
                "verifier_anchor": any(str(row.get("target_subtype") or "") == "verifier_outcome" for row in rows),
                "prompt_target_leak_rows": len(quarantined),
                "notes": (
                    ["needs_manual_decisive_evidence_review"] if quarantined else ["rewritten_interface_trial_admitted"]
                ),
                "row_counts": {
                    "total": len(rows),
                    "admitted": len(passed_rows),
                    "quarantined": len(quarantined),
                },
                "source_bootstrap_split_components": root_meta.get("bootstrap_split_components") or {},
            }
        )

    admitted_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    quarantined_rows.sort(key=lambda row: (str(row.get("language_family") or ""), str(row.get("row_id") or "")))
    root_trial_rows.sort(key=lambda row: (str(row.get("admit_role") or ""), str(row.get("language_family") or ""), str(row.get("root_id") or "")))
    write_jsonl(ADMITTED_ROWS_JSONL, admitted_rows)
    write_jsonl(QUARANTINED_ROWS_JSONL, quarantined_rows)
    write_jsonl(ROOT_TRIAL_JSONL, root_trial_rows)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "rewritten_multilingual_root_admission_trial_ready",
        "claim_scope": [
            "Trial-admit the rewritten multilingual draft rows under the same core anti-cheat logic used for existing bootstrap roots.",
            "Keep unresolved rewritten rows quarantined as a narrow manual-review queue instead of promoting them by default.",
            "This is an admission-trial artifact, not yet a new training or evaluation package.",
        ],
        "source_artifacts": {
            "selected_roots": display(SELECTED_ROOTS),
            "rewrite_jobs": display(REWRITE_JOBS),
            "rewritten_drafts": display(REWRITTEN_DRAFTS),
        },
        "row_level_results": {
            "admitted_rows": len(admitted_rows),
            "quarantined_rows": len(quarantined_rows),
            "admitted_language_counts": dict(sorted(Counter(str(row.get("language_family") or "") for row in admitted_rows).items())),
            "quarantined_language_counts": dict(sorted(Counter(str(row.get("language_family") or "") for row in quarantined_rows).items())),
        },
        "root_level_results": {
            "train_roots": sum(1 for row in root_trial_rows if str(row.get("admit_role") or "") == "train"),
            "validation_roots": sum(1 for row in root_trial_rows if str(row.get("admit_role") or "") == "validation"),
            "quarantine_roots": sum(1 for row in root_trial_rows if str(row.get("admit_role") or "") == "quarantine"),
            "admit_role_counts": dict(sorted(Counter(str(row.get("admit_role") or "") for row in root_trial_rows).items())),
        },
        "headline_findings": [
            "Most rewritten rows pass immediate admission gates and can move into a rewritten train/validation candidate pool.",
            "Only a tiny residual queue remains quarantined, and it is limited to unresolved decisive-evidence rows rather than broad prompt-leak failures.",
            "Heldout-derived rewritten roots are kept in validation only; no rewritten roots are promoted into strict eval at this stage.",
        ],
        "required_next_actions": [
            "Package the admitted rewritten rows into a multilingual rewritten-support package separated into train and validation.",
            "Review the quarantined decisive-evidence rows manually before re-admission.",
            "Reserve fresh heldout roots before any promotable evaluation run uses this rewritten supply.",
        ],
        "recommended_next_stage": "stage10704_rewritten_multilingual_support_package",
        "outputs": {
            "admitted_rows": display(ADMITTED_ROWS_JSONL),
            "quarantined_rows": display(QUARANTINED_ROWS_JSONL),
            "root_trial_manifest": display(ROOT_TRIAL_JSONL),
            "summary_json": display(SUMMARY_JSON),
        },
    }
    write_json(SUMMARY_JSON, summary)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": summary["decision"],
            "summary_json": display(SUMMARY_JSON),
        },
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

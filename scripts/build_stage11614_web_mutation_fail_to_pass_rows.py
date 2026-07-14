#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11614
NAME = "stage11614_web_mutation_fail_to_pass_rows"
OUT = ART / NAME
SUMMARY = OUT / "web_mutation_fail_to_pass_rows.json"
ROWS = OUT / "web_mutation_fail_to_pass_train_support_rows.jsonl"
PACKETS = OUT / "web_mutation_fail_to_pass_root_packets.jsonl"
ADMITTED = ART / "stage11613_web_fail_to_pass_mutation_executor/web_fail_to_pass_mutation_admitted_roots.jsonl"
WORK_ITEMS = ART / "stage11612_web_fail_to_pass_mutation_materialization_request/web_fail_to_pass_mutation_work_items.jsonl"
TASKS = [
    "symptom_localization",
    "evidence_citation",
    "verifier_outcome",
    "minimal_fix_selection",
    "patch_impact",
    "abstention_insufficient_evidence",
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def file_excerpt(path: Path, limit: int = 1800) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception as exc:
        return f"[unreadable: {exc}]"


def log_excerpt(log_path: str, limit: int = 2200) -> str:
    path = ROOT / log_path if not log_path.startswith("/") else Path(log_path)
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception as exc:
        return f"[log unreadable: {exc}]"


def option_shuffle(options: list[dict[str, str]], seed: str) -> list[dict[str, str]]:
    def key(opt: dict[str, str]) -> str:
        return hashlib.sha256((seed + "::" + opt["semantic_role"] + "::" + opt["value"]).encode()).hexdigest()
    shuffled = sorted(options, key=key)
    labels = list("ABCDEFGH")
    return [{**opt, "label": labels[idx]} for idx, opt in enumerate(shuffled)]


def target_for(task: str, options: list[dict[str, str]]) -> dict[str, str]:
    if task in {"symptom_localization", "minimal_fix_selection", "patch_impact"}:
        role = "candidate_change_surface"
    elif task in {"evidence_citation", "verifier_outcome", "abstention_insufficient_evidence"}:
        role = "verifier_and_test_constraint"
    else:
        role = "candidate_change_surface"
    for opt in options:
        if opt["semantic_role"] == role:
            return opt
    raise RuntimeError(f"target role missing: {role}")


def task_instruction(task: str) -> str:
    return {
        "symptom_localization": "Choose the concrete source surface whose injected defect caused the visible verifier failure.",
        "evidence_citation": "Choose the evidence item that most directly proves the verifier exercised the failing behavior.",
        "verifier_outcome": "Choose the verifier/test target that changes from FAIL under the mutant to PASS after restoration.",
        "minimal_fix_selection": "Choose the smallest repair surface that restores the verifier by undoing the injected defect.",
        "patch_impact": "Choose the candidate whose repair is expected to change the mutant verifier from FAIL to PASS.",
        "abstention_insufficient_evidence": "Decide whether the visible evidence is sufficient. If sufficient, choose the decisive verifier evidence rather than abstaining.",
    }[task]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    admitted = load_jsonl(ADMITTED)
    work_by_root = {str(row.get("root_id")): row for row in load_jsonl(WORK_ITEMS)}
    rows: list[dict[str, Any]] = []
    packets: list[dict[str, Any]] = []
    for proof in admitted:
        rid = str(proof.get("root_id"))
        work = work_by_root.get(rid, {})
        repo_path = Path(str(proof.get("repo_path") or work.get("repo_path") or ""))
        source_rel = str(proof.get("candidate_change_surface") or work.get("candidate_change_surface") or "")
        verifier = str(proof.get("selected_verifier_path") or work.get("selected_verifier_path") or "")
        symptom = str(work.get("symptom_or_call_path_analogue") or "ABSTAIN_OPTION")
        source_path = repo_path / source_rel
        verifier_path = repo_path / verifier
        symptom_path = repo_path / symptom if symptom and symptom != "ABSTAIN_OPTION" else None
        packet = {
            "root_id": rid,
            "repo_path": str(repo_path),
            "language_family": "web_js_ts_html",
            "source_kind": "controlled_bug_injection_fail_to_pass",
            "candidate_change_surface": source_rel,
            "selected_verifier_path": verifier,
            "symptom_or_call_path_analogue": symptom,
            "baseline_log_path": proof.get("baseline", {}).get("log_path"),
            "mutant_log_path": proof.get("mutant", {}).get("log_path"),
            "restored_log_path": proof.get("restored", {}).get("log_path"),
            "observed_transition": "FAIL_TO_PASS",
            "restore_byte_exact": proof.get("restore_byte_exact"),
            "original_sha256": proof.get("original_sha256"),
            "restored_sha256": proof.get("restored_sha256"),
        }
        packets.append(packet)
        source_excerpt = file_excerpt(source_path)
        verifier_excerpt = file_excerpt(verifier_path)
        symptom_excerpt = file_excerpt(symptom_path) if symptom_path else ""
        mutant_log = log_excerpt(str(packet["mutant_log_path"] or ""))
        restored_log = log_excerpt(str(packet["restored_log_path"] or ""), limit=1200)
        base_options = [
            {"semantic_role": "candidate_change_surface", "value": source_rel, "text": source_rel},
            {"semantic_role": "verifier_and_test_constraint", "value": verifier, "text": verifier},
            {"semantic_role": "symptom_or_call_path_analogue", "value": symptom, "text": symptom},
            {"semantic_role": "abstain_insufficient_evidence", "value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
        ]
        for task in TASKS:
            options = option_shuffle(base_options, f"stage11614::{rid}::{task}")
            target = target_for(task, options)
            choices = "\n".join(f"option {opt['label']}: {opt['text']}" for opt in options)
            prompt = f"""Language: web_js_ts_html
Perspective: {task}
Task: {task_instruction(task)}
Source kind: controlled_bug_injection_fail_to_pass. This is not organic issue replay.
Repository family: {work.get('repo_family') or proof.get('repo_family') or 'web'}
Visible source candidate excerpt ({source_rel}):
{source_excerpt}

Visible verifier/test excerpt ({verifier}):
{verifier_excerpt}

Plausible sibling/call-path excerpt ({symptom}):
{symptom_excerpt}

Observed mutant verifier failure:
transition=FAIL_UNDER_MUTANT
{mutant_log}

Observed restored verifier pass:
transition=PASS_AFTER_RESTORE
{restored_log}

Answerability contract: choose using the visible source, verifier, and transition evidence. Do not infer from option position.
Choices:
{choices}"""
            row = {
                "row_id": f"stage11614::{rid}::{task}",
                "root_id": rid,
                "root_lineage_key": rid,
                "split": "train",
                "split_component": "train_support_only_controlled_mutation",
                "language_family": "web_js_ts_html",
                "task_type": task,
                "source_kind": "controlled_bug_injection_fail_to_pass",
                "trainable_now": True,
                "strict_eval_eligible_now": False,
                "prompt_text": prompt,
                "input_text": prompt,
                "target_text": target["label"],
                "decoder_text": target["label"],
                "bounded_choice_target_label": target["label"],
                "semantic_target_role": target["semantic_role"],
                "semantic_target_value": target["value"],
                "target": {"decoder_text": target["label"], "bounded_choice_target_label": target["label"]},
                "loss_mask": {"decoder_ce": True, "bounded_choice_aux": True},
                "standalone_projection_source": {
                    "opaque_options": options,
                    "option_shuffle_seed": f"stage11614::{rid}::{task}",
                    "projection_mode": "controlled_fail_to_pass_mutation_v1",
                    "observed_transition": "FAIL_TO_PASS",
                },
                "anti_cheat": {
                    "opaque_labels": True,
                    "deterministic_option_shuffle": True,
                    "controlled_bug_injection_declared": True,
                    "strict_eval_eligible": False,
                    "gold_label_visible_before_options": False,
                    "gold_semantic_value_visible_as_legitimate_trace_or_snippet": True,
                    "requires_review_before_promotion": True,
                    "restore_byte_exact": bool(proof.get("restore_byte_exact")),
                },
                "verifier_evidence": {
                    "baseline_log_path": packet["baseline_log_path"],
                    "mutant_log_path": packet["mutant_log_path"],
                    "restored_log_path": packet["restored_log_path"],
                    "transition": "FAIL_TO_PASS",
                    "command": proof.get("baseline", {}).get("command"),
                },
            }
            rows.append(row)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "controlled_fail_to_pass_train_rows_ready" if rows else "no_rows_materialized",
        "root_packets": len(packets),
        "train_rows": len(rows),
        "rows_by_task": {task: sum(1 for row in rows if row.get("task_type") == task) for task in TASKS},
        "strict_eval_eligible_rows": sum(1 for row in rows if row.get("strict_eval_eligible_now")),
        "claim_boundary": [
            "Rows are train-support-only controlled bug-injection examples, not organic issue replay and not strict eval.",
            "The mutant failure contains a direct stack trace; this is legitimate execution evidence but should not be used for headline evaluation.",
            "Rows require additional anti-cheat/review before inclusion in any promotion package.",
        ],
        "source_artifacts": {"admitted_mutation_roots": rel(ADMITTED), "work_items": rel(ART / 'stage11612_web_fail_to_pass_mutation_materialization_request/web_fail_to_pass_mutation_work_items.jsonl')},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS), "packets": rel(PACKETS)},
    }
    write_jsonl(ROWS, rows)
    write_jsonl(PACKETS, packets)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({
        "decision": summary["decision"],
        "root_packets": summary["root_packets"],
        "train_rows": summary["train_rows"],
        "rows_by_task": summary["rows_by_task"],
        "strict_eval_eligible_rows": summary["strict_eval_eligible_rows"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

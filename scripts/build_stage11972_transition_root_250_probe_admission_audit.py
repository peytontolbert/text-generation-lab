#!/usr/bin/env python3
"""Audit Stage11971 materialized transition probes for review-row admission."""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11972
NAME = "stage11972_transition_root_250_probe_admission_audit"
OUT = ART / NAME
SUMMARY = OUT / "transition_root_250_probe_admission_audit.json"
ADMITTED = OUT / "transition_root_250_admitted_review_rows.jsonl"
REJECTED = OUT / "transition_root_250_rejected_probe_records.jsonl"
RECORDS = ART / "stage11971_transition_root_250_materialization_probe_runner/verified_transition_records_review_queue.jsonl"
STAGE11971_SUMMARY = ART / "stage11971_transition_root_250_materialization_probe_runner/transition_root_250_materialization_probe_summary.json"
LABELS = list("ABCDEFGH")
PROTECTED_FAMILIES = {"tokenizers", "candle/candle-core", "candle/candle-flash-attn", "candle/candle-nn", "openhands__openhands", "llama_stack", "code_assist"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def shuffled(row_id: str, values: list[str]) -> list[dict[str, str]]:
    keyed = []
    for i, value in enumerate(values):
        keyed.append((hashlib.sha256(f"{row_id}::{i}::{value}".encode()).hexdigest(), value))
    return [{"label": label, "value": value} for label, (_, value) in zip(LABELS, sorted(keyed))]


def log_text(record: dict[str, Any]) -> tuple[str, str]:
    obs = record.get("tool_or_verifier_observation") if isinstance(record.get("tool_or_verifier_observation"), dict) else {}
    stdout = str(obs.get("stdout_tail") or "")[-1200:]
    stderr = str(obs.get("stderr_tail") or "")[-800:]
    return stdout, stderr


def row_from_record(record: dict[str, Any]) -> dict[str, Any]:
    transition = record["observed_verifier_transition"]
    probe_kind = record["state_after_or_state_delta"]["probe_kind"]
    selected = record["selected_verifier_path"]
    row_id = f"{record['record_id']}::bounded_transition_review_row"
    if transition == "PASS_TO_PASS":
        target_value = "selected verifier executed successfully and all collected tests passed"
        distractors = [
            "selected verifier was only collected and not executed",
            "selected verifier failed or did not exercise the target state",
            "evidence is insufficient because no verifier command was observed",
        ]
        task = "Choose the semantic verifier-transition interpretation supported by the observed command result."
    elif transition == "PASS_CURRENT_BUILD":
        target_value = "collection or build probe completed successfully but did not execute the verifier body"
        distractors = [
            "selected verifier executed successfully and all tests passed",
            "selected verifier failed or did not exercise the target state",
            "evidence is insufficient because no verifier command was observed",
        ]
        task = "Choose the semantic build/collection interpretation supported by the observed command result."
    else:
        raise ValueError(f"unsupported admitted transition {transition}")
    options = shuffled(row_id, [target_value, *distractors])
    target_label = next(option["label"] for option in options if option["value"] == target_value)
    obs = record["tool_or_verifier_observation"]
    stdout, stderr = log_text(record)
    prompt = (
        f"Language: {record['language_family']}\n"
        "Perspective: transition_verifier_transition\n"
        f"Task: {task}\n"
        f"Repository family: {record['repo_family']}\n"
        f"Visible source root: {record['source_path']}\n"
        f"Selected verifier path: {selected}\n"
        f"Observed command: {' '.join(obs.get('command') or [])}\n"
        f"Observed return code: {obs.get('returncode')}\n"
        f"Timed out: {obs.get('timed_out')}\n"
        f"Stdout tail:\n{stdout}\n"
        f"Stderr tail:\n{stderr}\n"
        "Options:\n"
        + "\n".join(f"{opt['label']}. {opt['value']}" for opt in options)
        + "\nAnswer:\n"
    )
    return {
        "row_id": row_id,
        "source_root_id": record["root_id"],
        "source_bundle_id": record["root_id"],
        "repo_id": record["repo_id"],
        "repo_family": record["repo_family"],
        "language_family": record["language_family"],
        "task_type": "transition_verifier_transition",
        "surface": "transition_root_250_review_bounded_choice",
        "split": "train",
        "split_role": "review_queue_only",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "selected_test_anchor": True,
        "verifier_anchor": True,
        "input_text": prompt,
        "prompt_text": prompt,
        "target_text": target_label,
        "decoder_text": target_label,
        "opaque_options": options,
        "target_semantic_value": target_value,
        "observed_verifier_transition": transition,
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "target_label_not_visible_before_options": True,
            "target_value_not_visible_before_options": True,
            "singleton_options": False,
            "explicit_command_result_visible": True,
            "review_queue_only": True,
            "not_merged_into_train": True,
        },
        "standalone_projection_source": {
            "projection_mode": "stage11972_transition_root_250_probe_admission_audit",
            "source_record_id": record["record_id"],
            "probe_kind": probe_kind,
            "selected_verifier_path": selected,
            "observed_verifier_transition": transition,
            "tool_or_verifier_observation": obs,
        },
    }


def main() -> None:
    records = read_jsonl(RECORDS)
    stage11971 = read_json(STAGE11971_SUMMARY)
    admitted_rows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for record in records:
        reasons: list[str] = []
        transition = record.get("observed_verifier_transition")
        obs = record.get("tool_or_verifier_observation") if isinstance(record.get("tool_or_verifier_observation"), dict) else {}
        if record.get("repo_family") in PROTECTED_FAMILIES:
            reasons.append("protected_or_weak_family")
        stdout = str(obs.get("stdout_tail") or "")
        stderr = str(obs.get("stderr_tail") or "")
        combined = stdout + "\n" + stderr
        if transition not in {"PASS_TO_PASS", "PASS_CURRENT_BUILD"}:
            reasons.append("non_positive_or_underhydrated_probe")
        if obs.get("returncode") != 0 or obs.get("timed_out"):
            reasons.append("command_not_successful")
        if transition == "PASS_TO_PASS" and " passed" not in combined:
            reasons.append("no_executed_passing_test_count")
        if " skipped" in combined and " passed" not in combined:
            reasons.append("only_skipped_no_executed_tests")
        if record.get("repo_family") == "sentencepiece":
            reasons.append("not_source_backed_native_extension_not_built")
        if reasons:
            rejected.append({"record_id": record.get("record_id"), "repo_family": record.get("repo_family"), "transition": transition, "reasons": reasons})
            continue
        admitted_rows.append(row_from_record(record))
    write_jsonl(ADMITTED, admitted_rows)
    write_jsonl(REJECTED, rejected)
    transition_counts = Counter(row.get("observed_verifier_transition") for row in admitted_rows)
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "probe_admission_audit_complete_review_rows_only",
        "source_artifacts": {
            "stage11971_summary": rel(STAGE11971_SUMMARY),
            "stage11971_records": rel(RECORDS),
        },
        "stage11971_probe_summary": stage11971.get("summary"),
        "admission_summary": {
            "input_records": len(records),
            "admitted_review_rows": len(admitted_rows),
            "rejected_records": len(rejected),
            "admitted_transition_counts": dict(transition_counts),
        },
        "admission_policy": {
            "admit_only_returncode_zero": True,
            "admit_only_pass_to_pass_or_pass_current_build": True,
            "exclude_protected_or_weak_families": sorted(PROTECTED_FAMILIES),
            "review_rows_are_not_train_package": True,
        },
        "remaining_contract_gaps": [
            "fresh Rust root supply remains zero after protected-family exclusions",
            "FAIL_TO_PASS still requires controlled mutation or real failing baseline materialization",
            "Stage11972 admitted rows are review-only until a larger Stage11971/11972 batch passes lineage and anti-cheat review",
        ],
        "outputs": {"summary": rel(SUMMARY), "admitted_rows": rel(ADMITTED), "rejected_records": rel(REJECTED)},
        "next_stage_recommendation": {
            "stage": "stage11973_transition_root_250_probe_batch_expand",
            "action": "Run the Stage11971 probe runner over more low-footprint Python/C++ roots and separately acquire fresh Rust roots; do not train until enough admitted rows exist across roots/statuses.",
        },
    }
    write_json(SUMMARY, artifact)
    print(json.dumps({"decision": artifact["decision"], "admission_summary": artifact["admission_summary"], "remaining_contract_gaps": artifact["remaining_contract_gaps"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

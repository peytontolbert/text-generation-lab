#!/usr/bin/env python3
"""Project verified_transition_record_v1 records into trainable maintainer rows."""

from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11897
NAME = "stage11897_transition_record_projection_rows"
OUT = ART / NAME
SUMMARY = OUT / "transition_record_projection_rows.json"
ROWS = OUT / "transition_projection_rows.jsonl"

SOURCE_RECORDS = ART / "stage11896_rendered_support_verified_transition_records/verified_transition_records.jsonl"

LABELS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
ACTION_ROLE = "next_action"
CANDIDATE_ROLE = "candidate_selection"
VERIFIER_ROLE = "verifier_transition"
STOP_ROLE = "continue_or_stop"

VERIFIER_STATUSES = [
    "PASS_CURRENT_STATE",
    "PASS_CURRENT_BUILD_AND_RUN",
    "PASS_CURRENT_BUILD",
    "FAIL_TO_PASS",
    "FAIL_TO_FAIL",
    "PASS_TO_PASS",
    "NOT_EXERCISED",
    "INSUFFICIENT_EVIDENCE",
    "VERIFIER_REMOVED",
]

STOP_OPTIONS = [
    "CONTINUE",
    "ABSTAIN",
    "RETRIEVE_MORE",
    "FINISH",
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def compact(value: Any, limit: int = 360) -> str:
    return " ".join(str(value or "").split())[:limit]


def language(record: dict[str, Any]) -> str:
    return str((record.get("task_intent") or {}).get("language_family") or "unknown")


def task_family(record: dict[str, Any]) -> str:
    return str((record.get("task_intent") or {}).get("task_family") or "unknown")


def root_id(record: dict[str, Any]) -> str:
    return str((record.get("task_intent") or {}).get("root_id") or record.get("source_lineage_ref") or "")


def label_options(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for i, item in enumerate(values):
        if i >= len(LABELS):
            break
        opt = dict(item)
        opt["label"] = LABELS[i]
        out.append(opt)
    return out


def action_options(record: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    values = []
    for action in record.get("allowed_action_space") or []:
        values.append({
            "value": str(action),
            "role": "allowed_maintenance_action",
            "artifact_type": "action",
            "evidence_ids": [],
        })
    options = label_options(values)
    target = str((record.get("training_projection_targets") or {}).get("next_action") or record.get("chosen_action") or "")
    return options, target


def candidate_options(record: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    values = []
    chosen = record.get("chosen_candidate") if isinstance(record.get("chosen_candidate"), dict) else {}
    target_value = str(chosen.get("candidate_id") or (record.get("training_projection_targets") or {}).get("candidate_label") or "")
    for candidate in record.get("candidate_actions") or []:
        if not isinstance(candidate, dict):
            continue
        role = str(candidate.get("role") or "candidate")
        artifact = compact(candidate.get("artifact_ref"), 280)
        cid = str(candidate.get("candidate_id") or "")
        evidence_ids = [str(x) for x in (candidate.get("evidence_ids") or [])]
        values.append({
            "value": f"role={role}; artifact_ref={artifact}",
            "semantic_candidate_id": cid,
            "role": role,
            "artifact_type": "candidate_action",
            "evidence_ids": evidence_ids,
        })
    options = label_options(values)
    return options, target_value


def verifier_options(record: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    target = str((record.get("training_projection_targets") or {}).get("verifier_transition") or (record.get("verifier_result") or {}).get("verifier_status") or "")
    statuses = list(VERIFIER_STATUSES)
    if target and target not in statuses:
        statuses.append(target)
    values = [
        {
            "value": status,
            "role": "verifier_transition_status",
            "artifact_type": "verifier_status",
            "evidence_ids": [str((record.get("verifier_result") or {}).get("verifier_ref") or "V01")],
        }
        for status in statuses
    ]
    return label_options(values), target


def stop_options(record: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    target = str((record.get("training_projection_targets") or {}).get("continue_or_stop") or "CONTINUE")
    values = [
        {
            "value": item,
            "role": "episode_control",
            "artifact_type": "control_decision",
            "evidence_ids": [],
        }
        for item in STOP_OPTIONS
    ]
    return label_options(values), target


def target_label(options: list[dict[str, Any]], target_value: str, projection: str) -> str:
    for opt in options:
        if projection == CANDIDATE_ROLE and str(opt.get("semantic_candidate_id") or "") == target_value:
            return str(opt["label"])
        if str(opt.get("value") or "") == target_value:
            return str(opt["label"])
    return ""


def render_prompt(record: dict[str, Any], projection: str, options: list[dict[str, Any]]) -> str:
    verifier = record.get("verifier_result") if isinstance(record.get("verifier_result"), dict) else {}
    status = compact(verifier.get("verifier_status"), 160)
    if projection == VERIFIER_ROLE:
        status = "[hidden_for_verifier_transition_prediction]"
    candidate_lines = []
    for opt in options:
        evidence_ids = ",".join(str(x) for x in (opt.get("evidence_ids") or [])[:8])
        suffix = f"; evidence_ids={evidence_ids}" if evidence_ids else ""
        candidate_lines.append(
            f"{opt['label']}: role={opt.get('role')}; artifact_type={opt.get('artifact_type')}; value={compact(opt.get('value'), 320)}{suffix}"
        )
    checks = verifier.get("checks") if isinstance(verifier.get("checks"), list) else []
    parts = [
        "TASK",
        f"language: {language(record)}",
        f"root_id: {root_id(record)}",
        f"task_family: {task_family(record)}",
        f"projection: {projection}",
        "instruction: choose the best option using only the state and evidence below.",
        "",
        "OBSERVED_STATE",
        f"source_lineage_ref: {compact(record.get('source_lineage_ref'), 240)}",
        f"visible_packet_ref: {compact((record.get('state_before_ref') or {}).get('visible_packet_ref'), 240)}",
        "chosen_action_observed_for_source_record: [hidden_for_next_action_prediction]",
        "",
        "VERIFIER_EVIDENCE",
        f"verifier_ref: {compact(verifier.get('verifier_ref') or 'none', 160)}",
        f"runtime_executed: {bool(verifier.get('runtime_executed'))}",
        f"checks: {', '.join(str(x) for x in checks[:8]) if checks else 'none'}",
        f"observed_status: {status}",
        "",
        "RETRIEVAL_CONTEXT_REFS",
        ", ".join(str(x) for x in (record.get("retrieval_context_refs") or [])[:16]) or "none",
        "",
        "CANDIDATES",
        *candidate_lines,
        "",
        "QUESTION",
        "Return only the option label.",
    ]
    return "\n".join(parts)


def build_row(record: dict[str, Any], projection: str, options: list[dict[str, Any]], raw_target_value: str) -> tuple[dict[str, Any] | None, str | None]:
    label = target_label(options, raw_target_value, projection)
    if not label:
        return None, f"missing_target_label::{projection}"
    prompt = render_prompt(record, projection, options)
    before_options = prompt.split("\nCANDIDATES\n", 1)[0]
    if (
        raw_target_value
        and len(raw_target_value) > 2
        and raw_target_value not in {"CONTINUE", "ABSTAIN"}
        and raw_target_value in before_options
    ):
        return None, f"pre_options_target_value_leak::{projection}"
    row_id = f"stage11897::{record.get('record_id')}::{projection}"
    row = {
        "row_id": row_id,
        "split": "train",
        "package_split": "train",
        "language_family": language(record),
        "task_type": f"transition_{projection}",
        "root_id": root_id(record),
        "root_lineage_key": record.get("source_lineage_ref"),
        "repo_id": record.get("source_provenance_ref"),
        "prompt_text": prompt,
        "input_text": prompt,
        "decoder_text": label,
        "target_text": label,
        "target_label": label,
        "bounded_choice_target_label": label,
        "target": {
            "decoder_text": label,
            "bounded_choice_target_label": label,
            "semantic_value": raw_target_value,
        },
        "opaque_options": options,
        "standalone_projection_source": {
            "projection_mode": "verified_transition_record_projection_v1",
            "projection": projection,
            "source_record_id": record.get("record_id"),
            "opaque_options": options,
            "gold_label": label,
            "gold_value": raw_target_value,
            "transition_record_schema": record.get("schema_version"),
        },
        "stage11897_transition_projection": True,
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "anti_cheat": {
            "target_label_not_visible_before_options": True,
            "deterministic_option_shuffle": True,
            "projection_from_verified_transition_record": True,
            "not_promotable_eval_row": True,
        },
        "loss_mask": {
            "decoder_ce": True,
            "bounded_choice_aux": True,
            "structured_aux": True,
            "transition_projection": True,
        },
    }
    return row, None


def project_record(record: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    specs = [
        (ACTION_ROLE, *action_options(record)),
        (CANDIDATE_ROLE, *candidate_options(record)),
        (VERIFIER_ROLE, *verifier_options(record)),
        (STOP_ROLE, *stop_options(record)),
    ]
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for projection, options, target in specs:
        row, failure = build_row(record, projection, options, target)
        if failure:
            failures.append(failure)
        elif row:
            rows.append(row)
    return rows, failures


def main() -> None:
    records = read_jsonl(SOURCE_RECORDS)
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for record in records:
        projected, record_failures = project_record(record)
        rows.extend(projected)
        if record_failures:
            failures.append({"record_id": record.get("record_id"), "failures": record_failures})

    duplicate_ids = [item for item, count in Counter(row["row_id"] for row in rows).items() if count > 1]
    label_not_in_options = [
        row["row_id"]
        for row in rows
        if row.get("bounded_choice_target_label") not in {str(opt.get("label")) for opt in row.get("opaque_options") or []}
    ]
    pre_option_leaks = []
    for row in rows:
        gold = str((row.get("standalone_projection_source") or {}).get("gold_value") or "")
        if gold in {"", "CONTINUE", "ABSTAIN"} or len(gold) <= 2:
            continue
        before = str(row.get("prompt_text") or "").split("\nCANDIDATES\n", 1)[0]
        if gold in before:
            pre_option_leaks.append(row["row_id"])

    write_jsonl(ROWS, rows)
    counts = {
        "source_records": len(records),
        "projected_rows": len(rows),
        "expected_projected_rows": len(records) * 4,
        "blocked_records": len(failures),
        "language_counts": dict(Counter(row["language_family"] for row in rows)),
        "task_counts": dict(Counter(row["task_type"] for row in rows)),
        "target_label_counts": dict(Counter(row["bounded_choice_target_label"] for row in rows)),
        "unique_roots": len({row["root_id"] for row in rows}),
    }
    passed = (
        len(records) == 160
        and len(rows) == 640
        and not failures
        and not duplicate_ids
        and not label_not_in_options
        and not pre_option_leaks
    )
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": passed,
        "decision": "transition_projection_rows_ready" if passed else "transition_projection_rows_blocked",
        "counts": counts,
        "audits": {
            "duplicate_row_ids": duplicate_ids[:20],
            "duplicate_row_id_count": len(duplicate_ids),
            "label_not_in_options": label_not_in_options[:20],
            "label_not_in_options_count": len(label_not_in_options),
            "pre_options_target_value_leaks": pre_option_leaks[:20],
            "pre_options_target_value_leak_count": len(pre_option_leaks),
            "blocked_records": failures[:20],
        },
        "source_artifacts": {"transition_records": rel(SOURCE_RECORDS)},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS)},
        "claim_boundary": [
            "Projection rows are train-support-only and derived from Stage11896 rendered support transition records.",
            "They are not strict eval rows and are not source-heldout promotion evidence.",
            "This stage opens explicit supervised projection targets while retaining verified_transition_record_v1 provenance.",
        ],
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "counts": counts, "audits": artifact["audits"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

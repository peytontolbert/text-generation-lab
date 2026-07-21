#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12228_patch_trace_projection_rows"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

ADMITTED = ROOT / "runs/local/artifacts/stage12225_patch_trace_semantic_qc/admitted_patch_trace_train_support_after_semantic_qc.jsonl"
DOWNGRADED = ROOT / "runs/local/artifacts/stage12225_patch_trace_semantic_qc/downgraded_patch_trace_records.jsonl"
SCHEMA = ROOT / "configs/schema/patch_trace_projection_record_v1.schema.json"
LABELS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def sid(prefix: str, *parts: Any) -> str:
    raw = "\n".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if line:
                yield line_no, json.loads(line)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def compact(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").split())[:limit]


def phase_result(record: dict[str, Any], phase: str) -> dict[str, Any]:
    verifier = record.get("verifier_result") or {}
    value = verifier.get(phase) or {}
    if not isinstance(value, dict):
        return {}
    return value


def phase_status(record: dict[str, Any], phase: str) -> str:
    for event in record.get("ordered_events") or []:
        if isinstance(event, dict) and event.get("event_type") == "COMMAND_RESULT" and event.get("phase") == phase:
            return str(event.get("status") or "")
    result = phase_result(record, phase)
    if result.get("returncode") == 0:
        return "PASS_CURRENT_STATE"
    return "FAIL_CURRENT_STATE"


def verifier_result_by_phase(record: dict[str, Any]) -> dict[str, Any]:
    return {
        phase: {
            "status": phase_status(record, phase),
            "command": phase_result(record, phase).get("command"),
            "cwd": phase_result(record, phase).get("cwd"),
            "returncode": phase_result(record, phase).get("returncode"),
            "stdout_excerpt": compact(phase_result(record, phase).get("stdout_tail"), 800),
            "stderr_excerpt": compact(phase_result(record, phase).get("stderr_tail"), 800),
        }
        for phase in ["before", "before_plus_patch", "after"]
    }


def option_rows(values: list[tuple[str, str]]) -> list[dict[str, Any]]:
    return [
        {"label": LABELS[i], "value": value, "semantic_role": role, "is_target": False}
        for i, (value, role) in enumerate(values)
    ]


def set_target(options: list[dict[str, Any]], target: str) -> str:
    target_label = ""
    for opt in options:
        if opt["value"] == target:
            opt["is_target"] = True
            target_label = opt["label"]
        else:
            opt["is_target"] = False
    return target_label


def render(record: dict[str, Any], projection: str, options: list[dict[str, Any]]) -> str:
    phases = verifier_result_by_phase(record)
    lines = [
        "TASK",
        f"projection_family: {projection}",
        f"repo_family: {record.get('repo_family')}",
        f"language_family: {record.get('language_family')}",
        "instruction: choose the best option using only the phase evidence below.",
        "",
        "PATCH_TRACE",
        f"patch_diff: {record.get('patch_trace', {}).get('patch_diff')}",
        f"patch_apply_check_returncode: {(record.get('patch_trace') or {}).get('patch_apply_check', {}).get('returncode')}",
        f"patch_apply_returncode: {(record.get('patch_trace') or {}).get('patch_apply_result', {}).get('returncode')}",
        f"semantic_patch_validation_strength: {(record.get('patch_trace') or {}).get('semantic_patch_validation_strength')}",
        "",
        "PHASE_EVIDENCE",
    ]
    for phase in ["before", "before_plus_patch", "after"]:
        pr = phases[phase]
        lines.extend(
            [
                f"[{phase}] status={pr.get('status')} returncode={pr.get('returncode')}",
                f"[{phase}] command={compact(pr.get('command'), 300)}",
                f"[{phase}] stdout={compact(pr.get('stdout_excerpt'), 500)}",
                f"[{phase}] stderr={compact(pr.get('stderr_excerpt'), 500)}",
            ]
        )
    lines.append("")
    lines.append("CANDIDATES")
    for opt in options:
        lines.append(f"{opt['label']}: role={opt['semantic_role']}; value={opt['value']}")
    lines.extend(["", "QUESTION", "Return only the option label."])
    return "\n".join(lines)


def judgment(record: dict[str, Any]) -> str:
    strength = str((record.get("patch_trace") or {}).get("semantic_patch_validation_strength") or "")
    transition = str(record.get("verifier_transition") or "")
    if "downgraded" in strength or transition == "TEST_ADDED_OR_VERIFIER_NOT_COMPARABLE":
        return "TEST_ADDED_NOT_COMPARABLE"
    if "weak" in strength:
        return "WEAK_UNRELATED_VERIFIER"
    if transition == "FAIL_TO_PASS":
        return "DIRECT_FIX"
    if transition == "PASS_TO_PASS":
        return "PASS_TO_PASS_SAFE_REFACTOR"
    return "REJECT"


def allowed_projections(record: dict[str, Any], source_kind: str) -> list[str]:
    j = judgment(record)
    if source_kind == "downgraded":
        return ["patch_judgment"]
    if j == "WEAK_UNRELATED_VERIFIER":
        return ["patch_apply"]
    return ["patch_apply", "verifier_transition", "stop_continue", "next_action", "patch_judgment"]


def projection_spec(record: dict[str, Any], projection: str) -> tuple[list[dict[str, Any]], str]:
    transition = str(record.get("verifier_transition") or "")
    if projection == "patch_apply":
        values = [
            ("PATCH_APPLIES_CLEANLY", "patch_apply_success"),
            ("PATCH_DOES_NOT_APPLY", "patch_apply_failure"),
            ("ABSTAIN_PATCH_APPLY_UNKNOWN", "insufficient_patch_apply_evidence"),
        ]
        target = "PATCH_APPLIES_CLEANLY"
    elif projection == "verifier_transition":
        values = [
            ("FAIL_TO_PASS", "repair_transition"),
            ("PASS_TO_PASS", "safe_or_unrelated_pass_transition"),
            ("TEST_ADDED_OR_VERIFIER_NOT_COMPARABLE", "not_comparable"),
            ("ENV_BLOCKED", "environment_blocked"),
        ]
        target = transition
    elif projection == "stop_continue":
        values = [
            ("STOP_VERIFIED_DIRECT_FIX", "stop_after_direct_fix"),
            ("CONTINUE_WEAK_OR_PASS_TO_PASS", "continue_after_weak_or_nonrepair_evidence"),
            ("ABSTAIN_NOT_COMPARABLE", "abstain_not_comparable"),
        ]
        j = judgment(record)
        target = "STOP_VERIFIED_DIRECT_FIX" if j == "DIRECT_FIX" else ("ABSTAIN_NOT_COMPARABLE" if j == "TEST_ADDED_NOT_COMPARABLE" else "CONTINUE_WEAK_OR_PASS_TO_PASS")
    elif projection == "next_action":
        values = [
            ("RUN_BEFORE_PLUS_PATCH_VERIFIER", "verify_patch_candidate"),
            ("CLAIM_REPAIR_NOW", "premature_claim"),
            ("ABSTAIN_ENV_BLOCKED", "abstain_environment"),
        ]
        target = "RUN_BEFORE_PLUS_PATCH_VERIFIER"
    elif projection == "patch_judgment":
        values = [
            ("DIRECT_FIX", "direct_behavior_repair"),
            ("PASS_TO_PASS_SAFE_REFACTOR", "safe_replay_nonrepair"),
            ("WEAK_UNRELATED_VERIFIER", "weak_verifier"),
            ("TEST_ADDED_NOT_COMPARABLE", "test_added_shortcut"),
            ("REJECT", "reject_patch_trace"),
        ]
        target = judgment(record)
    else:
        raise ValueError(projection)
    options = option_rows(values)
    label = set_target(options, target)
    if not label:
        raise ValueError(f"target {target} missing from options for {projection}")
    return options, target


def build_row(record: dict[str, Any], projection: str, source_kind: str) -> dict[str, Any]:
    options, target = projection_spec(record, projection)
    prompt = render(record, projection, options)
    row_id = sid("stage12228_row", record.get("episode_id"), projection, target)
    label = next(opt["label"] for opt in options if opt["is_target"])
    state_after = dict(record.get("state_after") or {})
    state_after["verifier_transition"] = str(record.get("verifier_transition") or target)
    return {
        "row_id": row_id,
        "source_record_id": str(record.get("episode_id")),
        "episode_id": str(record.get("episode_id")),
        "root_id": str(record.get("root_id")),
        "repo_family": str(record.get("repo_family")),
        "language_family": str(record.get("language_family")),
        "split": "train_support",
        "projection_family": projection,
        "task_type": f"patch_trace_{projection}",
        "prompt_text": prompt,
        "input_text": prompt,
        "target": target,
        "decoder_text": label,
        "bounded_choice_target_label": label,
        "opaque_options": options,
        "standalone_projection_source": {"opaque_options": options},
        "state_before": record.get("state_before") or {},
        "state_before_plus_patch": {"phase": "before_plus_patch", "status": phase_status(record, "before_plus_patch")},
        "state_after": state_after,
        "ordered_events": record.get("ordered_events") or [],
        "patch_trace": record.get("patch_trace") or {},
        "verifier_result_by_phase": verifier_result_by_phase(record),
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "target_not_visible_before_options": True,
            "source_kind": source_kind,
            "semantic_qc_required": True,
        },
        "loss_mask": {
            "bounded_choice": False,
            "decoder_ce": False,
            "reason": "projection contract only; training blocked until supply floor and trainer task routing exist",
        },
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "training_allowed": False,
    }


def load_records() -> list[tuple[str, dict[str, Any]]]:
    records: list[tuple[str, dict[str, Any]]] = []
    for _, row in iter_jsonl(ADMITTED) or []:
        records.append(("admitted", row))
    for _, row in iter_jsonl(DOWNGRADED) or []:
        records.append(("downgraded", row))
    return records


def main() -> int:
    rows: list[dict[str, Any]] = []
    source_records = load_records()
    for source_kind, record in source_records:
        for projection in allowed_projections(record, source_kind):
            rows.append(build_row(record, projection, source_kind))

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "patch_trace_projection_rows.jsonl", rows)
    summary = {
        "stage": STAGE,
        "decision": "patch_trace_projection_rows_ready_training_blocked" if rows else "blocked_no_projection_rows",
        "source_stage": "stage12225_patch_trace_semantic_qc",
        "schema": str(SCHEMA),
        "source_record_count": len(source_records),
        "row_count": len(rows),
        "projection_counts": dict(Counter(r["projection_family"] for r in rows)),
        "task_type_counts": dict(Counter(r["task_type"] for r in rows)),
        "repo_family_counts": dict(Counter(r["repo_family"] for r in rows)),
        "language_counts": dict(Counter(r["language_family"] for r in rows)),
        "target_counts": dict(Counter(r["target"] for r in rows)),
        "training_allowed": False,
        "claim_boundary": "Projection contract rows only. Loss masks disabled until supply floor, QC, and trainer task routing are implemented.",
        "artifact_paths": {"rows": str(OUT / "patch_trace_projection_rows.jsonl")},
    }
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if rows else 2


if __name__ == "__main__":
    raise SystemExit(main())

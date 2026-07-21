#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12542_remaining_command_output_gap_feasibility_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12541_SUMMARY = ROOT / "runs/summaries/stage12541_command_log_no_test_insufficient_evidence_preflight.json"
STAGE12541_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12541_command_log_no_test_insufficient_evidence_preflight"
    / "stage12541_command_log_insufficient_evidence_preflight_rows.jsonl"
)
COMMAND_LOG_INDEX = ROOT / "runs/local/artifacts/stage12209_command_log_candidate_scanner/clean_candidate_command_logs.jsonl"

FEASIBILITY_ROWS_NAME = "stage12542_command_log_remaining_gap_feasibility_rows.jsonl"
WORKLIST_NAME = "stage12542_remaining_gap_worklist.jsonl"
AUDIT_NAME = "stage12542_remaining_command_output_gap_audit.json"

FIXTURE_RE = re.compile(r"^stage\d+_|controlled|fixture|mutation|probe|closure|materialization|transition_root", re.I)
NO_TEST_RE = re.compile(r"No tests were found|Total Tests:\s*0|collected 0 items|no tests collected|no tests ran", re.I)
SELECTED_RE = re.compile(r"--collect-only|\s-R\s|::|test_[A-Za-z0-9_./-]+\.py|selected", re.I)
FAIL_ENV_RE = re.compile(
    r"file or directory not found|offline mode|No tests|no tests|dependency|could not find|not found|ImportError|ModuleNotFound|timeout|timed out|network|lock file|resolution failures|unrecognized arguments|No such file",
    re.I,
)


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def sha256_text(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8", errors="replace")).hexdigest()


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                value["__line_no"] = line_no
                rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def risky_claims_false() -> dict[str, Any]:
    return {
        "training_allowed": False,
        "countable_train_support": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "level3_admitted": False,
        "level4_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
    }


def output_hash_from_index(row: dict[str, Any]) -> str:
    return stable_hash(
        {
            "returncode": row.get("returncode"),
            "stdout_tail_preview_hash": sha256_text(row.get("stdout_tail_preview")),
            "stderr_tail_preview_hash": sha256_text(row.get("stderr_tail_preview")),
        }
    )


def classify_command_log(row: dict[str, Any], prior_output_hashes: set[str]) -> dict[str, Any]:
    command = str(row.get("command") or "")
    output_text = "\n".join(str(row.get(key) or "") for key in ("stdout_tail_preview", "stderr_tail_preview"))
    repo_family = str(row.get("repo_family") or "")
    status = str(row.get("status") or "")
    out_hash = output_hash_from_index(row)
    reasons: list[str] = []
    potential_target = "none"

    if row.get("heldout_or_do_not_train_risk"):
        reasons.append("heldout_or_do_not_train_risk")
    if FIXTURE_RE.search(repo_family):
        reasons.append("fixture_or_stage_synthetic_repo_family")
    if SELECTED_RE.search(command) or "selected" in str(row.get("path") or "").lower():
        reasons.append("selected_or_exact_test_scope_not_source_expansion")
    if out_hash in prior_output_hashes:
        reasons.append("duplicate_of_stage12541_preflight_output")
    if status == "FAIL_CURRENT_STATE":
        potential_target = "FAIL_CURRENT_STATE"
        if FAIL_ENV_RE.search(output_text):
            reasons.append("fail_status_is_env_or_invalid_command_not_behavior_failure")
        else:
            reasons.append("fail_status_not_admissible_without_behavioral_or_build_failure_semantic_review")
    elif NO_TEST_RE.search(output_text):
        potential_target = "INSUFFICIENT_EVIDENCE"
        if not reasons:
            reasons.append("no_additional_nonduplicate_no_test_candidate_after_stage12541")
    else:
        reasons.append("not_remaining_target_family")

    return {
        "stage": STAGE,
        "record_type": "stage12542_command_log_remaining_gap_feasibility_row_v1",
        "source_line_hash": stable_hash({"source": str(COMMAND_LOG_INDEX), "line": row.get("__line_no")}),
        "source_record_hash": stable_hash(row),
        "repo_family_hash": stable_hash(repo_family),
        "language_family": row.get("language") or "unknown",
        "source_status": status,
        "potential_target_status": potential_target,
        "verifier_output_hash": out_hash,
        "feasibility": "blocked",
        "blocked_reasons": sorted(set(reasons)),
        **risky_claims_false(),
    }


def build_worklist(feasibility_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reason_counts = Counter(reason for row in feasibility_rows for reason in row.get("blocked_reasons", []))
    rows = [
        {
            "stage": STAGE,
            "record_type": "stage12542_remaining_gap_work_item_v1",
            "priority": 1,
            "blocker_reason": "target_status_shortfall_after_stage12542_feasibility_audit",
            "target_status": "FAIL_CURRENT_STATE",
            "minimum_new_rows_needed": 1,
            "recommended_next_action": "Execute or mine one non-selected, non-fixture behavioral/build failure with direct command output; reject missing-file, offline dependency, timeout, selected-test, and stage-synthetic failures.",
            **risky_claims_false(),
        },
        {
            "stage": STAGE,
            "record_type": "stage12542_remaining_gap_work_item_v1",
            "priority": 2,
            "blocker_reason": "target_status_shortfall_after_stage12542_feasibility_audit",
            "target_status": "INSUFFICIENT_EVIDENCE",
            "minimum_new_rows_needed": 1,
            "recommended_next_action": "Find one more non-selected, non-fixture no-test/zero-test command-output observation not duplicating Stage12541 output.",
            **risky_claims_false(),
        },
    ]
    priority = 3
    for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0])):
        rows.append(
            {
                "stage": STAGE,
                "record_type": "stage12542_remaining_gap_work_item_v1",
                "priority": priority,
                "blocker_reason": reason,
                "blocked_row_count": count,
                "recommended_next_action": "Do not relax this gate; acquire new direct command-output evidence instead.",
                **risky_claims_false(),
            }
        )
        priority += 1
    return rows


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12541_summary = read_json(STAGE12541_SUMMARY)
    stage12541_rows = read_jsonl(STAGE12541_ROWS)
    prior_outputs = {str(row.get("verifier_output_hash")) for row in stage12541_rows if row.get("verifier_output_hash")}
    command_logs = read_jsonl(COMMAND_LOG_INDEX)
    feasibility_rows = [classify_command_log(row, prior_outputs) for row in command_logs]
    relevant = [row for row in feasibility_rows if row["potential_target_status"] in {"FAIL_CURRENT_STATE", "INSUFFICIENT_EVIDENCE"}]
    worklist = build_worklist(relevant)

    feasibility_path = OUT / FEASIBILITY_ROWS_NAME
    worklist_path = OUT / WORKLIST_NAME
    audit_path = OUT / AUDIT_NAME
    write_jsonl(feasibility_path, relevant)
    write_jsonl(worklist_path, worklist)

    potential_counts = Counter(row["potential_target_status"] for row in relevant)
    reason_counts = Counter(reason for row in relevant for reason in row.get("blocked_reasons", []))
    audit = {
        "stage": STAGE,
        "record_type": "stage12542_remaining_gap_feasibility_audit_v1",
        "input_hashes": {
            "stage12541_summary": file_hash(STAGE12541_SUMMARY),
            "stage12541_rows": file_hash(STAGE12541_ROWS),
            "stage12209_clean_command_logs": file_hash(COMMAND_LOG_INDEX),
        },
        "stage12541_remaining_shortfall": stage12541_summary.get("remaining_shortfall_after_stage12541"),
        "command_log_rows_scanned": len(command_logs),
        "remaining_target_family_rows_reviewed": len(relevant),
        "potential_target_counts_before_blockers": dict(sorted(potential_counts.items())),
        "admissible_new_preflight_rows": 0,
        "blocked_reason_counts": dict(sorted(reason_counts.items())),
        **risky_claims_false(),
    }
    write_json(audit_path, audit)

    summary = {
        "stage": STAGE,
        "record_type": "stage12542_remaining_command_output_gap_summary_v1",
        "decision": "worklist_only_no_additional_safe_command_log_preflight_rows",
        "claim_boundary": "Stage12542 audits remaining command-log source feasibility only. It emits no preflight rows, no countable support, and no training/Level3/repair/source-heldout progress claim.",
        "stage12541_remaining_shortfall": stage12541_summary.get("remaining_shortfall_after_stage12541"),
        "new_preflight_row_count": 0,
        "remaining_shortfall_after_stage12542": {"FAIL_CURRENT_STATE": 1, "INSUFFICIENT_EVIDENCE": 1},
        "remaining_target_family_rows_reviewed": len(relevant),
        "potential_target_counts_before_blockers": dict(sorted(potential_counts.items())),
        "blocked_reason_counts": dict(sorted(reason_counts.items())),
        "worklist_row_count": len(worklist),
        **risky_claims_false(),
        "new_countable_train_support_count": 0,
        "artifact_refs": {
            "feasibility_rows": str(feasibility_path.relative_to(ROOT)),
            "worklist": str(worklist_path.relative_to(ROOT)),
            "audit": str(audit_path.relative_to(ROOT)),
            "summary": str(SUMMARY.relative_to(ROOT)),
        },
    }
    write_json(SUMMARY, summary)
    return summary


if __name__ == "__main__":
    build()

#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12541_command_log_no_test_insufficient_evidence_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12540_SUMMARY = ROOT / "runs/summaries/stage12540_command_output_verifier_observation_preflight_rows.json"
STAGE12540_WORKLIST = (
    ROOT
    / "runs/local/artifacts/stage12540_command_output_verifier_observation_preflight_rows"
    / "stage12540_remaining_materialization_worklist.jsonl"
)
STAGE12537_CANDIDATES = (
    ROOT
    / "runs/local/artifacts/stage12537_command_output_verifier_observation_materialization_preflight"
    / "real_command_output_verifier_observation_candidate_rows.jsonl"
)
COMMAND_LOG_INDEX = ROOT / "runs/local/artifacts/stage12209_command_log_candidate_scanner/clean_candidate_command_logs.jsonl"

PREFLIGHT_ROWS_NAME = "stage12541_command_log_insufficient_evidence_preflight_rows.jsonl"
BLOCKED_ROWS_NAME = "stage12541_blocked_command_log_rows.jsonl"
WORKLIST_NAME = "stage12541_remaining_source_expansion_worklist.jsonl"
AUDIT_NAME = "stage12541_command_log_source_audit.json"

TARGET = "INSUFFICIENT_EVIDENCE"
TARGET_BINDING_CLASS = "target_semantic_value_from_zero_test_or_no_test_command_output"
DIRECT_TARGETS = {"PASS_CURRENT_STATE", "FAIL_CURRENT_STATE", "INSUFFICIENT_EVIDENCE"}
FIXTURE_RE = re.compile(r"^stage\d+_|controlled|fixture|mutation|probe|closure|materialization|transition_root", re.I)
NO_TEST_RE = re.compile(r"No tests were found|Total Tests:\s*0|collected 0 items|no tests collected|no tests ran", re.I)
SELECTED_RE = re.compile(r"--collect-only|\s-R\s|::|test_[A-Za-z0-9_./-]+\.py|selected", re.I)
FAIL_ENV_RE = re.compile(
    r"file or directory not found|offline mode|No tests|no tests|dependency|could not find|not found|ImportError|ModuleNotFound|timeout|timed out|network|lock file|resolution failures|unrecognized arguments",
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


def target_shortfall() -> dict[str, int]:
    rows = read_jsonl(STAGE12540_WORKLIST)
    out: dict[str, int] = {}
    for row in rows:
        if row.get("blocker_reason") != "target_status_shortfall_after_stage12540_materialization":
            continue
        target = str(row.get("target_status") or "")
        if target in DIRECT_TARGETS:
            out[target] = int(row.get("minimum_new_rows_needed") or 0)
    return out or {"FAIL_CURRENT_STATE": 1, "INSUFFICIENT_EVIDENCE": 2}


def load_command_log(index_row: dict[str, Any]) -> dict[str, Any]:
    rel = str(index_row.get("path") or "")
    path = ROOT / rel
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    return value if isinstance(value, dict) else {}


def command_text_from(log: dict[str, Any], index_row: dict[str, Any]) -> str:
    value = log.get("command_text") or index_row.get("command") or log.get("command")
    if isinstance(value, list):
        return " ".join(str(part) for part in value)
    return str(value or "")


def output_text_from(log: dict[str, Any], index_row: dict[str, Any]) -> str:
    return "\n".join(
        str(value or "")
        for value in (
            log.get("stdout_tail"),
            log.get("stderr_tail"),
            index_row.get("stdout_tail_preview"),
            index_row.get("stderr_tail_preview"),
        )
    )


def blocked_row(index_row: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "record_type": "stage12541_blocked_command_log_row_v1",
        "source_line_hash": stable_hash({"source": str(COMMAND_LOG_INDEX), "line": index_row.get("__line_no")}),
        "source_record_hash": stable_hash(index_row),
        "repo_family_hash": stable_hash(index_row.get("repo_family")),
        "language_family": index_row.get("language") or "unknown",
        "blocked_reasons": sorted(set(reasons)),
        "candidate_row_emitted": False,
        **risky_claims_false(),
    }


def candidate_from_command_log(index_row: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    reasons: list[str] = []
    repo_family = str(index_row.get("repo_family") or "")
    command = str(index_row.get("command") or "")
    path = ROOT / str(index_row.get("path") or "")
    log = load_command_log(index_row)
    command_text = command_text_from(log, index_row)
    output_text = output_text_from(log, index_row)
    status = str(index_row.get("status") or "")

    if index_row.get("heldout_or_do_not_train_risk"):
        reasons.append("heldout_or_do_not_train_risk")
    if FIXTURE_RE.search(repo_family):
        reasons.append("fixture_or_stage_synthetic_repo_family")
    if not path.exists():
        reasons.append("command_log_file_missing")
    if not NO_TEST_RE.search(output_text):
        reasons.append("not_zero_test_or_no_test_observation")
    if SELECTED_RE.search(command) or SELECTED_RE.search(command_text) or "selected" in str(index_row.get("path") or "").lower():
        reasons.append("selected_or_exact_test_scope_not_source_expansion")
    if status == "FAIL_CURRENT_STATE" and FAIL_ENV_RE.search(output_text):
        reasons.append("fail_status_is_env_or_invalid_command_not_behavior_failure")
    if status not in {"PASS_CURRENT_STATE", "FAIL_CURRENT_STATE"}:
        reasons.append("unsupported_source_status")

    if reasons:
        return None, blocked_row(index_row, reasons)

    stdout_hash = sha256_text(log.get("stdout_tail") or index_row.get("stdout_tail_preview"))
    stderr_hash = sha256_text(log.get("stderr_tail") or index_row.get("stderr_tail_preview"))
    returncode = log.get("exit_code", index_row.get("returncode"))
    source_stage = "stage12209_command_log_candidate_scanner_clean_logs"
    join_hash = stable_hash(
        {
            "source_stage": source_stage,
            "command_log_path_hash": file_hash(path),
            "repo_family": repo_family,
            "command_text_hash": sha256_text(command_text),
            "cwd_hash": sha256_text(log.get("cwd")),
            "returncode": returncode,
            "stdout_hash": stdout_hash,
            "stderr_hash": stderr_hash,
            "target": TARGET,
        }
    )
    row = {
        "stage": STAGE,
        "record_type": "stage12541_command_log_insufficient_evidence_preflight_row_v1",
        "candidate_ref_hash": stable_hash({"source_line": index_row.get("__line_no"), "join": join_hash}),
        "source_stage": source_stage,
        "source_artifact_hash": file_hash(path),
        "source_line_hash": stable_hash({"source": str(COMMAND_LOG_INDEX), "line": index_row.get("__line_no")}),
        "root_lineage_key_hash": stable_hash({"repo_family": repo_family, "cwd": log.get("cwd"), "queue_id": log.get("queue_id")}),
        "repo_family_hash": stable_hash(repo_family),
        "language_family": index_row.get("language") or log.get("language") or "unknown",
        "task_projection": "transition_verifier_transition",
        "target_semantic_value": TARGET,
        "verifier_status": TARGET,
        "actual_verifier_command_output_observation_provenance": True,
        "verifier_command_ref_hash": stable_hash({"command_text_hash": sha256_text(command_text), "cwd_hash": sha256_text(log.get("cwd"))}),
        "command_result_id_hash": stable_hash({"path": str(index_row.get("path")), "label": log.get("label"), "queue_id": log.get("queue_id")}),
        "verifier_exit_status_class": "exit_zero" if int(returncode or 0) == 0 else "exit_nonzero",
        "verifier_stdout_hash": stdout_hash,
        "verifier_stderr_hash": stderr_hash,
        "verifier_output_hash": stable_hash({"returncode": returncode, "stdout_hash": stdout_hash, "stderr_hash": stderr_hash}),
        "verifier_observation_hash": stable_hash({"no_test_observation": True, "output_hashes": [stdout_hash, stderr_hash]}),
        "command_observation_join_hash": join_hash,
        "command_observation_join_hash_rule": "sha256_stage12541_command_log_path_command_output_zero_test_status_to_24hex",
        "target_binding_class": TARGET_BINDING_CLASS,
        "target_binding_rule_id_hash": stable_hash({"rule": TARGET_BINDING_CLASS, "target": TARGET}),
        "source_lineage_checked": True,
        "hydratable_verifier_observation_candidate": True,
        "controlled_fixture_like": False,
        "selected_test_scope_policy": "non_selected_test_source_scope",
        "selected_test_scope_materialization_allowed": True,
        "materialization_scope": "stage12541_preflight_only",
        **risky_claims_false(),
    }
    return row, None


def collapse_duplicate_outputs(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get("verifier_output_hash") or "")].append(row)
    accepted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    same_target_collapsed = 0
    for _, group in groups.items():
        ordered = sorted(group, key=lambda row: str(row.get("candidate_ref_hash")))
        accepted.append(ordered[0])
        for row in ordered[1:]:
            same_target_collapsed += 1
            blocked.append(
                {
                    "stage": STAGE,
                    "record_type": "stage12541_blocked_command_log_row_v1",
                    "candidate_ref_hash": row.get("candidate_ref_hash"),
                    "source_line_hash": row.get("source_line_hash"),
                    "repo_family_hash": row.get("repo_family_hash"),
                    "language_family": row.get("language_family"),
                    "blocked_reasons": ["duplicate_verifier_output_hash_collapsed_same_target"],
                    **risky_claims_false(),
                }
            )
    return accepted, blocked, {"duplicate_same_target_output_rows_collapsed": same_target_collapsed}


def select_to_shortfall(rows: list[dict[str, Any]], shortfall: dict[str, int]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    needed = int(shortfall.get(TARGET, 0))
    selected = sorted(rows, key=lambda row: (str(row.get("language_family")), str(row.get("repo_family_hash"))))[:needed]
    selected_refs = {row.get("candidate_ref_hash") for row in selected}
    blocked = [
        {
            "stage": STAGE,
            "record_type": "stage12541_blocked_command_log_row_v1",
            "candidate_ref_hash": row.get("candidate_ref_hash"),
            "source_line_hash": row.get("source_line_hash"),
            "repo_family_hash": row.get("repo_family_hash"),
            "language_family": row.get("language_family"),
            "blocked_reasons": ["above_stage12540_insufficient_evidence_shortfall_not_materialized"],
            **risky_claims_false(),
        }
        for row in rows
        if row.get("candidate_ref_hash") not in selected_refs
    ]
    return selected, blocked, {"selected_target_counts": {TARGET: len(selected)} if selected else {}, "remaining_shortfall": {TARGET: max(0, needed - len(selected))}}


def build_worklist(shortfall: dict[str, int], selection_audit: dict[str, Any], blocked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    priority = 1
    remaining_fail = int(shortfall.get("FAIL_CURRENT_STATE", 0))
    if remaining_fail:
        rows.append({
            "stage": STAGE,
            "record_type": "stage12541_remaining_source_expansion_work_item_v1",
            "priority": priority,
            "blocker_reason": "target_status_shortfall_after_stage12541_materialization",
            "target_status": "FAIL_CURRENT_STATE",
            "minimum_new_rows_needed": remaining_fail,
            "recommended_next_action": "Execute or mine non-selected, non-fixture behavioral/build failure command logs; env, missing-file, offline dependency, and selected-test failures stay blocked.",
            **risky_claims_false(),
        })
        priority += 1
    for target, missing in sorted(selection_audit.get("remaining_shortfall", {}).items()):
        if missing:
            rows.append({
                "stage": STAGE,
                "record_type": "stage12541_remaining_source_expansion_work_item_v1",
                "priority": priority,
                "blocker_reason": "target_status_shortfall_after_stage12541_materialization",
                "target_status": target,
                "minimum_new_rows_needed": missing,
                "recommended_next_action": "Find additional non-selected zero-test/no-test command-output observations with source-bound log hashes.",
                **risky_claims_false(),
            })
            priority += 1
    for reason, count in sorted(Counter(r for row in blocked for r in row.get("blocked_reasons", [])).items(), key=lambda x: (-x[1], x[0])):
        rows.append({
            "stage": STAGE,
            "record_type": "stage12541_remaining_source_expansion_work_item_v1",
            "priority": priority,
            "blocker_reason": reason,
            "blocked_row_count": count,
            "recommended_next_action": "Keep blocked unless the source can be re-executed or reclassified under direct non-selected command-output provenance.",
            **risky_claims_false(),
        })
        priority += 1
    return rows


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    shortfall = target_shortfall()
    raw_rows = read_jsonl(COMMAND_LOG_INDEX)
    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for row in raw_rows:
        candidate, blocker = candidate_from_command_log(row)
        if candidate:
            candidates.append(candidate)
        if blocker:
            blocked.append(blocker)
    collapsed, duplicate_blocked, duplicate_audit = collapse_duplicate_outputs(candidates)
    blocked.extend(duplicate_blocked)
    selected, excess_blocked, selection_audit = select_to_shortfall(collapsed, shortfall)
    blocked.extend(excess_blocked)
    worklist = build_worklist(shortfall, selection_audit, blocked)

    rows_path = OUT / PREFLIGHT_ROWS_NAME
    blocked_path = OUT / BLOCKED_ROWS_NAME
    worklist_path = OUT / WORKLIST_NAME
    audit_path = OUT / AUDIT_NAME
    write_jsonl(rows_path, selected)
    write_jsonl(blocked_path, blocked)
    write_jsonl(worklist_path, worklist)

    status_counts = Counter(row.get("target_semantic_value") for row in selected)
    blocked_counts = Counter(reason for row in blocked for reason in row.get("blocked_reasons", []))
    input_hashes = {
        "stage12540_summary": file_hash(STAGE12540_SUMMARY),
        "stage12540_worklist": file_hash(STAGE12540_WORKLIST),
        "stage12537_candidates": file_hash(STAGE12537_CANDIDATES),
        "stage12209_clean_command_logs": file_hash(COMMAND_LOG_INDEX),
    }
    audit = {
        "stage": STAGE,
        "record_type": "stage12541_command_log_source_audit_v1",
        "input_hashes": input_hashes,
        "stage12540_target_shortfall": shortfall,
        "raw_command_log_rows_scanned": len(raw_rows),
        "candidate_rows_before_duplicate_collapse": len(candidates),
        "candidate_rows_after_duplicate_collapse": len(collapsed),
        "selected_preflight_rows": len(selected),
        "blocked_rows": len(blocked),
        "duplicate_output_audit": duplicate_audit,
        "selection_audit": selection_audit,
        "blocked_reason_counts": dict(sorted(blocked_counts.items())),
        **risky_claims_false(),
    }
    write_json(audit_path, audit)

    summary = {
        "stage": STAGE,
        "record_type": "stage12541_command_log_no_test_preflight_summary_v1",
        "decision": "partial_insufficient_evidence_preflight_rows_materialized_training_blocked" if selected else "worklist_only_no_command_log_rows_materialized",
        "claim_boundary": "Stage12541 emits only sanitized preflight verifier-observation rows from command logs. It admits no countable support and makes no training, Level3, patch, repair, strict-eval, source-heldout, or model progress claim.",
        "stage12540_target_shortfall": shortfall,
        "preflight_row_count": len(selected),
        "preflight_status_counts": dict(sorted(status_counts.items())),
        "shortfall_satisfied_by_preflight_rows": all(status_counts.get(t, 0) >= n for t, n in shortfall.items()),
        "remaining_shortfall_after_stage12541": {"FAIL_CURRENT_STATE": int(shortfall.get("FAIL_CURRENT_STATE", 0)), **selection_audit.get("remaining_shortfall", {})},
        "worklist_row_count": len(worklist),
        "blocked_candidate_row_count": len(blocked),
        "command_observation_join_hash_present_on_all_rows": all(bool(row.get("command_observation_join_hash")) for row in selected),
        "selected_test_scope_rows": sum(1 for row in selected if str(row.get("selected_test_scope_policy", "")).startswith("selected_test")),
        "controlled_fixture_like_rows": sum(1 for row in selected if row.get("controlled_fixture_like") is True),
        **risky_claims_false(),
        "new_countable_train_support_count": 0,
        "artifact_refs": {
            "preflight_rows": str(rows_path.relative_to(ROOT)),
            "blocked_rows": str(blocked_path.relative_to(ROOT)),
            "worklist": str(worklist_path.relative_to(ROOT)),
            "audit": str(audit_path.relative_to(ROOT)),
            "summary": str(SUMMARY.relative_to(ROOT)),
        },
        "input_hashes": input_hashes,
    }
    write_json(SUMMARY, summary)
    return summary


def main() -> None:
    build()


if __name__ == "__main__":
    main()

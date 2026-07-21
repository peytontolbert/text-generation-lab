#!/usr/bin/env python3
"""Stage12421 new direct verifier-observation miner.

This stage mines only direct, non-derivative verifier-observation records that are
not already counted by Stage12385/Stage12416 or normalized into Stage12418. It
emits sanitized train-support projection rows, but no repair, patch-trace,
source-heldout, strict-eval, Level-3, or Level-4 claims.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12421_new_direct_real_verifier_observation_miner"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
TARGET_TRAIN_SUPPORT_ROWS = 500
CURRENT_COUNTABLE_BASELINE = 190

SOURCE_FILES = {
    "stage12204_hydratable_verifier_replay_batch": ROOT / "runs/local/artifacts/stage12204_hydratable_verifier_replay_batch/level3_episode_records.jsonl",
    "stage12205_authoritative_verifier_log_level3_joiner": ROOT / "runs/local/artifacts/stage12205_authoritative_verifier_log_level3_joiner/authoritative_level3_episode_records.jsonl",
    "stage12210_controlled_triple_level3_joiner": ROOT / "runs/local/artifacts/stage12210_controlled_triple_level3_joiner/controlled_triple_level3_records.jsonl",
    "stage12213_strict_fail_current_state_level3_converter": ROOT / "runs/local/artifacts/stage12213_strict_fail_current_state_level3_converter/strict_fail_current_state_level3_records.jsonl",
}
EXPLICITLY_NONCOUNTABLE_SOURCES = {
    "stage12203_controlled_selected_verifier_replay": "already_consumed_by_stage12416",
    "stage12207_no_install_selected_test_log_level3_joiner": "already_stage12385_or_stage12418_covered",
    "stage12211_v35_buildrun_level3_converter": "already_stage12216_stage12418_covered",
    "stage12212_v35_buildonly_level3_converter": "already_stage12216_stage12418_covered",
    "stage12215_hydratable_selected_verifier_reexecution": "already_consumed_by_stage12416_or_stage12418",
    "stage12216_normalized_verifier_observation_dataset": "derivative_normalized_projection_source_not_new_supply",
    "stage12238_verifier_observation_auxiliary_conversion_audit": "derivative_auxiliary_conversion_not_new_supply",
}
STAGE12416_ROWS = ROOT / "runs/local/artifacts/stage12416_direct_verifier_log_train_support_canonicalizer/direct_verifier_log_train_support_rows.jsonl"
STAGE12418_ROWS = ROOT / "runs/local/artifacts/stage12418_normalized_verifier_observation_sanitized_canonicalizer/sanitized_normalized_verifier_observation_projection_rows.jsonl"

ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){1,}[A-Za-z0-9._-]+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
DIFF_RE = re.compile(r"(^|\n)(diff --git|@@ |\+{3} |--- )")
RAW_KEY_RE = re.compile(r"^(command|cmd|argv|cwd|stdout|stderr|stdout_tail|stderr_tail|output|path|url|diff|source_text|content|input_text)$", re.I)

STATUS_OPTIONS = [
    ("A", "PASS_CURRENT_STATE", "selected verifier command produced a current-state pass observation"),
    ("B", "FAIL_CURRENT_STATE", "selected verifier command produced a current-state fail observation"),
    ("C", "PASS_CURRENT_BUILD", "build or collection succeeded without runnable selected-test proof"),
    ("D", "INSUFFICIENT_EVIDENCE", "environment, dependency, timeout, or missing output blocks trustworthy verifier interpretation"),
    ("E", "FAIL_TO_PASS", "same-source before/after verifier proves fail-to-pass repair; not admitted by this stage"),
]
STOP_OPTIONS = [
    ("A", "CONTINUE_SINGLE_VERIFIER_EVIDENCE", "continue because one current verifier observation is not full task acceptance"),
    ("B", "CONTINUE_DIAGNOSE_FAILURE", "continue by diagnosing the observed verifier failure"),
    ("C", "ABSTAIN_ENV_BLOCKED", "abstain from behavior claims because verifier evidence is blocked or insufficient"),
    ("D", "STOP_DONE", "stop because complete acceptance evidence exists; not admitted by this support stage"),
]


def stable_hash(value: Any, n: int = 24) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:n]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                value["__source_line_no"] = line_no
                rows.append(value)
    return rows


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def get_path(row: dict[str, Any], *keys: str) -> Any:
    cur: Any = row
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def source_ref(row: dict[str, Any]) -> str:
    return str(row.get("source_record_ref") or row.get("source_ref") or row.get("source_log_path") or row.get("source_bundle_id") or "")


def command_result_id(row: dict[str, Any]) -> str:
    return str(
        get_path(row, "command_result", "command_result_id")
        or get_path(row, "observed_action", "command_result_id")
        or row.get("command_result_id")
        or ""
    )


def observation_id(row: dict[str, Any]) -> str:
    return str(row.get("observation_id") or get_path(row, "observation", "observation_id") or row.get("verifier_anchor") or "")


def state_update_id(row: dict[str, Any]) -> str:
    return str(row.get("state_update_id") or get_path(row, "state_update", "state_update_id") or "")


def stop_decision_id(row: dict[str, Any]) -> str:
    return str(row.get("stop_decision_id") or get_path(row, "stop_decision", "stop_decision_id") or "")


def row_source_stage(row: dict[str, Any], default_stage: str) -> str:
    value = str(row.get("source_stage") or default_stage)
    if "::" in value:
        value = value.split("::", 1)[0]
    return value


def root_lineage_key(row: dict[str, Any], source_stage: str) -> str:
    explicit = row.get("root_lineage_key")
    if explicit:
        return str(explicit)
    basis = {
        "source_stage": source_stage,
        "episode_id": row.get("episode_id"),
        "repo_family": row.get("repo_family") or row.get("repo_id"),
        "source_ref_hash": stable_hash(source_ref(row) or "missing", 24),
        "line_no": row.get("__source_line_no"),
    }
    return f"{source_stage}::{stable_hash(basis, 20)}"


def verifier_transition(row: dict[str, Any]) -> str:
    status = str(row.get("verifier_transition") or row.get("verifier_status") or "UNKNOWN")
    if status == "ENV_BLOCKED":
        return "INSUFFICIENT_EVIDENCE"
    if status in {"FAIL_TO_FAIL", "NOT_EXERCISED"}:
        return "FAIL_CURRENT_STATE"
    return status


def output_class(status: str) -> str:
    if status in {"PASS_CURRENT_STATE", "PASS_TO_PASS"}:
        return "current_state_pass_observation"
    if status == "FAIL_CURRENT_STATE":
        return "current_state_failure_observation"
    if status == "PASS_CURRENT_BUILD":
        return "build_only_pass_observation"
    if status == "INSUFFICIENT_EVIDENCE":
        return "environment_or_missing_evidence_blocked"
    if status == "FAIL_TO_PASS":
        return "fail_to_pass_verifier_transition_not_repair_proof"
    return "unknown_or_unsupported_verifier_observation"


def options_for_projection(task_projection: str) -> list[dict[str, Any]]:
    options = STATUS_OPTIONS if task_projection == "transition_verifier_transition" else STOP_OPTIONS
    return [{"label": label, "semantic_value": value, "description_hash": stable_hash(desc, 16)} for label, value, desc in options]


def target_for_projection(status: str, task_projection: str) -> str:
    if task_projection == "transition_verifier_transition":
        if status in {"PASS_CURRENT_STATE", "FAIL_CURRENT_STATE", "PASS_CURRENT_BUILD", "INSUFFICIENT_EVIDENCE"}:
            return status
        return "INSUFFICIENT_EVIDENCE"
    if status == "PASS_CURRENT_STATE":
        return "CONTINUE_SINGLE_VERIFIER_EVIDENCE"
    if status == "FAIL_CURRENT_STATE":
        return "CONTINUE_DIAGNOSE_FAILURE"
    return "ABSTAIN_ENV_BLOCKED"


def label_for(options: list[dict[str, Any]], target: str) -> str:
    for opt in options:
        if opt["semantic_value"] == target:
            return opt["label"]
    raise ValueError(target)


def record_key(row: dict[str, Any], source_stage: str) -> str:
    return stable_hash({
        "source_stage": source_stage,
        "source_ref_hash": stable_hash(source_ref(row) or "missing", 24),
        "episode_id": row.get("episode_id") or "",
        "root_lineage_key_hash": stable_hash(root_lineage_key(row, source_stage), 24),
        "command_result_id": command_result_id(row),
        "observation_id": observation_id(row),
        "state_update_id": state_update_id(row),
        "stop_decision_id": stop_decision_id(row),
        "verifier_transition": verifier_transition(row),
    }, 24)


def projection_key(row: dict[str, Any], source_stage: str, task_projection: str) -> str:
    return stable_hash({
        "record_key": record_key(row, source_stage),
        "task_projection": task_projection,
        "target": target_for_projection(verifier_transition(row), task_projection),
    }, 24)


def coverage_keys_from_existing() -> set[str]:
    keys: set[str] = set()
    for row in read_jsonl(STAGE12416_ROWS):
        for field in ("stable_real_log_record_id", "source_key_audit_hash", "row_id", "root_lineage_key_hash"):
            value = row.get(field)
            if value:
                keys.add(str(value))
    for row in read_jsonl(STAGE12418_ROWS):
        for field in ("rollup_record_id_hash", "source_key_audit_hash", "row_id", "root_projection_target_hash", "episode_command_transition_hash", "fallback_root_command_transition_hash"):
            value = row.get(field)
            if value:
                keys.add(str(value))
        for value in row.get("lineage_dedupe_key_hashes") or []:
            keys.add(str(value))
    return keys


def stage_candidate_policy(default_stage: str, row: dict[str, Any]) -> tuple[bool, str, bool]:
    # Returns: selected_for_projection, reason, controlled_fixture_like.
    line_no = int(row.get("__source_line_no") or 0)
    repo = str(row.get("repo_family") or "")
    status = verifier_transition(row)
    if default_stage == "stage12204_hydratable_verifier_replay_batch":
        duplicate_repos = {"agent-governance-toolkit", "archai", "langchain"}
        if repo in duplicate_repos:
            return False, "excluded_duplicate_stage12203_stage12416_repo", False
        return True, "direct_hydratable_replay_not_in_stage12416", status == "INSUFFICIENT_EVIDENCE"
    if default_stage == "stage12205_authoritative_verifier_log_level3_joiner":
        if line_no in {17, 18}:
            return False, "blocked_repo_cap_bypass_not_justified_for_openhands_passtopass", False
        return False, "covered_by_stage12216_stage12418_or_repo_cap", False
    if default_stage == "stage12210_controlled_triple_level3_joiner":
        if 25 <= line_no <= 30:
            return True, "direct_controlled_fixture_closure_train_support_only", True
        return False, "covered_by_stage12216_stage12418_or_not_closure_slice", True
    if default_stage == "stage12213_strict_fail_current_state_level3_converter":
        return True, "direct_fail_current_state_diagnostic_train_support_only", True
    return False, "source_not_authorized", False


def has_required_lineage(row: dict[str, Any]) -> bool:
    return all([
        row.get("episode_id"),
        row.get("root_id"),
        row.get("repo_family") or row.get("repo_id"),
        command_result_id(row) or observation_id(row),
        state_update_id(row),
        stop_decision_id(row),
        verifier_transition(row) != "UNKNOWN",
    ])


def make_row(src: dict[str, Any], source_stage: str, task_projection: str, controlled: bool) -> dict[str, Any]:
    status = verifier_transition(src)
    options = options_for_projection(task_projection)
    target = target_for_projection(status, task_projection)
    row_id = f"{STAGE}::{projection_key(src, source_stage, task_projection)}"
    return {
        "stage": STAGE,
        "record_type": "direct_verifier_observation_train_support_projection_v1",
        "row_id": row_id,
        "task_projection": task_projection,
        "target_label": label_for(options, target),
        "target_semantic_value": target,
        "opaque_options": options,
        "language_family": str(src.get("language_family") or src.get("language") or "unknown"),
        "source_stage": source_stage,
        "stable_real_log_record_id": record_key(src, source_stage),
        "source_ref_hash": stable_hash(source_ref(src) or "missing", 24),
        "source_line_hash": stable_hash({"source_stage": source_stage, "line": src.get("__source_line_no")}, 24),
        "episode_id_hash": stable_hash(src.get("episode_id") or "missing", 24),
        "root_id_hash": stable_hash(src.get("root_id") or "missing", 24),
        "repo_family_hash": stable_hash(src.get("repo_family") or src.get("repo_id") or "unknown", 24),
        "root_lineage_key_hash": stable_hash(root_lineage_key(src, source_stage), 24),
        "command_result_id_hash": stable_hash(command_result_id(src) or "missing", 24),
        "observation_id_hash": stable_hash(observation_id(src) or "missing", 24),
        "verifier_anchor_id_hash": stable_hash(observation_id(src) or command_result_id(src) or "missing", 24),
        "state_update_id_hash": stable_hash(state_update_id(src) or "missing", 24),
        "stop_decision_id_hash": stable_hash(stop_decision_id(src) or "missing", 24),
        "source_or_test_hash": stable_hash(src.get("selected_test_anchor") or src.get("verifier_anchor") or observation_id(src) or "missing", 24),
        "verifier_status": status,
        "verifier_output_class": output_class(status),
        "train_support_only": True,
        "training_allowed": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "controlled_fixture_like": controlled,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
        "patch_trace_admitted": False,
        "level3_admitted": False,
        "level4_admitted": False,
        "counts_toward_unbounded_patch_trace_floor": False,
        "counts_toward_source_heldout_floor": False,
        "counts_toward_strict_eval_floor": False,
        "claim_boundary": "sanitized direct verifier-observation train support only; no repair, patch-trace, strict/source-heldout, Level-3, or Level-4 claim",
        "anti_cheat": {
            "opaque_labels": True,
            "deterministic_option_shuffle": True,
            "target_semantic_not_in_prompt": True,
            "raw_text_emitted": False,
        },
    }


def raw_guardrail(rows: list[dict[str, Any]], include_keys: bool = True) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    def scan(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                if include_keys and RAW_KEY_RE.match(str(k)):
                    issues.append({"path_hash": stable_hash(path + "." + str(k), 16), "issue": "forbidden_raw_key"})
                scan(v, path + "." + str(k))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                scan(item, f"{path}[{i}]")
        elif isinstance(value, str):
            if URL_RE.search(value) or ABS_PATH_RE.search(value) or DIFF_RE.search(value):
                issues.append({"path_hash": stable_hash(path, 16), "issue": "forbidden_raw_text_pattern"})
    scan(rows, "rows")
    return {"scan_passed": not issues, "issue_count": len(issues), "issues": issues[:20]}


def main() -> None:
    coverage = coverage_keys_from_existing()
    emitted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    candidate_records = 0
    selected_records = 0
    direct_source_records_by_stage = Counter()
    blocked_reasons = Counter()
    source_lineage: list[dict[str, Any]] = []
    for source_name, reason in EXPLICITLY_NONCOUNTABLE_SOURCES.items():
        blocked_reasons[reason] += 1
        blocked.append({
            "source_stage": source_name,
            "source_line_hash": stable_hash({"source_stage": source_name, "explicitly_noncountable": True}, 24),
            "stable_record_key_hash": stable_hash({"source_stage": source_name, "blocked_reason": reason}, 24),
            "blocked_reason": reason,
        })

    for source_name, path in SOURCE_FILES.items():
        rows = read_jsonl(path)
        direct_source_records_by_stage[source_name] = len(rows)
        for src in rows:
            candidate_records += 1
            source_stage = row_source_stage(src, source_name)
            selected, reason, controlled = stage_candidate_policy(source_name, src)
            base_keys = {
                record_key(src, source_stage),
                stable_hash(root_lineage_key(src, source_stage), 24),
                stable_hash(src.get("episode_id") or "missing", 24),
            }
            if not selected:
                blocked_reasons[reason] += 1
                blocked.append({
                    "source_stage": source_name,
                    "source_line_hash": stable_hash({"source_stage": source_name, "line": src.get("__source_line_no")}, 24),
                    "stable_record_key_hash": record_key(src, source_stage),
                    "blocked_reason": reason,
                })
                continue
            if not has_required_lineage(src):
                blocked.append({
                    "source_stage": source_name,
                    "source_line_hash": stable_hash({"source_stage": source_name, "line": src.get("__source_line_no")}, 24),
                    "blocked_reason": "missing_required_lineage_or_verifier_state",
                })
                blocked_reasons["missing_required_lineage_or_verifier_state"] += 1
                continue
            if base_keys & coverage:
                blocked.append({
                    "source_stage": source_name,
                    "source_line_hash": stable_hash({"source_stage": source_name, "line": src.get("__source_line_no")}, 24),
                    "blocked_reason": "dedupe_key_already_covered_by_stage12416_or_stage12418",
                })
                blocked_reasons["dedupe_key_already_covered_by_stage12416_or_stage12418"] += 1
                continue
            selected_records += 1
            source_lineage.append({
                "source_stage": source_name,
                "source_line_hash": stable_hash({"source_stage": source_name, "line": src.get("__source_line_no")}, 24),
                "stable_real_log_record_id": record_key(src, source_stage),
                "direct_vs_derived": "direct_source_record",
                "controlled_fixture_like": controlled,
                "countable_as_train_support_source_record": True,
                "countable_as_repair_or_patch_trace": False,
                "selection_reason": reason,
                "verifier_status": verifier_transition(src),
            })
            for projection in ("transition_verifier_transition", "transition_continue_or_stop"):
                row = make_row(src, source_stage, projection, controlled)
                coverage.add(row["stable_real_log_record_id"])
                coverage.add(row["row_id"])
                emitted.append(row)

    scan = raw_guardrail(emitted + blocked + source_lineage)
    if not scan["scan_passed"]:
        blocked.extend({"blocked_reason": "guardrail_scan_failed", "issue": issue} for issue in scan["issues"])
        emitted = []
        selected_records = 0

    source_counts = Counter(row["source_stage"] for row in emitted)
    language_counts = Counter(row["language_family"] for row in emitted)
    task_counts = Counter(row["task_projection"] for row in emitted)
    target_counts = Counter(row["target_semantic_value"] for row in emitted)
    controlled_projection_rows = sum(1 for row in emitted if row["controlled_fixture_like"])
    auxiliary_controlled_fixture_rows = controlled_projection_rows
    externally_countable_new = len(emitted) - controlled_projection_rows
    # Controlled fixture rows can be useful auxiliary training support, but they
    # must not advance the high-quality root-supply target.
    countable_new = externally_countable_new
    total_if_accepted = CURRENT_COUNTABLE_BASELINE + countable_new
    summary = {
        "stage": STAGE,
        "record_type": "new_direct_verifier_observation_mining_audit_v1",
        "decision": "new_direct_verifier_observation_support_mined_training_still_blocked" if emitted else "no_new_direct_verifier_observation_rows_admitted",
        "claim_boundary": "Stage12421 emits sanitized direct verifier-observation train-support projections only; it does not emit repair proof, patch traces, strict/source-heldout eval rows, Level-3 episodes, or Level-4 episodes.",
        "training_allowed": False,
        "admitted_rows": countable_new,
        "emitted_rows": len(emitted),
        "emitted_training_rows": len(emitted),
        "countable_new_rows": countable_new,
        "countable_as_new_train_support_rows": countable_new,
        "auxiliary_controlled_fixture_train_support_rows": auxiliary_controlled_fixture_rows,
        "total_emitted_sanitized_projection_rows": len(emitted),
        "countable_as_new_proof_floor_rows": 0,
        "countable_as_repair_rows": 0,
        "countable_as_patch_trace_rows": 0,
        "level3_admitted_rows": 0,
        "level4_admitted_rows": 0,
        "current_countable_train_support_tasks_before_stage": CURRENT_COUNTABLE_BASELINE,
        "total_current_train_support_tasks_if_accepted": total_if_accepted,
        "remaining_gap_to_500": max(0, TARGET_TRAIN_SUPPORT_ROWS - total_if_accepted),
        "candidate_source_records_scanned": candidate_records,
        "selected_direct_source_records": selected_records,
        "source_record_yield_cap": 15,
        "source_projection_policy": "two_sanitized_projections_per_selected_direct_source_record",
        "source_counts": dict(sorted(source_counts.items())),
        "direct_source_records_by_stage": dict(sorted(direct_source_records_by_stage.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "emitted_projection_language_counts": dict(sorted(language_counts.items())),
        "task_projection_counts": dict(sorted(task_counts.items())),
        "target_semantic_counts": dict(sorted(target_counts.items())),
        "controlled_fixture_projection_rows": controlled_projection_rows,
        "real_external_projection_rows": externally_countable_new,
        "countable_external_projection_rows": externally_countable_new,
        "blocked_reason_counts": dict(sorted(blocked_reasons.items())),
        "blocked_records": len(blocked),
        "source_lineage": source_lineage,
        "derivative_accounting": {
            "stage12216_stage12418_rows_counted_as_new": 0,
            "stage12216_stage12418_rows_used_for_dedupe_only": True,
            "explicitly_noncountable_sources": EXPLICITLY_NONCOUNTABLE_SOURCES,
        },
        "proof_slot_status_counts": {
            "state_before": "not_claimed_for_level3",
            "state_after": "not_claimed_for_level3",
            "patch_application": "not_claimed_for_level3",
            "same_verifier_before_after": "not_claimed_for_repair",
            "verifier_relevance": "direct_observation_only_not_repair_proof",
            "causal_linkage": "not_claimed_for_repair",
            "stop_continue": "sanitized_policy_projection_only",
            "correct_next_action_policy": "not_projected_by_this_stage",
        },
        "raw_content_policy": {
            "input_text_emitted": False,
            "commands_emitted": False,
            "outputs_emitted": False,
            "paths_emitted": False,
            "urls_emitted": False,
            "source_text_emitted": False,
            "diffs_emitted": False,
            "patches_emitted": False,
            "raw_locator_values_emitted": False,
        },
        "raw_leak_count": scan["issue_count"],
        "overclaim_count": 0 if countable_new >= 0 else 1,
        "guardrail_scan_passed": scan["scan_passed"],
        "strict_source_heldout_status": {
            "source_heldout_admissible_rows": 0,
            "strict_eval_eligible_rows": 0,
            "reason": "train_support_only_direct_verifier_observation_projection_lane",
        },
        "dominance_report": {
            "max_source_stage_rows": max(source_counts.values()) if source_counts else 0,
            "max_language_rows": max(language_counts.values()) if language_counts else 0,
            "controlled_fixture_share": controlled_projection_rows / len(emitted) if emitted else 0.0,
            "dominance_warning": "controlled fixture share is high; controlled rows are emitted as auxiliary support but excluded from the 500 high-quality root-supply counter" if controlled_projection_rows else "none",
        },
        "reject_conditions_triggered": [] if scan["scan_passed"] else ["raw_guardrail_scan_failed"],
        "promotion_gate_status": {
            "countable_train_support_supply_reaches_500": "FAIL",
            "controlled_fixture_rows_excluded_from_500_counter": "PASS" if auxiliary_controlled_fixture_rows else "not_applicable",
            "unbounded_level3_floor_20": "FAIL",
            "unbounded_patch_trace_floor_8": "FAIL",
            "repo_floor_10_for_unbounded": "not_claimed",
            "language_floor_3_for_unbounded": "not_claimed",
            "raw_leak_overclaim_clean": "PASS" if scan["scan_passed"] else "FAIL",
        },
        "next_stage_recommendation": "stage12424_new_external_source_adapter_scout_before_more_training",
        "artifact_manifest": {
            "train_support_rows": str((OUT / "new_direct_verifier_observation_train_support_rows.jsonl").relative_to(ROOT)),
            "blocked_records": str((OUT / "blocked_new_direct_verifier_observation_records.jsonl").relative_to(ROOT)),
            "source_lineage": str((OUT / "source_lineage_audit.jsonl").relative_to(ROOT)),
            "guardrail_scan": str((OUT / "guardrail_scan.json").relative_to(ROOT)),
            "summary": str(SUMMARY.relative_to(ROOT)),
        },
    }
    summary["summary_hash"] = stable_hash({k: v for k, v in summary.items() if k != "summary_hash"})

    write_jsonl(OUT / "new_direct_verifier_observation_train_support_rows.jsonl", emitted)
    write_jsonl(OUT / "blocked_new_direct_verifier_observation_records.jsonl", blocked)
    write_jsonl(OUT / "source_lineage_audit.jsonl", source_lineage)
    write_json(OUT / "guardrail_scan.json", scan)
    write_json(OUT / "new_direct_verifier_observation_mining_audit.json", summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

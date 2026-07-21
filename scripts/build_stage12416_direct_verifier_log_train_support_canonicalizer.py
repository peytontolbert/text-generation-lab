#!/usr/bin/env python3
"""Stage12416 direct verifier-log train-support canonicalizer.

This stage consumes only real verifier-log records from Stage12203/12207/12215
and emits safe train-support-only transition rows when the record is not already
covered by the Stage12385 selected-test ledger. It does not admit patch traces,
repair claims, source-heldout rows, or strict eval rows.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12416_direct_verifier_log_train_support_canonicalizer"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12385_ROWS = ROOT / "runs/local/artifacts/stage12385_combined_train_support_ledger_v15_dedup/combined_selected_test_rows_v15_dedup.jsonl"
STAGE12385_SUMMARY = ROOT / "runs/summaries/stage12385_combined_train_support_ledger_v15_dedup.json"
REAL_LOG_SOURCES = {
    "stage12203_controlled_selected_verifier_replay": ROOT / "runs/local/artifacts/stage12203_controlled_selected_verifier_replay/level3_episode_records.jsonl",
    "stage12207_no_install_selected_test_log_level3_joiner": ROOT / "runs/local/artifacts/stage12207_no_install_selected_test_log_level3_joiner/no_install_selected_test_level3_records.jsonl",
    "stage12215_hydratable_selected_verifier_reexecution": ROOT / "runs/local/artifacts/stage12215_hydratable_selected_verifier_reexecution/level3_reexecution_records.jsonl",
}

ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){1,}[A-Za-z0-9._-]+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
RAW_KEY_RE = re.compile(r"^(command|cmd|argv|cwd|stdout|stderr|stdout_tail|stderr_tail|output|path|url|diff|source_text|content)$", re.I)
COMMANDISH_RE = re.compile(r"\b(python|pytest|cargo|npm|yarn|pnpm|bash|sh|git)\b.+\s(-m|-q|test|run|checkout|diff)\b", re.I)
DIFF_RE = re.compile(r"(^|\n)(diff --git|@@ |\+{3} |--- )")

STATUS_OPTIONS = [
    ("A", "PASS_CURRENT_STATE", "selected verifier command executed and produced a current-state pass observation"),
    ("B", "FAIL_CURRENT_STATE", "selected verifier command executed and produced a current-state fail observation"),
    ("C", "PASS_CURRENT_BUILD", "build or collection succeeded but runnable selected verifier proof is incomplete"),
    ("D", "INSUFFICIENT_EVIDENCE", "environment, dependency, or missing output prevents trustworthy verifier interpretation"),
    ("E", "FAIL_TO_PASS", "same-source before/after verifier proves a repair changed fail to pass"),
]
STOP_OPTIONS = [
    ("A", "CONTINUE_SINGLE_VERIFIER_EVIDENCE", "continue because one selected verifier observation is not full task acceptance"),
    ("B", "CONTINUE_DIAGNOSE_FAILURE", "continue by diagnosing a current verifier failure"),
    ("C", "ABSTAIN_ENV_BLOCKED", "do not claim behavior when verifier evidence is environment-blocked or insufficient"),
    ("D", "STOP_DONE", "stop because full acceptance evidence is available"),
]
NEXT_ACTION_OPTIONS = [
    ("A", "RUN_SELECTED_VERIFIER", "run or preserve the selected verifier observation before stronger claims"),
    ("B", "DIAGNOSE_VERIFIER_FAILURE", "inspect failure evidence before patching or stopping"),
    ("C", "DIAGNOSE_ENVIRONMENT", "treat environment/dependency blockage as the next problem"),
    ("D", "PLAN_PATCH", "plan a patch before interpreting verifier status"),
    ("E", "FINISH", "declare task complete from this observation"),
]


def stable_hash(value: Any, n: int = 24) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
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


def get_path(row: dict[str, Any], *keys: str) -> Any:
    cur: Any = row
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def row_language(row: dict[str, Any]) -> str:
    return str(row.get("language_family") or row.get("language") or "unknown")


def command_result_id(row: dict[str, Any]) -> str:
    return str(
        get_path(row, "command_result", "command_result_id")
        or get_path(row, "observed_action", "command_result_id")
        or row.get("command_result_id")
        or ""
    )


def episode_id(row: dict[str, Any]) -> str:
    return str(row.get("episode_id") or "")


def observation_id(row: dict[str, Any]) -> str:
    return str(row.get("observation_id") or "")


def state_update_id(row: dict[str, Any]) -> str:
    return str(row.get("state_update_id") or get_path(row, "state_update", "state_update_id") or "")


def stop_decision_id(row: dict[str, Any]) -> str:
    return str(row.get("stop_decision_id") or get_path(row, "stop_decision", "stop_decision_id") or "")


def root_lineage_key(row: dict[str, Any], source_stage: str) -> str:
    explicit = row.get("root_lineage_key")
    if explicit:
        return str(explicit)
    basis = {
        "source_stage": source_stage,
        "episode_id": episode_id(row),
        "repo_family": row.get("repo_family") or row.get("repo_id"),
        "source_record_ref": row.get("source_record_ref") or row.get("source_ref"),
        "selected": row.get("selected_test_anchor") or row.get("verifier_anchor"),
    }
    return f"{source_stage}::{stable_hash(basis, 20)}"


def verifier_status(row: dict[str, Any]) -> str:
    status = str(row.get("verifier_status") or row.get("verifier_transition") or "UNKNOWN")
    if status == "ENV_BLOCKED":
        return "INSUFFICIENT_EVIDENCE"
    return status


def output_class(row: dict[str, Any]) -> str:
    status = verifier_status(row)
    rc = get_path(row, "command_result", "returncode")
    if status in {"PASS_CURRENT_STATE", "PASS_TO_PASS"}:
        return "exit_zero_selected_verifier_pass"
    if status in {"FAIL_CURRENT_STATE", "FAIL_TO_FAIL", "NOT_EXERCISED"}:
        return "exit_nonzero_or_not_exercised"
    if status in {"INSUFFICIENT_EVIDENCE", "ENV_BLOCKED"}:
        return "environment_or_dependency_blocked"
    if rc == 0:
        return "exit_zero_status_uncertain"
    if isinstance(rc, int):
        return "nonzero_status_uncertain"
    return "unknown_output_class"


def selected_anchor_hash(row: dict[str, Any]) -> str:
    anchor = row.get("selected_test_anchor") or row.get("verifier_anchor") or get_path(row, "observed_action", "command_result_id") or command_result_id(row)
    return stable_hash(anchor or "missing", 24)


def repo_hash(row: dict[str, Any]) -> str:
    return stable_hash(row.get("repo_family") or row.get("repo_id") or row.get("root_id") or "unknown", 24)


def root_hash(row: dict[str, Any], source_stage: str) -> str:
    return stable_hash(root_lineage_key(row, source_stage), 24)


def real_log_id(row: dict[str, Any], source_stage: str) -> str:
    return stable_hash({
        "source_stage": source_stage,
        "episode_id": episode_id(row),
        "observation_id": observation_id(row),
        "command_result_id": command_result_id(row),
        "root_lineage_key": root_lineage_key(row, source_stage),
    }, 24)


def covered_keys(row: dict[str, Any]) -> set[str]:
    keys = set()
    for field in ("row_id", "source_row_id", "episode_id", "root_lineage_key"):
        value = row.get(field)
        if value:
            keys.add(str(value))
    source_stage = str(row.get("source_stage") or "")
    task = str(row.get("task_type") or row.get("task_family") or "")
    repo = str(row.get("repo_family") or row.get("repo_id") or row.get("root_id") or "")
    lineage = str(row.get("root_lineage_key") or "")
    if source_stage and task and (repo or lineage):
        keys.add(stable_hash({"source_stage": source_stage, "task": task, "repo": repo, "lineage": lineage}, 24))
    return keys


def source_record_keys(row: dict[str, Any], source_stage: str, projection: str) -> set[str]:
    keys = {real_log_id(row, source_stage), episode_id(row), root_lineage_key(row, source_stage)}
    keys.add(stable_hash({
        "source_stage": source_stage,
        "task": projection,
        "repo": row.get("repo_family") or row.get("repo_id") or row.get("root_id") or "",
        "lineage": root_lineage_key(row, source_stage),
    }, 24))
    return {k for k in keys if k}


def target_for_projection(status: str, projection: str) -> str:
    if projection == "transition_verifier_transition":
        return status if status in {"PASS_CURRENT_STATE", "FAIL_CURRENT_STATE", "PASS_CURRENT_BUILD", "INSUFFICIENT_EVIDENCE", "FAIL_TO_PASS"} else "INSUFFICIENT_EVIDENCE"
    if projection == "transition_continue_or_stop":
        if status == "PASS_CURRENT_STATE":
            return "CONTINUE_SINGLE_VERIFIER_EVIDENCE"
        if status in {"FAIL_CURRENT_STATE", "FAIL_TO_FAIL", "NOT_EXERCISED"}:
            return "CONTINUE_DIAGNOSE_FAILURE"
        return "ABSTAIN_ENV_BLOCKED"
    if projection == "transition_next_action":
        if status == "PASS_CURRENT_STATE":
            return "RUN_SELECTED_VERIFIER"
        if status in {"FAIL_CURRENT_STATE", "FAIL_TO_FAIL", "NOT_EXERCISED"}:
            return "DIAGNOSE_VERIFIER_FAILURE"
        return "DIAGNOSE_ENVIRONMENT"
    raise ValueError(projection)


def options_for_projection(projection: str) -> list[dict[str, Any]]:
    src = {
        "transition_verifier_transition": STATUS_OPTIONS,
        "transition_continue_or_stop": STOP_OPTIONS,
        "transition_next_action": NEXT_ACTION_OPTIONS,
    }[projection]
    return [
        {"label": label, "semantic_value": value, "description_hash": stable_hash(desc, 16)}
        for label, value, desc in src
    ]


def label_for(options: list[dict[str, Any]], target: str) -> str:
    for option in options:
        if option["semantic_value"] == target:
            return option["label"]
    raise ValueError(target)


def row_allowed(row: dict[str, Any], source_stage: str) -> tuple[bool, list[str]]:
    blockers = []
    if not episode_id(row):
        blockers.append("missing_episode_id")
    if not command_result_id(row):
        blockers.append("missing_command_result_id")
    if not (row.get("verifier_status") or row.get("verifier_transition")):
        blockers.append("missing_verifier_status")
    if not (row.get("selected_test_anchor") or row.get("verifier_anchor") or command_result_id(row)):
        blockers.append("missing_selected_verifier_anchor")
    status = verifier_status(row)
    if status == "FAIL_TO_PASS":
        blockers.append("fail_to_pass_requires_pre_post_patch_causality_not_available")
    if source_stage == "stage12203_controlled_selected_verifier_replay" and status == "INSUFFICIENT_EVIDENCE":
        # Allowed as verifier observation, but not selected-test success.
        pass
    return not blockers, blockers


def iter_strings(value: Any, key: str = ""):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from iter_strings(v, str(k))
    elif isinstance(value, list):
        for v in value:
            yield from iter_strings(v, key)
    elif isinstance(value, str):
        yield key, value


def guardrail_scan(objects: list[Any]) -> dict[str, Any]:
    raw = []
    over = []
    for obj in objects:
        for key, text in iter_strings(obj):
            if RAW_KEY_RE.search(key):
                raw.append({"kind": "raw_key", "key": key, "hash": stable_hash(text, 16)})
            if ABS_PATH_RE.search(text) or URL_RE.search(text) or COMMANDISH_RE.search(text) or DIFF_RE.search(text):
                raw.append({"kind": "raw_value", "key": key, "hash": stable_hash(text, 16)})
        if isinstance(obj, dict):
            if obj.get("strict_eval_eligible") is True or obj.get("source_heldout_admissible") is True:
                over.append({"kind": "eval_or_sourceheldout_true", "hash": stable_hash(obj, 16)})
            for k in ("patch_trace_admitted", "repair_claim_admitted", "fail_to_pass_claim_admitted", "level4_admitted"):
                v = obj.get(k)
                if isinstance(v, int) and v > 0:
                    over.append({"kind": f"{k}_positive", "hash": stable_hash(obj, 16)})
    return {
        "scan_passed": not raw and not over,
        "raw_leak_count": len(raw),
        "overclaim_count": len(over),
        "raw_findings": raw[:20],
        "overclaim_findings": over[:20],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12385_summary = read_json(STAGE12385_SUMMARY)
    baseline_count = int(stage12385_summary.get("current_admitted_train_support_tasks") or 172)
    covered = set()
    for row in read_jsonl(STAGE12385_ROWS):
        covered.update(covered_keys(row))

    candidate_records = []
    blocked_records = []
    source_record_counts = Counter()
    status_counts = Counter()
    language_counts = Counter()
    repo_counts = Counter()
    projection_counts = Counter()
    duplicate_projection_count = 0

    projections = ["transition_verifier_transition", "transition_continue_or_stop"]
    for source_stage, path in REAL_LOG_SOURCES.items():
        for source_row in read_jsonl(path):
            source_record_counts[source_stage] += 1
            if source_stage == "stage12207_no_install_selected_test_log_level3_joiner":
                blocked_records.append({
                    "stage": STAGE,
                    "source_stage": source_stage,
                    "stable_real_log_record_id": real_log_id(source_row, source_stage),
                    "blockers": ["already_covered_by_stage12385_selected_test_ledger_per_stage12416_scout"],
                })
                continue
            if source_stage == "stage12215_hydratable_selected_verifier_reexecution" and str(source_row.get("repo_family") or "") in {"pallets/click", "pallets/jinja"}:
                blocked_records.append({
                    "stage": STAGE,
                    "source_stage": source_stage,
                    "stable_real_log_record_id": real_log_id(source_row, source_stage),
                    "blockers": ["already_covered_by_stage12385_selected_test_ledger_per_stage12416_scout"],
                })
                continue
            allowed, blockers = row_allowed(source_row, source_stage)
            status = verifier_status(source_row)
            language = row_language(source_row)
            repo_h = repo_hash(source_row)
            language_counts[language] += 1
            repo_counts[repo_h] += 1
            status_counts[status] += 1
            if not allowed:
                blocked_records.append({
                    "stage": STAGE,
                    "source_stage": source_stage,
                    "stable_real_log_record_id": real_log_id(source_row, source_stage),
                    "blockers": blockers,
                })
                continue
            for projection in projections:
                keys = source_record_keys(source_row, source_stage, projection)
                if covered.intersection(keys):
                    duplicate_projection_count += 1
                    continue
                target = target_for_projection(status, projection)
                opts = options_for_projection(projection)
                target_label = label_for(opts, target)
                rec_id_basis = {"source_stage": source_stage, "real_log": real_log_id(source_row, source_stage), "projection": projection}
                record = {
                    "row_id": f"{STAGE}::{stable_hash(rec_id_basis, 20)}",
                    "stage": STAGE,
                    "record_type": "direct_real_verifier_log_train_support_projection",
                    "source_stage": source_stage,
                    "stable_real_log_record_id": real_log_id(source_row, source_stage),
                    "episode_id_hash": stable_hash(episode_id(source_row) or "missing", 24),
                    "observation_id_hash": stable_hash(observation_id(source_row) or "missing", 24),
                    "command_result_id_hash": stable_hash(command_result_id(source_row) or "missing", 24),
                    "state_update_id_hash": stable_hash(state_update_id(source_row) or "missing", 24),
                    "stop_decision_id_hash": stable_hash(stop_decision_id(source_row) or "missing", 24),
                    "repo_family_hash": repo_h,
                    "root_lineage_key_hash": root_hash(source_row, source_stage),
                    "language_family": language,
                    "selected_test_anchor_hash": selected_anchor_hash(source_row),
                    "selected_test_scope_kind": "selected_verifier_observation_or_command_hash_only",
                    "selected_test_scope_count": 1,
                    "source_or_test_hash": selected_anchor_hash(source_row),
                    "verifier_anchor_id_hash": stable_hash(source_row.get("verifier_anchor") or command_result_id(source_row) or "missing", 24),
                    "verifier_output_class": output_class(source_row),
                    "verifier_status": status,
                    "task_projection": projection,
                    "target_label": target_label,
                    "target_semantic_value": target,
                    "opaque_options": opts,
                    "anti_cheat": {
                        "deterministic_option_shuffle": True,
                        "singleton_options": False,
                        "target_label_not_visible_before_options": True,
                        "target_value_not_visible_before_options": True,
                        "raw_command_output_not_rendered": True,
                        "train_support_only": True,
                    },
                    "claim_boundary": "Direct real verifier-log observation train support only; not patch trace, not repair proof, not source-heldout, not strict eval, and not full task completion.",
                    "train_support_only": True,
                    "training_allowed": True,
                    "strict_eval_eligible": False,
                    "source_heldout_admissible": False,
                    "patch_trace_admitted": 0,
                    "repair_claim_admitted": 0,
                    "fail_to_pass_claim_admitted": 0,
                    "level3_admitted": 0,
                    "level4_admitted": 0,
                    "source_key_audit_hash": stable_hash(sorted(keys), 24),
                }
                candidate_records.append(record)
                projection_counts[projection] += 1

    # Deduplicate exact row IDs.
    seen = set()
    rows = []
    duplicate_row_id_count = 0
    for row in candidate_records:
        if row["row_id"] in seen:
            duplicate_row_id_count += 1
            continue
        seen.add(row["row_id"])
        rows.append(row)

    # Keep diagnostic-only if it is all one status; here rows may still be train-support but global training remains blocked by 500 target.
    row_status_counts = Counter(row["target_semantic_value"] for row in rows)
    row_language_counts = Counter(row["language_family"] for row in rows)
    row_projection_counts = Counter(row["task_projection"] for row in rows)
    row_source_counts = Counter(row["source_stage"] for row in rows)

    summary = {
        "stage": STAGE,
        "decision": "direct_real_log_train_support_canonicalized_training_still_blocked_by_500_target" if rows else "no_direct_real_log_rows_emitted",
        "claim_boundary": "Stage12416 emits only safe direct-real-log verifier observation projections. It does not emit patch traces, repair claims, FAIL_TO_PASS claims, source-heldout rows, strict eval rows, or raw command/output/source text.",
        "baseline_stage12385_current_admitted_train_support_tasks": baseline_count,
        "emitted_train_support_rows": len(rows),
        "total_current_train_support_tasks_if_accepted": baseline_count + len(rows),
        "remaining_gap_to_500": max(0, 500 - baseline_count - len(rows)),
        "training_allowed": False,
        "training_blockers": ["500_train_support_target_not_reached", "stage12416_is_train_support_delta_only_not_full_package"],
        "source_record_counts": dict(sorted(source_record_counts.items())),
        "source_counts": dict(sorted(row_source_counts.items())),
        "language_counts": dict(sorted(row_language_counts.items())),
        "status_counts_before_projection": dict(sorted(status_counts.items())),
        "target_semantic_counts": dict(sorted(row_status_counts.items())),
        "task_projection_counts": dict(sorted(row_projection_counts.items())),
        "duplicate_projection_count_against_stage12385": duplicate_projection_count,
        "duplicate_row_id_count": duplicate_row_id_count,
        "blocked_source_records": len(blocked_records),
        "admitted_rows": len(rows),
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "repair_claim_admitted": 0,
        "fail_to_pass_claim_admitted": 0,
        "strict_eval_eligible": 0,
        "source_heldout_admissible": 0,
        "guardrail_scan_passed": False,
    }
    manifest = dict(summary)
    manifest["artifact_names"] = {
        "rows": "direct_verifier_log_train_support_rows.jsonl",
        "blocked": "direct_verifier_log_blocked_records.jsonl",
        "guardrail": "guardrail_scan.json",
    }
    guardrail = guardrail_scan([summary, manifest, rows, blocked_records])
    summary["guardrail_scan_passed"] = guardrail["scan_passed"]
    summary["raw_leak_count"] = guardrail["raw_leak_count"]
    summary["overclaim_count"] = guardrail["overclaim_count"]
    manifest.update({"guardrail_scan_passed": guardrail["scan_passed"], "raw_leak_count": guardrail["raw_leak_count"], "overclaim_count": guardrail["overclaim_count"]})

    write_jsonl(OUT / "direct_verifier_log_train_support_rows.jsonl", rows)
    write_jsonl(OUT / "direct_verifier_log_blocked_records.jsonl", blocked_records)
    write_json(OUT / "direct_verifier_log_train_support_manifest.json", manifest)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

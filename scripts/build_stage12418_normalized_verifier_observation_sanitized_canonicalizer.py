#!/usr/bin/env python3
"""Stage12418 sanitized derived projection lane for Stage12216.

Stage12216 normalizes verifier observations that are already derivative of
earlier source stages. This stage emits only sanitized train-support projection
rows and keeps the proof-floor boundary explicit: no raw commands, paths,
stdout/stderr, diffs, source text, URLs, patch traces, repair claims, strict eval,
or source-heldout admission.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12418_normalized_verifier_observation_sanitized_canonicalizer"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12216_ROWS = ROOT / "runs/local/artifacts/stage12216_normalized_verifier_observation_dataset/normalized_verifier_observation_records.jsonl"
STAGE12216_BLOCKED = ROOT / "runs/local/artifacts/stage12216_normalized_verifier_observation_dataset/blocked_normalization_rows.jsonl"
STAGE12216_SUMMARY = ROOT / "runs/local/artifacts/stage12216_normalized_verifier_observation_dataset/summary.json"
STAGE12417_ROWS = ROOT / "runs/local/artifacts/stage12417_combined_train_support_ledger_v16/combined_train_support_rows_v16.jsonl"
STAGE12417_LEDGER = ROOT / "runs/local/artifacts/stage12417_combined_train_support_ledger_v16/combined_train_support_ledger_v16.json"

TARGET_TRAIN_SUPPORT_ROWS = 500
ALLOWED_PROJECTIONS = ("transition_verifier_transition", "transition_continue_or_stop")

STATUS_OPTIONS = [
    ("A", "PASS_CURRENT_STATE", "selected verifier observation supports current-state pass"),
    ("B", "FAIL_CURRENT_STATE", "selected verifier observation supports current-state fail"),
    ("C", "PASS_CURRENT_BUILD", "build succeeded without runnable selected-verifier proof"),
    ("D", "PASS_CURRENT_BUILD_AND_RUN", "build and selected verifier run succeeded"),
    ("E", "PASS_TO_PASS", "transition stayed passing under the source transition policy"),
    ("F", "FAIL_TO_PASS", "source row already classifies fail-to-pass verifier transition only"),
    ("G", "INSUFFICIENT_EVIDENCE", "verifier evidence is insufficient for a stronger status"),
]
STOP_OPTIONS = [
    ("A", "CONTINUE_SINGLE_VERIFIER_EVIDENCE", "continue because one verifier observation is not full task acceptance"),
    ("B", "CONTINUE_DIAGNOSE_FAILURE", "continue by diagnosing verifier failure"),
    ("C", "ABSTAIN_ENV_BLOCKED", "abstain when evidence is insufficient or environment blocked"),
    ("D", "STOP_DONE", "stop only with full acceptance evidence"),
]

ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){1,}[A-Za-z0-9._-]+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
COMMANDISH_RE = re.compile(r"\b(python|pytest|cargo|npm|yarn|pnpm|bash|sh|git|ctest|cmake)\b.+\s(-m|-q|test|run|build|--test-dir|checkout|diff)\b", re.I)
DIFF_RE = re.compile(r"(^|\n)(diff --git|@@ |\+{3} |--- )")
RAW_KEY_RE = re.compile(
    r"^(command|cmd|argv|cwd|stdout|stderr|stdout_tail|stderr_tail|stdout_excerpt|stderr_excerpt|"
    r"output|path|url|diff|patch|patch_body|patch_diff|source_text|content|input_text|decoder_text)$",
    re.I,
)
RISKY_SOURCE_STAGE_RE = re.compile(r"(heldout|strict_eval|eval_strict|source_heldout)", re.I)


def stable_hash(value: Any, n: int = 24) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise TypeError(f"{path}:{line_no} did not contain a JSON object")
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


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value > 0
    return False


def verifier_transition(row: dict[str, Any]) -> str:
    status = str(
        row.get("verifier_transition")
        or row.get("verifier_status")
        or get_path(row, "verifier_result", "verifier_transition")
        or get_path(row, "verifier_result", "verifier_status")
        or "INSUFFICIENT_EVIDENCE"
    )
    if status == "ENV_BLOCKED":
        return "INSUFFICIENT_EVIDENCE"
    return status if status in {item[1] for item in STATUS_OPTIONS} else "INSUFFICIENT_EVIDENCE"


def command_result(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("command_result")
    return value if isinstance(value, dict) else {}


def patch_trace(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("patch_trace")
    return value if isinstance(value, dict) else {}


def row_language(row: dict[str, Any]) -> str:
    return str(row.get("language_family") or row.get("language") or "unknown")


def command_result_id(row: dict[str, Any]) -> str:
    return str(
        command_result(row).get("command_result_id")
        or get_path(row, "observed_action", "command_result_id")
        or get_path(row, "verifier_result", "command_result_id")
        or ""
    )


def observation_id(row: dict[str, Any]) -> str:
    return str(get_path(row, "observation", "observation_id") or "")


def root_lineage_key_hash(row: dict[str, Any]) -> str:
    basis = {
        "root_id": row.get("root_id"),
        "repo_family": row.get("repo_family"),
        "rollup_record_id": row.get("rollup_record_id"),
        "episode_id": row.get("episode_id"),
    }
    return stable_hash(basis, 24)


def required_source_keys(row: dict[str, Any]) -> dict[str, str]:
    cmd = command_result(row)
    transition = verifier_transition(row)
    fallback_command_hash = stable_hash(
        {
            "command": cmd.get("command") or get_path(row, "observed_action", "command") or get_path(row, "verifier_result", "command_text"),
            "returncode": cmd.get("returncode") if "returncode" in cmd else get_path(row, "verifier_result", "exit_code"),
            "stdout_sha256": cmd.get("stdout_sha256") or get_path(row, "verifier_result", "stdout_sha256"),
            "stderr_sha256": cmd.get("stderr_sha256") or get_path(row, "verifier_result", "stderr_sha256"),
        },
        24,
    )
    return {
        "rollup_record_id": str(row.get("rollup_record_id") or ""),
        "rollup_source_stage_ref": stable_hash(
            {
                "rollup_source_stage": row.get("rollup_source_stage"),
                "rollup_source_ref": row.get("rollup_source_ref"),
            },
            24,
        ),
        "episode_command_transition": stable_hash(
            {
                "episode_id": row.get("episode_id"),
                "command_result_id": command_result_id(row),
                "verifier_transition": transition,
            },
            24,
        ),
        "fallback_root_command_transition": stable_hash(
            {
                "root_id": row.get("root_id"),
                "command_hash": fallback_command_hash,
                "verifier_transition": transition,
            },
            24,
        ),
    }


def source_key_audit_hash(row: dict[str, Any], projection: str) -> str:
    return stable_hash({"projection": projection, "source_keys": required_source_keys(row)}, 24)


def root_projection_target(row: dict[str, Any], projection: str, target: str) -> str:
    return f"{root_lineage_key_hash(row)}::{projection}::{target}"


def target_for_projection(status: str, projection: str) -> str:
    if projection == "transition_verifier_transition":
        return status
    if projection == "transition_continue_or_stop":
        if status in {"FAIL_CURRENT_STATE", "FAIL_TO_PASS"}:
            return "CONTINUE_DIAGNOSE_FAILURE"
        if status in {"INSUFFICIENT_EVIDENCE"}:
            return "ABSTAIN_ENV_BLOCKED"
        return "CONTINUE_SINGLE_VERIFIER_EVIDENCE"
    raise ValueError(projection)


def options_for_projection(projection: str) -> list[dict[str, Any]]:
    src = STATUS_OPTIONS if projection == "transition_verifier_transition" else STOP_OPTIONS
    return [
        {
            "label": label,
            "semantic_value": value,
            "description_hash": stable_hash(description, 16),
        }
        for label, value, description in src
    ]


def label_for(options: list[dict[str, Any]], target: str) -> str:
    for option in options:
        if option["semantic_value"] == target:
            return str(option["label"])
    raise ValueError(target)


def verifier_output_class(row: dict[str, Any]) -> str:
    status = verifier_transition(row)
    build_only = truthy(row.get("counts_toward_build_only_floor")) or status == "PASS_CURRENT_BUILD"
    runnable = truthy(row.get("counts_toward_runnable_verifier_proof")) and not build_only
    if status == "PASS_CURRENT_BUILD":
        return "build_only_no_runnable_verifier_proof"
    if status == "PASS_CURRENT_BUILD_AND_RUN" and runnable:
        return "build_and_selected_verifier_pass"
    if status in {"PASS_CURRENT_STATE", "PASS_TO_PASS"} and runnable:
        return "selected_verifier_pass"
    if status in {"FAIL_CURRENT_STATE", "FAIL_TO_PASS"}:
        return "selected_verifier_failure_or_transition_failure"
    return "insufficient_or_uncertain_verifier_evidence"


def has_observed_action(row: dict[str, Any]) -> bool:
    observed = row.get("observed_action")
    if not isinstance(observed, dict):
        return False
    if not observed.get("command_result_id"):
        return False
    source = str(get_path(row, "candidate_action_set", "decision_training_blocker") or "")
    return "selected_test_intent" not in source


def row_blockers(row: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if row.get("split") != "train_support" or not truthy(row.get("train_support_only")):
        blockers.append("not_train_support_only")
    if truthy(row.get("strict_eval_eligible")):
        blockers.append("strict_eval_blocked")
    if truthy(row.get("source_heldout_admissible")):
        blockers.append("source_heldout_blocked")
    if RISKY_SOURCE_STAGE_RE.search(str(row.get("source_stage") or "")) or RISKY_SOURCE_STAGE_RE.search(str(row.get("rollup_source_stage") or "")):
        blockers.append("source_stage_eval_or_heldout_blocked")
    if patch_trace(row).get("has_patch_trace") or row.get("patch_diff"):
        blockers.append("patch_generation_or_trace_blocked")
    if truthy(patch_trace(row).get("counts_toward_patch_trace_floor")) or truthy(row.get("counts_toward_unbounded_patch_trace_floor")):
        blockers.append("patch_trace_floor_blocked")
    if not row.get("rollup_record_id"):
        blockers.append("missing_rollup_record_id")
    if not row.get("episode_id") or not command_result_id(row):
        blockers.append("missing_episode_or_command_result_id")
    return blockers


def target_semantic_value(row: dict[str, Any]) -> str:
    if row.get("target_semantic_value"):
        return str(row["target_semantic_value"])
    for option in row.get("opaque_options") or []:
        if isinstance(option, dict) and option.get("label") == row.get("bounded_choice_target_label"):
            return str(option.get("semantic_value") or option.get("semantic_id") or option.get("value") or "")
    return str(row.get("target_semantic_id") or "")


def task_projection(row: dict[str, Any]) -> str:
    return str(row.get("task_projection") or row.get("task_family") or row.get("record_type") or "")


def stage12417_dedupe_surfaces(rows: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    source_hashes: set[str] = set()
    root_targets: set[str] = set()
    for row in rows:
        if row.get("source_key_audit_hash"):
            source_hashes.add(str(row["source_key_audit_hash"]))
        root_hash = row.get("root_lineage_key_hash")
        projection = task_projection(row)
        target = target_semantic_value(row)
        if root_hash and projection and target:
            root_targets.add(f"{root_hash}::{projection}::{target}")
    return source_hashes, root_targets


def make_projection_row(row: dict[str, Any], projection: str) -> dict[str, Any]:
    status = verifier_transition(row)
    target = target_for_projection(status, projection)
    options = options_for_projection(projection)
    source_hash = source_key_audit_hash(row, projection)
    root_target = root_projection_target(row, projection, target)
    source_keys = required_source_keys(row)
    row_basis = {
        "stage": STAGE,
        "source_key_audit_hash": source_hash,
        "root_projection_target": root_target,
        "projection": projection,
    }
    return {
        "row_id": f"{STAGE}::{stable_hash(row_basis, 20)}",
        "stage": STAGE,
        "record_type": "derived_sanitized_verifier_observation_projection",
        "source_stage": str(row.get("source_stage") or "unknown"),
        "rollup_source_stage": str(row.get("rollup_source_stage") or "unknown"),
        "stage12216_source_line_hash": stable_hash(row.get("stage12216_source_line") or row.get("rollup_record_id") or row.get("episode_id"), 24),
        "rollup_record_id_hash": stable_hash(source_keys["rollup_record_id"] or "missing", 24),
        "rollup_source_stage_ref_hash": source_keys["rollup_source_stage_ref"],
        "episode_command_transition_hash": source_keys["episode_command_transition"],
        "fallback_root_command_transition_hash": source_keys["fallback_root_command_transition"],
        "source_key_audit_hash": source_hash,
        "root_lineage_key_hash": root_lineage_key_hash(row),
        "root_projection_target_hash": stable_hash(root_target, 24),
        "episode_id_hash": stable_hash(row.get("episode_id") or "missing", 24),
        "command_result_id_hash": stable_hash(command_result_id(row) or "missing", 24),
        "observation_id_hash": stable_hash(observation_id(row) or "missing", 24),
        "repo_family_hash": stable_hash(row.get("repo_family") or "unknown", 24),
        "root_id_hash": stable_hash(row.get("root_id") or "unknown", 24),
        "observed_action_hash": stable_hash(
            {
                "present": has_observed_action(row),
                "command_result_id": command_result_id(row),
                "action_type": get_path(row, "observed_action", "type"),
            },
            24,
        ),
        "language_family": row_language(row),
        "verifier_transition": status,
        "verifier_output_class": verifier_output_class(row),
        "pass_current_build_runnable_proof": False if status == "PASS_CURRENT_BUILD" else truthy(row.get("counts_toward_runnable_verifier_proof")),
        "pass_to_pass_transition_policy_only": status == "PASS_TO_PASS",
        "fail_to_pass_verifier_transition_only": status == "FAIL_TO_PASS",
        "task_projection": projection,
        "target_label": label_for(options, target),
        "target_semantic_value": target,
        "opaque_options": options,
        "lineage_dedupe_key_hashes": {
            "rollup_record_id": stable_hash(source_keys["rollup_record_id"] or "missing", 24),
            "rollup_source_stage_ref": source_keys["rollup_source_stage_ref"],
            "episode_command_transition": source_keys["episode_command_transition"],
            "fallback_root_command_transition": source_keys["fallback_root_command_transition"],
        },
        "admission": {
            "train_support_only": True,
            "derived_projection_lane": True,
            "countable_as_new_train_support_row": False,
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
            "patch_trace_admitted": 0,
            "repair_claim_admitted": 0,
            "fail_to_pass_claim_admitted": 0,
        },
        "anti_cheat": {
            "sanitized_hashes_and_classes_only": True,
            "raw_command_output_not_rendered": True,
            "raw_source_not_rendered": True,
            "raw_patch_not_rendered": True,
            "legacy_input_text_not_copied": True,
            "dedupe_against_stage12417": True,
        },
        "claim_boundary": "Derived sanitized projection from Stage12216 only; not a new proof floor, not strict eval, not source-heldout, not patch trace, and not repair proof.",
        "train_support_only": True,
        "training_allowed": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "patch_trace_admitted": 0,
        "repair_claim_admitted": 0,
        "fail_to_pass_claim_admitted": 0,
        "level3_admitted": 0,
        "level4_admitted": 0,
    }


def iter_strings(value: Any, key: str = ""):
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            yield from iter_strings(child_value, str(child_key))
    elif isinstance(value, list):
        for child_value in value:
            yield from iter_strings(child_value, key)
    elif isinstance(value, str):
        yield key, value


def guardrail_scan(objects: list[Any]) -> dict[str, Any]:
    raw_findings = []
    overclaim_findings = []
    for obj in objects:
        for key, text in iter_strings(obj):
            if RAW_KEY_RE.search(key):
                raw_findings.append({"kind": "raw_key", "key_hash": stable_hash(key, 16)})
            elif ABS_PATH_RE.search(text) or URL_RE.search(text) or COMMANDISH_RE.search(text) or DIFF_RE.search(text):
                raw_findings.append({"kind": "raw_value", "key_hash": stable_hash(key, 16), "value_hash": stable_hash(text, 16)})
        if isinstance(obj, dict):
            admission = obj.get("admission") if isinstance(obj.get("admission"), dict) else {}
            if truthy(obj.get("strict_eval_eligible")) or truthy(admission.get("strict_eval_eligible")):
                overclaim_findings.append({"kind": "strict_eval_eligible_true", "row_hash": stable_hash(obj, 16)})
            if truthy(obj.get("source_heldout_admissible")) or truthy(admission.get("source_heldout_admissible")):
                overclaim_findings.append({"kind": "source_heldout_admissible_true", "row_hash": stable_hash(obj, 16)})
            for field in ("patch_trace_admitted", "repair_claim_admitted", "fail_to_pass_claim_admitted", "level3_admitted", "level4_admitted"):
                if truthy(obj.get(field)) or truthy(admission.get(field)):
                    overclaim_findings.append({"kind": f"{field}_positive", "row_hash": stable_hash(obj, 16)})
    return {
        "scan_passed": not raw_findings and not overclaim_findings,
        "raw_leak_count": len(raw_findings),
        "overclaim_count": len(overclaim_findings),
        "raw_findings": raw_findings[:20],
        "overclaim_findings": overclaim_findings[:20],
    }


def count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(field) or "unknown") for row in rows).items()))


def main() -> None:
    source_rows = read_jsonl(STAGE12216_ROWS)
    blocked_source_rows = read_jsonl(STAGE12216_BLOCKED)
    stage12216_summary = read_json(STAGE12216_SUMMARY)
    stage12417_rows = read_jsonl(STAGE12417_ROWS)
    stage12417_ledger = read_json(STAGE12417_LEDGER)
    existing_source_hashes, existing_root_targets = stage12417_dedupe_surfaces(stage12417_rows)

    candidate_rows: list[dict[str, Any]] = []
    blocked_records: list[dict[str, Any]] = []
    duplicate_records: list[dict[str, Any]] = []
    derived_source_overlap_counts: Counter[str] = Counter()
    source_overlap_by_rollup_stage: Counter[str] = Counter()
    source_overlap_by_source_stage: Counter[str] = Counter()
    source_status_counts: Counter[str] = Counter()
    source_language_counts: Counter[str] = Counter()
    internal_seen: dict[tuple[str, str], str] = {}

    for row in source_rows:
        status = verifier_transition(row)
        source_status_counts[status] += 1
        source_language_counts[row_language(row)] += 1
        source_overlap_by_rollup_stage[str(row.get("rollup_source_stage") or "unknown")] += 1
        source_overlap_by_source_stage[str(row.get("source_stage") or "unknown")] += 1
        derived_source_overlap_counts["stage12216_normalized_verifier_observation_dataset"] += 1
        if row.get("rollup_source_stage"):
            derived_source_overlap_counts[str(row["rollup_source_stage"])] += 1

        blockers = row_blockers(row)
        if blockers:
            blocked_records.append({
                "stage": STAGE,
                "source_row_hash": stable_hash(required_source_keys(row), 24),
                "rollup_record_id_hash": stable_hash(str(row.get("rollup_record_id") or "missing"), 24),
                "verifier_transition": status,
                "blockers": blockers,
            })
            continue

        for projection in ALLOWED_PROJECTIONS:
            projection_row = make_projection_row(row, projection)
            source_hash = str(projection_row["source_key_audit_hash"])
            root_target = root_projection_target(row, projection, str(projection_row["target_semantic_value"]))
            internal_keys = [
                ("rollup_record_id", f"{projection}::{str(row.get('rollup_record_id') or '')}"),
                ("rollup_source_stage_ref", f"{projection}::{str(projection_row['rollup_source_stage_ref_hash'])}"),
                ("episode_command_transition", f"{projection}::{str(projection_row['episode_command_transition_hash'])}"),
                ("fallback_root_command_transition", f"{projection}::{str(projection_row['fallback_root_command_transition_hash'])}"),
                ("source_key_audit_hash", source_hash),
                ("root_projection_target", root_target),
            ]
            internal_keys = [(kind, value) for kind, value in internal_keys if value]
            internal_matches = [key for key in internal_keys if key in internal_seen]
            stage12417_matches = []
            if source_hash in existing_source_hashes:
                stage12417_matches.append("source_key_audit_hash")
            if root_target in existing_root_targets:
                stage12417_matches.append("root_projection_target")
            if internal_matches or stage12417_matches:
                duplicate_records.append({
                    "stage": STAGE,
                    "row_id": projection_row["row_id"],
                    "source_key_audit_hash": source_hash,
                    "root_projection_target_hash": projection_row["root_projection_target_hash"],
                    "task_projection": projection,
                    "verifier_transition": status,
                    "duplicate_reasons": [
                        {"dedupe_key_type": kind, "first_row_id": internal_seen[(kind, value)]}
                        for kind, value in internal_matches
                    ]
                    + [{"dedupe_key_type": kind, "first_row_id": "stage12417_combined_train_support_ledger_v16"} for kind in stage12417_matches],
                })
                continue
            candidate_rows.append(projection_row)
            for key in internal_keys:
                internal_seen[key] = str(projection_row["row_id"])

    for blocked in blocked_source_rows:
        blocked_records.append({
            "stage": STAGE,
            "source_row_hash": stable_hash(blocked, 24),
            "verifier_transition": verifier_transition(blocked),
            "blockers": ["blocked_by_stage12216_blocked_normalization_rows"],
        })

    row_projection_counts = Counter(row["task_projection"] for row in candidate_rows)
    row_status_counts = Counter(row["target_semantic_value"] for row in candidate_rows)
    duplicate_key_type_counts: Counter[str] = Counter()
    for row in duplicate_records:
        for reason in row.get("duplicate_reasons") or []:
            if isinstance(reason, dict):
                duplicate_key_type_counts[str(reason.get("dedupe_key_type") or "unknown")] += 1

    summary = {
        "stage": STAGE,
        "decision": "derived_sanitized_projection_lane_emitted_training_still_blocked_by_500_target",
        "claim_boundary": "Stage12418 is a sanitized derived projection lane from Stage12216. It is not counted as additional proof-floor evidence over Stage12216 source stages and admits no repair, patch-trace, source-heldout, strict-eval, or fail-to-pass repair claim.",
        "source_stage": "stage12216_normalized_verifier_observation_dataset",
        "source_row_count": len(source_rows),
        "stage12216_blocked_normalization_row_count": len(blocked_source_rows),
        "stage12216_training_allowed": bool(stage12216_summary.get("training_allowed")),
        "stage12417_current_admitted_train_support_tasks": int(stage12417_ledger.get("current_admitted_train_support_tasks") or 0),
        "target_train_support_rows": TARGET_TRAIN_SUPPORT_ROWS,
        "remaining_gap_to_500_from_stage12417": max(0, TARGET_TRAIN_SUPPORT_ROWS - int(stage12417_ledger.get("current_admitted_train_support_tasks") or 0)),
        "emitted_sanitized_projection_rows": len(candidate_rows),
        "countable_as_new_train_support_rows": 0,
        "countable_as_new_proof_floor_rows": 0,
        "training_allowed": False,
        "training_blockers": [
            "500_train_support_target_not_reached",
            "stage12418_is_derived_projection_lane_not_new_source_proof_floor",
        ],
        "allowed_projections": list(ALLOWED_PROJECTIONS),
        "optional_transition_next_action_emitted": 0,
        "blocked_source_records": len(blocked_records),
        "duplicate_projection_rows_removed": len(duplicate_records),
        "duplicate_key_type_counts": dict(sorted(duplicate_key_type_counts.items())),
        "derived_source_overlap_counts": dict(sorted(derived_source_overlap_counts.items())),
        "derived_source_overlap_by_rollup_source_stage": dict(sorted(source_overlap_by_rollup_stage.items())),
        "derived_source_overlap_by_source_stage": dict(sorted(source_overlap_by_source_stage.items())),
        "source_status_counts": dict(sorted(source_status_counts.items())),
        "source_language_counts": dict(sorted(source_language_counts.items())),
        "language_counts": count_by(candidate_rows, "language_family"),
        "status_counts": dict(sorted(Counter(row["verifier_transition"] for row in candidate_rows).items())),
        "target_semantic_counts": dict(sorted(row_status_counts.items())),
        "task_projection_counts": dict(sorted(row_projection_counts.items())),
        "raw_command_rows": 0,
        "legacy_input_text_copied_rows": 0,
        "pass_current_build_rows": sum(1 for row in candidate_rows if row["verifier_transition"] == "PASS_CURRENT_BUILD"),
        "pass_current_build_runnable_proof_rows_should_be_zero": sum(
            1 for row in candidate_rows if row["verifier_transition"] == "PASS_CURRENT_BUILD" and row["pass_current_build_runnable_proof"]
        ),
        "pass_to_pass_transition_policy_only_rows": sum(1 for row in candidate_rows if row["pass_to_pass_transition_policy_only"]),
        "fail_to_pass_verifier_transition_only_rows": sum(1 for row in candidate_rows if row["fail_to_pass_verifier_transition_only"]),
        "fail_to_pass_verifier_transition_target_rows": sum(
            1
            for row in candidate_rows
            if row["task_projection"] == "transition_verifier_transition" and row["target_semantic_value"] == "FAIL_TO_PASS"
        ),
        "fail_to_pass_non_transition_target_rows_should_be_zero": sum(
            1
            for row in candidate_rows
            if row["task_projection"] != "transition_verifier_transition" and row["target_semantic_value"] == "FAIL_TO_PASS"
        ),
        "strict_eval_eligible": 0,
        "source_heldout_admissible": 0,
        "patch_trace_admitted": 0,
        "repair_claim_admitted": 0,
        "fail_to_pass_claim_admitted": 0,
        "level3_admitted": 0,
        "level4_admitted": 0,
        "artifact_names": {
            "rows": "sanitized_normalized_verifier_observation_projection_rows.jsonl",
            "blocked": "blocked_sanitized_projection_records.jsonl",
            "duplicates": "duplicate_sanitized_projection_records.jsonl",
            "manifest": "sanitized_normalized_verifier_observation_manifest.json",
            "guardrail": "guardrail_scan.json",
        },
        "guardrail_scan_passed": False,
    }
    manifest = dict(summary)
    guardrail = guardrail_scan([summary, manifest, candidate_rows, blocked_records, duplicate_records])
    summary.update({
        "guardrail_scan_passed": guardrail["scan_passed"],
        "raw_leak_count": guardrail["raw_leak_count"],
        "overclaim_count": guardrail["overclaim_count"],
    })
    manifest.update({
        "guardrail_scan_passed": guardrail["scan_passed"],
        "raw_leak_count": guardrail["raw_leak_count"],
        "overclaim_count": guardrail["overclaim_count"],
    })

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "sanitized_normalized_verifier_observation_projection_rows.jsonl", candidate_rows)
    write_jsonl(OUT / "blocked_sanitized_projection_records.jsonl", blocked_records)
    write_jsonl(OUT / "duplicate_sanitized_projection_records.jsonl", duplicate_records)
    write_json(OUT / "sanitized_normalized_verifier_observation_manifest.json", manifest)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

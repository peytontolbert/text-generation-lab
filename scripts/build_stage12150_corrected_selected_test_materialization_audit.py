#!/usr/bin/env python3
"""Audit Stage12149 corrected selected-test materialization rows.

This stage is intentionally independent of the materializer. It rejects the
exact failure mode that produced Stage12130/12140 regressions: several
transition task families rendered as the same selected-test evidence choice.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
DEFAULT_STAGE = "stage12150_corrected_selected_test_materialization_audit"
DEFAULT_INPUT_STAGE = "stage12149_corrected_selected_test_row_materialization_package"
DEFAULT_INPUT_ROWS = REPO / "runs" / "local" / "artifacts" / DEFAULT_INPUT_STAGE / "corrected_selected_test_rows.jsonl"

TASK_TARGET_KINDS = {
    "transition_candidate_selection": {
        "candidate_artifact_or_evidence_candidate",
        "artifact",
        "evidence_candidate",
    },
    "transition_next_action": {"maintainer_action", "action"},
    "transition_continue_or_stop": {"episode_control_decision", "control"},
    "transition_verifier_transition": {"verifier_status", "status"},
    "transition_evidence_citation": {
        "evidence_role_or_evidence_item",
        "evidence_role",
        "evidence_item",
    },
}

EVIDENCE_OBJECT_ROLES = {
    "selected_test_backed_verifier_candidate",
    "verifier_and_test_constraint",
    "candidate_change_surface",
    "symptom_or_call_path_analogue",
    "source_surface",
    "insufficient_evidence",
}

ACTION_VALUES = {
    "SELECT_TEST",
    "RUN_VERIFIER",
    "RETRIEVE_EVIDENCE",
    "INSPECT_SOURCE",
    "PLAN_PATCH",
    "APPLY_PATCH",
    "APPLY_PATCH_ABSTRACT",
    "ABSTAIN_OR_ROLLBACK",
    "FINISH",
    "LOCALIZE_FAILURE",
    "BIND_SYMBOL",
    "VERIFY_RESULT",
    "REPAIR_AFTER_FAILURE",
}

CONTROL_VALUES = {
    "CONTINUE",
    "STOP_DONE",
    "NOT_DONE_MISSING_TESTS",
    "NOT_DONE_MISSING_VERIFIER",
    "ABSTAIN_INSUFFICIENT_EVIDENCE",
}

VERIFIER_VALUES = {
    "PASS_TO_PASS",
    "PASS_CURRENT_STATE",
    "PASS_CURRENT_BUILD",
    "PASS_CURRENT_BUILD_AND_RUN",
    "FAIL_TO_PASS",
    "FAIL_TO_FAIL",
    "NOT_EXERCISED",
    "INSUFFICIENT_EVIDENCE",
    "VERIFIER_REMOVED",
}

DEPENDENCY_PATH_MARKERS = (
    "node_modules/",
    "/node_modules/",
    ".git/",
    "/.git/",
    "target/debug/",
    "target/release/",
    "/target/",
    ".venv/",
    "/.venv/",
    "__pycache__/",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                rows.append(
                    {
                        "_parse_error": str(exc),
                        "_line_no": line_no,
                        "_raw_sha256": hashlib.sha256(line.encode()).hexdigest(),
                    }
                )
            else:
                row["_line_no"] = line_no
                rows.append(row)
    return rows


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def entropy(values: list[str]) -> float:
    if not values:
        return 0.0
    counts = Counter(values)
    total = sum(counts.values())
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def option_signature(options: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    return [
        (
            opt.get("label"),
            opt.get("role"),
            opt.get("artifact_type"),
            opt.get("value"),
            json.dumps(opt.get("semantic_candidate"), sort_keys=True),
        )
        for opt in options
    ]


def target_value(row: dict[str, Any]) -> str:
    target = row.get("target")
    if isinstance(target, dict):
        for key in ("semantic_value", "value", "decoder_text", "bounded_choice_target_label"):
            value = target.get(key)
            if value:
                return str(value)
    for key in ("target_semantic_value", "target_text", "decoder_text", "target_label"):
        value = row.get(key)
        if value:
            return str(value)
    return ""


def target_role(row: dict[str, Any]) -> str:
    label = row.get("target_label") or row.get("bounded_choice_target_label")
    options = row.get("opaque_options") or []
    for opt in options:
        if opt.get("label") == label:
            semantic = opt.get("semantic_candidate")
            if isinstance(semantic, dict) and semantic.get("role"):
                return str(semantic["role"])
            if opt.get("role"):
                return str(opt["role"])
    value = target_value(row)
    for role in EVIDENCE_OBJECT_ROLES:
        if role in value:
            return role
    if value in ACTION_VALUES | CONTROL_VALUES | VERIFIER_VALUES:
        return value
    return value


def row_blockers(row: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if "_parse_error" in row:
        return [f"json_parse_error:{row['_parse_error']}"]

    row_id = str(row.get("row_id") or f"line_{row.get('_line_no')}")
    task = str(row.get("task_type") or "")
    target_label = row.get("target_label") or row.get("bounded_choice_target_label")
    value = target_value(row)
    role = target_role(row)
    options = row.get("opaque_options")
    nested_options = (
        row.get("standalone_projection_source", {}).get("opaque_options")
        if isinstance(row.get("standalone_projection_source"), dict)
        else None
    )

    if task not in TASK_TARGET_KINDS:
        blockers.append(f"{row_id}:unknown_task_type:{task}")

    if not isinstance(options, list) or len(options) < 2:
        blockers.append(f"{row_id}:missing_or_singleton_opaque_options")
        options = []

    labels = [str(opt.get("label", "")) for opt in options]
    if any(len(label) != 1 or label < "A" or label > "Z" for label in labels):
        blockers.append(f"{row_id}:non_single_token_display_label")
    if len(labels) != len(set(labels)):
        blockers.append(f"{row_id}:duplicate_option_labels")
    if target_label not in labels:
        blockers.append(f"{row_id}:target_label_not_in_options")

    if option_signature(options) != option_signature(nested_options or []):
        blockers.append(f"{row_id}:nested_top_level_options_mismatch")

    prompt = str(row.get("input_text") or row.get("prompt_text") or "")
    pre_options = prompt.split("Options:", 1)[0].split("CANDIDATES", 1)[0]
    if value and value in pre_options:
        blockers.append(f"{row_id}:target_value_visible_before_options")

    anti_cheat = row.get("anti_cheat")
    if not isinstance(anti_cheat, dict) or not anti_cheat.get("deterministic_option_shuffle"):
        blockers.append(f"{row_id}:deterministic_option_shuffle_not_asserted")
    if row.get("strict_eval_eligible") is True:
        blockers.append(f"{row_id}:strict_eval_eligible_true_for_train_support_package")
    if row.get("train_support_only") is not True:
        blockers.append(f"{row_id}:train_support_only_not_true")

    target_kind = None
    for opt in options:
        if opt.get("label") == target_label:
            semantic = opt.get("semantic_candidate")
            if isinstance(semantic, dict):
                target_kind = semantic.get("target_kind")
            target_kind = target_kind or opt.get("target_kind")
            break
    if task in TASK_TARGET_KINDS and target_kind not in TASK_TARGET_KINDS[task]:
        blockers.append(f"{row_id}:target_kind_incompatible:{task}:{target_kind}")

    if task == "transition_next_action":
        if value not in ACTION_VALUES:
            blockers.append(f"{row_id}:next_action_target_not_action:{value}")
        if role in EVIDENCE_OBJECT_ROLES:
            blockers.append(f"{row_id}:next_action_target_is_evidence_object:{role}")
    elif task == "transition_continue_or_stop":
        if value not in CONTROL_VALUES:
            blockers.append(f"{row_id}:continue_stop_target_not_control:{value}")
        if role in EVIDENCE_OBJECT_ROLES:
            blockers.append(f"{row_id}:continue_stop_target_is_evidence_object:{role}")
    elif task == "transition_verifier_transition":
        if value not in VERIFIER_VALUES:
            blockers.append(f"{row_id}:verifier_transition_target_not_status:{value}")
        if role in EVIDENCE_OBJECT_ROLES:
            blockers.append(f"{row_id}:verifier_transition_target_is_evidence_object:{role}")

    path_blob = json.dumps(
        {
            "input_text": row.get("input_text"),
            "prompt_text": row.get("prompt_text"),
            "provenance": row.get("provenance"),
            "source_hashes": row.get("source_hashes"),
            "standalone_projection_source": row.get("standalone_projection_source"),
        },
        sort_keys=True,
    )
    for marker in DEPENDENCY_PATH_MARKERS:
        if marker in path_blob:
            blockers.append(f"{row_id}:dependency_or_build_path_visible:{marker}")
            break

    commit_sha = (
        row.get("commit_sha")
        or row.get("standalone_projection_source", {}).get("commit_sha")
        if isinstance(row.get("standalone_projection_source"), dict)
        else None
    )
    language = row.get("language_family")
    if language == "web_js_ts_html" and not commit_sha:
        blockers.append(f"{row_id}:missing_web_commit_sha")

    return blockers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default=DEFAULT_STAGE)
    parser.add_argument("--input-stage", default=DEFAULT_INPUT_STAGE)
    parser.add_argument("--input-rows", default=str(DEFAULT_INPUT_ROWS))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stage = args.stage
    input_stage = args.input_stage
    input_rows = Path(args.input_rows)
    output_dir = REPO / "runs" / "local" / "artifacts" / stage
    summary_path = REPO / "runs" / "summaries" / f"{stage}.json"

    rows = load_jsonl(input_rows)
    output_dir.mkdir(parents=True, exist_ok=True)

    blockers_by_row: dict[str, list[str]] = {}
    rows_by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows_by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    counts_by_language = Counter()
    counts_by_root = Counter()
    counts_by_task = Counter()

    for row in rows:
        row_id = str(row.get("row_id") or f"line_{row.get('_line_no')}")
        blockers = row_blockers(row)
        if blockers:
            blockers_by_row[row_id] = blockers
        root = str(row.get("root_id") or "unknown")
        task = str(row.get("task_type") or "unknown")
        language = str(row.get("language_family") or "unknown")
        rows_by_root[root].append(row)
        rows_by_task[task].append(row)
        counts_by_language[language] += 1
        counts_by_root[root] += 1
        counts_by_task[task] += 1

    root_diversity: dict[str, Any] = {}
    for root, root_rows in rows_by_root.items():
        targets = [target_value(row) for row in root_rows]
        tasks = [str(row.get("task_type") or "unknown") for row in root_rows]
        unique_targets = sorted(set(targets))
        collapsed = len(set(tasks)) > 1 and len(unique_targets) <= 1
        if collapsed:
            for row in root_rows:
                row_id = str(row.get("row_id") or f"line_{row.get('_line_no')}")
                blockers_by_row.setdefault(row_id, []).append(
                    f"{row_id}:root_task_family_target_collapse:{root}"
                )
        root_diversity[root] = {
            "row_count": len(root_rows),
            "task_count": len(set(tasks)),
            "unique_target_semantic_values": len(unique_targets),
            "target_semantic_values": unique_targets,
            "collapsed": collapsed,
        }

    task_role_entropy = {}
    for task, task_rows in rows_by_task.items():
        roles = [target_role(row) for row in task_rows]
        values = [target_value(row) for row in task_rows]
        task_role_entropy[task] = {
            "row_count": len(task_rows),
            "target_role_entropy": entropy(roles),
            "target_value_entropy": entropy(values),
            "target_role_counts": dict(sorted(Counter(roles).items())),
            "target_value_counts": dict(sorted(Counter(values).items())),
        }

    passed = bool(rows) and not blockers_by_row
    decision = (
        "pass_train_support_materialization_audit"
        if passed
        else "block_stage12149_from_training_until_repaired"
    )
    audit = {
        "stage": stage,
        "input_stage": input_stage,
        "created_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "input_rows_path": str(input_rows.relative_to(REPO)) if input_rows.is_absolute() and input_rows.is_relative_to(REPO) else str(input_rows),
        "rows_present": input_rows.exists(),
        "row_count": len(rows),
        "passed": passed,
        "decision": decision,
        "training_allowed": False,
        "strict_eval_eligible": False,
        "promotion_eligible": False,
        "blocker_row_count": len(blockers_by_row),
        "blockers_by_row": blockers_by_row,
        "counts_by_language": dict(sorted(counts_by_language.items())),
        "counts_by_root": dict(sorted(counts_by_root.items())),
        "counts_by_task": dict(sorted(counts_by_task.items())),
        "target_role_entropy_by_task": task_role_entropy,
        "per_root_semantic_diversity": root_diversity,
        "required_next_action": (
            "No training may consume Stage12149 until this audit passes. "
            "If it passes, a separate training request is still required."
        ),
    }
    dump_json(output_dir / "row_materialization_blocker_audit.json", audit)
    dump_json(output_dir / "summary.json", audit)
    dump_json(summary_path, audit)
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

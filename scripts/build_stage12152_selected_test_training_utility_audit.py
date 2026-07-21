#!/usr/bin/env python3
"""Training-utility audit for corrected selected-test rows.

Stage12150 checks contract safety. This stage checks whether a package is
useful enough to train without reinforcing a one-sided policy such as always
FINISH after seeing selected-test evidence.
"""

from __future__ import annotations

import json
import math
import argparse
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
DEFAULT_STAGE = "stage12152_selected_test_training_utility_audit"
DEFAULT_INPUT_STAGE = "stage12149_corrected_selected_test_row_materialization_package"
DEFAULT_INPUT_ROWS = REPO / "runs/local/artifacts" / DEFAULT_INPUT_STAGE / "corrected_selected_test_rows.jsonl"

MIN_ROOTS = 8
MIN_LANGUAGES = 3
MIN_ROWS = 40
MIN_TARGETS_BY_TASK = {
    "transition_next_action": 3,
    "transition_continue_or_stop": 2,
    "transition_verifier_transition": 3,
    "transition_evidence_citation": 2,
    "transition_candidate_selection": 2,
}

DISALLOWED_SINGLETON_TARGETS = {
    "transition_next_action": {"FINISH"},
    "transition_continue_or_stop": {"STOP_DONE"},
    "transition_evidence_citation": {"verifier_and_test_constraint"},
    "transition_candidate_selection": {"selected_test_backed_verifier_candidate"},
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def target_value(row: dict[str, Any]) -> str:
    target = row.get("target")
    if isinstance(target, dict):
        return str(target.get("semantic_value") or target.get("value") or target.get("decoder_text") or "")
    return str(row.get("target_semantic_value") or row.get("target_text") or "")


def entropy(values: list[str]) -> float:
    if not values:
        return 0.0
    counts = Counter(values)
    total = sum(counts.values())
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


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
    out = REPO / "runs/local/artifacts" / stage
    summary_path = REPO / "runs/summaries" / f"{stage}.json"

    rows = load_jsonl(input_rows)
    by_task: dict[str, list[str]] = defaultdict(list)
    by_root: dict[str, list[str]] = defaultdict(list)
    languages = Counter()
    blockers: list[str] = []

    for row in rows:
        task = str(row.get("task_type") or "unknown")
        root = str(row.get("root_id") or "unknown")
        language = str(row.get("language_family") or "unknown")
        value = target_value(row)
        by_task[task].append(value)
        by_root[root].append(value)
        languages[language] += 1

    if len(rows) < MIN_ROWS:
        blockers.append(f"row_count_below_training_floor:{len(rows)}<{MIN_ROWS}")
    if len(by_root) < MIN_ROOTS:
        blockers.append(f"root_count_below_training_floor:{len(by_root)}<{MIN_ROOTS}")
    if len(languages) < MIN_LANGUAGES:
        blockers.append(f"language_count_below_training_floor:{len(languages)}<{MIN_LANGUAGES}")

    task_report: dict[str, Any] = {}
    for task, values in sorted(by_task.items()):
        counts = Counter(values)
        unique_count = len(counts)
        task_report[task] = {
            "row_count": len(values),
            "target_counts": dict(sorted(counts.items())),
            "unique_targets": unique_count,
            "entropy_bits": entropy(values),
        }
        required = MIN_TARGETS_BY_TASK.get(task)
        if required and unique_count < required:
            blockers.append(f"{task}:target_diversity_below_floor:{unique_count}<{required}")
        singleton_disallowed = DISALLOWED_SINGLETON_TARGETS.get(task)
        if unique_count == 1 and singleton_disallowed and next(iter(counts)) in singleton_disallowed:
            blockers.append(f"{task}:one_sided_target_shortcut:{next(iter(counts))}")

    root_report = {
        root: {
            "row_count": len(values),
            "unique_targets": len(set(values)),
            "target_counts": dict(sorted(Counter(values).items())),
        }
        for root, values in sorted(by_root.items())
    }

    passed = bool(rows) and not blockers
    summary = {
        "stage": stage,
        "input_stage": input_stage,
        "created_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "row_count": len(rows),
        "root_count": len(by_root),
        "language_counts": dict(sorted(languages.items())),
        "task_report": task_report,
        "root_report": root_report,
        "passed": passed,
        "blockers": blockers,
        "decision": (
            "passes_training_utility_gate_for_future_training_request"
            if passed
            else "block_training_request_until_counterfactual_diverse_rows_added"
        ),
        "training_allowed": False,
        "strict_eval_eligible": False,
        "promotion_eligible": False,
        "required_next_action": (
            "Add counterfactual state variants and more roots before any training. "
            "Needed examples include RUN_VERIFIER/CONTINUE before verifier execution, "
            "INSUFFICIENT_EVIDENCE or VERIFIER_REMOVED when verifier evidence is absent, "
            "and candidate_change_surface/source_surface positives where appropriate."
        ),
    }
    out.mkdir(parents=True, exist_ok=True)
    for path in (out / "summary.json", summary_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

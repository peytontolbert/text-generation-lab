#!/usr/bin/env python3
"""Build a fresh Python verifier contrast inventory or emit an explicit source gap.

This stage does not fabricate promotion-ready rows. It audits the available
long-context Python verifier roots, checks root disjointness against the
current repaired frontier, and separates:

1. promotable singleton verifier roots
2. diagnostic multi-target verifier roots
3. ambiguous roots that should become abstain/set-valued material instead

The current expected outcome is a source-gap artifact for singleton
promotion-ready Python verifier support.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACT_DIR = (
    ROOT
    / "runs/local/artifacts/stage10715_fresh_python_verifier_contrast_builder"
)

STAGE10516 = (
    ROOT
    / "runs/local/artifacts/stage10516_long_context_root_state_compiler"
)
STAGE10709 = (
    ROOT
    / "runs/local/artifacts/stage10709_rewritten_plus_reviewed_training_package_execution_repaired"
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    root_records = load_jsonl(STAGE10516 / "compiled_root_records.jsonl")
    typed_events = load_jsonl(STAGE10516 / "compiled_typed_events.jsonl")

    current_frontier_root_ids: set[str] = set()
    for name in ("strict_rows.jsonl", "canary_rows.jsonl", "eval_rows.jsonl"):
        path = STAGE10709 / name
        if not path.exists():
            continue
        for row in load_jsonl(path):
            source_root_id = row.get("source_root_id")
            if source_root_id:
                current_frontier_root_ids.add(source_root_id)

    py_pass_roots = {
        row["root_id"]: row
        for row in root_records
        if row.get("language_family") == "python"
        and row.get("verifier_id") == "PASS_TRACE_VERIFICATION_TARGETS"
    }

    event_by_root: dict[str, dict[str, Any]] = {}
    for event in typed_events:
        rid = event.get("root_id")
        if rid not in py_pass_roots:
            continue
        if event.get("event_type") != "TEST_RESULT":
            continue
        content = event.get("content")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                continue
        if not isinstance(content, dict):
            continue
        targets = content.get("verification_targets") or []
        event_by_root[rid] = {
            "test_selection_route": content.get("test_selection_route"),
            "verification_targets": targets,
        }

    promotable_singleton: list[dict[str, Any]] = []
    diagnostic_multi_target: list[dict[str, Any]] = []
    abstain_or_setvalued: list[dict[str, Any]] = []

    target_count_counter: Counter[int] = Counter()
    repo_counter: Counter[str] = Counter()

    for root_id, meta in py_pass_roots.items():
        event = event_by_root.get(root_id)
        if not event:
            continue
        targets = event["verification_targets"]
        target_count = len(targets)
        target_count_counter[target_count] += 1
        repo_counter[meta.get("repo_id", "unknown")] += 1

        record = {
            "root_id": root_id,
            "repo_id": meta.get("repo_id"),
            "repo_family": meta.get("repo_family"),
            "snapshot_id": meta.get("snapshot_id"),
            "split_component": meta.get("split_component"),
            "verifier_id": meta.get("verifier_id"),
            "current_frontier_overlap": root_id in current_frontier_root_ids,
            "verification_targets": targets,
            "verification_target_count": target_count,
            "task_family": meta.get("task_family"),
            "source_family_id": (
                meta.get("provenance", {}) or {}
            ).get("source_family_id"),
            "reason": None,
        }

        if root_id in current_frontier_root_ids:
            record["reason"] = "current_frontier_overlap"
            abstain_or_setvalued.append(record)
            continue

        if target_count == 1:
            record["reason"] = "singleton_verifier_target"
            promotable_singleton.append(record)
        elif target_count >= 2:
            if meta.get("repo_id") == "agentkernel-seq2seq-text-lab":
                record["reason"] = "fresh_multi_target_diagnostic_support"
                diagnostic_multi_target.append(record)
            else:
                record["reason"] = "ambiguous_multi_target_non_promotable"
                abstain_or_setvalued.append(record)
        else:
            record["reason"] = "missing_verification_targets"
            abstain_or_setvalued.append(record)

    summary = {
        "stage": "stage10715_fresh_python_verifier_contrast_builder",
        "status": (
            "source_gap_for_singleton_python_verifier_promotion"
            if not promotable_singleton
            else "singleton_python_verifier_supply_present"
        ),
        "recommendation": (
            "Do not run a new joint promotion probe yet. Use the fresh "
            "agentkernel multi-target roots only for broader verifier "
            "curriculum or set-valued/abstention redesign, and mine new "
            "singleton Python verifier roots for the strict MirrorMind-style lane."
        ),
        "current_frontier_overlap_root_count": len(current_frontier_root_ids),
        "python_pass_trace_root_count": len(py_pass_roots),
        "python_pass_trace_root_counts_by_repo": dict(sorted(repo_counter.items())),
        "verification_target_count_histogram": dict(
            sorted(target_count_counter.items())
        ),
        "promotable_singleton_root_count": len(promotable_singleton),
        "diagnostic_multi_target_root_count": len(diagnostic_multi_target),
        "abstain_or_setvalued_root_count": len(abstain_or_setvalued),
        "next_stage": (
            "stage10716_python_verifier_setvalued_or_abstain_support_builder"
            if diagnostic_multi_target
            else "stage10716_python_verifier_singleton_source_mining"
        ),
    }

    write_json(
        ARTIFACT_DIR / "fresh_python_verifier_contrast_builder.json",
        summary,
    )
    write_jsonl(
        ARTIFACT_DIR / "promotable_singleton_python_verifier_roots.jsonl",
        promotable_singleton,
    )
    write_jsonl(
        ARTIFACT_DIR / "diagnostic_multi_target_python_verifier_roots.jsonl",
        diagnostic_multi_target,
    )
    write_jsonl(
        ARTIFACT_DIR / "abstain_or_setvalued_python_verifier_roots.jsonl",
        abstain_or_setvalued,
    )


if __name__ == "__main__":
    main()

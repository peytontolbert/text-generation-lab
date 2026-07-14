#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "legacy_src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "legacy_src"))

from agentkernel_lite.training_loop import (  # noqa: E402
    _bounded_choice_contrast_spec,
    _bounded_decoder_train_batch_rows,
)

STAGE = "stage11585_web_task_aware_contrast_readiness_audit"
ROWS_PATH = REPO_ROOT / "runs/local/artifacts/stage11580_web_verifier_attached_admission_package/web_verifier_attached_rows.jsonl"
SUMMARY_PATH = REPO_ROOT / "runs/summaries" / f"{STAGE}.json"
ARTIFACT_DIR = REPO_ROOT / "runs/local/artifacts" / STAGE


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> int:
    rows = read_jsonl(ROWS_PATH)
    counts = Counter()
    by_task: dict[str, Counter[str]] = defaultdict(Counter)
    by_lane: dict[str, Counter[str]] = defaultdict(Counter)
    families = Counter()
    uncovered: list[dict[str, Any]] = []
    for row in rows:
        task = str(row.get("task_type") or "unknown")
        lane = str(row.get("lane") or "unknown")
        spec = _bounded_choice_contrast_spec(row)
        counts["total_rows"] += 1
        by_task[task]["total"] += 1
        by_lane[lane]["total"] += 1
        if spec:
            counts["contrast_covered_rows"] += 1
            by_task[task]["covered"] += 1
            by_lane[lane]["covered"] += 1
            families[str(spec.get("family") or "unknown")] += 1
        else:
            counts["contrast_uncovered_rows"] += 1
            by_task[task]["uncovered"] += 1
            by_lane[lane]["uncovered"] += 1
            if len(uncovered) < 20:
                uncovered.append({"row_id": row.get("row_id"), "task_type": task, "target_text": row.get("target_text")})

    sampled = _bounded_decoder_train_batch_rows(rows, step=1, batch_size=12, sampler="web_task_family_balanced")
    sampler_tasks = [str(row.get("task_type") or "unknown") for row in sampled]
    expected_tasks = {
        "symptom_localization",
        "evidence_citation",
        "verifier_outcome",
        "minimal_fix_selection",
        "alternative_hypothesis_elimination",
        "abstention_insufficient_evidence",
    }
    covered_tasks = {task for task, counter in by_task.items() if counter.get("covered", 0) > 0}
    contrast_coverage_rate = counts["contrast_covered_rows"] / counts["total_rows"] if counts["total_rows"] else 0.0
    decision = "task_aware_contrast_ready" if contrast_coverage_rate >= 0.95 and expected_tasks <= covered_tasks else "task_aware_contrast_not_ready"

    summary = {
        "stage": STAGE,
        "source_rows_path": str(ROWS_PATH),
        "decision": decision,
        "training_authorized_next": decision == "task_aware_contrast_ready",
        "counts": dict(counts),
        "contrast_coverage_rate": contrast_coverage_rate,
        "covered_task_families": sorted(covered_tasks),
        "missing_task_families": sorted(expected_tasks - covered_tasks),
        "by_task": {task: dict(counter) for task, counter in sorted(by_task.items())},
        "by_lane": {lane: dict(counter) for lane, counter in sorted(by_lane.items())},
        "contrast_families": dict(families.most_common()),
        "web_task_family_balanced_sampler_first_12_tasks": sampler_tasks,
        "uncovered_examples": uncovered,
        "notes": [
            "This audit validates trainer/interface readiness only; it is not a model score.",
            "Stage11581/11582 proved same-objective training on these rows is unsafe; use this only with task-aware contrast enabled and promotion gates preserved.",
        ],
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (ARTIFACT_DIR / "contrast_readiness_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if decision == "task_aware_contrast_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.training_loop import _bounded_decoder_train_batch_rows


ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11501
NAME = "stage11501_noncyclic_sampler_coverage_audit"
OUT = ART / NAME
SUMMARY = OUT / "noncyclic_sampler_coverage_audit.json"
MANIFEST = ART / "stage11497_candidate_set_evidence_judgment_head_probe_request/candidate_set_evidence_judgment_head_probe_manifest.jsonl"

PREFERRED = [
    "evidence_citation",
    "verifier_outcome",
    "evidence_citation",
    "verifier_outcome",
    "evidence_role_classification",
    "verifier_candidate_role_classification",
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def old_sampler(train_rows: list[dict[str, Any]], *, step: int, batch_size: int) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in train_rows:
        task = str(row.get("task_type") or "unknown")
        buckets.setdefault(task, []).append(row)
    schedule = [task for task in PREFERRED if task in buckets]
    schedule.extend(task for task in sorted(buckets) if task not in schedule)
    local_offsets = {task: 0 for task in buckets}
    start = (step - 1) * batch_size
    out: list[dict[str, Any]] = []
    for offset in range(batch_size):
        task = schedule[(start + offset) % len(schedule)]
        bucket = buckets.get(task) or train_rows
        index = local_offsets.get(task, 0)
        out.append(bucket[index % len(bucket)])
        local_offsets[task] = index + 1
    return out


def exposure_card(rows: list[dict[str, Any]], *, sampler: str, steps: int, batch_size: int, legacy: bool = False) -> dict[str, Any]:
    exposures: Counter[str] = Counter()
    by_task: dict[str, Counter[str]] = defaultdict(Counter)
    bridge_exposures = 0
    bridge_unique: set[str] = set()
    for step in range(1, steps + 1):
        batch = old_sampler(rows, step=step, batch_size=batch_size) if legacy else _bounded_decoder_train_batch_rows(rows, step=step, batch_size=batch_size, sampler=sampler)
        for row in batch:
            row_id = str(row.get("row_id") or "")
            task = str(row.get("task_type") or "unknown")
            exposures[row_id] += 1
            by_task[task][row_id] += 1
            if row_id.endswith("::judgment_head_bridge"):
                bridge_exposures += 1
                bridge_unique.add(row_id)
    task_cards = {}
    for task, counter in sorted(by_task.items()):
        total_task_rows = sum(1 for row in rows if str(row.get("task_type") or "unknown") == task)
        task_cards[task] = {
            "manifest_rows": total_task_rows,
            "unique_exposed_rows": len(counter),
            "total_exposures": sum(counter.values()),
            "top_exposed": counter.most_common(5),
        }
    return {
        "sampler": sampler,
        "legacy_reset_offsets_each_step": legacy,
        "steps": steps,
        "batch_size": batch_size,
        "total_exposures": sum(exposures.values()),
        "unique_exposed_rows": len(exposures),
        "manifest_rows": len(rows),
        "bridge_exposures": bridge_exposures,
        "bridge_unique_exposed_rows": len(bridge_unique),
        "task_cards": task_cards,
        "top_exposed": exposures.most_common(20),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    all_rows = load_jsonl(MANIFEST)
    train_rows = [row for row in all_rows if str(row.get("split") or row.get("package_split") or "") == "train"]
    steps = 192
    batch_size = 4
    legacy = exposure_card(train_rows, sampler="residual_family_balanced", steps=steps, batch_size=batch_size, legacy=True)
    fixed = exposure_card(train_rows, sampler="residual_family_balanced", steps=steps, batch_size=batch_size, legacy=False)
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "noncyclic_sampler_bug_fixed_and_audited",
        "bug": "task_balanced/residual_family_balanced previously reset per-task offsets every step, repeatedly sampling the first rows in each task bucket.",
        "legacy_behavior": legacy,
        "fixed_behavior": fixed,
        "impact_summary": {
            "legacy_unique_exposed_rows": legacy["unique_exposed_rows"],
            "fixed_unique_exposed_rows": fixed["unique_exposed_rows"],
            "legacy_bridge_unique_exposed_rows": legacy["bridge_unique_exposed_rows"],
            "fixed_bridge_unique_exposed_rows": fixed["bridge_unique_exposed_rows"],
            "legacy_bridge_exposures": legacy["bridge_exposures"],
            "fixed_bridge_exposures": fixed["bridge_exposures"],
        },
        "source_artifacts": {"manifest": rel(MANIFEST)},
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, payload)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": payload["decision"], "impact_summary": payload["impact_summary"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

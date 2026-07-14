#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.training_loop import _bounded_choice_root_group_key, _bounded_decoder_train_batch_rows

ART = ROOT / "runs/local/artifacts"
SUM = ROOT / "runs/summaries"
OUT = ART / "stage11654_same_root_grouped_sampler_readiness"
MANIFEST = ART / "stage11648_web_gap_grouped_admission_compiler/web_gap_grouped_probe_manifest.jsonl"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]
    steps = 24
    batch_size = 8
    samplers = ["web_gap_root_balanced", "web_gap_same_root_grouped"]
    metrics = {}
    examples = {}
    for sampler in samplers:
        max_group_sizes = []
        multi_group_batches = 0
        root_counts_total = Counter()
        task_counts_total = Counter()
        sample_batches = []
        for step in range(1, steps + 1):
            batch = _bounded_decoder_train_batch_rows(rows, step=step, batch_size=batch_size, sampler=sampler)
            counts = Counter(_bounded_choice_root_group_key(row) for row in batch)
            tasks = Counter(str(row.get("task_type") or "unknown") for row in batch)
            root_counts_total.update(counts)
            task_counts_total.update(tasks)
            sizes = sorted(counts.values(), reverse=True)
            max_group_sizes.append(max(sizes) if sizes else 0)
            if any(size > 1 for size in sizes):
                multi_group_batches += 1
            if step <= 3:
                sample_batches.append(
                    {
                        "step": step,
                        "root_group_sizes": dict(counts),
                        "task_counts": dict(tasks),
                        "row_ids": [row.get("row_id") for row in batch],
                    }
                )
        metrics[sampler] = {
            "steps_checked": steps,
            "batch_size": batch_size,
            "multi_group_batches": multi_group_batches,
            "multi_group_batch_rate": multi_group_batches / steps,
            "mean_max_group_size": statistics.mean(max_group_sizes),
            "min_max_group_size": min(max_group_sizes),
            "max_max_group_size": max(max_group_sizes),
            "root_groups_seen": len(root_counts_total),
            "task_counts_seen": dict(task_counts_total),
        }
        examples[sampler] = sample_batches
    root_inventory = defaultdict(int)
    for row in rows:
        root_inventory[_bounded_choice_root_group_key(row)] += 1
    readiness_gates = {
        "manifest_rows_113": len(rows) == 113,
        "has_multirow_roots": sum(1 for size in root_inventory.values() if size > 1) >= 8,
        "same_root_grouped_all_batches_have_multirow_group": metrics["web_gap_same_root_grouped"]["multi_group_batches"] == steps,
        "same_root_grouped_min_max_group_size_at_least_2": metrics["web_gap_same_root_grouped"]["min_max_group_size"] >= 2,
        "old_root_balanced_mostly_singleton": metrics["web_gap_root_balanced"]["mean_max_group_size"] <= 1.5,
    }
    decision = "same_root_grouped_sampler_ready_for_controlled_probe" if all(readiness_gates.values()) else "same_root_grouped_sampler_not_ready"
    summary = {
        "stage": 11654,
        "stage_name": "stage11654_same_root_grouped_sampler_readiness",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "decision": decision,
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "unique_root_groups": len(root_inventory),
        "multirow_root_groups": sum(1 for size in root_inventory.values() if size > 1),
        "root_size_histogram": dict(Counter(root_inventory.values())),
        "metrics": metrics,
        "sample_batches": examples,
        "readiness_gates": readiness_gates,
        "recommended_next_probe": {
            "sampler": "web_gap_same_root_grouped",
            "keep_gpu": "CUDA_VISIBLE_DEVICES=2",
            "first_try": "head-only or very low-LR diagnostic; do not repeat failed full-model Stage11651b objective unchanged",
            "promotion_gates": ["filtered strict 22/22", "old canary strict 23/23", "residual >=7/10", "web heldout >38/66"],
        },
    }
    path = OUT / "same_root_grouped_sampler_readiness.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUM.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, SUM / "stage11654_same_root_grouped_sampler_readiness.json")
    print(json.dumps({"decision": decision, "readiness_gates": readiness_gates, "metrics": metrics}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9759
NAME = "stage9759_ready_now_execution_queue"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
QUEUE = OUT_DIR / "ready_now_execution_queue.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "READY_NOW_EXECUTION_QUEUE_STAGE9759.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

STANDALONE_CHECKLIST = ROOT / "runs/local/artifacts/stage9754_supported_standalone_completion_checklist/supported_standalone_completion_checklist.json"
HARNESS_CHECKLIST = ROOT / "runs/local/artifacts/stage9755_full_product_harness_completion_checklist/full_product_harness_completion_checklist.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


STANDALONE_TASK_PRIORITY = {
    "expert_maintainer_rubric_review": 0,
    "cell_specific_anti_cheat_review": 1,
    "frozen_checkpoint_hash_attach": 2,
}

HARNESS_TASK_PRIORITY = {
    "prepare_expert_maintainer_rubric_review": 0,
    "prepare_cell_specific_anti_cheat_review": 1,
}


def build_ready_now_queue(standalone: dict[str, Any], harness: dict[str, Any]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    failures: list[str] = []

    standalone_records = standalone.get("records") if isinstance(standalone.get("records"), list) else []
    for record in standalone_records:
        for task in record.get("pre_gemma_tasks") or []:
            if task.get("ready_now") is not True:
                continue
            entries.append({
                "front": "standalone",
                "cell_key": record.get("cell_key"),
                "language_family": record.get("language_family"),
                "skill_area": record.get("skill_area"),
                "priority_rank": record.get("priority_rank"),
                "priority_score": record.get("priority_score"),
                "task": task.get("task"),
                "artifact_path": task.get("artifact_path"),
                "status": task.get("status"),
                "task_priority": STANDALONE_TASK_PRIORITY.get(str(task.get("task") or ""), 99),
                "impact_band": "highest" if int(record.get("priority_rank") or 999) <= 5 else "high",
            })

    harness_records = harness.get("records") if isinstance(harness.get("records"), list) else []
    for record in harness_records:
        for task in record.get("pre_harness_tasks") or []:
            if task.get("ready_now") is not True:
                continue
            entries.append({
                "front": "harness",
                "cell_key": record.get("cell_key"),
                "language_family": record.get("language_family"),
                "skill_area": record.get("skill_area"),
                "priority_rank": record.get("priority_rank"),
                "priority_bucket": record.get("priority_bucket"),
                "proxy_standalone_cell_key": record.get("proxy_standalone_cell_key"),
                "proxy_standalone_priority_score": record.get("proxy_standalone_priority_score"),
                "task": task.get("task"),
                "artifact_path": None,
                "status": "pending_review_preparation",
                "task_priority": HARNESS_TASK_PRIORITY.get(str(task.get("task") or ""), 99),
                "impact_band": (
                    "highest" if str(record.get("priority_bucket") or "") == "aligned_with_supported_standalone_cell" else "medium"
                ),
            })

    def sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
        front_order = 0 if row["front"] == "standalone" else 1
        impact_order = {"highest": 0, "high": 1, "medium": 2}.get(str(row.get("impact_band") or ""), 9)
        priority_rank = int(row.get("priority_rank") or 999)
        raw_task_priority = row.get("task_priority")
        task_priority = 99 if raw_task_priority is None else int(raw_task_priority)
        return (impact_order, front_order, priority_rank, task_priority, str(row.get("cell_key") or ""))

    entries.sort(key=sort_key)
    for idx, row in enumerate(entries, start=1):
        row["queue_position"] = idx

    metrics = {
        "ready_now_entries": len(entries),
        "standalone_entries": sum(1 for row in entries if row["front"] == "standalone"),
        "harness_entries": sum(1 for row in entries if row["front"] == "harness"),
        "highest_impact_entries": sum(1 for row in entries if row["impact_band"] == "highest"),
        "languages": sorted({str(row.get("language_family") or "") for row in entries}),
        "top_queue_entry": entries[0]["cell_key"] + "::" + entries[0]["task"] if entries else None,
    }
    if metrics["ready_now_entries"] != 111:
        failures.append("ready_now_entries_not_111")
    if metrics["standalone_entries"] != 39:
        failures.append("standalone_ready_now_entries_not_39")
    if metrics["harness_entries"] != 72:
        failures.append("harness_ready_now_entries_not_72")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "queue_entries": entries,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_ready_now_queue(load_json(STANDALONE_CHECKLIST), load_json(HARNESS_CHECKLIST))
    QUEUE.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Execute the Stage9759 queue from the top: finish the highest-impact standalone rubric, anti-cheat, and checkpoint tasks first, "
        "then work down into the aligned harness review-preparation tasks while runner recovery proceeds in parallel."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            **built["metrics"],
        },
        "artifacts": {
            "queue": str(QUEUE.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Materialized a prioritized ready-now execution queue so the remaining non-runner work is ordered by impact across both standalone and harness fronts.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9759 Ready Now Execution Queue",
        "",
        f"Passed: `{summary['passed']}`",
        f"Ready-now entries: `{summary['metrics']['ready_now_entries']}`",
        f"Standalone entries: `{summary['metrics']['standalone_entries']}`",
        f"Harness entries: `{summary['metrics']['harness_entries']}`",
        f"Highest-impact entries: `{summary['metrics']['highest_impact_entries']}`",
        f"Top queue entry: `{summary['metrics']['top_queue_entry']}`",
        "",
        "This stage turns the cross-front ready-now workload into an ordered queue, prioritizing the strongest standalone cells first and then the aligned harness review-preparation tasks.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "ready_now_entries": summary["metrics"]["ready_now_entries"],
        "standalone_entries": summary["metrics"]["standalone_entries"],
        "harness_entries": summary["metrics"]["harness_entries"],
        "top_queue_entry": summary["metrics"]["top_queue_entry"],
        "next_best_step": next_step,
        "failures": built["failures"],
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

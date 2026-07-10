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
STAGE = 9755
NAME = "stage9755_full_product_harness_completion_checklist"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CHECKLIST = OUT_DIR / "full_product_harness_completion_checklist.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FULL_PRODUCT_HARNESS_COMPLETION_CHECKLIST_STAGE9755.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

QUEUE = ROOT / "runs/local/artifacts/stage9749_full_product_harness_gemma_queue/full_product_harness_gemma_queue.json"
RUNBOOK = ROOT / "runs/local/artifacts/stage9750_deferred_comparison_execution_runbook/deferred_comparison_execution_runbook.json"


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


def build_checklist(queue: dict[str, Any], runbook: dict[str, Any]) -> dict[str, Any]:
    entries = queue.get("queue_entries") if isinstance(queue.get("queue_entries"), list) else []
    harness_front = runbook.get("execution_fronts", {}).get("full_product_harness_comparison", {})
    runner_missing = harness_front.get("runner_status") == "missing_harness_runner_surface"
    records: list[dict[str, Any]] = []
    failures: list[str] = []

    for entry in entries:
        cell_key = str(entry.get("cell_key") or "")
        pre_harness_tasks = [
            {
                "task": "recover_or_authorize_harness_runner_surface",
                "ready_now": False,
                "completed": False,
                "blocked_by": "missing_harness_runner_surface",
            },
            {
                "task": "prepare_cell_specific_anti_cheat_review",
                "ready_now": True,
                "completed": False,
                "blocked_by": None,
            },
            {
                "task": "prepare_expert_maintainer_rubric_review",
                "ready_now": True,
                "completed": False,
                "blocked_by": None,
            },
        ]
        post_harness_tasks = [
            {
                "task": "record_harness_run_id",
                "ready_now": False,
                "completed": False,
                "blocked_by": "missing_harness_runner_surface",
            },
            {
                "task": "capture_same_task_pack_as_gemma12b",
                "ready_now": False,
                "completed": False,
                "blocked_by": "missing_harness_runner_surface",
            },
            {
                "task": "collect_tool_trace_spans",
                "ready_now": False,
                "completed": False,
                "blocked_by": "missing_harness_runner_surface",
            },
            {
                "task": "collect_verifier_results",
                "ready_now": False,
                "completed": False,
                "blocked_by": "missing_harness_runner_surface",
            },
            {
                "task": "collect_patch_minimality_or_abstain_scores",
                "ready_now": False,
                "completed": False,
                "blocked_by": "missing_harness_runner_surface",
            },
            {
                "task": "execute_same_task_pack_gemma12b_comparison",
                "ready_now": False,
                "completed": False,
                "blocked_by": "missing_harness_runner_surface",
            },
            {
                "task": "claim_ready_merge",
                "ready_now": False,
                "completed": False,
                "blocked_by": "requires_harness_and_gemma_evidence",
            },
        ]
        records.append({
            "cell_key": cell_key,
            "priority_rank": entry.get("priority_rank"),
            "priority_bucket": entry.get("priority_bucket"),
            "proxy_standalone_cell_key": entry.get("proxy_standalone_cell_key"),
            "proxy_standalone_priority_score": entry.get("proxy_standalone_priority_score"),
            "language_family": entry.get("language_family"),
            "skill_area": entry.get("skill_area"),
            "ready_for_harness_when_authorized": entry.get("ready_for_harness_when_authorized") is True,
            "harness_runner_missing": runner_missing,
            "pre_harness_tasks": pre_harness_tasks,
            "post_harness_tasks": post_harness_tasks,
            "pre_harness_ready_now_count": sum(1 for task in pre_harness_tasks if task["ready_now"]),
            "post_harness_ready_now_count": sum(1 for task in post_harness_tasks if task["ready_now"]),
        })

    records.sort(key=lambda row: (int(row.get("priority_rank") or 999), str(row.get("cell_key") or "")))
    metrics = {
        "queue_entries": len(entries),
        "checklist_rows": len(records),
        "pre_harness_tasks_total": sum(len(row["pre_harness_tasks"]) for row in records),
        "pre_harness_tasks_ready_now": sum(row["pre_harness_ready_now_count"] for row in records),
        "post_harness_tasks_total": sum(len(row["post_harness_tasks"]) for row in records),
        "post_harness_tasks_ready_now": sum(row["post_harness_ready_now_count"] for row in records),
        "cells_ready_for_harness_when_authorized": sum(1 for row in records if row["ready_for_harness_when_authorized"]),
        "cells_blocked_on_harness_runner": sum(1 for row in records if row["harness_runner_missing"]),
        "priority_buckets": dict(sorted((queue.get("metrics", {}).get("priority_buckets") or {}).items())),
        "top_priority_cell": records[0]["cell_key"] if records else None,
        "languages": sorted({str(row.get("language_family") or "") for row in records}),
        "skills": sorted({str(row.get("skill_area") or "") for row in records}),
    }
    if metrics["queue_entries"] != 36:
        failures.append("queue_entries_not_36")
    if metrics["checklist_rows"] != 36:
        failures.append("checklist_rows_not_36")
    if metrics["pre_harness_tasks_total"] != 108:
        failures.append("pre_harness_task_count_mismatch")
    if metrics["pre_harness_tasks_ready_now"] != 72:
        failures.append("pre_harness_ready_now_count_mismatch")
    if metrics["post_harness_tasks_total"] != 252:
        failures.append("post_harness_task_count_mismatch")
    if metrics["post_harness_tasks_ready_now"] != 0:
        failures.append("post_harness_ready_now_count_mismatch")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "records": records,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_checklist(load_json(QUEUE), load_json(RUNBOOK))
    CHECKLIST.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Complete the 72 harness-side review-preparation tasks that are already ready now, then recover or authorize the "
        "full-product harness runner so the remaining 252 harness execution and merge tasks can proceed."
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
            "checklist": str(CHECKLIST.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Materialized a harness-side completion checklist that separates review-preparation work from the much larger block of tasks still gated on a missing harness runner surface.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9755 Full Product Harness Completion Checklist",
        "",
        f"Passed: `{summary['passed']}`",
        f"Checklist rows: `{summary['metrics']['checklist_rows']}`",
        f"Pre-harness tasks total: `{summary['metrics']['pre_harness_tasks_total']}`",
        f"Pre-harness tasks ready now: `{summary['metrics']['pre_harness_tasks_ready_now']}`",
        f"Post-harness tasks total: `{summary['metrics']['post_harness_tasks_total']}`",
        f"Cells blocked on harness runner: `{summary['metrics']['cells_blocked_on_harness_runner']}`",
        "",
        "This stage makes the harness frontier explicit across all 36 cells: review preparation can start now, but harness execution, trace capture, verifier collection, patch-minimality scoring, Gemma comparison, and final merge are still blocked on the missing harness runner surface.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "pre_harness_tasks_total": summary["metrics"]["pre_harness_tasks_total"],
        "pre_harness_tasks_ready_now": summary["metrics"]["pre_harness_tasks_ready_now"],
        "post_harness_tasks_total": summary["metrics"]["post_harness_tasks_total"],
        "cells_blocked_on_harness_runner": summary["metrics"]["cells_blocked_on_harness_runner"],
        "top_priority_cell": summary["metrics"]["top_priority_cell"],
        "next_best_step": next_step,
        "failures": built["failures"],
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

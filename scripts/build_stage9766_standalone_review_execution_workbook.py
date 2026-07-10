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
STAGE = 9766
NAME = "stage9766_standalone_review_execution_workbook"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
WORKBOOK = OUT_DIR / "standalone_review_execution_workbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "STANDALONE_REVIEW_EXECUTION_WORKBOOK_STAGE9766.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

QUEUE = ROOT / "runs/local/artifacts/stage9761_truthful_ready_now_execution_queue/truthful_ready_now_execution_queue.json"
PACKETS = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/supported_standalone_review_packets.jsonl"
DRAFTS = ROOT / "runs/local/artifacts/stage9765_standalone_review_evidence_drafts/standalone_review_evidence_drafts_manifest.json"
HARNESS_PREP_AUDIT = ROOT / "runs/local/artifacts/stage9762_harness_prep_completion_audit/harness_prep_completion_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


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


def build_workbook(
    queue: dict[str, Any],
    packets: list[dict[str, Any]],
    drafts: dict[str, Any],
    harness_prep_audit: dict[str, Any],
) -> dict[str, Any]:
    queue_rows = queue.get("queue_entries") if isinstance(queue.get("queue_entries"), list) else []
    standalone_rows = [row for row in queue_rows if row.get("front") == "standalone"]
    packet_index = {str(row.get("cell_key") or ""): row for row in packets}
    draft_rows = drafts.get("rows") if isinstance(drafts.get("rows"), list) else []
    draft_index = {str(row.get("cell_key") or ""): row for row in draft_rows}
    harness_metrics = harness_prep_audit.get("metrics") if isinstance(harness_prep_audit.get("metrics"), dict) else {}

    workbook_rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for task_row in standalone_rows:
        cell_key = str(task_row.get("cell_key") or "")
        packet = packet_index.get(cell_key)
        draft = draft_index.get(cell_key)
        if packet is None:
            failures.append(f"missing_packet:{cell_key}")
            continue
        if draft is None:
            failures.append(f"missing_draft:{cell_key}")
            continue
        same_surface = packet.get("same_surface_packet") if isinstance(packet.get("same_surface_packet"), dict) else {}
        supports = packet.get("supporting_evidence_refs") if isinstance(packet.get("supporting_evidence_refs"), list) else []
        workbook_rows.append({
            "queue_position": task_row.get("queue_position"),
            "task": task_row.get("task"),
            "task_priority": task_row.get("task_priority"),
            "cell_key": cell_key,
            "language_family": task_row.get("language_family"),
            "skill_area": task_row.get("skill_area"),
            "impact_band": task_row.get("impact_band"),
            "priority_rank": task_row.get("priority_rank"),
            "priority_score": task_row.get("priority_score"),
            "same_surface_hash_100m": same_surface.get("surface_hash"),
            "same_surface_eval_exact": same_surface.get("eval_exact"),
            "same_surface_strict_exact": same_surface.get("strict_exact"),
            "same_surface_split_counts": same_surface.get("split_counts"),
            "draft_artifact_path": (
                draft.get("draft_rubric_path")
                if task_row.get("task") == "expert_maintainer_rubric_review"
                else draft.get("draft_anti_cheat_path")
            ),
            "target_stub_path": task_row.get("artifact_path"),
            "packet_dir": packet.get("review_packet_paths", {}).get("packet_dir"),
            "supporting_evidence_paths": [row.get("path") for row in supports if row.get("path")],
            "required_human_action": (
                "assign rubric subskill judgments and failure traces"
                if task_row.get("task") == "expert_maintainer_rubric_review"
                else "complete cell-specific anti-cheat judgments and notes for all challenge families"
            ),
            "status": task_row.get("status"),
        })

    workbook_rows.sort(key=lambda row: int(row.get("queue_position") or 9999))
    metrics = {
        "standalone_review_tasks": len(workbook_rows),
        "unique_cells": len({row["cell_key"] for row in workbook_rows}),
        "rubric_tasks": sum(1 for row in workbook_rows if row["task"] == "expert_maintainer_rubric_review"),
        "anti_cheat_tasks": sum(1 for row in workbook_rows if row["task"] == "cell_specific_anti_cheat_review"),
        "top_queue_entry": (
            workbook_rows[0]["cell_key"] + "::" + workbook_rows[0]["task"]
            if workbook_rows else None
        ),
        "harness_ready_now_after_prep_completion": int(harness_metrics.get("remaining_harness_entries_after_completion") or 0),
    }
    if metrics["standalone_review_tasks"] != 26:
        failures.append("standalone_review_tasks_not_26")
    if metrics["unique_cells"] != 13:
        failures.append("unique_cells_not_13")
    if metrics["rubric_tasks"] != 13:
        failures.append("rubric_tasks_not_13")
    if metrics["anti_cheat_tasks"] != 13:
        failures.append("anti_cheat_tasks_not_13")
    if metrics["harness_ready_now_after_prep_completion"] != 0:
        failures.append("harness_ready_now_after_prep_completion_not_0")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "rows": workbook_rows,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_workbook(
        load_json(QUEUE),
        load_jsonl(PACKETS),
        load_json(DRAFTS),
        load_json(HARNESS_PREP_AUDIT),
    )
    WORKBOOK.write_text(json.dumps({
        "stage": STAGE,
        "name": NAME,
        "passed": built["passed"],
        "metrics": built["metrics"],
        "rows": built["rows"],
        "authority": dict(AUTHORITY_CLOSED),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Work the Stage9766 workbook top to bottom: open the draft artifact path for the current task, review against the same-surface packet evidence, and write the final judgment into the target stub path."
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
            "workbook": str(WORKBOOK.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Materialized a queue-ordered standalone review workbook that maps each of the 26 remaining tasks to its evidence draft, final stub target, same-surface scores and hashes, and the exact human judgment still required.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9766 Standalone Review Execution Workbook",
        "",
        f"Passed: `{summary['passed']}`",
        f"Standalone review tasks: `{summary['metrics']['standalone_review_tasks']}`",
        f"Unique cells: `{summary['metrics']['unique_cells']}`",
        f"Rubric tasks: `{summary['metrics']['rubric_tasks']}`",
        f"Anti-cheat tasks: `{summary['metrics']['anti_cheat_tasks']}`",
        f"Top queue entry: `{summary['metrics']['top_queue_entry']}`",
        "",
        "This stage packages the remaining standalone review work into one execution workbook. Each row points to the evidence-backed draft artifact, the final stub file that must be completed, the same-surface 100M hash and scores, and the exact human action still required.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "standalone_review_tasks": summary["metrics"]["standalone_review_tasks"],
        "unique_cells": summary["metrics"]["unique_cells"],
        "rubric_tasks": summary["metrics"]["rubric_tasks"],
        "anti_cheat_tasks": summary["metrics"]["anti_cheat_tasks"],
        "top_queue_entry": summary["metrics"]["top_queue_entry"],
        "failures": built["failures"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

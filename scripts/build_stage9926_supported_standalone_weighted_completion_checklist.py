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
STAGE = 9926
NAME = "stage9926_supported_standalone_weighted_completion_checklist"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CHECKLIST = OUT_DIR / "supported_standalone_weighted_completion_checklist.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUPPORTED_STANDALONE_WEIGHTED_COMPLETION_CHECKLIST_STAGE9926.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
PACKETS = ROOT / "runs/local/artifacts/stage9925_supported_standalone_weighted_frontier_refresh/supported_standalone_weighted_frontier_packets.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_checklist(packets: list[dict[str, Any]]) -> dict[str, Any]:
    records = []
    failures: list[str] = []
    for packet in packets:
        cell_key = str(packet.get("cell_key") or "")
        weighted_frontier = "weighted hardened multilingual" in str(packet.get("priority_reason") or "") and str(packet.get("skill_area") or "") == "edit_localization"
        if weighted_frontier:
            pre = [
                {"task": "expert_maintainer_rubric_review", "ready_now": True, "completed": False, "status": "pending_human_review"},
                {"task": "cell_specific_anti_cheat_review", "ready_now": True, "completed": False, "status": "pending_cell_specific_review"},
            ]
            post = []
        else:
            pre = [
                {"task": "expert_maintainer_rubric_review", "ready_now": True, "completed": False, "status": "pending_human_review"},
                {"task": "cell_specific_anti_cheat_review", "ready_now": True, "completed": False, "status": "pending_cell_specific_review"},
                {"task": "frozen_checkpoint_hash_attach", "ready_now": True, "completed": False, "status": "pending_checkpoint_or_export_hash"},
            ]
            post = [
                {"task": "same_surface_gemma_execution", "ready_now": False, "completed": False, "status": "missing_gemma_runner_surface"},
                {"task": "claim_ready_merge", "ready_now": False, "completed": False, "status": "not_mergeable_until_all_evidence_is_real"},
            ]
        records.append({
            "cell_key": cell_key,
            "priority_rank": packet.get("priority_rank"),
            "priority_score": packet.get("priority_score"),
            "language_family": packet.get("language_family"),
            "skill_area": packet.get("skill_area"),
            "weighted_frontier_cell": weighted_frontier,
            "pre_gemma_tasks": pre,
            "post_gemma_tasks": post,
            "pre_gemma_total_count": len(pre),
            "post_gemma_total_count": len(post),
            "ready_for_human_review_now": True,
            "blocked_on_gemma_runner": not weighted_frontier,
        })
    records.sort(key=lambda row: (int(row.get("priority_rank") or 999), str(row.get("cell_key") or "")))
    metrics = {
        "checklist_rows": len(records),
        "weighted_frontier_cells": sum(1 for row in records if row["weighted_frontier_cell"]),
        "pre_gemma_tasks_total": sum(row["pre_gemma_total_count"] for row in records),
        "post_gemma_tasks_total": sum(row["post_gemma_total_count"] for row in records),
        "cells_blocked_on_gemma_runner": sum(1 for row in records if row["blocked_on_gemma_runner"]),
        "top_priority_cell": records[0]["cell_key"] if records else None,
    }
    if metrics["checklist_rows"] != 13:
        failures.append("checklist_rows_not_13")
    if metrics["weighted_frontier_cells"] != 4:
        failures.append("weighted_frontier_cells_not_4")
    return {"passed": not failures, "failures": failures, "metrics": metrics, "records": records, "authority": dict(AUTHORITY_CLOSED)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_checklist(load_jsonl(PACKETS))
    CHECKLIST.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Work the four weighted-frontier standalone winner cells first: only human rubric and anti-cheat review remain there, while the rest of the legacy standalone inventory still depends on extra Gemma or checkpoint work."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"checklist": str(CHECKLIST.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Materialized a refreshed standalone completion checklist where the four weighted-frontier edit-localization cells are no longer blocked on Gemma execution and only require human review signoff.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9926 Supported Standalone Weighted Completion Checklist",
        "",
        f"Passed: `{summary['passed']}`",
        f"Weighted frontier cells: `{built['metrics']['weighted_frontier_cells']}`",
        f"Pre-Gemma tasks total: `{built['metrics']['pre_gemma_tasks_total']}`",
        f"Post-Gemma tasks total: `{built['metrics']['post_gemma_tasks_total']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

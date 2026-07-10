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
STAGE = 9754
NAME = "stage9754_supported_standalone_completion_checklist"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CHECKLIST = OUT_DIR / "supported_standalone_completion_checklist.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUPPORTED_STANDALONE_COMPLETION_CHECKLIST_STAGE9754.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

PACKETS = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/supported_standalone_review_packets.jsonl"
STUBS = ROOT / "runs/local/artifacts/stage9753_supported_standalone_review_stub_files/supported_standalone_review_stub_manifest.json"


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


def _read_json(rel_path: str) -> dict[str, Any]:
    return json.loads((ROOT / rel_path).read_text(encoding="utf-8"))


def _read_text(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _checkpoint_present(checkpoint_text: str) -> bool:
    for line in checkpoint_text.splitlines():
        if line.startswith("frozen_export_or_checkpoint_hash="):
            return bool(line.partition("=")[2].strip())
    return False


def build_checklist(packets: list[dict[str, Any]], stub_manifest: dict[str, Any]) -> dict[str, Any]:
    manifest_rows = stub_manifest.get("rows") if isinstance(stub_manifest.get("rows"), list) else []
    manifest_index = {str(row.get("cell_key") or ""): row for row in manifest_rows}
    records: list[dict[str, Any]] = []
    failures: list[str] = []

    for packet in packets:
        cell_key = str(packet.get("cell_key") or "")
        stub_row = manifest_index.get(cell_key)
        if stub_row is None:
            failures.append(f"missing_stub_manifest_row:{cell_key}")
            continue
        rubric = _read_json(str(stub_row["expert_maintainer_rubric_scores"]))
        anti = _read_json(str(stub_row["anti_cheat_cards"]))
        gemma = _read_json(str(stub_row["same_prompt_surface_gemma12b_outputs"]))
        checkpoint = _read_text(str(stub_row["frozen_export_or_checkpoint_hash"]))
        checkpoint_present = _checkpoint_present(checkpoint)

        pre_gemma_tasks = [
            {
                "task": "expert_maintainer_rubric_review",
                "ready_now": True,
                "completed": rubric.get("passed") is True,
                "status": rubric.get("status"),
                "artifact_path": stub_row["expert_maintainer_rubric_scores"],
            },
            {
                "task": "cell_specific_anti_cheat_review",
                "ready_now": True,
                "completed": anti.get("passed") is True,
                "status": anti.get("status"),
                "artifact_path": stub_row["anti_cheat_cards"],
            },
            {
                "task": "frozen_checkpoint_hash_attach",
                "ready_now": True,
                "completed": checkpoint_present,
                "status": "complete" if checkpoint_present else "pending_checkpoint_or_export_hash",
                "artifact_path": stub_row["frozen_export_or_checkpoint_hash"],
            },
        ]
        post_gemma_tasks = [
            {
                "task": "same_surface_gemma_execution",
                "ready_now": False,
                "blocked_by": "missing_gemma_runner_surface",
                "completed": gemma.get("score_gemma12b") is not None,
                "status": gemma.get("status"),
                "artifact_path": stub_row["same_prompt_surface_gemma12b_outputs"],
            },
            {
                "task": "claim_ready_merge",
                "ready_now": False,
                "blocked_by": "requires_gemma_plus_completed_pre_gemma_reviews",
                "completed": False,
                "status": "not_mergeable_until_all_evidence_is_real",
                "artifact_path": packet["review_packet_paths"]["packet_dir"],
            },
        ]
        records.append({
            "cell_key": cell_key,
            "priority_rank": packet.get("priority_rank"),
            "priority_score": packet.get("priority_score"),
            "language_family": packet.get("language_family"),
            "skill_area": packet.get("skill_area"),
            "pre_gemma_tasks": pre_gemma_tasks,
            "post_gemma_tasks": post_gemma_tasks,
            "pre_gemma_completion_count": sum(1 for task in pre_gemma_tasks if task["completed"]),
            "pre_gemma_total_count": len(pre_gemma_tasks),
            "post_gemma_completion_count": sum(1 for task in post_gemma_tasks if task["completed"]),
            "post_gemma_total_count": len(post_gemma_tasks),
            "ready_for_human_review_now": True,
            "blocked_on_gemma_runner": True,
        })

    records.sort(key=lambda row: (int(row.get("priority_rank") or 999), str(row.get("cell_key") or "")))
    metrics = {
        "packets": len(packets),
        "checklist_rows": len(records),
        "pre_gemma_tasks_total": sum(row["pre_gemma_total_count"] for row in records),
        "pre_gemma_tasks_completed": sum(row["pre_gemma_completion_count"] for row in records),
        "post_gemma_tasks_total": sum(row["post_gemma_total_count"] for row in records),
        "post_gemma_tasks_completed": sum(row["post_gemma_completion_count"] for row in records),
        "cells_ready_for_human_review_now": sum(1 for row in records if row["ready_for_human_review_now"]),
        "cells_blocked_on_gemma_runner": sum(1 for row in records if row["blocked_on_gemma_runner"]),
        "top_priority_cell": records[0]["cell_key"] if records else None,
        "languages": sorted({str(row.get("language_family") or "") for row in records}),
        "skills": sorted({str(row.get("skill_area") or "") for row in records}),
    }
    if metrics["packets"] != 13:
        failures.append("packets_not_13")
    if metrics["checklist_rows"] != 13:
        failures.append("checklist_rows_not_13")
    if metrics["pre_gemma_tasks_total"] != 39:
        failures.append("pre_gemma_task_count_mismatch")
    if metrics["post_gemma_tasks_total"] != 26:
        failures.append("post_gemma_task_count_mismatch")

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
    built = build_checklist(load_jsonl(PACKETS), load_json(STUBS))
    CHECKLIST.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Complete the 39 pre-Gemma tasks across the 13 supported standalone cells by filling rubric, anti-cheat, and checkpoint evidence, "
        "then unlock the remaining 26 post-Gemma tasks by recovering or authorizing the Gemma runner surface."
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
        "decision": "Materialized a per-cell completion checklist that separates immediately actionable pre-Gemma review work from the tasks still blocked on Gemma execution.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9754 Supported Standalone Completion Checklist",
        "",
        f"Passed: `{summary['passed']}`",
        f"Checklist rows: `{summary['metrics']['checklist_rows']}`",
        f"Pre-Gemma tasks total: `{summary['metrics']['pre_gemma_tasks_total']}`",
        f"Post-Gemma tasks total: `{summary['metrics']['post_gemma_tasks_total']}`",
        f"Cells ready for human review now: `{summary['metrics']['cells_ready_for_human_review_now']}`",
        f"Cells blocked on Gemma runner: `{summary['metrics']['cells_blocked_on_gemma_runner']}`",
        "",
        "This stage makes the immediate work queue explicit: rubric scoring, cell-specific anti-cheat review, and checkpoint attachment can proceed now, while same-surface Gemma execution and final claim-ready merge remain blocked on the missing Gemma runner surface.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "pre_gemma_tasks_total": summary["metrics"]["pre_gemma_tasks_total"],
        "post_gemma_tasks_total": summary["metrics"]["post_gemma_tasks_total"],
        "cells_ready_for_human_review_now": summary["metrics"]["cells_ready_for_human_review_now"],
        "cells_blocked_on_gemma_runner": summary["metrics"]["cells_blocked_on_gemma_runner"],
        "top_priority_cell": summary["metrics"]["top_priority_cell"],
        "next_best_step": next_step,
        "failures": built["failures"],
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

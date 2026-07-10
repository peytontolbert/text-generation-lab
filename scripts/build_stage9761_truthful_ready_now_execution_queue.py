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
STAGE = 9761
NAME = "stage9761_truthful_ready_now_execution_queue"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
QUEUE = OUT_DIR / "truthful_ready_now_execution_queue.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUTHFUL_READY_NOW_EXECUTION_QUEUE_STAGE9761.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

READY_QUEUE = ROOT / "runs/local/artifacts/stage9759_ready_now_execution_queue/ready_now_execution_queue.json"
CHECKPOINT_AUDIT = ROOT / "runs/local/artifacts/stage9760_checkpoint_readiness_truthfulness_audit/checkpoint_readiness_truthfulness_audit.json"


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


def build_truthful_queue(ready_queue: dict[str, Any], checkpoint_audit: dict[str, Any]) -> dict[str, Any]:
    entries = ready_queue.get("queue_entries") if isinstance(ready_queue.get("queue_entries"), list) else []
    blocked_artifacts = {
        str(row.get("artifact_path") or "")
        for row in (checkpoint_audit.get("records") if isinstance(checkpoint_audit.get("records"), list) else [])
        if row.get("truthful_ready_now") is False
    }
    filtered = [row for row in entries if str(row.get("artifact_path") or "") not in blocked_artifacts]
    filtered.sort(key=lambda row: int(row.get("queue_position") or 9999))
    for idx, row in enumerate(filtered, start=1):
        row["queue_position"] = idx

    metrics = {
        "ready_now_entries": len(filtered),
        "standalone_entries": sum(1 for row in filtered if row.get("front") == "standalone"),
        "harness_entries": sum(1 for row in filtered if row.get("front") == "harness"),
        "removed_false_ready_entries": len(entries) - len(filtered),
        "highest_impact_entries": sum(1 for row in filtered if row.get("impact_band") == "highest"),
        "languages": sorted({str(row.get("language_family") or "") for row in filtered}),
        "top_queue_entry": (
            filtered[0]["cell_key"] + "::" + filtered[0]["task"]
            if filtered else None
        ),
    }
    failures: list[str] = []
    if metrics["ready_now_entries"] != 98:
        failures.append("truthful_ready_now_entries_not_98")
    if metrics["standalone_entries"] != 26:
        failures.append("truthful_standalone_entries_not_26")
    if metrics["harness_entries"] != 72:
        failures.append("truthful_harness_entries_not_72")
    if metrics["removed_false_ready_entries"] != 13:
        failures.append("removed_false_ready_entries_not_13")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "queue_entries": filtered,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_truthful_queue(load_json(READY_QUEUE), load_json(CHECKPOINT_AUDIT))
    QUEUE.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Execute the corrected Stage9761 queue from the top: finish standalone rubric and anti-cheat review first, then continue through the aligned harness review-preparation tasks while runner recovery proceeds separately."
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
        "decision": "Materialized the corrected ready-now execution queue after removing the 13 standalone checkpoint tasks that were not truthfully actionable under current evidence.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9761 Truthful Ready Now Execution Queue",
        "",
        f"Passed: `{summary['passed']}`",
        f"Ready-now entries: `{summary['metrics']['ready_now_entries']}`",
        f"Standalone entries: `{summary['metrics']['standalone_entries']}`",
        f"Harness entries: `{summary['metrics']['harness_entries']}`",
        f"Removed false-ready entries: `{summary['metrics']['removed_false_ready_entries']}`",
        f"Top queue entry: `{summary['metrics']['top_queue_entry']}`",
        "",
        "This stage is the queue that should actually be worked. It excludes the 13 standalone checkpoint-hash tasks that were previously counted as ready-now despite lacking any exported checkpoint artifact.",
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
        "removed_false_ready_entries": summary["metrics"]["removed_false_ready_entries"],
        "top_queue_entry": summary["metrics"]["top_queue_entry"],
        "next_best_step": next_step,
        "failures": built["failures"],
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

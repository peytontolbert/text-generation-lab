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
STAGE = 9758
NAME = "stage9758_cross_front_execution_ledger"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
LEDGER = OUT_DIR / "cross_front_execution_ledger.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CROSS_FRONT_EXECUTION_LEDGER_STAGE9758.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

STANDALONE_CHECKLIST = ROOT / "runs/local/artifacts/stage9754_supported_standalone_completion_checklist/supported_standalone_completion_checklist.json"
HARNESS_CHECKLIST = ROOT / "runs/local/artifacts/stage9755_full_product_harness_completion_checklist/full_product_harness_completion_checklist.json"
STANDALONE_STUBS = ROOT / "runs/local/artifacts/stage9753_supported_standalone_review_stub_files/supported_standalone_review_stub_manifest.json"
HARNESS_STUBS = ROOT / "runs/local/artifacts/stage9757_full_product_harness_review_stub_files/full_product_harness_review_stub_manifest.json"


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


def build_ledger(
    standalone_checklist: dict[str, Any],
    harness_checklist: dict[str, Any],
    standalone_stubs: dict[str, Any],
    harness_stubs: dict[str, Any],
) -> dict[str, Any]:
    s_metrics = standalone_checklist.get("metrics") if isinstance(standalone_checklist.get("metrics"), dict) else {}
    h_metrics = harness_checklist.get("metrics") if isinstance(harness_checklist.get("metrics"), dict) else {}
    ss_metrics = standalone_stubs.get("metrics") if isinstance(standalone_stubs.get("metrics"), dict) else {}
    hs_metrics = harness_stubs.get("metrics") if isinstance(harness_stubs.get("metrics"), dict) else {}

    totals = {
        "packets_total": int(s_metrics.get("packets") or 0) + int(hs_metrics.get("packets") or 0),
        "checklist_rows_total": int(s_metrics.get("checklist_rows") or 0) + int(h_metrics.get("checklist_rows") or 0),
        "ready_now_tasks_total": int(s_metrics.get("pre_gemma_tasks_total") or 0) + int(h_metrics.get("pre_harness_tasks_ready_now") or 0),
        "ready_now_tasks_completed": int(s_metrics.get("pre_gemma_tasks_completed") or 0),
        "runner_blocked_tasks_total": int(s_metrics.get("post_gemma_tasks_total") or 0) + int(h_metrics.get("post_harness_tasks_total") or 0),
        "standalone_stub_files_total": (
            int(ss_metrics.get("rubric_stub_files") or 0)
            + int(ss_metrics.get("anti_cheat_stub_files") or 0)
            + int(ss_metrics.get("gemma_stub_files") or 0)
            + int(ss_metrics.get("checkpoint_stub_files") or 0)
        ),
        "harness_stub_files_total": (
            int(hs_metrics.get("harness_run_id_stub_files") or 0)
            + int(hs_metrics.get("same_task_pack_stub_files") or 0)
            + int(hs_metrics.get("tool_trace_stub_files") or 0)
            + int(hs_metrics.get("verifier_result_stub_files") or 0)
            + int(hs_metrics.get("patch_score_stub_files") or 0)
            + int(hs_metrics.get("rubric_stub_files") or 0)
            + int(hs_metrics.get("anti_cheat_stub_files") or 0)
        ),
    }
    records = {
        "standalone_front": {
            "cells": int(s_metrics.get("checklist_rows") or 0),
            "ready_now_tasks": int(s_metrics.get("pre_gemma_tasks_total") or 0),
            "runner_blocked_tasks": int(s_metrics.get("post_gemma_tasks_total") or 0),
            "cells_blocked_on_runner": int(s_metrics.get("cells_blocked_on_gemma_runner") or 0),
            "top_priority_cell": s_metrics.get("top_priority_cell"),
            "languages": s_metrics.get("languages") or [],
            "skills": s_metrics.get("skills") or [],
            "stub_files": totals["standalone_stub_files_total"],
        },
        "harness_front": {
            "cells": int(h_metrics.get("checklist_rows") or 0),
            "ready_now_tasks": int(h_metrics.get("pre_harness_tasks_ready_now") or 0),
            "runner_blocked_tasks": int(h_metrics.get("post_harness_tasks_total") or 0),
            "cells_blocked_on_runner": int(h_metrics.get("cells_blocked_on_harness_runner") or 0),
            "top_priority_cell": h_metrics.get("top_priority_cell"),
            "languages": h_metrics.get("languages") or [],
            "skills": h_metrics.get("skills") or [],
            "stub_files": totals["harness_stub_files_total"],
        },
    }

    failures: list[str] = []
    if totals["packets_total"] != 49:
        failures.append("packet_total_mismatch")
    if totals["checklist_rows_total"] != 49:
        failures.append("checklist_total_mismatch")
    if totals["ready_now_tasks_total"] != 111:
        failures.append("ready_now_task_total_mismatch")
    if totals["runner_blocked_tasks_total"] != 278:
        failures.append("runner_blocked_task_total_mismatch")
    if totals["standalone_stub_files_total"] != 52:
        failures.append("standalone_stub_file_total_mismatch")
    if totals["harness_stub_files_total"] != 252:
        failures.append("harness_stub_file_total_mismatch")

    return {
        "passed": not failures,
        "failures": failures,
        "totals": totals,
        "fronts": records,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_ledger(
        load_json(STANDALONE_CHECKLIST),
        load_json(HARNESS_CHECKLIST),
        load_json(STANDALONE_STUBS),
        load_json(HARNESS_STUBS),
    )
    LEDGER.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Complete the 111 ready-now review and evidence-attachment tasks across both fronts, then recover or authorize the "
        "Gemma and harness runner surfaces to unlock the remaining 278 runner-blocked execution tasks."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            **built["totals"],
        },
        "artifacts": {
            "ledger": str(LEDGER.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Materialized a unified cross-front execution ledger that totals ready-now and runner-blocked work across both standalone and full-product harness evaluation fronts.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9758 Cross Front Execution Ledger",
        "",
        f"Passed: `{summary['passed']}`",
        f"Packets total: `{summary['metrics']['packets_total']}`",
        f"Checklist rows total: `{summary['metrics']['checklist_rows_total']}`",
        f"Ready-now tasks total: `{summary['metrics']['ready_now_tasks_total']}`",
        f"Runner-blocked tasks total: `{summary['metrics']['runner_blocked_tasks_total']}`",
        f"Standalone stub files total: `{summary['metrics']['standalone_stub_files_total']}`",
        f"Harness stub files total: `{summary['metrics']['harness_stub_files_total']}`",
        "",
        "This stage provides one authoritative operational view across both comparison fronts. The remaining blocker is no longer missing scaffolding; it is completing the ready-now review work and recovering the missing runner surfaces.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "packets_total": summary["metrics"]["packets_total"],
        "ready_now_tasks_total": summary["metrics"]["ready_now_tasks_total"],
        "runner_blocked_tasks_total": summary["metrics"]["runner_blocked_tasks_total"],
        "standalone_stub_files_total": summary["metrics"]["standalone_stub_files_total"],
        "harness_stub_files_total": summary["metrics"]["harness_stub_files_total"],
        "next_best_step": next_step,
        "failures": built["failures"],
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

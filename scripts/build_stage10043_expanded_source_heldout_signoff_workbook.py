#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10043
NAME = "stage10043_expanded_source_heldout_signoff_workbook"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
WORKBOOK = OUT_DIR / "expanded_source_heldout_signoff_workbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EXPANDED_SOURCE_HELDOUT_SIGNOFF_WORKBOOK_STAGE10043.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUEST = ROOT / "runs/summaries/stage10037_expanded_source_heldout_target100m_execution_request.json"
QUEUE = ROOT / "runs/summaries/stage10039_expanded_source_heldout_same_manifest_gemma_queue.json"
REVIEW_PACKET = ROOT / "runs/summaries/stage10042_expanded_source_heldout_review_packet.json"
LANGS = ["python", "c_cpp", "rust", "web_js_ts_html"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "next_best_step": summary["next_best_step"],
        }
    )
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


def build_workbook() -> dict[str, Any]:
    request = load_json(REQUEST)
    queue = load_json(QUEUE)
    review = load_json(REVIEW_PACKET)
    failures: list[str] = []

    request_metrics = request.get("metrics") or {}
    queue_metrics = queue.get("metrics") or {}
    review_metrics = review.get("metrics") or {}
    if request.get("passed") is not True:
        failures.append("stage10037_not_passed")
    if queue.get("passed") is not True:
        failures.append("stage10039_not_passed")
    if review.get("passed") is not True:
        failures.append("stage10042_not_passed")

    rows: list[dict[str, Any]] = []
    queue_position = 1
    for language in LANGS:
        rows.append(
            {
                "queue_position": queue_position,
                "cell_key": f"expanded_source_heldout_target100m::{language}::edit_localization::expert_review",
                "language_family": language,
                "task": "expert_maintainer_rubric_review",
                "review_status": "pending_post_execution_attachment",
                "required_human_action": "After stage10040/10041 outputs exist, review the same-manifest evidence for unique-label identifiability and maintainer-appropriate reasoning.",
                "supporting_evidence_paths": {
                    "target100m_request": display(ROOT / "runs/local/artifacts/stage10037_expanded_source_heldout_target100m_execution_request/expanded_source_heldout_target100m_execution_request.json"),
                    "gemma_queue": display(ROOT / "runs/local/artifacts/stage10039_expanded_source_heldout_same_manifest_gemma_queue/expanded_source_heldout_same_manifest_gemma_queue.json"),
                    "fresh_review_packet": display(ROOT / "runs/local/artifacts/stage10042_expanded_source_heldout_review_packet/expanded_source_heldout_review_rows.jsonl"),
                    "future_comparison_audit": display(ROOT / "runs/local/artifacts/stage10040_expanded_source_heldout_same_manifest_comparison_audit/expanded_source_heldout_same_manifest_comparison_audit.json"),
                },
            }
        )
        queue_position += 1
        rows.append(
            {
                "queue_position": queue_position,
                "cell_key": f"expanded_source_heldout_target100m::{language}::edit_localization::anti_cheat_review",
                "language_family": language,
                "task": "cell_specific_anti_cheat_review",
                "review_status": "pending_post_execution_attachment",
                "required_human_action": "After stage10040/10041 outputs exist, verify the row family still resists label-proxy shortcuts, source leakage, and metadata confounds on the expanded heldout surface.",
                "supporting_evidence_paths": {
                    "target100m_request": display(ROOT / "runs/local/artifacts/stage10037_expanded_source_heldout_target100m_execution_request/expanded_source_heldout_target100m_execution_request.json"),
                    "gemma_queue": display(ROOT / "runs/local/artifacts/stage10039_expanded_source_heldout_same_manifest_gemma_queue/expanded_source_heldout_same_manifest_gemma_queue.json"),
                    "fresh_review_packet": display(ROOT / "runs/local/artifacts/stage10042_expanded_source_heldout_review_packet/expanded_source_heldout_review_rows.jsonl"),
                    "future_comparison_rows": display(ROOT / "runs/local/artifacts/stage10040_expanded_source_heldout_same_manifest_comparison_audit/expanded_source_heldout_same_manifest_comparison_rows.jsonl"),
                },
            }
        )
        queue_position += 1

    metrics = {
        "signoff_tasks": len(rows),
        "unique_cells": len(LANGS),
        "rubric_tasks": sum(1 for row in rows if row.get("task") == "expert_maintainer_rubric_review"),
        "anti_cheat_tasks": sum(1 for row in rows if row.get("task") == "cell_specific_anti_cheat_review"),
        "expanded_manifest_rows": request_metrics.get("rows"),
        "expanded_compare_rows": queue_metrics.get("heldout_compare_rows"),
        "fresh_review_rows": review_metrics.get("rows"),
    }
    if metrics["signoff_tasks"] != 8:
        failures.append("signoff_tasks_not_8")
    if metrics["expanded_manifest_rows"] != 95:
        failures.append("expanded_manifest_rows_not_95")
    if metrics["expanded_compare_rows"] != 55:
        failures.append("expanded_compare_rows_not_55")
    if metrics["fresh_review_rows"] != 18:
        failures.append("fresh_review_rows_not_18")

    return {"passed": not failures, "failures": failures, "rows": rows, "metrics": metrics}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_workbook()
    WORKBOOK.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "After the expanded same-manifest 100M and Gemma outputs exist, work this signoff workbook language by language before promoting any stronger four-language source-heldout claim."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"workbook": display(WORKBOOK), "doc": display(DOC)},
        "decision": "Materialized the expanded source-heldout signoff workbook so expert-maintainer and anti-cheat review stay tied to the new 95-row manifest and future 55-row same-manifest comparison rather than the older smaller baseline.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10043 Expanded Source Heldout Signoff Workbook",
                "",
                f"Passed: `{summary['passed']}`",
                f"Signoff tasks: `{built['metrics']['signoff_tasks']}`",
                "",
                summary["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

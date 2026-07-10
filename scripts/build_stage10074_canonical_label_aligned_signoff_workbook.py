#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10074
NAME = "stage10074_canonical_label_aligned_signoff_workbook"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
WORKBOOK = OUT_DIR / "canonical_label_aligned_signoff_workbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CANONICAL_LABEL_ALIGNED_SIGNOFF_WORKBOOK_STAGE10074.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REVIEW = ROOT / "runs/summaries/stage10073_canonical_label_aligned_review_packets.json"
REQUEST = ROOT / "runs/summaries/stage10084_canonical_label_aligned_source_heldout_target100m_execution_request.json"
QUEUE = ROOT / "runs/summaries/stage10085_canonical_label_aligned_source_heldout_same_manifest_gemma_queue.json"
COMPARISON = ROOT / "runs/summaries/stage10086_canonical_label_aligned_source_heldout_same_manifest_comparison_audit.json"
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
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_workbook() -> dict[str, Any]:
    review = load_json(REVIEW)
    request = load_json(REQUEST)
    queue = load_json(QUEUE)
    comparison = load_json(COMPARISON)
    failures: list[str] = []

    if review.get("passed") is not True:
        failures.append("stage10073_not_passed")
    if request.get("passed") is not True:
        failures.append("stage10084_not_passed")
    if queue.get("passed") is not True:
        failures.append("stage10085_not_passed")
    if comparison.get("passed") is not True:
        failures.append("stage10086_not_passed")

    rows: list[dict[str, Any]] = []
    queue_position = 1
    for language in LANGS:
        rows.append(
            {
                "queue_position": queue_position,
                "cell_key": f"canonical_label_aligned_target100m::{language}::edit_localization::expert_review",
                "language_family": language,
                "task": "expert_maintainer_rubric_review",
                "review_status": "pending_human_signoff",
                "required_human_action": "Review the attached canonical-label source-heldout same-manifest outputs and decide whether visible evidence supports one maintainer-appropriate answer for this language slice.",
                "supporting_evidence_paths": {
                    "review_packets": display(ROOT / "runs/local/artifacts/stage10073_canonical_label_aligned_review_packets/canonical_label_aligned_review_packets.jsonl"),
                    "same_manifest_comparison": display(ROOT / "runs/local/artifacts/stage10086_canonical_label_aligned_source_heldout_same_manifest_comparison_audit/canonical_label_aligned_source_heldout_same_manifest_comparison_audit.json"),
                    "target100m_request": display(ROOT / "runs/local/artifacts/stage10084_canonical_label_aligned_source_heldout_target100m_execution_request/canonical_label_aligned_source_heldout_target100m_execution_request.json"),
                },
            }
        )
        queue_position += 1
        rows.append(
            {
                "queue_position": queue_position,
                "cell_key": f"canonical_label_aligned_target100m::{language}::edit_localization::anti_cheat_review",
                "language_family": language,
                "task": "cell_specific_anti_cheat_review",
                "review_status": "pending_human_signoff",
                "required_human_action": "Confirm the canonical remap eliminated cross-language label-semantic shortcuts and that no same-manifest leakage or fairness issue remains on this slice.",
                "supporting_evidence_paths": {
                    "review_packets": display(ROOT / "runs/local/artifacts/stage10073_canonical_label_aligned_review_packets/canonical_label_aligned_review_packets.jsonl"),
                    "label_collision_audit": display(ROOT / "runs/local/artifacts/stage10068_multilingual_label_semantics_collision_audit/multilingual_label_semantics_collision_audit.json"),
                    "gemma_queue": display(ROOT / "runs/local/artifacts/stage10085_canonical_label_aligned_source_heldout_same_manifest_gemma_queue/canonical_label_aligned_source_heldout_same_manifest_gemma_queue.json"),
                },
            }
        )
        queue_position += 1

    metrics = {
        "signoff_tasks": len(rows),
        "rubric_tasks": sum(1 for row in rows if row["task"] == "expert_maintainer_rubric_review"),
        "anti_cheat_tasks": sum(1 for row in rows if row["task"] == "cell_specific_anti_cheat_review"),
        "same_manifest_rows": (comparison.get("metrics") or {}).get("comparison_rows"),
        "wins_100m": (comparison.get("metrics") or {}).get("wins_100m"),
        "queue_rows": (queue.get("metrics") or {}).get("rows"),
    }
    if metrics["signoff_tasks"] != 8:
        failures.append("signoff_tasks_not_8")
    if metrics["same_manifest_rows"] != 55:
        failures.append("same_manifest_rows_not_55")
    if metrics["wins_100m"] != 4:
        failures.append("wins_100m_not_4")
    if metrics["queue_rows"] != 55:
        failures.append("queue_rows_not_55")
    return {"passed": not failures, "failures": failures, "rows": rows, "metrics": metrics}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_workbook()
    WORKBOOK.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Work the 8 canonical-label signoff tasks to turn the current machine-complete source-heldout 4-language win into human-reviewed same-surface evidence for the standalone v2.7 acceptance cells."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"workbook": display(WORKBOOK), "doc": display(DOC)},
        "decision": "Materialized the canonical-label signoff workbook so expert-maintainer and anti-cheat review can proceed directly on the stage10086 four-language source-heldout same-manifest win.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10074 Canonical Label Aligned Signoff Workbook",
        "",
        f"Passed: `{summary['passed']}`",
        f"Signoff tasks: `{built['metrics']['signoff_tasks']}`",
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

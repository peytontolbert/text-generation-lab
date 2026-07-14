#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs" / "local" / "artifacts"
SUM = ROOT / "runs" / "summaries"
NAME = "stage11514_selected_frontier_harness_result_audit"
OUT_DIR = ART / NAME
OUT_JSON = SUM / f"{NAME}.json"

PROMOTION = SUM / "stage11509_preservation_strengthened_frontier_promotion_decision.json"
COMPARISON = SUM / "stage11510_selected_frontier_same_manifest_gemma_comparison.json"
PAYLOAD = ART / "stage11511_selected_frontier_harness_payload/selected_frontier_harness_payload.json"
RUNTIME = ART / "stage11512_selected_frontier_harness_local_runtime/canonical_harness_local_runtime_summary.json"
WRITEBACK = ART / "stage11513_selected_frontier_harness_writeback/reviewed_v28_harness_writeback_repair.json"
HANDOFF = ART / "stage10657_repaired_headline_harness_handoff_bundle/repaired_headline_harness_handoff_bundle.json"

REQUIRED_FIELDS = (
    "harness_run_id",
    "same_task_pack_as_gemma12b",
    "tool_trace_spans",
    "verifier_results",
    "patch_minimality_or_abstain_scores",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def file_status(path: Path) -> dict[str, Any]:
    return {
        "path": rel(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }


def main() -> None:
    promotion = load_json(PROMOTION)
    comparison = load_json(COMPARISON)
    payload = load_json(PAYLOAD)
    runtime = load_json(RUNTIME)
    writeback = load_json(WRITEBACK)
    handoff = load_json(HANDOFF)

    handoff_cells = [row for row in handoff.get("handoff_cells") or [] if isinstance(row, dict)]
    runtime_results = {str(row.get("cell_key") or ""): row for row in runtime.get("results") or []}
    writeback_results = {
        str(row.get("cell_key") or ""): row
        for row in writeback.get("repaired_runs") or []
        if isinstance(row, dict)
    }

    failures: list[str] = []
    cell_results: list[dict[str, Any]] = []
    for cell in handoff_cells:
        cell_key = str(cell.get("cell_key") or "")
        artifact_paths = dict(cell.get("artifact_paths") or {})
        runtime_row = runtime_results.get(cell_key) or {}
        writeback_row = writeback_results.get(cell_key) or {}
        field_status = {
            field: file_status(ROOT / str(artifact_paths.get(field) or ""))
            for field in REQUIRED_FIELDS
        }
        missing_fields = [
            field
            for field, status in field_status.items()
            if not status["exists"] or int(status["size_bytes"]) <= 0
        ]
        if missing_fields:
            failures.append(f"missing_or_empty_writeback::{cell_key}::{','.join(missing_fields)}")
        if not runtime_row:
            failures.append(f"missing_runtime_result::{cell_key}")
        if not writeback_row:
            failures.append(f"missing_writeback_result::{cell_key}")

        cell_results.append(
            {
                "cell_key": cell_key,
                "language_family": cell.get("language_family"),
                "row_count": cell.get("row_count"),
                "harness_run_id": runtime_row.get("harness_run_id"),
                "hundred_m_runtime": runtime_row.get("hundred_m_runtime"),
                "gemma12b_runtime": runtime_row.get("gemma12b_runtime"),
                "same_task_pack_verified": (runtime_row.get("same_task_pack_as_gemma12b") or {}).get("same_task_pack_verified"),
                "writeback_failures": (writeback_row.get("result") or {}).get("failures"),
                "required_writeback_fields": field_status,
            }
        )

    runtime_metrics = runtime.get("metrics") or {}
    comparison_metrics = comparison.get("metrics") or {}
    promotion_metrics = promotion.get("stage11507_product_metrics") or {}
    selected_frontier = promotion.get("selected_frontier_after_decision") or {}
    payload_runs = [row for row in payload.get("runs") or [] if isinstance(row, dict)]
    payload_matched_rows = sum(len((row.get("task_pack") or {}).get("rows") or []) for row in payload_runs)
    if runtime.get("passed") is not True:
        failures.append("runtime_summary_not_passed")
    if writeback.get("passed") is not True:
        failures.append("writeback_not_passed")
    if int(runtime_metrics.get("completed_runs") or 0) != 4:
        failures.append("runtime_completed_runs_not_4")
    if int((writeback.get("metrics") or {}).get("repaired_runs") or 0) != 4:
        failures.append("writeback_repaired_runs_not_4")

    audit = {
        "stage": 11514,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": not failures,
        "decision": "selected_frontier_harness_writeback_complete" if not failures else "selected_frontier_harness_writeback_incomplete",
        "selected_frontier": {
            "runtime_stage": 11507,
            "promotion_decision": promotion.get("decision"),
            "runtime_bundle": selected_frontier.get("runtime_bundle"),
            "scorer": selected_frontier.get("scorer"),
        },
        "metrics": {
            "same_manifest_hundred_m_accuracy": comparison_metrics.get("hundred_m_accuracy"),
            "same_manifest_hundred_m_correct": comparison_metrics.get("hundred_m_correct"),
            "same_manifest_gemma_accuracy": comparison_metrics.get("gemma_accuracy"),
            "same_manifest_gemma_correct": comparison_metrics.get("gemma_correct"),
            "same_manifest_delta_accuracy": comparison_metrics.get("delta_accuracy"),
            "harness_completed_runs": runtime_metrics.get("completed_runs"),
            "harness_failed_runs": runtime_metrics.get("failed_runs"),
            "harness_writeback_runs": (writeback.get("metrics") or {}).get("repaired_runs"),
            "payload_matched_rows": payload_matched_rows,
            "promotion_filtered_strict": promotion_metrics.get("filtered_strict"),
            "promotion_old_canary_strict": promotion_metrics.get("old_canary_strict"),
            "promotion_filtered_validation": promotion_metrics.get("filtered_validation"),
            "promotion_old_canary_validation": promotion_metrics.get("old_canary_validation"),
            "promotion_residual_bank": promotion_metrics.get("residual_bank"),
            "promotion_bridge_train_rows": promotion_metrics.get("bridge_train_rows"),
        },
        "claim_boundary": [
            "This completes same-task-pack harness/writeback evidence for the selected compact maintainer-choice bounded scorer runtime.",
            "It does not establish broad freeform software repair, executable patch synthesis, or full-product verifier rows because this packet has no patch/verifier rows.",
        ],
        "cell_results": cell_results,
        "failures": failures,
        "source_artifacts": {
            "promotion": rel(PROMOTION),
            "comparison": rel(COMPARISON),
            "harness_payload": rel(PAYLOAD),
            "runtime_summary": rel(RUNTIME),
            "writeback": rel(WRITEBACK),
            "handoff": rel(HANDOFF),
        },
        "next_best_step": "Use stage11507 as selected frontier; only promote future runs that preserve canary/filtered strict and improve residual/generalization under the product scorer.",
    }
    write_json(OUT_DIR / f"{NAME}.json", audit)
    write_json(OUT_JSON, audit)
    print(json.dumps(audit, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"

STAGE = 11467
NAME = "stage11467_selected_runtime_harness_result_audit"
OUT = ART / NAME
OUT_JSON = OUT / "selected_runtime_harness_result_audit.json"

PAYLOAD_SUMMARY = ART / "stage11464_selected_runtime_harness_payload/selected_runtime_harness_payload_summary.json"
RUNTIME_SUMMARY = ART / "stage11465_selected_runtime_harness_local_runtime/canonical_harness_local_runtime_summary.json"
WRITEBACK = ART / "stage11466_selected_runtime_harness_writeback/reviewed_v28_harness_writeback_repair.json"
HANDOFF = ART / "stage10657_repaired_headline_harness_handoff_bundle/repaired_headline_harness_handoff_bundle.json"
FRONTIER = ART / "stage11462_post_rust_breadth_frontier_decision/post_rust_breadth_frontier_decision.json"

REQUIRED_FIELDS = (
    "harness_run_id",
    "same_task_pack_as_gemma12b",
    "tool_trace_spans",
    "verifier_results",
    "patch_minimality_or_abstain_scores",
)


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_status(path: Path) -> dict[str, Any]:
    return {
        "path": rel(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }


def read_runtime_payload(runtime_dir: str) -> dict[str, Any]:
    path = ROOT / runtime_dir / "runtime_payload.json"
    return load_json(path)


def main() -> None:
    payload_summary = load_json(PAYLOAD_SUMMARY)
    runtime_summary = load_json(RUNTIME_SUMMARY)
    writeback = load_json(WRITEBACK)
    handoff = load_json(HANDOFF)
    frontier = load_json(FRONTIER)

    selected_frontier = frontier.get("selected_frontier") or {}
    selected_sha = str(selected_frontier.get("weights_sha256") or "")
    selected_runtime_bundle = str(selected_frontier.get("runtime_bundle") or "")
    selected_scorer = str(selected_frontier.get("scorer") or "")

    results = [row for row in runtime_summary.get("results") or [] if isinstance(row, dict)]
    handoff_cells = [row for row in handoff.get("handoff_cells") or [] if isinstance(row, dict)]
    handoff_by_key = {str(row.get("cell_key") or ""): row for row in handoff_cells}

    cell_results = []
    failures: list[str] = []
    total_rows = 0
    total_hundred_m_correct = 0.0
    total_gemma_correct = 0.0
    for result in results:
        cell_key = str(result.get("cell_key") or "")
        cell = handoff_by_key.get(cell_key) or {}
        artifact_paths = cell.get("artifact_paths") if isinstance(cell.get("artifact_paths"), dict) else {}
        runtime_dir = str(result.get("runtime_dir") or "")
        runtime_payload = read_runtime_payload(runtime_dir)
        backend = runtime_payload.get("hundred_m_backend") if isinstance(runtime_payload.get("hundred_m_backend"), dict) else {}
        rows = int((result.get("hundred_m_runtime") or {}).get("rows") or 0)
        hundred_m_accuracy = (result.get("hundred_m_runtime") or {}).get("exact_accuracy")
        gemma_accuracy = (result.get("gemma12b_runtime") or {}).get("exact_accuracy")
        if hundred_m_accuracy is not None:
            total_hundred_m_correct += float(hundred_m_accuracy) * rows
        if gemma_accuracy is not None:
            total_gemma_correct += float(gemma_accuracy) * rows
        total_rows += rows

        required_status = {
            field: file_status(ROOT / str(artifact_paths.get(field) or ""))
            for field in REQUIRED_FIELDS
        }
        missing_fields = [field for field, status in required_status.items() if not status["exists"]]
        if missing_fields:
            failures.append(f"missing_writeback_fields::{cell_key}::{','.join(missing_fields)}")
        if backend.get("runtime_model_bundle") != selected_runtime_bundle:
            failures.append(f"runtime_bundle_mismatch::{cell_key}")
        if backend.get("weights_sha256") != selected_sha:
            failures.append(f"weights_sha256_mismatch::{cell_key}")
        if backend.get("bounded_choice_aux_source") != selected_scorer:
            failures.append(f"scorer_mismatch::{cell_key}")

        cell_results.append(
            {
                "cell_key": cell_key,
                "language_family": cell.get("language_family"),
                "rows": rows,
                "hundred_m_accuracy": hundred_m_accuracy,
                "gemma12b_accuracy": gemma_accuracy,
                "harness_run_id": result.get("harness_run_id"),
                "runtime_dir": runtime_dir,
                "runtime_payload_references_selected_runtime": backend.get("runtime_model_bundle") == selected_runtime_bundle,
                "runtime_payload_references_selected_weights": backend.get("weights_sha256") == selected_sha,
                "runtime_payload_references_selected_scorer": backend.get("bounded_choice_aux_source") == selected_scorer,
                "required_writeback_fields": required_status,
            }
        )

    hundred_m_accuracy = (total_hundred_m_correct / total_rows) if total_rows else None
    gemma_accuracy = (total_gemma_correct / total_rows) if total_rows else None
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": not failures and bool(results) and bool(writeback.get("passed")),
        "claim_scope": [
            "Current Stage11444 selected-runtime local harness execution over the repaired-headline matched old-canary task packs.",
            "This proves the harness/writeback path for the current selected bounded-choice runtime, not broad full-product software repair.",
        ],
        "selected_frontier": {
            "runtime_bundle": selected_runtime_bundle,
            "weights_sha256": selected_sha,
            "scorer": selected_scorer,
        },
        "metrics": {
            "cells": len(cell_results),
            "total_rows": total_rows,
            "hundred_m_accuracy": hundred_m_accuracy,
            "hundred_m_correct": total_hundred_m_correct,
            "gemma12b_accuracy": gemma_accuracy,
            "gemma12b_correct": total_gemma_correct,
            "delta_accuracy": (hundred_m_accuracy - gemma_accuracy)
            if hundred_m_accuracy is not None and gemma_accuracy is not None
            else None,
            "writeback_repaired_cells": (writeback.get("metrics") or {}).get("repaired_runs"),
        },
        "cell_results": cell_results,
        "failures": failures,
        "notes": [
            "Stage11465 executed with --skip-writeback first; Stage11466 replayed the generated adapter payloads into the reserved Stage10657 packet paths.",
            "Gemma was re-run locally through Ollama on the same task packs; aggregate accuracy remains 7/23, though per-language allocation can differ from Stage11447 due live generation/parsing behavior.",
            "Verifier and patch-minimality cards are present but contain no verifier/patch rows for this compact bounded-choice packet; this remains a maintainer-choice harness slice.",
            "The legacy Rust singleton verifier row is still included because it is part of the current 23-row selected canary; it should not be used as evidence of Rust verifier discrimination.",
        ],
        "decision": "selected_runtime_harness_writeback_complete" if not failures else "selected_runtime_harness_writeback_incomplete",
        "source_artifacts": {
            "payload_summary": rel(PAYLOAD_SUMMARY),
            "runtime_summary": rel(RUNTIME_SUMMARY),
            "writeback": rel(WRITEBACK),
            "handoff": rel(HANDOFF),
            "frontier_decision": rel(FRONTIER),
        },
        "outputs": {"summary": rel(OUT_JSON)},
    }
    write_json(OUT_JSON, payload)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OUT_JSON, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"passed": payload["passed"], "decision": payload["decision"], "metrics": payload["metrics"]}, indent=2, sort_keys=True))
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10134
NAME = "stage10134_v27_multilingual_comparison_spine"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SPINE = OUT_DIR / "v27_multilingual_comparison_spine.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "V27_MULTILINGUAL_COMPARISON_SPINE_STAGE10134.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

MAINTAINER_READINESS = ROOT / "runs/local/artifacts/stage10132_true_source_backed_first_wave_adjudication_readiness_ledger/true_source_backed_first_wave_adjudication_readiness_ledger.json"
MAINTAINER_COMPARISON = ROOT / "runs/local/artifacts/stage10133_true_source_backed_first_wave_comparison_contract/true_source_backed_first_wave_comparison_contract.json"
HARNESS_QUEUE = ROOT / "runs/local/artifacts/stage9749_full_product_harness_gemma_queue/full_product_harness_gemma_queue.json"
HARNESS_HANDOFF = ROOT / "runs/local/artifacts/stage10081_canonical_harness_backend_handoff_bundle/canonical_harness_backend_handoff_bundle.json"
ACCEPTANCE = ROOT / "docs" / "V27_MULTILINGUAL_EVAL_ACCEPTANCE_CONTRACT_STAGE9684.md"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)),
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_spine(
    *,
    maintainer_readiness_path: Path = MAINTAINER_READINESS,
    maintainer_comparison_path: Path = MAINTAINER_COMPARISON,
    harness_queue_path: Path = HARNESS_QUEUE,
    harness_handoff_path: Path = HARNESS_HANDOFF,
) -> dict[str, Any]:
    maintainer_readiness = load_json(maintainer_readiness_path)
    maintainer_comparison = load_json(maintainer_comparison_path)
    harness_queue = load_json(harness_queue_path)
    harness_handoff = load_json(harness_handoff_path)

    failures: list[str] = []
    if maintainer_readiness.get("passed") is not True:
        failures.append("stage10132_not_passed")
    if maintainer_comparison.get("passed") is not True:
        failures.append("stage10133_not_passed")
    if harness_queue.get("passed") is not True:
        failures.append("stage9749_not_passed")
    if harness_handoff.get("passed") is not True:
        failures.append("stage10081_not_passed")

    readiness_metrics = maintainer_readiness.get("metrics") or {}
    comparison_metrics = maintainer_comparison.get("metrics") or {}
    harness_queue_metrics = harness_queue.get("metrics") or {}
    harness_handoff_metrics = harness_handoff.get("metrics") or {}

    payload = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "decision": (
            "Join the current standalone maintainer frontier and the current full-product harness frontier into one v2.7 comparison spine so progress toward beating Gemma stays coordinated without collapsing distinct eval surfaces into one dishonest claim."
        ),
        "claim_boundary": {
            "standalone_maintainer_first_wave_claim_requires_stage10133_contract": True,
            "full_product_harness_claim_requires_external_runtime_writeback": True,
            "do_not_merge_standalone_maintainer_and_full_product_harness_scores_into_one_metric_yet": True,
            "multilingual_v27_completion_requires_both_tracks_not_just_one": True,
        },
        "tracks": {
            "standalone_maintainer_first_wave": {
                "bundle_count": int(readiness_metrics.get("first_wave_bundle_count", 0) or 0),
                "bundles_scoreable_now": int(readiness_metrics.get("bundles_scoreable_now", 0) or 0),
                "comparison_ready_now": bool(comparison_metrics.get("comparison_ready_now")),
                "primary_gate": "complete_human_rubric_anti_cheat_and_gold_signoff_for_all_8_bundles",
                "next_artifacts": [
                    display(maintainer_readiness_path),
                    display(maintainer_comparison_path),
                ],
            },
            "full_product_harness": {
                "queue_entries": int(harness_queue_metrics.get("queue_entries", 0) or 0),
                "aligned_with_supported_standalone_cell": int(
                    ((harness_queue_metrics.get("priority_buckets") or {}).get("aligned_with_supported_standalone_cell", 0) or 0)
                ),
                "canonical_handoff_cells": int(harness_handoff_metrics.get("canonical_handoff_cells", 0) or 0),
                "cells_requiring_external_backend": int(harness_handoff_metrics.get("cells_requiring_external_backend", 0) or 0),
                "primary_gate": "external_runtime_must_execute_and_write_back_reserved_handoff_artifacts",
                "next_artifacts": [
                    display(harness_queue_path),
                    display(harness_handoff_path),
                ],
            },
        },
        "execution_order": [
            "finish_8_bundle_human_signoff_for_standalone_maintainer_first_wave",
            "rerun_stage10129_stage10130_stage10132_stage10133_on_the_admitted_bundle_set",
            "run_one_frozen_100m_vs_gemma_standalone_maintainer_comparison",
            "hand_the_4_canonical_harness_backend_handoff_bundles_to_external_runtime",
            "execute_the_13_aligned_full_product_harness_cells_before_the_remaining_23",
            "report_standalone_and_harness_results_as_distinct_tracks_until_a_shared_maintainer-grade_harness_task_pack_exists",
        ],
        "metrics": {
            "standalone_first_wave_bundles": int(readiness_metrics.get("first_wave_bundle_count", 0) or 0),
            "standalone_first_wave_scoreable_now": int(readiness_metrics.get("bundles_scoreable_now", 0) or 0),
            "standalone_first_wave_comparison_ready_now": bool(comparison_metrics.get("comparison_ready_now")),
            "harness_queue_entries": int(harness_queue_metrics.get("queue_entries", 0) or 0),
            "harness_aligned_cells": int(((harness_queue_metrics.get("priority_buckets") or {}).get("aligned_with_supported_standalone_cell", 0) or 0)),
            "harness_canonical_handoff_cells": int(harness_handoff_metrics.get("canonical_handoff_cells", 0) or 0),
            "v27_multilingual_completion_ready_now": False,
        },
        "artifacts": {
            "maintainer_readiness_ledger": display(maintainer_readiness_path),
            "maintainer_comparison_contract": display(maintainer_comparison_path),
            "full_product_harness_queue": display(harness_queue_path),
            "canonical_harness_handoff_bundle": display(harness_handoff_path),
            "acceptance_contract": display(ACCEPTANCE),
        },
        "failures": failures,
        "next_best_step": (
            "Clear the 8 standalone maintainer signoff tasks first, then run the frozen standalone first-wave comparison, while independently handing the 4 canonical harness bundles to the external runtime and keeping harness claims separate until real writeback exists."
        ),
    }
    return payload


def main() -> None:
    built = build_spine()
    write_json(SPINE, built)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": built["metrics"],
        "artifacts": {
            "spine": display(SPINE),
            "doc": display(DOC),
        },
        "decision": built["decision"],
        "next_best_step": built["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage10134 V27 Multilingual Comparison Spine",
                "",
                f"Passed: `{summary['passed']}`",
                f"Standalone first-wave bundles: `{built['metrics']['standalone_first_wave_bundles']}`",
                f"Standalone first-wave scoreable now: `{built['metrics']['standalone_first_wave_scoreable_now']}`",
                f"Harness aligned cells: `{built['metrics']['harness_aligned_cells']}`",
                "",
                summary["decision"],
                "",
                f"Next: {built['next_best_step']}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": built["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

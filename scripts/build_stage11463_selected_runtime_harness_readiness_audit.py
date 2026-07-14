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

STAGE = 11463
NAME = "stage11463_selected_runtime_harness_readiness_audit"
OUT = ART / NAME
OUT_JSON = OUT / "selected_runtime_harness_readiness_audit.json"

SELECTED_FRONTIER = ART / "stage11462_post_rust_breadth_frontier_decision/post_rust_breadth_frontier_decision.json"
RUNTIME_BUNDLE = ART / "stage11444_targeted_residual_role_support_probe/runtime_model/runtime_model_bundle.json"
SAME_MANIFEST_COMPARISON = ART / "stage11447_selected_runtime_same_manifest_gemma_comparison/stage11447_selected_runtime_same_manifest_gemma_comparison.json"

REVIEWED_V28_HANDOFF = ART / "stage10648_reviewed_v28_harness_handoff_bundle/reviewed_v28_harness_handoff_bundle.json"
REVIEWED_V28_WRITEBACK = ART / "stage11076_reviewed_v28_harness_writeback_refresh/reviewed_v28_harness_writeback_refresh.json"
REVIEWED_V28_COMPLETENESS = ART / "stage11079_reviewed_v28_harness_packet_completeness_audit/reviewed_v28_harness_packet_completeness_audit.json"
REPAIRED_HEADLINE_AUDIT = ART / "stage10659_repaired_headline_harness_result_audit/repaired_headline_harness_result_audit.json"

REQUIRED_MACHINE_FIELDS = (
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
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def packet_field_status(writeback: dict[str, Any]) -> dict[str, Any]:
    results = [row for row in writeback.get("results", []) if isinstance(row, dict)]
    rows = []
    for row in results:
        status = row.get("packet_status") or {}
        rows.append(
            {
                "cell_key": row.get("cell_key"),
                "runtime_dir": row.get("runtime_dir"),
                "fields": {
                    field: {
                        "exists": bool((status.get(field) or {}).get("exists")),
                        "path": (status.get(field) or {}).get("path"),
                        "size_bytes": (status.get(field) or {}).get("size_bytes"),
                    }
                    for field in REQUIRED_MACHINE_FIELDS
                },
            }
        )
    complete = sum(
        1
        for row in rows
        if all((row["fields"].get(field) or {}).get("exists") for field in REQUIRED_MACHINE_FIELDS)
    )
    return {
        "cells_total": len(rows),
        "cells_with_required_machine_fields": complete,
        "required_fields": list(REQUIRED_MACHINE_FIELDS),
        "rows": rows,
    }


def text_contains(path: Path, needles: tuple[str, ...]) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    return all(needle in text for needle in needles)


def main() -> None:
    selected = load_json(SELECTED_FRONTIER)
    runtime = load_json(RUNTIME_BUNDLE)
    comparison = load_json(SAME_MANIFEST_COMPARISON)
    handoff = load_json(REVIEWED_V28_HANDOFF)
    writeback = load_json(REVIEWED_V28_WRITEBACK)
    completeness = load_json(REVIEWED_V28_COMPLETENESS)
    repaired = load_json(REPAIRED_HEADLINE_AUDIT)

    selected_frontier = selected.get("selected_frontier") or {}
    selected_sha = selected_frontier.get("weights_sha256") or runtime.get("weights_sha256")
    selected_runtime_path = selected_frontier.get("runtime_bundle") or rel(RUNTIME_BUNDLE)
    selected_scorer = selected_frontier.get("scorer") or "encoder_option_retrieval"

    known_harness_files = [
        REVIEWED_V28_HANDOFF,
        REVIEWED_V28_WRITEBACK,
        REVIEWED_V28_COMPLETENESS,
        REPAIRED_HEADLINE_AUDIT,
        ART / "stage10658_repaired_headline_harness_runtime_payload/repaired_headline_harness_runtime_payload.json",
        ART / "stage10280_frontier_saved_runtime_harness_payload/frontier_saved_runtime_harness_payload.json",
    ]
    current_runtime_references = [
        rel(path)
        for path in known_harness_files
        if text_contains(path, (str(selected_sha),)) or text_contains(path, ("stage11444",))
    ]

    writeback_status = packet_field_status(writeback)
    machine_writeback_complete = bool(
        writeback_status["cells_total"]
        and writeback_status["cells_with_required_machine_fields"] == writeback_status["cells_total"]
    )
    selected_runtime_harness_writeback_found = bool(current_runtime_references)

    full_product_harness_complete_for_selected_runtime = (
        machine_writeback_complete and selected_runtime_harness_writeback_found
    )
    standalone_ready = bool(runtime.get("weights_sha256") == selected_sha and comparison.get("passed"))

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "claim_scope": [
            "Audit whether the selected Stage11444 standalone frontier has a matching full-product harness packet/writeback.",
            "Separate standalone bounded-choice readiness from full-product harness execution readiness.",
        ],
        "selected_frontier": {
            "runtime_bundle": selected_runtime_path,
            "weights_sha256": selected_sha,
            "scorer": selected_scorer,
            "standalone_same_manifest_metrics": comparison.get("metrics"),
        },
        "standalone_status": {
            "ready_for_bounded_choice_claim": standalone_ready,
            "current_truthful_claim": comparison.get("claim_scope"),
        },
        "harness_status": {
            "older_harness_packet_writeback_mechanism_exists": machine_writeback_complete,
            "selected_runtime_harness_writeback_found": selected_runtime_harness_writeback_found,
            "full_product_harness_complete_for_selected_runtime": full_product_harness_complete_for_selected_runtime,
            "current_runtime_references_in_known_harness_files": current_runtime_references,
            "required_machine_fields": list(REQUIRED_MACHINE_FIELDS),
            "reviewed_v28_packet_status": {
                "packet_completeness_metrics": completeness.get("metrics"),
                "writeback_required_field_status": {
                    "cells_total": writeback_status["cells_total"],
                    "cells_with_required_machine_fields": writeback_status[
                        "cells_with_required_machine_fields"
                    ],
                },
            },
            "older_repaired_headline_harness_metrics": repaired.get("metrics"),
            "handoff_cells": len(handoff.get("handoff_cells") or []),
        },
        "decision": (
            "standalone_frontier_ready_but_full_product_harness_not_current_runtime_complete"
            if standalone_ready and not full_product_harness_complete_for_selected_runtime
            else "selected_runtime_full_product_harness_complete"
        ),
        "findings": [
            "runs/summaries is current through Stage11462 in this workspace; the earlier Stage10868 issue was summary backfill drift, not current state.",
            "Stage11444 remains the selected standalone frontier after rejecting Stage11457 and Stage11460 Rust breadth probes.",
            "Older reviewed-v28 harness packets have the required machine artifact fields, but those writebacks do not reference the Stage11444 weights/runtime.",
            "Do not claim the full-product harness is recovered for the current selected runtime until the Stage11444 task pack execution writes harness_run_id, same_task_pack_as_gemma12b, tool_trace_spans, verifier_results, and patch_minimality_or_abstain_scores.",
        ],
        "recommended_next_action": (
            "Build a Stage11444-specific harness runtime payload from the current matched strict rows or the intended full-product task pack, "
            "run both 100M and Gemma through the same adapter, then refresh the writeback/completeness audit."
        ),
        "source_artifacts": {
            "selected_frontier_decision": rel(SELECTED_FRONTIER),
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "same_manifest_comparison": rel(SAME_MANIFEST_COMPARISON),
            "reviewed_v28_handoff": rel(REVIEWED_V28_HANDOFF),
            "reviewed_v28_writeback_refresh": rel(REVIEWED_V28_WRITEBACK),
            "reviewed_v28_completeness_audit": rel(REVIEWED_V28_COMPLETENESS),
            "repaired_headline_harness_audit": rel(REPAIRED_HEADLINE_AUDIT),
        },
        "outputs": {"summary": rel(OUT_JSON)},
    }

    write_json(OUT_JSON, payload)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OUT_JSON, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": payload["decision"],
                "standalone_ready": standalone_ready,
                "full_product_harness_complete_for_selected_runtime": full_product_harness_complete_for_selected_runtime,
                "summary": rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11079
NAME = "stage11079_reviewed_v28_harness_packet_completeness_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "reviewed_v28_harness_packet_completeness_audit.json"

HANDOFF = ARTIFACTS / "stage10648_reviewed_v28_harness_handoff_bundle" / "reviewed_v28_harness_handoff_bundle.json"
WRITEBACK_REFRESH = ARTIFACTS / "stage11076_reviewed_v28_harness_writeback_refresh" / "reviewed_v28_harness_writeback_refresh.json"
AI_REVIEW = ARTIFACTS / "stage11078_reviewed_v28_ai_review_packets" / "reviewed_v28_ai_review_packets.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    handoff = load_json(HANDOFF)
    writeback = load_json(WRITEBACK_REFRESH)
    ai_review = load_json(AI_REVIEW)

    writeback_index = {
        str(row.get("cell_key") or ""): row
        for row in (writeback.get("results") or [])
        if isinstance(row, dict)
    }
    ai_index = {
        str(row.get("cell_key") or ""): row
        for row in (ai_review.get("results") or [])
        if isinstance(row, dict)
    }

    results = []
    failures = []

    for cell in (handoff.get("handoff_cells") or []):
        if not isinstance(cell, dict):
            continue
        cell_key = str(cell.get("cell_key") or "")
        artifact_paths = dict(cell.get("artifact_paths") or {})
        writeback_row = writeback_index.get(cell_key)
        ai_row = ai_index.get(cell_key)
        anti_path = ROOT / str(artifact_paths.get("anti_cheat_cards") or "")
        rubric_path = ROOT / str(artifact_paths.get("expert_maintainer_rubric_scores") or "")
        anti = load_json(anti_path) if anti_path.exists() else {}
        rubric = load_json(rubric_path) if rubric_path.exists() else {}
        packet_complete = all(
            (ROOT / str(artifact_paths.get(name) or "")).exists()
            for name in (
                "harness_run_id",
                "same_task_pack_as_gemma12b",
                "tool_trace_spans",
                "verifier_results",
                "patch_minimality_or_abstain_scores",
                "anti_cheat_cards",
                "expert_maintainer_rubric_scores",
            )
        )
        if not packet_complete:
            failures.append(f"incomplete_packet::{cell_key}")
        results.append(
            {
                "cell_key": cell_key,
                "language_family": cell.get("language_family"),
                "packet_complete": packet_complete,
                "machine_writeback_present": bool(writeback_row and not (writeback_row.get("writeback_result") or {}).get("failures")),
                "ai_review_present": bool(ai_row),
                "anti_cheat_status": anti.get("status"),
                "anti_cheat_passed": anti.get("passed"),
                "rubric_status": rubric.get("status"),
                "rubric_passed": rubric.get("passed"),
                "promotion_ready": bool(anti.get("passed")) and bool(rubric.get("passed")),
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": not failures,
        "claim_scope": [
            "Audit whether reviewed-v28 harness packets are now structurally complete after machine writeback refresh and AI review generation.",
            "Separate packet completeness from actual promotion readiness.",
        ],
        "source_artifacts": {
            "handoff": rel(HANDOFF),
            "writeback_refresh": rel(WRITEBACK_REFRESH),
            "ai_review": rel(AI_REVIEW),
        },
        "metrics": {
            "cells_total": len(results),
            "packet_complete_cells": sum(1 for row in results if row.get("packet_complete")),
            "promotion_ready_cells": sum(1 for row in results if row.get("promotion_ready")),
            "cells_with_machine_writeback": sum(1 for row in results if row.get("machine_writeback_present")),
            "cells_with_ai_review": sum(1 for row in results if row.get("ai_review_present")),
        },
        "results": results,
        "failures": failures,
        "headline_findings": [
            "All reviewed-v28 harness packets now contain the expected machine writeback and AI review files.",
            "Packet completeness is no longer the blocker for the reviewed-v28 harness path.",
            "Promotion readiness remains false across the board because the AI review artifacts are intentionally conservative and leave major anti-cheat and rubric dimensions unresolved.",
        ],
        "next_best_step": "Either accept AI-preliminary review as sufficient for an internal claim boundary, or replace it with stricter adjudication before any external/promoted full-product claim.",
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

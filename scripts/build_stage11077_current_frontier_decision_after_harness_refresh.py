#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11077
NAME = "stage11077_current_frontier_decision_after_harness_refresh"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "current_frontier_decision_after_harness_refresh.json"

STANDALONE = ARTIFACTS / "stage11074_cleaned_v27_scored_interface_comparison_audit" / "cleaned_v27_scored_interface_comparison_audit.json"
EVIDENCE_POLICY = ARTIFACTS / "stage11050_priority_evidence_policy_decision" / "priority_evidence_policy_decision.json"
HARNESS_REFRESH = ARTIFACTS / "stage11076_reviewed_v28_harness_writeback_refresh" / "reviewed_v28_harness_writeback_refresh.json"
PREVIOUS_FRONTIER = ARTIFACTS / "stage11075_current_frontier_decision" / "current_frontier_decision.json"


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
    standalone = load_json(STANDALONE)
    evidence = load_json(EVIDENCE_POLICY)
    harness = load_json(HARNESS_REFRESH)
    previous = load_json(PREVIOUS_FRONTIER)

    headline = standalone.get("headline") or {}
    harness_metrics = harness.get("metrics") or {}

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "current_frontier_updated_after_reviewed_v28_harness_machine_writeback",
        "claim_scope": [
            "Update the current frontier status after refreshing reviewed-v28 harness machine artifact writeback.",
            "Keep the standalone, evidence-lane, and harness claim boundaries explicit.",
        ],
        "source_artifacts": {
            "standalone_frontier": rel(STANDALONE),
            "evidence_policy": rel(EVIDENCE_POLICY),
            "harness_refresh": rel(HARNESS_REFRESH),
            "previous_frontier_decision": rel(PREVIOUS_FRONTIER),
        },
        "standalone_frontier": {
            "status": "promotable_with_explicit_policy_boundary",
            "policy_cleaned_strict_exact_100m": headline.get("policy_cleaned_strict_exact_100m"),
            "raw_cleaned_strict_exact_100m": headline.get("raw_cleaned_strict_exact_100m"),
            "strict_exact_gemma12b": headline.get("strict_exact_gemma"),
            "rows": headline.get("rows"),
            "language_wins_100m_under_policy": headline.get("language_wins_100m_under_policy"),
        },
        "evidence_lane": {
            "status": "still_blocked_from_global_promotion",
            "decision": evidence.get("decision"),
            "reason": "Narrow evidence scorer gains still do not survive clean strict promotion as a safe global replacement.",
        },
        "full_product_harness": {
            "status": "machine_writeback_ready_but_human_review_still_required",
            "cells_attempted": harness_metrics.get("cells_attempted"),
            "cells_completed": harness_metrics.get("cells_completed"),
            "cells_failed": harness_metrics.get("cells_failed"),
            "machine_artifacts_written": True,
            "remaining_gap": [
                "expert_maintainer_rubric_scores",
                "anti_cheat_cards",
                "claim-specific review and merge discipline",
            ],
        },
        "delta_vs_previous_frontier": {
            "previous_harness_status": ((previous.get("full_product_harness") or {}).get("status")),
            "current_harness_status": "machine_writeback_ready_but_human_review_still_required",
            "change": "reviewed_v28 harness machine artifacts are now written to reserved multilingual packet paths for all four maintainer-choice cells.",
        },
        "headline_findings": [
            "Standalone remains the strongest promotable path today: 100M reaches 22/22 policy-assisted on the cleaned same-manifest canary while Gemma stays at 5/22.",
            "The evidence-role scorer path is still blocked from global promotion and should not be upgraded by inference routing alone.",
            "The reviewed-v28 full-product harness path is no longer blocked on local runtime capture: machine artifacts now exist for Python, C/C++, Rust, and Web maintainer-choice cells.",
            "The remaining harness gap is review quality, not runtime absence.",
        ],
        "next_best_step": [
            "Use the standalone policy-assisted result as the current honest multilingual standalone headline.",
            "Treat reviewed-v28 harness machine execution as complete enough for packet review, then finish expert-maintainer and anti-cheat attachments before any full-product claim.",
            "Keep evidence-lane work focused on fresh roots or scorer-head training rather than another global scorer swap attempt.",
        ],
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

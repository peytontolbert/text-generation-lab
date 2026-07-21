#!/usr/bin/env python3
"""Stage12419 current dataset control board after Stage12416/12418."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12419_current_dataset_control_board_v17"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    s12385 = read_json(ROOT / "runs/summaries/stage12385_combined_train_support_ledger_v15_dedup.json")
    s12415 = read_json(ROOT / "runs/summaries/stage12415_selected_test_lineage_repair_audit.json")
    s12416 = read_json(ROOT / "runs/summaries/stage12416_direct_verifier_log_train_support_canonicalizer.json")
    s12417 = read_json(ROOT / "runs/summaries/stage12417_combined_train_support_ledger_v16.json")
    s12418 = read_json(ROOT / "runs/summaries/stage12418_normalized_verifier_observation_sanitized_canonicalizer.json")

    current_count = int(s12417.get("current_admitted_train_support_tasks") or 0)
    control = {
        "stage": STAGE,
        "decision": "control_board_training_blocked_countable_supply_190_derived_projection_lane_available",
        "claim_boundary": "Countable train-support tasks are separated from derived sanitized projections and blocked proof-gap requests. Do not train or claim frontier progress until the 500 task target and QC gates are met.",
        "countable_train_support": {
            "stage12385_baseline_tasks": int(s12385.get("current_admitted_train_support_tasks") or 0),
            "stage12416_net_new_direct_real_log_rows": int(s12416.get("emitted_train_support_rows") or 0),
            "stage12417_current_admitted_train_support_tasks": current_count,
            "remaining_gap_to_500": max(0, 500 - current_count),
            "training_allowed": False,
        },
        "derived_projection_lane": {
            "stage12418_source_record_count": int(s12418.get("source_row_count") or 0),
            "stage12418_sanitized_projection_rows": int(s12418.get("emitted_sanitized_projection_rows") or 0),
            "stage12418_countable_as_new_train_support_rows": int(s12418.get("countable_as_new_train_support_rows") or 0),
            "stage12418_guardrail_scan_passed": bool(s12418.get("guardrail_scan_passed")),
            "usage": "objective-shaping/projection-training candidate only; not root-supply accounting and not proof-floor accounting",
        },
        "blocked_or_request_lanes": {
            "stage12415_unrepaired_selected_test_items": int((s12415.get("counters") or {}).get("unrepaired_items") or 0),
            "stage12415_repairable_items": int((s12415.get("counters") or {}).get("repairable_items") or 0),
            "stage12415_required_upstream_fields": s12415.get("required_upstream_fields") or (s12415.get("counters") or {}).get("required_upstream_fields") or {},
        },
        "guardrail_status": {
            "stage12416_raw_leak_count": int(s12416.get("raw_leak_count") or 0),
            "stage12416_overclaim_count": int(s12416.get("overclaim_count") or 0),
            "stage12417_raw_leak_count": int(s12417.get("raw_leak_count") or 0),
            "stage12417_overclaim_count": int(s12417.get("overclaim_count") or 0),
            "stage12418_raw_leak_count": int(s12418.get("raw_leak_count") or 0),
            "stage12418_overclaim_count": int(s12418.get("overclaim_count") or 0),
            "known_legacy_model_facing_selected_test_text_present_in_stage12417_rows": True,
            "recommended_training_source": "use sanitized Stage12416/12418-style projections for new objectives; do not blindly train on raw legacy selected-test input_text",
        },
        "next_stage_plan": {
            "stage12420": "sanitize selected-test legacy ledger into model-facing central projection rows, or keep it as legacy-only if not needed",
            "stage12421": "find genuinely new direct real verifier observations, prioritizing Stage12204/12205 source rows not already normalized/countable, with strict dedupe",
            "stage12422": "execute replay micro-pilot for Stage12413 Open-SWE proof-gap requests to create non-derivative Level-3/patch-effect evidence",
        },
        "hard_rules_for_subagents": [
            "do not count derivative Stage12216 projections as new root supply",
            "do not count Stage12414/12415 blocked selected-test hashes as rows",
            "do not count PASS_TO_PASS or PASS_CURRENT_STATE as repair proof",
            "do not count FAIL_TO_PASS as repair proof unless pre/post patch causality is proven",
            "do not emit raw command/output/path/source/diff in model-facing artifacts",
            "do not merge raw legacy input_text into the central sanitized graph without a sanitization pass",
        ],
        "language_counts_countable": s12417.get("language_counts") or {},
        "task_counts_countable": s12417.get("task_family_or_record_type_counts") or {},
        "derived_target_counts": s12418.get("target_semantic_counts") or {},
        "derived_source_overlap_counts": s12418.get("derived_source_overlap_counts") or {},
        "training_allowed": False,
        "training_blockers": ["500_countable_train_support_target_not_reached", "central_sanitized_projection_ledger_not_yet_complete"],
    }
    write_json(OUT / "current_dataset_control_board_v17.json", control)
    write_json(SUMMARY, control)
    print(json.dumps(control, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

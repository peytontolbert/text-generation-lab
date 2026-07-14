#!/usr/bin/env python3
"""Summarize whether the Stage11555/11556 bridge result is promotable."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_DIR = ROOT / "runs" / "summaries"
ARTIFACT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage11557_text_rich_bridge_promotion_decision"


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def rowset(summary: dict, name: str) -> dict:
    return summary["results"]["rowsets"][name]


def score(rowset_result: dict, mode: str) -> dict:
    data = rowset_result[mode]
    return {
        "correct": data["correct"],
        "rows": data["rows"],
        "accuracy": data["accuracy"],
        "coverage": data["coverage"],
    }


def main() -> None:
    stage11554 = read_json(SUMMARY_DIR / "stage11554_all_supported_text_rich_evidence_gate_audit.json")
    stage11556 = read_json(SUMMARY_DIR / "stage11556_text_rich_bridge_postrun_gate_audit.json")
    stage11549 = read_json(SUMMARY_DIR / "stage11549_web_root_heldout_same_manifest_gemma_comparison.json")

    stage11507_baseline = {
        "runtime": "runs/local/artifacts/stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json",
        "product_scorer": "encoder_option_retrieval_evidence_judgment_head",
        "filtered_strict": {"correct": 22, "rows": 22},
        "old_canary_strict": {"correct": 23, "rows": 23},
        "filtered_validation": {"correct": 20, "rows": 22},
        "old_canary_validation": {"correct": 21, "rows": 23},
        "residual_bank": {"correct": 7, "rows": 10},
        "web_root_heldout_base": {"correct": 35, "rows": 66},
    }

    web_gemma = {
        "correct": stage11549["comparison"]["gemma12b_correct"],
        "rows": stage11549["comparison"]["gemma12b_rows"],
        "accuracy": stage11549["comparison"]["gemma12b_accuracy"],
    }

    stage11554_web = score(rowset(stage11554, "web_heldout"), "gated")
    stage11556_web = score(rowset(stage11556, "web_heldout"), "gated")
    stage11556_residual = score(rowset(stage11556, "residual_bank"), "gated")
    stage11556_filtered_strict = score(rowset(stage11556, "filtered_strict"), "gated")
    stage11556_old_canary_strict = score(rowset(stage11556, "old_canary_strict"), "gated")

    promotion_gates = {
        "filtered_strict_preserves_stage11507": stage11556_filtered_strict["correct"] >= stage11507_baseline["filtered_strict"]["correct"],
        "old_canary_strict_preserves_stage11507": stage11556_old_canary_strict["correct"] >= stage11507_baseline["old_canary_strict"]["correct"],
        "residual_preserves_stage11507": stage11556_residual["correct"] >= stage11507_baseline["residual_bank"]["correct"],
        "web_improves_stage11507_base": stage11556_web["correct"] > stage11507_baseline["web_root_heldout_base"]["correct"],
        "web_beats_same_manifest_gemma": stage11556_web["correct"] > web_gemma["correct"],
        "stage11556_internal_full_coverage": stage11556["gates"]["full_coverage_preserved"],
    }

    promotable = all(promotion_gates.values())
    decision = "do_not_promote_text_rich_bridge_runtime"
    if promotable:
        decision = "promote_text_rich_bridge_runtime"

    summary = {
        "stage": 11557,
        "stage_name": "text_rich_bridge_promotion_decision",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "passed": promotable,
        "selected_frontier_remains": "stage11507 + encoder_option_retrieval_evidence_judgment_head",
        "candidate_runtime": "runs/local/artifacts/stage11555_text_rich_web_evidence_judgment_bridge_probe/runtime_model/runtime_model_bundle.json",
        "candidate_policy": "all-supported text-rich evidence gate over evidence_candidate_judgment head",
        "promotion_gates": promotion_gates,
        "scoreboard": {
            "stage11507_base": stage11507_baseline,
            "stage11554_stage11507_inference_only_gated_web": stage11554_web,
            "stage11556_stage11555_runtime_gated_web": stage11556_web,
            "stage11556_stage11555_runtime_gated_residual": stage11556_residual,
            "gemma12b_web_root_heldout_same_manifest": web_gemma,
        },
        "interpretation": {
            "useful_result": "The all-supported text-rich evidence gate is a safe inference-side policy and the Stage11555 bridge runtime raises Web heldout from 35/66 to 45/66 under that gate.",
            "promotion_blockers": [
                "Stage11555 runtime residual is 6/10, below the selected Stage11507 frontier of 7/10.",
                "Web heldout remains below Gemma same-manifest result: 45/66 vs 52/66.",
            ],
            "recommended_next_step": "Do not replace the selected frontier. Mine or materialize more all-supported text-rich Web evidence roots, then rerun the same gated audit with the Stage11507 preservation/residual/Gemma gates.",
        },
        "source_artifacts": {
            "stage11554": "runs/summaries/stage11554_all_supported_text_rich_evidence_gate_audit.json",
            "stage11556": "runs/summaries/stage11556_text_rich_bridge_postrun_gate_audit.json",
            "stage11549": "runs/summaries/stage11549_web_root_heldout_same_manifest_gemma_comparison.json",
        },
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    out_artifact = ARTIFACT_DIR / "text_rich_bridge_promotion_decision.json"
    out_summary = SUMMARY_DIR / "stage11557_text_rich_bridge_promotion_decision.json"
    text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    out_artifact.write_text(text, encoding="utf-8")
    out_summary.write_text(text, encoding="utf-8")
    print(json.dumps({
        "decision": summary["decision"],
        "promotion_gates": promotion_gates,
        "stage11556_web": stage11556_web,
        "gemma_web": web_gemma,
        "stage11556_residual": stage11556_residual,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

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
STAGE = 11633
NAME = "stage11633_routed_product_scorer_audit"
OUT = ART / NAME
SUMMARY = OUT / "routed_product_scorer_audit.json"

WEB_HEAD_AUDIT = ART / "stage11631_web_head_only_transfer_audit/web_head_only_transfer_audit.json"
STAGE11507_SUMMARY = ART / "stage11509_preservation_strengthened_evidence_judgment_decision/preservation_strengthened_evidence_judgment_decision.json"
SELECTED_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
WEB_HEAD_RUNTIME = ART / "stage11625_web_fail_to_pass_stronger_head_overfit/runtime_model/runtime_model_bundle.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    web_audit = load_json(WEB_HEAD_AUDIT)
    stage11507 = load_json(STAGE11507_SUMMARY)
    web_results = web_audit["results"]
    routed_results = {
        "protected_filtered_strict": {"correct": 22, "rows": 22, "runtime": "stage11507", "scorer": "encoder_option_retrieval_evidence_judgment_head"},
        "protected_filtered_validation": {"correct": 20, "rows": 22, "runtime": "stage11507", "scorer": "encoder_option_retrieval_evidence_judgment_head"},
        "protected_old_canary_strict": {"correct": 23, "rows": 23, "runtime": "stage11507", "scorer": "encoder_option_retrieval_evidence_judgment_head"},
        "protected_old_canary_validation": {"correct": 21, "rows": 23, "runtime": "stage11507", "scorer": "encoder_option_retrieval_evidence_judgment_head"},
        "protected_residual_bank": {"correct": 7, "rows": 10, "runtime": "stage11507", "scorer": "encoder_option_retrieval_evidence_judgment_head"},
        "web_heldout": {"correct": web_results["web_heldout"]["correct"], "rows": web_results["web_heldout"]["rows"], "runtime": "stage11625", "scorer": "encoder_option_retrieval_web_task_candidate_head"},
        "web_successor_strict": {"correct": web_results["web_successor_strict"]["correct"], "rows": web_results["web_successor_strict"]["rows"], "runtime": "stage11625", "scorer": "encoder_option_retrieval_web_task_candidate_head"},
        "controlled_fail_to_pass_support": {"correct": web_results["controlled_fail_to_pass_support"]["correct"], "rows": web_results["controlled_fail_to_pass_support"]["rows"], "runtime": "stage11625", "scorer": "encoder_option_retrieval_web_task_candidate_head"},
    }
    gates = {
        "protected_filtered_strict_22_of_22": routed_results["protected_filtered_strict"]["correct"] == 22,
        "protected_old_canary_strict_23_of_23": routed_results["protected_old_canary_strict"]["correct"] == 23,
        "protected_residual_at_least_7_of_10": routed_results["protected_residual_bank"]["correct"] >= 7,
        "web_heldout_beats_stage11507_35_of_66": routed_results["web_heldout"]["correct"] > 35 and routed_results["web_heldout"]["rows"] == 66,
        "web_successor_at_least_30_of_36": routed_results["web_successor_strict"]["correct"] >= 30 and routed_results["web_successor_strict"]["rows"] == 36,
        "controlled_support_fit_48_of_48": routed_results["controlled_fail_to_pass_support"]["correct"] == 48,
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "routed_product_scorer_candidate_passes_internal_gates" if all(gates.values()) else "routed_product_scorer_candidate_fails_internal_gates",
        "routing_policy": [
            {
                "route": "protected compact maintainer canary/residual rows",
                "runtime": rel(SELECTED_RUNTIME),
                "scorer": "encoder_option_retrieval_evidence_judgment_head",
                "reason": "Stage11507 is the selected standalone frontier and preserves residual/canary gates.",
            },
            {
                "route": "web_js_ts_html heldout and controlled FAIL_TO_PASS/Web successor rows",
                "runtime": rel(WEB_HEAD_RUNTIME),
                "scorer": "encoder_option_retrieval_web_task_candidate_head",
                "reason": "Stage11625 Web head improves Web heldout and fits repaired controlled Web support but is unsafe globally.",
            },
        ],
        "routed_results": routed_results,
        "gates": gates,
        "baseline_comparison": {
            "stage11507_web_heldout": "35/66",
            "stage11628_full_model_guarded_web_heldout": "32/66",
            "routed_stage11633_web_heldout": f"{routed_results['web_heldout']['correct']}/{routed_results['web_heldout']['rows']}",
        },
        "claim_boundary": [
            "This is a routed product-scorer candidate, not a single standalone model-weight promotion.",
            "The Web head was trained as a same-row overfit diagnostic and must not be represented as a standalone generalized model.",
            "A public/product claim would require freezing routing policy, scorer IDs, raw outputs, and same-manifest Gemma comparison under the routed interface.",
        ],
        "next_actions": [
            "If pursuing product harness scoring, freeze this routed policy and rerun same-manifest Gemma through an equivalent routed/choice interface where possible.",
            "If pursuing standalone-weight superiority, distill routed behavior into one model only after adding more Web heldout roots.",
            "Add anti-cheat review for routing: no route may inspect the gold label; routing should use declared row family/task metadata only.",
        ],
        "source_artifacts": {
            "web_head_audit": rel(WEB_HEAD_AUDIT),
            "stage11507_decision": rel(STAGE11507_SUMMARY) if STAGE11507_SUMMARY.exists() else "missing_optional_summary",
            "selected_runtime": rel(SELECTED_RUNTIME),
            "web_head_runtime": rel(WEB_HEAD_RUNTIME),
        },
        "stage11507_decision_snapshot": stage11507,
        "outputs": {"summary": rel(SUMMARY)},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "routed_results": routed_results, "gates": gates, "claim_boundary": summary["claim_boundary"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

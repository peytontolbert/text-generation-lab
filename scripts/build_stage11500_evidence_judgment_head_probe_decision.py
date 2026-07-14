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
STAGE = 11500
NAME = "stage11500_evidence_judgment_head_probe_decision"
OUT = ART / NAME
SUMMARY = OUT / "evidence_judgment_head_probe_decision.json"

POSTRUN = ART / "stage11499_candidate_set_evidence_judgment_head_postrun_audit/candidate_set_evidence_judgment_head_postrun_audit.json"
STAGE11496 = ART / "stage11496_residual50_candidate_set_probe_decision/residual50_candidate_set_probe_decision.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def metric(summary: dict[str, Any], split: str) -> dict[str, Any]:
    product = summary["scored"]["encoder_option_retrieval_evidence_judgment_head"]
    return product[split]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    postrun = load_json(POSTRUN)
    prior_decision = load_json(STAGE11496)
    gates = postrun["promotion_gates"]
    promoted = all(gates.values())
    product = {
        "filtered_strict": metric(postrun, "filtered_strict"),
        "filtered_validation": metric(postrun, "filtered_validation"),
        "old_canary_strict": metric(postrun, "old_canary_strict"),
        "old_canary_validation": metric(postrun, "old_canary_validation"),
        "residual_bank": metric(postrun, "residual_bank"),
        "bridge_train_rows": metric(postrun, "bridge_train_rows"),
    }
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "reject_stage11498_do_not_promote" if not promoted else "promote_stage11498",
        "classification": "controlled_negative_result_stop_current_residual50_head_variants"
        if not promoted
        else "frontier_candidate",
        "selected_frontier_after_decision": {
            "runtime_stage": 11444 if not promoted else 11498,
            "scorer": "encoder_option_retrieval" if not promoted else "encoder_option_retrieval_evidence_judgment_head",
            "reason": "Stage11498 failed protected promotion gates; selected frontier remains Stage11444."
            if not promoted
            else "Stage11498 passed all protected promotion gates.",
        },
        "stage11498_product_metrics": {
            "filtered_strict": f"{product['filtered_strict']['correct']}/{product['filtered_strict']['rows']}",
            "filtered_validation": f"{product['filtered_validation']['correct']}/{product['filtered_validation']['rows']}",
            "old_canary_strict": f"{product['old_canary_strict']['correct']}/{product['old_canary_strict']['rows']}",
            "old_canary_validation": f"{product['old_canary_validation']['correct']}/{product['old_canary_validation']['rows']}",
            "residual_bank": f"{product['residual_bank']['correct']}/{product['residual_bank']['rows']}",
            "bridge_train_rows": f"{product['bridge_train_rows']['correct']}/{product['bridge_train_rows']['rows']}",
        },
        "promotion_gates": gates,
        "comparison_to_stage11494": postrun.get("comparison_to_stage11494_base_product"),
        "falsified_or_supported_findings": [
            "Candidate-set repair fixed an unsafe data geometry flaw, but Stage11494 showed it did not solve the residual plateau.",
            "Existing evidence_judgment_head training on bridged candidate-set rows does not solve the plateau either.",
            "Stage11498 residual remains 5/10 and protected strict/canary still regress.",
            "Bridge train rows are only 9/61 under the judgment-head product scorer, so the head is not even fitting the repaired support surface reliably.",
            "Current Residual-50 CE/support/sampler/candidate-set/evidence-head variants should stop until the objective is changed more substantially.",
        ],
        "recommended_next_hypothesis": {
            "id": "H_same_root_listwise_product_scorer_required",
            "description": "Train and evaluate a true listwise product scorer over same-root candidates, with one normalized candidate set per state and no letter-token CE as the primary evidence objective.",
            "requirements": [
                "Use Stage11492-style candidate-set rows, but optimize a listwise loss over all options in the same candidate set.",
                "Train candidate scoring directly on candidate role, evidence text, verifier/test anchors, and state text.",
                "Keep Stage11444 replay as preservation, not as the primary loss.",
                "Promote only if old canary strict 23/23, filtered strict 22/22, validation preserved, and residual bank >=6/10.",
            ],
        },
        "stop_condition": "Do not run more Residual-50 support-only, sampler-only, candidate-set-only, or existing-head-only probes before implementing a true listwise/product-scored objective.",
        "source_artifacts": {
            "postrun_audit": rel(POSTRUN),
            "prior_candidate_set_decision": rel(STAGE11496),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, payload)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": payload["decision"], "classification": payload["classification"], "metrics": payload["stage11498_product_metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

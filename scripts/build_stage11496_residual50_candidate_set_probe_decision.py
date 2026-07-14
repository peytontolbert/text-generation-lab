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

STAGE = 11496
NAME = "stage11496_residual50_candidate_set_probe_decision"
OUT = ART / NAME
SUMMARY = OUT / "residual50_candidate_set_probe_decision.json"

POSTRUN = ART / "stage11495_residual50_candidate_set_postrun_audit/residual50_candidate_set_postrun_audit.json"
REQUEST = ART / "stage11493_residual50_candidate_set_probe_request/residual50_candidate_set_probe_request.json"
PACKAGE = ART / "stage11492_residual50_candidate_set_recompiler/residual50_candidate_set_recompiler.json"
STAGE11489 = ART / "stage11489_residual50_sampler_ablation_decision/residual50_sampler_ablation_decision.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    postrun = load_json(POSTRUN)
    request = load_json(REQUEST)
    package = load_json(PACKAGE)
    stage11489 = load_json(STAGE11489)
    product = (postrun.get("scored") or {}).get("encoder_option_retrieval") or {}
    gates = postrun.get("promotion_gates") or {}
    failed = [name for name, passed in gates.items() if not passed]
    comparison = postrun.get("comparison_to_prior_residual50_runs") or {}
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "reject_stage11494_do_not_promote",
        "classification": "controlled_negative_result_stop_residual50_training_probes",
        "selected_frontier_unchanged": {
            "runtime": "runs/local/artifacts/stage11444_targeted_residual_role_support_probe/runtime_model/runtime_model_bundle.json",
            "product_scorer": "encoder_option_retrieval",
            "reason": "Stage11494 preserved the residual plateau at 5/10 but regressed protected strict surfaces to 18/22 and old canary strict to 19/23.",
        },
        "why_not_progress": {
            "failed_gates": failed,
            "filtered_strict": {
                "actual": f"{(product.get('filtered_strict') or {}).get('correct')}/22",
                "required": "22/22",
            },
            "old_canary_strict": {
                "actual": f"{(product.get('old_canary_strict') or {}).get('correct')}/23",
                "required": "23/23",
            },
            "residual_bank": {
                "actual": f"{(product.get('residual_bank') or {}).get('correct')}/10",
                "required": ">5/10",
            },
        },
        "what_was_falsified": [
            "Contradictory sibling rows in Stage11481 were a real data-geometry flaw, but removing them was not sufficient to improve the residual bank.",
            "The current CE plus option-retrieval auxiliary plus contrast objective still shifts protected evidence rows toward F-like predictions.",
            "Residual-50 support-data variants have now failed under raw data, cyclic sampler, and repaired candidate-set geometry.",
        ],
        "controlled_run_comparison": comparison,
        "stop_condition_triggered": {
            "condition": "Do not run another support/sampler/candidate-set probe on Stage11481 or Stage11492 before changing the scorer/objective consumed at evaluation.",
            "reason": "Three controlled Residual-50 probes failed to improve residual above 5/10; two regressed protected strict to 18/22.",
        },
        "next_experiment_contract": {
            "hypothesis_id": "H_product_scored_evidence_head_required",
            "single_changed_variable": "scorer/objective architecture consumed directly at evaluation",
            "recommended_intervention": [
                "implement a product-scored evidence/candidate head trained on candidate_set_id groups",
                "score (state, option_value, normalized_role, evidence_fact_text) directly rather than relying only on cosine option retrieval",
                "train the new head with listwise CE over each candidate set and preservation replay on protected B-evidence strict rows",
                "evaluate the new head as the product scorer only if it preserves old/filtered strict and lifts residual >=6/10",
            ],
            "must_hold_constant": [
                "Stage11444 base runtime for initialization",
                "Stage11492 repaired candidate-set rows for first architecture test",
                "protected validation/strict/residual splits",
                "same promotion gates",
            ],
            "promotion_requires": [
                "old canary strict 23/23",
                "filtered strict 22/22",
                "filtered validation >=20/22",
                "old validation >=21/23",
                "residual bank >=6/10",
                "full bounded-choice coverage",
            ],
        },
        "source_artifacts": {
            "postrun": rel(POSTRUN),
            "request": rel(REQUEST),
            "candidate_set_package": rel(PACKAGE),
            "stage11489_decision": rel(STAGE11489),
        },
        "outputs": {"summary": rel(SUMMARY)},
        "package_metrics": package.get("metrics"),
        "request_metrics": request.get("metrics"),
        "stage11489_reference": {
            "decision": stage11489.get("decision"),
            "stop_condition": ((stage11489.get("next_experiment_contract") or {}).get("stop_condition")),
        },
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "classification": summary["classification"], "why_not_progress": summary["why_not_progress"], "next_experiment_contract": summary["next_experiment_contract"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

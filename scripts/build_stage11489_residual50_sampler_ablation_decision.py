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

STAGE = 11489
NAME = "stage11489_residual50_sampler_ablation_decision"
OUT = ART / NAME
SUMMARY = OUT / "residual50_sampler_ablation_decision.json"

POSTRUN = ART / "stage11488_residual50_sampler_ablation_postrun_audit/residual50_sampler_ablation_postrun_audit.json"
REQUEST = ART / "stage11486_residual50_sampler_ablation_probe_request/residual50_sampler_ablation_probe_request.json"
PREVIOUS_DECISION = ART / "stage11485_residual50_controlled_probe_decision/residual50_controlled_probe_decision.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    postrun = load_json(POSTRUN)
    request = load_json(REQUEST)
    previous = load_json(PREVIOUS_DECISION) if PREVIOUS_DECISION.exists() else {}
    product = (postrun.get("scored") or {}).get("encoder_option_retrieval") or {}
    gates = postrun.get("promotion_gates") or {}
    failed = [name for name, passed in gates.items() if not passed]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "reject_stage11487_do_not_promote",
        "classification": "controlled_negative_result",
        "selected_frontier_unchanged": {
            "runtime": "runs/local/artifacts/stage11444_targeted_residual_role_support_probe/runtime_model/runtime_model_bundle.json",
            "product_scorer": "encoder_option_retrieval",
            "reason": "Stage11487 regressed protected strict surfaces and reduced residual-bank accuracy.",
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
            "Changing only the sampler from residual_family_balanced to cyclic does not repair the Stage11483 protected strict regression.",
            "Cyclic sampling on the same Residual-50 package worsens residual-bank accuracy from 5/10 to 2/10.",
            "The residual problem is not explained solely by residual-family oversampling; current CE+aux+contrast objective geometry is insufficient.",
        ],
        "experiment_control": {
            "single_changed_variable": ((request.get("hypothesis") or {}).get("single_changed_variable")),
            "held_constant": ((request.get("hypothesis") or {}).get("held_constant")),
            "stage11483_previous_decision": previous.get("decision"),
        },
        "next_experiment_contract": {
            "hypothesis_id": "H_listwise_same_root_candidate_objective_needed",
            "rationale": (
                "Both Residual-50 data-only/contrast training and sampler-only ablation failed. "
                "The next useful variable is the candidate objective itself: train scores over same-root candidate sets directly instead of relying on row-wise decoder CE plus generic option retrieval."
            ),
            "single_changed_variable": "objective/scorer architecture: add same-root listwise candidate scoring for bounded-choice rows",
            "must_hold_constant": [
                "Stage11481 Residual-50 data package for the first architecture test",
                "Stage11444 initialization",
                "protected validation/strict/residual splits",
                "promotion scorer contract until a new scorer is explicitly productized",
            ],
            "implementation_targets": [
                "compile same-root candidate groups from rows with opaque_options",
                "optimize listwise softmax or pairwise margin within each candidate set",
                "record margins against candidate_change_surface, verifier_and_test_constraint, and symptom_or_call_path_analogue",
                "preserve old/filtered canary rows with explicit replay or KL",
            ],
            "promotion_requires": [
                "old canary strict 23/23",
                "filtered strict 22/22",
                "filtered validation >=20/22",
                "old validation >=21/23",
                "residual bank >=6/10",
                "full bounded-choice coverage",
            ],
            "stop_condition": "Do not run another support/sampler probe on Stage11481 before implementing a direct listwise or same-root candidate objective.",
        },
        "source_artifacts": {
            "postrun": rel(POSTRUN),
            "request": rel(REQUEST),
            "previous_decision": rel(PREVIOUS_DECISION),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "classification": summary["classification"], "why_not_progress": summary["why_not_progress"], "next": summary["next_experiment_contract"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11218
NAME = "stage11218_evidence_fact_pairwise_decision"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "evidence_fact_pairwise_decision.json"
PAIRWISE = ARTIFACTS / "stage11217_evidence_fact_pairwise_postrun_audit/evidence_fact_pairwise_postrun_audit.json"
FACT_TEXT = ARTIFACTS / "stage11215_evidence_fact_text_decision/evidence_fact_text_decision.json"
TRADEOFF = ARTIFACTS / "stage11211_fresh_verifier_constraint_tradeoff_decision/fresh_verifier_constraint_tradeoff_decision.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def get(payload: dict[str, Any], path: list[str]) -> Any:
    cur: Any = payload
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def compact(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": payload.get("decision"),
        "promotion_gate": payload.get("promotion_gate"),
        "strict": get(payload, ["clean_strict", "row_metric"]),
        "validation": get(payload, ["clean_validation", "row_metric"]),
        "productized_residual": get(payload, ["clean_residual_successor", "productized_result", "row_metric"]),
        "all_residual_scorers": {
            key: value.get("row_metric")
            for key, value in (get(payload, ["clean_residual_successor", "all_scorer_results"]) or {}).items()
            if isinstance(value, dict)
        },
        "residual_by_gold": get(payload, ["clean_residual_successor", "productized_result", "by_gold_value"]),
        "residual_misses": get(payload, ["clean_residual_successor", "productized_result", "misses"]),
    }


def main() -> None:
    pairwise = load_json(PAIRWISE)
    fact_text = load_json(FACT_TEXT)
    tradeoff = load_json(TRADEOFF)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "reject_evidence_fact_pairwise_branch_for_promotion",
        "interpretation": (
            "The separate evidence-fact pair head is implemented and loadable, but the trained Stage11216 runtime does not improve the clean residual bank. "
            "It preserves strict 22/22 and improves validation to 21/23, but productized residual accuracy is 4/10 and verifier_and_test_constraint remains 0/3. "
            "Existing scorer paths on the same runtime remain at the 5/10 baseline, so the head did not produce hidden usable progress."
        ),
        "source_artifacts": {
            "pairwise_postrun": rel(PAIRWISE),
            "fact_text_decision": rel(FACT_TEXT),
            "fresh_support_tradeoff_decision": rel(TRADEOFF),
        },
        "pairwise_stage11217": compact(pairwise),
        "prior_decisions": {
            "stage11215": fact_text.get("decision"),
            "stage11211": tradeoff.get("decision"),
        },
        "blocked_claims": [
            "Do not promote encoder_option_retrieval_evidence_fact_pairwise.",
            "Do not claim verifier_and_test_constraint is repaired; it remains 0/3 on the clean residual bank.",
            "Do not treat validation 21/23 as a frontier gain because residual and Gemma comparison gates fail.",
        ],
        "next_required_work": [
            {
                "priority": 1,
                "work": "Materialize a larger admitted residual-heldout set for verifier_and_test_constraint with balanced candidate_change_surface controls, then split by root before training.",
                "reason": "All scorer/objective variants are overfitting or preserving priors on the tiny 3-row verifier/test residual slice.",
            },
            {
                "priority": 2,
                "work": "Change supervision from label choice to binary candidate validity rows: (state, candidate evidence item) -> decisive/supporting/distractor, with one positive and multiple hard negatives per root.",
                "reason": "Multi-option CE over a tiny row set keeps collapsing to candidate surface; binary candidate validity gives direct negative pressure per candidate.",
            },
            {
                "priority": 3,
                "work": "Keep clean strict 22/22, validation, clean residual 10-row bank, and Gemma row/cluster comparison as fixed gates.",
                "reason": "Recent branches only look useful when one of these gates is omitted.",
            },
        ],
        "outputs": {"summary_json": rel(SUMMARY_JSON)},
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

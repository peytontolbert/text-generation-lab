#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11215
NAME = "stage11215_evidence_fact_text_decision"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "evidence_fact_text_decision.json"
SCORER_AUDIT = ARTIFACTS / "stage11212_evidence_fact_text_scorer_audit/evidence_fact_text_scorer_audit.json"
TRAINED_AUDIT = ARTIFACTS / "stage11214_evidence_fact_text_postrun_audit/evidence_fact_text_postrun_audit.json"
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


def compact_trained(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": payload.get("decision"),
        "promotion_gate": payload.get("promotion_gate"),
        "strict": get(payload, ["clean_strict", "row_metric"]),
        "validation": get(payload, ["clean_validation", "row_metric"]),
        "residual": get(payload, ["clean_residual_successor", "productized_result", "row_metric"]),
        "residual_cluster": get(payload, ["clean_residual_successor", "productized_result", "cluster_metric"]),
        "residual_by_gold": get(payload, ["clean_residual_successor", "productized_result", "by_gold_value"]),
        "residual_misses": get(payload, ["clean_residual_successor", "productized_result", "misses"]),
    }


def compact_scorer(payload: dict[str, Any]) -> dict[str, Any]:
    fact = get(payload, ["results", "encoder_option_retrieval_evidence_fact_text"]) or {}
    product = get(payload, ["results", "encoder_option_retrieval_verifier_conditioned"]) or {}
    return {
        "decision": payload.get("decision"),
        "fact_text": {
            "strict": get(fact, ["strict", "row_metric"]),
            "validation": get(fact, ["validation", "row_metric"]),
            "residual": get(fact, ["residual", "row_metric"]),
            "residual_by_gold": get(fact, ["residual", "by_gold_value"]),
        },
        "productized_reference": {
            "strict": get(product, ["strict", "row_metric"]),
            "validation": get(product, ["validation", "row_metric"]),
            "residual": get(product, ["residual", "row_metric"]),
        },
    }


def main() -> None:
    scorer = load_json(SCORER_AUDIT)
    trained = load_json(TRAINED_AUDIT)
    tradeoff = load_json(TRADEOFF)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "reject_evidence_fact_text_branch_for_promotion",
        "interpretation": (
            "Row-local evidence text is a useful schema correction but not sufficient as a generic option-retrieval objective. "
            "As inference-only it is strict-safe after raw fallback but remains 5/10 on the residual bank. "
            "After training with Stage11205 support and KL preservation it keeps strict at 22/22 but drops the residual bank to 4/10."
        ),
        "source_artifacts": {
            "scorer_only_audit": rel(SCORER_AUDIT),
            "trained_postrun_audit": rel(TRAINED_AUDIT),
            "previous_tradeoff_decision": rel(TRADEOFF),
        },
        "scorer_only_stage11212": compact_scorer(scorer),
        "trained_stage11214": compact_trained(trained),
        "prior_tradeoff_stage11211_decision": tradeoff.get("decision"),
        "blocked_claims": [
            "Do not promote encoder_option_retrieval_evidence_fact_text as a product scorer.",
            "Do not claim verifier_and_test_constraint is repaired; Stage11214 remains 0/3 on that gold role in the residual bank.",
            "Do not run more same-manifest support sweeps without changing row admission or the candidate scoring objective.",
        ],
        "next_required_work": [
            {
                "priority": 1,
                "work": "Create an explicit pairwise semantic candidate objective with role, evidence text, and candidate-control labels supervised directly.",
                "reason": "Text substitution and generic retrieval training both fail to separate verifier_and_test_constraint from candidate_change_surface.",
            },
            {
                "priority": 2,
                "work": "Admit more root-disjoint verifier_and_test_constraint rows with true candidate_change_surface controls and selected-test anchors.",
                "reason": "Current residual-bank verifier/test rows remain 0/3 and the support signal is not stable under strict preservation.",
            },
            {
                "priority": 3,
                "work": "Keep the clean strict 22/22 canary and clean residual bank as gates for every next scorer/objective experiment.",
                "reason": "Recent probes can improve one metric only by damaging another, so both gates are necessary.",
            },
        ],
        "outputs": {"summary_json": rel(SUMMARY_JSON)},
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

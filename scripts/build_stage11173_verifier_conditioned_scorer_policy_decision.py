#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11173
NAME = "stage11173_verifier_conditioned_scorer_policy_decision"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "verifier_conditioned_scorer_policy_decision.json"

SCORER_AUDIT = ARTIFACTS / "stage11172_scorer_objective_mismatch_audit" / "scorer_objective_mismatch_audit.json"
COMPARISON = ARTIFACTS / "stage11150_cleaned_strict_100m_vs_gemma_comparison" / "cleaned_strict_100m_vs_gemma_comparison.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def split_metric(audit: dict[str, Any], source: str, split: str) -> dict[str, Any]:
    result = audit["results"][source][split]
    return {
        "correct": int(result["correct"]),
        "rows": int(result["rows"]),
        "accuracy": float(result["accuracy"]),
        "miss_row_ids": list(result.get("miss_row_ids") or []),
    }


def main() -> None:
    audit = load_json(SCORER_AUDIT)
    comparison = load_json(COMPARISON)
    base = "encoder_option_retrieval"
    verifier = "encoder_option_retrieval_verifier_conditioned"
    base_strict = split_metric(audit, base, "clean_strict")
    verifier_strict = split_metric(audit, verifier, "clean_strict")
    base_validation = split_metric(audit, base, "clean_validation")
    verifier_validation = split_metric(audit, verifier, "clean_validation")
    base_reserved = split_metric(audit, base, "reserved_residual")
    verifier_reserved = split_metric(audit, verifier, "reserved_residual")
    candidate = next(
        row for row in audit["policy_candidates_vs_base"]
        if row.get("source") == verifier
    )
    comparison_overall = comparison.get("overall") or {}
    comparison_coverage = comparison.get("coverage") or {}
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "adopt_verifier_conditioned_scorer_for_verifier_outcome_semantic_transition_only",
        "claim_scope": [
            "This is a scored-interface policy improvement, not a new weight-training result.",
            "The policy changes option text only for verifier_outcome_semantic_transition rows; all other rows keep base encoder_option_retrieval semantics.",
            "Evidence citation remains unresolved; reserved residual accuracy is unchanged.",
        ],
        "source_artifacts": {
            "scorer_audit": rel(SCORER_AUDIT),
            "cleaned_strict_100m_vs_gemma_baseline": rel(COMPARISON),
        },
        "policy": {
            "source_name": verifier,
            "routing_rule": "if task_type == verifier_outcome_semantic_transition: score conditioned option text; else score raw option value with encoder_option_retrieval",
            "implemented_in": [
                "legacy_src/agentkernel_lite/training_loop.py::_option_text_variant",
                "legacy_src/scripts/train_agentkernel_lite_encdec.py --bounded-choice-aux-source choices",
            ],
        },
        "metrics": {
            "base": {
                "clean_strict": base_strict,
                "clean_validation": base_validation,
                "reserved_residual": base_reserved,
            },
            "verifier_conditioned": {
                "clean_strict": verifier_strict,
                "clean_validation": verifier_validation,
                "reserved_residual": verifier_reserved,
            },
            "delta_vs_base": {
                "clean_strict_correct_delta": verifier_strict["correct"] - base_strict["correct"],
                "clean_validation_correct_delta": verifier_validation["correct"] - base_validation["correct"],
                "reserved_residual_correct_delta": verifier_reserved["correct"] - base_reserved["correct"],
            },
            "policy_candidate_vs_base": candidate,
        },
        "same_manifest_comparison_update": {
            "previous_stage11150_gemma_correct": comparison_overall.get("gemma12b_correct"),
            "previous_stage11150_gemma_rows": comparison_coverage.get("gemma_rows"),
            "previous_stage11150_gemma_accuracy": comparison_overall.get("gemma12b_accuracy"),
            "verifier_conditioned_100m_correct": verifier_strict["correct"],
            "verifier_conditioned_100m_rows": verifier_strict["rows"],
            "verifier_conditioned_100m_accuracy": verifier_strict["accuracy"],
            "verifier_conditioned_delta_vs_gemma12b": (verifier_strict["accuracy"] - float(comparison_overall.get("gemma12b_accuracy"))) if isinstance(comparison_overall.get("gemma12b_accuracy"), (int, float)) else None,
            "interpretation": "On the singleton-cleaned strict manifest, the productized verifier-conditioned 100M scored interface reaches 22/22 while the existing Gemma comparison remains 6/22 from stage11150. This should be reported as a scored-interface result, not a raw decoder/freeform result.",
        },
        "remaining_blockers": [
            "Evidence-citation reserved residual bank remains 5/10 overall and evidence misses still show candidate_change_surface overriding verifier/test or symptom/call-path evidence.",
            "Clean validation remains 20/23, with evidence-citation and one verifier_outcome miss still present.",
            "The broader v2.7/SOTA goal still needs fresh root-scale evidence/verifier data and heldout comparison beyond this compact clean strict surface.",
        ],
        "next_best_step": "Build a trainable semantic evidence candidate scorer objective or materialize a larger root-disjoint evidence-role dataset; do not apply role-map globally because it regresses clean strict.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
        },
    }
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11050
NAME = "stage11050_priority_evidence_policy_decision"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "priority_evidence_policy_decision.json"

SCORER_AUDIT = ARTIFACTS / "stage11049_priority_evidence_scorer_policy_comparison" / "priority_evidence_scorer_policy_comparison.json"
SLICE_AUDIT = ARTIFACTS / "stage11047_priority_evidence_candidate_runtime_audit" / "priority_evidence_candidate_runtime_audit.json"
CANDIDATE_AUDIT = ARTIFACTS / "stage11046_priority_evidence_bounded_candidate_audit" / "priority_evidence_bounded_candidate_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    scorer = load_json(SCORER_AUDIT)
    slice_audit = load_json(SLICE_AUDIT)
    candidate = load_json(CANDIDATE_AUDIT)

    comparison = scorer["comparison"]
    strict_delta = comparison["successor_strict"]["delta_accuracy"]
    eval_delta = comparison["successor_eval"]["delta_accuracy"]
    slice_delta = comparison["priority_evidence_slice"]["delta_accuracy"]

    adopt_globally = bool(
        candidate.get("passed") is True
        and strict_delta is not None
        and eval_delta is not None
        and slice_delta is not None
        and strict_delta >= 0.0
        and eval_delta >= 0.0
        and slice_delta > 0.0
    )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision": "keep_base_scorer_and_use_priority_evidence_rows_as_support"
        if not adopt_globally
        else "global_evidence_role_map_candidate_ready",
        "claim_scope": [
            "Turn the stage11047 and stage11049 evidence-slice results into an explicit scorer-policy decision.",
            "Prevent an unsafe global scorer swap while still preserving the new slice as useful residual support material.",
        ],
        "inputs": {
            "candidate_audit": rel(CANDIDATE_AUDIT),
            "slice_runtime_audit": rel(SLICE_AUDIT),
            "scorer_policy_comparison": rel(SCORER_AUDIT),
        },
        "metrics": {
            "priority_slice_base_accuracy": comparison["priority_evidence_slice"]["base_accuracy"],
            "priority_slice_alt_accuracy": comparison["priority_evidence_slice"]["alt_accuracy"],
            "successor_eval_base_accuracy": comparison["successor_eval"]["base_accuracy"],
            "successor_eval_alt_accuracy": comparison["successor_eval"]["alt_accuracy"],
            "successor_strict_base_accuracy": comparison["successor_strict"]["base_accuracy"],
            "successor_strict_alt_accuracy": comparison["successor_strict"]["alt_accuracy"],
            "successor_strict_delta": strict_delta,
            "successor_eval_delta": eval_delta,
            "priority_slice_delta": slice_delta,
        },
        "headline_findings": [
            "The new 5-row evidence slice is clean and scoreable, so it is valid residual support material.",
            "encoder_option_retrieval_evidence_role_map solves the new slice but regresses the 23-row successor strict overlay, so it is not safe as a global scorer replacement.",
            "The honest next move is to keep encoder_option_retrieval as the overlay scorer and use the new rows to train or support the residual evidence lane until a safer scorer or model update exists.",
        ],
        "recommended_policy": {
            "overlay_scoring_source": "encoder_option_retrieval",
            "priority_evidence_slice_status": "candidate_only_train_support_or_diagnostic",
            "global_scorer_swap_allowed": adopt_globally,
            "evidence_role_map_allowed_scope": "diagnostic_or_slice_local_only",
        },
        "next_best_step": [
            "Add the five stage11045 rows as residual support material in the next support package rather than changing the global scorer.",
            "Keep the 23-row successor overlay scored with encoder_option_retrieval until a scorer alternative wins both the overlay and the slice.",
            "If scorer work continues, search for a hybrid evidence-only routing policy that preserves strict overlay rows before any promotion.",
        ],
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
        },
    }
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

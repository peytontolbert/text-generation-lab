#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
AUDIT_PATH = (
    ROOT
    / "runs/local/artifacts/stage11090_pairwise_semantic_evidence_postrun_audit"
    / "pairwise_semantic_evidence_postrun_audit.json"
)
OUT_DIR = ROOT / "runs/local/artifacts/stage11091_pairwise_semantic_evidence_decision"
OUT_PATH = OUT_DIR / "pairwise_semantic_evidence_decision.json"


def main() -> None:
    audit = json.loads(AUDIT_PATH.read_text())
    clean = audit["cleaned_canary_result"]
    reserved = audit["reserved_candidate_result"]
    delta = audit["delta_vs_stage11086"]

    payload = {
        "stage": 11091,
        "stage_name": "stage11091_pairwise_semantic_evidence_decision",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_audit": str(AUDIT_PATH.relative_to(ROOT)),
        "claim_scope": [
            "Freeze the outcome of the current-package pairwise scorer branch.",
            "Decide whether pairwise scorer reuse is the next promotable standalone direction or another negative result.",
        ],
        "result_snapshot": {
            "bounded_choice_aux_source": audit.get("bounded_choice_aux_source"),
            "clean_validation_accuracy": clean["validation_accuracy"],
            "clean_strict_accuracy": clean["strict_accuracy"],
            "reserved_candidate_accuracy": reserved["overall"]["exact_accuracy"],
            "delta_vs_stage11086": delta,
        },
        "decision": {
            "promote_branch": False,
            "keep_current_standalone_contract": True,
            "verdict": "pairwise_scorer_reuse_is_flat_on_current_families",
            "reason": (
                "The pairwise scorer branch produced exactly the same cleaned canary and reserved residual accuracy as stage11086, "
                "so it does not justify changing the current standalone contract."
            ),
            "current_contract_reference": [
                "runs/local/artifacts/stage11073_cleaned_v27_scored_interface_contract_refresh/cleaned_v27_scored_interface_contract_refresh.json",
                "runs/local/artifacts/stage11074_cleaned_v27_scored_interface_comparison_audit/cleaned_v27_scored_interface_comparison_audit.json",
            ],
        },
        "blocking_findings": [
            {
                "finding": "Pairwise scorer reuse did not move the reserved residual evidence bank at all.",
                "evidence": {
                    "reserved_candidate_accuracy": reserved["overall"]["exact_accuracy"],
                    "reserved_evidence_accuracy": (reserved["by_task_type"]["evidence_citation"]["exact_accuracy"] if "evidence_citation" in reserved["by_task_type"] else None),
                    "delta_vs_stage11086": delta["reserved_candidate_accuracy"],
                },
            },
            {
                "finding": "The cleaned canary stayed identical, including the same Python verifier strict miss.",
                "evidence": {
                    "strict_accuracy": clean["strict_accuracy"],
                    "strict_miss_rows": clean["strict_miss_rows"],
                },
            },
            {
                "finding": "The same repeated repo families remain the mismatching residual bank rows.",
                "evidence": {
                    "mismatch_rows": reserved["mismatches"],
                },
            },
        ],
        "next_best_moves": [
            "Stop reusing the same scorer heads on the same residual families as the main path.",
            "Build fresh heldout evidence root families outside repository_library, parametergolf, tokenizers, and candle before the next promotable evidence-lane attempt.",
            "If scorer work continues, make it a new evidence-role-specific or ledger-aware head rather than another reuse of encoder_option_retrieval_pairwise.",
        ],
        "passed": True,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(str(OUT_PATH))


if __name__ == "__main__":
    main()

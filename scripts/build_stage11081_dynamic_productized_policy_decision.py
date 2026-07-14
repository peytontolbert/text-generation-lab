#!/usr/bin/env python3
"""Record the decision from the stage11080 dynamic productized policy audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
AUDIT_PATH = (
    ROOT
    / "runs/local/artifacts/stage11080_dynamic_productized_policy_audit"
    / "dynamic_productized_policy_audit.json"
)
OUT_DIR = ROOT / "runs/local/artifacts/stage11081_dynamic_productized_policy_decision"
OUT_PATH = OUT_DIR / "dynamic_productized_policy_decision.json"


def main() -> None:
    audit = json.loads(AUDIT_PATH.read_text())

    base = audit["base_policy"]
    dynamic_policy = audit["dynamic_productized_policy"]
    composite = audit["composite_policy"]

    decision = {
        "stage": 11081,
        "stage_name": "stage11081_dynamic_productized_policy_decision",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_audit": str(AUDIT_PATH.relative_to(ROOT)),
        "claim_scope": [
            "Freeze the outcome of the stage11080 inference-side scorer audit.",
            "Decide whether dynamic productized retrieval is promotable on the current standalone frontier.",
        ],
        "base_policy_summary": {
            "clean_strict_exact": base["clean_strict"]["exact_accuracy"],
            "clean_validation_exact": base["clean_validation"]["exact_accuracy"],
            "reserved_residual_exact": base["reserved_residual"]["exact_accuracy"],
        },
        "dynamic_productized_summary": {
            "clean_strict_exact": dynamic_policy["clean_strict"]["exact_accuracy"],
            "clean_validation_exact": dynamic_policy["clean_validation"]["exact_accuracy"],
            "reserved_residual_exact": dynamic_policy["reserved_residual"]["exact_accuracy"],
        },
        "composite_policy_summary": {
            "clean_strict_exact": composite["clean_strict"]["exact_accuracy"],
            "clean_validation_exact": composite["clean_validation"]["exact_accuracy"],
            "reserved_residual_exact": composite["reserved_residual"]["exact_accuracy"],
            "definition": composite["definition"],
        },
        "decision": {
            "promote_dynamic_productized_policy": False,
            "keep_current_scored_interface_contract": True,
            "current_contract_reference": [
                "runs/local/artifacts/stage11073_cleaned_v27_scored_interface_contract_refresh/cleaned_v27_scored_interface_contract_refresh.json",
                "runs/local/artifacts/stage11074_cleaned_v27_scored_interface_comparison_audit/cleaned_v27_scored_interface_comparison_audit.json",
            ],
            "reason": (
                "Dynamic productized retrieval improves some evidence rows but regresses the cleaned strict canary, "
                "and the composite policy does not improve the reserved residual bank."
            ),
        },
        "blocking_findings": [
            {
                "finding": "Dynamic productized retrieval is not safe as a global evidence-citation scorer.",
                "evidence": {
                    "base_clean_strict_exact": base["clean_strict"]["exact_accuracy"],
                    "dynamic_clean_strict_exact": dynamic_policy["clean_strict"]["exact_accuracy"],
                    "composite_clean_strict_exact": composite["clean_strict"]["exact_accuracy"],
                },
            },
            {
                "finding": "The composite policy preserves the verifier-transition override but still regresses the cleaned strict surface.",
                "evidence": {
                    "base_clean_strict_miss_rows": base["clean_strict"]["miss_rows"],
                    "composite_clean_strict_miss_rows": composite["clean_strict"]["miss_rows"],
                },
            },
            {
                "finding": "The reserved residual evidence bank does not improve under the composite policy.",
                "evidence": {
                    "base_reserved_exact": base["reserved_residual"]["exact_accuracy"],
                    "composite_reserved_exact": composite["reserved_residual"]["exact_accuracy"],
                },
            },
        ],
        "next_best_moves": [
            "Keep the current verifier-only scored-interface boundary as the standalone promoted contract.",
            "Pursue semantic evidence-candidate scoring or evidence-role-specific scorer heads instead of more inference routing tweaks.",
            "Continue replenishing fresh non-aliased evidence roots before attempting another scorer promotion.",
        ],
        "passed": True,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n")
    print(str(OUT_PATH))


if __name__ == "__main__":
    main()

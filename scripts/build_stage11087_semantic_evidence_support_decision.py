#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
AUDIT_PATH = (
    ROOT
    / "runs/local/artifacts/stage11086_semantic_evidence_support_postrun_audit"
    / "semantic_evidence_support_postrun_audit.json"
)
OUT_DIR = ROOT / "runs/local/artifacts/stage11087_semantic_evidence_support_decision"
OUT_PATH = OUT_DIR / "semantic_evidence_support_decision.json"


def main() -> None:
    audit = json.loads(AUDIT_PATH.read_text())

    clean = audit["cleaned_canary_result"]
    reserved = audit["reserved_candidate_result"]
    delta = audit["delta_vs_stage11080_base_policy"]

    payload = {
        "stage": 11087,
        "stage_name": "stage11087_semantic_evidence_support_decision",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_audit": str(AUDIT_PATH.relative_to(ROOT)),
        "claim_scope": [
            "Freeze the outcome of the stage11082 semantic evidence support probe.",
            "Decide whether the semantic evidence support branch is promotable or whether it remains a negative/diagnostic result.",
        ],
        "result_snapshot": {
            "clean_validation_accuracy": clean["validation_accuracy"],
            "clean_strict_accuracy": clean["strict_accuracy"],
            "reserved_candidate_accuracy": reserved["overall"]["exact_accuracy"],
            "delta_vs_stage11080_base_policy": delta,
        },
        "decision": {
            "promote_branch": False,
            "keep_current_standalone_contract": True,
            "verdict": "semantic_support_preserved_canary_but_did_not_move_reserved_evidence_bank",
            "reason": (
                "The branch preserved the cleaned canary but left the reserved residual bank flat at 0.5, "
                "so it does not justify changing the current standalone contract."
            ),
            "current_contract_reference": [
                "runs/local/artifacts/stage11073_cleaned_v27_scored_interface_contract_refresh/cleaned_v27_scored_interface_contract_refresh.json",
                "runs/local/artifacts/stage11074_cleaned_v27_scored_interface_comparison_audit/cleaned_v27_scored_interface_comparison_audit.json",
            ],
        },
        "blocking_findings": [
            {
                "finding": "Semantic evidence-role supervision did not improve the reserved evidence residual bank.",
                "evidence": {
                    "reserved_candidate_accuracy": reserved["overall"]["exact_accuracy"],
                    "reserved_candidate_rows": reserved["overall"]["rows"],
                    "reserved_evidence_accuracy": (reserved["by_task_type"]["evidence_citation"]["exact_accuracy"] if "evidence_citation" in reserved["by_task_type"] else None),
                },
            },
            {
                "finding": "The main Python verifier strict miss remains unchanged.",
                "evidence": {
                    "strict_miss_rows": clean["strict_miss_rows"],
                },
            },
            {
                "finding": "Several reserved evidence rows still show decoder/retrieval disagreement or poor target rank.",
                "evidence": {
                    "mismatch_rows": reserved["mismatches"],
                },
            },
        ],
        "next_best_moves": [
            "Do not run more semantic evidence support probes with the same scorer head and same ready-lane geometry.",
            "Move to a richer scorer objective or architecture, such as pairwise candidate-versus-verifier scoring that is consumed directly by encoder_option_retrieval_pairwise or a new evidence-role-specific head.",
            "Add fresh non-aliased heldout evidence roots, especially outside the current repository_library/parametergolf/tokenizers families, before the next promotable evidence-lane attempt.",
        ],
        "passed": True,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(str(OUT_PATH))


if __name__ == "__main__":
    main()

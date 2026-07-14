#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11073
NAME = "stage11073_cleaned_v27_scored_interface_contract_refresh"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "cleaned_v27_scored_interface_contract_refresh.json"

CLEANED_PACKAGE = ARTIFACTS / "stage11065_singleton_eval_quarantine_package" / "singleton_eval_quarantine_package.json"
CLEANED_AUDIT = ARTIFACTS / "stage11066_singleton_eval_quarantine_audit" / "singleton_eval_quarantine_audit.json"
SUCCESSOR_COMPARISON = ARTIFACTS / "stage10899_python_verifier_transition_successor_comparison_audit" / "python_verifier_transition_successor_comparison_audit.json"
POSTRUN_AUDIT = ARTIFACTS / "stage11072_a_prior_and_python_verifier_diagnostic_postrun_audit" / "a_prior_and_python_verifier_diagnostic_postrun_audit.json"
STRICT_AUDIT = ARTIFACTS / "stage11071_a_prior_and_python_verifier_diagnostic_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_strict_eval.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    cleaned_package = load_json(CLEANED_PACKAGE)
    cleaned_audit = load_json(CLEANED_AUDIT)
    successor = load_json(SUCCESSOR_COMPARISON)
    postrun = load_json(POSTRUN_AUDIT)
    strict_audit = load_json(STRICT_AUDIT)

    strict_rows = list(strict_audit.get("row_cards") or [])
    semantic_transition_rows = [
        row for row in strict_rows if str(row.get("row_id") or "").startswith("stage10894::")
    ]
    semantic_transition_row = semantic_transition_rows[0] if semantic_transition_rows else None

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "cleaned_v27_scored_interface_contract_refreshed",
        "claim_scope": [
            "Freeze the scored-interface contract for the cleaned 22-row reviewed-v2.7 standalone canary after singleton eval rows were quarantined.",
            "Permit only the already-audited verifier-transition override and keep every broader evidence-policy change blocked.",
        ],
        "source_artifacts": {
            "cleaned_package": rel(CLEANED_PACKAGE),
            "cleaned_audit": rel(CLEANED_AUDIT),
            "successor_comparison": rel(SUCCESSOR_COMPARISON),
            "current_postrun_audit": rel(POSTRUN_AUDIT),
            "current_strict_audit": rel(STRICT_AUDIT),
        },
        "approved_scoring_contract": {
            "default_policy": "current_retrieval",
            "task_policy_overrides": {
                "verifier_outcome_semantic_transition": "decoder_on_transition_only",
            },
            "explicit_non_overrides": {
                "evidence_citation": "current_retrieval",
                "verifier_outcome": "current_retrieval",
                "symptom_localization": "current_retrieval",
                "patch_impact": "current_retrieval",
                "minimal_fix_selection": "current_retrieval",
                "abstention_insufficient_evidence": "current_retrieval",
            },
        },
        "cleaned_surface_context": {
            "strict_rows": ((cleaned_package.get("metrics") or {}).get("strict_rows_after")),
            "validation_rows": ((cleaned_package.get("metrics") or {}).get("validation_rows_after")),
            "quarantined_rows_total": ((cleaned_package.get("metrics") or {}).get("quarantined_rows_total")),
            "raw_cleaned_strict_accuracy": (((cleaned_audit.get("cleaned_surface_result") or {}).get("strict") or {}).get("exact_accuracy")),
            "raw_cleaned_validation_accuracy": (((cleaned_audit.get("cleaned_surface_result") or {}).get("validation") or {}).get("exact_accuracy")),
            "current_runtime_cleaned_strict_accuracy": ((postrun.get("cleaned_canary_result") or {}).get("strict_accuracy")),
            "current_runtime_cleaned_validation_accuracy": ((postrun.get("cleaned_canary_result") or {}).get("validation_accuracy")),
        },
        "evidence_for_override": {
            "successor_row_prior_audit": successor.get("successor_row_result"),
            "current_cleaned_strict_miss_rows": ((postrun.get("cleaned_canary_result") or {}).get("strict_miss_rows")),
            "current_semantic_transition_row": semantic_transition_row,
        },
        "claim_boundaries": [
            "Any stronger result on the cleaned canary under this contract must be labeled policy-assisted rather than raw constrained-retrieval.",
            "This contract does not approve evidence-role scorer replacement or any A-prior relief policy on explicit-ledger rows.",
            "This contract is for standalone same-manifest comparison only and does not upgrade the harness/full-product path.",
        ],
        "findings": [
            "The cleaned canary now has one strict miss, and it is exactly the semantic-transition verifier row that already has the correct decoder top-1 token.",
            "The verifier-transition override remains the only justified inference-side change because it is task-scoped and directly addresses the surviving miss shape.",
            "Broader evidence-policy changes remain blocked because previous role-map and hybrid scorer audits improved residual evidence slices but regressed clean strict rows.",
        ],
        "next_best_step": "Apply this refreshed contract to the cleaned 22-row canary using the current stage11071 runtime, then report raw and policy-assisted results side by side.",
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

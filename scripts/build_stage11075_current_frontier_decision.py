#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11075
NAME = "stage11075_current_frontier_decision"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "current_frontier_decision.json"

STANDALONE_CONTRACT = ARTIFACTS / "stage11073_cleaned_v27_scored_interface_contract_refresh" / "cleaned_v27_scored_interface_contract_refresh.json"
STANDALONE_AUDIT = ARTIFACTS / "stage11074_cleaned_v27_scored_interface_comparison_audit" / "cleaned_v27_scored_interface_comparison_audit.json"
RAW_POSTRUN = ARTIFACTS / "stage11072_a_prior_and_python_verifier_diagnostic_postrun_audit" / "a_prior_and_python_verifier_diagnostic_postrun_audit.json"
EVIDENCE_POLICY = ARTIFACTS / "stage11050_priority_evidence_policy_decision" / "priority_evidence_policy_decision.json"
EVIDENCE_GATE = ARTIFACTS / "stage11056_explicit_ledger_gated_scorer_policy_audit" / "explicit_ledger_gated_scorer_policy_audit.json"
HARNESS_WRITEBACK = ARTIFACTS / "stage10138_canonical_harness_local_runtime" / "reviewed_full_product_harness_python_maintainer_choice" / "writeback_result.json"
HARNESS_PENDING_PACKET = ARTIFACTS / "stage9756_full_product_harness_review_packets" / "review_packets" / "full_product_harness__python__symbol_binding" / "harness_run_id.txt"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    standalone_contract = load_json(STANDALONE_CONTRACT)
    standalone_audit = load_json(STANDALONE_AUDIT)
    raw_postrun = load_json(RAW_POSTRUN)
    evidence_policy = load_json(EVIDENCE_POLICY)
    evidence_gate = load_json(EVIDENCE_GATE)
    harness_writeback = load_json(HARNESS_WRITEBACK)
    harness_pending_packet = load_text(HARNESS_PENDING_PACKET).strip().splitlines()

    headline = standalone_audit.get("headline") or {}
    raw_clean = (raw_postrun.get("cleaned_canary_result") or {})
    evidence_metrics = evidence_policy.get("metrics") or {}
    gated_comparison = evidence_gate.get("comparison") or {}

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "current_frontier_split_between_promotable_standalone_and_blocked_harness",
        "claim_scope": [
            "Freeze the current honest standalone frontier after the cleaned scored-interface refresh.",
            "Explicitly separate the promotable standalone same-manifest claim from the still-blocked evidence-scorer and full-product harness claim paths.",
        ],
        "source_artifacts": {
            "standalone_contract": rel(STANDALONE_CONTRACT),
            "standalone_audit": rel(STANDALONE_AUDIT),
            "raw_postrun": rel(RAW_POSTRUN),
            "evidence_policy": rel(EVIDENCE_POLICY),
            "evidence_gate": rel(EVIDENCE_GATE),
            "harness_writeback": rel(HARNESS_WRITEBACK),
            "harness_pending_packet": rel(HARNESS_PENDING_PACKET),
        },
        "standalone_frontier": {
            "status": "promotable_with_explicit_policy_boundary",
            "raw_cleaned_strict_exact_100m": headline.get("raw_cleaned_strict_exact_100m"),
            "policy_cleaned_strict_exact_100m": headline.get("policy_cleaned_strict_exact_100m"),
            "strict_exact_gemma12b": headline.get("strict_exact_gemma"),
            "policy_delta_100m_minus_gemma12b": headline.get("policy_delta_100m_minus_gemma"),
            "rows": headline.get("rows"),
            "language_wins_100m_under_policy": headline.get("language_wins_100m_under_policy"),
            "language_wins_gemma_under_policy": headline.get("language_wins_gemma_under_policy"),
            "language_ties_under_policy": headline.get("language_ties_under_policy"),
            "raw_cleaned_strict_miss_rows": raw_clean.get("strict_miss_rows"),
            "contract_boundary": (standalone_contract.get("claim_boundaries") or []),
        },
        "evidence_lane": {
            "status": "blocked_from_global_promotion",
            "base_overlay_policy": ((evidence_policy.get("recommended_policy") or {}).get("overlay_scoring_source")),
            "priority_slice_alt_accuracy": evidence_metrics.get("priority_slice_alt_accuracy"),
            "priority_slice_base_accuracy": evidence_metrics.get("priority_slice_base_accuracy"),
            "successor_strict_alt_accuracy": evidence_metrics.get("successor_strict_alt_accuracy"),
            "successor_strict_base_accuracy": evidence_metrics.get("successor_strict_base_accuracy"),
            "explicit_ledger_gate_priority_accuracy": (((gated_comparison.get("priority_evidence_slice") or {}).get("explicit_ledger_gated_accuracy"))),
            "explicit_ledger_gate_successor_strict_accuracy": (((gated_comparison.get("successor_strict") or {}).get("explicit_ledger_gated_accuracy"))),
            "blocking_reason": "Role-mapped or gated evidence scoring helps the narrow priority slice but is not yet safe as a global replacement on the clean strict surface.",
        },
        "full_product_harness": {
            "status": "not_claim_ready",
            "runtime_surface_exists": True,
            "runtime_machine_artifacts_expected": harness_writeback.get("machine_artifacts_only"),
            "runtime_validated_runs": harness_writeback.get("validated_runs"),
            "runtime_written_runs": harness_writeback.get("written_runs"),
            "runtime_failures": harness_writeback.get("failures"),
            "pending_packet_status": harness_pending_packet,
            "blocking_reason": "The local runtime scaffold exists, but the full-product review packets still show pending real harness_run_id and no validated same-task-pack execution evidence.",
        },
        "headline_findings": [
            "The standalone path is now stronger than before: the cleaned 22-row canary becomes 22/22 under the frozen verifier-transition override while Gemma stays at 5/22.",
            "That standalone gain is inference-policy-assisted, not a new training breakthrough, so the raw-vs-policy boundary must remain explicit.",
            "The evidence-role lane is still the main blocked standalone weakness because narrow scorer fixes improve residual slices without surviving clean strict promotion.",
            "The full-product harness path is still separate and unproven: runtime payload/writeback scaffolding exists, but real harness-run evidence is still pending in the review packets.",
        ],
        "next_best_step": [
            "Use the cleaned policy-assisted standalone result as the current honest multilingual headline for the standalone path.",
            "Do not promote any global evidence scorer change yet; continue with fresh evidence-root materialization or scorer-head training instead of more small routing tweaks.",
            "Keep the full-product harness claim blocked until the local runtime writes real harness_run_id, same_task_pack_as_gemma12b, tool_trace_spans, verifier_results, and patch_minimality_or_abstain_scores back into the review packets.",
        ],
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

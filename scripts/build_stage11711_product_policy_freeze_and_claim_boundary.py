#!/usr/bin/env python3
"""Freeze the current compact product-policy frontier and claim boundary.

This stage intentionally performs no model scoring. It collates the selected
frontier, hardened compact comparison, bridged Web policy, and permutation audit
into one auditable product-policy status card.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs/local/artifacts/stage11711_product_policy_freeze_and_claim_boundary"
SUMMARY_PATH = ROOT / "runs/summaries/stage11711_product_policy_freeze_and_claim_boundary.json"

SOURCE_PATHS = {
    "stage11509_promotion": ROOT
    / "runs/local/artifacts/stage11509_preservation_strengthened_frontier_promotion_decision/"
    / "preservation_strengthened_frontier_promotion_decision.json",
    "stage11510_compact_gemma": ROOT
    / "runs/local/artifacts/stage11510_selected_frontier_same_manifest_gemma_comparison/"
    / "selected_frontier_same_manifest_gemma_comparison.json",
    "stage11516_hardened_compact": ROOT
    / "runs/local/artifacts/stage11516_selected_frontier_hardened_subset_comparison/"
    / "stage11516_selected_frontier_hardened_subset_comparison.json",
    "stage11709_web_policy": ROOT
    / "runs/local/artifacts/stage11709_web_source_grounded_nonverifier_policy_audit/"
    / "web_source_grounded_nonverifier_policy_audit.json",
    "stage11710_web_permutation": ROOT
    / "runs/local/artifacts/stage11710_web_source_grounded_policy_permutation_audit/"
    / "web_source_grounded_policy_permutation_audit.json",
}


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def require_sources() -> dict[str, dict[str, Any]]:
    missing = [str(path) for path in SOURCE_PATHS.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("missing required source artifacts: " + ", ".join(missing))
    return {name: read_json(path) for name, path in SOURCE_PATHS.items()}


def main() -> None:
    sources = require_sources()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    compact = sources["stage11510_compact_gemma"]["metrics"]
    hardened = sources["stage11516_hardened_compact"]["metrics"]
    web = sources["stage11709_web_policy"]
    web_perm = sources["stage11710_web_permutation"]
    promotion = sources["stage11509_promotion"]

    gates = {
        "selected_frontier_promoted": promotion.get("decision")
        == "promote_stage11507_as_selected_frontier",
        "compact_same_manifest_100m_beats_gemma": compact["hundred_m_correct"]
        > compact["gemma_correct"],
        "hardened_compact_100m_beats_gemma": hardened["hundred_m_correct"]
        > hardened["gemma_correct"],
        "web_bridged_policy_100m_beats_gemma": web["metrics"]["correct"]
        > web["baselines"]["gemma"]["correct"],
        "web_bridged_policy_beats_stage11703": web["metrics"]["correct"]
        > web["baselines"]["stage11703"]["correct"],
        "web_policy_permutation_stable": web_perm["gates"][
            "all_three_permutations_66_of_66"
        ],
        "web_policy_anticheat_clean": all(
            web["gates"][key]
            for key in (
                "no_singletons",
                "no_prompt_label_leaks",
                "no_prompt_target_value_leaks",
            )
        ),
        "protected_filtered_strict_preserved": web["gates"][
            "protected_filtered_strict"
        ],
        "protected_old_canary_strict_preserved": web["gates"][
            "protected_old_canary_strict"
        ],
        "protected_residual_preserved": web["gates"]["protected_residual"],
    }

    supported_claims = [
        (
            "Stage11507 with encoder_option_retrieval_evidence_judgment_head is "
            "the selected compact multilingual frontier before the Web policy."
        ),
        (
            "On the matched compact maintainer-choice packet, the 100M selected "
            f"frontier scores {compact['hundred_m_correct']}/{compact['matched_rows']} "
            f"versus Gemma {compact['gemma_correct']}/{compact['matched_rows']}."
        ),
        (
            "On the hardened compact subset, after removing the worst shortcut "
            f"rows, the 100M selected frontier scores {hardened['hundred_m_correct']}/"
            f"{hardened['rows']} versus Gemma {hardened['gemma_correct']}/"
            f"{hardened['rows']}."
        ),
        (
            "On the canonical-bridged Web compact heldout, the Stage11709 "
            f"source-grounded product policy scores {web['metrics']['correct']}/"
            f"{web['metrics']['rows']} versus Gemma {web['baselines']['gemma']['correct']}/"
            f"{web['baselines']['gemma']['rows']}."
        ),
        (
            "Stage11710 shows the Stage11709 Web policy remains 66/66 under three "
            "deterministic option permutations."
        ),
    ]

    unsupported_claims = [
        "Broad source-heldout maintainer superiority across languages.",
        "Executable patch repair or end-to-end software repair.",
        "Freeform code generation quality.",
        "Full-product harness patch/verifier workflow superiority.",
        "A learned Web weight update from Stage11709; Stage11709 is an inference policy.",
    ]

    artifact = {
        "stage": 11711,
        "stage_name": "product_policy_freeze_and_claim_boundary",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": (
            "freeze_stage11507_plus_stage11709_as_current_compact_product_policy_candidate"
        ),
        "passed": all(gates.values()),
        "selected_policy": {
            "base_multilingual_runtime": promotion["selected_frontier_after_decision"],
            "web_identity_runtime": web["runtime"],
            "web_policy_components": [
                "Stage11690 canonical bridge for original Web heldout rows",
                "Stage11702 visible verifier-transition normalization for verifier_outcome",
                "Stage11709 visible source-grounded reranking for symptom/localization and minimal-fix identity rows",
            ],
            "product_scorer_contract": (
                "Use selected compact multilingual scorer for non-Web compact surfaces; "
                "use Stage11709 Web source-grounded policy for canonical-bridged Web compact heldout."
            ),
        },
        "metrics": {
            "compact_same_manifest": {
                "hundred_m": {
                    "correct": compact["hundred_m_correct"],
                    "rows": compact["matched_rows"],
                    "accuracy": compact["hundred_m_accuracy"],
                },
                "gemma": {
                    "correct": compact["gemma_correct"],
                    "rows": compact["matched_rows"],
                    "accuracy": compact["gemma_accuracy"],
                },
                "delta_accuracy": compact["delta_accuracy"],
            },
            "compact_hardened_subset": {
                "hundred_m": {
                    "correct": hardened["hundred_m_correct"],
                    "rows": hardened["rows"],
                    "accuracy": hardened["hundred_m_accuracy"],
                },
                "gemma": {
                    "correct": hardened["gemma_correct"],
                    "rows": hardened["rows"],
                    "accuracy": hardened["gemma_accuracy"],
                },
                "delta_accuracy": hardened["delta_accuracy"],
            },
            "web_canonical_bridged": {
                "hundred_m_policy": {
                    "correct": web["metrics"]["correct"],
                    "rows": web["metrics"]["rows"],
                    "accuracy": web["metrics"]["accuracy"],
                },
                "stage11703_baseline": web["baselines"]["stage11703"],
                "gemma": web["baselines"]["gemma"],
                "permutation_results": web_perm["permutation_results"],
            },
        },
        "gates": gates,
        "supported_claims": supported_claims,
        "unsupported_claims": unsupported_claims,
        "claim_boundary": {
            "headline": (
                "Current evidence supports a compact bounded-choice maintainer "
                "product-policy win over Gemma on matched compact packets and "
                "canonical-bridged Web compact heldout."
            ),
            "scope_limit": (
                "This is a compact decision/scoring result. It is not yet a "
                "full executable repair or broad source-heldout software "
                "maintenance result."
            ),
        },
        "recommended_next": [
            "Productize the Stage11709 Web policy as an explicit scorer route, or train an equivalent source-grounded Web candidate head.",
            "Build source-heldout multilingual smoke rows with no singleton options, deterministic option shuffle, verifier/test anchors, and no prompt target leaks.",
            "Add executable patch/verifier rows before making full-product harness claims.",
            "Keep Stage11507/11709 compact packets as regression gates while scaling root-based verifier-backed training data.",
        ],
        "source_artifacts": {name: str(path.relative_to(ROOT)) for name, path in SOURCE_PATHS.items()},
        "outputs": {
            "artifact": str(
                (OUT_DIR / "product_policy_freeze_and_claim_boundary.json").relative_to(ROOT)
            ),
            "summary": str(SUMMARY_PATH.relative_to(ROOT)),
        },
    }

    out_path = OUT_DIR / "product_policy_freeze_and_claim_boundary.json"
    out_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    shutil.copyfile(out_path, SUMMARY_PATH)
    print(json.dumps({"artifact": str(out_path), "summary": str(SUMMARY_PATH), "passed": artifact["passed"]}, indent=2))


if __name__ == "__main__":
    main()

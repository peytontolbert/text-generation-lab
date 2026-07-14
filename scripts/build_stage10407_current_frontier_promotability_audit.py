#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10407
NAME = "stage10407_current_frontier_promotability_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "current_frontier_promotability_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

FRONTIER = ROOT / "runs/local/artifacts/stage10404_generic_policy_frontier_eval/language_conditioned_frontier_eval.json"
GEMMA = ROOT / "runs/local/artifacts/stage10406_gemma_same_frontier_comparison/gemma_same_frontier_comparison.json"
ANTI_CHEAT = ROOT / "runs/local/artifacts/stage10405_python_verifier_drop_extension_anti_cheat_audit/python_verifier_drop_extension_anti_cheat_audit.json"
STALE_ATLAS = ROOT / "runs/local/artifacts/stage10233_train_support_replenishment_atlas/train_support_replenishment_atlas.json"
PYTHON_REVIEW = ROOT / "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets/review_packets/stage10119__localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_25t16_28_28_019abbd8_55f2_7781_97b4_efce_models_cli_py_models_scripts_build_repo_graphs_py_models_scripts_preprocess_pdfs_bde13d0440_aug_1500000_8b46e7f662__python"
C_CPP_REVIEW = ROOT / "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets/review_packets/stage10119__localsess_parametergolf_sessseed_codex_sessions_rollout_2026_03_28t16_57_23_019d3561_0381_7b01_8350_0c0a_peytontolbert_parameter_golf_records_track_10min_16mb_2026_03_26_statespace_caus_49a543bb0b_aug_1500000_8b46e7f662__c_cpp"
RUST_NN_REVIEW = ROOT / "runs/local/artifacts/stage10127_true_source_backed_rust_review_packets_and_signoff/review_packets/stage10126__candle__candle-nn__rust"
RUST_EXAMPLES_REVIEW = ROOT / "runs/local/artifacts/stage10127_true_source_backed_rust_review_packets_and_signoff/review_packets/stage10126__candle__candle-examples__rust"
WEB_REPLENISHMENT = ROOT / "runs/local/artifacts/stage10176_code_assist_web_replenishment_bundle/code_assist_web_replenishment_bundle.json"
WEB_REPLENISHMENT_ADMITTED = ROOT / "runs/local/artifacts/stage10176_code_assist_web_replenishment_bundle/code_assist_web_replenishment_admitted_manifest.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def review_status(base: Path) -> dict[str, Any]:
    rubric = load_json(base / "expert_maintainer_rubric_review.json")
    anti = load_json(base / "anti_cheat_review_card.json")
    gold = load_json(base / "perspective_gold_adjudication.json")
    return {
        "bundle_id": rubric.get("bundle_id") or anti.get("bundle_id") or gold.get("bundle_id"),
        "rubric_passed": rubric.get("passed"),
        "bundle_valid_for_eval": rubric.get("bundle_valid_for_eval"),
        "anti_cheat_passed": anti.get("passed"),
        "admissible_for_same_surface_comparison": anti.get("admissible_for_same_surface_comparison"),
        "gold_ready_for_eval": gold.get("bundle_gold_ready_for_eval"),
        "decision_rationale": rubric.get("decision_rationale") or anti.get("decision_rationale") or gold.get("decision_rationale"),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)

    frontier = load_json(FRONTIER)
    gemma = load_json(GEMMA)
    anti_cheat = load_json(ANTI_CHEAT)
    stale_atlas = load_json(STALE_ATLAS)
    web_bundle = load_json(WEB_REPLENISHMENT)
    web_admitted = load_json(WEB_REPLENISHMENT_ADMITTED)
    web_rows = web_admitted.get("rows") or []

    refreshed_inventory = {
        "python_extra_bundle": review_status(PYTHON_REVIEW),
        "c_cpp_extra_bundle": review_status(C_CPP_REVIEW),
        "rust_candle_nn_bundle": review_status(RUST_NN_REVIEW),
        "rust_candle_examples_bundle": review_status(RUST_EXAMPLES_REVIEW),
        "web_replenishment_bundle": {
            "bundle_id": web_bundle.get("bundle_id"),
            "language_family": web_bundle.get("language_family"),
            "repo_id": web_bundle.get("repo_id"),
            "supports_training_or_scoring_now": ((web_bundle.get("claim_boundary") or {}).get("supports_training_or_scoring_now")),
            "mixed_language_web_root": ((web_bundle.get("claim_boundary") or {}).get("mixed_language_web_root")),
            "selected_tests": web_bundle.get("selected_tests"),
            "admitted_row_count": web_admitted.get("row_count"),
            "admitted_language_counts": dict(Counter(row.get("language_family") for row in web_rows)),
        },
    }

    stale_pending_candidates = []
    for candidate in stale_atlas.get("replenishment_candidates") or []:
        if "pending_human_review" in json.dumps(candidate.get("review_status") or {}):
            stale_pending_candidates.append(candidate.get("bundle_id"))

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "current_frontier": {
            "artifact": display(FRONTIER),
            "correct": frontier.get("correct"),
            "rows": frontier.get("rows"),
            "accuracy": frontier.get("accuracy"),
            "policy": frontier.get("policy"),
        },
        "current_same_frontier_gemma_comparison": {
            "artifact": display(GEMMA),
            "model": gemma.get("model"),
            "hundred_m_accuracy": gemma.get("hundred_m_accuracy"),
            "gemma_accuracy": gemma.get("gemma_accuracy"),
            "delta_hundred_m_minus_gemma": gemma.get("delta_hundred_m_minus_gemma"),
            "per_language": gemma.get("per_language"),
        },
        "scorer_policy_anti_cheat": {
            "artifact": display(ANTI_CHEAT),
            "changed_row_count": anti_cheat.get("changed_row_count"),
            "scope_limited_to_python_verifier_rows": anti_cheat.get("scope_limited_to_python_verifier_rows"),
            "python_verifier_rows_unique_after_drop_extension": anti_cheat.get("python_verifier_rows_unique_after_drop_extension"),
            "collision_rows": anti_cheat.get("collision_rows"),
        },
        "promotability_blockers": [
            "Current 47/47 frontier depends on same-surface diagnostic training support for the recovered citation rows.",
            "The scorer policy win is current and fair on the admitted frontier, but still needs disjoint-root confirmation to support a benchmark-grade claim.",
            "The stale replenishment atlas still marks Python and C/C++ extra bundles as pending, but those bundles are now adjudicated invalid and cannot serve as honest rebuild support.",
            "Current reviewed Rust extra bundles are explicitly invalid for honest scoring or training support.",
            "The available admitted web replenishment stock is a mixed-language code_assist root; it can support training, but it is not a pure second independent web maintainer bundle.",
            "No current artifact proves the full-product harness beats Gemma on the same recovered maintainer frontier.",
        ],
        "refreshed_replenishment_inventory": refreshed_inventory,
        "stale_inventory_findings": {
            "stale_atlas_artifact": display(STALE_ATLAS),
            "stale_pending_candidate_bundle_ids": stale_pending_candidates,
            "refresh_required": len(stale_pending_candidates) > 0,
        },
        "recommended_next_actions": [
            "1. Refresh the replenishment atlas and stop treating the extra Python and C/C++ bundles as pending; they are completed-invalid.",
            "2. Build fresh independent Python and C/C++ maintainer bundles, because the old extra bundles cannot honestly rebuild the recovered win path.",
            "3. Build fresh independent Rust bundles; current reviewed extras are invalid.",
            "4. Keep the admitted mixed-language web replenishment root as auxiliary support, but build a second pure web root before making a broader promotable web claim.",
            "5. Re-run the recovered 100M frontier after any disjoint-root rebuild using the current scorer policy and the same admitted-row comparison script.",
            "6. Only upgrade the claim beyond frontier evidence after the recovered gains survive disjoint-root rebuilds and the same-surface diagnostic support can be retired.",
        ],
        "claim_boundary": [
            "Current evidence supports a strong same-frontier multilingual win over local gemma3:12b.",
            "Current evidence does not yet prove a disjoint-root promotable benchmark win for the full maintainer objective.",
            "Current evidence does not yet prove the full-product harness beats Gemma on the same frontier.",
        ],
    }

    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(
        json.dumps(
            {
                "stage": STAGE,
                "passed": True,
                "artifact": display(AUDIT),
                "recommended_next_actions": audit["recommended_next_actions"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"stage": STAGE, "passed": True, "artifact": display(AUDIT)}, indent=2))


if __name__ == "__main__":
    main()

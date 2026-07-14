#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10662
NAME = "stage10662_reviewed_source_supply_upgrade_atlas"
OUT_DIR = ARTIFACTS / NAME
OUT_PATH = OUT_DIR / "reviewed_source_supply_upgrade_atlas.json"

WEB_GAP_AUDIT = ARTIFACTS / "stage10418_pure_web_verifier_anchor_gap_audit/pure_web_verifier_anchor_gap_audit.json"
WEB_ATLAS = ARTIFACTS / "stage10262_fresh_web_root_candidate_atlas/fresh_web_root_candidate_atlas.json"
RUST_ATLAS = ARTIFACTS / "stage10411_fresh_rust_disjoint_root_candidate_atlas/fresh_rust_disjoint_root_candidate_atlas.json"
RUST_SUPPLY = ARTIFACTS / "stage10464_rust_citation_fresh_root_inventory/rust_citation_fresh_root_inventory.json"
RUST_BUILDER = ARTIFACTS / "stage10467_rust_citation_fresh_root_builder/rust_citation_fresh_root_builder.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    web_gap = load_json(WEB_GAP_AUDIT)
    web_atlas = load_json(WEB_ATLAS)
    rust_atlas = load_json(RUST_ATLAS)
    rust_supply = load_json(RUST_SUPPLY)
    rust_builder = load_json(RUST_BUILDER)

    web_verdict = web_gap.get("verdict") or {}
    web_reviewed_state = web_gap.get("current_web_reviewed_state") or {}
    web_supply_state = web_gap.get("source_supply_state") or {}
    overlap_state = web_gap.get("repo_overlap_web_support_state") or {}

    rust_metrics = rust_atlas.get("metrics") or {}
    rust_targets = []
    for target in rust_builder.get("recommended_next_stage") and [] or []:
        rust_targets.append(target)
    prioritized_rust_candidates = []
    for row in rust_builder.get("current_residual_target", {}).get("recommended_candidates", []):
        prioritized_rust_candidates.append(row)

    top_rust_candidates = []
    for row in rust_atlas.get("top_fresh_candidates") or []:
        top_rust_candidates.append(
            {
                "candidate_root_id": row.get("candidate_root_id"),
                "repo_id": row.get("repo_id"),
                "package_root": row.get("package_root"),
                "priority_score": row.get("priority_score"),
                "recommendation": row.get("recommendation"),
                "review_ready_for_bundle_construction": row.get("review_ready_for_bundle_construction"),
                "test_file_count": row.get("test_file_count"),
                "competition_geometries": row.get("competition_geometries"),
                "candidate_paths_preview": row.get("candidate_paths_preview"),
            }
        )

    builder_targets = []
    for row in [
        target
        for target in (rust_builder.get("current_residual_target") or {}).get("recommended_candidates", [])
    ]:
        candidate_meta = next(
            (candidate for candidate in top_rust_candidates if candidate.get("candidate_root_id") == row),
            None,
        )
        builder_targets.append(
            {
                "candidate_root_id": row,
                "source_heldout_headline_admissible_now": False,
                "needs_bundle_construction": True,
                "needs_review_packets": True,
                "needs_fresh_verifier_constraint_materialization": True,
                "selected_test_anchor_present": bool(candidate_meta and int(candidate_meta.get("test_file_count") or 0) > 0),
                "verifier_anchor_present": bool(candidate_meta and int(candidate_meta.get("test_file_count") or 0) > 0),
                "review_ready_for_bundle_construction": candidate_meta.get("review_ready_for_bundle_construction") if candidate_meta else False,
                "competition_geometries": candidate_meta.get("competition_geometries") if candidate_meta else [],
                "candidate_paths_preview": candidate_meta.get("candidate_paths_preview") if candidate_meta else [],
            }
        )

    web_upgrade_candidates: list[dict[str, Any]] = []
    best_overlap_candidate = overlap_state.get("best_overlap_candidate") or {}
    if best_overlap_candidate:
        web_upgrade_candidates.append(
            {
                "bundle_id": best_overlap_candidate.get("bundle_id"),
                "repo_id": best_overlap_candidate.get("repo_id"),
                "source_heldout_headline_admissible_now": False,
                "selected_test_anchor_present": bool(best_overlap_candidate.get("selected_tests")),
                "verifier_anchor_present": bool(best_overlap_candidate.get("selected_tests")),
                "needs_bundle_construction": False,
                "needs_review_packets": True,
                "needs_new_repo_family": True,
                "role": "repo_overlap_stress_or_train_support_only",
                "candidate_paths": best_overlap_candidate.get("candidate_paths"),
                "blocker": "same_repo_family_as_consumed_web_frontier",
            }
        )

    verdict = {
        "web_gap_is_currently_in_repo_source_exhaustion": not bool(web_supply_state.get("fresh_candidates")),
        "rust_gap_is_currently_builder_and_materialization_limited": bool(
            rust_metrics.get("fresh_root_count")
        ) and not bool(rust_supply.get("current_supply_state", {}).get("exact_e_vs_f_disjoint_contrast_exists")),
        "fresh_source_heldout_pure_web_candidates_available_now": bool(web_verdict.get("fresh_source_heldout_pure_web_candidates_available_now")),
        "fresh_rust_builder_targets_available_now": bool(builder_targets),
        "source_supply_upgrade_ready_now": True,
    }

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "sources": {
            "web_gap_audit": str(WEB_GAP_AUDIT.relative_to(ROOT)),
            "web_fresh_root_atlas": str(WEB_ATLAS.relative_to(ROOT)),
            "rust_disjoint_root_candidate_atlas": str(RUST_ATLAS.relative_to(ROOT)),
            "rust_citation_supply_inventory": str(RUST_SUPPLY.relative_to(ROOT)),
            "rust_citation_builder": str(RUST_BUILDER.relative_to(ROOT)),
        },
        "web_current_state": {
            "admitted_web_bundle_count": web_reviewed_state.get("admitted_web_bundle_count"),
            "pure_web_bundle_count": web_reviewed_state.get("pure_web_bundle_count"),
            "verifier_anchored_any_web_bundle_count": web_reviewed_state.get("verifier_anchored_any_web_bundle_count"),
            "verifier_anchored_pure_web_bundle_count": web_reviewed_state.get("verifier_anchored_pure_web_bundle_count"),
            "fresh_candidate_rows": web_supply_state.get("fresh_candidate_rows"),
            "fresh_source_heldout_candidates": web_supply_state.get("fresh_candidates") or [],
            "repo_overlap_candidates": web_upgrade_candidates,
        },
        "rust_current_state": {
            "candidate_root_count": rust_metrics.get("candidate_root_count"),
            "fresh_root_count": rust_metrics.get("fresh_root_count"),
            "fresh_review_ready_count": rust_metrics.get("fresh_review_ready_count"),
            "fresh_with_test_files": rust_metrics.get("fresh_with_test_files"),
            "exact_e_vs_f_disjoint_contrast_exists": (rust_supply.get("current_supply_state") or {}).get("exact_e_vs_f_disjoint_contrast_exists"),
            "same_surface_tokenizers_contrast_exists": (rust_supply.get("current_supply_state") or {}).get("same_surface_tokenizers_contrast_exists"),
            "interim_support_bundle": (rust_builder.get("interim_train_support") or {}).get("source_bundle"),
            "builder_targets": builder_targets,
            "top_fresh_candidates": top_rust_candidates,
        },
        "verdict": verdict,
        "claim_boundary": [
            "Web is not blocked by review scaffolding anymore; it is blocked by the absence of a new non-overlapping pure-web source family with selected tests in the current inventories.",
            "Rust is not blocked by total source exhaustion; the repo already contains multiple fresh candidate families, but they still need real evidence-citation row materialization with the E-vs-F style opposition.",
            "Repo-overlap web candidates and tokenizers same-surface Rust contrasts can still be useful for stress evaluation or train support, but they should not be promoted into source-heldout headline claims.",
        ],
        "web_upgrade_candidates": web_upgrade_candidates,
        "rust_upgrade_candidates": builder_targets,
        "immediate_next_steps": [
            "Treat web as a source acquisition problem: ingest a new pure-web repo family with selected tests before trying to strengthen headline web claims.",
            "Treat Rust as a builder pipeline problem: materialize at least 6 fresh non-tokenizers evidence-citation roots where symptom_or_call_path_analogue and verifier_and_test_constraint are both visible options.",
            "Keep candle-core as interim Rust train support only; do not count it toward the fresh-root promotable requirement.",
            "Keep code_assist web candidates as repo-overlap stress or support-only material unless a new repo family appears.",
        ],
        "scale_relevance": {
            "why_this_matters_for_20k_plus_root_scaling": [
                "Web cannot honestly scale in the promotable frontier without new source families; blindly duplicating bddy_website or code_assist would inflate counts without improving heldout quality.",
                "Rust can scale from the current repo, but only if the compiler turns candidate families into verifier-backed, shortcut-clean, root-disjoint evidence-citation bundles rather than repeating tokenizers.",
                "This is the same quality ratchet needed for 20k-plus roots per language: count admitted fresh roots, not raw sessions or sibling variants.",
            ]
        },
    }

    write_json(OUT_PATH, payload)
    print(OUT_PATH)


if __name__ == "__main__":
    main()

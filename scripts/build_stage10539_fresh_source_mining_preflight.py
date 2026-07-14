#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

STAGE = 10539
NAME = "stage10539_fresh_source_mining_preflight"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
CARD_JSON = OUT_DIR / "fresh_source_mining_preflight.json"

SESSION_INVENTORY = ROOT / "runs/local/artifacts/stage10100_true_source_backed_multilingual_session_inventory_audit/true_source_backed_multilingual_session_inventory_audit.json"
RUST_DISCOVERY = ROOT / "runs/local/artifacts/stage10125_true_source_backed_rust_root_discovery_manifest/true_source_backed_rust_root_discovery_manifest.json"
WEB_ATLAS = ROOT / "runs/local/artifacts/stage10262_fresh_web_root_candidate_atlas/fresh_web_root_candidate_atlas.json"
REFINERY = ROOT / "runs/local/artifacts/stage10510_long_context_refinery_inventory/long_context_refinery_inventory.json"
RUST_FRESH = ROOT / "runs/local/artifacts/stage10464_rust_citation_fresh_root_inventory/rust_citation_fresh_root_inventory.json"
EXPANSION_REQUEST = ROOT / "runs/local/artifacts/stage10537_multilingual_bootstrap_expansion_request/multilingual_bootstrap_expansion_request.json"
EXPANSION_INVENTORY = ROOT / "runs/local/artifacts/stage10538_compiled_root_expansion_inventory/compiled_root_expansion_inventory.json"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    session_inventory = load_json(SESSION_INVENTORY)
    rust_discovery = load_json(RUST_DISCOVERY)
    web_atlas = load_json(WEB_ATLAS)
    refinery = load_json(REFINERY)
    rust_fresh = load_json(RUST_FRESH)
    expansion_request = load_json(EXPANSION_REQUEST)
    expansion_inventory = load_json(EXPANSION_INVENTORY)

    best_inventory = session_inventory["best_bootstrap_inventory"]
    rust_metrics = rust_discovery["metrics"]
    web_metrics = web_atlas["metrics"]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Fresh-source mining preflight for the next multilingual maintainer-bundle expansion after the compiled-root inventory was exhausted.",
            "Maps each language lane to the best surviving source inventory and the concrete miner/builder entrypoints already in the repo.",
            "This is a source-supply and implementation artifact, not a model-quality result.",
        ],
        "source_artifacts": {
            "session_inventory": str(SESSION_INVENTORY.relative_to(ROOT)),
            "rust_discovery": str(RUST_DISCOVERY.relative_to(ROOT)),
            "web_atlas": str(WEB_ATLAS.relative_to(ROOT)),
            "refinery_inventory": str(REFINERY.relative_to(ROOT)),
            "rust_fresh_inventory": str(RUST_FRESH.relative_to(ROOT)),
            "expansion_request": str(EXPANSION_REQUEST.relative_to(ROOT)),
            "compiled_root_expansion_inventory": str(EXPANSION_INVENTORY.relative_to(ROOT)),
        },
        "preflight_findings": {
            "compiled_root_inventory_exhausted": expansion_inventory["compiled_supply"]["unused_roots"] == 0,
            "python_cpp_web_real_session_inventory_exists": bool(best_inventory.get("supports_builder_minimum_fields")),
            "rust_real_session_inventory_missing": session_inventory["claim_boundary"]["rust_replenishment_required_before_four_language_claim"],
            "web_fresh_candidates_currently_zero": web_metrics["fresh_candidate_rows"] == 0,
            "rust_discovery_candidates_available": rust_metrics["candidate_root_count"],
            "rust_review_ready_candidates": rust_metrics["review_ready_candidates"],
        },
        "language_lane_plan": {
            "python": {
                "status": "can_mine_from_existing_real_session_inventory",
                "best_source_inventory": best_inventory["inventory_path"],
                "available_row_count": best_inventory["language_row_counts"]["python"],
                "notes": [
                    "real-session inventory already has code snippets, changed files, query text, trace-like context, and selected tests",
                    "use for fresh heldout patch/action target materialization after root dedup"
                ],
            },
            "c_cpp": {
                "status": "can_mine_from_existing_real_session_inventory",
                "best_source_inventory": best_inventory["inventory_path"],
                "available_row_count": best_inventory["language_row_counts"]["c_cpp"],
                "notes": [
                    "real-session inventory has limited but nonzero C/C++ supply",
                    "prioritize heldout patch/action targets before more train-only support growth"
                ],
            },
            "rust": {
                "status": "must_convert_true_source_backed_rust_discovery_and_mine_more_non_tokenizers_roots",
                "best_source_inventory": str(RUST_DISCOVERY.relative_to(ROOT)),
                "available_candidate_roots": rust_metrics["candidate_root_count"],
                "review_ready_candidates": rust_metrics["top_review_ready_candidates"],
                "residual_gap": rust_fresh["identified_gap"],
                "notes": [
                    "stage10125 provides real rust source candidates across 6 repos",
                    "stage10464 confirms the exact E-vs-F contrast is still missing on disjoint non-tokenizers roots"
                ],
            },
            "web_js_ts_html": {
                "status": "existing_inventory_exhausted_requires_new_source_session_inventory",
                "best_source_inventory": best_inventory["inventory_path"],
                "available_row_count": best_inventory["language_row_counts"]["web_js_ts_html"],
                "fresh_candidates_now": web_metrics["fresh_candidate_rows"],
                "notes": [
                    "stage10262 found zero fresh web candidates in the current atlas after consumed-example and consumed-repo-family filtering",
                    "do not replay consumed bddy_website or code_assist web examples into the next strict path"
                ],
            },
        },
        "recommended_entrypoints": [
            {
                "script": "scripts/mine_local_root_session_episodes.py",
                "role": "materialize execution-backed local session episodes with selected tests, verification targets, and task summaries from real repos",
            },
            {
                "script": "scripts/build_session_episode_seed_candidates.py",
                "role": "turn normalized metadata/session traces into episode seed candidates with verification targets and route labels",
            },
            {
                "script": "scripts/mine_external_repo_commit_episode_seeds.py",
                "role": "mine fresh external repo commit seeds when local/session supply is exhausted, especially for new web repos and additional Rust repos",
            },
            {
                "script": "scripts/build_stage10125_true_source_backed_rust_root_discovery_manifest.py",
                "role": "use as the current authoritative Rust root discovery source",
            },
            {
                "script": "scripts/build_stage10262_fresh_web_root_candidate_atlas.py",
                "role": "rerun against new web source/session inventories only; current default inventory is exhausted",
            },
        ],
        "next_stage_contract": {
            "recommended_stage_name": "stage10540_fresh_source_multilingual_root_mining_request",
            "minimum_outputs": [
                "at least 8 fresh rust structured roots from non-tokenizers families with maintainer-visible evidence",
                "at least 4 fresh web roots from at least 2 new repo families",
                "at least 2 heldout patch_sketch or next_action roots per language",
                "root/repo/time lineage fields sufficient for leak and split audits",
            ],
            "gates": [
                "no reuse of consumed web examples or consumed web repo families from stage10262",
                "rust tokenizers same-surface rows remain diagnostic-only",
                "selected tests or equivalent verifier anchors present where patch/action targets are claimed",
                "fresh roots are materialized before any new training request",
            ],
        },
        "program_context": {
            "refinery_recommendation": refinery["recommended_pipeline"],
            "expansion_priorities": expansion_request["expansion_priorities"],
        },
        "next_best_step": (
            "Launch fresh-source multilingual root mining: mine new web/session sources, convert the Rust discovery manifest into maintainer bundles, "
            "and materialize fresh patch/action heldout roots before the next post-stage10531 training package."
        ),
    }

    write_json(CARD_JSON, payload)
    write_json(SUMMARY, payload)


if __name__ == "__main__":
    main()

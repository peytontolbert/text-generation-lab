#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

STAGE = 10540
NAME = "stage10540_fresh_source_multilingual_root_mining_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
REQUEST_JSON = OUT_DIR / "fresh_source_multilingual_root_mining_request.json"

PREFLIGHT = ROOT / "runs/local/artifacts/stage10539_fresh_source_mining_preflight/fresh_source_mining_preflight.json"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    preflight = load_json(PREFLIGHT)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Concrete fresh-source multilingual root mining request after stage10539 preflight confirmed compiled-root exhaustion.",
            "Specifies the exact language lanes, source inventories, entrypoint scripts, and gating rules for the next maintainer-bundle expansion.",
            "This is a source-materialization request artifact, not a model-quality result.",
        ],
        "source_preflight": str(PREFLIGHT.relative_to(ROOT)),
        "objective_alignment": {
            "why_now": [
                "stage10538 proved the current compiled root inventory is exhausted",
                "stage10539 identified Python/C++ reusable session supply, Rust true-source discovery supply, and web inventory exhaustion",
                "the next multilingual maintainer improvement requires fresh roots before any further honest training/package expansion",
            ],
            "post_stage10531_role": "Use mined fresh roots to build the next multilingual heldout/support manifest after the current bootstrap-heldout comparison lands.",
        },
        "lane_requests": [
            {
                "language_family": "python",
                "status": "mine_from_existing_real_session_inventory",
                "source_inventory": preflight["language_lane_plan"]["python"]["best_source_inventory"],
                "preferred_entrypoints": [
                    "scripts/mine_local_root_session_episodes.py",
                    "scripts/build_session_episode_seed_candidates.py",
                ],
                "minimum_outputs": {
                    "fresh_roots": 4,
                    "heldout_patch_or_action_roots": 2,
                    "selected_test_or_verifier_anchor_required": True,
                },
                "focus": [
                    "patch_sketch",
                    "next_action",
                    "selected_test",
                    "visible_evidence_key",
                ],
            },
            {
                "language_family": "c_cpp",
                "status": "mine_from_existing_real_session_inventory",
                "source_inventory": preflight["language_lane_plan"]["c_cpp"]["best_source_inventory"],
                "preferred_entrypoints": [
                    "scripts/mine_local_root_session_episodes.py",
                    "scripts/build_session_episode_seed_candidates.py",
                ],
                "minimum_outputs": {
                    "fresh_roots": 4,
                    "heldout_patch_or_action_roots": 2,
                    "selected_test_or_verifier_anchor_required": True,
                },
                "focus": [
                    "patch_sketch",
                    "next_action",
                    "selected_test",
                    "visible_evidence_key",
                ],
            },
            {
                "language_family": "rust",
                "status": "convert_rust_discovery_manifest_and_mine_more_non_tokenizers_roots",
                "source_inventory": preflight["language_lane_plan"]["rust"]["best_source_inventory"],
                "preferred_entrypoints": [
                    "scripts/build_stage10125_true_source_backed_rust_root_discovery_manifest.py",
                    "scripts/mine_external_repo_commit_episode_seeds.py",
                ],
                "minimum_outputs": {
                    "fresh_roots": 8,
                    "new_repo_families": 3,
                    "non_tokenizers_roots_required": 4,
                    "heldout_patch_or_action_roots": 2,
                },
                "focus": [
                    "next_action",
                    "patch_sketch",
                    "repair_intent",
                    "selected_test",
                    "visible_evidence_key",
                ],
                "diagnostic_only_exclusions": [
                    "same-surface tokenizers E-vs-F rows stay diagnostic-only",
                ],
            },
            {
                "language_family": "web_js_ts_html",
                "status": "requires_new_source_session_inventory",
                "source_inventory": preflight["language_lane_plan"]["web_js_ts_html"]["best_source_inventory"],
                "preferred_entrypoints": [
                    "scripts/mine_external_repo_commit_episode_seeds.py",
                    "scripts/build_stage10262_fresh_web_root_candidate_atlas.py",
                ],
                "minimum_outputs": {
                    "fresh_roots": 4,
                    "new_repo_families": 2,
                    "heldout_decisive_or_action_roots": 2,
                },
                "focus": [
                    "decisive_evidence",
                    "retrieve_answer_abstain",
                    "next_action",
                    "patch_sketch",
                ],
                "hard_exclusions": [
                    "do not reuse consumed bddy_website examples",
                    "do not reuse consumed code_assist web examples in strict path",
                ],
            },
        ],
        "global_gates": preflight["next_stage_contract"]["gates"],
        "global_minimum_outputs": preflight["next_stage_contract"]["minimum_outputs"],
        "repair_intent_followup": {
            "target_rows_over_cap": 17,
            "action": "rewrite_or_summarize_long_repair_intents to <=1024 tokens before next seq2seq package promotion",
        },
        "recommended_execution_order": [
            "mine or convert fresh Rust roots first, because Rust is the thinnest lane and blocks four-language strength",
            "mine new web roots from fresh source/session inventory, because current atlas is exhausted",
            "materialize heldout patch_sketch and next_action roots for Python and C/C++ from the surviving real-session inventory",
            "rerun leak/root/repo/time audits before any next training request",
        ],
        "next_best_step": (
            "Use the named miners/builders to materialize fresh multilingual roots, then compile a post-stage10531 expansion manifest "
            "with real Rust/Web growth and heldout patch/action targets."
        ),
    }

    write_json(REQUEST_JSON, payload)
    write_json(SUMMARY, payload)


if __name__ == "__main__":
    main()

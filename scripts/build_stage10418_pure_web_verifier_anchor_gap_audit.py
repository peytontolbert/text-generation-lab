#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10418
NAME = "stage10418_pure_web_verifier_anchor_gap_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_PATH = OUT_DIR / "pure_web_verifier_anchor_gap_audit.json"

ATLAS_10417 = ROOT / "runs/local/artifacts/stage10417_multilingual_reviewed_scaling_atlas/multilingual_reviewed_scaling_atlas.json"
ATLAS_10262 = ROOT / "runs/local/artifacts/stage10262_fresh_web_root_candidate_atlas/fresh_web_root_candidate_atlas.json"
AUDIT_10175 = ROOT / "runs/local/artifacts/stage10175_web_root_supply_and_bundle_gap_audit/web_root_supply_and_bundle_gap_audit.json"
STAGE10176 = ROOT / "runs/local/artifacts/stage10176_code_assist_web_replenishment_bundle/code_assist_web_replenishment_bundle.json"
STAGE10263 = ROOT / "runs/local/artifacts/stage10263_code_assist_web_git_history_candidate_manifest/code_assist_web_git_history_candidate_manifest.json"
STAGE10264 = ROOT / "runs/local/artifacts/stage10264_code_assist_web_commit_bundle_candidates/code_assist_web_commit_bundle_candidates.json"
STAGE10273 = ROOT / "runs/local/artifacts/stage10273_code_assist_web_support_probe_audit/code_assist_web_support_probe_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    atlas_10417 = load_json(ATLAS_10417)
    atlas_10262 = load_json(ATLAS_10262)
    audit_10175 = load_json(AUDIT_10175)
    stage10176 = load_json(STAGE10176)
    stage10263 = load_json(STAGE10263)
    stage10264 = load_json(STAGE10264)
    stage10273 = load_json(STAGE10273)

    admitted_web_rows = [
        row for row in (atlas_10417.get("admitted_bundle_rows") or [])
        if row.get("language_family") == "web_js_ts_html"
    ]
    pure_web_rows = [row for row in admitted_web_rows if row.get("repo_id") == "bddy_website"]
    verifier_anchored_pure_web_rows = [row for row in pure_web_rows if int(row.get("selected_tests_count", 0) or 0) > 0]
    verifier_anchored_web_rows = [row for row in admitted_web_rows if int(row.get("selected_tests_count", 0) or 0) > 0]

    overlap_commit_candidates = stage10263.get("candidate_commits") or []
    commit_bundle_candidates = stage10264.get("bundle_candidates") or []

    best_overlap_candidate = None
    if commit_bundle_candidates:
        best_overlap_candidate = {
            "bundle_id": commit_bundle_candidates[0].get("bundle_id"),
            "commit": commit_bundle_candidates[0].get("commit"),
            "repo_id": commit_bundle_candidates[0].get("repo_id"),
            "candidate_paths": commit_bundle_candidates[0].get("candidate_paths"),
            "selected_tests": commit_bundle_candidates[0].get("perspective_rows", [{}])[0].get("prompt_contract", {}).get("selected_tests", []),
            "claim_boundary": commit_bundle_candidates[0].get("claim_boundary"),
        }

    verdict = {
        "has_pure_web_admitted_bundle": bool(pure_web_rows),
        "has_pure_web_verifier_anchored_bundle": bool(verifier_anchored_pure_web_rows),
        "has_any_verifier_anchored_web_bundle": bool(verifier_anchored_web_rows),
        "fresh_source_heldout_pure_web_candidates_available_now": bool(atlas_10262.get("fresh_candidates")),
        "web_source_heldout_headline_ready": bool(verifier_anchored_pure_web_rows),
    }

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "current_web_reviewed_state": {
            "admitted_web_bundle_count": len(admitted_web_rows),
            "pure_web_bundle_count": len(pure_web_rows),
            "verifier_anchored_pure_web_bundle_count": len(verifier_anchored_pure_web_rows),
            "verifier_anchored_any_web_bundle_count": len(verifier_anchored_web_rows),
            "admitted_web_rows": admitted_web_rows,
        },
        "source_supply_state": {
            "fresh_candidate_rows": int((atlas_10262.get("metrics") or {}).get("fresh_candidate_rows", 0) or 0),
            "fresh_candidates": atlas_10262.get("fresh_candidates") or [],
            "rejection_reason_counts": (atlas_10262.get("metrics") or {}).get("rejection_reason_counts", {}),
            "inventory_decision": atlas_10262.get("decision"),
            "web_gap_decision": audit_10175.get("decision"),
        },
        "repo_overlap_web_support_state": {
            "admitted_stage10176_bundle_id": stage10176.get("bundle_id"),
            "admitted_stage10176_selected_tests": (
                stage10176.get("perspective_rows", [{}])[0].get("prompt_contract", {}).get("selected_tests", [])
                if stage10176.get("perspective_rows") else []
            ),
            "same_repo_commit_candidate_count": len(overlap_commit_candidates),
            "best_overlap_candidate": best_overlap_candidate,
            "negative_training_result": {
                "stage": stage10273.get("stage"),
                "headline": stage10273.get("headline"),
                "strict_eval_delta": (stage10273.get("strict_eval") or {}).get("delta"),
                "web_language_delta": ((stage10273.get("language_delta") or {}).get("web_js_ts_html") or {}).get("delta"),
                "python_language_delta": ((stage10273.get("language_delta") or {}).get("python") or {}).get("delta"),
            },
        },
        "verdict": verdict,
        "claim_boundary": [
            "The current inventory supports one verifier-anchored web bundle, but it is from the same code_assist repo family as previously consumed web support and should not be promoted as source-heldout pure-web headline evidence.",
            "The admitted pure-web bddy_website bundles remain useful maintainer packets, but neither has selected-test anchors, so they are weaker for verifier-grade claims.",
            "The current source-backed inventory contains zero fresh pure-web candidates beyond the consumed families, so the honest web scaling frontier is a supply problem, not just a training problem."
        ],
        "next_dataset_scaling_priorities": [
            "Treat stage10176 and the stage10263/stage10264 code_assist commit candidates as repo-overlap stress-eval or train-support material only, never as source-heldout headline web evidence.",
            "Do not rerun the stage10272-style support blend unchanged; stage10273 proved it causes large Python and web regressions.",
            "Acquire a new non-overlapping pure-web repo family with selected tests if the v2.7 claim must include strong verifier-anchored web evidence.",
            "Until then, keep web claims scoped to one anchored mixed-language web bundle plus two weaker pure-web maintainer bundles with no selected tests."
        ],
        "next_best_step": (
            "Build or ingest a new non-overlapping pure-web source family with selected tests; absent that, limit web scaling to repo-overlap stress evaluation and keep the headline claim conservative."
        ),
    }
    write_json(SUMMARY_PATH, summary)


if __name__ == "__main__":
    main()

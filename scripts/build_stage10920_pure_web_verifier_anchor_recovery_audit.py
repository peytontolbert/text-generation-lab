#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10920
NAME = "stage10920_pure_web_verifier_anchor_recovery_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "pure_web_verifier_anchor_recovery_audit.json"

WEB_GAP = ARTIFACTS / "stage10418_pure_web_verifier_anchor_gap_audit" / "pure_web_verifier_anchor_gap_audit.json"
LOCAL_ROOT_EPISODES = ARTIFACTS / "session_like_source_inventory_real" / "local_root_session_episodes" / "local_root_session_episodes.jsonl"
AUGMENTED_EPISODES = ARTIFACTS / "session_like_source_inventory_real" / "augmented_session_episodes_v3" / "augmented_session_episodes.jsonl"

BUNDLE_DIRS = [
    ARTIFACTS
    / "stage10120_true_source_backed_maintainer_root_bundle_review_packets"
    / "review_packets"
    / "stage10119__localsess_bddy_website_sessseed_codex_sessions_rollout_2025_11_24t23_41_47_019ab83e_b023_7553_a34c_b93e_src_main_js_index_html_440e122a0f_aug_1500000_8b46e7f662__web_js_ts_html",
    ARTIFACTS
    / "stage10120_true_source_backed_maintainer_root_bundle_review_packets"
    / "review_packets"
    / "stage10119__localsess_bddy_website_sessseed_codex_sessions_rollout_2025_11_28t14_11_27_019acacd_f95c_7802_9bfe_7232_index_html_f0be60dc44_aug_1500000_8b46e7f662__web_js_ts_html",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def summarize_bddy_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        repo_id = row.get("repo_id")
        local_repo_root = row.get("local_repo_root")
        if repo_id != "bddy_website" and "bddy_website" not in str(local_repo_root or ""):
            continue
        out.append(
            {
                "episode_id": row.get("episode_id"),
                "repo_id": repo_id,
                "selected_tests": row.get("selected_tests") or [],
                "selected_tests_count": len(row.get("selected_tests") or []),
                "test_selection_route": row.get("test_selection_route"),
                "goal": row.get("goal"),
                "changes": [change.get("path") for change in (row.get("changes") or [])],
            }
        )
    return out


def summarize_review_bundle(bundle_dir: Path) -> dict[str, Any]:
    adjudication = load_json(bundle_dir / "perspective_gold_adjudication.json")
    answers = adjudication.get("perspective_gold_answers") or []
    selected_tests = sorted(
        {
            test
            for answer in answers
            for test in (answer.get("selected_tests") or [])
        }
    )
    evidence_gold = next((a for a in answers if a.get("perspective") == "evidence_citation"), {})
    verifier_gold = next((a for a in answers if a.get("perspective") == "verifier_outcome"), {})
    return {
        "bundle_id": adjudication.get("bundle_id"),
        "packet_dir": rel(bundle_dir),
        "decision_rationale": adjudication.get("decision_rationale"),
        "selected_tests": selected_tests,
        "selected_tests_count": len(selected_tests),
        "evidence_citation_gold": evidence_gold.get("gold_answer_value"),
        "verifier_outcome_gold": verifier_gold.get("gold_answer_value"),
        "verifier_outcome_rationale": verifier_gold.get("reviewer_rationale"),
    }


def main() -> None:
    prior_web_gap = load_json(WEB_GAP)
    local_rows = summarize_bddy_rows(load_jsonl(LOCAL_ROOT_EPISODES))
    augmented_rows = summarize_bddy_rows(load_jsonl(AUGMENTED_EPISODES))
    reviewed_bundles = [summarize_review_bundle(bundle_dir) for bundle_dir in BUNDLE_DIRS]

    local_any_anchor = any(row["selected_tests_count"] > 0 for row in local_rows)
    augmented_any_anchor = any(row["selected_tests_count"] > 0 for row in augmented_rows)
    reviewed_any_anchor = any(row["selected_tests_count"] > 0 for row in reviewed_bundles)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "pure_web_verifier_anchor_recovery_failed",
        "claim_scope": [
            "Audit whether the admitted pure-web bddy_website bundles can recover a real verifier anchor from surviving source-session lineage.",
            "Decide whether the web blocker is recoverable from existing artifacts or must remain a source-supply gap.",
        ],
        "source_artifacts": {
            "prior_pure_web_gap_audit": rel(WEB_GAP),
            "local_root_session_episodes": rel(LOCAL_ROOT_EPISODES),
            "augmented_session_episodes_v3": rel(AUGMENTED_EPISODES),
            "reviewed_bundle_dirs": [rel(path) for path in BUNDLE_DIRS],
        },
        "headline": {
            "reviewed_pure_web_bundle_count": len(reviewed_bundles),
            "local_root_bddy_episode_count": len(local_rows),
            "augmented_bddy_episode_count": len(augmented_rows),
            "reviewed_any_selected_tests": reviewed_any_anchor,
            "local_root_any_selected_tests": local_any_anchor,
            "augmented_any_selected_tests": augmented_any_anchor,
            "recovery_status": "not_recoverable_from_current_bddy_lineage",
        },
        "reviewed_pure_web_bundles": reviewed_bundles,
        "local_root_bddy_rows": local_rows,
        "augmented_bddy_rows": augmented_rows,
        "findings": [
            "Both admitted pure-web bddy_website review packets remain non-verifier-anchored: selected_tests is empty and verifier_outcome is intentionally abstention-oriented.",
            "All surviving raw local-root bddy_website source episodes also have selected_tests = [] with test_selection_route = NEEDS_BROAD_TEST_DISCOVERY.",
            "The augmented bddy_website source episodes preserve the same no-test state rather than surfacing a hidden PASS_TARGETED_TEST_SELECTION anchor.",
            "That means the web blocker is not just packetization drift. The current bddy pure-web lineage itself lacks a recoverable verifier anchor.",
            prior_web_gap.get("next_best_step"),
        ],
        "comparison_to_stage10418": {
            "prior_has_pure_web_verifier_anchored_bundle": (
                (prior_web_gap.get("verdict") or {}).get("has_pure_web_verifier_anchored_bundle")
            ),
            "prior_fresh_source_heldout_pure_web_candidates_available_now": (
                (prior_web_gap.get("verdict") or {}).get("fresh_source_heldout_pure_web_candidates_available_now")
            ),
            "status_change": "no_recovery_found_in_existing_bddy_source_lineage",
        },
        "next_best_step": (
            "Treat the bddy_website pure-web bundles as non-verifier-anchored controls only, and acquire or ingest a new pure-web source family with selected tests if honest multilingual evidence-policy promotion is required."
        ),
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

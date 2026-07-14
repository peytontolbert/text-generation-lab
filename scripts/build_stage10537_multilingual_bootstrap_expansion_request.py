#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

STAGE = 10537
NAME = "stage10537_multilingual_bootstrap_expansion_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
REQUEST_JSON = OUT_DIR / "multilingual_bootstrap_expansion_request.json"

SOURCE_AUDIT = ROOT / "runs/local/artifacts/stage10536_split_corrected_bootstrap_package_balance_audit/split_corrected_bootstrap_package_balance_audit.json"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    audit = load_json(SOURCE_AUDIT)
    train = audit["train"]
    strict = audit["cleaned_strict_successor"]
    gaps = audit["gaps"]

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Concrete next-manifest expansion request derived from the split-corrected root-based bootstrap package audit.",
            "Prioritizes multilingual supply that moves the bootstrap seq2seq path toward a credible 100M-vs-Gemma maintainer comparison.",
            "This is a planning/package artifact, not a model-quality result.",
        ],
        "source_artifact": str(SOURCE_AUDIT.relative_to(ROOT)),
        "current_bootstrap_state": {
            "train_rows": train["rows"],
            "strict_rows": strict["rows"],
            "train_language_counts": train["language_counts"],
            "strict_language_counts": strict["language_counts"],
            "strict_target_subtype_counts": strict["target_subtype_counts"],
            "strict_single_repo_languages": gaps["cleaned_strict_single_repo_languages"],
            "train_decoder_cap_rows_over_1024": {
                key: value["rows_over_cap"] for key, value in train["decoder_cap_1024"].items() if value["rows_over_cap"] > 0
            },
        },
        "blocking_gaps": [
            "Strict heldout only covers decisive_evidence and retrieve_answer_abstain.",
            "Web strict coverage is single-repo.",
            "Rust train support is tiny and missing most structured target families.",
            "Repair-intent train supply still contains long targets beyond the current 1024-token decoder cap.",
        ],
        "expansion_priorities": [
            {
                "priority": 1,
                "name": "rust_structured_support_replenishment",
                "why": "Rust train has only 20 rows total and is missing next_action, patch_sketch, repair_intent, selected_test, and visible_evidence_key support.",
                "minimum_request": {
                    "new_roots": 8,
                    "repo_diversity": 3,
                    "target_subtypes": [
                        "next_action",
                        "patch_sketch",
                        "repair_intent",
                        "selected_test",
                        "visible_evidence_key",
                    ],
                },
            },
            {
                "priority": 2,
                "name": "web_repo_diverse_strict_heldout",
                "why": "Web strict is currently four roots from one repo, which is too weak for a multilingual maintainer claim.",
                "minimum_request": {
                    "new_strict_roots": 4,
                    "new_repos": 2,
                    "target_subtypes": [
                        "decisive_evidence",
                        "retrieve_answer_abstain",
                    ],
                },
            },
            {
                "priority": 3,
                "name": "heldout_patch_and_action_targets",
                "why": "The current strict slice cannot say anything about patch_sketch, next_action, or verifier-like behavior.",
                "minimum_request": {
                    "new_strict_roots_per_language": 2,
                    "languages": [
                        "python",
                        "c_cpp",
                        "rust",
                        "web_js_ts_html",
                    ],
                    "target_subtypes": [
                        "patch_sketch",
                        "next_action",
                    ],
                },
            },
            {
                "priority": 4,
                "name": "python_c_cpp_selected_test_and_evidence_keys",
                "why": "Python and C/C++ train support are missing selected_test and visible_evidence_key projections needed for richer verifier-conditioned supervision.",
                "minimum_request": {
                    "new_roots_per_language": 4,
                    "target_subtypes": [
                        "selected_test",
                        "visible_evidence_key",
                    ],
                },
            },
            {
                "priority": 5,
                "name": "repair_intent_cap_safe_rewrite",
                "why": "17 repair_intent train rows remain over the current 1024-token cap, weakening the seq2seq curriculum even though heldout is reachable.",
                "minimum_request": {
                    "action": "rewrite_or_summarize_long_repair_intents",
                    "target_rows": 17,
                    "new_cap_goal": 1024,
                },
            },
        ],
        "promotion_gates_for_next_manifest": [
            "Zero strict prompt-target leaks.",
            "Zero root split violations.",
            "At least two repos for web strict coverage.",
            "Nontrivial Rust structured support beyond decisive_evidence/retrieve_answer_abstain.",
            "At least one heldout target family beyond decisive_evidence and retrieve_answer_abstain.",
            "No train repair_intent targets above the declared decoder cap, or else an explicitly higher runtime cap.",
        ],
        "recommended_next_stage_name": "stage10538_multilingual_bootstrap_manifest_expansion_v1",
        "next_best_step": (
            "Build the next root-based bootstrap manifest with Rust structured support, repo-diverse web heldout, and heldout patch/action targets "
            "before treating the seq2seq path as a serious multilingual maintainer comparison beyond the current 36-row bootstrap slice."
        ),
    }

    write_json(REQUEST_JSON, request)
    write_json(SUMMARY, request)


if __name__ == "__main__":
    main()

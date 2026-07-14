#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10416
NAME = "stage10416_ai_adjudicate_rust_flash_attn_bundle"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_PATH = OUT_DIR / "rust_flash_attn_ai_adjudication_summary.json"

PACKET_DIR = (
    ROOT
    / "runs/local/artifacts/stage10415_rust_flash_attn_review_packets/review_packets"
    / "stage10413__candle__candle-flash-attn__rust"
)
RUBRIC_PATH = PACKET_DIR / "expert_maintainer_rubric_review.json"
ANTI_CHEAT_PATH = PACKET_DIR / "anti_cheat_review_card.json"
GOLD_PATH = PACKET_DIR / "perspective_gold_adjudication.json"
PREVIEW_PATH = ROOT / "runs/local/artifacts/stage10413_fresh_rust_flash_attn_preview/fresh_rust_flash_attn_preview_bundle.json"

REVIEWER_ID = "codex-gpt5-ai-review"
REVIEWER_NOTES = (
    "AI maintainer adjudication performed in-repo on the bounded packet evidence, "
    "using abstention wherever the visible flash-attn evidence did not honestly "
    "justify a singleton repair target."
)
DECISION_RATIONALE = (
    "Admit, but as an abstention-heavy packet. The bundle is real and source-backed, "
    "with a concrete selected test plus implementation, FFI, and build competition. "
    "However, the visible evidence does not uniquely separate src/lib.rs from src/ffi.rs "
    "for localization-grade judgments, so singleton repair perspectives should abstain "
    "instead of forcing a guess."
)
ANTI_CHEAT_RATIONALE = (
    "Admit with caution. The main residual risk is a small candidate set that includes "
    "a prominent build.rs path, but the packet still requires distinguishing build/test "
    "constraints from runtime implementation evidence, and the abstention policy prevents "
    "dishonest forced singleton scoring."
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fill_gold_answers(payload: dict[str, Any]) -> dict[str, Any]:
    answers = payload["perspective_gold_answers"]
    by_perspective = {row["perspective"]: row for row in answers}

    def update(
        perspective: str,
        *,
        kind: str,
        value: str,
        rationale: str,
    ) -> None:
        row = by_perspective[perspective]
        row["gold_answer_kind"] = kind
        row["gold_answer_value"] = value
        row["reviewer_rationale"] = rationale

    update(
        "symptom_localization",
        kind="abstain",
        value="ABSTAIN_INSUFFICIENT_EVIDENCE",
        rationale=(
            "The visible packet exposes plausible runtime owners in both src/lib.rs and "
            "src/ffi.rs, while build.rs also appears in the verifier/build constraints. "
            "That is enough for maintainer reasoning, but not enough for an honest singleton edit target."
        ),
    )
    update(
        "evidence_citation",
        kind="visible_evidence_key",
        value="symptom_or_call_path_analogue",
        rationale=(
            "The strongest visible support is the symptom/call-path evidence tying the package behavior "
            "to the runtime FFI boundary and selected test path, which is exactly why the bounded packet "
            "supports a real ambiguity rather than a unique editable file."
        ),
    )
    update(
        "alternative_hypothesis_elimination",
        kind="freeform_explanation",
        value=(
            "A pure build.rs fix is less justified than the runtime code surfaces because the visible "
            "test and call-path evidence centers flash-attention execution behavior, not only kernel compilation. "
            "Even after eliminating build.rs as the primary hypothesis, the packet still does not uniquely choose "
            "between src/lib.rs and src/ffi.rs."
        ),
        rationale=(
            "This row can test maintainer-style elimination without pretending that the remaining runtime candidates "
            "collapse to one uniquely justified file."
        ),
    )
    update(
        "patch_impact",
        kind="abstain",
        value="ABSTAIN_INSUFFICIENT_EVIDENCE",
        rationale=(
            "The bundle does not expose enough failure-specific behavior to justify which candidate patch would "
            "change the selected test outcome with least risk."
        ),
    )
    update(
        "verifier_outcome",
        kind="selected_test",
        value="candle-flash-attn/tests/flash_attn_tests.rs",
        rationale=(
            "That is the only explicit selected verifier target attached to the bundle and it is directly visible "
            "in the verifier-and-test evidence."
        ),
    )
    update(
        "minimal_fix_selection",
        kind="abstain",
        value="ABSTAIN_INSUFFICIENT_EVIDENCE",
        rationale=(
            "The visible evidence does not honestly support a smallest safe file-level fix among build.rs, src/lib.rs, "
            "and src/ffi.rs."
        ),
    )
    update(
        "regression_risk",
        kind="freeform_risk",
        value=(
            "A flash-attention fix could regress CUDA kernel launch behavior, FFI boundary assumptions, or numerical "
            "agreement between the selected flash_attn_tests.rs checks and the runtime implementation."
        ),
        rationale=(
            "The packet exposes real implementation, FFI, and test surfaces, which is enough to support a concrete "
            "maintainer-style regression warning."
        ),
    )
    update(
        "abstention_insufficient_evidence",
        kind="abstain",
        value="ABSTAIN_INSUFFICIENT_EVIDENCE",
        rationale="This is the explicit honesty row and the packet genuinely supports abstention.",
    )

    payload["bundle_gold_ready_for_eval"] = True
    payload["decision_rationale"] = DECISION_RATIONALE
    payload["reviewer_id"] = REVIEWER_ID
    payload["status"] = "completed"
    payload["passed"] = True
    return payload


def main() -> None:
    preview = load_json(PREVIEW_PATH)
    rubric = load_json(RUBRIC_PATH)
    anti_cheat = load_json(ANTI_CHEAT_PATH)
    gold = fill_gold_answers(load_json(GOLD_PATH))

    rubric.update(
        {
            "status": "completed",
            "passed": True,
            "bundle_valid_for_eval": True,
            "reviewer_id": REVIEWER_ID,
            "reviewer_notes": REVIEWER_NOTES,
            "decision_rationale": DECISION_RATIONALE,
            "gold_adjudication_slot": {
                "bundle_level_signoff": True,
                "perspective_gold_answers_recorded": True,
                "reviewer_rationale": DECISION_RATIONALE,
            },
            "rubric_lines": {
                "abstention_is_available_when_evidence_is_insufficient": True,
                "candidate_paths_are_maintainer_plausible": True,
                "perspectives_test_distinct_reasoning_not_template_rephrases": True,
                "root_bundle_is_maintainer_meaningful": True,
                "visible_evidence_is_sufficient_for_bundle_perspectives": True,
            },
        }
    )

    anti_cheat.update(
        {
            "status": "completed",
            "passed": True,
            "admissible_for_same_surface_comparison": True,
            "reviewer_id": REVIEWER_ID,
            "reviewer_notes": REVIEWER_NOTES,
            "decision_rationale": ANTI_CHEAT_RATIONALE,
            "challenge_families": {
                "candidate_path_or_order_bias": True,
                "cross_repo_analogue_leakage": True,
                "hidden_reference_or_metadata_leakage": True,
                "perspective_paraphrase_collapse": True,
                "same_surface_fairness_for_future_gemma_comparison": True,
                "template_and_surface_prior_shortcuts": True,
            },
        }
    )

    write_json(RUBRIC_PATH, rubric)
    write_json(ANTI_CHEAT_PATH, anti_cheat)
    write_json(GOLD_PATH, gold)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "bundle_id": preview["bundle_id"],
        "repo_id": preview["repo_id"],
        "language_family": preview["language_family"],
        "claim_boundary": [
            "Flash-attn is admitted as a real source-backed maintainer bundle, but only with abstention-heavy scoring.",
            "The visible packet is strong enough for honest evaluation because it contains a real selected test and nontrivial implementation/build competition.",
            "The packet still should not be treated as a unique-file localization benchmark because src/lib.rs and src/ffi.rs remain jointly plausible from visible evidence.",
        ],
        "bundle_valid_for_eval": rubric["bundle_valid_for_eval"],
        "admissible_for_same_surface_comparison": anti_cheat["admissible_for_same_surface_comparison"],
        "bundle_gold_ready_for_eval": gold["bundle_gold_ready_for_eval"],
        "abstention_gold_count": sum(
            1 for row in gold["perspective_gold_answers"] if row["gold_answer_kind"] == "abstain"
        ),
        "non_abstention_gold_count": sum(
            1 for row in gold["perspective_gold_answers"] if row["gold_answer_kind"] != "abstain"
        ),
        "selected_tests": preview["selected_tests"],
        "candidate_paths": preview["candidate_paths"],
        "next_best_step": (
            "Use flash-attn as a reviewed fresh Rust successor bundle in the multilingual scaling path, "
            "then prioritize additional disjoint Rust roots with equally concrete selected-test evidence."
        ),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY_PATH, summary)


if __name__ == "__main__":
    main()

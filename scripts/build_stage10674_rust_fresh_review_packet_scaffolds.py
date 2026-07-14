#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10674
NAME = "stage10674_rust_fresh_review_packet_scaffolds"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "rust_fresh_review_packet_scaffolds.json"
PACKETS_DIR = OUT_DIR / "review_packets"

BUILDER_PACKET = ARTIFACTS / "stage10673_multilingual_residual_builder_packet/multilingual_residual_builder_packet.json"
BUILDER_TARGETS = ARTIFACTS / "stage10673_multilingual_residual_builder_packet/multilingual_residual_builder_targets.jsonl"
FLASH_PREVIEW = ARTIFACTS / "stage10413_fresh_rust_flash_attn_preview/fresh_rust_flash_attn_preview_bundle.json"
FLASH_ANTI_CHEAT = ARTIFACTS / "stage10415_rust_flash_attn_review_packets/review_packets/stage10413__candle__candle-flash-attn__rust/anti_cheat_review_card.json"

PERSPECTIVES = [
    "symptom_localization",
    "evidence_citation",
    "alternative_hypothesis_elimination",
    "patch_impact",
    "verifier_outcome",
    "minimal_fix_selection",
    "regression_risk",
    "abstention_insufficient_evidence",
]

VISIBLE_EVIDENCE_KEYS = [
    "algorithmic_background_reference",
    "candidate_change_surface",
    "nearby_definition_or_usage_context",
    "symptom_or_call_path_analogue",
    "verifier_and_test_constraint",
]

PERSPECTIVE_TASKS = {
    "symptom_localization": "Choose the most likely rust edit target from the visible code and verifier evidence.",
    "evidence_citation": "Name the visible rust fact that best supports the chosen edit target.",
    "alternative_hypothesis_elimination": "Explain why a plausible alternative rust target is less justified.",
    "patch_impact": "Compare candidate rust edits by likely behavior change and risk.",
    "verifier_outcome": "Choose the selected test or verifier consequence that best matches the visible rust evidence.",
    "minimal_fix_selection": "Choose the smallest justified rust edit target or abstain if the evidence is insufficient.",
    "regression_risk": "Identify the most plausible regression risk implied by the visible rust evidence.",
    "abstention_insufficient_evidence": "Decide whether the visible rust evidence is sufficient for a confident maintenance choice.",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def bundle_slug(bundle_id: str) -> str:
    return bundle_id.replace("::", "__")


def make_preview_bundle(target: dict[str, Any], flash_preview: dict[str, Any]) -> dict[str, Any]:
    bundle_id = target["bundle_id"]
    seed_paths = target.get("candidate_paths_preview") or []
    return {
        "bundle_id": f"stage10674::{bundle_id}",
        "root_example_id": bundle_id,
        "repo_id": bundle_id.split("::", 1)[0] if "::" in bundle_id else bundle_id.split(":", 1)[0],
        "language_family": "rust",
        "source_route": "external_repo_graph_spans_scaffold",
        "seed_paths": seed_paths,
        "selected_tests": [],
        "claim_boundary": {
            "gold_answers_fully_adjudicated": False,
            "supports_training_or_scoring_now": False,
            "preview_only": True,
            "scaffold_only_until_verifier_anchor_materialized": True,
        },
        "maintainer_visible_evidence": {
            "candidate_change_surface": [
                {
                    "path": path,
                    "source_type": "external_repo_graph_span_placeholder",
                    "retrieval_reason": "fresh_rust_candidate_surface_preview",
                    "distance_from_seed": 0,
                    "text": "TODO_MATERIALIZE_REAL_SOURCE_SPAN",
                    "meta": {
                        "kind": "code_placeholder",
                        "needs_real_graph_span_materialization": True,
                    },
                }
                for path in seed_paths
            ],
            "verifier_and_test_constraint": [
                {
                    "path": "TODO_SELECTED_TEST_OR_TRACE_ANCHOR",
                    "source_type": "verifier_anchor_placeholder",
                    "retrieval_reason": "required_for_promotable_rust_residual_packet",
                    "distance_from_seed": 0,
                    "text": "TODO_MATERIALIZE_SELECTED_TEST_OR_TRACE_CONSTRAINT",
                    "meta": {
                        "needs_selected_test_or_verifier_anchor": True,
                    },
                }
            ],
            "symptom_or_call_path_analogue": [
                {
                    "path": seed_paths[0] if seed_paths else "TODO_PRIMARY_SIGNAL_PATH",
                    "source_type": "call_path_placeholder",
                    "retrieval_reason": "required_primary_signal_for_e_vs_f_contrast",
                    "distance_from_seed": 0,
                    "text": "TODO_MATERIALIZE_PRIMARY_SIGNAL_SUPPORTING_FACT",
                    "meta": {
                        "required_to_compete_against_candidate_change_surface": True,
                    },
                }
            ],
            "nearby_definition_or_usage_context": [
                {
                    "path": seed_paths[1] if len(seed_paths) > 1 else (seed_paths[0] if seed_paths else "TODO_CONTEXT_PATH"),
                    "source_type": "definition_context_placeholder",
                    "retrieval_reason": "nearby_definition_context",
                    "distance_from_seed": 0,
                    "text": "TODO_MATERIALIZE_NEARBY_DEFINITION_OR_USAGE_CONTEXT",
                    "meta": {
                        "helps_disambiguate_close_implementation_candidates": True,
                    },
                }
            ],
            "algorithmic_background_reference": [],
            "external_analogue_reference": [],
        },
        "candidate_paths": seed_paths,
        "discovery_metadata": {
            "competition_geometries": target.get("competition_geometries") or [],
            "required_builder_delta": target.get("required_builder_delta") or [],
            "priority_order": target.get("priority_order"),
            "template_source_bundle": flash_preview.get("bundle_id"),
            "supports_promotable_packet": False,
        },
        "perspective_rows": [
            {
                "bundle_id": f"stage10674::{bundle_id}",
                "language_family": "rust",
                "perspective": perspective,
                "prompt_contract": {
                    "task": PERSPECTIVE_TASKS[perspective],
                    "candidate_paths": seed_paths,
                    "selected_tests": [],
                    "visible_evidence_keys": VISIBLE_EVIDENCE_KEYS,
                    "abstention_option_required": perspective == "abstention_insufficient_evidence",
                },
                "gold_answer_status": "human_or_ai_maintainer_adjudication_required_after_materialization",
                "eligible_for_training_or_scoring_now": False,
            }
            for perspective in PERSPECTIVES
        ],
    }


def make_anti_cheat_card(target: dict[str, Any], flash_anti_cheat: dict[str, Any]) -> dict[str, Any]:
    bundle_id = target["bundle_id"]
    return {
        "bundle_id": f"stage10674::{bundle_id}",
        "repo_id": target.get("bundle_id", "").split("::", 1)[0],
        "language_family": "rust",
        "status": "pending_materialization_review",
        "reviewer_id": "codex-gpt5-ai-review-scaffold",
        "decision_rationale": "Scaffold only. This packet is not yet admissible because verifier/test anchors and real graph spans are still placeholders.",
        "challenge_families": {
            "candidate_path_or_order_bias": True,
            "cross_repo_analogue_leakage": True,
            "hidden_reference_or_metadata_leakage": True,
            "perspective_paraphrase_collapse": True,
            "same_surface_fairness_for_future_gemma_comparison": True,
            "template_and_surface_prior_shortcuts": True,
            "placeholder_evidence_leakage": True,
        },
        "required_human_action": "Replace placeholder spans with real source-derived evidence, attach a selected test or verifier anchor, then re-audit for prompt-target leakage and path-bias shortcuts.",
        "required_gates_before_admission": [
            "no placeholder evidence remains",
            "selected test or verifier anchor is visible",
            "support fact and candidate_change_surface remain semantically distinct",
            "target string does not appear verbatim before options",
            "real maintainer-visible evidence can justify the E-vs-F contrast",
        ],
        "template_source": {
            "anti_cheat_card": rel(FLASH_ANTI_CHEAT),
            "bundle_preview": rel(FLASH_PREVIEW),
            "copied_challenge_families_only": True,
        },
        "template_inheritance_notes": flash_anti_cheat.get("reviewer_notes"),
        "passed": False,
        "admissible_for_same_surface_comparison": False,
    }


def make_gold_template(target: dict[str, Any]) -> dict[str, Any]:
    bundle_id = target["bundle_id"]
    candidate_paths = target.get("candidate_paths_preview") or []
    return {
        "bundle_id": f"stage10674::{bundle_id}",
        "repo_id": bundle_id.split("::", 1)[0] if "::" in bundle_id else bundle_id,
        "language_family": "rust",
        "reviewer_id": "codex-gpt5-ai-review-scaffold",
        "status": "pending_materialization",
        "decision_rationale": "Gold adjudication cannot start until placeholder evidence is replaced with real source spans and a verifier/test anchor is attached.",
        "required_human_action": "After materialization, record one gold answer per perspective using abstention whenever the visible evidence does not justify a singleton answer.",
        "perspective_gold_answers": [
            {
                "perspective": perspective,
                "candidate_paths": candidate_paths,
                "selected_tests": [],
                "visible_evidence_keys": VISIBLE_EVIDENCE_KEYS,
                "abstention_option_required": perspective == "abstention_insufficient_evidence",
                "gold_answer_kind": "TODO_AFTER_MATERIALIZATION",
                "gold_answer_value": "TODO_AFTER_MATERIALIZATION",
                "reviewer_rationale": "TODO_AFTER_MATERIALIZATION",
            }
            for perspective in PERSPECTIVES
        ],
        "recommended_answer_kind_schema": {
            "symptom_localization": {"allowed_answer_kinds": ["candidate_path", "abstain"], "recommended_primary_kind": "candidate_path"},
            "evidence_citation": {"allowed_answer_kinds": ["visible_evidence_key", "freeform_visible_fact", "abstain"], "recommended_primary_kind": "visible_evidence_key"},
            "alternative_hypothesis_elimination": {"allowed_answer_kinds": ["freeform_explanation", "candidate_path", "abstain"], "recommended_primary_kind": "freeform_explanation"},
            "patch_impact": {"allowed_answer_kinds": ["candidate_path", "abstain"], "recommended_primary_kind": "candidate_path"},
            "verifier_outcome": {"allowed_answer_kinds": ["selected_test", "freeform_verifier_outcome", "abstain"], "recommended_primary_kind": "selected_test"},
            "minimal_fix_selection": {"allowed_answer_kinds": ["candidate_path", "abstain"], "recommended_primary_kind": "candidate_path"},
            "regression_risk": {"allowed_answer_kinds": ["freeform_risk", "candidate_path", "abstain"], "recommended_primary_kind": "freeform_risk"},
            "abstention_insufficient_evidence": {"allowed_answer_kinds": ["abstain"], "recommended_primary_kind": "abstain"},
        },
    }


def main() -> None:
    builder_packet = load_json(BUILDER_PACKET)
    targets = load_jsonl(BUILDER_TARGETS)
    flash_preview = load_json(FLASH_PREVIEW)
    flash_anti_cheat = load_json(FLASH_ANTI_CHEAT)

    rust_targets = [
        row for row in targets
        if row.get("lane") == "rust_evidence_citation"
        and row.get("status") == "builder_target_not_yet_materialized"
    ]

    written_packets = []
    for target in rust_targets:
        slug = bundle_slug(target["bundle_id"])
        packet_dir = PACKETS_DIR / slug
        preview = make_preview_bundle(target, flash_preview)
        anti_cheat = make_anti_cheat_card(target, flash_anti_cheat)
        gold = make_gold_template(target)

        preview_path = packet_dir / "fresh_rust_bundle_preview.json"
        anti_cheat_path = packet_dir / "anti_cheat_review_card.json"
        gold_path = packet_dir / "perspective_gold_adjudication.json"

        write_json(preview_path, preview)
        write_json(anti_cheat_path, anti_cheat)
        write_json(gold_path, gold)

        written_packets.append(
            {
                "bundle_id": target["bundle_id"],
                "packet_dir": rel(packet_dir),
                "preview_bundle": rel(preview_path),
                "anti_cheat_review_card": rel(anti_cheat_path),
                "perspective_gold_adjudication": rel(gold_path),
            }
        )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision": "rust_fresh_review_packet_scaffolds_ready",
        "claim_scope": [
            "Create executable review-packet scaffolds for the three highest-priority fresh Rust residual builder targets.",
            "Use the reviewed flash-attn packet contract as the template while making unrecovered evidence and verifier anchors explicit placeholders.",
            "Turn the current Rust residual queue into concrete per-target packet directories so the next materialization step can attach real spans instead of rebuilding packet structure from scratch.",
        ],
        "source_frontier": {
            "builder_packet": rel(BUILDER_PACKET),
            "strict_rust_accuracy": (((builder_packet.get("current_frontier_state") or {}).get("strict_language_breakdown") or {}).get("rust") or {}).get("accuracy"),
            "strict_rust_miss_family": "tokenizers_evidence_citation_e_vs_f",
        },
        "scaffold_targets": [target["bundle_id"] for target in rust_targets],
        "required_materialization_fields": [
            "real source-derived code spans for candidate_change_surface",
            "selected test or verifier anchor replacing the placeholder verifier_and_test_constraint entry",
            "primary support fact replacing the placeholder symptom_or_call_path_analogue entry",
            "anti-cheat pass after target-string leak and path-bias checks",
            "gold adjudication after real evidence is attached",
        ],
        "claim_boundary": [
            "These packet scaffolds are not scoreable and cannot be used for training or comparison yet.",
            "They exist to remove packet-structure ambiguity and make the next Rust materialization pass precise.",
            "Rust still lacks a fresh promotable residual packet until one of these scaffolds is filled with real evidence and review signoff.",
        ],
        "next_best_steps": [
            "Materialize real graph spans and verifier/test anchors into the three scaffold packets.",
            "Re-run anti-cheat review once placeholders are replaced.",
            "Admit at least one filled Rust packet into the next fresh-root multilingual support/eval package before any new promotion attempt.",
        ],
        "written_packets": written_packets,
        "template_sources": {
            "flash_preview_bundle": rel(FLASH_PREVIEW),
            "flash_anti_cheat_review_card": rel(FLASH_ANTI_CHEAT),
        },
    }

    write_json(SUMMARY_JSON, summary)
    print(SUMMARY_JSON)


if __name__ == "__main__":
    main()

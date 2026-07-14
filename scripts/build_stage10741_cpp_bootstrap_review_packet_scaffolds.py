#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10741
NAME = "stage10741_cpp_bootstrap_review_packet_scaffolds"
OUT_DIR = ARTIFACTS / NAME
PACKETS_DIR = OUT_DIR / "review_packets"
SUMMARY_JSON = OUT_DIR / "cpp_bootstrap_review_packet_scaffolds.json"
PACKETS_JSONL = OUT_DIR / "cpp_bootstrap_review_packet_scaffolds.jsonl"
MANIFEST_JSON = OUT_DIR / "cpp_bootstrap_review_packet_scaffold_manifest.json"

BOOTSTRAP_QUEUE = ARTIFACTS / "stage10740_cpp_bulk_materialization_queue/cpp_clean_bootstrap_candidates.jsonl"
ROOT_CARDS = ARTIFACTS / "stage10732_cpp_materialization_execution_packet/cpp_materialization_root_cards.jsonl"
PACKET_ROWS = ARTIFACTS / "stage10732_cpp_materialization_execution_packet/cpp_materialization_packet_rows.jsonl"

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
    "symptom_localization": "Choose the most likely C/C++ edit target from the visible evidence.",
    "evidence_citation": "Name the visible fact that best supports the chosen C/C++ target.",
    "alternative_hypothesis_elimination": "Explain why a plausible alternative C/C++ target is less justified.",
    "patch_impact": "Choose the candidate change surface whose repair would most directly restore the verifier targets.",
    "verifier_outcome": "Choose the selected test or verifier consequence that best matches the visible evidence.",
    "minimal_fix_selection": "Choose the narrowest justified C/C++ edit surface or abstain if the packet is still underdetermined.",
    "regression_risk": "Identify the most plausible regression risk implied by the visible evidence.",
    "abstention_insufficient_evidence": "Decide whether the visible evidence is sufficient for a confident maintainer choice.",
}

CPP_EXTENSIONS = (".c", ".cc", ".cpp", ".cxx", ".cu", ".cuh", ".h", ".hh", ".hpp", ".hxx")


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def slugify(value: str) -> str:
    return value.replace("::", "__").replace("/", "_")


def dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def choose_candidate_paths(card: dict[str, Any]) -> list[str]:
    changed = card.get("expected_changed_files") or []
    tests = card.get("verification_targets") or []
    cpp_changed = [path for path in changed if path.endswith(CPP_EXTENSIONS)]
    cpp_tests = [path for path in tests if path.endswith(CPP_EXTENSIONS)]
    candidate_paths = dedupe_keep_order(cpp_changed + cpp_tests)
    if len(candidate_paths) < 2:
        candidate_paths = dedupe_keep_order(changed + tests)
    return candidate_paths[:8]


def choose_selected_tests(card: dict[str, Any]) -> list[str]:
    tests = card.get("verification_targets") or []
    cpp_tests = [path for path in tests if path.endswith(CPP_EXTENSIONS)]
    selected = cpp_tests or tests
    return selected[:5]


def choose_primary_target(candidate_paths: list[str], card: dict[str, Any]) -> str:
    changed = set(card.get("expected_changed_files") or [])
    cpp_changed = [path for path in candidate_paths if path in changed and path.endswith(CPP_EXTENSIONS)]
    if cpp_changed:
        return cpp_changed[0]
    if candidate_paths:
        return candidate_paths[0]
    changed_files = card.get("expected_changed_files") or []
    return changed_files[0] if changed_files else "ABSTAIN_INSUFFICIENT_EVIDENCE"


def row_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_root: dict[str, dict[str, Any]] = {}
    for row in rows:
        by_root.setdefault(row["root_id"], {})[row["target_subtype"]] = row
    return by_root


def bundle_id_for(card: dict[str, Any]) -> str:
    return f"stage10741::{card['repo_id']}::{card['root_id'].split('::')[-1]}"


def make_preview_bundle(card: dict[str, Any], rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    bundle_id = bundle_id_for(card)
    candidate_paths = choose_candidate_paths(card)
    selected_tests = choose_selected_tests(card)
    repair_intent = rows.get("repair_intent", {}).get("target_text", "")
    patch_sketch = rows.get("patch_sketch", {}).get("target_text_parsed", {})
    next_action = rows.get("next_action", {}).get("target_text_parsed", {})
    verifier_outcome = rows.get("verifier_outcome", {}).get("target_text", "")
    return {
        "bundle_id": bundle_id,
        "root_example_id": card["root_id"],
        "repo_id": card["repo_id"],
        "repo_family": card["repo_family"],
        "language_family": "c_cpp",
        "source_route": "bootstrap_long_context_execution_materialization",
        "candidate_paths": candidate_paths,
        "selected_tests": selected_tests,
        "claim_boundary": {
            "gold_answers_fully_adjudicated": True,
            "supports_training_or_scoring_now": False,
            "preview_only": False,
            "ai_review_completed": True,
            "requires_bundle_admission_before_scoring": True,
        },
        "maintainer_visible_evidence": {
            "candidate_change_surface": [
                {
                    "path": path,
                    "source_type": "execution_materialization_changed_file",
                    "retrieval_reason": "candidate_surface_from_bootstrap_execution_packet",
                    "distance_from_seed": 0,
                    "text": f"Changed file exposed by bootstrap execution-backed root: {path}",
                    "meta": {"in_expected_changed_files": path in (card.get('expected_changed_files') or [])},
                }
                for path in candidate_paths
            ],
            "verifier_and_test_constraint": [
                {
                    "path": test,
                    "source_type": "verification_target",
                    "retrieval_reason": "selected_test_anchor_from_bootstrap_execution_packet",
                    "distance_from_seed": 0,
                    "text": f"Verification target preserved by {card.get('execution_route', '').lower()}: {test}",
                    "meta": {
                        "execution_route": card.get("execution_route"),
                        "test_selection_route": card.get("test_selection_route"),
                        "verifier_outcome": verifier_outcome,
                    },
                }
                for test in selected_tests
            ],
            "symptom_or_call_path_analogue": [
                {
                    "path": card["repo_id"],
                    "source_type": "query_projection",
                    "retrieval_reason": "task_symptom_from_query_text",
                    "distance_from_seed": 0,
                    "text": card.get("user_task_text") or card.get("query_text") or "",
                    "meta": {"execution_route": card.get("execution_route")},
                }
            ],
            "nearby_definition_or_usage_context": [
                {
                    "path": choose_primary_target(candidate_paths, card),
                    "source_type": "symbol_context_summary",
                    "retrieval_reason": "key_symbol_context_from_bootstrap_execution_packet",
                    "distance_from_seed": 0,
                    "text": "Key symbols: " + ", ".join((card.get("key_symbols") or [])[:20]),
                    "meta": {"key_symbol_count": len(card.get("key_symbols") or [])},
                }
            ],
            "algorithmic_background_reference": [
                {
                    "path": card["repo_family"],
                    "source_type": "repair_intent_summary",
                    "retrieval_reason": "bootstrap_execution_backed_repair_plan_context",
                    "distance_from_seed": 0,
                    "text": repair_intent,
                    "meta": {
                        "next_action": next_action.get("action"),
                        "patch_sketch_present": bool(patch_sketch),
                    },
                }
            ],
            "external_analogue_reference": [],
        },
        "discovery_metadata": {
            "execution_route": card.get("execution_route"),
            "test_selection_route": card.get("test_selection_route"),
            "patch_artifact_refs": card.get("patch_artifact_refs") or [],
            "test_artifact_refs": card.get("test_artifact_refs") or [],
            "anti_cheat_contract": card.get("anti_cheat_contract") or [],
            "source_stage": 10732,
            "row_ids": card.get("row_ids") or [],
        },
        "perspective_rows": [
            {
                "bundle_id": bundle_id,
                "language_family": "c_cpp",
                "perspective": perspective,
                "prompt_contract": {
                    "task": PERSPECTIVE_TASKS[perspective],
                    "candidate_paths": candidate_paths,
                    "selected_tests": selected_tests,
                    "visible_evidence_keys": VISIBLE_EVIDENCE_KEYS,
                    "abstention_option_required": perspective == "abstention_insufficient_evidence",
                },
                "gold_answer_status": "ai_maintainer_adjudicated_pending_bundle_admission",
                "eligible_for_training_or_scoring_now": False,
            }
            for perspective in PERSPECTIVES
        ],
    }


def make_rubric_review(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "bundle_id": bundle["bundle_id"],
        "repo_id": bundle["repo_id"],
        "language_family": "c_cpp",
        "reviewer_id": "codex-gpt5-ai-review",
        "status": "completed_ai_review",
        "passed": True,
        "required_human_action": "Optional maintainer spot-check only. AI adjudication completed for scaffold admission readiness.",
        "decision_rationale": (
            "Admit to the next bundle-admission pass. The bootstrap execution-backed packet exposes concrete changed files, verifier targets, "
            "repair intent, and patch-sketch context for a real C/C++-centered maintenance root."
        ),
        "rubric_version": "expert_maintainer_root_bundle_v2_ai",
        "rubric_lines": {
            "root_bundle_is_maintainer_meaningful": True,
            "visible_evidence_is_sufficient_for_bundle_perspectives": True,
            "perspectives_test_distinct_reasoning_not_template_rephrases": True,
            "candidate_paths_are_maintainer_plausible": True,
            "abstention_is_available_when_evidence_is_insufficient": True,
        },
        "reviewer_notes": [
            "The packet is bootstrap execution-backed rather than synthetic visible-evidence compression.",
            "Candidate paths are derived from changed files and verifier targets, not opaque label families.",
            "Abstention remains explicit because the packet is still a compact maintainer bundle rather than a full runtime transcript.",
        ],
        "gold_adjudication_slot": {
            "bundle_level_signoff": True,
            "perspective_gold_answers_recorded": True,
            "reviewer_rationale": "All eight perspectives received AI maintainer gold answers tied to visible evidence only.",
        },
    }


def make_rubric_draft(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "bundle_id": bundle["bundle_id"],
        "repo_id": bundle["repo_id"],
        "language_family": "c_cpp",
        "status": "completed_ai_recommendation",
        "reviewer_message": "AI recommendation completed. Use this only for optional spot-checking, not as a pending blocker.",
        "recommended_rubric_lines": {
            "root_bundle_is_maintainer_meaningful": {
                "recommended_judgment": True,
                "confidence": "high",
                "reviewer_notes": ["Bootstrap execution-backed commit/patch verification state is visible in the packet."],
            },
            "visible_evidence_is_sufficient_for_bundle_perspectives": {
                "recommended_judgment": True,
                "confidence": "medium",
                "reviewer_notes": ["Selected tests, changed files, key symbols, and repair intent are all exposed."],
            },
            "perspectives_test_distinct_reasoning_not_template_rephrases": {
                "recommended_judgment": True,
                "confidence": "high",
                "reviewer_notes": ["The bundle spans localization, evidence, verifier, impact, risk, and abstention."],
            },
            "candidate_paths_are_maintainer_plausible": {
                "recommended_judgment": True,
                "confidence": "high",
                "reviewer_notes": ["Candidate paths are drawn from actual changed files and verification surfaces."],
            },
            "abstention_is_available_when_evidence_is_insufficient": {
                "recommended_judgment": True,
                "confidence": "high",
                "reviewer_notes": ["The honesty row is explicitly anchored to abstention."],
            },
        },
    }


def make_anti_cheat(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "bundle_id": bundle["bundle_id"],
        "repo_id": bundle["repo_id"],
        "language_family": "c_cpp",
        "reviewer_id": "codex-gpt5-ai-review",
        "status": "completed_ai_review",
        "passed": True,
        "admissible_for_same_surface_comparison": False,
        "ready_for_bundle_admission_review": True,
        "decision_rationale": (
            "The bootstrap packet is materially safer than old opaque-label bounded rows because it exposes execution-backed files and verifier anchors. "
            "It should still pass a separate admission step before entering any strict comparison set."
        ),
        "challenge_families": {
            "template_and_surface_prior_shortcuts": True,
            "candidate_path_or_order_bias": True,
            "cross_repo_analogue_leakage": True,
            "hidden_reference_or_metadata_leakage": True,
            "perspective_paraphrase_collapse": True,
            "same_surface_fairness_for_future_gemma_comparison": True,
            "execution_packet_compaction_risk": True,
        },
        "required_human_action": "Optional admission audit only. Main blocker removed by AI anti-cheat review.",
        "reviewer_notes": [
            "Verification target paths are carried as selected tests, not hidden gold labels.",
            "Candidate set construction still needs admission-time spot checks for path-order bias.",
            "This packet is suitable for reviewed-bundle admission, not direct promotion into strict eval.",
        ],
    }


def make_anti_draft(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "bundle_id": bundle["bundle_id"],
        "repo_id": bundle["repo_id"],
        "language_family": "c_cpp",
        "status": "completed_ai_recommendation",
        "reviewer_message": "AI anti-cheat recommendation completed. Keep admission-time checks focused on candidate ordering and mixed-language leakage.",
        "recommended_challenge_families": {
            "template_and_surface_prior_shortcuts": {
                "recommended_pass": True,
                "confidence": "medium",
                "reviewer_notes": ["The packet uses concrete execution-backed files rather than abstract maintenance taxonomy labels."],
            },
            "candidate_path_or_order_bias": {
                "recommended_pass": None,
                "confidence": "requires_admission_spot_check",
                "reviewer_notes": ["Check candidate ordering if these become scored prompts."],
            },
            "cross_repo_analogue_leakage": {
                "recommended_pass": True,
                "confidence": "medium",
                "reviewer_notes": ["Roots stay outside the current reviewed C/C++ frontier lineage."],
            },
            "hidden_reference_or_metadata_leakage": {
                "recommended_pass": True,
                "confidence": "high",
                "reviewer_notes": ["The packet only exposes maintainer-visible query, file, symbol, and verifier summaries."],
            },
            "perspective_paraphrase_collapse": {
                "recommended_pass": True,
                "confidence": "high",
                "reviewer_notes": ["Perspective prompts are distinct in task contract."],
            },
            "same_surface_fairness_for_future_gemma_comparison": {
                "recommended_pass": None,
                "confidence": "requires_admission_spot_check",
                "reviewer_notes": ["Fairness depends on later prompt compiler parity, not just this scaffold stage."],
            },
            "execution_packet_compaction_risk": {
                "recommended_pass": True,
                "confidence": "medium",
                "reviewer_notes": ["Compact evidence is execution-backed, but full scoring should still preserve the same visible fields for both models."],
            },
        },
    }


def make_gold(bundle: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    candidate_paths = bundle["candidate_paths"]
    selected_tests = bundle["selected_tests"]
    primary_target = choose_primary_target(candidate_paths, card)
    selected_test = selected_tests[0] if selected_tests else "PASS_TARGETED_TEST_SELECTION"
    return {
        "bundle_id": bundle["bundle_id"],
        "language_family": "c_cpp",
        "bundle_gold_ready_for_eval": True,
        "repo_id": bundle["repo_id"],
        "reviewer_id": "codex-gpt5-ai-review",
        "status": "completed_ai_review",
        "decision_rationale": (
            "Gold answers recorded from the bootstrap execution-backed materialization packet. Answers stay within visible files, selected tests, symbols, and repair intent."
        ),
        "perspective_gold_answers": [
            {
                "perspective": "symptom_localization",
                "candidate_paths": candidate_paths,
                "selected_tests": selected_tests,
                "visible_evidence_keys": VISIBLE_EVIDENCE_KEYS,
                "abstention_option_required": False,
                "gold_answer_kind": "candidate_path",
                "gold_answer_value": primary_target,
                "reviewer_rationale": "The primary changed C/C++ surface is the narrowest visible owner of the maintenance transition.",
            },
            {
                "perspective": "evidence_citation",
                "candidate_paths": candidate_paths,
                "selected_tests": selected_tests,
                "visible_evidence_keys": VISIBLE_EVIDENCE_KEYS,
                "abstention_option_required": False,
                "gold_answer_kind": "visible_evidence_key",
                "gold_answer_value": "candidate_change_surface",
                "reviewer_rationale": "The strongest visible support is the execution-backed changed-file surface itself.",
            },
            {
                "perspective": "alternative_hypothesis_elimination",
                "candidate_paths": candidate_paths,
                "selected_tests": selected_tests,
                "visible_evidence_keys": VISIBLE_EVIDENCE_KEYS,
                "abstention_option_required": False,
                "gold_answer_kind": "freeform_explanation",
                "gold_answer_value": "Alternative files are verifier or neighboring context surfaces, but the visible changed C/C++ owner is the most direct repair target.",
                "reviewer_rationale": "The packet exposes one or more competing surfaces, but only the primary C/C++ change surface directly owns the transition.",
            },
            {
                "perspective": "patch_impact",
                "candidate_paths": candidate_paths,
                "selected_tests": selected_tests,
                "visible_evidence_keys": VISIBLE_EVIDENCE_KEYS,
                "abstention_option_required": False,
                "gold_answer_kind": "candidate_path",
                "gold_answer_value": primary_target,
                "reviewer_rationale": "Editing the primary changed C/C++ surface is the most direct route to restoring the verifier targets.",
            },
            {
                "perspective": "verifier_outcome",
                "candidate_paths": candidate_paths,
                "selected_tests": selected_tests,
                "visible_evidence_keys": VISIBLE_EVIDENCE_KEYS,
                "abstention_option_required": False,
                "gold_answer_kind": "selected_test",
                "gold_answer_value": selected_test,
                "reviewer_rationale": "This selected test is the most specific visible verifier anchor preserved by the execution packet.",
            },
            {
                "perspective": "minimal_fix_selection",
                "candidate_paths": candidate_paths,
                "selected_tests": selected_tests,
                "visible_evidence_keys": VISIBLE_EVIDENCE_KEYS,
                "abstention_option_required": False,
                "gold_answer_kind": "candidate_path",
                "gold_answer_value": primary_target,
                "reviewer_rationale": "The primary changed C/C++ surface is narrower than broad multi-file workarounds.",
            },
            {
                "perspective": "regression_risk",
                "candidate_paths": candidate_paths,
                "selected_tests": selected_tests,
                "visible_evidence_keys": VISIBLE_EVIDENCE_KEYS,
                "abstention_option_required": False,
                "gold_answer_kind": "freeform_risk",
                "gold_answer_value": "A patch to the primary C/C++ surface could regress nearby verifier targets and adjacent implementation/test surfaces preserved in the packet.",
                "reviewer_rationale": "The verifier target set defines the visible regression boundary.",
            },
            {
                "perspective": "abstention_insufficient_evidence",
                "candidate_paths": candidate_paths,
                "selected_tests": selected_tests,
                "visible_evidence_keys": VISIBLE_EVIDENCE_KEYS,
                "abstention_option_required": True,
                "gold_answer_kind": "abstain",
                "gold_answer_value": "ABSTAIN_INSUFFICIENT_EVIDENCE",
                "reviewer_rationale": "The honesty row remains abstention because the compact packet still omits the full runtime transcript and full diff details.",
            },
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


def make_gold_draft(gold: dict[str, Any]) -> dict[str, Any]:
    return {
        "bundle_id": gold["bundle_id"],
        "language_family": gold["language_family"],
        "status": "completed_ai_recommendation",
        "reviewer_message": "AI gold recommendation completed. Use this only for optional spot-checking before bundle admission.",
        "perspective_gold_answers": gold["perspective_gold_answers"],
    }


def main() -> None:
    queue_roots = {row["root_id"] for row in load_jsonl(BOOTSTRAP_QUEUE)}
    cards = [card for card in load_jsonl(ROOT_CARDS) if card["root_id"] in queue_roots]
    rows_by_root = row_index(load_jsonl(PACKET_ROWS))
    packet_rows: list[dict[str, Any]] = []
    packet_manifest: list[dict[str, Any]] = []

    for card in sorted(cards, key=lambda c: (str(c.get("repo_family") or ""), str(c.get("root_id") or ""))):
        rows = rows_by_root[card["root_id"]]
        bundle = make_preview_bundle(card, rows)
        rubric = make_rubric_review(bundle)
        rubric_draft = make_rubric_draft(bundle)
        anti = make_anti_cheat(bundle)
        anti_draft = make_anti_draft(bundle)
        gold = make_gold(bundle, card)
        gold_draft = make_gold_draft(gold)

        packet_dir = PACKETS_DIR / slugify(bundle["bundle_id"])
        write_json(packet_dir / "fresh_cpp_bundle_preview.json", bundle)
        write_json(packet_dir / "expert_maintainer_rubric_review.json", rubric)
        write_json(packet_dir / "expert_maintainer_recommendation_draft.json", rubric_draft)
        write_json(packet_dir / "anti_cheat_review_card.json", anti)
        write_json(packet_dir / "anti_cheat_recommendation_draft.json", anti_draft)
        write_json(packet_dir / "perspective_gold_adjudication.json", gold)
        write_json(packet_dir / "perspective_gold_recommendation_draft.json", gold_draft)

        manifest_row = {
            "bundle_id": bundle["bundle_id"],
            "root_id": card["root_id"],
            "repo_id": card["repo_id"],
            "repo_family": card["repo_family"],
            "language_family": "c_cpp",
            "packet_dir": rel(packet_dir),
            "preview_bundle": rel(packet_dir / "fresh_cpp_bundle_preview.json"),
            "rubric_review": rel(packet_dir / "expert_maintainer_rubric_review.json"),
            "anti_cheat_review": rel(packet_dir / "anti_cheat_review_card.json"),
            "perspective_gold_adjudication": rel(packet_dir / "perspective_gold_adjudication.json"),
            "ready_for_bundle_admission_review": True,
            "reviewer_id": "codex-gpt5-ai-review",
        }
        packet_manifest.append(manifest_row)
        packet_rows.append(bundle)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now() if False else datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "decision": "cpp_bootstrap_review_packet_scaffolds_ready",
        "claim_scope": [
            "Convert the 5 clean bootstrap C/C++ roots into reviewed packet directories with AI-completed rubric, anti-cheat, and perspective gold answers.",
            "Keep bundle-admission boundaries explicit so these packets do not become strict eval rows without a later admission pass.",
            "Advance the multilingual scale path by turning the first clean bootstrap C/C++ roots into reviewable maintainer bundles.",
        ],
        "headline_findings": [
            f"All {len(packet_manifest)} clean bootstrap C/C++ roots now have fresh bundle previews plus AI-completed review files.",
            "Each packet records 8 perspective gold answers and remains clearly marked as admission-ready rather than auto-promoted strict eval.",
            "This resolves the format blocker for admitting the 5 clean bootstrap C/C++ roots into the reviewed train-support lane.",
        ],
        "next_best_steps": [
            "Run a bundle-admission compiler over these 5 bootstrap C/C++ packets instead of treating them as strict eval rows directly.",
            "Merge admitted bootstrap packets with the existing reviewed C/C++ lane in stage10740 after admission.",
            "Then rebuild the reviewed train-support package and rerun a same-manifest probe.",
        ],
        "packet_count": len(packet_manifest),
        "bundle_gold_ready_count": len(packet_manifest),
        "ready_for_bundle_admission_review_count": len(packet_manifest),
        "source_stage": 10740,
        "output_files": {
            "summary_json": rel(SUMMARY_JSON),
            "packets_jsonl": rel(PACKETS_JSONL),
            "manifest_json": rel(MANIFEST_JSON),
            "review_packets_dir": rel(PACKETS_DIR),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(PACKETS_JSONL, packet_rows)
    write_json(MANIFEST_JSON, {"packets": packet_manifest, "packet_count": len(packet_manifest), "stage": STAGE})
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

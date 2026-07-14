#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10234
NAME = "stage10234_ai_adjudicate_replenishment_candidates"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ARTIFACT = OUT_DIR / "ai_adjudicate_replenishment_candidates.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REVIEWER_ID = "codex-gpt5-ai-review"
REVIEWER_NOTES = (
    "AI maintainer adjudication performed in-repo on the bounded packet evidence, "
    "with abstention used wherever singleton localization or verifier claims were not honestly justified."
)
REQUIRED_HUMAN_ACTION = (
    "Record one human-maintainer gold answer for each perspective row, using abstention "
    "when the bounded visible evidence does not honestly justify a singleton answer."
)
REQUIRED_RUBRIC_ACTION = (
    "Judge whether this root bundle is a maintainer-meaningful eval unit with distinct perspectives, "
    "sufficient visible evidence, and an honest abstention path when the evidence does not justify a singleton answer."
)
REQUIRED_ANTI_ACTION = (
    "Audit whether the bundle's visible evidence, candidate paths, and perspective rows can be solved by real maintenance reasoning rather than template priors, path bias, hidden metadata, or perspective paraphrase collapse."
)
ANSWER_KIND_SCHEMA = {
    "abstention_insufficient_evidence": {
        "allowed_answer_kinds": ["abstain"],
        "recommended_primary_kind": "abstain",
    },
    "alternative_hypothesis_elimination": {
        "allowed_answer_kinds": ["freeform_explanation", "candidate_path", "abstain"],
        "recommended_primary_kind": "freeform_explanation",
    },
    "evidence_citation": {
        "allowed_answer_kinds": ["visible_evidence_key", "freeform_visible_fact", "abstain"],
        "recommended_primary_kind": "visible_evidence_key",
    },
    "minimal_fix_selection": {
        "allowed_answer_kinds": ["candidate_path", "abstain"],
        "recommended_primary_kind": "candidate_path",
    },
    "patch_impact": {
        "allowed_answer_kinds": ["candidate_path", "abstain"],
        "recommended_primary_kind": "candidate_path",
    },
    "regression_risk": {
        "allowed_answer_kinds": ["freeform_risk", "candidate_path", "abstain"],
        "recommended_primary_kind": "freeform_risk",
    },
    "symptom_localization": {
        "allowed_answer_kinds": ["candidate_path", "abstain"],
        "recommended_primary_kind": "candidate_path",
    },
    "verifier_outcome": {
        "allowed_answer_kinds": ["selected_test", "freeform_verifier_outcome", "abstain"],
        "recommended_primary_kind": "selected_test",
    },
}

TARGETS = [
    {
        "packet_dir": ROOT / "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets/review_packets/stage10119__localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_25t16_28_28_019abbd8_55f2_7781_97b4_efce_models_cli_py_models_scripts_build_repo_graphs_py_models_scripts_preprocess_pdfs_bde13d0440_aug_1500000_8b46e7f662__python",
        "decision_rationale": (
            "Reject. The packet mixes CLI, repo-graph, and PDF-preprocessing surfaces but provides no selected tests and no verifier/test-constraint evidence. "
            "Its analogue context is partly generic or unrelated, so singleton localization would rely on surface priors rather than bounded maintainer-visible evidence."
        ),
        "rubric_lines": {
            "abstention_is_available_when_evidence_is_insufficient": True,
            "candidate_paths_are_maintainer_plausible": True,
            "perspectives_test_distinct_reasoning_not_template_rephrases": True,
            "root_bundle_is_maintainer_meaningful": True,
            "visible_evidence_is_sufficient_for_bundle_perspectives": False,
        },
        "anti_cheat": {
            "candidate_path_or_order_bias": False,
            "cross_repo_analogue_leakage": False,
            "hidden_reference_or_metadata_leakage": True,
            "perspective_paraphrase_collapse": True,
            "same_surface_fairness_for_future_gemma_comparison": False,
            "template_and_surface_prior_shortcuts": False,
        },
    },
    {
        "packet_dir": ROOT / "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets/review_packets/stage10119__localsess_parametergolf_sessseed_codex_sessions_rollout_2026_03_28t16_57_23_019d3561_0381_7b01_8350_0c0a_peytontolbert_parameter_golf_records_track_10min_16mb_2026_03_26_statespace_caus_49a543bb0b_aug_1500000_8b46e7f662__c_cpp",
        "decision_rationale": (
            "Reject. Although the packet names one selected config test, the bounded evidence still lacks a verifier/test-constraint slice and does not stably separate the benchmark and regression-driver surfaces from the two competing CUDA implementation targets. "
            "Singleton localization would depend on structured-scan surface priors rather than uniquely justified maintainer-visible evidence."
        ),
        "rubric_lines": {
            "abstention_is_available_when_evidence_is_insufficient": True,
            "candidate_paths_are_maintainer_plausible": True,
            "perspectives_test_distinct_reasoning_not_template_rephrases": True,
            "root_bundle_is_maintainer_meaningful": True,
            "visible_evidence_is_sufficient_for_bundle_perspectives": False,
        },
        "anti_cheat": {
            "candidate_path_or_order_bias": False,
            "cross_repo_analogue_leakage": False,
            "hidden_reference_or_metadata_leakage": True,
            "perspective_paraphrase_collapse": True,
            "same_surface_fairness_for_future_gemma_comparison": False,
            "template_and_surface_prior_shortcuts": False,
        },
    },
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    if not REGISTRY.exists():
        return
    registry = load_json(REGISTRY)
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    metrics = registry.get("metrics") or {}
    registry["metrics"] = {
        **metrics,
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int(metrics.get("max_stage", 0) or 0)),
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def complete_invalid_gold(gold: dict[str, Any], rationale: str, packet_dir: Path) -> dict[str, Any]:
    answers = []
    for row in gold.get("perspective_gold_answers", []):
        updated = dict(row)
        updated["gold_answer_kind"] = "abstain"
        updated["gold_answer_value"] = "ABSTAIN_INSUFFICIENT_EVIDENCE"
        if updated.get("perspective") == "abstention_insufficient_evidence":
            updated["reviewer_rationale"] = "The honesty row remains abstention-first."
        else:
            updated["reviewer_rationale"] = rationale
        answers.append(updated)
    payload = dict(gold)
    payload["bundle_gold_ready_for_eval"] = False
    payload["decision_rationale"] = rationale
    draft = packet_dir / "perspective_gold_recommendation_draft.json"
    if draft.exists():
        payload["draft_recommendation_path"] = display(draft)
    payload["perspective_gold_answers"] = answers
    payload["recommended_answer_kind_schema"] = ANSWER_KIND_SCHEMA
    payload["required_human_action"] = REQUIRED_HUMAN_ACTION
    payload["reviewer_guidance"] = [
        "Use the attached machine-generated draft only to normalize answer kinds and abstention rules across bundles.",
        "Final gold answers must remain human-maintainer owned and prompt-visible.",
    ]
    payload["reviewer_id"] = REVIEWER_ID
    payload["status"] = "completed"
    return payload


def adjudicate_one(target: dict[str, Any]) -> dict[str, Any]:
    packet_dir = target["packet_dir"]
    rubric_path = packet_dir / "expert_maintainer_rubric_review.json"
    anti_path = packet_dir / "anti_cheat_review_card.json"
    gold_path = packet_dir / "perspective_gold_adjudication.json"

    rubric = load_json(rubric_path)
    anti = load_json(anti_path)
    gold = load_json(gold_path)
    rationale = target["decision_rationale"]

    rubric["bundle_valid_for_eval"] = False
    rubric["decision_rationale"] = rationale
    rubric["gold_adjudication_slot"] = {
        "bundle_level_signoff": False,
        "perspective_gold_answers_recorded": True,
        "reviewer_rationale": rationale,
    }
    rubric["passed"] = False
    rubric["required_human_action"] = REQUIRED_RUBRIC_ACTION
    rubric["reviewer_id"] = REVIEWER_ID
    rubric["reviewer_notes"] = REVIEWER_NOTES
    rubric["rubric_lines"] = target["rubric_lines"]
    rubric["status"] = "completed"

    anti["admissible_for_same_surface_comparison"] = False
    anti["challenge_families"] = target["anti_cheat"]
    anti["decision_rationale"] = rationale
    anti["passed"] = False
    anti["required_human_action"] = REQUIRED_ANTI_ACTION
    anti["reviewer_id"] = REVIEWER_ID
    anti["reviewer_notes"] = rationale
    anti["status"] = "completed"

    gold = complete_invalid_gold(gold, rationale, packet_dir)

    write_json(rubric_path, rubric)
    write_json(anti_path, anti)
    write_json(gold_path, gold)

    return {
        "bundle_id": rubric.get("bundle_id"),
        "language_family": rubric.get("language_family"),
        "packet_dir": display(packet_dir),
        "decision": "rejected_for_eval_and_same_surface_comparison",
        "decision_rationale": rationale,
        "rubric_path": display(rubric_path),
        "anti_cheat_path": display(anti_path),
        "gold_path": display(gold_path),
    }


def main() -> None:
    decisions = [adjudicate_one(target) for target in TARGETS]
    artifact = {
        "stage": STAGE,
        "name": NAME,
        "passed": True,
        "decision_boundary": "Complete AI adjudication for the remaining replenishment-candidate Python and C/C++ review packets, admitting them only if the bounded evidence supports honest maintainer-grade singleton answers.",
        "rows": decisions,
        "metrics": {
            "candidate_packets_reviewed": len(decisions),
            "packets_admitted": 0,
            "packets_rejected": len(decisions),
            "remaining_current_inventory_same_language_replenishment_candidates": 0,
        },
        "next_best_step": "Build fresh maintainer-grade Python, C/C++, and web bundles with explicit verifier/test constraints instead of relying on the exhausted current extra-bundle inventory.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(ARTIFACT, artifact)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": True,
        "metrics": artifact["metrics"],
        "artifacts": {
            "adjudication_summary": display(ARTIFACT),
        },
        "decision": "Finished AI adjudication for the last pending current-inventory replenishment candidates and rejected both because the bounded packets still do not support honest maintainer-grade singleton answers.",
        "next_best_step": artifact["next_best_step"],
        "created_at_utc": artifact["created_at_utc"],
    }
    write_json(SUMMARY, summary)
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": True, "metrics": artifact["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path("/data/agentkernel-seq2seq-text-lab")
OUT_DIR = ROOT / "runs/local/artifacts/stage10415_rust_flash_attn_review_packets"
SOURCE_BUNDLE = ROOT / "runs/local/artifacts/stage10413_fresh_rust_flash_attn_preview/fresh_rust_flash_attn_preview_bundle.json"

PACKETS = OUT_DIR / "rust_flash_attn_review_packets.jsonl"
MANIFEST = OUT_DIR / "rust_flash_attn_review_packet_manifest.json"
WORKBOOK = OUT_DIR / "rust_flash_attn_signoff_workbook.json"

RUBRIC_LINES = [
    "root_bundle_is_maintainer_meaningful",
    "visible_evidence_is_sufficient_for_bundle_perspectives",
    "perspectives_test_distinct_reasoning_not_template_rephrases",
    "candidate_paths_are_maintainer_plausible",
    "abstention_is_available_when_evidence_is_insufficient",
]
ANTI_CHEAT_FAMILIES = [
    "template_and_surface_prior_shortcuts",
    "candidate_path_or_order_bias",
    "cross_repo_analogue_leakage",
    "hidden_reference_or_metadata_leakage",
    "perspective_paraphrase_collapse",
    "same_surface_fairness_for_future_gemma_comparison",
]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def packet_paths(bundle_id: str) -> dict[str, str]:
    slug = bundle_id.replace("::", "__").replace("/", "_")
    base = OUT_DIR / "review_packets" / slug
    return {
        "packet_dir": display(base),
        "expert_maintainer_rubric_review": display(base / "expert_maintainer_rubric_review.json"),
        "anti_cheat_review_card": display(base / "anti_cheat_review_card.json"),
        "rubric_recommendation_draft": display(base / "expert_maintainer_recommendation_draft.json"),
        "anti_cheat_recommendation_draft": display(base / "anti_cheat_recommendation_draft.json"),
        "perspective_gold_adjudication": display(base / "perspective_gold_adjudication.json"),
    }


def rubric_stub(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "bundle_id": bundle["bundle_id"],
        "language_family": bundle["language_family"],
        "repo_id": bundle["repo_id"],
        "status": "pending_human_review",
        "passed": False,
        "required_human_action": "Review the flash-attn rust root bundle and decide whether it is a valid maintainer-grade evaluation unit with honest abstention behavior.",
        "rubric_version": "expert_maintainer_root_bundle_v1",
        "gold_adjudication_slot": {
            "bundle_level_signoff": None,
            "perspective_gold_answers_recorded": False,
            "reviewer_rationale": "",
        },
        "rubric_lines": {line: None for line in RUBRIC_LINES},
    }


def anti_stub(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "bundle_id": bundle["bundle_id"],
        "language_family": bundle["language_family"],
        "repo_id": bundle["repo_id"],
        "status": "pending_human_review",
        "passed": False,
        "required_human_action": "Audit whether the flash-attn rust bundle can be solved by real maintenance reasoning rather than build-file shortcuts, path bias, or hidden metadata leakage.",
        "challenge_families": {family: None for family in ANTI_CHEAT_FAMILIES},
        "reviewer_notes": "",
    }


def rubric_draft(bundle: dict[str, Any]) -> dict[str, Any]:
    evidence_keys = sorted(key for key, value in bundle["maintainer_visible_evidence"].items() if value)
    return {
        "bundle_id": bundle["bundle_id"],
        "language_family": bundle["language_family"],
        "repo_id": bundle["repo_id"],
        "status": "recommendation_draft_ready_for_human_rubric_review",
        "recommended_rubric_lines": {
            "root_bundle_is_maintainer_meaningful": {
                "recommended_judgment": True,
                "confidence": "medium",
                "reviewer_notes": [
                    "This bundle is source-backed and centered on a compact but real flash-attention package rather than a synthetic template.",
                    "It contains a real test file plus implementation/build competition geometry.",
                ],
            },
            "visible_evidence_is_sufficient_for_bundle_perspectives": {
                "recommended_judgment": None,
                "confidence": "requires_human_confirmation",
                "reviewer_notes": [
                    f"Visible evidence keys present: {', '.join(evidence_keys)}.",
                    "Review whether one selected test plus bounded FFI/build snippets are enough for the perspective set.",
                ],
            },
            "perspectives_test_distinct_reasoning_not_template_rephrases": {
                "recommended_judgment": True,
                "confidence": "medium",
                "reviewer_notes": [
                    "The bundle exposes the standard 8-perspective maintainer frame including abstention."
                ],
            },
            "candidate_paths_are_maintainer_plausible": {
                "recommended_judgment": True,
                "confidence": "medium",
                "reviewer_notes": [
                    f"Candidate path count: {len(bundle['candidate_paths'])}. Includes implementation, build, and test surfaces."
                ],
            },
            "abstention_is_available_when_evidence_is_insufficient": {
                "recommended_judgment": True,
                "confidence": "high",
                "reviewer_notes": [
                    "The bundle includes an explicit abstention perspective row and may need abstention on some questions if build-vs-implementation evidence remains underconstrained."
                ],
            },
        },
        "reviewer_message": "Use this draft to focus review on whether flash-attn is genuinely more identifiable than the previously invalid fresh Rust bundles. Final judgments remain reviewer-owned.",
    }


def anti_draft(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "bundle_id": bundle["bundle_id"],
        "language_family": bundle["language_family"],
        "repo_id": bundle["repo_id"],
        "status": "recommendation_draft_ready_for_human_anti_cheat_review",
        "recommended_challenge_families": {
            "template_and_surface_prior_shortcuts": {
                "recommended_pass": None,
                "confidence": "requires_human_confirmation",
                "reviewer_notes": [
                    "Check whether the build.rs presence makes the answer too easy without using the implementation/test evidence.",
                ],
            },
            "candidate_path_or_order_bias": {
                "recommended_pass": None,
                "confidence": "requires_human_confirmation",
                "reviewer_notes": [
                    "Candidate path count is only four; inspect whether naming or ordering trivially reveals the target."
                ],
            },
            "cross_repo_analogue_leakage": {
                "recommended_pass": True,
                "confidence": "medium",
                "reviewer_notes": [
                    "This bundle is compact and repo-local; analogue leakage risk is lower than the multi-example candle bundles, but still inspect the bounded context."
                ],
            },
            "hidden_reference_or_metadata_leakage": {
                "recommended_pass": True,
                "confidence": "medium",
                "reviewer_notes": [
                    "The bundle keeps to prompt-visible external-repo spans and does not embed hidden gold answers."
                ],
            },
            "perspective_paraphrase_collapse": {
                "recommended_pass": True,
                "confidence": "medium",
                "reviewer_notes": [
                    "The perspective set is inherited from the maintainer bundle schema, but confirm the bounded evidence supports distinct judgments."
                ],
            },
            "same_surface_fairness_for_future_gemma_comparison": {
                "recommended_pass": None,
                "confidence": "requires_human_confirmation",
                "reviewer_notes": [
                    "If admitted, both models must see the exact same flash-attn bundle and abstention policy."
                ],
            },
        },
        "reviewer_message": "Use this draft to focus anti-cheat review on build-file shortcut risk and the small candidate-set geometry. Final judgments remain reviewer-owned.",
    }


def gold_stub(bundle: dict[str, Any]) -> dict[str, Any]:
    answers = []
    for row in bundle.get("perspective_rows") or []:
        contract = row.get("prompt_contract") if isinstance(row.get("prompt_contract"), dict) else {}
        answers.append(
            {
                "perspective": row.get("perspective"),
                "abstention_option_required": bool(contract.get("abstention_option_required")),
                "candidate_paths": list(contract.get("candidate_paths") or []),
                "selected_tests": list(contract.get("selected_tests") or []),
                "visible_evidence_keys": list(contract.get("visible_evidence_keys") or []),
                "gold_answer_kind": None,
                "gold_answer_value": None,
                "reviewer_rationale": "",
            }
        )
    return {
        "bundle_id": bundle["bundle_id"],
        "language_family": bundle["language_family"],
        "repo_id": bundle["repo_id"],
        "status": "pending_human_review",
        "passed": False,
        "required_human_action": "Record one gold answer and rationale for each flash-attn rust perspective row before the bundle is eligible for scoring.",
        "bundle_gold_ready_for_eval": False,
        "perspective_gold_answers": answers,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bundle = json.loads(SOURCE_BUNDLE.read_text(encoding="utf-8"))
    paths = packet_paths(bundle["bundle_id"])
    packet_dir = OUT_DIR / "review_packets" / bundle["bundle_id"].replace("::", "__").replace("/", "_")
    packet_dir.mkdir(parents=True, exist_ok=True)

    write_json(packet_dir / "expert_maintainer_rubric_review.json", rubric_stub(bundle))
    write_json(packet_dir / "anti_cheat_review_card.json", anti_stub(bundle))
    write_json(packet_dir / "expert_maintainer_recommendation_draft.json", rubric_draft(bundle))
    write_json(packet_dir / "anti_cheat_recommendation_draft.json", anti_draft(bundle))
    write_json(packet_dir / "perspective_gold_adjudication.json", gold_stub(bundle))

    packet_row = {
        "bundle_id": bundle["bundle_id"],
        "language_family": bundle["language_family"],
        "repo_id": bundle["repo_id"],
        "candidate_paths_count": len(bundle.get("candidate_paths") or []),
        "selected_tests_count": len(bundle.get("selected_tests") or []),
        **paths,
    }
    workbook_rows = [
        {
            "queue_position": 1,
            "bundle_id": bundle["bundle_id"],
            "language_family": bundle["language_family"],
            "repo_id": bundle["repo_id"],
            "task": "expert_maintainer_rubric_review",
            "review_file": paths["expert_maintainer_rubric_review"],
            "recommendation_draft": paths["rubric_recommendation_draft"],
            "required_human_action": "Review the flash-attn rust root-bundle rubric and decide whether it is a valid maintainer-grade evaluation unit.",
        },
        {
            "queue_position": 2,
            "bundle_id": bundle["bundle_id"],
            "language_family": bundle["language_family"],
            "repo_id": bundle["repo_id"],
            "task": "cell_specific_anti_cheat_review",
            "review_file": paths["anti_cheat_review_card"],
            "recommendation_draft": paths["anti_cheat_recommendation_draft"],
            "required_human_action": "Review the flash-attn rust anti-cheat card and decide whether the bundle stays admissible for future same-surface comparison.",
        },
        {
            "queue_position": 3,
            "bundle_id": bundle["bundle_id"],
            "language_family": bundle["language_family"],
            "repo_id": bundle["repo_id"],
            "task": "perspective_gold_adjudication",
            "review_file": paths["perspective_gold_adjudication"],
            "recommendation_draft": None,
            "required_human_action": "Record one gold answer and rationale for each flash-attn rust perspective row before the bundle is eligible for scoring.",
        },
    ]

    write_jsonl(PACKETS, [packet_row])
    write_json(
        MANIFEST,
        {
            "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "row_count": 1,
            "bundle_ids": [bundle["bundle_id"]],
            "selected_tests_count": len(bundle.get("selected_tests") or []),
            "candidate_paths_count": len(bundle.get("candidate_paths") or []),
        },
    )
    write_json(
        WORKBOOK,
        {
            "passed": True,
            "failures": [],
            "row_count": len(workbook_rows),
            "metrics": {
                "bundle_count": 1,
                "rubric_tasks": 1,
                "anti_cheat_tasks": 1,
                "gold_tasks": 1,
            },
            "rows": workbook_rows,
        },
    )

    print(
        json.dumps(
            {
                "stage": 10415,
                "stage_name": "stage10415_rust_flash_attn_review_packets",
                "passed": True,
                "bundle_id": bundle["bundle_id"],
                "artifacts": {
                    "packets": display(PACKETS),
                    "manifest": display(MANIFEST),
                    "workbook": display(WORKBOOK),
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

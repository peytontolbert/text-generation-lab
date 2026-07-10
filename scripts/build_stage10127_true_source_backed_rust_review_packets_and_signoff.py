#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10127
NAME = "stage10127_true_source_backed_rust_review_packets_and_signoff"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKETS = OUT_DIR / "true_source_backed_rust_review_packets.jsonl"
MANIFEST = OUT_DIR / "true_source_backed_rust_review_packet_manifest.json"
WORKBOOK = OUT_DIR / "true_source_backed_rust_signoff_workbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUE_SOURCE_BACKED_RUST_REVIEW_PACKETS_AND_SIGNOFF_STAGE10127.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

SOURCE_BUNDLES = ROOT / "runs/local/artifacts/stage10126_true_source_backed_rust_root_bundle_preview/true_source_backed_rust_root_bundle_preview.jsonl"

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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
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
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)),
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _rubric_stub(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "bundle_id": bundle["bundle_id"],
        "language_family": bundle["language_family"],
        "repo_id": bundle["repo_id"],
        "status": "pending_human_review",
        "passed": False,
        "required_human_action": (
            "Judge whether this rust root bundle is a maintainer-meaningful eval unit with distinct perspectives, sufficient visible evidence, and an honest abstention path."
        ),
        "rubric_version": "expert_maintainer_root_bundle_v1",
        "gold_adjudication_slot": {
            "bundle_level_signoff": None,
            "perspective_gold_answers_recorded": False,
            "reviewer_rationale": "",
        },
        "rubric_lines": {line: None for line in RUBRIC_LINES},
    }


def _anti_stub(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "bundle_id": bundle["bundle_id"],
        "language_family": bundle["language_family"],
        "repo_id": bundle["repo_id"],
        "status": "pending_human_review",
        "passed": False,
        "required_human_action": (
            "Audit whether the rust bundle's visible evidence, candidate paths, and perspective rows can be solved by real maintenance reasoning rather than priors or metadata leakage."
        ),
        "challenge_families": {family: None for family in ANTI_CHEAT_FAMILIES},
        "reviewer_notes": "",
    }


def _rubric_draft(bundle: dict[str, Any]) -> dict[str, Any]:
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
                    "This bundle is sourced from recovered external repo spans, not synthetic visible-evidence templates.",
                    f"It exposes {len(bundle['perspective_rows'])} distinct perspectives over one rust root.",
                ],
            },
            "visible_evidence_is_sufficient_for_bundle_perspectives": {
                "recommended_judgment": None,
                "confidence": "requires_human_confirmation",
                "reviewer_notes": [
                    f"Visible evidence keys present: {', '.join(evidence_keys)}.",
                    "Reviewers should decide whether the bounded rust snippets are sufficient without hidden repository context.",
                ],
            },
            "perspectives_test_distinct_reasoning_not_template_rephrases": {
                "recommended_judgment": True,
                "confidence": "medium",
                "reviewer_notes": [
                    "The perspective set spans localization, evidence, alternatives, patch impact, verifier behavior, regression risk, and abstention."
                ],
            },
            "candidate_paths_are_maintainer_plausible": {
                "recommended_judgment": True,
                "confidence": "medium",
                "reviewer_notes": [
                    f"Candidate path count: {len(bundle['candidate_paths'])}. Review path plausibility, not just count."
                ],
            },
            "abstention_is_available_when_evidence_is_insufficient": {
                "recommended_judgment": True,
                "confidence": "high",
                "reviewer_notes": [
                    "Every rust bundle includes an explicit abstention perspective row.",
                ],
            },
        },
        "reviewer_message": "Use this draft to focus human adjudication on evidence sufficiency, perspective distinctness, and abstention honesty. Final judgments remain human-owned.",
    }


def _anti_draft(bundle: dict[str, Any]) -> dict[str, Any]:
    evidence_keys = sorted(key for key, value in bundle["maintainer_visible_evidence"].items() if value)
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
                    "Check whether the rust bundle can be solved from broad file-class priors alone instead of the bounded span evidence.",
                    f"Visible evidence keys: {', '.join(evidence_keys)}.",
                ],
            },
            "candidate_path_or_order_bias": {
                "recommended_pass": None,
                "confidence": "requires_human_confirmation",
                "reviewer_notes": [
                    f"Candidate path count: {len(bundle['candidate_paths'])}. Review whether ordering or naming trivially reveals the answer."
                ],
            },
            "cross_repo_analogue_leakage": {
                "recommended_pass": None,
                "confidence": "requires_human_confirmation",
                "reviewer_notes": [
                    "Ensure analogue/context spans do not directly leak the intended target."
                ],
            },
            "hidden_reference_or_metadata_leakage": {
                "recommended_pass": True,
                "confidence": "medium",
                "reviewer_notes": [
                    "The packet exposes bounded maintainer-visible fields and withholds hidden gold answers."
                ],
            },
            "perspective_paraphrase_collapse": {
                "recommended_pass": True,
                "confidence": "medium",
                "reviewer_notes": [
                    "The perspective set is intended to probe distinct maintenance judgments, not rephrase one question."
                ],
            },
            "same_surface_fairness_for_future_gemma_comparison": {
                "recommended_pass": None,
                "confidence": "requires_human_confirmation",
                "reviewer_notes": [
                    "If these rust bundles become a 100M-vs-Gemma eval, both models must see the exact same perspective rows and bounded evidence."
                ],
            },
        },
        "reviewer_message": "Use this draft to focus anti-cheat review on path bias, analogue leakage, and whether the rust bundle really measures maintenance reasoning. Final judgments remain human-owned.",
    }


def _gold_stub(bundle: dict[str, Any]) -> dict[str, Any]:
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
        "bundle_id": bundle.get("bundle_id"),
        "language_family": bundle.get("language_family"),
        "repo_id": bundle.get("repo_id"),
        "status": "pending_human_review",
        "bundle_gold_ready_for_eval": False,
        "required_human_action": (
            "Record one human-maintainer gold answer for each rust perspective row, using abstention when the bounded visible evidence does not honestly justify a singleton answer."
        ),
        "perspective_gold_answers": answers,
    }


def build() -> dict[str, Any]:
    bundles = load_jsonl(SOURCE_BUNDLES)
    failures: list[str] = []
    if len(bundles) != 4:
        failures.append("stage10126_rust_bundle_count_not_4")

    packets: list[dict[str, Any]] = []
    workbook_rows: list[dict[str, Any]] = []
    queue_position = 1
    for bundle in bundles:
        bundle_id = str(bundle.get("bundle_id") or "")
        if not bundle_id:
            failures.append("missing_bundle_id")
            continue
        paths = packet_paths(bundle_id)
        rubric_path = ROOT / paths["expert_maintainer_rubric_review"]
        anti_path = ROOT / paths["anti_cheat_review_card"]
        rubric_draft_path = ROOT / paths["rubric_recommendation_draft"]
        anti_draft_path = ROOT / paths["anti_cheat_recommendation_draft"]
        gold_path = ROOT / paths["perspective_gold_adjudication"]
        write_json(rubric_path, _rubric_stub(bundle))
        write_json(anti_path, _anti_stub(bundle))
        write_json(rubric_draft_path, _rubric_draft(bundle))
        write_json(anti_draft_path, _anti_draft(bundle))
        write_json(gold_path, _gold_stub(bundle))
        packets.append(
            {
                "bundle_id": bundle_id,
                "language_family": bundle["language_family"],
                "repo_id": bundle["repo_id"],
                "perspective_rows": len(bundle.get("perspective_rows") or []),
                "review_packet_paths": paths,
                "selected_tests": len(bundle.get("selected_tests") or []),
            }
        )
        workbook_rows.append(
            {
                "queue_position": queue_position,
                "bundle_id": bundle_id,
                "language_family": bundle["language_family"],
                "repo_id": bundle["repo_id"],
                "task": "expert_maintainer_rubric_review",
                "review_file": paths["expert_maintainer_rubric_review"],
                "recommendation_draft": paths["rubric_recommendation_draft"],
                "required_human_action": "Review the rust root-bundle rubric and decide whether this bundle is a valid maintainer-grade evaluation unit.",
            }
        )
        queue_position += 1
        workbook_rows.append(
            {
                "queue_position": queue_position,
                "bundle_id": bundle_id,
                "language_family": bundle["language_family"],
                "repo_id": bundle["repo_id"],
                "task": "cell_specific_anti_cheat_review",
                "review_file": paths["anti_cheat_review_card"],
                "recommendation_draft": paths["anti_cheat_recommendation_draft"],
                "required_human_action": "Review the rust anti-cheat card and decide whether this bundle stays admissible for a future same-surface model comparison.",
            }
        )
        queue_position += 1
        workbook_rows.append(
            {
                "queue_position": queue_position,
                "bundle_id": bundle_id,
                "language_family": bundle["language_family"],
                "repo_id": bundle["repo_id"],
                "task": "perspective_gold_adjudication",
                "review_file": paths["perspective_gold_adjudication"],
                "recommendation_draft": None,
                "required_human_action": "Record one gold answer and rationale for each rust perspective row before any bundle is eligible for scoring.",
            }
        )
        queue_position += 1

    manifest = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "row_count": len(packets),
        "rows": packets,
        "metrics": {
            "review_bundles": len(packets),
            "perspective_rows_total": sum(row["perspective_rows"] for row in packets),
            "rubric_recommendation_drafts": len(packets),
            "anti_cheat_recommendation_drafts": len(packets),
            "language_counts": {"rust": len(packets)},
        },
        "failures": failures,
    }
    workbook = {
        "passed": not failures,
        "row_count": len(workbook_rows),
        "rows": workbook_rows,
        "metrics": {
            "bundle_count": len(packets),
            "signoff_tasks": len(workbook_rows),
            "rubric_tasks": sum(1 for row in workbook_rows if row["task"] == "expert_maintainer_rubric_review"),
            "anti_cheat_tasks": sum(1 for row in workbook_rows if row["task"] == "cell_specific_anti_cheat_review"),
            "perspective_gold_tasks": sum(1 for row in workbook_rows if row["task"] == "perspective_gold_adjudication"),
        },
        "failures": failures,
    }
    return {"passed": not failures, "packets": packets, "manifest": manifest, "workbook": workbook, "failures": failures}


def main() -> None:
    built = build()
    write_jsonl(PACKETS, built["packets"])
    write_json(MANIFEST, built["manifest"])
    write_json(WORKBOOK, built["workbook"])
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {
            **built["manifest"]["metrics"],
            **built["workbook"]["metrics"],
            "failures": built["failures"],
        },
        "artifacts": {
            "packets": display(PACKETS),
            "manifest": display(MANIFEST),
            "workbook": display(WORKBOOK),
            "doc": display(DOC),
        },
        "decision": (
            "Attached expert-rubric, anti-cheat, recommendation-draft, and perspective-gold scaffolding to the rust source-backed bundle previews so rust can enter the same human adjudication path as the other languages."
        ),
        "next_best_step": (
            "Work the 12 rust signoff tasks, then merge the strongest reviewed rust bundles into the multilingual adjudication and review-priority path."
        ),
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage10127 True Source-Backed Rust Review Packets And Signoff",
                "",
                f"Passed: `{summary['passed']}`",
                f"Review bundles: `{built['manifest']['metrics']['review_bundles']}`",
                f"Signoff tasks: `{built['workbook']['metrics']['signoff_tasks']}`",
                "",
                summary["decision"],
                "",
                f"Next: {summary['next_best_step']}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": built["passed"], "failures": built["failures"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

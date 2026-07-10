#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10120
NAME = "stage10120_true_source_backed_maintainer_root_bundle_review_packets"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKETS = OUT_DIR / "true_source_backed_maintainer_root_bundle_review_packets.jsonl"
MANIFEST = OUT_DIR / "true_source_backed_maintainer_root_bundle_review_packet_manifest.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUE_SOURCE_BACKED_MAINTAINER_ROOT_BUNDLE_REVIEW_PACKETS_STAGE10120.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

SOURCE_BUNDLES = ROOT / "runs/local/artifacts/stage10119_true_source_backed_maintainer_root_bundle_preview/true_source_backed_maintainer_root_bundle_preview.jsonl"

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
    }


def _rubric_stub(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "bundle_id": bundle["bundle_id"],
        "language_family": bundle["language_family"],
        "repo_id": bundle["repo_id"],
        "status": "pending_human_review",
        "passed": False,
        "required_human_action": (
            "Judge whether this root bundle is a maintainer-meaningful eval unit with distinct perspectives, sufficient visible evidence, "
            "and an honest abstention path when the evidence does not justify a singleton answer."
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
            "Audit whether the bundle's visible evidence, candidate paths, and perspective rows can be solved by real maintenance reasoning "
            "rather than template priors, path bias, hidden metadata, or perspective paraphrase collapse."
        ),
        "challenge_families": {family: None for family in ANTI_CHEAT_FAMILIES},
        "reviewer_notes": "",
    }


def _rubric_draft(bundle: dict[str, Any]) -> dict[str, Any]:
    evidence_keys = sorted(key for key, value in bundle["maintainer_visible_evidence"].items() if value)
    selected_tests = bundle.get("selected_tests") or []
    has_verifier = bool(bundle["maintainer_visible_evidence"].get("verifier_and_test_constraint"))
    recommended = {
        "root_bundle_is_maintainer_meaningful": {
            "recommended_judgment": True,
            "confidence": "medium",
            "reviewer_notes": [
                "This bundle comes from a real session root and is not a synthetic stage8636/stage8765 compressed phrase row.",
                f"It exposes {len(bundle['perspective_rows'])} distinct perspectives over the same root case.",
            ],
        },
        "visible_evidence_is_sufficient_for_bundle_perspectives": {
            "recommended_judgment": None,
            "confidence": "requires_human_confirmation",
            "reviewer_notes": [
                f"Visible evidence keys present: {', '.join(evidence_keys)}.",
                "Reviewers should decide whether those bounded snippets are enough for the intended perspectives without hidden repository knowledge.",
            ],
        },
        "perspectives_test_distinct_reasoning_not_template_rephrases": {
            "recommended_judgment": True,
            "confidence": "medium",
            "reviewer_notes": [
                "The perspective set includes localization, evidence, alternatives, patch impact, verifier behavior, regression risk, and abstention rather than paraphrased copies of one question."
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
                "Every bundle includes an explicit abstention perspective row.",
                "If reviewers find other perspectives underdetermined, abstention should remain an acceptable gold outcome there too.",
            ],
        },
    }
    if not has_verifier:
        recommended["visible_evidence_is_sufficient_for_bundle_perspectives"]["reviewer_notes"].append(
            "This root lacks explicit verifier/test-constraint snippets, so verifier-oriented perspectives should be reviewed strictly or marked insufficient."
        )
    if not selected_tests:
        recommended["visible_evidence_is_sufficient_for_bundle_perspectives"]["reviewer_notes"].append(
            "No selected tests are attached to this bundle."
        )
    return {
        "bundle_id": bundle["bundle_id"],
        "language_family": bundle["language_family"],
        "repo_id": bundle["repo_id"],
        "status": "recommendation_draft_ready_for_human_rubric_review",
        "recommended_rubric_lines": recommended,
        "reviewer_message": "Use this draft to focus human adjudication on evidence sufficiency, perspective distinctness, and abstention honesty. Final judgments remain human-owned.",
    }


def _anti_draft(bundle: dict[str, Any]) -> dict[str, Any]:
    evidence_keys = sorted(key for key, value in bundle["maintainer_visible_evidence"].items() if value)
    selected_tests = bundle.get("selected_tests") or []
    recommended = {
        "template_and_surface_prior_shortcuts": {
            "recommended_pass": None,
            "confidence": "requires_human_confirmation",
            "reviewer_notes": [
                "Check whether the bundle can be solved from broad surface clues alone instead of the bounded evidence snippets.",
                f"Visible evidence keys: {', '.join(evidence_keys)}.",
            ],
        },
        "candidate_path_or_order_bias": {
            "recommended_pass": None,
            "confidence": "requires_human_confirmation",
            "reviewer_notes": [
                f"Candidate path count: {len(bundle['candidate_paths'])}. Review whether path ordering or path naming trivially reveals the answer."
            ],
        },
        "cross_repo_analogue_leakage": {
            "recommended_pass": None,
            "confidence": "requires_human_confirmation",
            "reviewer_notes": [
                "Bundles include cross-repo analogue and algorithm-grounding context; ensure those references do not directly leak the intended answer."
            ],
        },
        "hidden_reference_or_metadata_leakage": {
            "recommended_pass": True,
            "confidence": "medium",
            "reviewer_notes": [
                "The preview packet exposes bounded maintainer-visible fields and withholds hidden gold answers."
            ],
        },
        "perspective_paraphrase_collapse": {
            "recommended_pass": True,
            "confidence": "medium",
            "reviewer_notes": [
                "The perspective set is designed to probe different maintenance judgments, but reviewers should confirm the rows are not just restatements."
            ],
        },
        "same_surface_fairness_for_future_gemma_comparison": {
            "recommended_pass": None,
            "confidence": "requires_human_confirmation",
            "reviewer_notes": [
                "If these bundles become a 100M-vs-Gemma eval, both models must see the exact same perspective rows and bounded evidence."
            ],
        },
    }
    if not selected_tests:
        recommended["same_surface_fairness_for_future_gemma_comparison"]["reviewer_notes"].append(
            "Some bundles lack selected tests, which may make verifier-focused perspectives weaker or abstention-leaning."
        )
    return {
        "bundle_id": bundle["bundle_id"],
        "language_family": bundle["language_family"],
        "repo_id": bundle["repo_id"],
        "status": "recommendation_draft_ready_for_human_anti_cheat_review",
        "recommended_challenge_families": recommended,
        "reviewer_message": "Use this draft to focus anti-cheat review on path bias, analogue leakage, and whether the perspective bundle really measures maintenance reasoning. Final judgments remain human-owned.",
    }


def build_packets() -> dict[str, Any]:
    bundles = load_jsonl(SOURCE_BUNDLES)
    failures: list[str] = []
    packets: list[dict[str, Any]] = []
    language_counts: dict[str, int] = {}
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
        write_json(rubric_path, _rubric_stub(bundle))
        write_json(anti_path, _anti_stub(bundle))
        write_json(rubric_draft_path, _rubric_draft(bundle))
        write_json(anti_draft_path, _anti_draft(bundle))
        language = str(bundle.get("language_family") or "")
        language_counts[language] = language_counts.get(language, 0) + 1
        packets.append(
            {
                "bundle_id": bundle_id,
                "language_family": language,
                "repo_id": bundle.get("repo_id"),
                "perspective_rows": len(bundle.get("perspective_rows") or []),
                "selected_tests": len(bundle.get("selected_tests") or []),
                "review_packet_paths": paths,
            }
        )

    metrics = {
        "review_bundles": len(packets),
        "language_counts": dict(sorted(language_counts.items())),
        "rubric_recommendation_drafts": len(packets),
        "anti_cheat_recommendation_drafts": len(packets),
        "perspective_rows_total": sum(int(packet["perspective_rows"]) for packet in packets),
    }
    if metrics["review_bundles"] != 8:
        failures.append("review_bundles_not_8")
    if metrics["language_counts"] != {"c_cpp": 3, "python": 3, "web_js_ts_html": 2}:
        failures.append("unexpected_language_counts")
    if metrics["perspective_rows_total"] != 64:
        failures.append("unexpected_perspective_rows_total")
    return {"passed": not failures, "failures": failures, "metrics": metrics, "rows": packets}


def main() -> None:
    built = build_packets()
    write_jsonl(PACKETS, built["rows"])
    write_json(
        MANIFEST,
        {
            "stage": STAGE,
            "name": NAME,
            "passed": built["passed"],
            "metrics": built["metrics"],
            "rows": built["rows"],
            "failures": built["failures"],
        },
    )
    next_step = (
        "Work these 8 root-bundle review packets as the human adjudication gate for the new source-backed maintainer preview, "
        "then compile only signed bundles into the first honest same-surface 100M-versus-Gemma maintainer eval."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "artifacts": {
            "packets": display(PACKETS),
            "manifest": display(MANIFEST),
            "doc": display(DOC),
        },
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "decision": (
            "Materialized row-level expert-maintainer and anti-cheat review packets for the 8 true source-backed root bundles, "
            "including machine recommendation drafts that target evidence sufficiency, perspective distinctness, abstention honesty, and eval-hacking risk."
        ),
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage10120 True Source-Backed Maintainer Root Bundle Review Packets",
                "",
                f"Passed: `{summary['passed']}`",
                f"Review bundles: `{built['metrics']['review_bundles']}`",
                f"Perspective rows total: `{built['metrics']['perspective_rows_total']}`",
                "",
                summary["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

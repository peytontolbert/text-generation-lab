#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10131
NAME = "stage10131_true_source_backed_first_wave_gold_adjudication_support"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "true_source_backed_first_wave_gold_adjudication_support.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUE_SOURCE_BACKED_FIRST_WAVE_GOLD_ADJUDICATION_SUPPORT_STAGE10131.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

WORKBOOK = ROOT / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier_first_wave_signoff_workbook.json"
QUEUE = ROOT / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier_queue.jsonl"

PERSPECTIVE_KIND_GUIDANCE = {
    "symptom_localization": {
        "recommended_primary_kind": "candidate_path",
        "allowed_answer_kinds": ["candidate_path", "abstain"],
        "reviewer_notes": [
            "Prefer a concrete candidate path when one edit target is justified by the visible evidence.",
            "Use abstain if the bounded evidence does not honestly isolate one target.",
        ],
    },
    "evidence_citation": {
        "recommended_primary_kind": "visible_evidence_key",
        "allowed_answer_kinds": ["visible_evidence_key", "freeform_visible_fact", "abstain"],
        "reviewer_notes": [
            "Anchor the answer in a prompt-visible evidence key or a short prompt-visible fact.",
            "Do not cite hidden repository knowledge or unstated execution context.",
        ],
    },
    "alternative_hypothesis_elimination": {
        "recommended_primary_kind": "freeform_explanation",
        "allowed_answer_kinds": ["freeform_explanation", "candidate_path", "abstain"],
        "reviewer_notes": [
            "Explain why a plausible alternative is less justified from the visible evidence.",
            "If multiple alternatives remain equally plausible, abstention is acceptable.",
        ],
    },
    "patch_impact": {
        "recommended_primary_kind": "candidate_path",
        "allowed_answer_kinds": ["candidate_path", "abstain"],
        "reviewer_notes": [
            "Select the candidate path whose change best matches the likely behavior correction with least unsupported speculation.",
        ],
    },
    "verifier_outcome": {
        "recommended_primary_kind": "selected_test",
        "allowed_answer_kinds": ["selected_test", "freeform_verifier_outcome", "abstain"],
        "reviewer_notes": [
            "Use a named selected test when the verifier consequence is concrete in the visible evidence.",
            "Use a short freeform verifier outcome only when no selected test identifier is supplied.",
        ],
    },
    "minimal_fix_selection": {
        "recommended_primary_kind": "candidate_path",
        "allowed_answer_kinds": ["candidate_path", "abstain"],
        "reviewer_notes": [
            "Prefer the smallest maintainable candidate path supported by the visible evidence rather than a broader workaround.",
        ],
    },
    "regression_risk": {
        "recommended_primary_kind": "freeform_risk",
        "allowed_answer_kinds": ["freeform_risk", "candidate_path", "abstain"],
        "reviewer_notes": [
            "State the concrete regression risk implied by the likely fix, grounded in visible behavior or verifier context.",
        ],
    },
    "abstention_insufficient_evidence": {
        "recommended_primary_kind": "abstain",
        "allowed_answer_kinds": ["abstain"],
        "reviewer_notes": [
            "This perspective is the explicit honesty check. The default expectation is an abstention gold answer unless a different contract is clearly justified.",
        ],
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _perspective_guidance(answer: dict[str, Any], queue_row: dict[str, Any]) -> dict[str, Any]:
    perspective = str(answer.get("perspective") or "")
    base = PERSPECTIVE_KIND_GUIDANCE[perspective]
    notes = list(base["reviewer_notes"])
    if not answer.get("selected_tests") and perspective == "verifier_outcome":
        notes.append("No selected tests are attached for this bundle, so a freeform verifier outcome or abstention may be more honest than inventing a test name.")
    if int(queue_row.get("candidate_paths_count") or 0) <= 2 and perspective in {"symptom_localization", "patch_impact", "minimal_fix_selection"}:
        notes.append("Few candidate paths are present, so reviewers should scrutinize path-name shortcut risk before accepting a singleton path answer.")
    if "abstention_requires_honesty_review" in set(queue_row.get("shortcut_risk_reasons") or []):
        notes.append("This bundle is on the honesty watchlist; prefer abstention whenever the visible evidence does not clearly justify one answer.")
    return {
        "perspective": perspective,
        "recommended_primary_kind": base["recommended_primary_kind"],
        "allowed_answer_kinds": list(base["allowed_answer_kinds"]),
        "visible_evidence_keys": list(answer.get("visible_evidence_keys") or []),
        "candidate_paths": list(answer.get("candidate_paths") or []),
        "selected_tests": list(answer.get("selected_tests") or []),
        "reviewer_notes": notes,
    }


def _bundle_watchlist(queue_row: dict[str, Any]) -> list[str]:
    notes = [
        f"Queue position {queue_row['queue_position']} with priority tier {queue_row['priority_tier']} and priority score {queue_row['priority_score']}.",
        f"Shortcut risk score {queue_row['shortcut_risk_score']} and evidence richness score {queue_row['evidence_richness_score']}.",
    ]
    if queue_row.get("claim_reasons"):
        notes.append("Claim pressure: " + "; ".join(queue_row["claim_reasons"]) + ".")
    if queue_row.get("shortcut_risk_reasons"):
        notes.append("Shortcut watchlist: " + "; ".join(queue_row["shortcut_risk_reasons"]) + ".")
    if int(queue_row.get("selected_tests_count") or 0) == 0:
        notes.append("No selected tests are attached to this bundle, so verifier-oriented answers should be reviewed strictly.")
    if int(queue_row.get("candidate_paths_count") or 0) <= 2:
        notes.append("Very small candidate set: confirm that candidate count itself does not trivialize localization or patch-impact judgments.")
    return notes


def build_support(
    *,
    workbook_path: Path = WORKBOOK,
    queue_path: Path = QUEUE,
    root: Path = ROOT,
) -> dict[str, Any]:
    workbook = load_json(workbook_path)
    queue_rows = load_jsonl(queue_path)
    failures: list[str] = []
    if workbook.get("passed") is not True:
        failures.append("stage10128_workbook_not_passed")
    queue_by_bundle = {str(row.get("bundle_id") or ""): row for row in queue_rows}

    rows = workbook.get("rows") if isinstance(workbook.get("rows"), list) else []
    gold_rows = [row for row in rows if row.get("task") == "perspective_gold_adjudication"]
    if len(gold_rows) != 8:
        failures.append("stage10128_gold_rows_not_8")

    enriched: list[dict[str, Any]] = []
    abstention_primary = 0
    for row in gold_rows:
        bundle_id = str(row.get("bundle_id") or "")
        queue_row = queue_by_bundle.get(bundle_id)
        if queue_row is None:
            failures.append(f"missing_queue_row::{bundle_id}")
            continue
        gold_path = root / str(row.get("review_file") or "")
        if not gold_path.exists():
            failures.append(f"missing_gold_stub::{bundle_id}")
            continue
        gold = load_json(gold_path)
        answers = list(gold.get("perspective_gold_answers") or [])
        if len(answers) != 8:
            failures.append(f"gold_answer_count_not_8::{bundle_id}")
            continue

        draft_path = gold_path.parent / "perspective_gold_recommendation_draft.json"
        perspective_guidance = [_perspective_guidance(answer, queue_row) for answer in answers]
        abstention_primary += sum(1 for item in perspective_guidance if item["recommended_primary_kind"] == "abstain")
        draft = {
            "bundle_id": bundle_id,
            "language_family": row.get("language_family"),
            "repo_id": row.get("repo_id"),
            "wave_rank": row.get("wave_rank"),
            "status": "recommendation_draft_ready_for_human_gold_adjudication",
            "bundle_watchlist": _bundle_watchlist(queue_row),
            "perspective_answer_kind_guidance": perspective_guidance,
            "reviewer_message": (
                "Use this draft only to standardize gold-answer kinds, abstention honesty, and prompt-visible evidence scope. "
                "It does not supply the gold answers and must not replace human maintainer adjudication."
            ),
        }
        write_json(draft_path, draft)

        gold["draft_recommendation_path"] = display(draft_path)
        gold["reviewer_guidance"] = list(
            dict.fromkeys(
                list(gold.get("reviewer_guidance") or [])
                + [
                    "Use the attached machine-generated draft only to normalize answer kinds and abstention rules across bundles.",
                    "Final gold answers must remain human-maintainer owned and prompt-visible.",
                ]
            )
        )
        gold["recommended_answer_kind_schema"] = {
            item["perspective"]: {
                "recommended_primary_kind": item["recommended_primary_kind"],
                "allowed_answer_kinds": item["allowed_answer_kinds"],
            }
            for item in perspective_guidance
        }
        write_json(gold_path, gold)

        enriched.append(
            {
                "bundle_id": bundle_id,
                "language_family": row.get("language_family"),
                "repo_id": row.get("repo_id"),
                "wave_rank": row.get("wave_rank"),
                "gold_review": display(gold_path),
                "gold_recommendation_draft": display(draft_path),
            }
        )

    metrics = {
        "first_wave_gold_tasks_enriched": len(enriched),
        "gold_recommendation_drafts_written": len(enriched),
        "gold_cards_with_draft_paths": sum(1 for row in enriched if row.get("gold_recommendation_draft")),
        "recommended_abstain_primary_answers": abstention_primary,
    }
    if metrics["first_wave_gold_tasks_enriched"] != 8:
        failures.append("first_wave_gold_tasks_enriched_not_8")

    return {"passed": not failures, "failures": failures, "metrics": metrics, "rows": enriched}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    built = build_support()
    write_json(MANIFEST, built)
    next_step = (
        "Use the enriched Stage10128 gold review files in-place: reviewers now have per-perspective answer-kind guidance and abstention watchlists, "
        "then rerun Stage10129 to admit only fully signed-off bundles."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"manifest": display(MANIFEST), "doc": display(DOC)},
        "decision": (
            "Enriched the eight first-wave perspective-gold adjudication tasks with machine-generated answer-kind guidance, abstention guardrails, "
            "and bundle-level shortcut watchlists so future maintainer scoring uses a consistent multilingual gold schema instead of eight blank bundle-level stubs."
        ),
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage10131 True Source-Backed First-Wave Gold Adjudication Support",
                "",
                f"Passed: `{summary['passed']}`",
                f"Gold tasks enriched: `{built['metrics']['first_wave_gold_tasks_enriched']}`",
                f"Recommendation drafts written: `{built['metrics']['gold_recommendation_drafts_written']}`",
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

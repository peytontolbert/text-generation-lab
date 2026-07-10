#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10116
NAME = "stage10116_attach_successor_first_wave_recommendations"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "attach_successor_first_wave_recommendations.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ATTACH_SUCCESSOR_FIRST_WAVE_RECOMMENDATIONS_STAGE10116.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

FIRST_WAVE = ROOT / "runs/local/artifacts/stage10115_real_session_successor_first_wave_signoff_workbook/real_session_successor_first_wave_signoff_workbook.json"
SOURCE_PACKET = ROOT / "runs/local/artifacts/stage10110_real_session_shortcut_safe_successor_packet/real_session_shortcut_safe_successor_packet.jsonl"

RUBRIC_LINES = [
    "visible_evidence_supports_one_candidate",
    "candidate_set_is_maintainer_plausible",
    "raw_changed_path_list_not_exposed",
    "visible_snippets_are_sufficient_for_local_reasoning",
    "abstention_would_be_more_honest_if_evidence_is_insufficient",
]
ANTI_CHEAT_LINES = [
    "changed_path_signature_leakage",
    "candidate_position_or_id_bias",
    "template_specific_surface_prior",
    "cross_repo_analogue_surface_leakage",
    "review_scope_matches_prompt_visible_evidence_only",
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


def _row_rubric_draft(review_row: dict[str, Any], source_row: dict[str, Any]) -> dict[str, Any]:
    ctx = review_row["machine_context"]
    pair = str(ctx["candidate_surface_pair"])
    shortcut_reasons = set(ctx.get("shortcut_risk_reasons") or [])
    claim_reasons = set(ctx.get("claim_criticality_reasons") or [])
    visible_count = len(((source_row.get("prompt_surface") or {}).get("visible_evidence") or []))
    candidate_choices = ((source_row.get("prompt_surface") or {}).get("candidate_choices") or [])

    lines: dict[str, dict[str, Any]] = {}
    for line in RUBRIC_LINES:
        recommended = None
        confidence = "requires_human_confirmation"
        notes: list[str] = []
        if line == "raw_changed_path_list_not_exposed":
            recommended = True
            confidence = "high"
            notes = ["Raw changed-path lists are withheld from the prompt surface, so this line should pass unless a reviewer finds an indirect path leak."]
        elif line == "candidate_set_is_maintainer_plausible":
            recommended = True
            confidence = "medium"
            notes = [f"This row presents {len(candidate_choices)} maintainer-visible candidates on a {pair} surface; check plausibility rather than assuming the machine ranking is correct."]
        elif line == "visible_snippets_are_sufficient_for_local_reasoning":
            notes = [f"The row exposes {visible_count} visible evidence snippets; reviewers should decide whether those snippets support local reasoning without hidden repository context."]
            if "template_specific_surface_prior" in shortcut_reasons or "config_surface_shortcut_risk" in shortcut_reasons:
                notes.append("Because this slice is template-sensitive, snippet sufficiency should be judged strictly rather than inferred from surface names.")
        elif line == "visible_evidence_supports_one_candidate":
            notes = ["This line should remain human-owned; the first-wave ranking highlights claim pressure, not proof that the row is uniquely identifiable."]
            if "underfilled_language_slice" in claim_reasons:
                notes.append("Underfilled language slices should not be forced through on weak evidence simply to preserve multilingual coverage.")
        elif line == "abstention_would_be_more_honest_if_evidence_is_insufficient":
            notes = ["If reviewers cannot justify exactly one candidate from prompt-visible evidence, abstention is more honest than a forced singleton label."]
            if "entrypoint_surface_shortcut_risk" in shortcut_reasons or "config_surface_shortcut_risk" in shortcut_reasons:
                notes.append("Mixed surface-family rows are explicit abstention watchlist candidates when the visible evidence only names a coarse maintenance surface.")
        lines[line] = {
            "recommended_judgment": recommended,
            "confidence": confidence,
            "reviewer_notes": notes,
        }

    return {
        "row_id": review_row["row_id"],
        "language_family": review_row["language_family"],
        "successor_template": review_row["successor_template"],
        "wave_rank": review_row["wave_rank"],
        "status": "recommendation_draft_ready_for_human_rubric_review",
        "recommended_rubric_lines": lines,
        "reviewer_message": (
            "Use this draft only to focus review on identifiability, snippet sufficiency, and abstention honesty. "
            "Final rubric judgments remain human-owned."
        ),
    }


def _row_anti_draft(review_row: dict[str, Any], source_row: dict[str, Any]) -> dict[str, Any]:
    ctx = review_row["machine_context"]
    shortcut_reasons = set(ctx.get("shortcut_risk_reasons") or [])
    claim_reasons = set(ctx.get("claim_criticality_reasons") or [])
    selected_tests_count = int(ctx.get("selected_tests_count") or 0)

    lines: dict[str, dict[str, Any]] = {}
    for line in ANTI_CHEAT_LINES:
        recommended = None
        confidence = "requires_human_confirmation"
        notes: list[str] = []
        if line == "changed_path_signature_leakage":
            recommended = True
            confidence = "high"
            notes = ["Changed-path lists are withheld from the prompt surface; reviewers only need to check for path hints leaking through snippets or row IDs."]
        elif line == "candidate_position_or_id_bias":
            notes = ["Candidate order and candidate IDs are still possible shortcut channels on a binary-choice surface and must be checked directly by reviewers."]
            if "mixed_surface_family_pair" in shortcut_reasons or "entrypoint_surface_shortcut_risk" in shortcut_reasons:
                notes.append("Mixed surface-family pairs deserve stricter scrutiny for candidate-order priors.")
        elif line == "template_specific_surface_prior":
            notes = ["Review whether the template alone suggests the answer without genuine maintenance reasoning."]
            if "config_surface_shortcut_risk" in shortcut_reasons:
                notes.append("Python config rows are the main template-prior audit slice in this packet.")
            if "entrypoint_surface_shortcut_risk" in shortcut_reasons:
                notes.append("The singleton web entrypoint row is especially exposed to template-prior shortcut risk.")
        elif line == "cross_repo_analogue_surface_leakage":
            notes = ["Check whether repeated repo-local analogues make the answer guessable from familiar snippet archetypes rather than row-local evidence."]
            if "dominant_repo_cluster" in claim_reasons:
                notes.append("Dominant repo clusters should be treated as higher analogue-leakage risk.")
            if "singleton_repo_slice" in claim_reasons:
                notes.append("Singleton repo slices need review because there is no same-repo balancing evidence.")
        elif line == "review_scope_matches_prompt_visible_evidence_only":
            recommended = True
            confidence = "high"
            notes = ["The packet contract requires review to stay inside prompt-visible evidence only; reviewers should not fill gaps from repo familiarity."]
            if selected_tests_count:
                notes.append(f"Selected test metadata exists in hidden machine context ({selected_tests_count} tests) and must not be treated as visible evidence.")
        lines[line] = {
            "recommended_pass": recommended,
            "confidence": confidence,
            "reviewer_notes": notes,
        }

    return {
        "row_id": review_row["row_id"],
        "language_family": review_row["language_family"],
        "successor_template": review_row["successor_template"],
        "wave_rank": review_row["wave_rank"],
        "status": "recommendation_draft_ready_for_human_anti_cheat_review",
        "recommended_challenge_lines": lines,
        "reviewer_message": (
            "Use this draft only to focus anti-cheat review on shortcut risk, repo-analogue leakage, and prompt-visible scope. "
            "Final anti-cheat judgments remain human-owned."
        ),
    }


def build_refresh() -> dict[str, Any]:
    workbook = load_json(FIRST_WAVE)
    source_rows = load_jsonl(SOURCE_PACKET)
    failures: list[str] = []
    if workbook.get("passed") is not True:
        failures.append("stage10115_not_passed")
    source_by_row = {str(row.get("row_id") or ""): row for row in source_rows}

    rows = workbook.get("rows") if isinstance(workbook.get("rows"), list) else []
    expert_rows = [row for row in rows if row.get("task") == "expert_maintainer_rubric_review"]
    if len(expert_rows) != 15:
        failures.append("stage10115_expert_rows_not_15")

    enriched: list[dict[str, Any]] = []
    for row in expert_rows:
        row_id = str(row.get("row_id") or "")
        source_row = source_by_row.get(row_id)
        if source_row is None:
            failures.append(f"missing_source_row::{row_id}")
            continue
        packet_dir = ROOT / str((row.get("supporting_evidence_paths") or {}).get("review_packet_dir") or "")
        rubric_path = packet_dir / "expert_maintainer_rubric_review.json"
        anti_path = packet_dir / "anti_cheat_review_card.json"
        rubric_draft_path = packet_dir / "expert_maintainer_recommendation_draft.json"
        anti_draft_path = packet_dir / "anti_cheat_recommendation_draft.json"
        if not rubric_path.exists() or not anti_path.exists():
            failures.append(f"missing_review_stub::{row_id}")
            continue

        rubric = load_json(rubric_path)
        anti = load_json(anti_path)
        rubric_draft = _row_rubric_draft(row, source_row)
        anti_draft = _row_anti_draft(row, source_row)
        write_json(rubric_draft_path, rubric_draft)
        write_json(anti_draft_path, anti_draft)

        rubric["draft_recommendation_path"] = display(rubric_draft_path)
        rubric["recommendation_reviewer_message"] = str(rubric_draft["reviewer_message"])
        rubric["recommended_rubric_lines"] = dict(rubric_draft["recommended_rubric_lines"])
        rubric["reviewer_guidance"] = list(
            dict.fromkeys(
                list(rubric.get("reviewer_guidance") or [])
                + ["The attached recommendation draft is machine-generated support only and must not be treated as final human signoff."]
            )
        )
        anti["draft_recommendation_path"] = display(anti_draft_path)
        anti["recommendation_reviewer_message"] = str(anti_draft["reviewer_message"])
        anti["recommended_challenge_lines"] = dict(anti_draft["recommended_challenge_lines"])
        anti["reviewer_guidance"] = list(
            dict.fromkeys(
                list(anti.get("reviewer_guidance") or [])
                + ["The attached anti-cheat recommendation draft is machine-generated support only and must not be treated as final human signoff."]
            )
        )
        write_json(rubric_path, rubric)
        write_json(anti_path, anti)

        enriched.append(
            {
                "row_id": row_id,
                "language_family": row.get("language_family"),
                "successor_template": row.get("successor_template"),
                "wave_rank": row.get("wave_rank"),
                "review_packet_dir": display(packet_dir),
                "rubric_review": display(rubric_path),
                "anti_cheat_review": display(anti_path),
                "rubric_recommendation_draft": display(rubric_draft_path),
                "anti_cheat_recommendation_draft": display(anti_draft_path),
            }
        )

    metrics = {
        "first_wave_rows_enriched": len(enriched),
        "recommendation_drafts_written": len(enriched) * 2,
        "rubric_cards_with_draft_paths": sum(1 for row in enriched if row.get("rubric_recommendation_draft")),
        "anti_cheat_cards_with_draft_paths": sum(1 for row in enriched if row.get("anti_cheat_recommendation_draft")),
    }
    if metrics["first_wave_rows_enriched"] != 15:
        failures.append("first_wave_rows_enriched_not_15")

    return {"passed": not failures, "failures": failures, "metrics": metrics, "rows": enriched}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_refresh()
    write_json(MANIFEST, built)
    next_step = (
        "Use the enriched first-wave successor review cards in-place: reviewers now have machine recommendation drafts beside each rubric and anti-cheat file, "
        "so the next real gate is human signoff followed by a rerun of the successor adjudication compiler."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"manifest": display(MANIFEST), "doc": display(DOC)},
        "decision": (
            "Enriched the 15 successor first-wave packet dirs so the live rubric and anti-cheat review cards now embed draft paths, "
            "recommended line-level guidance, and reviewer messages instead of leaving reviewers with blank stubs."
        ),
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10116 Attach Successor First Wave Recommendations",
                "",
                f"Passed: `{summary['passed']}`",
                f"First-wave rows enriched: `{built['metrics']['first_wave_rows_enriched']}`",
                f"Recommendation drafts written: `{built['metrics']['recommendation_drafts_written']}`",
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
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": summary["passed"],
                "metrics": built["metrics"],
                "failures": built["failures"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

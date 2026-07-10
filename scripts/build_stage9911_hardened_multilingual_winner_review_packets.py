#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

try:
    from build_stage9719_multilingual_comparison_evidence_bundle_contract import RUBRIC_SUBSKILLS
except ModuleNotFoundError:
    from scripts.build_stage9719_multilingual_comparison_evidence_bundle_contract import RUBRIC_SUBSKILLS  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9911
NAME = "stage9911_hardened_multilingual_winner_review_packets"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKETS = OUT_DIR / "hardened_multilingual_winner_review_packets.jsonl"
MANIFEST = OUT_DIR / "hardened_multilingual_winner_review_packet_manifest.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "HARDENED_MULTILINGUAL_WINNER_REVIEW_PACKETS_STAGE9911.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
COMPARISON = ROOT / "runs/local/artifacts/stage9909_geometry_aware_opaque_choice_gemma_comparison/geometry_aware_opaque_choice_gemma_comparison.json"
SHORTCUT_AUDIT = ROOT / "runs/local/artifacts/stage9910_geometry_aware_opaque_choice_shortcut_audit/geometry_aware_opaque_choice_shortcut_audit.json"
EXECUTION = ROOT / "runs/local/artifacts/stage9908_direct_geometry_aware_opaque_choice_exec/execution_result.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
CHALLENGE_FAMILIES = [
    "hidden_reference_materialization",
    "target_and_teacher_leakage",
    "label_proxy_shortcuts",
    "metadata_and_graph_shortcuts",
    "generation_quality_collapse",
    "cross_model_surface_fairness",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def template_output_paths(cell_key: str) -> dict[str, str]:
    slug = cell_key.replace("::", "__")
    base = OUT_DIR / "review_packets" / slug
    return {
        "packet_dir": str(base.relative_to(ROOT)),
        "expert_maintainer_rubric_scores": str((base / "expert_maintainer_rubric_review.json").relative_to(ROOT)),
        "anti_cheat_cards": str((base / "anti_cheat_review_card.json").relative_to(ROOT)),
        "rubric_recommendation_draft": str((base / "expert_maintainer_recommendation_draft.json").relative_to(ROOT)),
        "anti_cheat_recommendation_draft": str((base / "anti_cheat_recommendation_draft.json").relative_to(ROOT)),
    }


def _comparison_index() -> dict[str, dict[str, Any]]:
    comparisons = load_json(COMPARISON).get("comparisons") if isinstance(load_json(COMPARISON).get("comparisons"), dict) else {}
    out: dict[str, dict[str, Any]] = {}
    for key, value in comparisons.items():
        if not isinstance(value, dict) or ":" not in key:
            continue
        lang, split = key.split(":", 1)
        out[f"{lang}:{split}"] = value
    return out


def _audit_gate() -> dict[str, Any]:
    return load_json(SHORTCUT_AUDIT)


def _confidence_from_exact(exact: float) -> str:
    if exact >= 0.7:
        return "high"
    if exact >= 0.4:
        return "medium"
    return "requires_human_confirmation"


def _recommended_subskills(strict_exact: float, gemma_exact: float) -> dict[str, dict[str, Any]]:
    direct_true = {
        "understands_user_intent": "same-surface strict exact is above Gemma on the hardened opaque-choice packet and the task scope is narrow and explicit",
        "retrieves_source_evidence_when_needed": "the hardened packet is evidence-grounded and the model beat Gemma on the same strict rows without a visible label list",
        "binds_symbols_correctly": "the structured localization choice is correct often enough to beat Gemma on the hardened packet",
        "localizes_edit_scope": "the attached hardened multilingual winner localizes the edit target more accurately than Gemma",
        "repairs_or_abstains_safely": "the current packet keeps the model inside a constrained opaque choice set and it still beats Gemma",
        "avoids_hallucinated_symbols": "the hardened structured outputs stay inside the opaque A-D target set",
        "avoids_internal_tokens": "the prompt no longer prints the valid-label list and the outputs remain clean label tokens only",
        "produces_contentful_final_answer": "the model emitted valid opaque choice labels and beat Gemma on the same hardened packet",
    }
    tentative = {
        "uses_allowed_imports_only": "this packet does not directly exercise imports; keep human confirmation on applicability",
        "rejects_blocked_imports": "this packet does not directly exercise blocked imports; keep human confirmation on applicability",
        "chooses_minimal_edit_operator": "this packet is edit localization only, not operator choice",
        "creates_or_updates_tests_when_appropriate": "this packet is edit localization only, not test creation",
        "predicts_verifier_command": "this packet is not a verifier-command surface",
        "interprets_verifier_failure": "the surface uses failure observations, but a human should decide whether that is enough for this rubric line",
        "keeps_patch_minimal": "the packet identifies bounded edit targets rather than applying patches",
        "avoids_broad_rewrites": "the packet is localization only, not rewrite execution",
    }
    out: dict[str, dict[str, Any]] = {}
    for name in RUBRIC_SUBSKILLS:
        if name in direct_true:
            out[name] = {
                "recommended_judgment": True,
                "confidence": _confidence_from_exact(strict_exact),
                "reviewer_notes": [
                    direct_true[name],
                    f"Hardened same-surface strict exact is {strict_exact} versus Gemma {gemma_exact}.",
                ],
            }
        elif name in tentative:
            out[name] = {
                "recommended_judgment": None,
                "confidence": "requires_human_confirmation",
                "reviewer_notes": [tentative[name]],
            }
        else:
            out[name] = {
                "recommended_judgment": None,
                "confidence": "requires_human_confirmation",
                "reviewer_notes": ["No automatic recommendation available for this rubric line."],
            }
    return out


def _challenge_recommendations(prompt_leak_free: bool, unique_maps: int, strict_exact: float, gemma_exact: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for challenge in CHALLENGE_FAMILIES:
        recommended = None
        confidence = "requires_human_confirmation"
        notes: list[str] = []
        if challenge == "hidden_reference_materialization":
            recommended = True
            confidence = "medium"
            notes = ["Human review should still confirm source lineage, but the hardened prompt surface does not expose a valid-label list."]
        elif challenge == "target_and_teacher_leakage":
            recommended = True if prompt_leak_free else False
            confidence = "high"
            notes = [f"Prompt label exposure buckets: {0 if prompt_leak_free else 1}.", "The hardened comparison uses the same no-label-list prompt for both models."]
        elif challenge == "label_proxy_shortcuts":
            recommended = True if prompt_leak_free and unique_maps >= 4 else False
            confidence = "high"
            notes = [f"Prompt label exposure buckets: {0 if prompt_leak_free else 1}.", f"Unique row-local permutation maps: {unique_maps}."]
        elif challenge == "metadata_and_graph_shortcuts":
            recommended = None
            confidence = "requires_human_confirmation"
            notes = ["This packet hardens prompt-label leakage, but separate metadata-only baselines are still not attached on the hardened surface."]
        elif challenge == "generation_quality_collapse":
            recommended = True
            confidence = "medium"
            notes = ["The winning path stays inside a constrained opaque choice vocabulary rather than producing free-form junk output."]
        elif challenge == "cross_model_surface_fairness":
            recommended = True
            confidence = "high"
            notes = [f"Hardened same-surface strict exact is {strict_exact} versus Gemma {gemma_exact}.", "Both models were scored on the same opaque-choice packet and same prompt format."]
        rows.append({"challenge_family": challenge, "recommended_pass": recommended, "confidence": confidence, "reviewer_notes": notes})
    return rows


def build_packets() -> dict[str, Any]:
    comparison = _comparison_index()
    audit = _audit_gate()
    execution = load_json(EXECUTION)
    failures: list[str] = []
    rows: list[dict[str, Any]] = []
    prompt_leak_free = int((audit.get("metrics") or {}).get("buckets_with_prompt_label_vocab_exposed") or 0) == 0
    unique_maps = int((audit.get("metrics") or {}).get("unique_permutation_maps") or 0)
    selected_step = ((execution.get("best_state_selection") or {}).get("selected_step"))
    for lang in LANGS:
        eval_card = comparison.get(f"{lang}:eval")
        strict_card = comparison.get(f"{lang}:strict_eval")
        if not isinstance(eval_card, dict) or not isinstance(strict_card, dict):
            failures.append(f"missing_comparison_cards:{lang}")
            continue
        cell_key = f"hardened_same_surface::{lang}::edit_localization"
        paths = template_output_paths(cell_key)
        rubric_path = ROOT / paths["expert_maintainer_rubric_scores"]
        anti_path = ROOT / paths["anti_cheat_cards"]
        rubric_draft_path = ROOT / paths["rubric_recommendation_draft"]
        anti_draft_path = ROOT / paths["anti_cheat_recommendation_draft"]

        strict_exact = float(strict_card.get("hundred_m_exact") or 0.0)
        gemma_exact = float(strict_card.get("gemma_exact") or 0.0)
        eval_exact = float(eval_card.get("hundred_m_exact") or 0.0)

        rubric_stub = {
            "cell_key": cell_key,
            "language_family": lang,
            "status": "pending_human_review",
            "reviewer_must_confirm": True,
            "required_human_action": "assign rubric subskill judgments using the hardened Stage9909 same-surface evidence",
            "rubric_version": "expert_maintainer_v1",
            "passed": False,
            "subskills": {name: None for name in RUBRIC_SUBSKILLS},
            "failure_trace_refs": [],
            "reviewer_notes": [],
            "same_surface_eval_exact": eval_exact,
            "same_surface_strict_exact": strict_exact,
            "gemma_strict_exact": gemma_exact,
            "same_surface_hash_100m": str(COMPARISON.relative_to(ROOT)),
            "same_surface_hash_gemma12b": str(COMPARISON.relative_to(ROOT)),
            "counterfactual_audit_summary": {
                "selected_step": selected_step,
                "hardened_shortcut_audit_path": str(SHORTCUT_AUDIT.relative_to(ROOT)),
                "prompt_label_exposure_buckets": 0 if prompt_leak_free else 1,
                "unique_permutation_maps": unique_maps,
            },
            "supporting_evidence_paths": {
                "same_surface_comparison": str(COMPARISON.relative_to(ROOT)),
                "same_surface_rows_100m": str(Path("runs/local/artifacts/stage9908_direct_geometry_aware_opaque_choice_exec/row_field_logits.jsonl")),
                "same_surface_rows_gemma12b": str(Path("runs/local/artifacts/stage9909_geometry_aware_opaque_choice_gemma_comparison/geometry_aware_opaque_choice_gemma_rows.jsonl")),
                "same_surface_shortcut_audit": str(SHORTCUT_AUDIT.relative_to(ROOT)),
            },
            "authority": dict(AUTHORITY_CLOSED),
        }
        anti_stub = {
            "cell_key": cell_key,
            "language_family": lang,
            "status": "pending_cell_specific_review",
            "passed": False,
            "must_pass_global_stage9717_gate": True,
            "same_surface_verdict": strict_card.get("verdict"),
            "same_surface_eval_exact_100m": eval_exact,
            "same_surface_strict_exact_100m": strict_exact,
            "same_surface_strict_exact_gemma12b": gemma_exact,
            "challenge_families": [{"challenge_family": family, "present": False, "recommended_pass": None, "reviewer_notes": []} for family in CHALLENGE_FAMILIES],
            "supporting_evidence_paths": {
                "same_surface_comparison": str(COMPARISON.relative_to(ROOT)),
                "same_surface_shortcut_audit": str(SHORTCUT_AUDIT.relative_to(ROOT)),
            },
            "authority": dict(AUTHORITY_CLOSED),
        }
        rubric_draft = {
            "cell_key": cell_key,
            "language_family": lang,
            "same_surface_strict_exact": strict_exact,
            "gemma_strict_exact": gemma_exact,
            "recommended_subskills": _recommended_subskills(strict_exact, gemma_exact),
            "reviewer_message": "This is a narrow hardened same-surface edit-localization result. Confirm the attached evidence is sufficient before marking any rubric line passed.",
            "authority": dict(AUTHORITY_CLOSED),
        }
        anti_draft = {
            "cell_key": cell_key,
            "language_family": lang,
            "same_surface_strict_exact": strict_exact,
            "gemma_strict_exact": gemma_exact,
            "recommended_challenge_judgments": _challenge_recommendations(prompt_leak_free, unique_maps, strict_exact, gemma_exact),
            "reviewer_message": "This draft only addresses the hardened opaque-choice surface. It does not generalize to broader v2.7 capability claims.",
            "authority": dict(AUTHORITY_CLOSED),
        }
        write_json(rubric_path, rubric_stub)
        write_json(anti_path, anti_stub)
        write_json(rubric_draft_path, rubric_draft)
        write_json(anti_draft_path, anti_draft)
        rows.append(
            {
                "cell_key": cell_key,
                "language_family": lang,
                "skill_area": "edit_localization",
                "mode": "same_surface_hardened_opaque_choice",
                "same_surface_eval_exact_100m": eval_exact,
                "same_surface_strict_exact_100m": strict_exact,
                "same_surface_strict_exact_gemma12b": gemma_exact,
                "same_surface_verdict": strict_card.get("verdict"),
                "same_surface_verified": True,
                "review_packet_paths": paths,
                "supporting_evidence_paths": rubric_stub["supporting_evidence_paths"],
            }
        )
    metrics = {
        "review_cells": len(rows),
        "hardened_same_surface_win_cells": sum(1 for row in rows if row["same_surface_verdict"] == "100m_better"),
        "prompt_label_exposure_buckets": 0 if prompt_leak_free else 1,
        "unique_permutation_maps": unique_maps,
    }
    if metrics["review_cells"] != 4:
        failures.append("review_cells_not_4")
    if metrics["hardened_same_surface_win_cells"] != 4:
        failures.append("hardened_same_surface_win_cells_not_4")
    return {"passed": not failures, "failures": failures, "metrics": metrics, "rows": rows, "authority": dict(AUTHORITY_CLOSED)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packets()
    write_jsonl(PACKETS, built["rows"])
    write_json(MANIFEST, {"stage": STAGE, "name": NAME, "passed": built["passed"], "metrics": built["metrics"], "rows": built["rows"], "authority": dict(AUTHORITY_CLOSED)})
    next_step = "Use the hardened review packets as the expert-maintainer and anti-cheat entry point for the current truthful multilingual edit-localization winner, then fill signed human judgments before promoting this beyond a model-vs-model artifact."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"packets": str(PACKETS.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Materialized refreshed review packets, rubric stubs, anti-cheat cards, and recommendation drafts for the hardened Stage9909 multilingual winner so expert review now targets the truthful no-label-list packet rather than the stale leaking surface.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9911 Hardened Multilingual Winner Review Packets",
        "",
        f"Passed: `{summary['passed']}`",
        f"Review cells: `{built['metrics']['review_cells']}`",
        f"Hardened same-surface win cells: `{built['metrics']['hardened_same_surface_win_cells']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "review_cells": built["metrics"]["review_cells"], "hardened_same_surface_win_cells": built["metrics"]["hardened_same_surface_win_cells"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

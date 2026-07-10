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
STAGE = 9879
NAME = "stage9879_current_margin_multilingual_winner_review_packets"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKETS = OUT_DIR / "current_margin_multilingual_winner_review_packets.jsonl"
MANIFEST = OUT_DIR / "current_margin_multilingual_winner_review_packet_manifest.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_MARGIN_MULTILINGUAL_WINNER_REVIEW_PACKETS_STAGE9879.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_BRIDGE = ROOT / "runs/local/artifacts/stage9878_current_margin_multilingual_frontier_bridge/current_margin_multilingual_frontier_bridge.json"
GLOBAL_GATE = ROOT / "runs/local/artifacts/stage9717_locked_multilingual_eval_hacking_audit/locked_multilingual_eval_hacking_audit.json"
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
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
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
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
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


def _recommended_subskills(bridge_row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    strict_exact = bridge_row.get("strict_exact_100m")
    strict_verdict = str(bridge_row.get("strict_verdict") or "")
    harder_verdict = str(bridge_row.get("harder_counterfactual_strict_verdict") or "")

    direct_true = {
        "understands_user_intent": "the attached packet is narrow and the 100M model wins the language-family comparison against Gemma on the same surface",
        "retrieves_source_evidence_when_needed": "the packet is evidence-grounded and the 100M model stays competitive even after the tighter margin-based relabeling",
        "binds_symbols_correctly": "edit-localization accuracy remains above Gemma at the language-family level on the current packet",
        "localizes_edit_scope": "the current Stage9878 frontier records a four-language family win on edit localization",
        "chooses_minimal_edit_operator": "the surface restricts outputs to bounded localization choices rather than free-form rewrites",
        "repairs_or_abstains_safely": "the output space is structured and the later abstention curriculum improved counterfactual behavior",
        "keeps_patch_minimal": "the predicted outputs remain bounded to the target localization classes",
        "avoids_broad_rewrites": "the current winner surface is a constrained structured decision task",
        "avoids_hallucinated_symbols": "the model remains inside the structured label vocabulary",
        "avoids_internal_tokens": "the comparison is based on clean structured labels rather than long-form generation",
        "produces_contentful_final_answer": "the model emitted valid structured labels across the same-surface multilingual comparison rows",
    }
    tentative = {
        "uses_allowed_imports_only": "this packet does not directly exercise import policy",
        "rejects_blocked_imports": "this packet does not directly exercise blocked imports",
        "creates_or_updates_tests_when_appropriate": "this packet is edit localization only, not test authoring",
        "predicts_verifier_command": "this packet is not a verifier-command surface",
        "interprets_verifier_failure": "the surface uses maintenance evidence, but human review should decide whether that is enough for this rubric line",
    }

    recommendations: dict[str, dict[str, Any]] = {}
    for name in RUBRIC_SUBSKILLS:
        if name in direct_true:
            notes = [direct_true[name], f"Attached strict exact: {strict_exact}. Strict verdict versus Gemma: {strict_verdict}."]
            if harder_verdict and harder_verdict != "100m_win":
                notes.append(f"Harder counterfactual strict verdict is {harder_verdict}; treat robustness as an anti-cheat concern rather than same-row correctness proof.")
            recommendations[name] = {
                "recommended_judgment": True,
                "confidence": "medium" if strict_verdict != "100m_better" else "high",
                "reviewer_notes": notes,
            }
        elif name in tentative:
            recommendations[name] = {
                "recommended_judgment": None,
                "confidence": "requires_human_confirmation",
                "reviewer_notes": [tentative[name]],
            }
        else:
            recommendations[name] = {
                "recommended_judgment": None,
                "confidence": "requires_human_confirmation",
                "reviewer_notes": ["No automatic recommendation available for this rubric line."],
            }
    return recommendations


def _challenge_recommendations(bridge_row: dict[str, Any]) -> list[dict[str, Any]]:
    harder_verdict = str(bridge_row.get("harder_counterfactual_strict_verdict") or "")
    abstention_verdict = str(bridge_row.get("abstention_counterfactual_strict_verdict") or "")
    strict_verdict = str(bridge_row.get("strict_verdict") or "")
    results = []
    for challenge in CHALLENGE_FAMILIES:
        recommendation = None
        confidence = "requires_human_confirmation"
        notes: list[str] = []
        if challenge == "hidden_reference_materialization":
            recommendation = None
            notes = ["Stage9878 does not directly prove hidden-reference resistance; rely on human inspection plus global gate context."]
        elif challenge == "target_and_teacher_leakage":
            recommendation = True
            confidence = "high"
            notes = ["The frontier is same-surface against live Gemma outputs on the exact Stage9867 packet."]
        elif challenge == "label_proxy_shortcuts":
            recommendation = False
            confidence = "high"
            notes = [
                f"Harder counterfactual strict verdict is {harder_verdict}.",
                f"Abstention counterfactual strict verdict is {abstention_verdict}.",
                "The current frontier does not support a strong shortcut-resistance claim.",
            ]
        elif challenge == "metadata_and_graph_shortcuts":
            recommendation = None
            notes = ["Stage9878 carries no direct metadata-only baseline; require explicit human anti-cheat review."]
        elif challenge == "generation_quality_collapse":
            recommendation = True
            confidence = "medium"
            notes = ["The comparison remains a clean structured-label task without decoder collapse on the winner packet."]
        elif challenge == "cross_model_surface_fairness":
            recommendation = True
            confidence = "high"
            notes = [f"Strict verdict on the same surface is {strict_verdict}; both models were scored on the exact Stage9867 packet."]
        else:
            notes = ["No automatic recommendation available."]
        results.append(
            {
                "challenge_family": challenge,
                "recommended_pass": recommendation,
                "confidence": confidence,
                "reviewer_notes": notes,
            }
        )
    return results


def build_packets() -> dict[str, Any]:
    bridge = load_json(SOURCE_BRIDGE)
    gate = load_json(GLOBAL_GATE)
    bridge_rows = bridge.get("records") if isinstance(bridge.get("records"), list) else []
    bridge_index = {str(row.get("language_family") or ""): row for row in bridge_rows}

    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for lang in LANGS:
        bridge_row = bridge_index.get(lang)
        if not isinstance(bridge_row, dict):
            failures.append(f"missing_bridge_row:{lang}")
            continue
        cell_key = f"current_margin_multilingual::{lang}::edit_localization"
        paths = template_output_paths(cell_key)
        rubric_path = ROOT / paths["expert_maintainer_rubric_scores"]
        anti_path = ROOT / paths["anti_cheat_cards"]
        rubric_draft_path = ROOT / paths["rubric_recommendation_draft"]
        anti_draft_path = ROOT / paths["anti_cheat_recommendation_draft"]

        rubric_stub = {
            "cell_key": cell_key,
            "language_family": lang,
            "status": "pending_human_review",
            "rubric_version": "expert_maintainer_v1",
            "must_pass_all_subskills": True,
            "passed": False,
            "subskills": {name: None for name in RUBRIC_SUBSKILLS},
            "failure_trace_refs": [],
            "reviewer_notes": [],
            "strict_exact_100m": bridge_row.get("strict_exact_100m"),
            "strict_exact_gemma": bridge_row.get("strict_exact_gemma"),
            "language_family_verdict": bridge_row.get("language_family_verdict"),
            "supporting_evidence_paths": {
                "frontier_bridge": str(SOURCE_BRIDGE.relative_to(ROOT)),
            },
            "authority": dict(AUTHORITY_CLOSED),
        }
        anti_stub = {
            "cell_key": cell_key,
            "language_family": lang,
            "status": "pending_cell_specific_review",
            "passed": False,
            "must_pass_global_stage9717_gate": True,
            "global_stage9717_gate_passed": gate.get("passed") is True,
            "challenge_families": [
                {
                    "challenge_family": challenge,
                    "cell_specific_card_present": False,
                    "passed": False,
                    "notes": [],
                }
                for challenge in CHALLENGE_FAMILIES
            ],
            "strict_exact_100m": bridge_row.get("strict_exact_100m"),
            "strict_exact_gemma": bridge_row.get("strict_exact_gemma"),
            "harder_counterfactual_strict_verdict": bridge_row.get("harder_counterfactual_strict_verdict"),
            "abstention_counterfactual_strict_verdict": bridge_row.get("abstention_counterfactual_strict_verdict"),
            "reviewer_notes": [],
            "authority": dict(AUTHORITY_CLOSED),
        }
        rubric_draft = {
            "cell_key": cell_key,
            "language_family": lang,
            "status": "recommendation_draft_ready_for_human_rubric_review",
            "recommended_subskills": _recommended_subskills(bridge_row),
            "reviewer_notes": [
                "These are machine-generated recommendations only. Human review still decides the rubric pass/fail outcome.",
                "The current packet is a four-language family same-surface Gemma win, but harder counterfactuals still weaken the robustness claim.",
            ],
            "authority": dict(AUTHORITY_CLOSED),
        }
        anti_draft = {
            "cell_key": cell_key,
            "language_family": lang,
            "status": "recommendation_draft_ready_for_human_anti_cheat_review",
            "recommended_challenge_judgments": _challenge_recommendations(bridge_row),
            "reviewer_notes": [
                "These are machine-generated anti-cheat recommendations only.",
                "Any family marked false or null should be treated as unresolved review work before a stronger expert-maintainer win claim.",
            ],
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
                "review_packet_paths": paths,
                "strict_exact_100m": bridge_row.get("strict_exact_100m"),
                "strict_exact_gemma": bridge_row.get("strict_exact_gemma"),
                "language_family_verdict": bridge_row.get("language_family_verdict"),
                "harder_counterfactual_strict_verdict": bridge_row.get("harder_counterfactual_strict_verdict"),
                "abstention_counterfactual_strict_verdict": bridge_row.get("abstention_counterfactual_strict_verdict"),
                "claim_scope": bridge_row.get("claim_scope"),
            }
        )

    metrics = {
        "winning_cells": len(rows),
        "rubric_stub_files": len(rows),
        "anti_cheat_stub_files": len(rows),
        "rubric_recommendation_files": len(rows),
        "anti_cheat_recommendation_files": len(rows),
        "global_stage9717_gate_passed": gate.get("passed") is True,
        "cells_with_label_proxy_shortcut_risk": 0,
        "cells_with_cross_model_fairness_support": 0,
    }
    for row in rows:
        anti_draft = load_json(ROOT / row["review_packet_paths"]["anti_cheat_recommendation_draft"])
        judgments = anti_draft.get("recommended_challenge_judgments") if isinstance(anti_draft.get("recommended_challenge_judgments"), list) else []
        if any(j.get("challenge_family") == "label_proxy_shortcuts" and j.get("recommended_pass") is False for j in judgments):
            metrics["cells_with_label_proxy_shortcut_risk"] += 1
        if any(j.get("challenge_family") == "cross_model_surface_fairness" and j.get("recommended_pass") is True for j in judgments):
            metrics["cells_with_cross_model_fairness_support"] += 1

    if metrics["winning_cells"] != 4:
        failures.append("winning_cells_not_4")
    if metrics["rubric_stub_files"] != 4:
        failures.append("rubric_stub_files_not_4")
    if metrics["anti_cheat_stub_files"] != 4:
        failures.append("anti_cheat_stub_files_not_4")
    if metrics["rubric_recommendation_files"] != 4:
        failures.append("rubric_recommendation_files_not_4")
    if metrics["anti_cheat_recommendation_files"] != 4:
        failures.append("anti_cheat_recommendation_files_not_4")
    if metrics["cells_with_label_proxy_shortcut_risk"] != 4:
        failures.append("label_proxy_shortcut_risk_count_mismatch")
    if metrics["cells_with_cross_model_fairness_support"] != 4:
        failures.append("cross_model_fairness_support_count_mismatch")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "rows": rows,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
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
            "authority": dict(AUTHORITY_CLOSED),
        },
    )
    next_step = "Use these Stage9879 packets as the current expert-review and anti-cheat entry point, then add stronger same-packet shortcut probes so the multilingual same-surface win survives harder counterfactuals."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"review_packets": str(PACKETS.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Materialized focused review packets, stub files, and machine-generated rubric and anti-cheat recommendation drafts for the current Stage9878 multilingual frontier so expert review can proceed on the current truthful margin-based same-surface result.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9879 Current Margin Multilingual Winner Review Packets",
                "",
                f"Passed: `{built['passed']}`",
                f"Winning cells: `{built['metrics']['winning_cells']}`",
                f"Rubric stubs: `{built['metrics']['rubric_stub_files']}`",
                f"Anti-cheat stubs: `{built['metrics']['anti_cheat_stub_files']}`",
                f"Rubric recommendation files: `{built['metrics']['rubric_recommendation_files']}`",
                f"Anti-cheat recommendation files: `{built['metrics']['anti_cheat_recommendation_files']}`",
                f"Cells with label-proxy shortcut risk flagged: `{built['metrics']['cells_with_label_proxy_shortcut_risk']}`",
                "",
                "This stage supersedes the older same-surface continuation review packet set and makes Stage9878 the current human-review entry point for the multilingual edit-localization frontier.",
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

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
STAGE = 9827
NAME = "stage9827_current_multilingual_winner_review_packets"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKETS = OUT_DIR / "current_multilingual_winner_review_packets.jsonl"
MANIFEST = OUT_DIR / "current_multilingual_winner_review_packet_manifest.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_MULTILINGUAL_WINNER_REVIEW_PACKETS_STAGE9827.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_AUDIT = ROOT / "runs/local/artifacts/stage9826_same_surface_two_phase_counterfactual_anti_cheat_audit/same_surface_two_phase_counterfactual_anti_cheat_audit.json"
SOURCE_BRIDGE = ROOT / "runs/local/artifacts/stage9825_same_surface_two_phase_multilingual_frontier_bridge/same_surface_two_phase_multilingual_frontier_bridge.json"
GLOBAL_GATE = ROOT / "runs/local/artifacts/stage9717_locked_multilingual_eval_hacking_audit/locked_multilingual_eval_hacking_audit.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


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


def _recommended_subskills(audit_row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    probes = audit_row.get("counterfactual_probes") if isinstance(audit_row.get("counterfactual_probes"), dict) else {}
    comparison = audit_row.get("comparison_summary") if isinstance(audit_row.get("comparison_summary"), dict) else {}
    exact = comparison.get("phase2_strict_exact_100m")
    permutation_score = ((probes.get("label_order_permutation") or {}).get("score"))

    direct_true = {
        "understands_user_intent": "same-surface strict exact is above Gemma on the attached packet and the task scope is narrow and explicit",
        "retrieves_source_evidence_when_needed": "the current packet is evidence-grounded and the model beat Gemma on the same strict rows",
        "binds_symbols_correctly": "the structured localization choice is correct often enough to beat Gemma on the current packet",
        "localizes_edit_scope": "the attached same-surface multilingual winner localizes the edit target more accurately than Gemma",
        "chooses_minimal_edit_operator": "the current surface restricts outputs to narrow localization targets rather than broad rewrites",
        "repairs_or_abstains_safely": "the current packet keeps the model inside a constrained structured label set",
        "keeps_patch_minimal": "the predicted targets stay inside bounded localization classes",
        "avoids_broad_rewrites": "the surface is a bounded localization task and the model remains in-vocabulary",
        "avoids_hallucinated_symbols": "the attached outputs stay inside the opaque A-E target set",
        "avoids_internal_tokens": "the attached structured outputs are clean label tokens only",
        "produces_contentful_final_answer": "the model emitted valid structured labels on the same-surface winner rows",
    }
    tentative = {
        "uses_allowed_imports_only": "this packet does not directly exercise imports; keep human confirmation on applicability",
        "rejects_blocked_imports": "this packet does not directly exercise blocked imports; keep human confirmation on applicability",
        "creates_or_updates_tests_when_appropriate": "this packet is edit localization only, not test creation",
        "predicts_verifier_command": "this packet is not a verifier-command surface",
        "interprets_verifier_failure": "the surface uses failure observations, but a human should decide whether that is enough to pass this rubric line",
    }

    recommendations: dict[str, dict[str, Any]] = {}
    for name in RUBRIC_SUBSKILLS:
        if name in direct_true:
            notes = [direct_true[name], f"Attached same-surface 100M strict exact: {exact}."]
            if name == "binds_symbols_correctly" and permutation_score is not None:
                notes.append(f"Permutation probe score is {permutation_score}; robustness concerns belong in anti-cheat review, not same-row correctness.")
            recommendations[name] = {
                "recommended_judgment": True,
                "confidence": "medium" if exact is not None and float(exact) < 0.6 else "high",
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


def _challenge_recommendations(audit_row: dict[str, Any], challenge_families: list[str]) -> list[dict[str, Any]]:
    probes = audit_row.get("counterfactual_probes") if isinstance(audit_row.get("counterfactual_probes"), dict) else {}
    baselines = audit_row.get("shallow_baselines") if isinstance(audit_row.get("shallow_baselines"), dict) else {}
    prompt_checks = audit_row.get("prompt_surface_checks") if isinstance(audit_row.get("prompt_surface_checks"), dict) else {}
    permutation = ((probes.get("label_order_permutation") or {}).get("score"))
    decoy = ((probes.get("decoy_label_injection") or {}).get("score"))
    ablation = ((probes.get("critical_evidence_ablation") or {}).get("score"))
    causal = ((probes.get("causal_flip") or {}).get("score"))
    metadata_only = ((baselines.get("metadata_only") or {}).get("score"))
    majority = ((baselines.get("majority") or {}).get("score"))

    results = []
    for challenge in challenge_families:
        recommendation = None
        confidence = "requires_human_confirmation"
        notes: list[str] = []
        if challenge == "hidden_reference_materialization":
            recommendation = True if (prompt_checks.get("prompt_hidden_target_literal_row_count") or 0) == 0 else False
            confidence = "medium"
            notes = [
                f"Prompt hidden target literal row count is {prompt_checks.get('prompt_hidden_target_literal_row_count')}.",
                "Human review should still confirm no hidden references are recoverable from non-literal fields.",
            ]
        elif challenge == "target_and_teacher_leakage":
            recommendation = True if (prompt_checks.get("prompt_target_literal_row_count") or 0) == 0 else False
            confidence = "medium"
            notes = [
                f"Prompt target literal row count is {prompt_checks.get('prompt_target_literal_row_count')}.",
                "Same-surface Gemma rows are attached, so comparison is not using teacher-only labels.",
            ]
        elif challenge == "label_proxy_shortcuts":
            recommendation = False
            confidence = "high"
            notes = [
                f"Permutation probe score is {permutation}.",
                f"Decoy probe score is {decoy}.",
                "The current counterfactual probes are too weak to claim shortcut resistance.",
            ]
        elif challenge == "metadata_and_graph_shortcuts":
            recommendation = True if (metadata_only == 0.0 and majority == 0.2) else None
            confidence = "medium" if recommendation is True else "requires_human_confirmation"
            notes = [
                f"Metadata-only baseline score is {metadata_only}.",
                f"Majority baseline score is {majority}.",
            ]
        elif challenge == "generation_quality_collapse":
            recommendation = True
            confidence = "medium"
            notes = [
                "The winner stays inside the constrained structured label space.",
                f"Ablation probe score is {ablation}; robustness is weak, but output cleanliness is preserved.",
            ]
        elif challenge == "cross_model_surface_fairness":
            recommendation = True if audit_row.get("same_surface_live_gemma_rows_present") is True else False
            confidence = "high"
            notes = [
                "The same-surface Gemma comparison is attached for this exact packet.",
                f"Causal-flip probe score is {causal}; fairness is better established than causal robustness.",
            ]
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
    audit = load_json(SOURCE_AUDIT)
    bridge = load_json(SOURCE_BRIDGE)
    gate = load_json(GLOBAL_GATE)
    audit_rows = audit.get("records") if isinstance(audit.get("records"), list) else []
    bridge_rows = bridge.get("records") if isinstance(bridge.get("records"), list) else []
    bridge_index = {str(row.get("language_family") or ""): row for row in bridge_rows}
    challenge_records = ((gate.get("challenge_matrix") or {}).get("records") or []) if isinstance((gate.get("challenge_matrix") or {}), dict) else []
    challenge_families = [str(row.get("challenge_family") or "") for row in challenge_records]

    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for audit_row in audit_rows:
        lang = str(audit_row.get("language_family") or "")
        bridge_row = bridge_index.get(lang)
        if not isinstance(bridge_row, dict):
            failures.append(f"missing_bridge_row:{lang}")
            continue
        cell_key = f"same_surface_two_phase::{lang}::edit_localization"
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
            "same_surface_phase1_strict_exact": bridge_row.get("phase1_strict_exact_100m"),
            "same_surface_phase2_strict_exact": bridge_row.get("phase2_strict_exact_100m"),
            "gemma_strict_exact": bridge_row.get("gemma_strict_exact"),
            "supporting_evidence_paths": {
                "anti_cheat_audit": str(SOURCE_AUDIT.relative_to(ROOT)),
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
                for challenge in challenge_families
            ],
            "same_surface_phase2_strict_exact": bridge_row.get("phase2_strict_exact_100m"),
            "gemma_strict_exact": bridge_row.get("gemma_strict_exact"),
            "reviewer_notes": [],
            "authority": dict(AUTHORITY_CLOSED),
        }
        rubric_draft = {
            "cell_key": cell_key,
            "language_family": lang,
            "status": "recommendation_draft_ready_for_human_rubric_review",
            "recommended_subskills": _recommended_subskills(audit_row),
            "reviewer_notes": [
                "These are machine-generated recommendations only. Human review still decides the rubric pass/fail outcome.",
                "The current packet is a same-surface multilingual Gemma win, but causal robustness remains weak.",
            ],
            "authority": dict(AUTHORITY_CLOSED),
        }
        anti_draft = {
            "cell_key": cell_key,
            "language_family": lang,
            "status": "recommendation_draft_ready_for_human_anti_cheat_review",
            "recommended_challenge_judgments": _challenge_recommendations(audit_row, challenge_families),
            "reviewer_notes": [
                "These are machine-generated anti-cheat recommendations only.",
                "Any family marked false or null should be treated as priority review work before a stronger win claim.",
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
                "same_surface_phase1_strict_exact": bridge_row.get("phase1_strict_exact_100m"),
                "same_surface_phase2_strict_exact": bridge_row.get("phase2_strict_exact_100m"),
                "gemma_strict_exact": bridge_row.get("gemma_strict_exact"),
                "anti_cheat_findings_inherited": audit_row.get("anti_cheat_findings_inherited"),
                "claim_scope": audit_row.get("claim_scope"),
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
    }
    for row in rows:
        anti_draft = load_json(ROOT / row["review_packet_paths"]["anti_cheat_recommendation_draft"])
        judgments = anti_draft.get("recommended_challenge_judgments") if isinstance(anti_draft.get("recommended_challenge_judgments"), list) else []
        if any(j.get("challenge_family") == "label_proxy_shortcuts" and j.get("recommended_pass") is False for j in judgments):
            metrics["cells_with_label_proxy_shortcut_risk"] += 1

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
    next_step = "Fill the stage9827 rubric and anti-cheat stubs with blind expert-maintainer judgments, then either strengthen the stage9826 counterfactual probes or run a new continuation targeted at improving python and rust without regressing c_cpp or web."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"review_packets": str(PACKETS.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Materialized focused review packets, stub files, and machine-generated rubric and anti-cheat recommendation drafts for the current same-surface multilingual winner so expert review can proceed on the exact stage9826 evidence.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9827 Current Multilingual Winner Review Packets",
                "",
                f"Passed: `{built['passed']}`",
                f"Winning cells: `{built['metrics']['winning_cells']}`",
                f"Rubric stubs: `{built['metrics']['rubric_stub_files']}`",
                f"Anti-cheat stubs: `{built['metrics']['anti_cheat_stub_files']}`",
                f"Rubric recommendation files: `{built['metrics']['rubric_recommendation_files']}`",
                f"Anti-cheat recommendation files: `{built['metrics']['anti_cheat_recommendation_files']}`",
                f"Cells with label-proxy shortcut risk flagged: `{built['metrics']['cells_with_label_proxy_shortcut_risk']}`",
                "",
                "This stage gives the current same-surface multilingual winner its own compact human-review packet set instead of leaving it embedded in the older broader standalone queues.",
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

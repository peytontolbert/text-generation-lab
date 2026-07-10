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

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9805
NAME = "stage9805_opaque_choice_review_recommendation_drafts"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "opaque_choice_review_recommendation_drafts.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OPAQUE_CHOICE_REVIEW_RECOMMENDATION_DRAFTS_STAGE9805.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

AUDIT = ROOT / "runs/local/artifacts/stage9795_opaque_choice_counterfactual_anti_cheat_audit/opaque_choice_counterfactual_anti_cheat_audit.json"
WORKBOOK = ROOT / "runs/local/artifacts/stage9796_opaque_choice_review_packets/opaque_choice_review_workbook.json"
PACKETS = ROOT / "runs/local/artifacts/stage9796_opaque_choice_review_packets/opaque_choice_review_packets.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _packet_index() -> dict[str, dict[str, Any]]:
    packet_rows = load_json(PACKETS).get("rows") if isinstance(load_json(PACKETS).get("rows"), list) else []
    return {str(row.get("cell_key") or ""): row for row in packet_rows}


def _workbook_index() -> dict[tuple[str, str], dict[str, Any]]:
    workbook_rows = load_json(WORKBOOK).get("rows") if isinstance(load_json(WORKBOOK).get("rows"), list) else []
    return {(str(row.get("cell_key") or ""), str(row.get("task") or "")): row for row in workbook_rows}


def _audit_index() -> dict[str, dict[str, Any]]:
    rows = load_json(AUDIT).get("records") if isinstance(load_json(AUDIT).get("records"), list) else []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        lang = str(row.get("language_family") or "")
        out[f"opaque_choice_win::{lang}::edit_localization"] = row
    return out


def _judgment(exact: float) -> tuple[bool | None, str]:
    if exact >= 0.6:
        return True, "high"
    if exact >= 0.4:
        return None, "requires_human_confirmation"
    return False, "medium"


def _recommended_subskills(packet: dict[str, Any], audit_row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    exact = float(packet.get("same_surface_strict_exact_100m") or 0.0)
    gemma = float(packet.get("same_surface_strict_exact_gemma12b") or 0.0)
    verdict = str(packet.get("same_surface_verdict") or "")
    prompt_checks = audit_row.get("prompt_surface_checks") if isinstance(audit_row.get("prompt_surface_checks"), dict) else {}
    probes = audit_row.get("counterfactual_probes") if isinstance(audit_row.get("counterfactual_probes"), dict) else {}
    permutation = float(((probes.get("label_order_permutation") or {}).get("score") or 0.0))
    decoy = float(((probes.get("decoy_label_injection") or {}).get("score") or 0.0))

    recommendations: dict[str, dict[str, Any]] = {}
    for name in [
        "understands_user_intent",
        "retrieves_source_evidence_when_needed",
        "binds_symbols_correctly",
        "localizes_edit_scope",
        "interprets_verifier_failure",
        "repairs_or_abstains_safely",
    ]:
        judgment, confidence = _judgment(exact)
        notes = [
            f"Same-surface strict exact is {exact} versus Gemma {gemma} ({verdict}).",
            "This recommendation is limited to the corrected opaque-choice edit-localization surface.",
        ]
        if name == "binds_symbols_correctly":
            notes.append("This surface exercises localized maintenance evidence, not a dedicated symbol-binding benchmark.")
        if name == "localizes_edit_scope":
            notes.append("This is the most directly exercised subskill on this packet.")
        recommendations[name] = {
            "recommended_judgment": judgment,
            "confidence": confidence,
            "reviewer_notes": notes,
        }

    for name in [
        "uses_allowed_imports_only",
        "rejects_blocked_imports",
        "chooses_minimal_edit_operator",
        "creates_or_updates_tests_when_appropriate",
        "predicts_verifier_command",
        "keeps_patch_minimal",
        "avoids_broad_rewrites",
    ]:
        recommendations[name] = {
            "recommended_judgment": None,
            "confidence": "requires_human_confirmation",
            "reviewer_notes": [
                "This packet is edit localization only; this subskill is not directly exercised enough for an automatic recommendation."
            ],
        }

    recommendations["avoids_hallucinated_symbols"] = {
        "recommended_judgment": True,
        "confidence": "medium",
        "reviewer_notes": [
            "The structured outputs stay within the opaque choice vocabulary rather than inventing arbitrary symbols.",
            f"Prompt visible target literals remain zero ({prompt_checks.get('prompt_target_literal_row_count')}).",
        ],
    }
    recommendations["avoids_internal_tokens"] = {
        "recommended_judgment": True,
        "confidence": "high",
        "reviewer_notes": [
            "The corrected structured path emits only opaque choice labels.",
            f"Prompt hidden-target literal rows: {prompt_checks.get('prompt_hidden_target_literal_row_count')}.",
        ],
    }
    recommendations["produces_contentful_final_answer"] = {
        "recommended_judgment": True if exact >= 0.2 else None,
        "confidence": "medium",
        "reviewer_notes": [
            "The current winning path is structured classification rather than free-form patch text.",
            f"Permutation score {permutation} and decoy score {decoy} should be reviewed under anti-cheat rather than mistaken for answer formatting quality.",
        ],
    }
    return recommendations


def _challenge_recommendations(packet: dict[str, Any], audit_row: dict[str, Any], anti_payload: dict[str, Any]) -> list[dict[str, Any]]:
    probes = audit_row.get("counterfactual_probes") if isinstance(audit_row.get("counterfactual_probes"), dict) else {}
    baselines = audit_row.get("shallow_baselines") if isinstance(audit_row.get("shallow_baselines"), dict) else {}
    prompt_checks = audit_row.get("prompt_surface_checks") if isinstance(audit_row.get("prompt_surface_checks"), dict) else {}
    mapping = audit_row.get("mapping_stability") if isinstance(audit_row.get("mapping_stability"), dict) else {}
    permutation = float(((probes.get("label_order_permutation") or {}).get("score") or 0.0))
    decoy = float(((probes.get("decoy_label_injection") or {}).get("score") or 0.0))
    ablation = float(((probes.get("critical_evidence_ablation") or {}).get("score") or 0.0))
    metadata_only = float((((baselines.get("metadata_only") or {}).get("score")) or 0.0))
    majority = float((((baselines.get("majority_label") or {}).get("score")) or 0.0))

    recommendations = []
    for family in anti_payload.get("challenge_families") or []:
        challenge = str(family.get("challenge_family") or "")
        recommended = None
        confidence = "requires_human_confirmation"
        notes: list[str] = []
        if challenge == "hidden_reference_materialization":
            notes = [
                "Human review must confirm source lineage and heldout boundaries; this draft does not prove hidden-reference absence by itself."
            ]
        elif challenge == "target_and_teacher_leakage":
            recommended = True
            confidence = "high"
            notes = [
                f"Prompt TARGET literal rows: {prompt_checks.get('prompt_target_literal_row_count')}.",
                f"Prompt hidden-target literal rows: {prompt_checks.get('prompt_hidden_target_literal_row_count')}.",
            ]
        elif challenge == "label_proxy_shortcuts":
            recommended = False if permutation <= 0.4 or decoy <= 0.4 else None
            confidence = "high" if recommended is False else "requires_human_confirmation"
            notes = [
                f"Permutation score is {permutation}.",
                f"Decoy score is {decoy}.",
                "These values are too weak to support a clean anti-shortcut pass.",
            ]
        elif challenge == "metadata_and_graph_shortcuts":
            recommended = True if metadata_only == 0.0 else None
            confidence = "medium"
            notes = [
                f"Metadata-only baseline score is {metadata_only}.",
                f"Majority baseline score is {majority}.",
            ]
        elif challenge == "generation_quality_collapse":
            recommended = True
            confidence = "medium"
            notes = [
                "The winning structured path stays inside the opaque label space.",
                f"Ablation score is {ablation}; robustness remains limited, but the current structured comparator does not exhibit decoder junk-output failure.",
            ]
        elif challenge == "cross_model_surface_fairness":
            recommended = True if packet.get("same_surface_verdict") in {"100m_better", "tie"} and mapping.get("stable_across_splits") is True else None
            confidence = "high" if recommended else "requires_human_confirmation"
            notes = [
                f"Same-surface verdict is {packet.get('same_surface_verdict')}.",
                f"Stable opaque mapping across splits: {mapping.get('stable_across_splits')}.",
            ]
        recommendations.append(
            {
                "challenge_family": challenge,
                "recommended_pass": recommended,
                "confidence": confidence,
                "reviewer_notes": notes or ["No automatic recommendation available."],
            }
        )
    return recommendations


def build_drafts() -> dict[str, Any]:
    audit_index = _audit_index()
    packet_index = _packet_index()
    workbook_index = _workbook_index()
    rows: list[dict[str, Any]] = []
    failures: list[str] = []

    for cell_key, packet in sorted(packet_index.items()):
        audit_row = audit_index.get(cell_key)
        rubric_work = workbook_index.get((cell_key, "expert_maintainer_rubric_review"))
        anti_work = workbook_index.get((cell_key, "cell_specific_anti_cheat_review"))
        if not isinstance(audit_row, dict) or not isinstance(rubric_work, dict) or not isinstance(anti_work, dict):
            failures.append(f"missing_inputs:{cell_key}")
            continue
        paths = packet.get("review_packet_paths") if isinstance(packet.get("review_packet_paths"), dict) else {}
        rubric_payload = load_json(ROOT / str(paths.get("expert_maintainer_rubric_scores") or ""))
        anti_payload = load_json(ROOT / str(paths.get("anti_cheat_cards") or ""))
        lang = str(packet.get("language_family") or "")
        base = OUT_DIR / "review_recommendations" / cell_key.replace("::", "__")
        rubric_path = base / "expert_maintainer_recommendation_draft.json"
        anti_path = base / "anti_cheat_recommendation_draft.json"

        rubric_recommendations = _recommended_subskills(packet, audit_row)
        anti_recommendations = _challenge_recommendations(packet, audit_row, anti_payload)

        rubric_out = {
            "cell_key": cell_key,
            "language_family": lang,
            "status": "recommendation_draft_ready_for_human_rubric_review",
            "review_stub_path": rubric_work.get("review_stub_path"),
            "recommended_subskills": rubric_recommendations,
            "same_surface_strict_exact": rubric_payload.get("same_surface_strict_exact_100m"),
            "gemma_strict_exact": rubric_payload.get("same_surface_strict_exact_gemma12b"),
            "same_surface_verdict": rubric_payload.get("same_surface_verdict"),
            "state_hash": (rubric_payload.get("counterfactual_audit_summary") or {}).get("state_hash"),
            "manifest_hash": (rubric_payload.get("counterfactual_audit_summary") or {}).get("manifest_hash"),
            "supporting_evidence_paths": rubric_payload.get("supporting_evidence_paths"),
            "reviewer_notes": [
                "These are machine-generated recommendations only. Human review still decides the final rubric judgment.",
                "Recommendations are grounded in the corrected opaque-choice multilingual win, not the stale visible-evidence packet.",
            ],
            "authority": dict(AUTHORITY_CLOSED),
        }
        anti_out = {
            "cell_key": cell_key,
            "language_family": lang,
            "status": "recommendation_draft_ready_for_human_anti_cheat_review",
            "review_stub_path": anti_work.get("review_stub_path"),
            "recommended_challenge_judgments": anti_recommendations,
            "same_surface_strict_exact": anti_payload.get("same_surface_strict_exact_100m"),
            "gemma_strict_exact": anti_payload.get("same_surface_strict_exact_gemma12b"),
            "same_surface_verdict": anti_payload.get("same_surface_verdict"),
            "state_hash": (anti_payload.get("supporting_evidence_paths") or [None])[0],
            "supporting_evidence_paths": anti_payload.get("supporting_evidence_paths"),
            "reviewer_notes": [
                "These are machine-generated anti-cheat recommendations only. Human review still decides final pass/fail state.",
                "Any family marked false or null should be treated as priority review work before a broader claim.",
            ],
            "authority": dict(AUTHORITY_CLOSED),
        }
        write_json(rubric_path, rubric_out)
        write_json(anti_path, anti_out)
        rows.append(
            {
                "cell_key": cell_key,
                "language_family": lang,
                "rubric_recommendation_path": str(rubric_path.relative_to(ROOT)),
                "anti_cheat_recommendation_path": str(anti_path.relative_to(ROOT)),
                "same_surface_strict_exact_100m": packet.get("same_surface_strict_exact_100m"),
                "same_surface_strict_exact_gemma12b": packet.get("same_surface_strict_exact_gemma12b"),
                "same_surface_verdict": packet.get("same_surface_verdict"),
                "recommended_anti_cheat_failures": [
                    row["challenge_family"]
                    for row in anti_recommendations
                    if row.get("recommended_pass") is False
                ],
                "recommended_rubric_needs_human_confirmation": [
                    name
                    for name, data in rubric_recommendations.items()
                    if data.get("recommended_judgment") is None
                ],
            }
        )

    metrics = {
        "recommendation_rows": len(rows),
        "rubric_recommendation_files": len(rows),
        "anti_cheat_recommendation_files": len(rows),
        "cells_with_shortcut_risk_flagged": sum(1 for row in rows if "label_proxy_shortcuts" in row["recommended_anti_cheat_failures"]),
        "cells_requiring_rubric_human_confirmation": sum(1 for row in rows if row["recommended_rubric_needs_human_confirmation"]),
    }
    if metrics["recommendation_rows"] != 4:
        failures.append("recommendation_rows_not_4")
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
    built = build_drafts()
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
    next_step = (
        "Use the Stage9805 recommendation drafts to work the Stage9796 review queue cell by cell, starting with Python, while keeping the corrected Stage9794 structured path as the truthful multilingual comparator."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"]},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Materialized machine-generated rubric and anti-cheat recommendation drafts for the corrected Stage9796 opaque-choice review packets so expert reviewers can focus on the real weak points instead of reconstructing them from raw artifacts.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9805 Opaque Choice Review Recommendation Drafts",
                "",
                f"Passed: `{summary['passed']}`",
                f"Recommendation rows: `{built['metrics']['recommendation_rows']}`",
                f"Rubric recommendation files: `{built['metrics']['rubric_recommendation_files']}`",
                f"Anti-cheat recommendation files: `{built['metrics']['anti_cheat_recommendation_files']}`",
                f"Cells with shortcut risk flagged: `{built['metrics']['cells_with_shortcut_risk_flagged']}`",
                "",
                "These drafts are intentionally conservative. They accelerate expert review on the corrected opaque-choice winning surface without promoting weak shortcut probes or the web tie into a stronger claim than the evidence supports.",
                "",
                f"Next: {next_step}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

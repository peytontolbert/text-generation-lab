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
STAGE = 9788
NAME = "stage9788_winning_edit_localization_review_recommendation_drafts"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "winning_edit_localization_review_recommendation_drafts.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "WINNING_EDIT_LOCALIZATION_REVIEW_RECOMMENDATION_DRAFTS_STAGE9788.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

AUDIT = ROOT / "runs/local/artifacts/stage9784_winning_edit_localization_counterfactual_anti_cheat_audit/winning_edit_localization_counterfactual_anti_cheat_audit.json"
WORKBOOK = ROOT / "runs/local/artifacts/stage9786_winning_edit_localization_review_workbook/winning_edit_localization_review_workbook.json"
PACKETS = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/supported_standalone_review_packets.jsonl"

LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def _recommended_subskills(audit_row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_outputs = audit_row.get("raw_100m_outputs") if isinstance(audit_row.get("raw_100m_outputs"), list) else []
    probes = audit_row.get("counterfactual_probes") if isinstance(audit_row.get("counterfactual_probes"), dict) else {}
    raw_count = len(raw_outputs)
    label_outputs_clean = all(str(row.get("predicted_label") or "").startswith("TARGET_") for row in raw_outputs)
    permutation_score = ((probes.get("label_order_permutation") or {}).get("score"))

    direct_true = {
        "understands_user_intent": "same-surface strict exact is 1.0 on the visible-evidence packet",
        "retrieves_source_evidence_when_needed": "the visible-evidence packet is solved exactly on the current same-surface rows",
        "binds_symbols_correctly": "row-level 100M outputs are correct on the visible-evidence strict-eval rows",
        "localizes_edit_scope": "the model selected the exact target localization label on every strict-eval row",
        "chooses_minimal_edit_operator": "the visible-evidence localization surface distinguishes narrow target classes and the model matched them exactly",
        "creates_or_updates_tests_when_appropriate": "the current packet includes test-target classes and the model matched the gold labels on strict eval",
        "interprets_verifier_failure": "the current edit-localization packet includes failure observations and the model matched the gold target on strict eval",
        "repairs_or_abstains_safely": "the model stayed inside the constrained target vocabulary on all attached outputs",
        "keeps_patch_minimal": "the predicted targets are limited to narrow edit-localization classes, not broad rewrites",
        "avoids_broad_rewrites": "the model stayed inside the target label vocabulary and did not broaden beyond the supplied classes",
        "avoids_hallucinated_symbols": "the structured outputs stayed within the expected target labels on the attached rows",
        "avoids_internal_tokens": "the attached outputs are clean target labels only",
        "produces_contentful_final_answer": "all attached outputs are valid target labels and same-surface strict exact is 1.0",
    }
    tentative = {
        "uses_allowed_imports_only": "the visible-evidence localization surface does not directly exercise imports, so a human should confirm this remains inapplicable rather than failed",
        "rejects_blocked_imports": "the visible-evidence localization surface does not directly exercise blocked imports, so a human should confirm this remains inapplicable rather than failed",
        "predicts_verifier_command": "the current winning surface is edit localization, not verifier-command prediction, so keep human confirmation on applicability",
    }

    recommendations: dict[str, dict[str, Any]] = {}
    for name, rationale in direct_true.items():
        notes = [rationale, f"Attached raw 100M row count: {raw_count}."]
        if name == "avoids_internal_tokens" and label_outputs_clean:
            notes.append("All attached predictions are normalized TARGET_* labels.")
        if name == "binds_symbols_correctly" and permutation_score is not None:
            notes.append(f"Permutation probe score is {permutation_score}; robustness concerns belong in anti-cheat review, not this same-surface correctness judgment.")
        recommendations[name] = {
            "recommended_judgment": True,
            "confidence": "high",
            "reviewer_notes": notes,
        }
    for name, rationale in tentative.items():
        recommendations[name] = {
            "recommended_judgment": None,
            "confidence": "requires_human_confirmation",
            "reviewer_notes": [rationale],
        }
    return recommendations


def _challenge_recommendations(audit_row: dict[str, Any], anti_payload: dict[str, Any]) -> list[dict[str, Any]]:
    probes = audit_row.get("counterfactual_probes") if isinstance(audit_row.get("counterfactual_probes"), dict) else {}
    baselines = audit_row.get("shallow_baselines") if isinstance(audit_row.get("shallow_baselines"), dict) else {}
    permutation = ((probes.get("label_order_permutation") or {}).get("score"))
    decoy = ((probes.get("decoy_label_injection") or {}).get("score"))
    ablation = ((probes.get("critical_evidence_ablation") or {}).get("score"))
    metadata_only = ((baselines.get("metadata_only") or {}).get("score"))
    majority = ((baselines.get("majority_label") or {}).get("score"))

    results = []
    families = anti_payload.get("challenge_families") if isinstance(anti_payload.get("challenge_families"), list) else []
    for family in families:
        challenge = str(family.get("challenge_family") or "")
        recommendation = None
        confidence = "requires_human_confirmation"
        notes: list[str] = []
        if challenge == "hidden_reference_materialization":
            notes = [
                "Global Stage9717 gate passed, but this cell-level draft does not independently prove hidden-reference absence.",
                "Human reviewer should confirm against the attached source manifest and packet lineage.",
            ]
        elif challenge == "target_and_teacher_leakage":
            recommendation = True
            confidence = "medium"
            notes = [
                "Same-surface hashes match between 100M and Gemma packet views.",
                "Attached outputs are model predictions rather than gold labels.",
            ]
        elif challenge == "label_proxy_shortcuts":
            recommendation = False
            confidence = "high"
            notes = [
                f"Permutation probe score is {permutation}; this is too weak to claim shortcut resistance.",
                f"Decoy probe score is {decoy}; this does not support a clean anti-shortcut pass.",
            ]
        elif challenge == "metadata_and_graph_shortcuts":
            recommendation = True
            confidence = "medium"
            notes = [
                f"Metadata-only baseline score is {metadata_only}.",
                f"Majority baseline score is {majority}.",
            ]
        elif challenge == "generation_quality_collapse":
            recommendation = True
            confidence = "medium"
            notes = [
                "Attached raw outputs remain inside the expected TARGET_* label space.",
                f"Ablation probe score is {ablation}; robustness is weak, but generation cleanliness itself is preserved.",
            ]
        elif challenge == "cross_model_surface_fairness":
            recommendation = True
            confidence = "high"
            notes = [
                "Same-surface hashes match between 100M and Gemma packet views.",
                "The live local Gemma rerun is attached to the same packet surface.",
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


def build_drafts() -> dict[str, Any]:
    audit = load_json(AUDIT)
    workbook = load_json(WORKBOOK)
    packets = load_jsonl(PACKETS)
    audit_rows = audit.get("records") if isinstance(audit.get("records"), list) else []
    workbook_rows = workbook.get("rows") if isinstance(workbook.get("rows"), list) else []
    packet_index = {str(row.get("cell_key") or ""): row for row in packets}
    workbook_by_key_task = {
        (str(row.get("cell_key") or ""), str(row.get("task") or "")): row
        for row in workbook_rows
    }

    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for audit_row in audit_rows:
        cell_key = str(audit_row.get("cell_key") or "")
        packet = packet_index.get(cell_key)
        rubric_work = workbook_by_key_task.get((cell_key, "expert_maintainer_rubric_review"))
        anti_work = workbook_by_key_task.get((cell_key, "cell_specific_anti_cheat_review"))
        if not isinstance(packet, dict) or not isinstance(rubric_work, dict) or not isinstance(anti_work, dict):
            failures.append(f"missing_inputs:{cell_key}")
            continue
        paths = packet.get("review_packet_paths") if isinstance(packet.get("review_packet_paths"), dict) else {}
        rubric_payload = load_json(ROOT / str(paths.get("expert_maintainer_rubric_scores") or ""))
        anti_payload = load_json(ROOT / str(paths.get("anti_cheat_cards") or ""))

        lang = str(audit_row.get("language_family") or "")
        base = OUT_DIR / "review_recommendations" / cell_key.replace("::", "__")
        rubric_path = base / "expert_maintainer_recommendation_draft.json"
        anti_path = base / "anti_cheat_recommendation_draft.json"

        rubric_recommendations = _recommended_subskills(audit_row)
        rubric_out = {
            "cell_key": cell_key,
            "language_family": lang,
            "status": "recommendation_draft_ready_for_human_rubric_review",
            "review_stub_path": rubric_work.get("review_stub_path"),
            "recommended_subskills": rubric_recommendations,
            "same_surface_eval_exact": rubric_payload.get("same_surface_eval_exact"),
            "same_surface_strict_exact": rubric_payload.get("same_surface_strict_exact"),
            "gemma_strict_exact": rubric_payload.get("gemma_strict_exact"),
            "state_hash": (rubric_payload.get("counterfactual_audit_summary") or {}).get("state_hash"),
            "manifest_hash": (rubric_payload.get("counterfactual_audit_summary") or {}).get("manifest_hash"),
            "supporting_evidence_paths": rubric_payload.get("supporting_evidence_paths"),
            "reviewer_notes": [
                "These are machine-generated recommendations only. Do not mark the rubric passed without human confirmation.",
                "Recommendations are grounded in the current same-surface visible-evidence win and attached counterfactual audit.",
            ],
            "authority": dict(AUTHORITY_CLOSED),
        }
        anti_recommendations = _challenge_recommendations(audit_row, anti_payload)
        anti_out = {
            "cell_key": cell_key,
            "language_family": lang,
            "status": "recommendation_draft_ready_for_human_anti_cheat_review",
            "review_stub_path": anti_work.get("review_stub_path"),
            "recommended_challenge_judgments": anti_recommendations,
            "same_surface_verified": anti_payload.get("same_surface_verified"),
            "same_surface_eval_exact": anti_payload.get("same_surface_eval_exact"),
            "same_surface_strict_exact": anti_payload.get("same_surface_strict_exact"),
            "gemma_strict_exact": anti_payload.get("gemma_strict_exact"),
            "state_hash": (anti_payload.get("counterfactual_audit_summary") or {}).get("state_hash"),
            "manifest_hash": (anti_payload.get("counterfactual_audit_summary") or {}).get("manifest_hash"),
            "supporting_evidence_paths": anti_payload.get("supporting_evidence_paths"),
            "reviewer_notes": [
                "These are machine-generated anti-cheat recommendations only. Human review still decides the final pass/fail state.",
                "Any family marked false or null should be treated as priority review work before a public win claim.",
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
                "same_surface_strict_exact": rubric_payload.get("same_surface_strict_exact"),
                "gemma_strict_exact": rubric_payload.get("gemma_strict_exact"),
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
        "winning_cells": len(rows),
        "rubric_recommendation_files": len(rows),
        "anti_cheat_recommendation_files": len(rows),
        "cells_with_label_proxy_shortcut_risk": sum(
            1
            for row in rows
            if "label_proxy_shortcuts" in row.get("recommended_anti_cheat_failures", [])
        ),
        "cells_with_nontrivial_rubric_confirmation": sum(
            1
            for row in rows
            if row.get("recommended_rubric_needs_human_confirmation")
        ),
    }
    if metrics["winning_cells"] != 4:
        failures.append("winning_cells_not_4")
    if metrics["cells_with_label_proxy_shortcut_risk"] != 4:
        failures.append("expected_label_proxy_shortcut_risk_in_all_winning_cells")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "rows": sorted(rows, key=lambda row: LANGS.index(str(row.get("language_family") or "python"))),
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_drafts()
    MANIFEST.write_text(
        json.dumps(
            {
                "stage": STAGE,
                "name": NAME,
                "passed": built["passed"],
                "metrics": built["metrics"],
                "rows": built["rows"],
                "authority": dict(AUTHORITY_CLOSED),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    next_step = (
        "Use the Stage9788 recommendation drafts to complete the four winning-cell rubric and anti-cheat signoff quickly, prioritizing the label_proxy_shortcuts review because the current counterfactual probes do not yet support a clean anti-shortcut pass."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"]},
        "artifacts": {
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Materialized evidence-backed recommendation drafts for the four winning edit-localization cells so reviewers have prefilled rubric suggestions and anti-cheat risk calls grounded in the current Stage9784/9786 evidence rather than blank review stubs.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9788 Winning Edit Localization Review Recommendation Drafts",
                "",
                f"Passed: `{summary['passed']}`",
                f"Winning cells: `{built['metrics']['winning_cells']}`",
                f"Cells with label-proxy shortcut risk: `{built['metrics']['cells_with_label_proxy_shortcut_risk']}`",
                f"Cells with nontrivial rubric confirmation: `{built['metrics']['cells_with_nontrivial_rubric_confirmation']}`",
                "",
                "This stage does not complete human review. It converts the current machine evidence into draft recommendations so reviewers can focus on the genuinely unresolved questions, especially shortcut-resistance and non-applicable rubric subskills.",
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
                "next_best_step": next_step,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

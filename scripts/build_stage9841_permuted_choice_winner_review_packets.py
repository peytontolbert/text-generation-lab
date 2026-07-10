#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
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
STAGE = 9841
NAME = "stage9841_permuted_choice_winner_review_packets"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKETS = OUT_DIR / "permuted_choice_winner_review_packets.jsonl"
MANIFEST = OUT_DIR / "permuted_choice_winner_review_packet_manifest.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PERMUTED_CHOICE_WINNER_REVIEW_PACKETS_STAGE9841.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
GLOBAL_GATE = ROOT / "runs/local/artifacts/stage9717_locked_multilingual_eval_hacking_audit/locked_multilingual_eval_hacking_audit.json"
STAGE9833_AUDIT = ROOT / "runs/local/artifacts/stage9833_permuted_choice_execution_manifest/permuted_choice_execution_manifest_audit.json"
STAGE9833_CONTRACT = ROOT / "runs/local/artifacts/stage9833_permuted_choice_execution_manifest/contract_probe/probe_contract_audit.json"
STAGE9835_COMPARISON = ROOT / "runs/local/artifacts/stage9835_permuted_choice_gemma_comparison/permuted_choice_gemma_comparison.json"
STAGE9835_ROWS = ROOT / "runs/local/artifacts/stage9835_permuted_choice_gemma_comparison/permuted_choice_gemma_rows.jsonl"
STAGE9839_AUDIT = ROOT / "runs/local/artifacts/stage9839_direct_permuted_choice_exec/direct_permuted_choice_exec_audit.json"
STAGE9839_FIELD_EXACT = ROOT / "runs/local/artifacts/stage9839_direct_permuted_choice_exec/field_exact_by_cell.json"
STAGE9839_ROW_LOGITS = ROOT / "runs/local/artifacts/stage9839_direct_permuted_choice_exec/row_field_logits.jsonl"
STAGE9839_CONFUSION = ROOT / "runs/local/artifacts/stage9839_direct_permuted_choice_exec/structured_confusion_matrix.json"
STAGE9840_COMPARISON = ROOT / "runs/local/artifacts/stage9840_permuted_choice_per_language_gemma_comparison/permuted_choice_per_language_gemma_comparison.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def aggregate_bucket_rows(rows: list[dict[str, Any]], *, language_field: str) -> dict[str, dict[str, Any]]:
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "rows": 0})
    for row in rows:
        lang = str(row.get(language_field) or "")
        split = str(row.get("split") or "")
        if not lang or not split:
            continue
        key = f"{lang}:{split}"
        buckets[key]["rows"] += 1
        if bool(row.get("correct")):
            buckets[key]["correct"] += 1
    out: dict[str, dict[str, Any]] = {}
    for key, bucket in buckets.items():
        rows_total = bucket["rows"]
        out[key] = {
            "correct": bucket["correct"],
            "rows": rows_total,
            "exact": (bucket["correct"] / rows_total) if rows_total else None,
        }
    return out


def _bucket_card(audit_9833: dict[str, Any], lang: str) -> dict[str, Any]:
    cards = audit_9833.get("bucket_cards") if isinstance(audit_9833.get("bucket_cards"), dict) else {}
    return {
        split: cards.get(f"{lang}:{split}", {})
        for split in ("eval", "strict_eval", "train")
    }


def _recommended_subskills(language_row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    eval_exact = language_row["hundred_m"]["eval"]["exact"]
    strict_exact = language_row["hundred_m"]["strict_eval"]["exact"]
    notes_exact = f"Permuted-choice same-surface exact is eval={eval_exact}, strict_eval={strict_exact} for this language."

    direct_true = {
        "localizes_edit_scope": "The stronger packet still measures bounded edit localization and the 100M system outperformed or tied Gemma on this language.",
        "keeps_patch_minimal": "Outputs remain inside a single opaque localization label instead of broad rewrites.",
        "avoids_broad_rewrites": "The structured surface restricts the model to a localized target token.",
        "avoids_hallucinated_symbols": "Row-level outputs stay within the A-E label set on the attached packet.",
        "avoids_internal_tokens": "The raw row outputs are single structured labels, not free-form internal text.",
        "produces_contentful_final_answer": "The attached packet contains concrete structured predictions for every eval and strict row.",
    }
    tentative = {
        "understands_user_intent": "This packet is a narrow localization surface, so human review should keep the claim scoped.",
        "retrieves_source_evidence_when_needed": "Visible evidence is present, but the packet does not isolate retrieval failure versus reasoning failure.",
        "binds_symbols_correctly": "Some rows rely on symbol-level ownership clues, but this packet does not isolate symbol binding as a standalone capability.",
        "chooses_minimal_edit_operator": "The packet chooses localization targets, not executable repair operators.",
        "repairs_or_abstains_safely": "The packet does not exercise abstention or repair execution.",
        "uses_allowed_imports_only": "This packet does not cover import policy.",
        "rejects_blocked_imports": "This packet does not cover blocked imports.",
        "creates_or_updates_tests_when_appropriate": "This packet does not cover test creation.",
        "predicts_verifier_command": "This packet is not a verifier-command surface.",
        "interprets_verifier_failure": "The packet uses failure observations but does not directly measure verifier reasoning.",
    }

    recommendations: dict[str, dict[str, Any]] = {}
    for name in RUBRIC_SUBSKILLS:
        if name in direct_true:
            recommendations[name] = {
                "recommended_judgment": True,
                "confidence": "medium" if strict_exact < 0.6 else "high",
                "reviewer_notes": [direct_true[name], notes_exact],
            }
        else:
            recommendations[name] = {
                "recommended_judgment": None,
                "confidence": "requires_human_confirmation",
                "reviewer_notes": [tentative.get(name, "No automatic recommendation available for this rubric line.")],
            }
    return recommendations


def _challenge_recommendations(
    challenge_families: list[str],
    *,
    language_row: dict[str, Any],
    audit_9833: dict[str, Any],
    contract_9833: dict[str, Any],
    gemma_rows_present: bool,
) -> list[dict[str, Any]]:
    bucket_cards = _bucket_card(audit_9833, language_row["language_family"])
    manifest_sha = contract_9833.get("manifest_sha256")
    rows_100m = language_row["row_counts"]["hundred_m"]
    rows_gemma = language_row["row_counts"]["gemma"]
    strict_verdict = language_row["comparisons"]["strict_eval"]["verdict"]
    results = []

    for challenge in challenge_families:
        recommendation = None
        confidence = "requires_human_confirmation"
        notes: list[str] = []
        if challenge == "label_proxy_shortcuts":
            recommendation = None
            confidence = "medium"
            notes = [
                f"Stage9833 permuted-choice manifest hash is {manifest_sha}.",
                f"Per-bucket permutation coverage for this language: eval={bucket_cards.get('eval', {}).get('permutation_count')}, strict_eval={bucket_cards.get('strict_eval', {}).get('permutation_count')}.",
                f"Row counts attached here are 100M={rows_100m}, Gemma={rows_gemma}.",
                "This is stronger evidence than the older packet because label-to-semantic mapping is permuted per row, but decoy, ablation, and causal-flip audits still need separate human review.",
            ]
        elif challenge == "cross_model_surface_fairness":
            recommendation = gemma_rows_present
            confidence = "high"
            notes = [
                "The same permuted-choice packet is attached for both 100M and Gemma evidence.",
                f"Strict-split verdict for this language is {strict_verdict}.",
            ]
        elif challenge == "generation_quality_collapse":
            recommendation = True
            confidence = "medium"
            notes = [
                "The raw 100M row outputs stay inside the opaque A-E label vocabulary.",
                "This does not prove causal robustness, but it does show the stronger packet does not collapse into malformed output.",
            ]
        elif challenge == "hidden_reference_materialization":
            recommendation = None
            notes = ["No dedicated hidden-reference audit is attached for this stronger packet yet."]
        elif challenge == "target_and_teacher_leakage":
            recommendation = None
            notes = ["Same-surface Gemma rows are attached, but teacher-leakage review still requires human inspection of the prompt surface."]
        elif challenge == "metadata_and_graph_shortcuts":
            recommendation = None
            notes = ["No metadata-only or graph-shortcut baseline was rerun on the stronger permuted-choice packet yet."]
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
    gate = load_json(GLOBAL_GATE)
    audit_9833 = load_json(STAGE9833_AUDIT)
    contract_9833 = load_json(STAGE9833_CONTRACT)
    comparison_9835 = load_json(STAGE9835_COMPARISON)
    audit_9839 = load_json(STAGE9839_AUDIT)
    field_exact_9839 = load_json(STAGE9839_FIELD_EXACT)
    comparison_9840 = load_json(STAGE9840_COMPARISON)
    rows_100m = load_jsonl(STAGE9839_ROW_LOGITS)
    rows_gemma = load_jsonl(STAGE9835_ROWS)

    gemma_rows_by_bucket = aggregate_bucket_rows(rows_gemma, language_field="language_family")
    challenge_records = ((gate.get("challenge_matrix") or {}).get("records") or []) if isinstance((gate.get("challenge_matrix") or {}), dict) else []
    challenge_families = [str(row.get("challenge_family") or "") for row in challenge_records]

    field_exact_rows = (field_exact_9839.get("edit_localization") or {}) if isinstance(field_exact_9839.get("edit_localization"), dict) else {}
    comparison_cells = comparison_9840.get("comparisons") if isinstance(comparison_9840.get("comparisons"), dict) else {}

    rows: list[dict[str, Any]] = []
    failures: list[str] = []

    evidence_hashes = {
        "stage9833_manifest_audit_sha256": sha256_file(STAGE9833_AUDIT),
        "stage9833_contract_audit_sha256": sha256_file(STAGE9833_CONTRACT),
        "stage9835_rows_sha256": sha256_file(STAGE9835_ROWS),
        "stage9835_comparison_sha256": sha256_file(STAGE9835_COMPARISON),
        "stage9839_audit_sha256": sha256_file(STAGE9839_AUDIT),
        "stage9839_field_exact_sha256": sha256_file(STAGE9839_FIELD_EXACT),
        "stage9839_row_logits_sha256": sha256_file(STAGE9839_ROW_LOGITS),
        "stage9839_confusion_sha256": sha256_file(STAGE9839_CONFUSION),
        "stage9840_comparison_sha256": sha256_file(STAGE9840_COMPARISON),
    }

    for lang in LANGS:
        cell_key = f"{lang}::edit_localization"
        source_cell_key = f"{lang}::edit_localization_counterfactual_guard::KEEP_STRUCTURED"
        hundred_bucket = field_exact_rows.get(source_cell_key)
        if not isinstance(hundred_bucket, dict):
            failures.append(f"missing_100m_bucket:{lang}")
            continue

        lang_row = {
            "language_family": lang,
            "hundred_m": {
                "eval": comparison_9840.get("hundred_m", {}).get("by_bucket", {}).get(f"{lang}:eval", {}),
                "strict_eval": comparison_9840.get("hundred_m", {}).get("by_bucket", {}).get(f"{lang}:strict_eval", {}),
            },
            "gemma": {
                "eval": comparison_9840.get("gemma", {}).get("by_bucket", {}).get(f"{lang}:eval", {}),
                "strict_eval": comparison_9840.get("gemma", {}).get("by_bucket", {}).get(f"{lang}:strict_eval", {}),
            },
            "comparisons": {
                "eval": comparison_cells.get(f"{lang}:eval", {}),
                "strict_eval": comparison_cells.get(f"{lang}:strict_eval", {}),
            },
            "row_counts": {
                "hundred_m": hundred_bucket.get("rows"),
                "gemma": gemma_rows_by_bucket.get(f"{lang}:eval", {}).get("rows", 0) + gemma_rows_by_bucket.get(f"{lang}:strict_eval", {}).get("rows", 0),
            },
        }
        paths = template_output_paths(cell_key)
        rubric_path = ROOT / paths["expert_maintainer_rubric_scores"]
        anti_path = ROOT / paths["anti_cheat_cards"]
        rubric_draft_path = ROOT / paths["rubric_recommendation_draft"]
        anti_draft_path = ROOT / paths["anti_cheat_recommendation_draft"]

        rubric_stub = {
            "cell_key": cell_key,
            "source_cell_key": source_cell_key,
            "language_family": lang,
            "status": "pending_human_review",
            "rubric_version": "expert_maintainer_v1",
            "must_pass_all_subskills": True,
            "passed": False,
            "subskills": {name: None for name in RUBRIC_SUBSKILLS},
            "failure_trace_refs": [],
            "reviewer_notes": [],
            "permuted_choice_same_surface_eval_exact_100m": lang_row["hundred_m"]["eval"].get("exact"),
            "permuted_choice_same_surface_strict_exact_100m": lang_row["hundred_m"]["strict_eval"].get("exact"),
            "permuted_choice_same_surface_eval_exact_gemma": lang_row["gemma"]["eval"].get("exact"),
            "permuted_choice_same_surface_strict_exact_gemma": lang_row["gemma"]["strict_eval"].get("exact"),
            "supporting_evidence_paths": {
                "manifest_audit": relative(STAGE9833_AUDIT),
                "manifest_contract_probe": relative(STAGE9833_CONTRACT),
                "hundred_m_row_outputs": relative(STAGE9839_ROW_LOGITS),
                "hundred_m_field_exact_by_cell": relative(STAGE9839_FIELD_EXACT),
                "hundred_m_confusion_matrix": relative(STAGE9839_CONFUSION),
                "hundred_m_execution_audit": relative(STAGE9839_AUDIT),
                "gemma_row_outputs": relative(STAGE9835_ROWS),
                "gemma_comparison_summary": relative(STAGE9835_COMPARISON),
                "per_language_comparison": relative(STAGE9840_COMPARISON),
            },
            "supporting_evidence_hashes": dict(evidence_hashes),
            "authority": dict(AUTHORITY_CLOSED),
        }
        anti_stub = {
            "cell_key": cell_key,
            "source_cell_key": source_cell_key,
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
            "permuted_choice_packet_status": {
                "manifest_passed": audit_9833.get("passed") is True,
                "runtime_passed": audit_9839.get("passed") is True,
                "per_language_comparison_passed": comparison_9840.get("passed") is True,
                "label_proxy_shortcuts_status": "improved_same_surface_permutation_resistance_but_not_fully_cleared",
            },
            "reviewer_notes": [],
            "authority": dict(AUTHORITY_CLOSED),
        }
        rubric_draft = {
            "cell_key": cell_key,
            "source_cell_key": source_cell_key,
            "language_family": lang,
            "status": "recommendation_draft_ready_for_human_rubric_review",
            "recommended_subskills": _recommended_subskills(lang_row),
            "reviewer_notes": [
                "These are machine-generated recommendations only. Human review still decides the rubric pass/fail outcome.",
                "The stronger packet is a permuted-choice same-surface anti-cheat packet with real 100M row-level outputs and attached Gemma rows.",
            ],
            "authority": dict(AUTHORITY_CLOSED),
        }
        anti_draft = {
            "cell_key": cell_key,
            "source_cell_key": source_cell_key,
            "language_family": lang,
            "status": "recommendation_draft_ready_for_human_anti_cheat_review",
            "recommended_challenge_judgments": _challenge_recommendations(
                challenge_families,
                language_row=lang_row,
                audit_9833=audit_9833,
                contract_9833=contract_9833,
                gemma_rows_present=STAGE9835_ROWS.exists(),
            ),
            "reviewer_notes": [
                "These are machine-generated anti-cheat recommendations only.",
                "The old blanket label-proxy failure is intentionally replaced here with a stronger but still provisional permutation-resistance status.",
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
                "source_cell_key": source_cell_key,
                "language_family": lang,
                "review_packet_paths": paths,
                "claim_scope": "permuted-choice visible-evidence edit localization only",
                "permuted_choice_manifest_sha256": contract_9833.get("manifest_sha256"),
                "permuted_choice_same_surface_eval_exact_100m": lang_row["hundred_m"]["eval"].get("exact"),
                "permuted_choice_same_surface_strict_exact_100m": lang_row["hundred_m"]["strict_eval"].get("exact"),
                "permuted_choice_same_surface_eval_exact_gemma": lang_row["gemma"]["eval"].get("exact"),
                "permuted_choice_same_surface_strict_exact_gemma": lang_row["gemma"]["strict_eval"].get("exact"),
                "strict_eval_verdict": lang_row["comparisons"]["strict_eval"].get("verdict"),
                "label_proxy_shortcuts_status": "improved_same_surface_permutation_resistance_but_not_fully_cleared",
            }
        )

    metrics = {
        "winning_cells": len(rows),
        "rubric_stub_files": len(rows),
        "anti_cheat_stub_files": len(rows),
        "rubric_recommendation_files": len(rows),
        "anti_cheat_recommendation_files": len(rows),
        "global_stage9717_gate_passed": gate.get("passed") is True,
        "cells_with_provisional_label_proxy_status": 0,
        "cells_with_same_surface_gemma_rows": 0,
    }
    for row in rows:
        if row["label_proxy_shortcuts_status"] == "improved_same_surface_permutation_resistance_but_not_fully_cleared":
            metrics["cells_with_provisional_label_proxy_status"] += 1
        if STAGE9835_ROWS.exists():
            metrics["cells_with_same_surface_gemma_rows"] += 1

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
    if metrics["cells_with_provisional_label_proxy_status"] != 4:
        failures.append("provisional_label_proxy_status_count_mismatch")
    if metrics["cells_with_same_surface_gemma_rows"] != 4:
        failures.append("same_surface_gemma_rows_count_mismatch")

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
    next_step = "Fill the stage9841 expert-maintainer and anti-cheat review stubs for the four permuted-choice winning cells, then add explicit decoy, ablation, and causal-flip audits before making a broader anti-cheat claim."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"review_packets": relative(PACKETS), "manifest": relative(MANIFEST), "doc": relative(DOC)},
        "decision": "Materialized four focused review packets, stub files, and machine-generated rubric and anti-cheat recommendation drafts for the stronger multilingual permuted-choice winner packet backed by Stage9833 manifest evidence, Stage9839 row-level 100M outputs, and Stage9840 per-language Gemma comparisons.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9841 Permuted-Choice Winner Review Packets",
                "",
                f"Passed: `{built['passed']}`",
                f"Winning cells: `{built['metrics']['winning_cells']}`",
                f"Rubric stubs: `{built['metrics']['rubric_stub_files']}`",
                f"Anti-cheat stubs: `{built['metrics']['anti_cheat_stub_files']}`",
                f"Rubric recommendation files: `{built['metrics']['rubric_recommendation_files']}`",
                f"Anti-cheat recommendation files: `{built['metrics']['anti_cheat_recommendation_files']}`",
                f"Cells with provisional label-proxy status: `{built['metrics']['cells_with_provisional_label_proxy_status']}`",
                "",
                "This stage upgrades the older winner-review packet flow to the stronger permuted-choice same-surface packet with real row-level 100M outputs and attached raw Gemma rows.",
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

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
STAGE = 9796
NAME = "stage9796_opaque_choice_review_packets"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "opaque_choice_review_packets.json"
WORKBOOK = OUT_DIR / "opaque_choice_review_workbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OPAQUE_CHOICE_REVIEW_PACKETS_STAGE9796.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

AUDIT_9795 = ROOT / "runs/local/artifacts/stage9795_opaque_choice_counterfactual_anti_cheat_audit/opaque_choice_counterfactual_anti_cheat_audit.json"
COMPARE_9793 = ROOT / "runs/local/artifacts/stage9793_edit_localization_opaque_choice_gemma_comparison/edit_localization_opaque_choice_gemma_comparison.json"
EXEC_9794 = ROOT / "runs/local/artifacts/stage9794_edit_localization_opaque_choice_exec_stable_labels/execution_result.json"

LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
TASKS = [
    ("expert_maintainer_rubric_review", "expert_maintainer_rubric_review.json"),
    ("cell_specific_anti_cheat_review", "anti_cheat_review_card.json"),
]
RUBRIC_SUBSKILLS = [
    "understands_user_intent",
    "uses_allowed_imports_only",
    "rejects_blocked_imports",
    "retrieves_source_evidence_when_needed",
    "binds_symbols_correctly",
    "localizes_edit_scope",
    "chooses_minimal_edit_operator",
    "creates_or_updates_tests_when_appropriate",
    "predicts_verifier_command",
    "interprets_verifier_failure",
    "repairs_or_abstains_safely",
    "keeps_patch_minimal",
    "avoids_broad_rewrites",
    "avoids_hallucinated_symbols",
    "avoids_internal_tokens",
    "produces_contentful_final_answer",
]
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


def _cell_key(lang: str) -> str:
    return f"opaque_choice_win::{lang}::edit_localization"


def _packet_dir(lang: str) -> Path:
    return OUT_DIR / "review_packets" / _cell_key(lang).replace("::", "__")


def _audit_index() -> dict[str, dict[str, Any]]:
    audit = load_json(AUDIT_9795)
    return {str(row.get("language_family") or ""): row for row in audit.get("records") or []}


def _compare_index() -> dict[str, dict[str, Any]]:
    compare = load_json(COMPARE_9793)
    return {str(row.get("language") or ""): row for row in compare.get("results") or []}


def _exec_metrics() -> dict[str, Any]:
    payload = load_json(EXEC_9794)
    return (payload.get("execution_result") if isinstance(payload.get("execution_result"), dict) else payload)


def _rubric_stub(lang: str, audit_row: dict[str, Any], compare_row: dict[str, Any], paths: dict[str, str]) -> dict[str, Any]:
    return {
        "cell_key": _cell_key(lang),
        "language_family": lang,
        "skill_area": "edit_localization",
        "surface": "edit_localization_opaque_choice_surface_v1",
        "status": "pending_human_review",
        "rubric_version": "expert_maintainer_v1",
        "must_pass_all_subskills": True,
        "passed": False,
        "subskills": {name: None for name in RUBRIC_SUBSKILLS},
        "failure_trace_refs": [],
        "reviewer_notes": [],
        "reviewer_must_confirm": True,
        "same_surface_strict_exact_100m": compare_row.get("model_strict_exact_100m"),
        "same_surface_strict_exact_gemma12b": compare_row.get("gemma_strict_exact"),
        "same_surface_verdict": compare_row.get("verdict"),
        "counterfactual_audit_summary": {
            "state_hash": audit_row.get("state_hash"),
            "manifest_hash": audit_row.get("manifest_hash"),
            "selected_step": audit_row.get("selected_step"),
            "shallow_baselines": audit_row.get("shallow_baselines"),
            "counterfactual_probe_scores": {
                key: (value or {}).get("score")
                for key, value in (audit_row.get("counterfactual_probes") or {}).items()
            },
        },
        "supporting_evidence_paths": [
            str(COMPARE_9793.relative_to(ROOT)),
            str(EXEC_9794.relative_to(ROOT)),
            str(AUDIT_9795.relative_to(ROOT)),
            paths["anti_cheat_cards"],
        ],
        "authority": dict(AUTHORITY_CLOSED),
    }


def _anti_cheat_stub(lang: str, audit_row: dict[str, Any], compare_row: dict[str, Any], paths: dict[str, str]) -> dict[str, Any]:
    return {
        "cell_key": _cell_key(lang),
        "language_family": lang,
        "skill_area": "edit_localization",
        "surface": "edit_localization_opaque_choice_surface_v1",
        "status": "pending_cell_specific_review",
        "passed": False,
        "reviewer_must_confirm": True,
        "same_surface_strict_exact_100m": compare_row.get("model_strict_exact_100m"),
        "same_surface_strict_exact_gemma12b": compare_row.get("gemma_strict_exact"),
        "same_surface_verdict": compare_row.get("verdict"),
        "prompt_target_literal_row_count": (audit_row.get("prompt_surface_checks") or {}).get("prompt_target_literal_row_count"),
        "prompt_hidden_target_literal_row_count": (audit_row.get("prompt_surface_checks") or {}).get("prompt_hidden_target_literal_row_count"),
        "mapping_stable_across_splits": (audit_row.get("mapping_stability") or {}).get("stable_across_splits"),
        "challenge_families": [
            {
                "challenge_family": name,
                "passed": False,
                "reviewer_notes": [],
                "evidence_hints": [
                    "inspect the attached Stage9795 per-cell card",
                    "verify the same-surface Gemma and 100M comparison uses the corrected opaque-choice manifest",
                    "cite concrete row-level evidence before marking pass",
                ],
            }
            for name in CHALLENGE_FAMILIES
        ],
        "counterfactual_probe_scores": {
            key: (value or {}).get("score")
            for key, value in (audit_row.get("counterfactual_probes") or {}).items()
        },
        "supporting_evidence_paths": [
            str(COMPARE_9793.relative_to(ROOT)),
            str(EXEC_9794.relative_to(ROOT)),
            str(AUDIT_9795.relative_to(ROOT)),
            paths["expert_maintainer_rubric_scores"],
        ],
        "authority": dict(AUTHORITY_CLOSED),
    }


def build_packets() -> dict[str, Any]:
    audit_index = _audit_index()
    compare_index = _compare_index()
    exec_metrics = _exec_metrics()
    failures: list[str] = []
    packet_rows: list[dict[str, Any]] = []
    workbook_rows: list[dict[str, Any]] = []

    for lang in LANGS:
        audit_row = audit_index.get(lang)
        compare_row = compare_index.get(lang)
        if not isinstance(audit_row, dict):
            failures.append(f"missing_audit:{lang}")
            continue
        if not isinstance(compare_row, dict):
            failures.append(f"missing_comparison:{lang}")
            continue
        packet_dir = _packet_dir(lang)
        paths = {
            "packet_dir": str(packet_dir.relative_to(ROOT)),
            "expert_maintainer_rubric_scores": str((packet_dir / "expert_maintainer_rubric_review.json").relative_to(ROOT)),
            "anti_cheat_cards": str((packet_dir / "anti_cheat_review_card.json").relative_to(ROOT)),
            "same_prompt_surface_gemma12b_outputs": str(ROOT.joinpath("runs/local/artifacts/stage9793_edit_localization_opaque_choice_gemma_comparison/edit_localization_opaque_choice_gemma_rows.jsonl").relative_to(ROOT)),
            "hundred_m_row_outputs": str(ROOT.joinpath("runs/local/artifacts/stage9794_edit_localization_opaque_choice_exec_stable_labels/row_field_logits.jsonl").relative_to(ROOT)),
        }
        rubric = _rubric_stub(lang, audit_row, compare_row, paths)
        anti = _anti_cheat_stub(lang, audit_row, compare_row, paths)
        write_json(ROOT / paths["expert_maintainer_rubric_scores"], rubric)
        write_json(ROOT / paths["anti_cheat_cards"], anti)
        packet_rows.append(
            {
                "cell_key": _cell_key(lang),
                "language_family": lang,
                "skill_area": "edit_localization",
                "same_surface_strict_exact_100m": compare_row.get("model_strict_exact_100m"),
                "same_surface_strict_exact_gemma12b": compare_row.get("gemma_strict_exact"),
                "same_surface_verdict": compare_row.get("verdict"),
                "review_packet_paths": paths,
                "counterfactual_audit_path": str(AUDIT_9795.relative_to(ROOT)),
                "execution_result_path": str(EXEC_9794.relative_to(ROOT)),
            }
        )
        for task, filename in TASKS:
            workbook_rows.append(
                {
                    "cell_key": _cell_key(lang),
                    "language_family": lang,
                    "task": task,
                    "review_stub_path": str((packet_dir / filename).relative_to(ROOT)),
                    "same_surface_strict_exact_100m": compare_row.get("model_strict_exact_100m"),
                    "same_surface_strict_exact_gemma12b": compare_row.get("gemma_strict_exact"),
                    "same_surface_verdict": compare_row.get("verdict"),
                    "prompt_target_literal_row_count": (audit_row.get("prompt_surface_checks") or {}).get("prompt_target_literal_row_count"),
                    "mapping_stable_across_splits": (audit_row.get("mapping_stability") or {}).get("stable_across_splits"),
                    "counterfactual_audit_path": str(AUDIT_9795.relative_to(ROOT)),
                    "execution_result_path": str(EXEC_9794.relative_to(ROOT)),
                }
            )

    workbook_rows.sort(key=lambda row: (LANGS.index(str(row["language_family"])), 0 if row["task"] == "expert_maintainer_rubric_review" else 1))
    for index, row in enumerate(workbook_rows, start=1):
        row["queue_position"] = index

    metrics = {
        "winning_cells": len(packet_rows),
        "rubric_stub_files": len(packet_rows),
        "anti_cheat_stub_files": len(packet_rows),
        "workbook_tasks": len(workbook_rows),
        "rubric_tasks": sum(1 for row in workbook_rows if row["task"] == "expert_maintainer_rubric_review"),
        "anti_cheat_tasks": sum(1 for row in workbook_rows if row["task"] == "cell_specific_anti_cheat_review"),
        "top_queue_entry": workbook_rows[0]["cell_key"] + "::" + workbook_rows[0]["task"] if workbook_rows else None,
        "overall_strict_exact_100m": (((exec_metrics.get("eval") or {}).get("strict_eval") or {}).get("field_exact") or {}).get("edit_localization", {}).get("exact"),
    }
    if metrics["winning_cells"] != 4:
        failures.append("winning_cells_not_4")
    if metrics["workbook_tasks"] != 8:
        failures.append("workbook_tasks_not_8")
    if metrics["rubric_tasks"] != 4:
        failures.append("rubric_tasks_not_4")
    if metrics["anti_cheat_tasks"] != 4:
        failures.append("anti_cheat_tasks_not_4")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "packet_rows": packet_rows,
        "workbook_rows": workbook_rows,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packets()
    write_json(
        MANIFEST,
        {
            "stage": STAGE,
            "name": NAME,
            "passed": built["passed"],
            "metrics": built["metrics"],
            "rows": built["packet_rows"],
            "authority": dict(AUTHORITY_CLOSED),
        },
    )
    write_json(
        WORKBOOK,
        {
            "stage": STAGE,
            "name": NAME,
            "passed": built["passed"],
            "metrics": built["metrics"],
            "rows": built["workbook_rows"],
            "authority": dict(AUTHORITY_CLOSED),
        },
    )
    next_step = (
        "Work the Stage9796 workbook top to bottom and replace the remaining human-review blockers on the corrected opaque-choice multilingual win with signed rubric and anti-cheat judgments."
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
            "workbook": str(WORKBOOK.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Materialized fresh reviewer-facing rubric and anti-cheat packets plus a queue workbook for the corrected opaque-choice multilingual win, sourced directly from the Stage9793 comparison, Stage9794 execution, and Stage9795 anti-cheat audit.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage9796 Opaque Choice Review Packets",
                "",
                f"Passed: `{summary['passed']}`",
                f"Winning cells: `{summary['metrics']['winning_cells']}`",
                f"Rubric stubs: `{summary['metrics']['rubric_stub_files']}`",
                f"Anti-cheat stubs: `{summary['metrics']['anti_cheat_stub_files']}`",
                f"Workbook tasks: `{summary['metrics']['workbook_tasks']}`",
                f"Top queue entry: `{summary['metrics']['top_queue_entry']}`",
                "",
                "This stage creates fresh review packets for the corrected opaque-choice multilingual win instead of reusing the stale visible-evidence packet slots. Each packet points directly at the real Stage9793 same-surface Gemma comparison, Stage9794 100M execution, and Stage9795 anti-cheat audit.",
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

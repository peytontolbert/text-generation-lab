#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from typing import Any

def _load_symbol(module_name: str, path: Path, symbol: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return getattr(module, symbol)

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_CLOSED = _load_symbol('stage10004_contract', ROOT / 'scripts/diagnostic_ticket_contract.py', 'AUTHORITY_CLOSED')
STAGE = 10004
NAME = "stage10004_heldout_multilingual_winner_signoff_workbook"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
WORKBOOK = OUT_DIR / "heldout_multilingual_winner_signoff_workbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "HELDOUT_MULTILINGUAL_WINNER_SIGNOFF_WORKBOOK_STAGE10004.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

COMPARISON = ROOT / "runs/summaries/stage10001_source_heldout_same_manifest_comparison_audit.json"
REVIEW_BASE = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/review_packets"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
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


def _packet_dir(language: str) -> Path:
    return REVIEW_BASE / f"standalone_100m_weights__{language}__edit_localization"


def build_workbook() -> dict[str, Any]:
    comparison = load_json(COMPARISON)
    per_language = ((comparison.get("metrics") or {}).get("per_language") or {})
    failures: list[str] = []
    rows: list[dict[str, Any]] = []
    queue_position = 1
    for language in LANGS:
        metrics = per_language.get(language)
        packet_dir = _packet_dir(language)
        if not isinstance(metrics, dict):
            failures.append(f"missing_language_metrics:{language}")
            continue
        if not packet_dir.exists():
            failures.append(f"missing_packet_dir:{language}")
            continue
        common = {
            "cell_key": f"standalone_100m_weights::{language}::edit_localization",
            "language_family": language,
            "packet_dir": display(packet_dir),
            "same_surface_eval_exact": metrics.get("hundred_m_exact"),
            "gemma_strict_exact": metrics.get("gemma_exact"),
            "supporting_evidence_paths": {
                "same_surface_comparison": display(ROOT / "runs/local/artifacts/stage10001_source_heldout_same_manifest_comparison_audit/source_heldout_same_manifest_comparison_audit.json"),
                "same_surface_rows_100m": display(ROOT / "runs/local/artifacts/stage9998_source_heldout_target100m_probe/edit_localization_probe/row_field_logits.jsonl"),
                "same_surface_rows_gemma12b": display(ROOT / "runs/local/artifacts/stage10000_source_heldout_same_manifest_gemma_execution/same_prompt_surface_gemma12b_outputs_rows.jsonl"),
                "source_overlap_eval_hacking_audit": display(ROOT / "runs/local/artifacts/stage9995_source_overlap_eval_hacking_audit/source_overlap_eval_rows.jsonl"),
                "duplicate_rowid_eval_audit": display(ROOT / "runs/local/artifacts/stage10002_duplicate_rowid_eval_audit/duplicate_eval_row_ids.jsonl"),
                "deduped_successor_manifest": display(ROOT / "runs/local/artifacts/stage10003_deduped_source_heldout_successor_request/edit_localization_manifest.jsonl"),
            },
            "reviewer_guidance": [
                "This active standalone winner packet is now aligned to the source-heldout same-manifest multilingual frontier.",
                "The attached recommendation draft is machine-generated support only and must not be treated as final human signoff.",
                "Use the source-overlap and duplicate-row audits to confirm the current evaluation surface is honest before finalizing rubric or anti-cheat judgments.",
            ],
            "rubric_recommendation_draft": display(packet_dir / "expert_maintainer_recommendation_draft.json"),
            "anti_cheat_recommendation_draft": display(packet_dir / "anti_cheat_recommendation_draft.json"),
        }
        rows.append({
            **common,
            "queue_position": queue_position,
            "task": "expert_maintainer_rubric_review",
            "review_file": display(packet_dir / "expert_maintainer_rubric_review.json"),
            "review_status": "pending_human_review_with_source_heldout_evidence",
            "required_human_action": "review the attached source-heldout same-manifest evidence and confirm final expert-maintainer rubric judgments",
            "recommendation_source_path": display(packet_dir / "expert_maintainer_recommendation_draft.json"),
            "draft_recommendation_path": display(packet_dir / "expert_maintainer_recommendation_draft.json"),
            "recommended_subskills": 16,
            "recommended_challenge_families": 0,
        })
        queue_position += 1
        rows.append({
            **common,
            "queue_position": queue_position,
            "task": "cell_specific_anti_cheat_review",
            "review_file": display(packet_dir / "anti_cheat_review_card.json"),
            "review_status": "pending_cell_specific_review_with_source_heldout_evidence",
            "required_human_action": "review the attached source-heldout anti-cheat evidence and confirm final challenge-family judgments",
            "recommendation_source_path": display(packet_dir / "anti_cheat_recommendation_draft.json"),
            "draft_recommendation_path": display(packet_dir / "anti_cheat_recommendation_draft.json"),
            "recommended_subskills": 0,
            "recommended_challenge_families": 6,
        })
        queue_position += 1
    metrics = {
        **dict(AUTHORITY_CLOSED),
        "unique_cells": len(LANGS),
        "signoff_tasks": len(rows),
        "rubric_tasks": sum(1 for row in rows if row.get("task") == "expert_maintainer_rubric_review"),
        "anti_cheat_tasks": sum(1 for row in rows if row.get("task") == "cell_specific_anti_cheat_review"),
        "tasks_with_recommendation_source": sum(1 for row in rows if row.get("recommendation_source_path")),
        "top_queue_entry": rows[0]["cell_key"] + "::" + rows[0]["task"] if rows else None,
    }
    if metrics["signoff_tasks"] != 8:
        failures.append("signoff_tasks_not_8")
    return {
        "passed": not failures,
        "failures": failures,
        "rows": rows,
        "metrics": metrics,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_workbook()
    WORKBOOK.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Work this heldout workbook top to bottom in the active standalone winner packet dirs, then mark the four source-heldout multilingual winners human-complete once rubric and anti-cheat judgments are signed."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"workbook": display(WORKBOOK), "doc": display(DOC)},
        "decision": "Materialized a compact live signoff workbook for the four active standalone heldout-winner cells, pointed at the current source-heldout same-manifest comparison and eval-hacking evidence.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10004 Heldout Multilingual Winner Signoff Workbook",
        "",
        f"Passed: `{summary['passed']}`",
        f"Signoff tasks: `{built['metrics']['signoff_tasks']}`",
        f"Unique cells: `{built['metrics']['unique_cells']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

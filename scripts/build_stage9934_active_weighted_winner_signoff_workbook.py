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
STAGE = 9934
NAME = "stage9934_active_weighted_winner_signoff_workbook"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
WORKBOOK = OUT_DIR / "active_weighted_winner_signoff_workbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ACTIVE_WEIGHTED_WINNER_SIGNOFF_WORKBOOK_STAGE9934.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
BASE = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/review_packets"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
TASKS = [
    ("expert_maintainer_rubric_review", "expert_maintainer_rubric_review.json"),
    ("cell_specific_anti_cheat_review", "anti_cheat_review_card.json"),
]


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


def _cell_dir(lang: str) -> Path:
    return BASE / f"standalone_100m_weights__{lang}__edit_localization"


def _task_order(task: str) -> int:
    return 0 if task == "expert_maintainer_rubric_review" else 1


def build_workbook() -> dict[str, Any]:
    failures: list[str] = []
    rows: list[dict[str, Any]] = []
    for lang in LANGS:
        cell_key = f"standalone_100m_weights::{lang}::edit_localization"
        cell_dir = _cell_dir(lang)
        rubric_draft = cell_dir / "expert_maintainer_recommendation_draft.json"
        anti_draft = cell_dir / "anti_cheat_recommendation_draft.json"
        for task, filename in TASKS:
            review_path = cell_dir / filename
            if not review_path.exists():
                failures.append(f"missing_review_file:{lang}:{task}")
                continue
            payload = load_json(review_path)
            rows.append({
                "cell_key": cell_key,
                "language_family": lang,
                "task": task,
                "queue_position": 0,
                "review_status": payload.get("status"),
                "required_human_action": payload.get("required_human_action"),
                "review_file": display(review_path),
                "packet_dir": display(cell_dir),
                "same_surface_eval_exact": payload.get("same_surface_eval_exact") or payload.get("same_surface_eval_exact_100m"),
                "same_surface_strict_exact": payload.get("same_surface_strict_exact") or payload.get("same_surface_strict_exact_100m"),
                "gemma_strict_exact": payload.get("gemma_strict_exact") or payload.get("same_surface_strict_exact_gemma12b"),
                "recommendation_source_path": payload.get("recommendation_source_path"),
                "draft_recommendation_path": payload.get("draft_recommendation_path"),
                "recommended_subskills": len(payload.get("recommended_subskills") or {}),
                "recommended_challenge_families": sum(1 for row in payload.get("challenge_families", []) if isinstance(row, dict) and "recommended_pass" in row),
                "reviewer_guidance": payload.get("reviewer_guidance"),
                "rubric_recommendation_draft": display(rubric_draft) if rubric_draft.exists() else None,
                "anti_cheat_recommendation_draft": display(anti_draft) if anti_draft.exists() else None,
                "supporting_evidence_paths": payload.get("supporting_evidence_paths"),
            })
    rows.sort(key=lambda row: (LANGS.index(row["language_family"]), _task_order(str(row["task"]))))
    for idx, row in enumerate(rows, start=1):
        row["queue_position"] = idx
    metrics = {
        "signoff_tasks": len(rows),
        "unique_cells": len({row["cell_key"] for row in rows}),
        "rubric_tasks": sum(1 for row in rows if row["task"] == "expert_maintainer_rubric_review"),
        "anti_cheat_tasks": sum(1 for row in rows if row["task"] == "cell_specific_anti_cheat_review"),
        "tasks_with_recommendation_source": sum(1 for row in rows if row.get("recommendation_source_path")),
        "top_queue_entry": rows[0]["cell_key"] + "::" + rows[0]["task"] if rows else None,
    }
    if metrics["signoff_tasks"] != 8:
        failures.append("signoff_tasks_not_8")
    if metrics["unique_cells"] != 4:
        failures.append("unique_cells_not_4")
    if metrics["tasks_with_recommendation_source"] != 8:
        failures.append("tasks_with_recommendation_source_not_8")
    return {"passed": not failures, "failures": failures, "metrics": metrics, "rows": rows, "authority": dict(AUTHORITY_CLOSED)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_workbook()
    WORKBOOK.write_text(json.dumps({"stage": STAGE, "name": NAME, "passed": built["passed"], "metrics": built["metrics"], "rows": built["rows"], "authority": dict(AUTHORITY_CLOSED)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Work the Stage9934 signoff workbook top to bottom in the active standalone winner packet dirs, then mark the four weighted multilingual same-surface winners human-complete once rubric and anti-cheat judgments are signed."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"workbook": display(WORKBOOK), "doc": display(DOC)},
        "decision": "Materialized a compact live signoff workbook for the four active standalone weighted winner cells, pointed at the current packet dirs and enriched review cards rather than the older stage9921 packet set.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9934 Active Weighted Winner Signoff Workbook",
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
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

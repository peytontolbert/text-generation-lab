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
STAGE = 9923
NAME = "stage9923_hardened_weighted_multilingual_review_workbook"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
WORKBOOK = OUT_DIR / "hardened_weighted_multilingual_review_workbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "HARDENED_WEIGHTED_MULTILINGUAL_REVIEW_WORKBOOK_STAGE9923.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
PACKETS = ROOT / "runs/local/artifacts/stage9921_hardened_weighted_multilingual_winner_review_packets/hardened_weighted_multilingual_winner_review_packets.jsonl"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
TASKS = [
    ("expert_maintainer_rubric_review", "expert_maintainer_rubric_scores"),
    ("cell_specific_anti_cheat_review", "anti_cheat_cards"),
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _language_order(cell_key: str) -> int:
    for idx, lang in enumerate(LANGS):
        if f"::{lang}::" in cell_key:
            return idx
    return len(LANGS)


def _task_order(task: str) -> int:
    return 0 if task == "expert_maintainer_rubric_review" else 1


def build_workbook() -> dict[str, Any]:
    packets = load_jsonl(PACKETS)
    failures: list[str] = []
    rows: list[dict[str, Any]] = []
    for packet in packets:
        cell_key = str(packet.get("cell_key") or "")
        paths = packet.get("review_packet_paths") if isinstance(packet.get("review_packet_paths"), dict) else {}
        for task, path_key in TASKS:
            review_rel = str(paths.get(path_key) or "")
            review_path = ROOT / review_rel
            if not review_rel or not review_path.exists():
                failures.append(f"missing_review_stub:{cell_key}:{task}")
                continue
            payload = load_json(review_path)
            rows.append(
                {
                    "cell_key": cell_key,
                    "language_family": packet.get("language_family"),
                    "skill_area": packet.get("skill_area"),
                    "task": task,
                    "review_stub_path": review_rel,
                    "queue_position": 0,
                    "review_status": payload.get("status"),
                    "required_human_action": payload.get("required_human_action"),
                    "same_surface_eval_exact": payload.get("same_surface_eval_exact") or payload.get("same_surface_eval_exact_100m"),
                    "same_surface_strict_exact": payload.get("same_surface_strict_exact") or payload.get("same_surface_strict_exact_100m"),
                    "gemma_strict_exact": payload.get("gemma_strict_exact") or payload.get("same_surface_strict_exact_gemma12b"),
                    "packet_dir": paths.get("packet_dir"),
                    "rubric_recommendation_draft": paths.get("rubric_recommendation_draft"),
                    "anti_cheat_recommendation_draft": paths.get("anti_cheat_recommendation_draft"),
                    "supporting_evidence_paths": packet.get("supporting_evidence_paths"),
                }
            )
    rows.sort(key=lambda row: (_language_order(str(row.get("cell_key") or "")), _task_order(str(row.get("task") or ""))))
    for idx, row in enumerate(rows, start=1):
        row["queue_position"] = idx
    metrics = {
        "winning_review_tasks": len(rows),
        "unique_cells": len({row["cell_key"] for row in rows}),
        "rubric_tasks": sum(1 for row in rows if row["task"] == "expert_maintainer_rubric_review"),
        "anti_cheat_tasks": sum(1 for row in rows if row["task"] == "cell_specific_anti_cheat_review"),
        "top_queue_entry": rows[0]["cell_key"] + "::" + rows[0]["task"] if rows else None,
    }
    if metrics["winning_review_tasks"] != 8:
        failures.append("winning_review_tasks_not_8")
    if metrics["unique_cells"] != 4:
        failures.append("unique_cells_not_4")
    return {"passed": not failures, "failures": failures, "metrics": metrics, "rows": rows, "authority": dict(AUTHORITY_CLOSED)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_workbook()
    WORKBOOK.write_text(json.dumps({"stage": STAGE, "name": NAME, "passed": built["passed"], "metrics": built["metrics"], "rows": built["rows"], "authority": dict(AUTHORITY_CLOSED)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Work the Stage9923 workbook top to bottom and replace the remaining human-review blockers on the four weighted hardened multilingual winner cells with signed rubric and anti-cheat judgments."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"workbook": str(WORKBOOK.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Materialized a reviewer-facing workbook for the four weighted hardened multilingual winner cells, with direct links to the refreshed rubric stubs, anti-cheat cards, and recommendation drafts tied to Stage9919 and Stage9920.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9923 Hardened Weighted Multilingual Review Workbook",
        "",
        f"Passed: `{summary['passed']}`",
        f"Winning review tasks: `{built['metrics']['winning_review_tasks']}`",
        f"Unique cells: `{built['metrics']['unique_cells']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "winning_review_tasks": built["metrics"]["winning_review_tasks"], "unique_cells": built["metrics"]["unique_cells"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

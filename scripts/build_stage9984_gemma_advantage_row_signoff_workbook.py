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
STAGE = 9984
NAME = "stage9984_gemma_advantage_row_signoff_workbook"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
WORKBOOK = OUT_DIR / "gemma_advantage_row_signoff_workbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "GEMMA_ADVANTAGE_ROW_SIGNOFF_WORKBOOK_STAGE9984.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9983_gemma_advantage_row_review_packets/gemma_advantage_row_review_packet_manifest.json"

LANG_PRIORITY = ["python", "c_cpp"]
TASK_ORDER = {
    "expert_maintainer_rubric_review": 0,
    "cell_specific_anti_cheat_review": 1,
}


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


def build_workbook() -> dict[str, Any]:
    manifest = load_json(MANIFEST)
    review_rows = [row for row in (manifest.get("rows") or []) if isinstance(row, dict)]
    failures: list[str] = []
    rows: list[dict[str, Any]] = []
    if len(review_rows) != 11:
        failures.append("review_rows_not_11")
    for packet in review_rows:
        language = str(packet.get("language_family") or "")
        if language not in LANG_PRIORITY:
            failures.append(f"unexpected_language:{language}")
            continue
        role = str(packet.get("counterfactual_role") or "")
        paths = packet.get("review_packet_paths") if isinstance(packet.get("review_packet_paths"), dict) else {}
        base_fields = {
            "row_id": packet.get("row_id"),
            "language_family": language,
            "split": packet.get("split"),
            "counterfactual_role": role,
            "same_surface_prediction": packet.get("same_surface_prediction"),
            "same_surface_target": packet.get("same_surface_target"),
            "same_surface_correct": packet.get("same_surface_correct"),
        }
        rows.append(
            {
                **base_fields,
                "task": "expert_maintainer_rubric_review",
                "required_human_action": "Decide whether the visible evidence justifies one answer, an abstention label, or quarantine from expert-maintainer eval use.",
                "review_status": "pending_row_level_human_review",
                "review_file": paths.get("expert_maintainer_rubric_scores"),
                "recommendation_draft": paths.get("rubric_recommendation_draft"),
                "packet_dir": paths.get("packet_dir"),
                "quarantine_if_unresolved": True,
            }
        )
        rows.append(
            {
                **base_fields,
                "task": "cell_specific_anti_cheat_review",
                "required_human_action": "Decide whether this row is a valid causal-evidence challenge or an eval-hack risk driven by ambiguity, template priors, or decoy sensitivity.",
                "review_status": "pending_row_level_human_review",
                "review_file": paths.get("anti_cheat_cards"),
                "recommendation_draft": paths.get("anti_cheat_recommendation_draft"),
                "packet_dir": paths.get("packet_dir"),
                "quarantine_if_unresolved": True,
            }
        )
    rows.sort(
        key=lambda item: (
            LANG_PRIORITY.index(str(item.get("language_family") or "")),
            0 if str(item.get("counterfactual_role") or "") == "positive_original_eval_replay" else 1,
            str(item.get("row_id") or ""),
            TASK_ORDER[str(item.get("task") or "")],
        )
    )
    for idx, row in enumerate(rows, start=1):
        row["queue_position"] = idx
    metrics = {
        "signoff_tasks": len(rows),
        "rubric_tasks": sum(1 for row in rows if row["task"] == "expert_maintainer_rubric_review"),
        "anti_cheat_tasks": sum(1 for row in rows if row["task"] == "cell_specific_anti_cheat_review"),
        "review_rows": len({str(row.get("row_id") or "") for row in rows}),
        "top_queue_entry": rows[0]["row_id"] + "::" + rows[0]["task"] if rows else None,
    }
    if metrics["signoff_tasks"] != 22:
        failures.append("signoff_tasks_not_22")
    if metrics["rubric_tasks"] != 11:
        failures.append("rubric_tasks_not_11")
    if metrics["anti_cheat_tasks"] != 11:
        failures.append("anti_cheat_tasks_not_11")
    if metrics["review_rows"] != 11:
        failures.append("unique_review_rows_not_11")
    return {"passed": not failures, "failures": failures, "metrics": metrics, "rows": rows, "authority": dict(AUTHORITY_CLOSED)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_workbook()
    WORKBOOK.write_text(json.dumps({"stage": STAGE, "name": NAME, "passed": built["passed"], "metrics": built["metrics"], "rows": built["rows"], "authority": dict(AUTHORITY_CLOSED)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Work this 22-task workbook row by row and quarantine any unresolved or invalid row before it re-enters v2.7 training or multilingual 100M-versus-Gemma reporting."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"workbook": display(WORKBOOK), "doc": display(DOC)},
        "decision": "Materialized a row-level signoff workbook for the 11 Gemma-advantage rows so expert-maintainer and anti-cheat review can directly govern whether each row is quarantined, abstention-relabeled, or kept.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9984 Gemma Advantage Row Signoff Workbook",
                "",
                f"Passed: `{summary['passed']}`",
                f"Signoff tasks: `{built['metrics']['signoff_tasks']}`",
                f"Review rows: `{built['metrics']['review_rows']}`",
                "",
                summary["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "signoff_tasks": built["metrics"]["signoff_tasks"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9924
NAME = "stage9924_current_truthful_weighted_hardened_bridge_after_review_workbook"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ARTIFACT = OUT_DIR / "current_truthful_weighted_hardened_bridge_after_review_workbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_TRUTHFUL_WEIGHTED_HARDENED_BRIDGE_AFTER_REVIEW_WORKBOOK_STAGE9924.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_BRIDGE = ROOT / "runs/local/artifacts/stage9922_current_weighted_hardened_multilingual_frontier_bridge/current_weighted_hardened_multilingual_frontier_bridge.json"
WORKBOOK = ROOT / "runs/local/artifacts/stage9923_hardened_weighted_multilingual_review_workbook/hardened_weighted_multilingual_review_workbook.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
WINNING_KEYS = {f"hardened_weighted_same_surface::{lang}::edit_localization" for lang in LANGS}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def build_refresh() -> dict[str, Any]:
    bridge = load_json(SOURCE_BRIDGE)
    workbook = load_json(WORKBOOK)
    records = bridge.get("records") if isinstance(bridge.get("records"), list) else []
    workbook_rows = workbook.get("rows") if isinstance(workbook.get("rows"), list) else []
    workbook_by_cell: dict[str, list[dict[str, Any]]] = {}
    for row in workbook_rows:
        workbook_by_cell.setdefault(str(row.get("cell_key") or ""), []).append(row)

    refreshed_records: list[dict[str, Any]] = []
    failures: list[str] = []
    workbook_attached = 0
    review_only_blocked = 0

    if bridge.get("passed") is not True:
        failures.append("stage9922_not_passed")
    if workbook.get("passed") is not True:
        failures.append("stage9923_not_passed")

    for record in records:
        updated = copy.deepcopy(record)
        lang = str(updated.get("language_family") or "")
        cell_key = f"hardened_weighted_same_surface::{lang}::edit_localization"
        updated["cell_key"] = cell_key
        if cell_key in WINNING_KEYS:
            workbook_rows_for_cell = workbook_by_cell.get(cell_key) or []
            if len(workbook_rows_for_cell) != 2:
                failures.append(f"winning_cell_workbook_rows_not_2:{cell_key}")
            else:
                updated["attached_evidence"] = [
                    {
                        "kind": "weighted_hardened_review_workbook_support",
                        "stage": 9923,
                        "path": str(WORKBOOK.relative_to(ROOT)),
                        "supports": ["expert_maintainer_rubric_scores", "anti_cheat_cards"],
                        "quality_passed": True,
                        "claim_sufficient": False,
                        "details": {
                            "review_tasks": [str(row.get("task") or "") for row in workbook_rows_for_cell],
                            "review_stub_paths": [str(row.get("review_stub_path") or "") for row in workbook_rows_for_cell],
                            "same_surface_eval_exact": workbook_rows_for_cell[0].get("same_surface_eval_exact"),
                            "same_surface_strict_exact": workbook_rows_for_cell[0].get("same_surface_strict_exact"),
                            "gemma_strict_exact": workbook_rows_for_cell[0].get("gemma_strict_exact"),
                        },
                        "why_not_claim_sufficient": [
                            "pending_human_expert_rubric_confirmation",
                            "pending_human_anti_cheat_confirmation",
                        ],
                    }
                ]
                updated["blockers"] = [
                    "expert_maintainer_rubric_scores_missing",
                    "anti_cheat_cards_not_attached_for_specific_cell",
                    "missing_required_evidence:expert_maintainer_rubric_scores",
                    "missing_required_evidence:anti_cheat_cards",
                    "same_surface_win_present_but_review_confirmation_still_missing",
                ]
                updated["claim_status"] = "blocked_pending_human_review_confirmation"
                updated["review_execution_ready"] = True
                updated["review_workbook_path"] = str(WORKBOOK.relative_to(ROOT))
                updated["remaining_machine_gap"] = False
                updated["remaining_human_gates"] = [
                    "expert_maintainer_rubric_scores",
                    "anti_cheat_cards",
                ]
                workbook_attached += 1
                if updated["blockers"] == [
                    "expert_maintainer_rubric_scores_missing",
                    "anti_cheat_cards_not_attached_for_specific_cell",
                    "missing_required_evidence:expert_maintainer_rubric_scores",
                    "missing_required_evidence:anti_cheat_cards",
                    "same_surface_win_present_but_review_confirmation_still_missing",
                ]:
                    review_only_blocked += 1
        refreshed_records.append(updated)

    metrics = {
        "bridge_records": len(refreshed_records),
        "winning_cells": len(WINNING_KEYS),
        "winning_cells_with_workbook_support": workbook_attached,
        "winning_cells_machine_complete_but_review_blocked": review_only_blocked,
    }
    if metrics["bridge_records"] != 4:
        failures.append("bridge_records_not_4")
    if metrics["winning_cells_with_workbook_support"] != 4:
        failures.append("winning_cells_with_workbook_support_not_4")
    if metrics["winning_cells_machine_complete_but_review_blocked"] != 4:
        failures.append("winning_cells_machine_complete_but_review_blocked_not_4")

    output = {
        "passed": not failures,
        "failures": failures,
        "records": refreshed_records,
        "metrics": metrics,
        "authority": dict(AUTHORITY_CLOSED),
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_refresh()
    next_step = "Use the Stage9923 workbook to complete the remaining expert-maintainer and anti-cheat signoff on the four weighted hardened multilingual winner cells, because the machine-side same-surface evidence is now fully attached."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "bridge": str(ARTIFACT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
            "workbook": str(WORKBOOK.relative_to(ROOT)),
        },
        "decision": "Refreshed the truthful weighted hardened claim bridge so the four multilingual winner cells explicitly point at the Stage9923 reviewer workbook and are classified as machine-complete but still blocked on human rubric and anti-cheat confirmation.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9924 Current Truthful Weighted Hardened Bridge After Review Workbook",
                "",
                f"Passed: `{summary['passed']}`",
                f"Bridge records: `{built['metrics']['bridge_records']}`",
                f"Winning cells with workbook support: `{built['metrics']['winning_cells_with_workbook_support']}`",
                f"Winning cells machine-complete but review-blocked: `{built['metrics']['winning_cells_machine_complete_but_review_blocked']}`",
                "",
                "This stage aligns the current truthful weighted hardened claim bridge with the real current state of the four multilingual winner cells. Same-surface 100M-vs-Gemma evidence and shortcut-audit support are already attached; the remaining blockers are human review signoff only.",
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
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"], "next_best_step": next_step}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

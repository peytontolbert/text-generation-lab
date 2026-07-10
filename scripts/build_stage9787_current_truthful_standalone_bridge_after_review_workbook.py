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
STAGE = 9787
NAME = "stage9787_current_truthful_standalone_bridge_after_review_workbook"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ARTIFACT = OUT_DIR / "current_truthful_standalone_bridge_after_review_workbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_TRUTHFUL_STANDALONE_BRIDGE_AFTER_REVIEW_WORKBOOK_STAGE9787.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

SOURCE_BRIDGE = ROOT / "runs/local/artifacts/stage9785_attach_counterfactual_audit_to_winning_packets_and_bridge/attach_counterfactual_audit_to_winning_packets_and_bridge.json"
WORKBOOK = ROOT / "runs/local/artifacts/stage9786_winning_edit_localization_review_workbook/winning_edit_localization_review_workbook.json"

LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
WINNING_KEYS = {f"standalone_100m_weights::{lang}::edit_localization" for lang in LANGS}


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
        failures.append("stage9785_not_passed")
    if workbook.get("passed") is not True:
        failures.append("stage9786_not_passed")

    for record in records:
        updated = copy.deepcopy(record)
        cell_key = str(updated.get("cell_key") or "")
        if cell_key in WINNING_KEYS:
            workbook_rows_for_cell = workbook_by_cell.get(cell_key) or []
            if len(workbook_rows_for_cell) != 2:
                failures.append(f"winning_cell_workbook_rows_not_2:{cell_key}")
            else:
                attached = list(updated.get("attached_evidence") or [])
                attached.append(
                    {
                        "kind": "winning_review_workbook_support",
                        "stage": 9786,
                        "path": str(WORKBOOK.relative_to(ROOT)),
                        "supports": ["expert_maintainer_rubric_scores", "anti_cheat_cards"],
                        "quality_passed": True,
                        "claim_sufficient": False,
                        "details": {
                            "review_tasks": [str(row.get("task") or "") for row in workbook_rows_for_cell],
                            "review_stub_paths": [str(row.get("review_stub_path") or "") for row in workbook_rows_for_cell],
                            "same_surface_hash_100m": workbook_rows_for_cell[0].get("same_surface_hash_100m"),
                            "same_surface_hash_gemma12b": workbook_rows_for_cell[0].get("same_surface_hash_gemma12b"),
                            "state_hash": workbook_rows_for_cell[0].get("state_hash"),
                            "manifest_hash": workbook_rows_for_cell[0].get("manifest_hash"),
                        },
                        "why_not_claim_sufficient": [
                            "pending_human_expert_rubric_confirmation",
                            "pending_human_anti_cheat_confirmation",
                        ],
                    }
                )
                updated["attached_evidence"] = attached
                blockers = [
                    blocker
                    for blocker in (updated.get("blockers") or [])
                    if blocker not in {
                        "same_surface_100m_vs_gemma12b_evidence_missing",
                        "same_surface_win_present_but_review_and_checkpoint_evidence_still_missing",
                    }
                ]
                if "same_surface_win_present_but_review_confirmation_still_missing" not in blockers:
                    blockers.append("same_surface_win_present_but_review_confirmation_still_missing")
                updated["blockers"] = blockers
                updated["claim_status"] = "blocked_pending_human_review_confirmation"
                updated["review_execution_ready"] = True
                updated["review_workbook_path"] = str(WORKBOOK.relative_to(ROOT))
                updated["remaining_machine_gap"] = False
                updated["remaining_human_gates"] = [
                    "expert_maintainer_rubric_scores",
                    "anti_cheat_cards",
                ]
                workbook_attached += 1
                if blockers == [
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
    if metrics["bridge_records"] != 72:
        failures.append("bridge_records_not_72")
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
    next_step = (
        "Use the Stage9786 workbook to complete the remaining expert-maintainer and anti-cheat signoff on the four winning edit-localization cells, because the standalone claim bridge now reflects that the machine-side same-surface evidence is already attached."
    )
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
        "decision": "Refreshed the truthful standalone claim bridge so the four winning edit-localization cells explicitly point at the Stage9786 reviewer workbook and are classified as machine-complete but still blocked on human rubric and anti-cheat confirmation.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9787 Current Truthful Standalone Bridge After Review Workbook",
                "",
                f"Passed: `{summary['passed']}`",
                f"Bridge records: `{built['metrics']['bridge_records']}`",
                f"Winning cells with workbook support: `{built['metrics']['winning_cells_with_workbook_support']}`",
                f"Winning cells machine-complete but review-blocked: `{built['metrics']['winning_cells_machine_complete_but_review_blocked']}`",
                "",
                "This stage aligns the current truthful standalone claim bridge with the real current state of the four winning visible-evidence edit-localization cells. Same-surface 100M-vs-Gemma evidence, checkpoint hashes, local Gemma reruns, and counterfactual audit support are already attached; the remaining blockers are human review signoff only.",
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

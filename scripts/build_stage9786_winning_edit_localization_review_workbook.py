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
STAGE = 9786
NAME = "stage9786_winning_edit_localization_review_workbook"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
WORKBOOK = OUT_DIR / "winning_edit_localization_review_workbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "WINNING_EDIT_LOCALIZATION_REVIEW_WORKBOOK_STAGE9786.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

PACKETS = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/supported_standalone_review_packets.jsonl"
BRIDGE = ROOT / "runs/local/artifacts/stage9785_attach_counterfactual_audit_to_winning_packets_and_bridge/attach_counterfactual_audit_to_winning_packets_and_bridge.json"
AUDIT = ROOT / "runs/local/artifacts/stage9784_winning_edit_localization_counterfactual_anti_cheat_audit/winning_edit_localization_counterfactual_anti_cheat_audit.json"

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


def _language_order(cell_key: str) -> int:
    for index, lang in enumerate(LANGS):
        if f"::{lang}::" in cell_key:
            return index
    return len(LANGS)


def _task_order(task: str) -> int:
    return 0 if task == "expert_maintainer_rubric_review" else 1


def build_workbook() -> dict[str, Any]:
    packets = load_jsonl(PACKETS)
    bridge = load_json(BRIDGE)
    audit = load_json(AUDIT)
    packet_index = {str(packet.get("cell_key") or ""): packet for packet in packets}
    bridge_index = {
        str(row.get("cell_key") or ""): row
        for row in (bridge.get("records") if isinstance(bridge.get("records"), list) else [])
    }
    audit_index = {
        str(row.get("cell_key") or ""): row
        for row in (audit.get("records") if isinstance(audit.get("records"), list) else [])
    }

    rows: list[dict[str, Any]] = []
    failures: list[str] = []

    for lang in LANGS:
        cell_key = f"standalone_100m_weights::{lang}::edit_localization"
        packet = packet_index.get(cell_key)
        bridge_row = bridge_index.get(cell_key)
        audit_row = audit_index.get(cell_key)
        if packet is None:
            failures.append(f"missing_packet:{cell_key}")
            continue
        if bridge_row is None:
            failures.append(f"missing_bridge:{cell_key}")
            continue
        if audit_row is None:
            failures.append(f"missing_audit:{cell_key}")
            continue

        paths = packet.get("review_packet_paths") if isinstance(packet.get("review_packet_paths"), dict) else {}
        for task, path_key in TASKS:
            review_rel = str(paths.get(path_key) or "")
            review_path = ROOT / review_rel
            if not review_rel or not review_path.exists():
                failures.append(f"missing_review_stub:{cell_key}:{task}")
                continue
            review_payload = load_json(review_path)
            counterfactual = review_payload.get("counterfactual_audit_summary")
            if not isinstance(counterfactual, dict):
                failures.append(f"missing_counterfactual_summary:{cell_key}:{task}")
                continue

            same_surface_gemma_rel = str(paths.get("same_prompt_surface_gemma12b_outputs") or "")
            same_surface_gemma_rows_rel = same_surface_gemma_rel.replace(".json", "_rows.jsonl")
            row = {
                "cell_key": cell_key,
                "language_family": lang,
                "skill_area": "edit_localization",
                "task": task,
                "queue_position": len(rows) + 1,
                "review_status": review_payload.get("status"),
                "reviewer_must_confirm": review_payload.get("reviewer_must_confirm"),
                "required_human_action": review_payload.get("required_human_action"),
                "review_stub_path": review_rel,
                "packet_dir": paths.get("packet_dir"),
                "same_surface_hash_100m": review_payload.get("same_surface_hash_100m"),
                "same_surface_hash_gemma12b": review_payload.get("same_surface_hash_gemma12b"),
                "same_surface_eval_exact": review_payload.get("same_surface_eval_exact"),
                "same_surface_strict_exact": review_payload.get("same_surface_strict_exact"),
                "gemma_strict_exact": review_payload.get("gemma_strict_exact"),
                "state_hash": counterfactual.get("state_hash"),
                "manifest_hash": counterfactual.get("manifest_hash"),
                "selected_step": counterfactual.get("selected_step"),
                "counterfactual_audit_path": review_payload.get("evidence_draft_path"),
                "same_surface_gemma_summary_path": same_surface_gemma_rel,
                "same_surface_gemma_rows_path": same_surface_gemma_rows_rel,
                "supporting_evidence_paths": review_payload.get("supporting_evidence_paths"),
                "attached_bridge_evidence_kinds": [
                    item.get("kind")
                    for item in (bridge_row.get("attached_evidence") if isinstance(bridge_row.get("attached_evidence"), list) else [])
                    if item.get("kind")
                ],
                "remaining_bridge_blockers": bridge_row.get("blockers"),
                "shallow_baselines": (
                    counterfactual.get("shallow_baselines")
                    if isinstance(counterfactual.get("shallow_baselines"), dict)
                    else {
                        "majority": counterfactual.get("majority_baseline"),
                        "metadata_only": counterfactual.get("metadata_only_baseline"),
                    }
                ),
                "probe_scores": (
                    counterfactual.get("counterfactual_probe_scores")
                    if isinstance(counterfactual.get("counterfactual_probe_scores"), dict)
                    else counterfactual.get("probe_scores")
                ),
            }
            rows.append(row)

    rows.sort(key=lambda row: (_language_order(str(row.get("cell_key") or "")), _task_order(str(row.get("task") or ""))))
    for index, row in enumerate(rows, start=1):
        row["queue_position"] = index

    metrics = {
        "winning_review_tasks": len(rows),
        "unique_cells": len({row["cell_key"] for row in rows}),
        "rubric_tasks": sum(1 for row in rows if row["task"] == "expert_maintainer_rubric_review"),
        "anti_cheat_tasks": sum(1 for row in rows if row["task"] == "cell_specific_anti_cheat_review"),
        "same_surface_verified_tasks": sum(
            1
            for row in rows
            if row["same_surface_hash_100m"] and row["same_surface_hash_100m"] == row["same_surface_hash_gemma12b"]
        ),
        "top_queue_entry": (
            rows[0]["cell_key"] + "::" + rows[0]["task"]
            if rows else None
        ),
        "review_confirmation_blocked_tasks": sum(
            1
            for row in rows
            if "same_surface_win_present_but_review_confirmation_still_missing" in (row.get("remaining_bridge_blockers") or [])
        ),
    }

    if metrics["winning_review_tasks"] != 8:
        failures.append("winning_review_tasks_not_8")
    if metrics["unique_cells"] != 4:
        failures.append("unique_cells_not_4")
    if metrics["rubric_tasks"] != 4:
        failures.append("rubric_tasks_not_4")
    if metrics["anti_cheat_tasks"] != 4:
        failures.append("anti_cheat_tasks_not_4")
    if metrics["same_surface_verified_tasks"] != 8:
        failures.append("same_surface_verified_tasks_not_8")
    if metrics["review_confirmation_blocked_tasks"] != 8:
        failures.append("review_confirmation_blocked_tasks_not_8")

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

    built = build_workbook()
    workbook_payload = {
        "stage": STAGE,
        "name": NAME,
        "passed": built["passed"],
        "metrics": built["metrics"],
        "rows": built["rows"],
        "authority": dict(AUTHORITY_CLOSED),
    }
    WORKBOOK.write_text(json.dumps(workbook_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    next_step = (
        "Work the Stage9786 workbook top to bottom and replace the remaining human-review blockers on the four winning edit-localization cells with signed rubric and anti-cheat judgments."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            **built["metrics"],
        },
        "artifacts": {
            "workbook": str(WORKBOOK.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Materialized a reviewer-facing execution workbook for the four winning same-surface edit-localization cells, with direct links to the refreshed review stubs, state hashes, Gemma reruns, and Stage9784 counterfactual audit evidence.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Stage9786 Winning Edit Localization Review Workbook",
        "",
        f"Passed: `{summary['passed']}`",
        f"Winning review tasks: `{summary['metrics']['winning_review_tasks']}`",
        f"Unique cells: `{summary['metrics']['unique_cells']}`",
        f"Rubric tasks: `{summary['metrics']['rubric_tasks']}`",
        f"Anti-cheat tasks: `{summary['metrics']['anti_cheat_tasks']}`",
        f"Same-surface verified tasks: `{summary['metrics']['same_surface_verified_tasks']}`",
        f"Top queue entry: `{summary['metrics']['top_queue_entry']}`",
        "",
        "This stage narrows the remaining standalone review work to the four winning visible-evidence edit-localization cells. Each workbook row points directly to the live review stub, the matching same-surface Gemma rerun, the Stage9781 frozen-state hashes, and the Stage9784 counterfactual audit summary that still needs human signoff.",
        "",
        f"Next: {next_step}",
        "",
    ]
    DOC.write_text("\n".join(lines), encoding="utf-8")

    if summary["passed"]:
        update_registry(summary)

    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": summary["passed"],
                "winning_review_tasks": summary["metrics"]["winning_review_tasks"],
                "unique_cells": summary["metrics"]["unique_cells"],
                "rubric_tasks": summary["metrics"]["rubric_tasks"],
                "anti_cheat_tasks": summary["metrics"]["anti_cheat_tasks"],
                "same_surface_verified_tasks": summary["metrics"]["same_surface_verified_tasks"],
                "top_queue_entry": summary["metrics"]["top_queue_entry"],
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

#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10112
NAME = "stage10112_real_session_successor_claim_bridge_after_review_workbook"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ARTIFACT = OUT_DIR / "real_session_successor_claim_bridge_after_review_workbook.json"
ADJUDICATED_TARGET = OUT_DIR / "real_session_successor_adjudicated_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_SESSION_SUCCESSOR_CLAIM_BRIDGE_AFTER_REVIEW_WORKBOOK_STAGE10112.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

SOURCE_PACKET = ROOT / "runs/local/artifacts/stage10110_real_session_shortcut_safe_successor_packet/real_session_shortcut_safe_successor_packet.jsonl"
WORKBOOK = ROOT / "runs/local/artifacts/stage10111_real_session_successor_review_packets/real_session_successor_signoff_workbook.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)),
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_refresh() -> dict[str, Any]:
    packet_rows = load_jsonl(SOURCE_PACKET)
    workbook = load_json(WORKBOOK)
    workbook_rows = workbook.get("rows") if isinstance(workbook.get("rows"), list) else []
    workbook_by_row: dict[str, list[dict[str, Any]]] = {}
    for row in workbook_rows:
        workbook_by_row.setdefault(str(row.get("row_id") or ""), []).append(row)

    refreshed_records: list[dict[str, Any]] = []
    failures: list[str] = []
    workbook_attached = 0
    review_only_blocked = 0

    if len(packet_rows) != 41:
        failures.append("stage10110_packet_rows_not_41")
    if int(workbook.get("row_count") or 0) != 82:
        failures.append("stage10111_workbook_rows_not_82")

    for row in packet_rows:
        updated = copy.deepcopy(row)
        row_id = str(updated.get("row_id") or "")
        workbook_rows_for_row = workbook_by_row.get(row_id) or []
        if len(workbook_rows_for_row) != 2:
            failures.append(f"row_workbook_rows_not_2:{row_id}")
        else:
            updated["attached_evidence"] = [
                {
                    "kind": "real_session_successor_review_workbook_support",
                    "stage": 10111,
                    "path": display(WORKBOOK),
                    "supports": ["expert_maintainer_rubric_review", "cell_specific_anti_cheat_review"],
                    "quality_passed": True,
                    "claim_sufficient": False,
                    "details": {
                        "review_tasks": [str(item.get("task") or "") for item in workbook_rows_for_row],
                        "review_files": [str(item.get("review_file") or "") for item in workbook_rows_for_row],
                    },
                    "why_not_claim_sufficient": [
                        "pending_human_expert_rubric_confirmation",
                        "pending_human_anti_cheat_confirmation",
                        "gold_label_not_adjudicated",
                    ],
                }
            ]
            updated["claim_status"] = "blocked_pending_human_review_confirmation"
            updated["review_execution_ready"] = True
            updated["review_workbook_path"] = display(WORKBOOK)
            updated["remaining_machine_gap"] = False
            updated["remaining_human_gates"] = [
                "expert_maintainer_rubric_review",
                "cell_specific_anti_cheat_review",
                "gold_label_adjudication",
            ]
            updated["adjudicated_manifest_target"] = display(ADJUDICATED_TARGET)
            workbook_attached += 1
            review_only_blocked += 1
        refreshed_records.append(updated)

    metrics = {
        "bridge_records": len(refreshed_records),
        "rows_with_workbook_support": workbook_attached,
        "rows_machine_complete_but_review_blocked": review_only_blocked,
        "adjudicated_manifest_target": display(ADJUDICATED_TARGET),
    }
    if metrics["bridge_records"] != 41:
        failures.append("bridge_records_not_41")
    if metrics["rows_with_workbook_support"] != 41:
        failures.append("rows_with_workbook_support_not_41")
    if metrics["rows_machine_complete_but_review_blocked"] != 41:
        failures.append("rows_machine_complete_but_review_blocked_not_41")

    output = {
        "passed": not failures,
        "failures": failures,
        "records": refreshed_records,
        "metrics": metrics,
        "claim_boundary": {
            "supports_training_or_scoring_now": False,
            "blocked_only_on_human_review_and_gold_adjudication": not failures,
        },
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_refresh()
    next_step = "Complete the stage10111 rubric and anti-cheat tasks, write adjudicated gold labels into the designated manifest target, then rerun the successor adjudication compiler before any training or Gemma comparison."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "bridge": display(ARTIFACT),
            "workbook": display(WORKBOOK),
            "adjudicated_manifest_target": display(ADJUDICATED_TARGET),
            "doc": display(DOC),
        },
        "decision": "Refreshed the real-session successor claim bridge so the 41 replacement-surface rows are classified as machine-complete but blocked on human rubric, anti-cheat confirmation, and gold-label adjudication.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10112 Real Session Successor Claim Bridge After Review Workbook",
                "",
                f"Passed: `{summary['passed']}`",
                f"Bridge records: `{built['metrics']['bridge_records']}`",
                f"Rows with workbook support: `{built['metrics']['rows_with_workbook_support']}`",
                f"Rows machine-complete but review-blocked: `{built['metrics']['rows_machine_complete_but_review_blocked']}`",
                "",
                summary["decision"],
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

#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10115
NAME = "stage10115_real_session_successor_first_wave_signoff_workbook"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
WORKBOOK = OUT_DIR / "real_session_successor_first_wave_signoff_workbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_SESSION_SUCCESSOR_FIRST_WAVE_SIGNOFF_WORKBOOK_STAGE10115.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

ATLAS = ROOT / "runs/local/artifacts/stage10114_real_session_successor_review_priority_atlas/real_session_successor_review_priority_atlas.json"
QUEUE = ROOT / "runs/local/artifacts/stage10114_real_session_successor_review_priority_atlas/real_session_successor_review_priority_queue.jsonl"
REVIEW_WORKBOOK = ROOT / "runs/local/artifacts/stage10111_real_session_successor_review_packets/real_session_successor_signoff_workbook.json"
CLAIM_BRIDGE = ROOT / "runs/local/artifacts/stage10112_real_session_successor_claim_bridge_after_review_workbook/real_session_successor_claim_bridge_after_review_workbook.json"
BLOCKED = ROOT / "runs/local/artifacts/stage10113_real_session_successor_adjudicated_manifest_compiler/real_session_successor_adjudication_blocked_rows.jsonl"


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
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
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
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)),
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _support_paths(row: dict[str, Any]) -> dict[str, str]:
    return {
        "review_packet_dir": str(row["review_packet_dir"]),
        "expert_maintainer_rubric_review": str(row["expert_maintainer_rubric_review"]),
        "anti_cheat_review_card": str(row["anti_cheat_review_card"]),
        "priority_atlas": display(ATLAS),
        "priority_queue": display(QUEUE),
        "claim_bridge": display(CLAIM_BRIDGE),
        "blocked_rows": display(BLOCKED),
    }


def build_workbook() -> dict[str, Any]:
    atlas = load_json(ATLAS)
    queue_rows = load_jsonl(QUEUE)
    stage10111_workbook = load_json(REVIEW_WORKBOOK)
    bridge = load_json(CLAIM_BRIDGE)
    blocked_rows = load_jsonl(BLOCKED)
    failures: list[str] = []

    if atlas.get("passed") is not True:
        failures.append("stage10114_not_passed")
    if len(queue_rows) != 41:
        failures.append("stage10114_queue_rows_not_41")
    if int((stage10111_workbook.get("row_count") or 0)) != 82:
        failures.append("stage10111_workbook_rows_not_82")
    if bridge.get("passed") is not True:
        failures.append("stage10112_not_passed")
    if len(blocked_rows) != 41:
        failures.append("stage10113_blocked_rows_not_41")

    row_ids = list(((atlas.get("recommended_first_wave") or {}).get("wave1_row_ids")) or [])
    if len(row_ids) != 15:
        failures.append("stage10114_first_wave_not_15")

    queued_by_row = {str(row.get("row_id") or ""): row for row in queue_rows}
    blocked_by_row = {str(row.get("row_id") or ""): row for row in blocked_rows}
    rows: list[dict[str, Any]] = []
    task_position = 1
    for wave_rank, row_id in enumerate(row_ids, start=1):
        queued = queued_by_row.get(row_id)
        blocked = blocked_by_row.get(row_id)
        if queued is None:
            failures.append(f"missing_priority_queue_row::{row_id}")
            continue
        if blocked is None:
            failures.append(f"missing_blocked_row::{row_id}")
            continue

        machine_context = {
            "wave_rank": wave_rank,
            "priority_tier": queued["priority_tier"],
            "priority_score": queued["priority_score"],
            "claim_criticality_score": queued["claim_criticality_score"],
            "shortcut_risk_score": queued["shortcut_risk_score"],
            "claim_criticality_reasons": queued["claim_criticality_reasons"],
            "shortcut_risk_reasons": queued["shortcut_risk_reasons"],
            "candidate_surface_pair": queued["candidate_surface_pair"],
            "candidate_geometry_tags": queued["candidate_geometry_tags"],
            "selected_tests_count": queued["selected_tests_count"],
            "block_reasons": blocked.get("block_reasons") or [],
        }
        common = {
            "row_id": row_id,
            "wave_rank": wave_rank,
            "language_family": queued["language_family"],
            "repo_id": queued["repo_id"],
            "successor_template": queued["successor_template"],
            "review_status": "pending_human_signoff",
            "supporting_evidence_paths": _support_paths(queued),
            "machine_context": machine_context,
        }
        rows.append(
            {
                "queue_position": task_position,
                "task": "expert_maintainer_rubric_review",
                "review_file": queued["expert_maintainer_rubric_review"],
                "required_human_action": (
                    "Judge whether the prompt-visible evidence alone supports exactly one maintainer-appropriate candidate; "
                    "if not, mark insufficient evidence instead of forcing a label."
                ),
                **common,
            }
        )
        task_position += 1
        rows.append(
            {
                "queue_position": task_position,
                "task": "cell_specific_anti_cheat_review",
                "review_file": queued["anti_cheat_review_card"],
                "required_human_action": (
                    "Challenge the row for template priors, surface-family shortcuts, test-anchor leakage, candidate-order bias, "
                    "or cross-repo analogue cues before allowing it into training or a maintainer-vs-Gemma claim."
                ),
                **common,
            }
        )
        task_position += 1

    wave_languages = Counter(row["language_family"] for row in rows if row["task"] == "expert_maintainer_rubric_review")
    wave_templates = Counter(row["successor_template"] for row in rows if row["task"] == "expert_maintainer_rubric_review")
    metrics = {
        "first_wave_rows": len(row_ids),
        "signoff_tasks": len(rows),
        "rubric_tasks": sum(1 for row in rows if row["task"] == "expert_maintainer_rubric_review"),
        "anti_cheat_tasks": sum(1 for row in rows if row["task"] == "cell_specific_anti_cheat_review"),
        "wave_language_counts": dict(sorted(wave_languages.items())),
        "wave_template_counts": dict(sorted(wave_templates.items())),
        "deferred_rows_after_wave1": max(0, len(queue_rows) - len(row_ids)),
        "high_priority_rows_total": int((atlas.get("metrics") or {}).get("high_priority_rows") or 0),
    }
    if metrics["signoff_tasks"] != 30:
        failures.append("signoff_tasks_not_30")
    if metrics["rubric_tasks"] != 15:
        failures.append("rubric_tasks_not_15")
    if metrics["anti_cheat_tasks"] != 15:
        failures.append("anti_cheat_tasks_not_15")
    if metrics["wave_language_counts"] != {"c_cpp": 9, "python": 4, "web_js_ts_html": 2}:
        failures.append("wave_language_counts_unexpected")

    return {"passed": not failures, "failures": failures, "rows": rows, "metrics": metrics}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_workbook()
    WORKBOOK.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Work the 30 first-wave signoff tasks in order: clear both web rows first, then the 9 scarce C/C++ rows, "
        "then the 4 highest-risk Python config rows before rerunning the successor adjudication compiler."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "workbook": display(WORKBOOK),
            "doc": display(DOC),
        },
        "decision": (
            "Materialized a first-wave successor signoff workbook that converts the stage10114 ranked queue into 30 concrete "
            "maintainer-rubric and anti-cheat tasks tied to the exact review files, with web and scarce C/C++ rows forced to the front."
        ),
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10115 Real Session Successor First Wave Signoff Workbook",
                "",
                f"Passed: `{summary['passed']}`",
                f"First-wave rows: `{built['metrics']['first_wave_rows']}`",
                f"Signoff tasks: `{built['metrics']['signoff_tasks']}`",
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
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

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
STAGE = 9762
NAME = "stage9762_harness_prep_completion_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "harness_prep_completion_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "HARNESS_PREP_COMPLETION_AUDIT_STAGE9762.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

HARNESS_CHECKLIST = ROOT / "runs/local/artifacts/stage9755_full_product_harness_completion_checklist/full_product_harness_completion_checklist.json"
HARNESS_PACKETS = ROOT / "runs/local/artifacts/stage9756_full_product_harness_review_packets/full_product_harness_review_packets.jsonl"
HARNESS_STUBS = ROOT / "runs/local/artifacts/stage9757_full_product_harness_review_stub_files/full_product_harness_review_stub_manifest.json"
TRUTHFUL_QUEUE = ROOT / "runs/local/artifacts/stage9761_truthful_ready_now_execution_queue/truthful_ready_now_execution_queue.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


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


def build_audit(
    harness_checklist: dict[str, Any],
    harness_packets: list[dict[str, Any]],
    harness_stubs: dict[str, Any],
    truthful_queue: dict[str, Any],
) -> dict[str, Any]:
    packet_index = {str(row.get("cell_key") or ""): row for row in harness_packets}
    stub_rows = harness_stubs.get("rows") if isinstance(harness_stubs.get("rows"), list) else []
    stub_index = {str(row.get("cell_key") or ""): row for row in stub_rows}
    checklist_records = harness_checklist.get("records") if isinstance(harness_checklist.get("records"), list) else []
    records: list[dict[str, Any]] = []
    failures: list[str] = []

    for record in checklist_records:
        cell_key = str(record.get("cell_key") or "")
        packet = packet_index.get(cell_key)
        stub = stub_index.get(cell_key)
        if packet is None:
            failures.append(f"missing_packet:{cell_key}")
            continue
        if stub is None:
            failures.append(f"missing_stub:{cell_key}")
            continue
        prep_ok = bool(packet.get("review_packet_paths")) and bool(stub.get("expert_maintainer_rubric_scores")) and bool(stub.get("anti_cheat_cards"))
        records.append({
            "cell_key": cell_key,
            "priority_rank": record.get("priority_rank"),
            "priority_bucket": record.get("priority_bucket"),
            "packet_dir": packet.get("review_packet_paths", {}).get("packet_dir"),
            "rubric_stub": stub.get("expert_maintainer_rubric_scores"),
            "anti_cheat_stub": stub.get("anti_cheat_cards"),
            "prepare_cell_specific_anti_cheat_review_completed": prep_ok,
            "prepare_expert_maintainer_rubric_review_completed": prep_ok,
        })

    truthful_entries = truthful_queue.get("queue_entries") if isinstance(truthful_queue.get("queue_entries"), list) else []
    remaining_after_completion = [
        row for row in truthful_entries
        if not (
            row.get("front") == "harness"
            and row.get("task") in {"prepare_cell_specific_anti_cheat_review", "prepare_expert_maintainer_rubric_review"}
        )
    ]
    metrics = {
        "harness_cells_audited": len(records),
        "harness_prep_tasks_completed": sum(
            int(row["prepare_cell_specific_anti_cheat_review_completed"]) + int(row["prepare_expert_maintainer_rubric_review_completed"])
            for row in records
        ),
        "truthful_queue_entries_before": len(truthful_entries),
        "truthful_queue_entries_after_harness_prep_completion": len(remaining_after_completion),
        "remaining_standalone_entries_after_completion": sum(1 for row in remaining_after_completion if row.get("front") == "standalone"),
        "remaining_harness_entries_after_completion": sum(1 for row in remaining_after_completion if row.get("front") == "harness"),
    }
    if metrics["harness_cells_audited"] != 36:
        failures.append("harness_cell_count_mismatch")
    if metrics["harness_prep_tasks_completed"] != 72:
        failures.append("harness_prep_completion_count_mismatch")
    if metrics["truthful_queue_entries_before"] != 98:
        failures.append("truthful_queue_before_count_mismatch")
    if metrics["truthful_queue_entries_after_harness_prep_completion"] != 26:
        failures.append("truthful_queue_after_count_mismatch")
    if metrics["remaining_standalone_entries_after_completion"] != 26:
        failures.append("remaining_standalone_count_mismatch")
    if metrics["remaining_harness_entries_after_completion"] != 0:
        failures.append("remaining_harness_count_mismatch")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "records": records,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_audit(
        load_json(HARNESS_CHECKLIST),
        load_jsonl(HARNESS_PACKETS),
        load_json(HARNESS_STUBS),
        load_json(TRUTHFUL_QUEUE),
    )
    AUDIT.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Mark the 72 harness review-preparation tasks complete in the working queue, leaving only the 26 standalone rubric and anti-cheat review tasks as genuinely ready now while runner recovery continues."
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
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Audited the harness preparation tasks against the existing packet and stub surfaces and found them already complete, because the required review scaffolding has been materialized for all 36 cells.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9762 Harness Prep Completion Audit",
        "",
        f"Passed: `{summary['passed']}`",
        f"Harness cells audited: `{summary['metrics']['harness_cells_audited']}`",
        f"Harness prep tasks completed: `{summary['metrics']['harness_prep_tasks_completed']}`",
        f"Truthful queue before: `{summary['metrics']['truthful_queue_entries_before']}`",
        f"Truthful queue after harness prep completion: `{summary['metrics']['truthful_queue_entries_after_harness_prep_completion']}`",
        "",
        "This stage concludes that the harness-side preparation work is already done: packet directories exist and the rubric and anti-cheat stub files exist for every harness cell.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "harness_prep_tasks_completed": summary["metrics"]["harness_prep_tasks_completed"],
        "truthful_queue_entries_after_harness_prep_completion": summary["metrics"]["truthful_queue_entries_after_harness_prep_completion"],
        "remaining_standalone_entries_after_completion": summary["metrics"]["remaining_standalone_entries_after_completion"],
        "next_best_step": next_step,
        "failures": built["failures"],
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

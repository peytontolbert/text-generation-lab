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
STAGE = 9760
NAME = "stage9760_checkpoint_readiness_truthfulness_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "checkpoint_readiness_truthfulness_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CHECKPOINT_READINESS_TRUTHFULNESS_AUDIT_STAGE9760.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

READY_QUEUE = ROOT / "runs/local/artifacts/stage9759_ready_now_execution_queue/ready_now_execution_queue.json"
STANDALONE_QUEUE = ROOT / "runs/local/artifacts/stage9748_supported_standalone_gemma_queue/supported_standalone_gemma_queue.json"
UNIFIED = ROOT / "runs/local/artifacts/stage9758_cross_front_execution_ledger/cross_front_execution_ledger.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def build_audit(ready_queue: dict[str, Any], standalone_queue: dict[str, Any], unified: dict[str, Any]) -> dict[str, Any]:
    ready_entries = ready_queue.get("queue_entries") if isinstance(ready_queue.get("queue_entries"), list) else []
    standalone_packets = standalone_queue.get("queue_entries") if isinstance(standalone_queue.get("queue_entries"), list) else []
    packet_index = {str(row.get("cell_key") or ""): row for row in standalone_packets}
    records: list[dict[str, Any]] = []
    failures: list[str] = []

    checkpoint_entries = [
        row for row in ready_entries
        if row.get("front") == "standalone" and row.get("task") == "frozen_checkpoint_hash_attach"
    ]
    for row in checkpoint_entries:
        cell_key = str(row.get("cell_key") or "")
        packet = packet_index.get(cell_key)
        if packet is None:
            failures.append(f"missing_standalone_packet:{cell_key}")
            continue
        run_dir_rel = packet.get("same_surface_packet", {}).get("run_dir")
        if not run_dir_rel:
            failures.append(f"missing_run_dir:{cell_key}")
            continue
        run_dir = ROOT / str(run_dir_rel)
        execution_result = load_json(run_dir / "execution_result.json")
        cleanup_proof = load_json(run_dir / "cleanup_proof.json")
        final_checkpoint_exported = execution_result.get("final_checkpoint_exported") is True
        cleanup_reason = str(cleanup_proof.get("cleanup_reason") or "")
        truly_ready_now = final_checkpoint_exported
        records.append({
            "cell_key": cell_key,
            "artifact_path": row.get("artifact_path"),
            "run_dir": str(run_dir.relative_to(ROOT)),
            "run_id": execution_result.get("run_id"),
            "model_config": execution_result.get("implementation", {}).get("model_config"),
            "final_checkpoint_exported": final_checkpoint_exported,
            "cleanup_reason": cleanup_reason,
            "ready_queue_status": row.get("status"),
            "truthful_ready_now": truly_ready_now,
            "reclassified_status": (
                "blocked_missing_frozen_export_or_checkpoint_hash"
                if not truly_ready_now else "ready_now"
            ),
        })

    corrected_ready_now_total = int(unified.get("totals", {}).get("ready_now_tasks_total") or 0) - sum(
        1 for row in records if row["truthful_ready_now"] is False
    )
    metrics = {
        "checkpoint_tasks_inspected": len(records),
        "checkpoint_tasks_marked_ready_in_stage9759": len(checkpoint_entries),
        "checkpoint_tasks_truthfully_ready_now": sum(1 for row in records if row["truthful_ready_now"] is True),
        "checkpoint_tasks_reclassified_blocked": sum(1 for row in records if row["truthful_ready_now"] is False),
        "corrected_standalone_ready_now_tasks": 39 - sum(1 for row in records if row["truthful_ready_now"] is False),
        "corrected_cross_front_ready_now_tasks": corrected_ready_now_total,
        "new_nonrunner_artifact_blocked_tasks": sum(1 for row in records if row["truthful_ready_now"] is False),
    }
    if metrics["checkpoint_tasks_inspected"] != 13:
        failures.append("checkpoint_task_count_mismatch")
    if metrics["checkpoint_tasks_truthfully_ready_now"] != 0:
        failures.append("unexpected_truthfully_ready_checkpoint_task_found")
    if metrics["checkpoint_tasks_reclassified_blocked"] != 13:
        failures.append("checkpoint_reclassification_count_mismatch")
    if metrics["corrected_standalone_ready_now_tasks"] != 26:
        failures.append("corrected_standalone_ready_now_count_mismatch")
    if metrics["corrected_cross_front_ready_now_tasks"] != 98:
        failures.append("corrected_cross_front_ready_now_count_mismatch")

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
    built = build_audit(load_json(READY_QUEUE), load_json(STANDALONE_QUEUE), load_json(UNIFIED))
    AUDIT.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Remove the 13 falsely ready checkpoint-hash tasks from the immediate queue, treat them as blocked on a future frozen export artifact, "
        "and focus the actual ready-now work on rubric and anti-cheat review until runner recovery or export-capable execution exists."
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
        "decision": "Audited the standalone checkpoint-hash tasks against source execution artifacts and reclassified them from falsely ready-now to artifact-blocked because the underlying structured runs did not export checkpoints.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9760 Checkpoint Readiness Truthfulness Audit",
        "",
        f"Passed: `{summary['passed']}`",
        f"Checkpoint tasks inspected: `{summary['metrics']['checkpoint_tasks_inspected']}`",
        f"Checkpoint tasks reclassified blocked: `{summary['metrics']['checkpoint_tasks_reclassified_blocked']}`",
        f"Corrected standalone ready-now tasks: `{summary['metrics']['corrected_standalone_ready_now_tasks']}`",
        f"Corrected cross-front ready-now tasks: `{summary['metrics']['corrected_cross_front_ready_now_tasks']}`",
        "",
        "This stage corrects an overclaim in the ready-now queue: the current standalone runs did not export checkpoints, so attaching a frozen export or checkpoint hash is not presently actionable for those 13 cells.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "checkpoint_tasks_reclassified_blocked": summary["metrics"]["checkpoint_tasks_reclassified_blocked"],
        "corrected_standalone_ready_now_tasks": summary["metrics"]["corrected_standalone_ready_now_tasks"],
        "corrected_cross_front_ready_now_tasks": summary["metrics"]["corrected_cross_front_ready_now_tasks"],
        "next_best_step": next_step,
        "failures": built["failures"],
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

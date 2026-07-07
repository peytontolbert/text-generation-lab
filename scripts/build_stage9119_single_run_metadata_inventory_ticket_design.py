#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9119
NAME = "stage9119_single_run_metadata_inventory_ticket_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9118 = ROOT / "runs/summaries/stage9118_metadata_inventory_runner_execution_authorization_review.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SINGLE_RUN_METADATA_INVENTORY_TICKET_STAGE9119.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TICKET = OUT_DIR / "single_run_metadata_inventory_ticket.json"

RUN_COMMAND_SPEC = [
    "python",
    "scripts/metadata_only_inventory_runner.py",
    "--datasets-root", "/arxiv/datasets",
    "--repositories-root", "/arxiv/repositories",
    "--output-dir", "runs/local/artifacts/stage912x_metadata_only_inventory_output",
    "--max-depth", "2",
    "--metadata-only",
    "--no-row-reads",
    "--no-source-body-reads",
    "--no-arxiv-writes",
    "--no-follow-symlinks",
    "--require-ticket-audit", "runs/local/artifacts/stage9114_metadata_only_real_data_inventory_ticket_audit/metadata_only_real_data_inventory_ticket_audit.json",
]

PRE_EXECUTION_REQUIREMENTS = [
    "stage9117_static_audit_passed",
    "stage9118_execution_authorization_review_passed",
    "single_run_ticket_audit_passed",
    "final_pre_execution_audit_passed",
    "output_dir_absent_or_empty_before_run",
    "output_dir_under_runs_local_artifacts",
    "max_depth_2_or_less",
    "metadata_only_flags_present",
]

FORBIDDEN_IN_TICKET_STAGE = [
    "runner_execution",
    "arxiv_access",
    "arxiv_stat",
    "dataset_file_name_read",
    "repository_root_name_read",
    "dataset_row_read",
    "repository_source_body_read",
    "arxiv_write",
    "data_mining",
    "trainer_execution",
    "model_forward",
    "network_upload",
    "cleanup_execution",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_ticket(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9118)
    checks = {
        "source_stage9118_passed": source.get("passed") is True,
        "source_stage9118_execution_not_authorized": (source.get("metrics") or {}).get("inventory_execution_authorized_next") is False,
        "run_command_spec_recorded": len(RUN_COMMAND_SPEC) >= 17,
        "pre_execution_requirements_recorded": len(PRE_EXECUTION_REQUIREMENTS) >= 8,
        "forbidden_stage_operations_recorded": len(FORBIDDEN_IN_TICKET_STAGE) >= 13,
        "registry_frontier_stage9118": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9118,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "SINGLE_RUN_METADATA_INVENTORY_TICKET_DESIGN_NO_EXECUTION",
        "run_command_spec": list(RUN_COMMAND_SPEC),
        "pre_execution_requirements": list(PRE_EXECUTION_REQUIREMENTS),
        "forbidden_in_this_stage": list(FORBIDDEN_IN_TICKET_STAGE),
        "checks": checks,
        "metrics": {
            "run_command_spec_items": len(RUN_COMMAND_SPEC),
            "pre_execution_requirements": len(PRE_EXECUTION_REQUIREMENTS),
            "forbidden_in_this_stage": len(FORBIDDEN_IN_TICKET_STAGE),
            "inventory_execution_authorized_now": False,
            "inventory_execution_authorized_next": False,
            "runner_executed_now": False,
            "arxiv_access_performed": False,
            "arxiv_stat_performed": False,
            "dataset_file_names_read_now": False,
            "repository_root_names_read_now": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "data_mining_authorized": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Designed a single-run metadata inventory ticket. This stage records the future command spec but does not authorize or execute it; final pre-execution audit remains required.",
    }


def validate_ticket(ticket: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in ticket["checks"].items() if value is not True]
    if any((ticket.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9118, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for requirement in PRE_EXECUTION_REQUIREMENTS:
        if requirement not in ticket.get("pre_execution_requirements", []):
            failures.append(f"missing_pre_execution_requirement:{requirement}")
    for operation in FORBIDDEN_IN_TICKET_STAGE:
        if operation not in ticket.get("forbidden_in_this_stage", []):
            failures.append(f"missing_forbidden_operation:{operation}")
    for key in [
        "inventory_execution_authorized_now",
        "inventory_execution_authorized_next",
        "runner_executed_now",
        "arxiv_access_performed",
        "arxiv_stat_performed",
        "dataset_file_names_read_now",
        "repository_root_names_read_now",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "data_mining_authorized",
        "trainer_executed_now",
        "model_forward_attempted",
        "training_authorized",
        "network_upload_performed",
        "cleanup_authorized_now",
    ]:
        if ticket["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    ticket = build_ticket(registry)
    failures = validate_ticket(ticket, registry)
    TICKET.write_text(json.dumps(ticket, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **ticket["metrics"]},
        "artifacts": {"ticket": str(TICKET.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": ticket["decision"] if not failures else "Single-run metadata inventory ticket design failed.",
        "next_best_step": "Audit the single-run metadata inventory ticket, then run final pre-execution audit before any inventory execution.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9119 Single-Run Metadata Inventory Ticket",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Designs the future single-run metadata inventory ticket. This stage does not execute the runner.",
        "",
        "Command spec:",
        "",
        "```text",
        " ".join(RUN_COMMAND_SPEC),
        "```",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

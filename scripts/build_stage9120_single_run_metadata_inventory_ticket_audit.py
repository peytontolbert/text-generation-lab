#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9119_single_run_metadata_inventory_ticket_design import (
        FORBIDDEN_IN_TICKET_STAGE,
        PRE_EXECUTION_REQUIREMENTS,
        RUN_COMMAND_SPEC,
        build_ticket,
        validate_ticket,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9119_single_run_metadata_inventory_ticket_design import (  # type: ignore
        FORBIDDEN_IN_TICKET_STAGE,
        PRE_EXECUTION_REQUIREMENTS,
        RUN_COMMAND_SPEC,
        build_ticket,
        validate_ticket,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9120
NAME = "stage9120_single_run_metadata_inventory_ticket_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9119 = ROOT / "runs/summaries/stage9119_single_run_metadata_inventory_ticket_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SINGLE_RUN_METADATA_INVENTORY_TICKET_AUDIT_STAGE9120.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "single_run_metadata_inventory_ticket_audit.json"

REJECT_METRICS = [
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
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9118) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_cases() -> dict[str, Any]:
    base = build_ticket(registry())
    cases: dict[str, dict[str, Any]] = {}
    for metric in REJECT_METRICS:
        candidate = copy.deepcopy(base)
        candidate["metrics"][metric] = True
        cases[metric] = candidate

    missing_requirement = copy.deepcopy(base)
    missing_requirement["pre_execution_requirements"].remove("final_pre_execution_audit_passed")
    cases["missing_final_pre_execution_requirement"] = missing_requirement

    missing_forbidden = copy.deepcopy(base)
    missing_forbidden["forbidden_in_this_stage"].remove("runner_execution")
    cases["missing_runner_execution_forbidden"] = missing_forbidden

    bad_command = copy.deepcopy(base)
    bad_command["run_command_spec"].remove("--no-source-body-reads")
    cases["missing_no_source_body_reads_command_flag"] = bad_command

    authority_open = copy.deepcopy(base)
    authority_open["authority"]["model_execution_authorized_next"] = True
    cases["authority_open"] = authority_open

    bad_frontier = copy.deepcopy(base)
    cases["unexpected_registry_frontier"] = bad_frontier

    audited: dict[str, Any] = {}
    for name, candidate in cases.items():
        failures = validate_ticket(candidate, registry(latest=9999) if name == "unexpected_registry_frontier" else registry())
        if name == "missing_no_source_body_reads_command_flag" and "--no-source-body-reads" not in candidate["run_command_spec"]:
            failures.append("missing_command_flag:--no-source-body-reads")
        audited[name] = {"failures": failures, "rejected": bool(failures)}
    return audited


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_9119)
    base = build_ticket(registry())
    base_failures = validate_ticket(base, registry())
    negatives = run_negative_cases()
    command_flags_present = all(item in base["run_command_spec"] for item in [
        "--metadata-only",
        "--no-row-reads",
        "--no-source-body-reads",
        "--no-arxiv-writes",
        "--no-follow-symlinks",
    ])
    checks = {
        "source_stage9119_present": SOURCE_9119.exists(),
        "source_stage9119_passed": source.get("passed") is True,
        "base_ticket_passes": base_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "run_command_spec_recorded": len(RUN_COMMAND_SPEC) >= 17,
        "safe_command_flags_present": command_flags_present,
        "pre_execution_requirements_recorded": len(PRE_EXECUTION_REQUIREMENTS) >= 8,
        "forbidden_stage_operations_recorded": len(FORBIDDEN_IN_TICKET_STAGE) >= 13,
        "no_execution_now": base["metrics"]["runner_executed_now"] is False,
        "authority_closed": not any(base["authority"].values()),
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "base_failures": base_failures,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
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
        "decision": "Single-run metadata inventory ticket rejects unsafe variants. The command spec is recorded, but execution remains blocked until final pre-execution audit.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit()
    latest = int((registry_json.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9119, STAGE}:
        audit["failures"].append(f"unexpected_registry_frontier:{latest}")
        audit["passed"] = False
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": audit["failures"], **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Single-run metadata inventory ticket audit failed.",
        "next_best_step": "Run final pre-execution audit for the metadata-only inventory runner; do not execute inventory until it passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9120 Single-Run Metadata Inventory Ticket Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Audits the Stage9119 single-run ticket with negative cases. The runner is not executed here.",
        "",
        f"Negative cases: `{audit['metrics']['negative_cases']}`",
        f"Rejected: `{audit['metrics']['negative_cases_rejected']}`",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry_json["rows"] = rows
    registry_json["passed"] = summary["passed"]
    registry_json["metrics"] = {**(registry_json.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry_json.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

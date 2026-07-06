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
STAGE = 8985
NAME = "stage8985_active_parquet_footer_ticket_instance_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ACTIVE_PARQUET_FOOTER_TICKET_INSTANCE_AUDIT_STAGE8985.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "active_parquet_footer_ticket_instance_audit.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8984_active_parquet_footer_ticket_instance_design.json"
SOURCE_DESIGN = ROOT / "runs/local/artifacts/stage8984_active_parquet_footer_ticket_instance_design/active_parquet_footer_ticket_instance_design.json"
SOURCE_TICKET = ROOT / "runs/local/artifacts/stage8984_active_parquet_footer_ticket_instance_design/active_parquet_footer_ticket_instance_pending_audit.json"
SELECTED_IDS = ROOT / "runs/local/artifacts/stage8984_active_parquet_footer_ticket_instance_design/selected_candidate_ids_pending_audit.jsonl"
DRY_ROWS = ROOT / "runs/local/artifacts/stage8979_zero_row_preflight_runner_contract/zero_row_preflight_dry_run_rows.jsonl"

EXPECTED_TICKET_STATE = "PENDING_AUDIT_NOT_EXECUTABLE"
EXPECTED_PROBE_TYPE = "PARQUET_FOOTER_SCHEMA_METADATA_ONLY"
REQUIRED_FALSE_FLAGS = [
    "row_body_reads_allowed",
    "repository_source_body_reads_allowed",
    "arxiv_write_allowed",
    "batch_materialization_allowed",
    "footer_access_authorized_now",
    "execution_authorized",
]
REQUIRED_FORBIDDEN_OPERATIONS = [
    "DATASET_ROW_SCAN",
    "REPOSITORY_SOURCE_BODY_READ",
    "ARXIV_WRITE",
    "TRAINING",
    "MINING",
    "MODEL_EXECUTION",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def dry_row_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("candidate_id")): row for row in rows}


def validate_ticket(ticket: dict[str, Any], selected: list[dict[str, Any]], dry_rows: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    selected_ids = [str(row.get("candidate_id")) for row in selected]
    ticket_ids = [str(item) for item in ticket.get("selected_candidate_ids") or []]
    dry_by_id = dry_row_by_id(dry_rows)
    if ticket.get("ticket_state") != EXPECTED_TICKET_STATE:
        failures.append("ticket_state")
    if ticket.get("allowed_probe_type") != EXPECTED_PROBE_TYPE:
        failures.append("allowed_probe_type")
    if ticket_ids != selected_ids:
        failures.append("ticket_selected_ids_match_selected_file")
    if len(ticket_ids) == 0 or len(ticket_ids) > int(ticket.get("max_candidates", 0)):
        failures.append("selected_count_within_limit")
    if len(ticket_ids) != len(set(ticket_ids)):
        failures.append("duplicate_ticket_ids")
    if not set(ticket_ids).issubset(dry_by_id):
        failures.append("ticket_ids_subset_of_dry_rows")
    for candidate_id in ticket_ids:
        row = dry_by_id.get(candidate_id, {})
        if row.get("planned_probe") != "future_parquet_footer_schema_ticket_required":
            failures.append(f"candidate_not_footer_planned:{candidate_id}")
        if row.get("probe_executed_now") is not False:
            failures.append(f"candidate_probe_executed:{candidate_id}")
        if row.get("arxiv_file_opened_now") is not False:
            failures.append(f"candidate_file_opened:{candidate_id}")
    for flag in REQUIRED_FALSE_FLAGS:
        if ticket.get(flag) is not False:
            failures.append(flag)
    forbidden = set(ticket.get("forbidden_operations") or [])
    for item in REQUIRED_FORBIDDEN_OPERATIONS:
        if item not in forbidden:
            failures.append(f"missing_forbidden:{item}")
    if not str(ticket.get("output_dir", "")).startswith("runs/local/artifacts/"):
        failures.append("output_dir")
    return failures


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    design = load_json(SOURCE_DESIGN)
    ticket = load_json(SOURCE_TICKET)
    selected = read_jsonl(SELECTED_IDS)
    dry_rows = read_jsonl(DRY_ROWS)
    ticket_failures = validate_ticket(ticket, selected, dry_rows)
    checks = {
        "source_stage8984_passed": source.get("passed") is True,
        "source_design_present": SOURCE_DESIGN.exists(),
        "source_ticket_present": SOURCE_TICKET.exists(),
        "selected_ids_present": SELECTED_IDS.exists() and len(selected) > 0,
        "dry_rows_present": DRY_ROWS.exists() and len(dry_rows) > 0,
        "design_checks_passed": all((design.get("checks") or {}).values()),
        "ticket_valid_pending_audit": not ticket_failures,
        "ticket_state_pending_audit": ticket.get("ticket_state") == EXPECTED_TICKET_STATE,
        "ticket_not_executable": ticket.get("execution_authorized") is False,
        "footer_access_not_authorized": ticket.get("footer_access_authorized_now") is False,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ACTIVE_PARQUET_FOOTER_TICKET_INSTANCE_AUDIT",
        "ticket_id": ticket.get("ticket_id"),
        "selected_candidate_ids": ticket.get("selected_candidate_ids") or [],
        "ticket_failures": ticket_failures,
        "checks": checks,
        "metrics": {
            "selected_candidate_count": len(selected),
            "dry_run_rows": len(dry_rows),
            "ticket_failures": len(ticket_failures),
            "ticket_pending_audit": True,
            "ticket_audit_passed": not ticket_failures,
            "footer_access_authorized_now": False,
            "execution_authorized": False,
            "parquet_footer_access_performed": False,
            "candidate_file_opened": False,
            "schema_or_header_read_performed": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Pending active parquet-footer ticket instance audit passed. The ticket is structurally valid but still not executable; footer access requires a separate execution gate.",
    }


def validate_audit(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    if card["metrics"].get("ticket_failures") != 0:
        failures.append("ticket_failures")
    for key in [
        "footer_access_authorized_now",
        "execution_authorized",
        "parquet_footer_access_performed",
        "candidate_file_opened",
        "schema_or_header_read_performed",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "network_upload_performed",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_audit(registry)
    failures = validate_audit(card)
    AUDIT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Design a separate execution gate for parquet-footer metadata-only access. Do not execute footer access until that gate passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8985 Active Parquet Footer Ticket Instance Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage audits the pending active parquet-footer ticket instance. It validates selected candidate IDs, required forbidden operations, and false execution flags. It does not execute footer access or open files.",
        "",
        f"Selected candidate count: `{summary['metrics']['selected_candidate_count']}`",
        f"Ticket failures: `{summary['metrics']['ticket_failures']}`",
        f"Execution authorized: `{summary['metrics']['execution_authorized']}`",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    existing_metrics = registry.get("metrics") or {}
    existing_latest = int(existing_metrics.get("latest_stage", -1))
    effective_latest = max(STAGE, existing_latest)
    registry["metrics"] = {
        **existing_metrics,
        "latest_stage": effective_latest,
        "latest_stage_name": NAME if effective_latest == STAGE else existing_metrics.get("latest_stage_name", NAME),
        "latest_stage_next_best_step": summary["next_best_step"] if effective_latest == STAGE else existing_metrics.get("latest_stage_next_best_step", summary["next_best_step"]),
        "max_stage": max(STAGE, int(existing_metrics.get("max_stage", 0)), existing_latest),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8985 Active Parquet Footer Ticket Instance Audit"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8985 audits the pending active parquet-footer ticket instance and keeps footer access, file opens, row/source-body reads, mining, training, model execution, and runtime closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

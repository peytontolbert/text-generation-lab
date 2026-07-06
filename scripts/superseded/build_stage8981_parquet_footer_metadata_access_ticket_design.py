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
STAGE = 8981
NAME = "stage8981_parquet_footer_metadata_access_ticket_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PARQUET_FOOTER_METADATA_ACCESS_TICKET_DESIGN_STAGE8981.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TICKET = OUT_DIR / "parquet_footer_metadata_access_ticket_design.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8980_zero_row_runner_contract_audit.json"
SOURCE_AUDIT = ROOT / "runs/local/artifacts/stage8980_zero_row_runner_contract_audit/zero_row_runner_contract_audit.json"

REQUIRED_TICKET_FIELDS = [
    "ticket_id",
    "source_stage",
    "candidate_source_artifact",
    "selected_candidate_ids",
    "allowed_probe_type",
    "max_candidates",
    "row_body_reads_allowed",
    "repository_source_body_reads_allowed",
    "arxiv_write_allowed",
    "output_dir",
    "required_artifacts",
    "rollback_plan",
]

ALLOWED_PROBE_TYPES = [
    "PARQUET_FOOTER_SCHEMA_METADATA_ONLY",
]

FORBIDDEN_OPERATIONS = [
    "PARQUET_ROW_GROUP_READ",
    "PARQUET_BATCH_MATERIALIZATION",
    "DATASET_ROW_SCAN",
    "JSONL_FIRST_LINE_READ",
    "CSV_HEADER_READ",
    "REPOSITORY_SOURCE_BODY_READ",
    "ARXIV_WRITE",
    "TRAINING",
    "MINING",
    "MODEL_EXECUTION",
    "RUNTIME_EXECUTION",
]

REQUIRED_ARTIFACTS = [
    "ticket_authorization_card.json",
    "selected_candidate_ids.jsonl",
    "parquet_footer_schema_metadata_only.jsonl",
    "footer_access_audit_card.json",
    "decision_card.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def ticket_design() -> dict[str, Any]:
    return {
        "ticket_id": "future_ticket_required_not_granted",
        "source_stage": 8980,
        "candidate_source_artifact": "runs/local/artifacts/stage8979_zero_row_preflight_runner_contract/zero_row_preflight_dry_run_rows.jsonl",
        "selected_candidate_ids": [],
        "allowed_probe_type": None,
        "max_candidates": 20,
        "row_body_reads_allowed": False,
        "repository_source_body_reads_allowed": False,
        "arxiv_write_allowed": False,
        "output_dir": "runs/local/artifacts/future_parquet_footer_metadata_access_ticket",
        "required_artifacts": REQUIRED_ARTIFACTS,
        "rollback_plan": "delete only future ticket output directory; do not touch /arxiv or training artifacts",
        "ticket_granted_now": False,
        "footer_access_authorized_now": False,
    }


def build_design(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    audit = load_json(SOURCE_AUDIT)
    ticket = ticket_design()
    checks = {
        "source_stage8980_passed": source.get("passed") is True,
        "source_audit_present": SOURCE_AUDIT.exists(),
        "source_has_parquet_future_rows": int((audit.get("metrics") or {}).get("parquet_future_ticket_rows", 0)) > 0,
        "required_ticket_fields_recorded": len(REQUIRED_TICKET_FIELDS) >= 12,
        "ticket_contains_required_fields": all(field in ticket for field in REQUIRED_TICKET_FIELDS),
        "allowed_probe_types_limited": ALLOWED_PROBE_TYPES == ["PARQUET_FOOTER_SCHEMA_METADATA_ONLY"],
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 10,
        "ticket_not_granted_now": ticket["ticket_granted_now"] is False,
        "footer_access_not_authorized_now": ticket["footer_access_authorized_now"] is False,
        "row_body_reads_forbidden": ticket["row_body_reads_allowed"] is False,
        "repository_source_body_reads_forbidden": ticket["repository_source_body_reads_allowed"] is False,
        "arxiv_write_forbidden": ticket["arxiv_write_allowed"] is False,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8980_or_8981": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {8980, STAGE},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "PARQUET_FOOTER_METADATA_ACCESS_TICKET_DESIGN_ONLY",
        "source_stage": 8980,
        "ticket_design": ticket,
        "required_ticket_fields": REQUIRED_TICKET_FIELDS,
        "allowed_probe_types": ALLOWED_PROBE_TYPES,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "required_ticket_fields": len(REQUIRED_TICKET_FIELDS),
            "allowed_probe_types": len(ALLOWED_PROBE_TYPES),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "required_artifacts": len(REQUIRED_ARTIFACTS),
            "ticket_granted_now": False,
            "footer_access_authorized_now": False,
            "parquet_footer_read_performed": False,
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
        "decision": "Parquet-footer metadata-only access ticket schema is designed but not granted. No footer access, row/body reads, /arxiv writes, mining, training, model execution, or runtime execution are authorized.",
    }


def validate_design(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8980, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "ticket_granted_now",
        "footer_access_authorized_now",
        "parquet_footer_read_performed",
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
    card = build_design(registry)
    failures = validate_design(card, registry)
    TICKET.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": failures,
            **card["metrics"],
        },
        "artifacts": {"ticket_design": str(TICKET.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Audit the parquet-footer metadata-only ticket design. Do not execute footer access until a separate explicit ticket is granted.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8981 Parquet Footer Metadata Access Ticket Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage designs the future ticket required for parquet-footer schema metadata access. It does not grant the ticket and does not read footers, rows, JSONL lines, CSV headers, repository source bodies, or write to `/arxiv`.",
        "",
        f"Required ticket fields: `{summary['metrics']['required_ticket_fields']}`",
        f"Forbidden operations: `{summary['metrics']['forbidden_operations']}`",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8981 Parquet Footer Metadata Access Ticket Design"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8981 designs a future parquet-footer metadata-only access ticket. The ticket is not granted; footer reads, row/body reads, /arxiv writes, mining, training, model execution, and runtime remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

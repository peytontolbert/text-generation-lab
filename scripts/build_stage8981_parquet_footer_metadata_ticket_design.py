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
NAME = "stage8981_parquet_footer_metadata_ticket_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PARQUET_FOOTER_METADATA_TICKET_DESIGN_STAGE8981.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TICKET_SCHEMA = OUT_DIR / "parquet_footer_metadata_ticket_schema.json"
TICKET_TEMPLATE = OUT_DIR / "parquet_footer_metadata_ticket_template_inactive.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8980_zero_row_runner_contract_audit.json"
SOURCE_AUDIT = ROOT / "runs/local/artifacts/stage8980_zero_row_runner_contract_audit/zero_row_runner_contract_audit.json"

ALLOWED_PROBE_TYPE = "PARQUET_FOOTER_SCHEMA_METADATA_ONLY"
MAX_CANDIDATES = 20

REQUIRED_TICKET_FIELDS = [
    "ticket_id",
    "source_stage",
    "source_audit_artifact",
    "selected_candidate_ids",
    "allowed_probe_type",
    "max_candidates",
    "row_body_reads_allowed",
    "repository_source_body_reads_allowed",
    "arxiv_write_allowed",
    "batch_materialization_allowed",
    "output_dir",
    "required_artifacts",
    "expiration_stage",
]

REQUIRED_ARTIFACTS = [
    "ticket_authorization_card.json",
    "selected_candidate_ids.jsonl",
    "parquet_footer_schema_metadata_only.jsonl",
    "parquet_footer_access_audit_card.json",
    "decision_card.json",
]

FORBIDDEN_OPERATIONS = [
    "DATASET_ROW_SCAN",
    "DATASET_ROW_MATERIALIZATION",
    "PARQUET_BATCH_MATERIALIZATION",
    "JSONL_FIRST_LINE_READ",
    "CSV_HEADER_READ",
    "REPOSITORY_SOURCE_BODY_READ",
    "ARXIV_WRITE",
    "CHECKPOINT_LOAD",
    "TRAINING",
    "MINING",
    "MODEL_EXECUTION",
    "RUNTIME_EXECUTION",
    "NETWORK_UPLOAD",
]

PASS_GATES = [
    "source_stage8980_passed",
    "selected_candidate_ids_subset_of_stage8979_dry_run_rows",
    "selected_candidates_count_lte_20",
    "allowed_probe_type_exact_parquet_footer_schema_metadata_only",
    "row_body_reads_allowed_false",
    "repository_source_body_reads_allowed_false",
    "arxiv_write_allowed_false",
    "batch_materialization_allowed_false",
    "output_dir_under_runs_local_artifacts",
    "required_artifacts_declared",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_ticket_schema() -> dict[str, Any]:
    return {
        "schema_name": "parquet_footer_metadata_only_access_ticket_v1",
        "stage": STAGE,
        "required_fields": REQUIRED_TICKET_FIELDS,
        "allowed_probe_type": ALLOWED_PROBE_TYPE,
        "max_candidates": MAX_CANDIDATES,
        "required_artifacts": REQUIRED_ARTIFACTS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "pass_gates": PASS_GATES,
        "defaults": {
            "row_body_reads_allowed": False,
            "repository_source_body_reads_allowed": False,
            "arxiv_write_allowed": False,
            "batch_materialization_allowed": False,
            "output_dir_root": "runs/local/artifacts",
        },
    }


def build_ticket_template() -> dict[str, Any]:
    return {
        "ticket_id": "inactive_future_parquet_footer_metadata_ticket",
        "source_stage": 8980,
        "source_audit_artifact": str(SOURCE_AUDIT.relative_to(ROOT)),
        "selected_candidate_ids": [],
        "allowed_probe_type": ALLOWED_PROBE_TYPE,
        "max_candidates": MAX_CANDIDATES,
        "row_body_reads_allowed": False,
        "repository_source_body_reads_allowed": False,
        "arxiv_write_allowed": False,
        "batch_materialization_allowed": False,
        "output_dir": "runs/local/artifacts/future_parquet_footer_metadata_only_ticket_output",
        "required_artifacts": REQUIRED_ARTIFACTS,
        "expiration_stage": 8990,
        "active": False,
        "execution_authorized": False,
    }


def validate_ticket_template(ticket: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for field in REQUIRED_TICKET_FIELDS:
        if field not in ticket:
            failures.append(f"missing_field:{field}")
    if ticket.get("allowed_probe_type") != ALLOWED_PROBE_TYPE:
        failures.append("allowed_probe_type")
    if int(ticket.get("max_candidates", 0)) > MAX_CANDIDATES:
        failures.append("max_candidates")
    for field in [
        "row_body_reads_allowed",
        "repository_source_body_reads_allowed",
        "arxiv_write_allowed",
        "batch_materialization_allowed",
        "active",
        "execution_authorized",
    ]:
        if ticket.get(field) is not False:
            failures.append(field)
    if not str(ticket.get("output_dir", "")).startswith("runs/local/artifacts/"):
        failures.append("output_dir")
    return failures


def build_design(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    source_audit = load_json(SOURCE_AUDIT)
    schema = build_ticket_schema()
    template = build_ticket_template()
    template_failures = validate_ticket_template(template)
    checks = {
        "source_stage8980_passed": source.get("passed") is True,
        "source_audit_present": SOURCE_AUDIT.exists(),
        "source_has_parquet_future_rows": int((source.get("metrics") or {}).get("parquet_future_ticket_rows", 0)) > 0,
        "schema_required_fields_declared": len(schema["required_fields"]) >= 13,
        "schema_forbidden_operations_declared": len(schema["forbidden_operations"]) >= 12,
        "schema_pass_gates_declared": len(schema["pass_gates"]) >= 10,
        "ticket_template_valid": not template_failures,
        "ticket_template_inactive": template["active"] is False,
        "ticket_execution_unauthorized": template["execution_authorized"] is False,
        "no_footer_access_performed": True,
        "no_dataset_rows_loaded": True,
        "no_repository_source_bodies_loaded": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8980_or_8981": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {8980, STAGE},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "PARQUET_FOOTER_METADATA_TICKET_DESIGN",
        "schema": schema,
        "template": template,
        "template_failures": template_failures,
        "source_route_counts": source_audit.get("route_counts", {}),
        "checks": checks,
        "metrics": {
            "required_ticket_fields": len(REQUIRED_TICKET_FIELDS),
            "required_artifacts": len(REQUIRED_ARTIFACTS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "pass_gates": len(PASS_GATES),
            "template_failures": len(template_failures),
            "ticket_active": False,
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
        "decision": "Explicit parquet-footer metadata-only access ticket is designed but inactive. Footer access remains unauthorized until a future ticket is activated and audited.",
    }


def validate_design(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8980, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "ticket_active",
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
    if card["metrics"].get("template_failures") != 0:
        failures.append("template_failures")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_design(registry)
    failures = validate_design(card, registry)
    TICKET_SCHEMA.write_text(json.dumps(card["schema"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    TICKET_TEMPLATE.write_text(json.dumps(card["template"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "parquet_footer_metadata_ticket_design.json").write_text(json.dumps({k: v for k, v in card.items() if k not in {"schema", "template"}}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        "artifacts": {
            "ticket_schema": str(TICKET_SCHEMA.relative_to(ROOT)),
            "ticket_template": str(TICKET_TEMPLATE.relative_to(ROOT)),
            "design": str((OUT_DIR / "parquet_footer_metadata_ticket_design.json").relative_to(ROOT)),
        },
        "decision": card["decision"],
        "next_best_step": "Audit the inactive parquet-footer metadata ticket schema. Do not execute footer access until a later active ticket passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8981 Parquet Footer Metadata Ticket Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage designs an inactive future ticket for parquet-footer schema metadata access. It does not open candidate files, read footers, materialize batches, read dataset rows, read repository source bodies, mine, train, or execute models.",
        "",
        f"Required ticket fields: `{summary['metrics']['required_ticket_fields']}`",
        f"Forbidden operations: `{summary['metrics']['forbidden_operations']}`",
        f"Ticket active: `{summary['metrics']['ticket_active']}`",
        f"Execution authorized: `{summary['metrics']['execution_authorized']}`",
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
    marker = "## Stage8981 Parquet Footer Metadata Ticket Design"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8981 designs an inactive future ticket for parquet-footer metadata-only schema access. It does not perform footer access and keeps row reads, source-body reads, mining, training, and runtime closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

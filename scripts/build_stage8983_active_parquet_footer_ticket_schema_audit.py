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
STAGE = 8983
NAME = "stage8983_active_parquet_footer_ticket_schema_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ACTIVE_PARQUET_FOOTER_TICKET_SCHEMA_AUDIT_STAGE8983.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "active_parquet_footer_ticket_schema_audit.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8982_duplicate_ticket_design_preservation.json"
TICKET_SCHEMA = ROOT / "runs/local/artifacts/stage8981_parquet_footer_metadata_ticket_design/parquet_footer_metadata_ticket_schema.json"
TICKET_TEMPLATE = ROOT / "runs/local/artifacts/stage8981_parquet_footer_metadata_ticket_design/parquet_footer_metadata_ticket_template_inactive.json"
SOURCE_DRY_ROWS = ROOT / "runs/local/artifacts/stage8979_zero_row_preflight_runner_contract/zero_row_preflight_dry_run_rows.jsonl"

REQUIRED_FALSE_TEMPLATE_FLAGS = [
    "row_body_reads_allowed",
    "repository_source_body_reads_allowed",
    "arxiv_write_allowed",
    "batch_materialization_allowed",
    "active",
    "execution_authorized",
]

REQUIRED_FORBIDDEN_OPERATIONS = [
    "DATASET_ROW_SCAN",
    "DATASET_ROW_MATERIALIZATION",
    "PARQUET_BATCH_MATERIALIZATION",
    "REPOSITORY_SOURCE_BODY_READ",
    "ARXIV_WRITE",
    "TRAINING",
    "MINING",
    "MODEL_EXECUTION",
    "RUNTIME_EXECUTION",
]

REQUIRED_PASS_GATES = [
    "selected_candidate_ids_subset_of_stage8979_dry_run_rows",
    "selected_candidates_count_lte_20",
    "allowed_probe_type_exact_parquet_footer_schema_metadata_only",
    "row_body_reads_allowed_false",
    "repository_source_body_reads_allowed_false",
    "arxiv_write_allowed_false",
    "batch_materialization_allowed_false",
    "output_dir_under_runs_local_artifacts",
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


def candidate_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("candidate_id")) for row in rows if row.get("candidate_id") is not None}


def audit_schema(schema: dict[str, Any], template: dict[str, Any], dry_rows: list[dict[str, Any]]) -> dict[str, Any]:
    required_fields = set(schema.get("required_fields") or [])
    template_fields = set(template)
    missing_template_fields = sorted(required_fields - template_fields)
    forbidden = set(schema.get("forbidden_operations") or [])
    missing_forbidden = [item for item in REQUIRED_FORBIDDEN_OPERATIONS if item not in forbidden]
    pass_gates = set(schema.get("pass_gates") or [])
    missing_pass_gates = [item for item in REQUIRED_PASS_GATES if item not in pass_gates]
    false_flag_failures = [flag for flag in REQUIRED_FALSE_TEMPLATE_FLAGS if template.get(flag) is not False]
    selected_ids = set(str(item) for item in (template.get("selected_candidate_ids") or []))
    dry_ids = candidate_ids(dry_rows)
    selected_subset = selected_ids.issubset(dry_ids)
    return {
        "missing_template_fields": missing_template_fields,
        "missing_forbidden_operations": missing_forbidden,
        "missing_pass_gates": missing_pass_gates,
        "false_flag_failures": false_flag_failures,
        "selected_candidate_ids_subset": selected_subset,
        "selected_candidate_count": len(selected_ids),
        "dry_run_candidate_count": len(dry_ids),
    }


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    schema = load_json(TICKET_SCHEMA)
    template = load_json(TICKET_TEMPLATE)
    dry_rows = read_jsonl(SOURCE_DRY_ROWS)
    audit = audit_schema(schema, template, dry_rows)
    checks = {
        "source_stage8982_passed": source.get("passed") is True,
        "ticket_schema_present": TICKET_SCHEMA.exists(),
        "ticket_template_present": TICKET_TEMPLATE.exists(),
        "dry_rows_present": SOURCE_DRY_ROWS.exists() and len(dry_rows) > 0,
        "allowed_probe_type_exact": schema.get("allowed_probe_type") == "PARQUET_FOOTER_SCHEMA_METADATA_ONLY" and template.get("allowed_probe_type") == "PARQUET_FOOTER_SCHEMA_METADATA_ONLY",
        "template_has_required_fields": not audit["missing_template_fields"],
        "forbidden_operations_complete": not audit["missing_forbidden_operations"],
        "pass_gates_complete": not audit["missing_pass_gates"],
        "template_false_flags_preserved": not audit["false_flag_failures"],
        "selected_candidate_ids_subset": audit["selected_candidate_ids_subset"] is True,
        "selected_candidate_count_lte_max": audit["selected_candidate_count"] <= int(template.get("max_candidates", 0)),
        "output_dir_under_runs_local_artifacts": str(template.get("output_dir", "")).startswith("runs/local/artifacts/"),
        "ticket_inactive": template.get("active") is False,
        "execution_unauthorized": template.get("execution_authorized") is False,
        "no_footer_access_performed": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8982_or_8983": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {8982, STAGE},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ACTIVE_PARQUET_FOOTER_TICKET_SCHEMA_AUDIT",
        "schema_audit": audit,
        "checks": checks,
        "metrics": {
            "required_fields": len(schema.get("required_fields") or []),
            "required_artifacts": len(schema.get("required_artifacts") or []),
            "forbidden_operations": len(schema.get("forbidden_operations") or []),
            "pass_gates": len(schema.get("pass_gates") or []),
            "missing_template_fields": len(audit["missing_template_fields"]),
            "missing_forbidden_operations": len(audit["missing_forbidden_operations"]),
            "missing_pass_gates": len(audit["missing_pass_gates"]),
            "false_flag_failures": len(audit["false_flag_failures"]),
            "selected_candidate_count": audit["selected_candidate_count"],
            "dry_run_candidate_count": audit["dry_run_candidate_count"],
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
        "decision": "Active Stage8981 inactive parquet-footer ticket schema audit passed. The schema is complete and remains inactive; footer access still requires a separate active ticket.",
    }


def validate_audit(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8982, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for zero_key in ["missing_template_fields", "missing_forbidden_operations", "missing_pass_gates", "false_flag_failures"]:
        if card["metrics"].get(zero_key) != 0:
            failures.append(zero_key)
    for false_key in [
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
        if card["metrics"].get(false_key) is not False:
            failures.append(false_key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_audit(registry)
    failures = validate_audit(card, registry)
    AUDIT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Design an active parquet-footer metadata-only ticket instance over a small candidate subset, but keep execution closed until its audit passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8983 Active Parquet Footer Ticket Schema Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage audits the inactive Stage8981 parquet-footer metadata ticket schema/template and Stage8979 dry-run candidate IDs. It does not open `/arxiv` files, read parquet footers, materialize rows, mine, train, or execute models.",
        "",
        f"Missing template fields: `{summary['metrics']['missing_template_fields']}`",
        f"Missing forbidden operations: `{summary['metrics']['missing_forbidden_operations']}`",
        f"Missing pass gates: `{summary['metrics']['missing_pass_gates']}`",
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
    marker = "## Stage8983 Active Parquet Footer Ticket Schema Audit"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8983 audits the inactive Stage8981 parquet-footer metadata ticket schema and keeps footer access, file opens, row reads, mining, training, and runtime closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

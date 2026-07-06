#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8980
NAME = "stage8980_zero_row_runner_contract_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ZERO_ROW_RUNNER_CONTRACT_AUDIT_STAGE8980.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "zero_row_runner_contract_audit.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8979_zero_row_preflight_runner_contract.json"
CONTRACT = ROOT / "runs/local/artifacts/stage8979_zero_row_preflight_runner_contract/zero_row_preflight_runner_contract.json"
DRY_ROWS = ROOT / "runs/local/artifacts/stage8979_zero_row_preflight_runner_contract/zero_row_preflight_dry_run_rows.jsonl"

REQUIRED_DRY_ROW_FIELDS = [
    "candidate_id",
    "route",
    "relative_path",
    "extension",
    "planned_probe",
    "probe_executed_now",
    "arxiv_file_opened_now",
    "dataset_rows_loaded",
    "repository_source_bodies_loaded",
    "status",
]

REQUIRED_FUTURE_TICKET_FIELDS = [
    "ticket_id",
    "source_stage",
    "selected_candidate_ids",
    "allowed_probe_type",
    "max_candidates",
    "row_body_reads_allowed",
    "repository_source_body_reads_allowed",
    "arxiv_write_allowed",
    "output_dir",
    "required_artifacts",
]

FUTURE_TICKET_ALLOWED_PROBE_TYPES = [
    "PARQUET_FOOTER_SCHEMA_METADATA_ONLY",
]

FUTURE_TICKET_FORBIDDEN = [
    "JSONL_FIRST_LINE_READ",
    "CSV_HEADER_READ",
    "PARQUET_BATCH_MATERIALIZATION",
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


def missing_fields(row: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_DRY_ROW_FIELDS if field not in row]


def count_routes(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get("route")) for row in rows).items()))


def build_future_ticket_schema() -> dict[str, Any]:
    return {
        "ticket_name": "future_metadata_only_parquet_footer_schema_access_ticket_v1",
        "fields": REQUIRED_FUTURE_TICKET_FIELDS,
        "allowed_probe_types": FUTURE_TICKET_ALLOWED_PROBE_TYPES,
        "forbidden_operations": FUTURE_TICKET_FORBIDDEN,
        "defaults": {
            "row_body_reads_allowed": False,
            "repository_source_body_reads_allowed": False,
            "arxiv_write_allowed": False,
            "max_candidates": 20,
            "output_dir_root": "runs/local/artifacts",
        },
        "required_artifacts": [
            "ticket_authorization_card.json",
            "selected_candidate_ids.jsonl",
            "parquet_footer_schema_metadata_only.jsonl",
            "footer_access_audit_card.json",
            "decision_card.json",
        ],
    }


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(CONTRACT)
    rows = read_jsonl(DRY_ROWS)
    field_failures = {row.get("candidate_id", f"row_{idx}"): missing_fields(row) for idx, row in enumerate(rows) if missing_fields(row)}
    probe_executed = [row for row in rows if row.get("probe_executed_now") is not False]
    file_opened = [row for row in rows if row.get("arxiv_file_opened_now") is not False]
    row_loaded = [row for row in rows if row.get("dataset_rows_loaded") is not False]
    source_read = [row for row in rows if row.get("repository_source_bodies_loaded") is not False]
    parquet_future_rows = [row for row in rows if row.get("planned_probe") == "future_parquet_footer_schema_ticket_required"]
    ticket_schema = build_future_ticket_schema()
    checks = {
        "source_stage8979_passed": source.get("passed") is True,
        "contract_present": CONTRACT.exists(),
        "dry_rows_present": DRY_ROWS.exists() and len(rows) > 0,
        "dry_rows_match_contract_count": len(rows) == int((contract.get("metrics") or {}).get("dry_run_rows", -1)),
        "required_fields_present": not field_failures,
        "all_probes_not_executed": not probe_executed,
        "all_arxiv_files_not_opened": not file_opened,
        "all_dataset_rows_not_loaded": not row_loaded,
        "all_repository_source_bodies_not_loaded": not source_read,
        "parquet_future_rows_present": len(parquet_future_rows) > 0,
        "future_ticket_schema_declared": len(ticket_schema["fields"]) >= 10,
        "future_ticket_forbids_rows_source_training": all(item in ticket_schema["forbidden_operations"] for item in ["DATASET_ROW_SCAN", "REPOSITORY_SOURCE_BODY_READ", "TRAINING", "MINING"]),
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8979_or_8980": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {8979, STAGE},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ZERO_ROW_RUNNER_CONTRACT_AUDIT",
        "route_counts": count_routes(rows),
        "field_failures": field_failures,
        "future_ticket_schema": ticket_schema,
        "checks": checks,
        "metrics": {
            "dry_run_rows": len(rows),
            "route_count": len(count_routes(rows)),
            "field_failure_rows": len(field_failures),
            "probe_executed_rows": len(probe_executed),
            "arxiv_file_opened_rows": len(file_opened),
            "dataset_rows_loaded_rows": len(row_loaded),
            "repository_source_body_read_rows": len(source_read),
            "parquet_future_ticket_rows": len(parquet_future_rows),
            "future_ticket_fields": len(ticket_schema["fields"]),
            "future_ticket_forbidden_operations": len(ticket_schema["forbidden_operations"]),
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
        "decision": "Zero-row runner contract audit passed. The future ticket schema may allow parquet footer schema metadata access only, but row/body reads, /arxiv writes, mining, training, model execution, and runtime remain closed.",
    }


def validate_audit(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8979, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
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
    for key in [
        "field_failure_rows",
        "probe_executed_rows",
        "arxiv_file_opened_rows",
        "dataset_rows_loaded_rows",
        "repository_source_body_read_rows",
    ]:
        if card["metrics"].get(key) != 0:
            failures.append(key)
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
        "next_best_step": "Design the explicit parquet-footer metadata-only access ticket. Do not execute footer access until that ticket passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8980 Zero-Row Runner Contract Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage audits Stage8979 dry-run rows and declares a future ticket schema. It does not open `/arxiv` files, read schemas/headers/rows, read repository source bodies, mine, train, or execute models.",
        "",
        f"Dry-run rows: `{summary['metrics']['dry_run_rows']}`",
        f"Parquet future-ticket rows: `{summary['metrics']['parquet_future_ticket_rows']}`",
        f"Probe executed rows: `{summary['metrics']['probe_executed_rows']}`",
        f"Arxiv file opened rows: `{summary['metrics']['arxiv_file_opened_rows']}`",
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
    marker = "## Stage8980 Zero-Row Runner Contract Audit"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8980 audits Stage8979 dry-run rows and introduces a future ticket schema for parquet-footer metadata-only access while keeping all file opens, row/source-body reads, mining, training, and runtime closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

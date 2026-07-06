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
STAGE = 8984
NAME = "stage8984_active_parquet_footer_ticket_instance_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ACTIVE_PARQUET_FOOTER_TICKET_INSTANCE_DESIGN_STAGE8984.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TICKET = OUT_DIR / "active_parquet_footer_ticket_instance_pending_audit.json"
SELECTED_IDS = OUT_DIR / "selected_candidate_ids_pending_audit.jsonl"
DESIGN = OUT_DIR / "active_parquet_footer_ticket_instance_design.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8983_active_parquet_footer_ticket_schema_audit.json"
SCHEMA = ROOT / "runs/local/artifacts/stage8981_parquet_footer_metadata_ticket_design/parquet_footer_metadata_ticket_schema.json"
DRY_ROWS = ROOT / "runs/local/artifacts/stage8979_zero_row_preflight_runner_contract/zero_row_preflight_dry_run_rows.jsonl"

SELECTED_LIMIT = 5
ALLOWED_PROBE_TYPE = "PARQUET_FOOTER_SCHEMA_METADATA_ONLY"
TICKET_STATE = "PENDING_AUDIT_NOT_EXECUTABLE"

REQUIRED_EXECUTION_FALSE_FLAGS = [
    "footer_access_authorized_now",
    "execution_authorized",
    "parquet_footer_access_performed",
    "candidate_file_opened",
    "dataset_rows_loaded",
    "repository_source_bodies_loaded",
    "arxiv_write_authorized",
    "training_authorized",
    "data_mining_authorized",
    "model_execution_attempted",
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


def parquet_candidate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if row.get("planned_probe") == "future_parquet_footer_schema_ticket_required"
        and str(row.get("extension", "")).lower() == ".parquet"
        and row.get("probe_executed_now") is False
        and row.get("arxiv_file_opened_now") is False
        and row.get("dataset_rows_loaded") is False
    ]


def select_candidate_ids(rows: list[dict[str, Any]], *, limit: int = SELECTED_LIMIT) -> list[dict[str, Any]]:
    selected = []
    for row in parquet_candidate_rows(rows)[:limit]:
        selected.append({
            "candidate_id": row.get("candidate_id"),
            "relative_path": row.get("relative_path"),
            "route": row.get("route"),
            "extension": row.get("extension"),
            "selected_from_stage8979_dry_run": True,
            "candidate_file_opened": False,
            "footer_access_authorized_now": False,
        })
    return selected


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def build_ticket(selected: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticket_id": "stage8984_pending_audit_parquet_footer_metadata_subset",
        "ticket_state": TICKET_STATE,
        "source_stage": 8983,
        "source_schema_artifact": str(SCHEMA.relative_to(ROOT)),
        "candidate_source_artifact": str(DRY_ROWS.relative_to(ROOT)),
        "selected_candidate_ids": [row["candidate_id"] for row in selected],
        "selected_candidate_count": len(selected),
        "allowed_probe_type": ALLOWED_PROBE_TYPE,
        "max_candidates": SELECTED_LIMIT,
        "row_body_reads_allowed": False,
        "repository_source_body_reads_allowed": False,
        "arxiv_write_allowed": False,
        "batch_materialization_allowed": False,
        "footer_access_authorized_now": False,
        "execution_authorized": False,
        "output_dir": "runs/local/artifacts/future_stage898x_parquet_footer_metadata_only_access",
        "required_artifacts": schema.get("required_artifacts") or [],
        "forbidden_operations": schema.get("forbidden_operations") or [],
        "pass_gates": schema.get("pass_gates") or [],
        "expiration_stage": 8990,
    }


def validate_ticket(ticket: dict[str, Any], selected: list[dict[str, Any]], dry_rows: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    dry_ids = {str(row.get("candidate_id")) for row in dry_rows}
    ids = [str(item) for item in ticket.get("selected_candidate_ids") or []]
    if ticket.get("ticket_state") != TICKET_STATE:
        failures.append("ticket_state")
    if ticket.get("allowed_probe_type") != ALLOWED_PROBE_TYPE:
        failures.append("allowed_probe_type")
    if len(ids) == 0 or len(ids) > SELECTED_LIMIT:
        failures.append("selected_candidate_count")
    if not set(ids).issubset(dry_ids):
        failures.append("selected_candidate_ids_subset")
    if len(ids) != len(set(ids)):
        failures.append("duplicate_candidate_ids")
    for field in [
        "row_body_reads_allowed",
        "repository_source_body_reads_allowed",
        "arxiv_write_allowed",
        "batch_materialization_allowed",
        "footer_access_authorized_now",
        "execution_authorized",
    ]:
        if ticket.get(field) is not False:
            failures.append(field)
    if not str(ticket.get("output_dir", "")).startswith("runs/local/artifacts/"):
        failures.append("output_dir")
    if any(row.get("candidate_file_opened") is not False for row in selected):
        failures.append("selected_candidate_file_opened")
    return failures


def build_design(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    schema = load_json(SCHEMA)
    dry_rows = read_jsonl(DRY_ROWS)
    parquet_rows = parquet_candidate_rows(dry_rows)
    selected = select_candidate_ids(dry_rows)
    ticket = build_ticket(selected, schema)
    ticket_failures = validate_ticket(ticket, selected, dry_rows)
    latest_stage = int((registry.get("metrics") or {}).get("latest_stage", -1))
    checks = {
        "source_stage8983_passed": source.get("passed") is True,
        "schema_present": SCHEMA.exists(),
        "dry_rows_present": DRY_ROWS.exists() and len(dry_rows) > 0,
        "parquet_candidate_rows_present": len(parquet_rows) >= SELECTED_LIMIT,
        "selected_candidates_present": len(selected) == SELECTED_LIMIT,
        "ticket_valid_pending_audit": not ticket_failures,
        "ticket_state_pending_audit": ticket["ticket_state"] == TICKET_STATE,
        "footer_access_not_authorized": ticket["footer_access_authorized_now"] is False,
        "execution_not_authorized": ticket["execution_authorized"] is False,
        "no_candidate_files_opened": all(row["candidate_file_opened"] is False for row in selected),
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8983_to_8990": 8983 <= latest_stage <= 8990,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ACTIVE_PARQUET_FOOTER_TICKET_INSTANCE_DESIGN_PENDING_AUDIT",
        "ticket": ticket,
        "selected_candidates": selected,
        "ticket_failures": ticket_failures,
        "checks": checks,
        "metrics": {
            "dry_run_rows": len(dry_rows),
            "parquet_candidate_rows": len(parquet_rows),
            "selected_candidate_count": len(selected),
            "ticket_failures": len(ticket_failures),
            "ticket_pending_audit": True,
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
        "decision": "Active parquet-footer ticket instance was designed in pending-audit state over a five-candidate subset. It does not authorize or execute footer access.",
    }


def validate_design(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if not (8983 <= latest <= 8990):
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    if card["metrics"].get("ticket_failures") != 0:
        failures.append("ticket_failures")
    for key in REQUIRED_EXECUTION_FALSE_FLAGS + [
        "schema_or_header_read_performed",
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
    TICKET.write_text(json.dumps(card["ticket"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(SELECTED_IDS, card["selected_candidates"])
    DESIGN.write_text(json.dumps({k: v for k, v in card.items() if k not in {"ticket", "selected_candidates"}}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
            "ticket": str(TICKET.relative_to(ROOT)),
            "selected_candidate_ids": str(SELECTED_IDS.relative_to(ROOT)),
            "design": str(DESIGN.relative_to(ROOT)),
        },
        "decision": card["decision"],
        "next_best_step": "Audit the pending active parquet-footer ticket instance. Do not execute footer access until that audit passes and a separate execution gate is granted.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8984 Active Parquet Footer Ticket Instance Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage designs a pending-audit active ticket instance over selected Stage8979 dry-run candidate IDs. It does not open files, read parquet footers, read rows, read source bodies, mine, train, or execute models.",
        "",
        f"Selected candidate count: `{summary['metrics']['selected_candidate_count']}`",
        f"Ticket pending audit: `{summary['metrics']['ticket_pending_audit']}`",
        f"Footer access authorized now: `{summary['metrics']['footer_access_authorized_now']}`",
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
    marker = "## Stage8984 Active Parquet Footer Ticket Instance Design"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8984 designs a pending-audit active parquet-footer ticket instance over a small candidate subset. It does not authorize or execute footer access.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

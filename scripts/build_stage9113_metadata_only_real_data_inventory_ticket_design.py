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
STAGE = 9113
NAME = "stage9113_metadata_only_real_data_inventory_ticket_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9112 = ROOT / "runs/summaries/stage9112_current_frontier_reconciliation_after_metadata_preflight_graph.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "METADATA_ONLY_REAL_DATA_INVENTORY_TICKET_STAGE9113.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TICKET = OUT_DIR / "metadata_only_real_data_inventory_ticket.json"

PROTECTED_ROOTS = ["/arxiv", "/arxiv/datasets", "/arxiv/repositories"]

ALLOWED_FUTURE_OPERATIONS = [
    "check_root_exists",
    "record_root_directory_metadata_without_following_symlinks",
    "list_dataset_file_names_one_level_or_bounded_depth",
    "list_repository_root_names_one_level",
    "record_file_size_bytes",
    "record_file_mtime_epoch",
    "record_file_extension",
    "record_directory_entry_count_without_body_reads",
    "write_inventory_outputs_under_runs_local_artifacts_only",
]

FORBIDDEN_FUTURE_OPERATIONS = [
    "read_dataset_rows",
    "read_dataset_parquet_row_groups",
    "read_dataset_jsonl_bodies",
    "read_repository_source_bodies",
    "follow_symlink_outside_arxiv",
    "write_to_arxiv",
    "delete_from_arxiv",
    "start_mining",
    "materialize_route_cards",
    "translate_route_to_loss",
    "invoke_trainer_contract_only",
    "execute_trainer",
    "model_forward",
    "decoder_ce_training",
    "denoise_ce_training",
    "network_upload",
    "cleanup_execution",
]

REQUIRED_OUTPUTS = [
    "arxiv_root_metadata_card.json",
    "dataset_file_inventory_metadata_only.jsonl",
    "repository_root_inventory_metadata_only.jsonl",
    "inventory_scope_card.json",
    "protected_path_policy_card.json",
    "source_output_ticket_requirement_card.json",
    "route_card_handoff_block_card.json",
    "real_data_availability_preflight_decision_card.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_ticket(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9112)
    checks = {
        "source_stage9112_passed": source.get("passed") is True,
        "protected_roots_recorded": set(PROTECTED_ROOTS) == {"/arxiv", "/arxiv/datasets", "/arxiv/repositories"},
        "allowed_future_operations_recorded": len(ALLOWED_FUTURE_OPERATIONS) >= 9,
        "forbidden_future_operations_recorded": len(FORBIDDEN_FUTURE_OPERATIONS) >= 16,
        "required_outputs_recorded": len(REQUIRED_OUTPUTS) >= 8,
        "registry_frontier_stage9112": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9112,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "METADATA_ONLY_REAL_DATA_INVENTORY_TICKET_DESIGN_NO_ACCESS_NOW",
        "protected_roots": list(PROTECTED_ROOTS),
        "allowed_future_operations": list(ALLOWED_FUTURE_OPERATIONS),
        "forbidden_future_operations": list(FORBIDDEN_FUTURE_OPERATIONS),
        "required_outputs": list(REQUIRED_OUTPUTS),
        "checks": checks,
        "metrics": {
            "protected_roots": len(PROTECTED_ROOTS),
            "allowed_future_operations": len(ALLOWED_FUTURE_OPERATIONS),
            "forbidden_future_operations": len(FORBIDDEN_FUTURE_OPERATIONS),
            "required_outputs": len(REQUIRED_OUTPUTS),
            "arxiv_access_performed": False,
            "arxiv_stat_performed": False,
            "dataset_file_names_read_now": False,
            "repository_root_names_read_now": False,
            "dataset_rows_loaded": False,
            "dataset_parquet_groups_read": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "data_mining_authorized": False,
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
            "trainer_executed_now": False,
            "contract_only_invoked_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Designed a future metadata-only inventory ticket. This stage does not access/stat /arxiv, read file names, read dataset rows, read parquet groups, read repository source bodies, write to /arxiv, mine data, materialize route cards, invoke trainer paths, run model forward, upload, cleanup, or train.",
    }


def validate_ticket(ticket: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in ticket["checks"].items() if value is not True]
    if any((ticket.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9112, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for root in PROTECTED_ROOTS:
        if root not in ticket.get("protected_roots", []):
            failures.append(f"missing_protected_root:{root}")
    for operation in FORBIDDEN_FUTURE_OPERATIONS:
        if operation not in ticket.get("forbidden_future_operations", []):
            failures.append(f"missing_forbidden_operation:{operation}")
    for output in REQUIRED_OUTPUTS:
        if output not in ticket.get("required_outputs", []):
            failures.append(f"missing_required_output:{output}")
    for key in [
        "arxiv_access_performed",
        "arxiv_stat_performed",
        "dataset_file_names_read_now",
        "repository_root_names_read_now",
        "dataset_rows_loaded",
        "dataset_parquet_groups_read",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "data_mining_authorized",
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
        "trainer_executed_now",
        "contract_only_invoked_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
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
        "decision": ticket["decision"] if not failures else "Metadata-only real data inventory ticket design failed.",
        "next_best_step": "Audit the metadata-only inventory ticket with negative cases before any /arxiv metadata inventory.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9113 Metadata-Only Real Data Inventory Ticket",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Designs the future metadata-only inventory ticket. This stage does not access `/arxiv`, read dataset rows, read source bodies, invoke trainer paths, upload, cleanup, or train.",
        "",
        "Allowed future operations:",
        "",
        *[f"- {item}" for item in ALLOWED_FUTURE_OPERATIONS],
        "",
        "Forbidden future operations:",
        "",
        *[f"- {item}" for item in FORBIDDEN_FUTURE_OPERATIONS],
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

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
STAGE = 9121
NAME = "stage9121_metadata_inventory_final_pre_execution_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9117 = ROOT / "runs/summaries/stage9117_metadata_only_inventory_runner_static_audit.json"
SOURCE_9118 = ROOT / "runs/summaries/stage9118_metadata_inventory_runner_execution_authorization_review.json"
SOURCE_9120 = ROOT / "runs/summaries/stage9120_single_run_metadata_inventory_ticket_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "METADATA_INVENTORY_FINAL_PRE_EXECUTION_AUDIT_STAGE9121.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "metadata_inventory_final_pre_execution_audit.json"

FINAL_REQUIREMENTS = [
    "stage9117_static_audit_passed",
    "stage9118_execution_authorization_review_passed",
    "stage9120_single_run_ticket_audit_passed",
    "explicit_user_inventory_execution_request_present",
    "output_dir_under_runs_local_artifacts",
    "safe_command_flags_present",
    "metadata_only_runner_static_clean",
    "no_row_or_source_body_read_flags_present",
    "no_arxiv_write_flag_present",
    "no_follow_symlinks_flag_present",
]

CURRENT_BLOCKERS = [
    "explicit_user_inventory_execution_request_missing",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    s9117 = load_json(SOURCE_9117)
    s9118 = load_json(SOURCE_9118)
    s9120 = load_json(SOURCE_9120)
    checks = {
        "source_stage9117_passed": s9117.get("passed") is True,
        "source_stage9118_passed": s9118.get("passed") is True,
        "source_stage9120_passed": s9120.get("passed") is True,
        "stage9117_runner_not_executed": (s9117.get("metrics") or {}).get("runner_executed_now") is False,
        "stage9118_execution_not_authorized": (s9118.get("metrics") or {}).get("inventory_execution_authorized_next") is False,
        "stage9120_ticket_rejected_negative_cases": (s9120.get("metrics") or {}).get("negative_cases_rejected") == (s9120.get("metrics") or {}).get("negative_cases"),
        "final_requirements_recorded": len(FINAL_REQUIREMENTS) >= 10,
        "current_blockers_recorded": len(CURRENT_BLOCKERS) >= 1,
        "registry_frontier_stage9120": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9120,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "FINAL_PRE_EXECUTION_AUDIT_REVIEW_ONLY_EXECUTION_NOT_AUTHORIZED",
        "final_requirements": list(FINAL_REQUIREMENTS),
        "current_blockers": list(CURRENT_BLOCKERS),
        "checks": checks,
        "metrics": {
            "final_requirements": len(FINAL_REQUIREMENTS),
            "current_blockers": len(CURRENT_BLOCKERS),
            "explicit_user_inventory_execution_request_present": False,
            "final_pre_execution_audit_passed_for_execution": False,
            "inventory_execution_authorized_now": False,
            "inventory_execution_authorized_next": False,
            "runner_executed_now": False,
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
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Final pre-execution audit reviewed the metadata-only inventory path but did not authorize execution because an explicit user inventory execution request is missing. No inventory, /arxiv access/stat, row reads, source-body reads, writes, mining, trainer/model path, upload, cleanup, or training occurred.",
    }


def validate_audit(audit: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in audit["checks"].items() if value is not True]
    if any((audit.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9120, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for requirement in FINAL_REQUIREMENTS:
        if requirement not in audit.get("final_requirements", []):
            failures.append(f"missing_final_requirement:{requirement}")
    if "explicit_user_inventory_execution_request_missing" not in audit.get("current_blockers", []):
        failures.append("missing_current_blocker:explicit_user_inventory_execution_request_missing")
    for key in [
        "explicit_user_inventory_execution_request_present",
        "final_pre_execution_audit_passed_for_execution",
        "inventory_execution_authorized_now",
        "inventory_execution_authorized_next",
        "runner_executed_now",
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
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "network_upload_performed",
        "cleanup_authorized_now",
    ]:
        if audit["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit(registry)
    failures = validate_audit(audit, registry)
    audit["passed"] = not failures
    audit["failures"] = failures
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Metadata inventory final pre-execution audit failed.",
        "next_best_step": "Wait for explicit user authorization before executing metadata-only inventory; otherwise return to compiler/training recovery work.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9121 Metadata Inventory Final Pre-Execution Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This is a review-only final pre-execution audit. It does not authorize or execute inventory because explicit user inventory execution authorization is missing.",
        "",
        "Current blockers:",
        "",
        *[f"- {item}" for item in CURRENT_BLOCKERS],
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

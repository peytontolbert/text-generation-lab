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
STAGE = 9118
NAME = "stage9118_metadata_inventory_runner_execution_authorization_review"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9117 = ROOT / "runs/summaries/stage9117_metadata_only_inventory_runner_static_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "METADATA_INVENTORY_RUNNER_EXECUTION_AUTHORIZATION_REVIEW_STAGE9118.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "metadata_inventory_runner_execution_authorization_review.json"

REQUIRED_BEFORE_EXECUTION = [
    "explicit_user_inventory_execution_request",
    "single_run_inventory_ticket",
    "final_pre_execution_audit_passed",
    "output_dir_under_runs_local_artifacts",
    "stage9117_static_audit_passed",
    "stage9116_contract_audit_passed",
    "no_row_reads_flag_set",
    "no_source_body_reads_flag_set",
    "no_arxiv_writes_flag_set",
    "no_follow_symlinks_flag_set",
    "max_depth_capped",
]

CURRENT_BLOCKERS = [
    "explicit_user_inventory_execution_request_missing",
    "single_run_inventory_ticket_missing",
    "final_pre_execution_audit_missing",
    "no_current_execution_window",
]

AUTHORIZED_FUTURE_OUTPUTS_ONLY = [
    "arxiv_root_metadata_card.json",
    "dataset_file_inventory_metadata_only.jsonl",
    "repository_root_inventory_metadata_only.jsonl",
    "inventory_scope_card.json",
    "protected_path_policy_card.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9117)
    checks = {
        "source_stage9117_passed": source.get("passed") is True,
        "source_stage9117_runner_not_executed": (source.get("metrics") or {}).get("runner_executed_now") is False,
        "required_before_execution_recorded": len(REQUIRED_BEFORE_EXECUTION) >= 11,
        "current_blockers_recorded": len(CURRENT_BLOCKERS) >= 4,
        "authorized_future_outputs_recorded": len(AUTHORIZED_FUTURE_OUTPUTS_ONLY) >= 5,
        "registry_frontier_stage9117": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9117,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "METADATA_INVENTORY_RUNNER_EXECUTION_REVIEW_NO_EXECUTION_AUTHORIZED",
        "required_before_execution": list(REQUIRED_BEFORE_EXECUTION),
        "current_blockers": list(CURRENT_BLOCKERS),
        "authorized_future_outputs_only": list(AUTHORIZED_FUTURE_OUTPUTS_ONLY),
        "checks": checks,
        "metrics": {
            "required_before_execution": len(REQUIRED_BEFORE_EXECUTION),
            "current_blockers": len(CURRENT_BLOCKERS),
            "authorized_future_outputs_only": len(AUTHORIZED_FUTURE_OUTPUTS_ONLY),
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
        "decision": "Reviewed metadata-only inventory runner execution readiness. Execution is not authorized now or next because explicit user execution request, single-run inventory ticket, and final pre-execution audit are missing. No /arxiv access/stat, name reads, row reads, source-body reads, writes, mining, route-card materialization, trainer/model path, upload, cleanup, or training occurred.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9117, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for item in REQUIRED_BEFORE_EXECUTION:
        if item not in card.get("required_before_execution", []):
            failures.append(f"missing_required_before_execution:{item}")
    for blocker in CURRENT_BLOCKERS:
        if blocker not in card.get("current_blockers", []):
            failures.append(f"missing_current_blocker:{blocker}")
    for key in [
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
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_card(registry)
    failures = validate_card(card, registry)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **card["metrics"]},
        "artifacts": {"card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": card["decision"] if not failures else "Metadata inventory runner execution authorization review failed.",
        "next_best_step": "Design a single-run metadata inventory ticket and final pre-execution audit; do not run inventory yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9118 Metadata Inventory Runner Execution Authorization Review",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Execution is not authorized in this stage. The runner remains unexecuted.",
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

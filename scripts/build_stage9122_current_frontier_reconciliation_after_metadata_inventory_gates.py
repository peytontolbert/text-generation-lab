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
STAGE = 9122
NAME = "stage9122_current_frontier_reconciliation_after_metadata_inventory_gates"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9117 = ROOT / "runs/summaries/stage9117_metadata_only_inventory_runner_static_audit.json"
SOURCE_9120 = ROOT / "runs/summaries/stage9120_single_run_metadata_inventory_ticket_audit.json"
SOURCE_9121 = ROOT / "runs/summaries/stage9121_metadata_inventory_final_pre_execution_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_FRONTIER_AFTER_METADATA_INVENTORY_GATES_STAGE9122.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "current_frontier_after_metadata_inventory_gates.json"

RECOVERED_CONTROLS = [
    "stage9117_metadata_only_inventory_runner_static_audit",
    "stage9118_metadata_inventory_execution_authorization_review",
    "stage9119_single_run_metadata_inventory_ticket_design",
    "stage9120_single_run_metadata_inventory_ticket_audit",
    "stage9121_metadata_inventory_final_pre_execution_audit_review_only",
]

ACTIVE_BLOCKERS = [
    "explicit_user_inventory_execution_request_missing",
    "metadata_inventory_execution_not_authorized",
    "training_execution_not_authorized",
    "decoder_ce_training_not_authorized",
    "denoise_ce_training_not_authorized",
    "runtime_not_authorized",
]

NEXT_SAFE_BRANCHES = [
    "return_to_compiler_training_recovery_gap_walk",
    "route_card_materialization_design_without_execution",
    "trainer_contract_only_artifact_materialization_design_without_invocation",
    "metadata_inventory_execution_only_after_explicit_user_request",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    s9117 = load_json(SOURCE_9117)
    s9120 = load_json(SOURCE_9120)
    s9121 = load_json(SOURCE_9121)
    checks = {
        "source_stage9117_passed": s9117.get("passed") is True,
        "source_stage9120_passed": s9120.get("passed") is True,
        "source_stage9121_passed": s9121.get("passed") is True,
        "stage9117_runner_not_executed": (s9117.get("metrics") or {}).get("runner_executed_now") is False,
        "stage9120_negative_cases_rejected": (s9120.get("metrics") or {}).get("negative_cases_rejected") == (s9120.get("metrics") or {}).get("negative_cases"),
        "stage9121_execution_not_authorized": (s9121.get("metrics") or {}).get("inventory_execution_authorized_next") is False,
        "recovered_controls_recorded": len(RECOVERED_CONTROLS) >= 5,
        "active_blockers_recorded": len(ACTIVE_BLOCKERS) >= 6,
        "next_safe_branches_recorded": len(NEXT_SAFE_BRANCHES) >= 4,
        "registry_frontier_stage9121": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9121,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "FRONTIER_RECONCILED_AFTER_METADATA_INVENTORY_GATES",
        "recovered_controls": list(RECOVERED_CONTROLS),
        "active_blockers": list(ACTIVE_BLOCKERS),
        "next_safe_branches": list(NEXT_SAFE_BRANCHES),
        "checks": checks,
        "metrics": {
            "recovered_controls": len(RECOVERED_CONTROLS),
            "active_blockers": len(ACTIVE_BLOCKERS),
            "next_safe_branches": len(NEXT_SAFE_BRANCHES),
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
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Frontier reconciled after metadata inventory gates. Metadata inventory execution remains blocked without explicit user authorization; safe continuation is compiler/training recovery gap work, not /arxiv inventory or training execution.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9121, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
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
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
        "trainer_executed_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
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
        "decision": card["decision"] if not failures else "Current frontier reconciliation after metadata inventory gates failed.",
        "next_best_step": "Run compiler/training recovery gap walk; keep /arxiv inventory and training execution closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9122 Current Frontier After Metadata Inventory Gates",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Metadata inventory controls are recovered and execution remains blocked. The safe continuation is compiler/training recovery work.",
        "",
        "Active blockers:",
        "",
        *[f"- {item}" for item in ACTIVE_BLOCKERS],
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
    marker = "## Stage9122 Current Frontier After Metadata Inventory Gates"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9122 reconciles metadata inventory controls through Stage9121. Metadata inventory execution remains blocked without explicit user authorization, and training/runtime/decoder/denoise authority remains closed. The active safe branch returns to compiler/training recovery gap work.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

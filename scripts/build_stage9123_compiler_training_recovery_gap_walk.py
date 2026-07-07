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
STAGE = 9123
NAME = "stage9123_compiler_training_recovery_gap_walk"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9122 = ROOT / "runs/summaries/stage9122_current_frontier_reconciliation_after_metadata_inventory_gates.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "COMPILER_TRAINING_RECOVERY_GAP_WALK_STAGE9123.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "compiler_training_recovery_gap_walk.json"

RECOVERED_TRAINING_CONTROL_AREAS = [
    "authority_flags_and_registry",
    "safe_cleanup_policy",
    "metadata_only_inventory_controls",
    "trainer_command_surface_contracts",
    "trainer_runtime_assertion_inventory",
    "trainer_contract_only_artifact_schema",
    "structured_policy_spine_docs",
    "central_research_graph",
]

OPEN_GAPS = [
    "route_cards_not_materialized",
    "route_to_loss_translation_not_materialized",
    "loss_mask_cards_not_materialized_from_real_routes",
    "dataset_judge_outputs_not_bound_to_compiler_inputs",
    "junk_ranker_routes_not_bound_to_loss_masks",
    "curriculum_compiler_runner_not_recovered_as_single_entrypoint",
    "trainer_contract_only_artifacts_not_materialized",
    "final_trainer_pre_execution_audit_missing",
    "one_run_training_ticket_missing",
    "telemetry_artifact_contract_not_reverified_against_current_trainer",
]

NEXT_SAFE_BRANCHES = [
    "route_card_schema_recovery_refresh",
    "route_to_loss_translation_contract_refresh",
    "loss_mask_card_materialization_design",
    "curriculum_compiler_single_entrypoint_design",
    "trainer_contract_only_artifact_materialization_design",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9122)
    checks = {
        "source_stage9122_passed": source.get("passed") is True,
        "source_stage9122_inventory_closed": (source.get("metrics") or {}).get("inventory_execution_authorized_next") is False,
        "recovered_training_control_areas_recorded": len(RECOVERED_TRAINING_CONTROL_AREAS) >= 8,
        "open_gaps_recorded": len(OPEN_GAPS) >= 10,
        "next_safe_branches_recorded": len(NEXT_SAFE_BRANCHES) >= 5,
        "registry_frontier_stage9122": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9122,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "COMPILER_TRAINING_RECOVERY_GAP_WALK_NO_EXECUTION",
        "recovered_training_control_areas": list(RECOVERED_TRAINING_CONTROL_AREAS),
        "open_gaps": list(OPEN_GAPS),
        "next_safe_branches": list(NEXT_SAFE_BRANCHES),
        "checks": checks,
        "metrics": {
            "recovered_training_control_areas": len(RECOVERED_TRAINING_CONTROL_AREAS),
            "open_gaps": len(OPEN_GAPS),
            "next_safe_branches": len(NEXT_SAFE_BRANCHES),
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
            "loss_mask_cards_materialized_now": False,
            "compiler_handoff_ready_now": False,
            "trainer_contract_only_artifacts_materialized_now": False,
            "trainer_executed_now": False,
            "contract_only_invoked_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "inventory_execution_authorized_next": False,
            "arxiv_access_performed": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Compiler/training recovery gap walk complete. The next safe work is route-card schema recovery and route-to-loss translation contract refresh; no route cards, loss masks, compiler handoff, trainer invocation, model forward, inventory, /arxiv row/source reads, upload, cleanup, or training are authorized.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9122, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for gap in OPEN_GAPS:
        if gap not in card.get("open_gaps", []):
            failures.append(f"missing_open_gap:{gap}")
    for key in [
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
        "loss_mask_cards_materialized_now",
        "compiler_handoff_ready_now",
        "trainer_contract_only_artifacts_materialized_now",
        "trainer_executed_now",
        "contract_only_invoked_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "inventory_execution_authorized_next",
        "arxiv_access_performed",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
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
        "decision": card["decision"] if not failures else "Compiler/training recovery gap walk failed.",
        "next_best_step": "Recover route-card schema and route-to-loss translation contracts; do not materialize real route cards yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9123 Compiler/Training Recovery Gap Walk",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Open gaps:",
        "",
        *[f"- {item}" for item in OPEN_GAPS],
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

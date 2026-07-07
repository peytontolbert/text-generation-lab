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
STAGE = 9126
NAME = "stage9126_route_to_loss_translation_contract_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9125 = ROOT / "runs/summaries/stage9125_route_card_schema_recovery_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROUTE_TO_LOSS_TRANSLATION_CONTRACT_STAGE9126.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "route_to_loss_translation_contract.json"

ROUTE_TO_LOSSES = {
    "KEEP_STRUCTURED": ["surface_role_ce", "repair_surface_ce", "action_ce", "evidence_state_ce", "budget_gate_ce", "decode_gate_ce"],
    "KEEP_BOUNDED_DECODER": ["decoder_ce"],
    "HOLD_LONG_OUTPUT": ["long_output_holdout_supervision"],
    "USE_FOR_DENOISE_REPAIR": ["denoise_ce"],
    "USE_AS_NEGATIVE": ["abstain_ce", "suppress_decode_ce"],
    "NEEDS_RETRIEVAL": ["retrieve_more_ce", "decode_block_ce"],
    "QUARANTINE_LABEL_CONFLICT": [],
    "DROP_DUPLICATE": [],
    "NEEDS_HUMAN_REVIEW": [],
}

LOSS_AUTHORITY_RULES = {
    "decoder_ce": ["decoder_budget_ok", "decode_allowed", "authority_closed", "no_long_blob", "no_html_doc_fragment"],
    "denoise_ce": ["repair_route", "authority_closed", "clean_target_available"],
    "surface_role_ce": ["structured_route", "target_not_in_input"],
    "repair_surface_ce": ["structured_route", "target_not_in_input"],
    "action_ce": ["structured_route", "target_not_in_input"],
    "evidence_state_ce": ["structured_route", "target_not_in_input"],
    "budget_gate_ce": ["structured_route", "deterministic_budget_fact_available"],
    "decode_gate_ce": ["structured_route", "deterministic_overlay_available"],
}

FORBIDDEN_TRANSLATIONS = [
    "QUARANTINE_LABEL_CONFLICT_to_any_loss",
    "DROP_DUPLICATE_to_any_loss",
    "NEEDS_HUMAN_REVIEW_to_any_loss",
    "HOLD_LONG_OUTPUT_to_decoder_ce",
    "USE_AS_NEGATIVE_to_decoder_ce",
    "NEEDS_RETRIEVAL_to_decoder_ce",
    "KEEP_STRUCTURED_to_decoder_ce",
    "KEEP_BOUNDED_DECODER_to_runtime_reward",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9125)
    checks = {
        "source_stage9125_passed": source.get("passed") is True,
        "route_to_losses_recorded": len(ROUTE_TO_LOSSES) >= 9,
        "loss_authority_rules_recorded": len(LOSS_AUTHORITY_RULES) >= 8,
        "forbidden_translations_recorded": len(FORBIDDEN_TRANSLATIONS) >= 8,
        "quarantine_routes_have_no_losses": ROUTE_TO_LOSSES["QUARANTINE_LABEL_CONFLICT"] == [] and ROUTE_TO_LOSSES["DROP_DUPLICATE"] == [] and ROUTE_TO_LOSSES["NEEDS_HUMAN_REVIEW"] == [],
        "registry_frontier_stage9125": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9125,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ROUTE_TO_LOSS_TRANSLATION_CONTRACT_DESIGN_NO_TRANSLATION_READY",
        "route_to_losses": json.loads(json.dumps(ROUTE_TO_LOSSES)),
        "loss_authority_rules": json.loads(json.dumps(LOSS_AUTHORITY_RULES)),
        "forbidden_translations": list(FORBIDDEN_TRANSLATIONS),
        "checks": checks,
        "metrics": {
            "routes": len(ROUTE_TO_LOSSES),
            "loss_authority_rules": len(LOSS_AUTHORITY_RULES),
            "forbidden_translations": len(FORBIDDEN_TRANSLATIONS),
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
            "loss_mask_cards_materialized_now": False,
            "compiler_handoff_ready_now": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
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
        "decision": "Recovered route-to-loss translation contract design. Translation is not ready and no loss masks, compiler handoff, trainer/model paths, uploads, cleanup, or training are materialized.",
    }


def validate_contract(contract: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in contract["checks"].items() if value is not True]
    if any((contract.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9125, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for route in ROUTE_TO_LOSSES:
        if route not in contract.get("route_to_losses", {}):
            failures.append(f"missing_route_translation:{route}")
    for forbidden in FORBIDDEN_TRANSLATIONS:
        if forbidden not in contract.get("forbidden_translations", []):
            failures.append(f"missing_forbidden_translation:{forbidden}")
    for key in [
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
        "loss_mask_cards_materialized_now",
        "compiler_handoff_ready_now",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "trainer_executed_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "network_upload_performed",
        "cleanup_authorized_now",
    ]:
        if contract["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    contract = build_contract(registry)
    failures = validate_contract(contract, registry)
    CONTRACT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **contract["metrics"]},
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": contract["decision"] if not failures else "Route-to-loss translation contract design failed.",
        "next_best_step": "Audit route-to-loss translation contract; do not translate real routes yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9126 Route-To-Loss Translation Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Recovered route-to-loss translation rules without translating real route cards.",
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

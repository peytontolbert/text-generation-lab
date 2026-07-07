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
STAGE = 9130
NAME = "stage9130_synthetic_route_to_loss_mask_translator_smoke_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9127 = ROOT / "runs/summaries/stage9127_route_to_loss_translation_contract_audit.json"
SOURCE_9129 = ROOT / "runs/summaries/stage9129_loss_mask_card_schema_recovery_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SYNTHETIC_ROUTE_TO_LOSS_MASK_TRANSLATOR_SMOKE_STAGE9130.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "synthetic_route_to_loss_mask_translator_smoke_design.json"

SYNTHETIC_FIXTURES = [
    {
        "fixture_id": "synthetic_keep_structured",
        "route": "KEEP_STRUCTURED",
        "decoder_budget_ok": False,
        "decode_allowed": False,
        "expected_enabled_losses": ["surface_role_ce", "repair_surface_ce", "action_ce", "evidence_state_ce", "budget_gate_ce", "decode_gate_ce"],
        "expected_disabled_losses": ["decoder_ce", "denoise_ce", "runtime_reward"],
    },
    {
        "fixture_id": "synthetic_keep_bounded_decoder",
        "route": "KEEP_BOUNDED_DECODER",
        "decoder_budget_ok": True,
        "decode_allowed": True,
        "target_token_len": 128,
        "expected_enabled_losses": ["decoder_ce"],
        "expected_disabled_losses": ["denoise_ce", "runtime_reward"],
    },
    {
        "fixture_id": "synthetic_hold_long_output",
        "route": "HOLD_LONG_OUTPUT",
        "decoder_budget_ok": False,
        "decode_allowed": False,
        "target_token_len": 12000,
        "expected_enabled_losses": ["long_output_holdout_supervision"],
        "expected_disabled_losses": ["decoder_ce", "denoise_ce", "runtime_reward"],
    },
    {
        "fixture_id": "synthetic_use_for_denoise_repair",
        "route": "USE_FOR_DENOISE_REPAIR",
        "decoder_budget_ok": True,
        "decode_allowed": False,
        "repair_route": True,
        "expected_enabled_losses": ["denoise_ce"],
        "expected_disabled_losses": ["decoder_ce", "runtime_reward"],
    },
    {
        "fixture_id": "synthetic_needs_retrieval",
        "route": "NEEDS_RETRIEVAL",
        "decoder_budget_ok": True,
        "decode_allowed": False,
        "expected_enabled_losses": ["retrieve_more_ce", "decode_block_ce"],
        "expected_disabled_losses": ["decoder_ce", "denoise_ce", "runtime_reward"],
    },
    {
        "fixture_id": "synthetic_quarantine_label_conflict",
        "route": "QUARANTINE_LABEL_CONFLICT",
        "decoder_budget_ok": True,
        "decode_allowed": False,
        "expected_enabled_losses": [],
        "expected_disabled_losses": ["decoder_ce", "denoise_ce", "runtime_reward", "surface_role_ce", "action_ce"],
    },
]

REQUIRED_SMOKE_CHECKS = [
    "synthetic_only_inputs",
    "all_route_fixtures_present",
    "decoder_ce_only_for_keep_bounded_decoder",
    "quarantine_fixture_has_no_enabled_losses",
    "hold_long_output_blocks_decoder_ce",
    "needs_retrieval_blocks_decoder_ce",
    "denoise_route_blocks_decoder_ce",
    "all_fixtures_emit_authority_closed",
    "all_fixtures_emit_telemetry_required",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_design(registry: dict[str, Any]) -> dict[str, Any]:
    s9127 = load_json(SOURCE_9127)
    s9129 = load_json(SOURCE_9129)
    fixture_routes = {fixture["route"] for fixture in SYNTHETIC_FIXTURES}
    decoder_ce_routes = {
        fixture["route"]
        for fixture in SYNTHETIC_FIXTURES
        if "decoder_ce" in fixture.get("expected_enabled_losses", [])
    }
    checks = {
        "source_stage9127_passed": s9127.get("passed") is True,
        "source_stage9129_passed": s9129.get("passed") is True,
        "synthetic_fixtures_recorded": len(SYNTHETIC_FIXTURES) >= 6,
        "required_smoke_checks_recorded": len(REQUIRED_SMOKE_CHECKS) >= 9,
        "keep_bounded_decoder_fixture_present": "KEEP_BOUNDED_DECODER" in fixture_routes,
        "quarantine_fixture_present": "QUARANTINE_LABEL_CONFLICT" in fixture_routes,
        "decoder_ce_only_for_keep_bounded_decoder": decoder_ce_routes == {"KEEP_BOUNDED_DECODER"},
        "registry_frontier_stage9129": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9129,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "SYNTHETIC_ROUTE_TO_LOSS_MASK_TRANSLATOR_SMOKE_DESIGN_NO_REAL_DATA",
        "synthetic_fixtures": json.loads(json.dumps(SYNTHETIC_FIXTURES)),
        "required_smoke_checks": list(REQUIRED_SMOKE_CHECKS),
        "checks": checks,
        "metrics": {
            "synthetic_fixtures": len(SYNTHETIC_FIXTURES),
            "required_smoke_checks": len(REQUIRED_SMOKE_CHECKS),
            "real_route_cards_used": 0,
            "real_loss_masks_materialized": 0,
            "synthetic_loss_masks_materialized_now": False,
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
        "decision": "Designed a synthetic-only route-card to loss-mask translator smoke. No real route cards, real loss masks, compiler handoff, trainer/model paths, uploads, cleanup, or training are materialized.",
    }


def validate_design(design: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in design["checks"].items() if value is not True]
    if any((design.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9129, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    fixtures = design.get("synthetic_fixtures", [])
    if not fixtures:
        failures.append("missing_synthetic_fixtures")
    decoder_routes = {
        fixture.get("route")
        for fixture in fixtures
        if "decoder_ce" in fixture.get("expected_enabled_losses", [])
    }
    if decoder_routes != {"KEEP_BOUNDED_DECODER"}:
        failures.append("decoder_ce_route_violation")
    for fixture in fixtures:
        if fixture.get("route") == "QUARANTINE_LABEL_CONFLICT" and fixture.get("expected_enabled_losses") != []:
            failures.append("quarantine_fixture_has_enabled_loss")
    for check in REQUIRED_SMOKE_CHECKS:
        if check not in design.get("required_smoke_checks", []):
            failures.append(f"missing_smoke_check:{check}")
    for key in [
        "synthetic_loss_masks_materialized_now",
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
        if design["metrics"].get(key) is not False:
            failures.append(key)
    for key in ["real_route_cards_used", "real_loss_masks_materialized"]:
        if design["metrics"].get(key) != 0:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    design = build_design(registry)
    failures = validate_design(design, registry)
    DESIGN.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **design["metrics"]},
        "artifacts": {"design": str(DESIGN.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": design["decision"] if not failures else "Synthetic route-card to loss-mask translator smoke design failed.",
        "next_best_step": "Audit synthetic route-card to loss-mask translator smoke design, then implement synthetic-only translator smoke.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9130 Synthetic Route-To-Loss-Mask Translator Smoke Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Designs a synthetic-only smoke for translating route cards to loss-mask cards. No real data or real loss masks are materialized.",
        "",
        f"Synthetic fixtures: `{design['metrics']['synthetic_fixtures']}`",
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

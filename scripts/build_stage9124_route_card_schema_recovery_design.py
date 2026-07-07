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
STAGE = 9124
NAME = "stage9124_route_card_schema_recovery_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9123 = ROOT / "runs/summaries/stage9123_compiler_training_recovery_gap_walk.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROUTE_CARD_SCHEMA_RECOVERY_STAGE9124.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SCHEMA = OUT_DIR / "route_card_schema_recovery_design.json"

REQUIRED_ROUTE_FIELDS = [
    "row_id",
    "source_manifest",
    "source_stage",
    "objective_family",
    "route",
    "risk_bucket",
    "recommended_action",
    "split",
    "language_family",
    "surface",
    "task_phase",
    "state_schema_ref",
    "evidence_state",
    "decoder_budget_ok",
    "target_length_bucket",
    "loss_mask_ref",
    "authority",
    "judge_reasons",
    "anti_cheat",
    "provenance",
]

ROUTE_ENUM = [
    "KEEP_STRUCTURED",
    "KEEP_BOUNDED_DECODER",
    "HOLD_LONG_OUTPUT",
    "USE_FOR_DENOISE_REPAIR",
    "USE_AS_NEGATIVE",
    "NEEDS_RETRIEVAL",
    "QUARANTINE_LABEL_CONFLICT",
    "DROP_DUPLICATE",
    "NEEDS_HUMAN_REVIEW",
]

OBJECTIVE_FAMILIES = [
    "intent_to_build_strategy",
    "repo_state_graph",
    "symbol_binding",
    "edit_localization",
    "patch_operator",
    "verifier_repair",
    "bounded_decoder_arguments",
    "bounded_decoder_ce",
    "output_repair_denoise",
]

ANTI_CHEAT_FIELDS = [
    "label_leak_checked",
    "shortcut_baseline_max",
    "split_overlap_checked",
    "raw_text_forbidden_checked",
    "authority_closed_checked",
    "target_not_in_input_checked",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_schema(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9123)
    checks = {
        "source_stage9123_passed": source.get("passed") is True,
        "required_route_fields_recorded": len(REQUIRED_ROUTE_FIELDS) >= 20,
        "route_enum_recorded": len(ROUTE_ENUM) >= 9,
        "objective_families_recorded": len(OBJECTIVE_FAMILIES) >= 9,
        "anti_cheat_fields_recorded": len(ANTI_CHEAT_FIELDS) >= 6,
        "registry_frontier_stage9123": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9123,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ROUTE_CARD_SCHEMA_RECOVERY_DESIGN_NO_ROUTE_MATERIALIZATION",
        "required_route_fields": list(REQUIRED_ROUTE_FIELDS),
        "route_enum": list(ROUTE_ENUM),
        "objective_families": list(OBJECTIVE_FAMILIES),
        "anti_cheat_fields": list(ANTI_CHEAT_FIELDS),
        "checks": checks,
        "metrics": {
            "required_route_fields": len(REQUIRED_ROUTE_FIELDS),
            "route_enum": len(ROUTE_ENUM),
            "objective_families": len(OBJECTIVE_FAMILIES),
            "anti_cheat_fields": len(ANTI_CHEAT_FIELDS),
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
        "decision": "Recovered the route-card schema design. No real route cards, loss masks, compiler handoff, dataset rows, source bodies, trainer/model paths, uploads, cleanup, or training are materialized.",
    }


def validate_schema(schema: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in schema["checks"].items() if value is not True]
    if any((schema.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9123, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for field in REQUIRED_ROUTE_FIELDS:
        if field not in schema.get("required_route_fields", []):
            failures.append(f"missing_route_field:{field}")
    for route in ROUTE_ENUM:
        if route not in schema.get("route_enum", []):
            failures.append(f"missing_route_enum:{route}")
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
        if schema["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    schema = build_schema(registry)
    failures = validate_schema(schema, registry)
    SCHEMA.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **schema["metrics"]},
        "artifacts": {"schema": str(SCHEMA.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": schema["decision"] if not failures else "Route-card schema recovery design failed.",
        "next_best_step": "Audit route-card schema recovery, then recover route-to-loss translation contract.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9124 Route-Card Schema Recovery",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Recovered the route-card schema without materializing real route cards.",
        "",
        "Routes:",
        "",
        *[f"- `{item}`" for item in ROUTE_ENUM],
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

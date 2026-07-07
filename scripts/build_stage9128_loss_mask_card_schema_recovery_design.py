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
STAGE = 9128
NAME = "stage9128_loss_mask_card_schema_recovery_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9127 = ROOT / "runs/summaries/stage9127_route_to_loss_translation_contract_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LOSS_MASK_CARD_SCHEMA_RECOVERY_STAGE9128.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SCHEMA = OUT_DIR / "loss_mask_card_schema_recovery_design.json"

REQUIRED_LOSS_MASK_FIELDS = [
    "row_id",
    "route_card_ref",
    "enabled_losses",
    "disabled_losses",
    "loss_weights",
    "decoder_ce_allowed",
    "denoise_ce_allowed",
    "structured_aux_allowed",
    "runtime_reward_allowed",
    "authority",
    "decoder_budget_ok",
    "decode_allowed",
    "target_token_len",
    "target_length_bucket",
    "loss_authority_evidence",
    "forbidden_loss_reasons",
    "telemetry_required",
    "anti_cheat",
    "created_by_stage",
    "schema_version",
]

REQUIRED_DISABLED_BY_DEFAULT = [
    "decoder_ce",
    "denoise_ce",
    "runtime_reward",
    "source_body_loss",
    "gemma_distill_loss",
    "harness_score_loss",
]

REQUIRED_TELEMETRY = [
    "row_field_losses",
    "row_field_logits",
    "row_token_loss_if_decoder_ce",
    "loss_mask_enforcement_audit",
    "module_delta_norms",
    "failure_bucket_card",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_schema(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9127)
    checks = {
        "source_stage9127_passed": source.get("passed") is True,
        "required_loss_mask_fields_recorded": len(REQUIRED_LOSS_MASK_FIELDS) >= 20,
        "required_disabled_by_default_recorded": len(REQUIRED_DISABLED_BY_DEFAULT) >= 6,
        "required_telemetry_recorded": len(REQUIRED_TELEMETRY) >= 6,
        "registry_frontier_stage9127": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9127,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "LOSS_MASK_CARD_SCHEMA_RECOVERY_DESIGN_NO_MATERIALIZATION",
        "required_loss_mask_fields": list(REQUIRED_LOSS_MASK_FIELDS),
        "required_disabled_by_default": list(REQUIRED_DISABLED_BY_DEFAULT),
        "required_telemetry": list(REQUIRED_TELEMETRY),
        "checks": checks,
        "metrics": {
            "required_loss_mask_fields": len(REQUIRED_LOSS_MASK_FIELDS),
            "required_disabled_by_default": len(REQUIRED_DISABLED_BY_DEFAULT),
            "required_telemetry": len(REQUIRED_TELEMETRY),
            "loss_mask_cards_materialized_now": False,
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
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
        "decision": "Recovered loss-mask card schema design. No loss masks, route cards, compiler handoff, trainer/model paths, uploads, cleanup, or training are materialized.",
    }


def validate_schema(schema: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in schema["checks"].items() if value is not True]
    if any((schema.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9127, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for field in REQUIRED_LOSS_MASK_FIELDS:
        if field not in schema.get("required_loss_mask_fields", []):
            failures.append(f"missing_loss_mask_field:{field}")
    for loss in REQUIRED_DISABLED_BY_DEFAULT:
        if loss not in schema.get("required_disabled_by_default", []):
            failures.append(f"missing_disabled_default_loss:{loss}")
    for telemetry in REQUIRED_TELEMETRY:
        if telemetry not in schema.get("required_telemetry", []):
            failures.append(f"missing_required_telemetry:{telemetry}")
    for key in [
        "loss_mask_cards_materialized_now",
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
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
        "decision": schema["decision"] if not failures else "Loss-mask card schema recovery design failed.",
        "next_best_step": "Audit loss-mask card schema; do not materialize real loss masks yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9128 Loss-Mask Card Schema Recovery",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Recovered the loss-mask card schema without materializing real loss masks.",
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

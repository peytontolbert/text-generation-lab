#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9138_real_route_card_input_authorization_gate_design import (
        FORBIDDEN_INPUT_FIELDS,
        REQUIRED_PREFLIGHT_CHECKS,
        REQUIRED_TICKET_FIELDS,
    )
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9138_real_route_card_input_authorization_gate_design import (  # type: ignore
        FORBIDDEN_INPUT_FIELDS,
        REQUIRED_PREFLIGHT_CHECKS,
        REQUIRED_TICKET_FIELDS,
    )
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9142
NAME = "stage9142_real_route_card_input_ticket_instance_schema_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9141 = ROOT / "runs/summaries/stage9141_real_route_card_input_ticket_template_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_ROUTE_CARD_INPUT_TICKET_INSTANCE_SCHEMA_DESIGN_STAGE9142.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SCHEMA = OUT_DIR / "real_route_card_input_ticket_instance_schema_design.json"

INSTANCE_REQUIRED_FIELDS = [
    "ticket_schema_version",
    "ticket_kind",
    "ticket_id",
    "created_by_stage",
    "approved_for_preflight_only",
    "approved_for_route_card_materialization",
    "objective_rows_path",
    "judge_rows_path",
    "junk_ranker_rows_path",
    "shortcut_baseline_card_path",
    "counterfactual_obligation_card_path",
    "source_lineage_card_path",
    "max_rows",
    "allowed_input_root",
    "output_dir",
    "dry_run_only",
    "no_source_bodies",
    "no_decoder_targets",
    "no_trainer_execution",
    "path_validation_required",
    "schema_validation_required",
    "forbidden_input_fields",
    "required_preflight_checks",
    "authority",
    "manual_approval_record",
]

INSTANCE_INVARIANTS = [
    "ticket_kind_must_be_instance",
    "approved_for_preflight_only_true",
    "approved_for_route_card_materialization_false",
    "max_rows_positive_and_capped",
    "all_paths_repo_local_or_explicit_workspace",
    "arxiv_paths_forbidden_without_separate_authorization",
    "source_body_and_decoder_target_fields_forbidden",
    "authority_closed",
    "output_dir_repo_local",
    "trainer_execution_forbidden",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_schema(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9141)
    checks = {
        "source_stage9141_passed": source.get("passed") is True,
        "template_ticket_fields_reused": set(REQUIRED_TICKET_FIELDS).issubset(set(INSTANCE_REQUIRED_FIELDS)),
        "instance_required_fields_recorded": len(INSTANCE_REQUIRED_FIELDS) >= 21,
        "instance_invariants_recorded": len(INSTANCE_INVARIANTS) >= 10,
        "required_preflight_checks_reused": len(REQUIRED_PREFLIGHT_CHECKS) >= 13,
        "forbidden_input_fields_reused": len(FORBIDDEN_INPUT_FIELDS) >= 9,
        "registry_frontier_stage9141": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9141,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "REAL_ROUTE_CARD_INPUT_TICKET_INSTANCE_SCHEMA_DESIGN_NO_INSTANCE",
        "instance_required_fields": list(INSTANCE_REQUIRED_FIELDS),
        "instance_invariants": list(INSTANCE_INVARIANTS),
        "required_preflight_checks": list(REQUIRED_PREFLIGHT_CHECKS),
        "forbidden_input_fields": list(FORBIDDEN_INPUT_FIELDS),
        "checks": checks,
        "metrics": {
            "instance_required_fields": len(INSTANCE_REQUIRED_FIELDS),
            "instance_invariants": len(INSTANCE_INVARIANTS),
            "ticket_instance_schema_designed": True,
            "ticket_instance_materialized": False,
            "approved_for_preflight_only": False,
            "approved_for_route_card_materialization": False,
            "real_input_authorized_now": False,
            "real_judge_rows_used": 0,
            "real_ranker_rows_used": 0,
            "real_route_cards_materialized": 0,
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
        "decision": "Designed the schema for a future bounded real route-card input preflight ticket instance. No ticket instance or real input authorization was created.",
    }


def validate_schema(schema: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in schema["checks"].items() if value is not True]
    if any((schema.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9141, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for field in INSTANCE_REQUIRED_FIELDS:
        if field not in schema.get("instance_required_fields", []):
            failures.append(f"missing_instance_field:{field}")
    for invariant in INSTANCE_INVARIANTS:
        if invariant not in schema.get("instance_invariants", []):
            failures.append(f"missing_instance_invariant:{invariant}")
    for key in [
        "ticket_instance_materialized",
        "approved_for_preflight_only",
        "approved_for_route_card_materialization",
        "real_input_authorized_now",
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
    for key in ["real_judge_rows_used", "real_ranker_rows_used", "real_route_cards_materialized"]:
        if schema["metrics"].get(key) != 0:
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
        "decision": schema["decision"] if not failures else "Real route-card input ticket instance schema design failed.",
        "next_best_step": "Audit ticket-instance schema before creating any bounded preflight ticket instance.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9142 Real Route-Card Input Ticket Instance Schema Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Designed a future ticket-instance schema only. No instance was created.",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
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
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

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
STAGE = 9140
NAME = "stage9140_real_route_card_input_ticket_template"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9139 = ROOT / "runs/summaries/stage9139_real_route_card_input_authorization_gate_design_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_ROUTE_CARD_INPUT_TICKET_TEMPLATE_STAGE9140.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TEMPLATE = OUT_DIR / "real_route_card_input_ticket_template.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_ticket_template(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9139)
    ticket = {
        "ticket_schema_version": "real_route_card_input_ticket_v1",
        "ticket_kind": "REAL_ROUTE_CARD_INPUT_PREFLIGHT_TEMPLATE_NOT_INSTANCE",
        "approved_for_execution": False,
        "objective_rows_path": "PLACEHOLDER_REPO_LOCAL_ARTIFACT_JSONL",
        "judge_rows_path": "PLACEHOLDER_REPO_LOCAL_ARTIFACT_JSONL",
        "junk_ranker_rows_path": "PLACEHOLDER_REPO_LOCAL_ARTIFACT_JSONL",
        "shortcut_baseline_card_path": "PLACEHOLDER_REPO_LOCAL_ARTIFACT_JSON",
        "counterfactual_obligation_card_path": "PLACEHOLDER_REPO_LOCAL_ARTIFACT_JSON",
        "source_lineage_card_path": "PLACEHOLDER_REPO_LOCAL_ARTIFACT_JSON",
        "max_rows": 0,
        "allowed_input_root": "runs/local/artifacts",
        "output_dir": "runs/local/artifacts/PLACEHOLDER_REAL_ROUTE_CARD_INPUT_PREFLIGHT",
        "dry_run_only": True,
        "no_source_bodies": True,
        "no_decoder_targets": True,
        "no_trainer_execution": True,
        "path_validation_required": True,
        "schema_validation_required": True,
        "required_preflight_checks": list(REQUIRED_PREFLIGHT_CHECKS),
        "forbidden_input_fields": list(FORBIDDEN_INPUT_FIELDS),
        "authority": dict(AUTHORITY_CLOSED),
        "required_manual_approvals": [
            "explicit_user_approval_for_real_input_ticket_instance",
            "separate_authorization_for_any_arxiv_path",
            "separate_authorization_before_route_card_materialization",
        ],
    }
    checks = {
        "source_stage9139_passed": source.get("passed") is True,
        "all_required_ticket_fields_present": all(field in ticket for field in REQUIRED_TICKET_FIELDS),
        "template_not_instance": ticket["ticket_kind"].endswith("TEMPLATE_NOT_INSTANCE"),
        "not_approved_for_execution": ticket["approved_for_execution"] is False,
        "max_rows_zero": ticket["max_rows"] == 0,
        "dry_run_only": ticket["dry_run_only"] is True,
        "no_source_bodies": ticket["no_source_bodies"] is True,
        "no_decoder_targets": ticket["no_decoder_targets"] is True,
        "no_trainer_execution": ticket["no_trainer_execution"] is True,
        "authority_closed": not any(ticket["authority"].values()),
        "registry_frontier_stage9139": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9139,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "REAL_ROUTE_CARD_INPUT_TICKET_TEMPLATE_NO_INSTANCE_NO_INPUT_LOADING",
        "ticket_template": ticket,
        "checks": checks,
        "metrics": {
            "required_ticket_fields": len(REQUIRED_TICKET_FIELDS),
            "required_preflight_checks": len(REQUIRED_PREFLIGHT_CHECKS),
            "forbidden_input_fields": len(FORBIDDEN_INPUT_FIELDS),
            "ticket_template_materialized": True,
            "ticket_instance_materialized": False,
            "approved_for_execution": False,
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
        "decision": "Created a real route-card input ticket template only. No ticket instance, real input authorization, route-card materialization, compiler handoff, trainer/model path, runtime, cleanup, or training was opened.",
    }


def validate_ticket_template(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    ticket = card.get("ticket_template") or {}
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    if any((ticket.get("authority") or {}).values()):
        failures.append("ticket_authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9139, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for field in REQUIRED_TICKET_FIELDS:
        if field not in ticket:
            failures.append(f"missing_ticket_field:{field}")
    if ticket.get("approved_for_execution") is not False:
        failures.append("ticket_approved_for_execution")
    if ticket.get("max_rows") != 0:
        failures.append("template_max_rows_not_zero")
    for key in [
        "ticket_instance_materialized",
        "approved_for_execution",
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
        if card["metrics"].get(key) is not False:
            failures.append(key)
    for key in ["real_judge_rows_used", "real_ranker_rows_used", "real_route_cards_materialized"]:
        if card["metrics"].get(key) != 0:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_ticket_template(registry)
    failures = validate_ticket_template(card, registry)
    TEMPLATE.write_text(json.dumps(card["ticket_template"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **card["metrics"]},
        "artifacts": {"ticket_template": str(TEMPLATE.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": card["decision"] if not failures else "Real route-card input ticket template failed.",
        "next_best_step": "Audit real route-card input ticket template before creating any ticket instance.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9140 Real Route-Card Input Ticket Template",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Created a template only. It is not an approved ticket instance and cannot authorize real input reads.",
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

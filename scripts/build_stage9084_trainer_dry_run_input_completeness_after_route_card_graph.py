#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9072_trainer_dry_run_documentation_refresh import RECOVERED_INPUTS as STAGE9072_INPUTS
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9072_trainer_dry_run_documentation_refresh import RECOVERED_INPUTS as STAGE9072_INPUTS  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9084
NAME = "stage9084_trainer_dry_run_input_completeness_after_route_card_graph"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9078 = ROOT / "runs/summaries/stage9078_source_output_ticket_graph_attachment.json"
SOURCE_9082 = ROOT / "runs/summaries/stage9082_route_card_audit_instance_graph_attachment.json"
SOURCE_9083 = ROOT / "runs/summaries/stage9083_current_frontier_reconciliation_after_route_card_graph.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_DRY_RUN_INPUT_COMPLETENESS_AFTER_ROUTE_CARD_GRAPH_STAGE9084.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CHECKLIST = OUT_DIR / "trainer_dry_run_input_completeness_after_route_card_graph.json"

ADDITIONAL_REQUIRED_INPUTS = [
    "source_output_ticket_authorization_card.json",
    "source_output_ticket_design_audit.json",
    "source_output_ticket_graph_attachment_card.json",
    "route_card_materialization_audit_instance_design.json",
    "route_card_materialization_audit_instance_audit.json",
    "route_card_audit_instance_graph_attachment_card.json",
    "route_card_materialization_audit_output.json",
    "route_to_trainer_loss_translation_status.json",
]

REQUIRED_BLOCKING_ASSERTIONS = [
    "source_output_ticket_instantiated_and_audited_before_any_source_access",
    "never_delete_arxiv_gate_present",
    "no_source_body_read_without_ticket",
    "no_route_card_materialization_without_ticket",
    "route_card_audit_instance_negative_cases_rejected",
    "compiler_handoff_blocked_until_route_card_audit_passes",
    "trainer_dry_run_blocked_until_route_card_audit_passes",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_checklist(registry: dict[str, Any]) -> dict[str, Any]:
    s9078 = load_json(SOURCE_9078)
    s9082 = load_json(SOURCE_9082)
    s9083 = load_json(SOURCE_9083)
    required_inputs = list(dict.fromkeys([*STAGE9072_INPUTS, *ADDITIONAL_REQUIRED_INPUTS]))
    checks = {
        "source_stage9078_passed": s9078.get("passed") is True,
        "source_stage9082_passed": s9082.get("passed") is True,
        "source_stage9083_passed": s9083.get("passed") is True,
        "stage9072_inputs_preserved": set(STAGE9072_INPUTS).issubset(set(required_inputs)),
        "additional_inputs_added": set(ADDITIONAL_REQUIRED_INPUTS).issubset(set(required_inputs)),
        "blocking_assertions_recorded": len(REQUIRED_BLOCKING_ASSERTIONS) >= 7,
        "source_output_graph_attached": (s9078.get("metrics") or {}).get("added_nodes", 0) >= 5,
        "route_card_graph_attached": (s9082.get("metrics") or {}).get("added_nodes", 0) >= 5,
        "stage9083_trainer_closed": (s9083.get("metrics") or {}).get("trainer_dry_run_ready_now") is False,
        "registry_frontier_stage9083": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9083,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TRAINER_DRY_RUN_INPUT_COMPLETENESS_REFRESH_NO_EXECUTION",
        "future_required_inputs": required_inputs,
        "additional_required_inputs": ADDITIONAL_REQUIRED_INPUTS,
        "required_blocking_assertions": REQUIRED_BLOCKING_ASSERTIONS,
        "checks": checks,
        "metrics": {
            "future_required_inputs": len(required_inputs),
            "additional_required_inputs": len(ADDITIONAL_REQUIRED_INPUTS),
            "required_blocking_assertions": len(REQUIRED_BLOCKING_ASSERTIONS),
            "trainer_dry_run_ready_now": False,
            "trainer_dry_run_executed_now": False,
            "source_output_ticket_instantiated_now": False,
            "route_cards_materialized_now": False,
            "candidate_rows_materialized": 0,
            "compiler_handoff_ready_now": False,
            "model_forward_attempted": False,
            "training_ready": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Trainer dry-run input completeness checklist now includes source/output ticket and route-card audit-instance controls. This refresh executes no trainer, loads no rows, materializes no route cards, and authorizes no training.",
    }


def validate_checklist(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9083, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for required in ADDITIONAL_REQUIRED_INPUTS:
        if required not in card.get("future_required_inputs", []):
            failures.append(f"missing_additional_input:{required}")
    for required in REQUIRED_BLOCKING_ASSERTIONS:
        if required not in card.get("required_blocking_assertions", []):
            failures.append(f"missing_blocking_assertion:{required}")
    for key in [
        "trainer_dry_run_ready_now",
        "trainer_dry_run_executed_now",
        "source_output_ticket_instantiated_now",
        "route_cards_materialized_now",
        "compiler_handoff_ready_now",
        "model_forward_attempted",
        "training_ready",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    if card["metrics"].get("candidate_rows_materialized") != 0:
        failures.append("candidate_rows_materialized")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_checklist(registry)
    failures = validate_checklist(card, registry)
    CHECKLIST.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **card["metrics"]},
        "artifacts": {"checklist": str(CHECKLIST.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": card["decision"] if not failures else "Trainer dry-run input completeness checklist refresh failed.",
        "next_best_step": "Audit this trainer dry-run input completeness checklist; do not execute trainer or load rows.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9084 Trainer Dry-Run Input Completeness After Route-Card Graph",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Refreshes the future trainer dry-run input checklist after source/output ticket and route-card audit-instance controls were attached to the graph.",
        "",
        f"Future required inputs: `{summary['metrics']['future_required_inputs']}`",
        f"Additional inputs: `{summary['metrics']['additional_required_inputs']}`",
        f"Trainer dry-run ready now: `{summary['metrics']['trainer_dry_run_ready_now']}`",
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
    marker = "## Stage9084 Trainer Dry-Run Input Completeness After Route-Card Graph"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9084 refreshes the future trainer dry-run input completeness checklist to include source/output ticket controls and route-card materialization audit instance controls.",
            "",
            "Trainer dry-run readiness remains false; no rows, source bodies, route cards, compiler handoff, trainer execution, model forward, decoder CE, denoise CE, runtime, /arxiv IO, or training are authorized.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

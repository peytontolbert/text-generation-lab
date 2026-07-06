#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9059_long_context_route_card_materialization_audit_contract import (
        REQUIRED_MATERIALIZATION_AUDITS,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9059_long_context_route_card_materialization_audit_contract import (  # type: ignore
        REQUIRED_MATERIALIZATION_AUDITS,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9080
NAME = "stage9080_no_data_route_card_materialization_audit_instance_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9059 = ROOT / "runs/summaries/stage9059_long_context_route_card_materialization_audit_contract.json"
SOURCE_9078 = ROOT / "runs/summaries/stage9078_source_output_ticket_graph_attachment.json"
SOURCE_9079 = ROOT / "runs/summaries/stage9079_current_frontier_reconciliation_after_source_output_graph.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NO_DATA_ROUTE_CARD_MATERIALIZATION_AUDIT_INSTANCE_DESIGN_STAGE9080.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "no_data_route_card_materialization_audit_instance_design.json"

FUTURE_REQUIRED_INPUTS = [
    "source_output_ticket_authorization_card.json",
    "future_candidate_metadata_index.jsonl",
    "future_source_lineage_card.json",
    "future_dataset_junk_ood_ranker_card.json",
    "future_shortcut_baseline_card.json",
    "future_counterfactual_obligation_card.json",
    "future_split_overlap_card.json",
    "future_loss_mask_card.json",
    "future_telemetry_contract.json",
]

FUTURE_REQUIRED_OUTPUTS = [
    "route_card_materialization_audit.json",
    "accepted_route_card_ids.jsonl",
    "rejected_route_card_ids.jsonl",
    "compiler_handoff_blocker_status.json",
    "route_to_trainer_loss_translation_status.json",
]

INSTANCE_TEMPLATE = {
    "instance_id": "future_stage9xxx_route_card_materialization_audit_instance_inactive",
    "contract_stage": "stage9059_long_context_route_card_materialization_audit_contract",
    "source_output_ticket_stage": "future_explicit_ticket_required",
    "required_inputs": FUTURE_REQUIRED_INPUTS,
    "required_outputs": FUTURE_REQUIRED_OUTPUTS,
    "required_materialization_audits": list(REQUIRED_MATERIALIZATION_AUDITS),
    "caps": {
        "max_candidate_metadata_rows": 0,
        "max_route_cards": 0,
        "max_output_bytes": 0,
    },
    "closed_now": {
        "instance_instantiated_now": False,
        "source_output_ticket_instantiated_now": False,
        "source_metadata_read_now": False,
        "row_bodies_read_now": False,
        "repository_source_bodies_read_now": False,
        "route_cards_materialized_now": False,
        "compiler_handoff_ready_now": False,
        "trainer_dry_run_ready_now": False,
        "training_ready_now": False,
    },
    "authority": dict(AUTHORITY_CLOSED),
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_design(registry: dict[str, Any]) -> dict[str, Any]:
    s9059 = load_json(SOURCE_9059)
    s9078 = load_json(SOURCE_9078)
    s9079 = load_json(SOURCE_9079)
    checks = {
        "source_stage9059_present": SOURCE_9059.exists(),
        "source_stage9059_passed": s9059.get("passed") is True,
        "source_stage9078_passed": s9078.get("passed") is True,
        "source_stage9079_passed": s9079.get("passed") is True,
        "required_inputs_recorded": len(FUTURE_REQUIRED_INPUTS) >= 9,
        "required_outputs_recorded": len(FUTURE_REQUIRED_OUTPUTS) >= 5,
        "required_audits_preserved": set(REQUIRED_MATERIALIZATION_AUDITS).issubset(set(INSTANCE_TEMPLATE["required_materialization_audits"])),
        "instance_closed_now": not any(INSTANCE_TEMPLATE["closed_now"].values()),
        "instance_authority_closed": not any(INSTANCE_TEMPLATE["authority"].values()),
        "stage9078_source_ticket_controls_graph_attached": (s9078.get("metrics") or {}).get("added_nodes", 0) >= 5,
        "stage9079_reconciled_closed": (s9079.get("metrics") or {}).get("ticket_instantiated_now") is False,
        "registry_frontier_stage9079": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9079,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "NO_DATA_ROUTE_CARD_MATERIALIZATION_AUDIT_INSTANCE_DESIGN_INACTIVE",
        "instance_template": INSTANCE_TEMPLATE,
        "checks": checks,
        "metrics": {
            "required_inputs": len(FUTURE_REQUIRED_INPUTS),
            "required_outputs": len(FUTURE_REQUIRED_OUTPUTS),
            "required_materialization_audits": len(REQUIRED_MATERIALIZATION_AUDITS),
            "instance_instantiated_now": False,
            "source_output_ticket_instantiated_now": False,
            "source_metadata_read_now": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
            "route_cards_materialized_now": False,
            "candidate_rows_materialized": 0,
            "compiler_handoff_ready_now": False,
            "trainer_dry_run_ready_now": False,
            "training_ready": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
            "cleanup_authorized_now": False,
            "model_forward_attempted": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "No-data route-card materialization audit instance is designed as inactive. It defines future inputs/outputs and required audits, but does not instantiate a source/output ticket, read metadata, read bodies, materialize route cards, compile manifests, run trainer dry run, or train.",
    }


def validate_design(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9079, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    template = card.get("instance_template") or {}
    if any((template.get("authority") or {}).values()):
        failures.append("template_authority_open")
    if any((template.get("closed_now") or {}).values()):
        failures.append("template_opened_current_operation")
    for key in [
        "instance_instantiated_now",
        "source_output_ticket_instantiated_now",
        "source_metadata_read_now",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
        "route_cards_materialized_now",
        "compiler_handoff_ready_now",
        "trainer_dry_run_ready_now",
        "training_ready",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
        "cleanup_authorized_now",
        "model_forward_attempted",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    if card["metrics"].get("candidate_rows_materialized") != 0:
        failures.append("candidate_rows_materialized")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_design(registry)
    failures = validate_design(card, registry)
    DESIGN.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **card["metrics"]},
        "artifacts": {"design": str(DESIGN.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": card["decision"] if not failures else "No-data route-card materialization audit instance design failed.",
        "next_best_step": "Audit this inactive route-card materialization audit instance design; do not instantiate source/output tickets or materialize route cards.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9080 No-Data Route-Card Materialization Audit Instance Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Defines an inactive future route-card materialization audit instance. No source/output ticket is instantiated and no route cards are materialized.",
        "",
        f"Required inputs: `{summary['metrics']['required_inputs']}`",
        f"Required outputs: `{summary['metrics']['required_outputs']}`",
        f"Route cards materialized now: `{summary['metrics']['route_cards_materialized_now']}`",
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
    marker = "## Stage9080 No-Data Route-Card Materialization Audit Instance Design"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9080 designs an inactive route-card materialization audit instance. It records future required inputs, outputs, and audits while keeping source/output tickets, metadata reads, body reads, route-card materialization, compiler handoff, trainer dry run, and training closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

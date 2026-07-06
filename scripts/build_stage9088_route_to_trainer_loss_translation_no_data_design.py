#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9062_long_context_loss_mask_compiler_preflight import (
        ROUTE_TO_TRAINER_LOSS_TRANSLATION,
        audit_loss_mask_preflight,
        translate_route_losses,
    )
    from scripts.build_stage9057_long_context_route_card_schema_contract import LOSS_KEYS as ROUTE_LOSS_KEYS
    from scripts.loss_mask_card import LOSS_KEYS as TRAINER_LOSS_KEYS
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9062_long_context_loss_mask_compiler_preflight import (  # type: ignore
        ROUTE_TO_TRAINER_LOSS_TRANSLATION,
        audit_loss_mask_preflight,
        translate_route_losses,
    )
    from build_stage9057_long_context_route_card_schema_contract import LOSS_KEYS as ROUTE_LOSS_KEYS  # type: ignore
    from loss_mask_card import LOSS_KEYS as TRAINER_LOSS_KEYS  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9088
NAME = "stage9088_route_to_trainer_loss_translation_no_data_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9062 = ROOT / "runs/summaries/stage9062_long_context_loss_mask_compiler_preflight.json"
SOURCE_9086 = ROOT / "runs/summaries/stage9086_trainer_dry_run_input_controls_graph_attachment.json"
SOURCE_9087 = ROOT / "runs/summaries/stage9087_current_frontier_reconciliation_after_trainer_input_graph.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROUTE_TO_TRAINER_LOSS_TRANSLATION_NO_DATA_DESIGN_STAGE9088.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "route_to_trainer_loss_translation_no_data_design.json"

REQUIRED_INPUTS = [
    "source_output_ticket_authorization_card.json",
    "source_output_ticket_design_audit.json",
    "source_output_ticket_graph_attachment_card.json",
    "route_card_materialization_audit_instance_design.json",
    "route_card_materialization_audit_instance_audit.json",
    "route_card_audit_instance_graph_attachment_card.json",
    "route_card_materialization_audit_output.json",
    "trainer_dry_run_input_completeness_audit.json",
    "trainer_dry_run_input_controls_graph_attachment_card.json",
]

TRANSLATION_OUTPUTS = [
    "route_to_trainer_loss_translation_status.json",
    "route_loss_to_trainer_loss_map.json",
    "closed_loss_mask_card_template.json",
    "structured_aux_only_loss_mask_template.json",
    "translation_negative_case_audit.json",
]

BLOCKING_ASSERTIONS = [
    "all_required_inputs_present_before_translation",
    "no_route_card_materialization_without_ticket",
    "no_source_body_read_without_ticket",
    "route_card_audit_output_passed_before_translation",
    "trainer_input_completeness_audit_passed_before_translation",
    "decoder_ce_remains_closed",
    "denoise_ce_remains_closed",
    "runtime_reward_remains_closed",
    "model_forward_remains_closed",
]

FORBIDDEN_TRAINER_LOSSES_NOW = {"decoder_ce", "denoise_ce", "runtime_reward"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def closed_route_card() -> dict[str, Any]:
    return {
        "route_card_id": "stage9088_closed_no_data_example",
        "route": "NEEDS_SOURCE_OUTPUT_TICKET",
        "artifact_status": {name: False for name in REQUIRED_INPUTS},
        "losses_enabled": {key: False for key in ROUTE_LOSS_KEYS},
        "translation_ready": False,
        "compiler_ready": False,
        "trainer_dry_run_ready": False,
        "model_input_ready": False,
        "training_ready": False,
        "authority": dict(AUTHORITY_CLOSED),
    }


def structured_after_all_controls_card() -> dict[str, Any]:
    card = closed_route_card()
    card.update({
        "route_card_id": "stage9088_structured_after_all_controls_example",
        "route": "KEEP_STRUCTURED_AFTER_SOURCE_AND_ROUTE_AUDITS",
        "artifact_status": {name: True for name in REQUIRED_INPUTS},
        "losses_enabled": {key: key == "structured_aux_ce" for key in ROUTE_LOSS_KEYS},
        "translation_ready": True,
        "compiler_ready": False,
        "trainer_dry_run_ready": False,
        "model_input_ready": False,
        "training_ready": False,
    })
    return card


def audit_translation_design(route_card: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    route_losses = route_card.get("losses_enabled") or {}
    for key in ROUTE_LOSS_KEYS:
        if key not in route_losses:
            failures.append(f"missing_route_loss:{key}")
    unknown_route_losses = sorted(set(route_losses) - set(ROUTE_LOSS_KEYS))
    for key in unknown_route_losses:
        failures.append(f"unknown_route_loss:{key}")
    if route_card.get("translation_ready") is True:
        artifacts = route_card.get("artifact_status") or {}
        missing = [name for name in REQUIRED_INPUTS if artifacts.get(name) is not True]
        if missing:
            failures.append("translation_ready_missing_required_inputs")
    elif any(route_losses.values()):
        failures.append("loss_open_before_translation_ready")
    trainer_losses = translate_route_losses({key: bool(route_losses.get(key, False)) for key in ROUTE_LOSS_KEYS})
    for key in FORBIDDEN_TRAINER_LOSSES_NOW:
        if trainer_losses.get(key):
            failures.append(f"forbidden_trainer_loss_open:{key}")
    if route_card.get("compiler_ready") is True:
        failures.append("compiler_ready_not_allowed_by_design")
    if route_card.get("trainer_dry_run_ready") is True:
        failures.append("trainer_dry_run_ready_not_allowed_by_design")
    if route_card.get("model_input_ready") is True:
        failures.append("model_input_ready_not_allowed_by_design")
    if route_card.get("training_ready") is True:
        failures.append("training_ready_not_allowed_by_design")
    if any((route_card.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED):
        failures.append("authority_open")
    return failures


def run_negative_cases() -> dict[str, Any]:
    base = closed_route_card()
    cases: dict[str, dict[str, Any]] = {}
    loss_before_ready = copy.deepcopy(base)
    loss_before_ready["losses_enabled"]["structured_aux_ce"] = True
    cases["structured_loss_before_translation_ready"] = loss_before_ready
    missing_input = copy.deepcopy(structured_after_all_controls_card())
    missing_input["artifact_status"]["route_card_materialization_audit_output.json"] = False
    cases["translation_ready_missing_route_card_audit_output"] = missing_input
    decoder_open = copy.deepcopy(structured_after_all_controls_card())
    decoder_open["losses_enabled"]["decoder_ce"] = True
    cases["decoder_ce_open"] = decoder_open
    denoise_open = copy.deepcopy(structured_after_all_controls_card())
    denoise_open["losses_enabled"]["denoise_ce"] = True
    cases["denoise_ce_open"] = denoise_open
    runtime_open = copy.deepcopy(structured_after_all_controls_card())
    runtime_open["losses_enabled"]["runtime_reward"] = True
    cases["runtime_reward_open"] = runtime_open
    trainer_ready = copy.deepcopy(structured_after_all_controls_card())
    trainer_ready["trainer_dry_run_ready"] = True
    cases["trainer_dry_run_ready"] = trainer_ready
    model_ready = copy.deepcopy(structured_after_all_controls_card())
    model_ready["model_input_ready"] = True
    cases["model_input_ready"] = model_ready
    authority_open = copy.deepcopy(structured_after_all_controls_card())
    authority_open["authority"]["model_execution_authorized_next"] = True
    cases["authority_open"] = authority_open
    return {name: {"failures": audit_translation_design(card), "rejected": bool(audit_translation_design(card))} for name, card in cases.items()}


def build_design(registry: dict[str, Any]) -> dict[str, Any]:
    s9062 = load_json(SOURCE_9062)
    s9086 = load_json(SOURCE_9086)
    s9087 = load_json(SOURCE_9087)
    closed_failures = audit_translation_design(closed_route_card())
    structured_failures = audit_translation_design(structured_after_all_controls_card())
    prior_structured_failures = audit_loss_mask_preflight({
        "losses_enabled": {key: key == "structured_aux_ce" for key in ROUTE_LOSS_KEYS},
        "artifact_status": {},
        "compiler_ready": False,
        "training_ready": False,
        "model_input_ready": False,
        "authority": dict(AUTHORITY_CLOSED),
    })
    negatives = run_negative_cases()
    checks = {
        "source_stage9062_passed": s9062.get("passed") is True,
        "source_stage9086_passed": s9086.get("passed") is True,
        "source_stage9087_passed": s9087.get("passed") is True,
        "translation_keys_cover_route_losses": set(ROUTE_LOSS_KEYS) == set(ROUTE_TO_TRAINER_LOSS_TRANSLATION),
        "trainer_loss_keys_known": set(FORBIDDEN_TRAINER_LOSSES_NOW).issubset(set(TRAINER_LOSS_KEYS)),
        "required_inputs_recorded": len(REQUIRED_INPUTS) >= 9,
        "translation_outputs_recorded": len(TRANSLATION_OUTPUTS) >= 5,
        "blocking_assertions_recorded": len(BLOCKING_ASSERTIONS) >= 9,
        "closed_card_passes": closed_failures == [],
        "structured_after_all_controls_passes_design_only": structured_failures == [],
        "prior_preflight_still_blocks_loss_before_compiler_ready": "loss_open_before_compiler_ready" in prior_structured_failures,
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "stage9087_frontier": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9087,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ROUTE_TO_TRAINER_LOSS_TRANSLATION_DESIGN_NO_DATA",
        "route_to_trainer_loss_translation": ROUTE_TO_TRAINER_LOSS_TRANSLATION,
        "required_inputs": REQUIRED_INPUTS,
        "translation_outputs": TRANSLATION_OUTPUTS,
        "blocking_assertions": BLOCKING_ASSERTIONS,
        "forbidden_trainer_losses_now": sorted(FORBIDDEN_TRAINER_LOSSES_NOW),
        "checks": checks,
        "closed_card_failures": closed_failures,
        "structured_after_all_controls_failures": structured_failures,
        "prior_preflight_structured_failures": prior_structured_failures,
        "negative_cases": negatives,
        "metrics": {
            "route_loss_keys": len(ROUTE_LOSS_KEYS),
            "trainer_loss_keys": len(TRAINER_LOSS_KEYS),
            "required_inputs": len(REQUIRED_INPUTS),
            "translation_outputs": len(TRANSLATION_OUTPUTS),
            "blocking_assertions": len(BLOCKING_ASSERTIONS),
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
            "translation_ready_now": False,
            "compiler_handoff_ready_now": False,
            "trainer_dry_run_ready_now": False,
            "trainer_dry_run_executed_now": False,
            "model_input_rows_now": 0,
            "candidate_rows_materialized": 0,
            "route_cards_materialized_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Designed the no-data route-to-trainer-loss translation layer. It documents how future audited route-card losses translate to trainer loss masks while keeping translation, compiler handoff, trainer dry run, model input rows, decoder CE, denoise CE, runtime, /arxiv IO, and training closed.",
    }


def validate_design(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9087, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "translation_ready_now",
        "compiler_handoff_ready_now",
        "trainer_dry_run_ready_now",
        "trainer_dry_run_executed_now",
        "route_cards_materialized_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    for key in ["model_input_rows_now", "candidate_rows_materialized"]:
        if card["metrics"].get(key) != 0:
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
        "decision": design["decision"] if not failures else "Route-to-trainer-loss translation no-data design failed.",
        "next_best_step": "Audit the route-to-trainer-loss translation no-data design; do not execute trainer or load rows.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9088 Route-To-Trainer-Loss Translation No-Data Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Defines a no-data translation layer from future audited route-card losses to trainer loss-mask keys. It does not materialize route cards, load rows, run compiler handoff, execute a trainer, or authorize model execution.",
        "",
        f"Required inputs: `{design['metrics']['required_inputs']}`",
        f"Translation outputs: `{design['metrics']['translation_outputs']}`",
        f"Negative cases rejected: `{design['metrics']['negative_cases_rejected']}`",
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
    marker = "## Stage9088 Route-To-Trainer-Loss Translation No-Data Design"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9088 designs the no-data route-to-trainer-loss translation layer after source/output ticket, route-card audit, and trainer input graph controls. It maps future audited route-card loss intents to trainer loss-mask keys while keeping translation, compiler handoff, trainer execution, model forward, row loading, /arxiv IO, decoder CE, denoise CE, runtime, and training closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

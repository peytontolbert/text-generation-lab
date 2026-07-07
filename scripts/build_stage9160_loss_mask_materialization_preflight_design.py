#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9128_loss_mask_card_schema_recovery_design import (
        REQUIRED_DISABLED_BY_DEFAULT,
        REQUIRED_LOSS_MASK_FIELDS,
        REQUIRED_TELEMETRY,
    )
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9128_loss_mask_card_schema_recovery_design import (  # type: ignore
        REQUIRED_DISABLED_BY_DEFAULT,
        REQUIRED_LOSS_MASK_FIELDS,
        REQUIRED_TELEMETRY,
    )
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9160
NAME = "stage9160_loss_mask_materialization_preflight_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9159 = ROOT / "runs/summaries/stage9159_route_to_loss_readiness_refresh_after_inventory_gates.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LOSS_MASK_MATERIALIZATION_PREFLIGHT_DESIGN_STAGE9160.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "loss_mask_materialization_preflight_design.json"

REQUIRED_INPUTS_BEFORE_LOSS_MASKS = [
    "stage9159_route_to_loss_readiness_refresh_passed",
    "metadata_inventory_output_audited",
    "route_cards_jsonl_materialized_and_audited",
    "route_card_candidate_quality_gate_applied",
    "route_to_loss_translation_status_passed",
    "route_loss_to_trainer_loss_map_validated",
    "loss_mask_schema_audit_passed",
    "all_rows_have_authority_closed",
    "all_forbidden_losses_disabled_by_default",
]

LOSS_MASK_PREFLIGHT_CHECKS = [
    "row_id_join_integrity",
    "route_card_ref_resolves",
    "enabled_losses_subset_of_route_translation",
    "disabled_losses_include_forbidden_defaults",
    "decoder_ce_requires_keep_bounded_decoder_and_budget_ok",
    "denoise_ce_requires_repair_route_and_clean_target",
    "runtime_reward_forbidden",
    "source_body_loss_forbidden",
    "gemma_distill_loss_forbidden",
    "harness_score_loss_forbidden",
    "telemetry_required_for_every_enabled_loss",
    "authority_closed_for_every_row",
]

BLOCKED_OUTPUTS = [
    "loss_mask_cards.jsonl",
    "loss_mask_authority_audit.json",
    "loss_mask_enforcement_audit.json",
    "trainer_dry_run_input.json",
]

NEGATIVE_CASES = [
    "source_stage_missing",
    "missing_required_input",
    "missing_preflight_check",
    "missing_blocked_output",
    "missing_loss_mask_field",
    "missing_disabled_default",
    "missing_telemetry",
    "loss_masks_materialized",
    "trainer_input_materialized",
    "compiler_handoff_ready",
    "trainer_ready",
    "training_authorized",
    "decoder_ce_authorized",
    "denoise_ce_authorized",
    "runtime_authorized",
    "authority_open",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_design(source_9159: dict[str, Any] | None = None) -> dict[str, Any]:
    source_9159 = source_9159 if source_9159 is not None else load_json(SOURCE_9159)
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "design_type": "loss_mask_materialization_preflight_design_v1",
        "source_stage9159_passed": source_9159.get("passed") is True,
        "required_inputs_before_loss_masks": list(REQUIRED_INPUTS_BEFORE_LOSS_MASKS),
        "required_loss_mask_fields": list(REQUIRED_LOSS_MASK_FIELDS),
        "required_disabled_by_default": list(REQUIRED_DISABLED_BY_DEFAULT),
        "required_telemetry": list(REQUIRED_TELEMETRY),
        "loss_mask_preflight_checks": list(LOSS_MASK_PREFLIGHT_CHECKS),
        "blocked_outputs": list(BLOCKED_OUTPUTS),
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "design_only": True,
            "source_stage9159_passed": source_9159.get("passed") is True,
            "required_inputs_before_loss_masks": len(REQUIRED_INPUTS_BEFORE_LOSS_MASKS),
            "required_loss_mask_fields": len(REQUIRED_LOSS_MASK_FIELDS),
            "required_disabled_by_default": len(REQUIRED_DISABLED_BY_DEFAULT),
            "required_telemetry": len(REQUIRED_TELEMETRY),
            "loss_mask_preflight_checks": len(LOSS_MASK_PREFLIGHT_CHECKS),
            "blocked_outputs": len(BLOCKED_OUTPUTS),
            "metadata_inventory_executed_now": False,
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
            "loss_mask_cards_materialized_now": False,
            "trainer_input_materialized_now": False,
            "compiler_handoff_ready_now": False,
            "trainer_dry_run_ready_now": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_accessed": False,
            "file_content_read": False,
            "dataset_rows_loaded": False,
            "cleanup_authorized_now": False,
        },
        "decision": (
            "Designed loss-mask materialization preflight against the refreshed "
            "route-to-loss blockers. This stage does not materialize loss masks, "
            "trainer inputs, compiler handoff artifacts, or training rows."
        ),
    }


def validate_design(design: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    metrics = design.get("metrics") or {}
    if design.get("source_stage9159_passed") is not True or metrics.get("source_stage9159_passed") is not True:
        failures.append("source_stage9159_not_passed")
    for item in REQUIRED_INPUTS_BEFORE_LOSS_MASKS:
        if item not in design.get("required_inputs_before_loss_masks", []):
            failures.append(f"missing_required_input:{item}")
    for field in REQUIRED_LOSS_MASK_FIELDS:
        if field not in design.get("required_loss_mask_fields", []):
            failures.append(f"missing_loss_mask_field:{field}")
    for item in REQUIRED_DISABLED_BY_DEFAULT:
        if item not in design.get("required_disabled_by_default", []):
            failures.append(f"missing_disabled_default:{item}")
    for item in REQUIRED_TELEMETRY:
        if item not in design.get("required_telemetry", []):
            failures.append(f"missing_telemetry:{item}")
    for item in LOSS_MASK_PREFLIGHT_CHECKS:
        if item not in design.get("loss_mask_preflight_checks", []):
            failures.append(f"missing_preflight_check:{item}")
    for item in BLOCKED_OUTPUTS:
        if item not in design.get("blocked_outputs", []):
            failures.append(f"missing_blocked_output:{item}")
    if any((design.get("authority") or {}).values()):
        failures.append("authority_open")
    false_keys = [
        "metadata_inventory_executed_now",
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
        "loss_mask_cards_materialized_now",
        "trainer_input_materialized_now",
        "compiler_handoff_ready_now",
        "trainer_dry_run_ready_now",
        "trainer_executed_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "arxiv_accessed",
        "file_content_read",
        "dataset_rows_loaded",
        "cleanup_authorized_now",
    ]
    for key in false_keys:
        if metrics.get(key) is not False:
            failures.append(key)
    return failures


def run_negative_cases() -> dict[str, Any]:
    base = build_design()
    cases: dict[str, dict[str, Any]] = {}
    for name in NEGATIVE_CASES:
        candidate = copy.deepcopy(base)
        if name == "source_stage_missing":
            candidate["source_stage9159_passed"] = False
            candidate["metrics"]["source_stage9159_passed"] = False
        elif name == "missing_required_input":
            candidate["required_inputs_before_loss_masks"].remove("route_cards_jsonl_materialized_and_audited")
        elif name == "missing_preflight_check":
            candidate["loss_mask_preflight_checks"].remove("decoder_ce_requires_keep_bounded_decoder_and_budget_ok")
        elif name == "missing_blocked_output":
            candidate["blocked_outputs"].remove("loss_mask_cards.jsonl")
        elif name == "missing_loss_mask_field":
            candidate["required_loss_mask_fields"].remove("loss_authority_evidence")
        elif name == "missing_disabled_default":
            candidate["required_disabled_by_default"].remove("runtime_reward")
        elif name == "missing_telemetry":
            candidate["required_telemetry"].remove("loss_mask_enforcement_audit")
        elif name == "loss_masks_materialized":
            candidate["metrics"]["loss_mask_cards_materialized_now"] = True
        elif name == "trainer_input_materialized":
            candidate["metrics"]["trainer_input_materialized_now"] = True
        elif name == "compiler_handoff_ready":
            candidate["metrics"]["compiler_handoff_ready_now"] = True
        elif name == "trainer_ready":
            candidate["metrics"]["trainer_dry_run_ready_now"] = True
        elif name == "training_authorized":
            candidate["metrics"]["training_authorized"] = True
        elif name == "decoder_ce_authorized":
            candidate["metrics"]["decoder_ce_authorized"] = True
        elif name == "denoise_ce_authorized":
            candidate["metrics"]["denoise_ce_authorized"] = True
        elif name == "runtime_authorized":
            candidate["metrics"]["runtime_authorized_flag"] = True
        elif name == "authority_open":
            candidate["authority"]["model_execution_authorized_next"] = True
        cases[name] = candidate
    return {
        name: {"failures": validate_design(candidate), "rejected": bool(validate_design(candidate))}
        for name, candidate in cases.items()
    }


def build_summary() -> dict[str, Any]:
    design = build_design()
    failures = validate_design(design)
    negatives = run_negative_cases()
    checks = {
        "design_passes": failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "loss_mask_output_blocked": "loss_mask_cards.jsonl" in design["blocked_outputs"],
        "trainer_input_blocked": "trainer_dry_run_input.json" in design["blocked_outputs"],
        "authority_closed": not any(design["authority"].values()),
    }
    all_failures = [key for key, value in checks.items() if value is not True]
    all_failures.extend(failures)
    passed = not all_failures
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "checks": checks,
        "failures": all_failures,
        "design": design,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **design["metrics"],
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
        },
        "decision": design["decision"] if passed else "Loss-mask materialization preflight design failed validation.",
        "next_best_step": "Audit the loss-mask materialization preflight; still do not materialize loss masks or train.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = build_summary()
    DESIGN.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    public_summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **summary["metrics"], "failures": summary["failures"]},
        "artifacts": {"design": str(DESIGN.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": summary["decision"],
        "next_best_step": summary["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(public_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9160 Loss-Mask Materialization Preflight Design",
        "",
        f"Passed: `{public_summary['passed']}`",
        "",
        "Designs the loss-mask materialization preflight without materializing loss masks.",
        "",
        f"Required inputs: `{summary['metrics']['required_inputs_before_loss_masks']}`",
        f"Preflight checks: `{summary['metrics']['loss_mask_preflight_checks']}`",
        f"Negative cases rejected: `{summary['metrics']['negative_cases_rejected']}/{summary['metrics']['negative_cases']}`",
        "",
        f"Next: {public_summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME and row.get("stage") != STAGE]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": public_summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": public_summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry_json["rows"] = rows
    registry_json["passed"] = public_summary["passed"]
    registry_json["metrics"] = {
        **(registry_json.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": public_summary["next_best_step"],
        "max_stage": max(STAGE, int((registry_json.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(public_summary, indent=2, sort_keys=True))
    raise SystemExit(0 if public_summary["passed"] else 1)


if __name__ == "__main__":
    main()

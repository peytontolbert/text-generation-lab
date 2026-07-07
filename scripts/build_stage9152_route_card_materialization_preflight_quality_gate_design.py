#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9152
NAME = "stage9152_route_card_materialization_preflight_quality_gate_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9150 = ROOT / "runs/summaries/stage9150_metadata_only_inventory_runner_dry_run_audit.json"
SOURCE_9151 = ROOT / "runs/summaries/stage9151_route_card_candidate_quality_gate_contract.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROUTE_CARD_MATERIALIZATION_PREFLIGHT_QUALITY_GATE_DESIGN_STAGE9152.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "route_card_materialization_preflight_quality_gate_design.json"

PREFLIGHT_INPUTS = [
    "stage9150_metadata_only_inventory_runner_dry_run_audit",
    "stage9151_route_card_candidate_quality_gate_contract",
    "future_explicit_inventory_execution_ticket",
    "future_metadata_only_repo_local_path_inventory_manifest",
    "future_real_route_card_input_ticket_instance",
    "route_card_schema_recovery_contract",
    "route_card_materializer_contract",
]

PREFLIGHT_SECTIONS = [
    "source_stage_guard",
    "inventory_execution_ticket_guard",
    "repo_local_path_guard",
    "metadata_only_inventory_guard",
    "candidate_required_field_guard",
    "candidate_quality_gate_guard",
    "anti_cheat_and_authority_guard",
    "route_schema_guard",
    "loss_mask_policy_closed_guard",
    "materialization_output_guard",
    "compiler_handoff_blocker",
    "trainer_runtime_blocker",
]

REQUIRED_PRECHECKS = [
    "stage9150_passed",
    "stage9151_passed",
    "candidate_quality_gate_contract_attached",
    "future_inventory_ticket_required",
    "future_ticket_instance_required",
    "repo_local_inventory_paths_only",
    "arxiv_forbidden",
    "file_content_reads_forbidden",
    "json_parse_forbidden_until_inventory_execution_authorized",
    "jsonl_row_count_forbidden_until_inventory_execution_authorized",
    "candidate_rows_not_loaded_now",
    "route_cards_not_materialized_now",
    "loss_masks_not_materialized_now",
    "compiler_handoff_not_ready_now",
    "trainer_not_executed_now",
    "authority_closed",
]

OUTPUTS_BLOCKED_UNTIL_SEPARATE_AUDIT = [
    "route_cards.jsonl",
    "route_card_materialization_audit.json",
    "route_reason_counts.json",
    "route_cell_card.json",
    "route_to_loss_ready_blocker_card.json",
]

NEGATIVE_CASES = [
    "source_stage9150_missing",
    "source_stage9151_missing",
    "quality_gate_not_attached",
    "missing_preflight_section",
    "missing_required_precheck",
    "missing_blocked_output",
    "inventory_executed_now",
    "metadata_inventory_loaded_now",
    "file_content_read",
    "json_parsed",
    "jsonl_rows_counted",
    "candidate_rows_loaded",
    "route_cards_materialized",
    "loss_masks_materialized",
    "compiler_handoff_ready",
    "trainer_executed",
    "training_authorized",
    "authority_open",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_design(source_9150: dict[str, Any] | None = None, source_9151: dict[str, Any] | None = None) -> dict[str, Any]:
    source_9150 = source_9150 if source_9150 is not None else load_json(SOURCE_9150)
    source_9151 = source_9151 if source_9151 is not None else load_json(SOURCE_9151)
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "contract_type": "route_card_materialization_preflight_quality_gate_design_v1",
        "purpose": (
            "Define the future no-execution preflight that must attach the Stage9151 "
            "candidate quality gate before any metadata-inventory-derived route-card "
            "materialization can run."
        ),
        "preflight_inputs": list(PREFLIGHT_INPUTS),
        "preflight_sections": list(PREFLIGHT_SECTIONS),
        "required_prechecks": list(REQUIRED_PRECHECKS),
        "outputs_blocked_until_separate_audit": list(OUTPUTS_BLOCKED_UNTIL_SEPARATE_AUDIT),
        "quality_gate_attachment": {
            "required": True,
            "source_stage": 9151,
            "contract_name": "route_card_candidate_quality_gate_v1",
            "must_validate_before": [
                "route_card_materializer_reads_candidate_rows",
                "route_cards_jsonl_write",
                "route_to_loss_translation",
                "compiler_handoff",
            ],
        },
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "design_only": True,
            "source_stage9150_passed": source_9150.get("passed") is True,
            "source_stage9151_passed": source_9151.get("passed") is True,
            "candidate_quality_gate_attached": True,
            "inventory_runner_executed_now": False,
            "metadata_path_inventory_loaded_now": False,
            "path_inventory_rows_loaded": 0,
            "candidate_rows_loaded": 0,
            "file_content_read": False,
            "json_parsed": False,
            "jsonl_rows_counted": False,
            "dataset_rows_loaded": False,
            "arxiv_accessed": False,
            "hidden_eval_allowed": False,
            "locked_eval_allowed": False,
            "route_cards_materialized_now": False,
            "loss_mask_cards_materialized_now": False,
            "compiler_handoff_ready_now": False,
            "trainer_dry_run_passed_now": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "decision": (
            "This design attaches the candidate quality gate to the future route-card "
            "materialization preflight. It does not execute inventory, load candidate "
            "rows, read file bodies, parse JSON/JSONL, materialize route cards, compile "
            "loss masks, hand off to the compiler, or authorize training."
        ),
    }


def validate_design(design: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    metrics = design.get("metrics") or {}
    if metrics.get("source_stage9150_passed") is not True:
        failures.append("source_stage9150_not_passed")
    if metrics.get("source_stage9151_passed") is not True:
        failures.append("source_stage9151_not_passed")
    if metrics.get("candidate_quality_gate_attached") is not True:
        failures.append("candidate_quality_gate_not_attached")
    for item in PREFLIGHT_INPUTS:
        if item not in design.get("preflight_inputs", []):
            failures.append(f"missing_preflight_input:{item}")
    for item in PREFLIGHT_SECTIONS:
        if item not in design.get("preflight_sections", []):
            failures.append(f"missing_preflight_section:{item}")
    for item in REQUIRED_PRECHECKS:
        if item not in design.get("required_prechecks", []):
            failures.append(f"missing_required_precheck:{item}")
    for item in OUTPUTS_BLOCKED_UNTIL_SEPARATE_AUDIT:
        if item not in design.get("outputs_blocked_until_separate_audit", []):
            failures.append(f"missing_blocked_output:{item}")
    if not (design.get("quality_gate_attachment") or {}).get("required"):
        failures.append("quality_gate_attachment_not_required")
    if any((design.get("authority") or {}).values()):
        failures.append("authority_open")

    closed_false = [
        "inventory_runner_executed_now",
        "metadata_path_inventory_loaded_now",
        "file_content_read",
        "json_parsed",
        "jsonl_rows_counted",
        "dataset_rows_loaded",
        "arxiv_accessed",
        "hidden_eval_allowed",
        "locked_eval_allowed",
        "route_cards_materialized_now",
        "loss_mask_cards_materialized_now",
        "compiler_handoff_ready_now",
        "trainer_dry_run_passed_now",
        "trainer_executed_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "network_upload_performed",
        "cleanup_authorized_now",
    ]
    for key in closed_false:
        if metrics.get(key) is not False:
            failures.append(key)
    for key in ["path_inventory_rows_loaded", "candidate_rows_loaded"]:
        if metrics.get(key) != 0:
            failures.append(key)
    return failures


def run_negative_cases() -> dict[str, Any]:
    base = build_design()
    cases: dict[str, dict[str, Any]] = {}
    for name in NEGATIVE_CASES:
        candidate = copy.deepcopy(base)
        if name == "source_stage9150_missing":
            candidate["metrics"]["source_stage9150_passed"] = False
        elif name == "source_stage9151_missing":
            candidate["metrics"]["source_stage9151_passed"] = False
        elif name == "quality_gate_not_attached":
            candidate["metrics"]["candidate_quality_gate_attached"] = False
            candidate["quality_gate_attachment"]["required"] = False
        elif name == "missing_preflight_section":
            candidate["preflight_sections"].remove("candidate_quality_gate_guard")
        elif name == "missing_required_precheck":
            candidate["required_prechecks"].remove("candidate_quality_gate_contract_attached")
        elif name == "missing_blocked_output":
            candidate["outputs_blocked_until_separate_audit"].remove("route_cards.jsonl")
        elif name == "inventory_executed_now":
            candidate["metrics"]["inventory_runner_executed_now"] = True
        elif name == "metadata_inventory_loaded_now":
            candidate["metrics"]["metadata_path_inventory_loaded_now"] = True
            candidate["metrics"]["path_inventory_rows_loaded"] = 1
        elif name == "file_content_read":
            candidate["metrics"]["file_content_read"] = True
        elif name == "json_parsed":
            candidate["metrics"]["json_parsed"] = True
        elif name == "jsonl_rows_counted":
            candidate["metrics"]["jsonl_rows_counted"] = True
        elif name == "candidate_rows_loaded":
            candidate["metrics"]["candidate_rows_loaded"] = 1
        elif name == "route_cards_materialized":
            candidate["metrics"]["route_cards_materialized_now"] = True
        elif name == "loss_masks_materialized":
            candidate["metrics"]["loss_mask_cards_materialized_now"] = True
        elif name == "compiler_handoff_ready":
            candidate["metrics"]["compiler_handoff_ready_now"] = True
        elif name == "trainer_executed":
            candidate["metrics"]["trainer_executed_now"] = True
        elif name == "training_authorized":
            candidate["metrics"]["training_authorized"] = True
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
        "quality_gate_attached": design["metrics"]["candidate_quality_gate_attached"] is True,
        "no_inventory_execution": design["metrics"]["inventory_runner_executed_now"] is False,
        "no_candidate_loading": design["metrics"]["candidate_rows_loaded"] == 0,
        "no_route_materialization": design["metrics"]["route_cards_materialized_now"] is False,
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
            "preflight_inputs": len(PREFLIGHT_INPUTS),
            "preflight_sections": len(PREFLIGHT_SECTIONS),
            "required_prechecks": len(REQUIRED_PRECHECKS),
            "blocked_outputs": len(OUTPUTS_BLOCKED_UNTIL_SEPARATE_AUDIT),
        },
        "decision": design["decision"] if passed else "Route-card materialization preflight quality-gate design failed validation.",
        "next_best_step": (
            "Audit the Stage9152 preflight design, then require a separate explicit "
            "execution ticket before any metadata inventory or route-card materializer run."
        ),
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
        "# Stage9152 Route-Card Materialization Preflight Quality-Gate Design",
        "",
        f"Passed: `{public_summary['passed']}`",
        "",
        "Defines a design-only preflight that attaches the Stage9151 candidate quality gate before future route-card materialization.",
        "",
        f"Preflight sections: `{summary['metrics']['preflight_sections']}`",
        f"Required prechecks: `{summary['metrics']['required_prechecks']}`",
        f"Blocked outputs pending separate audit: `{summary['metrics']['blocked_outputs']}`",
        f"Negative cases rejected: `{summary['metrics']['negative_cases_rejected']}/{summary['metrics']['negative_cases']}`",
        "",
        f"Next: {public_summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")

    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME and row.get("stage") != STAGE]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": public_summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": public_summary["next_best_step"],
    })
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

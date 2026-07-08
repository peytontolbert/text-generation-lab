#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9229
NAME = "stage9229_family_audit_design_output_schema"
PREV_SUMMARY = ROOT / "runs/summaries/stage9228_request_to_audit_instantiation_blocker.json"
PREV_CARD = ROOT / "runs/local/artifacts/stage9228_request_to_audit_instantiation_blocker/request_to_audit_instantiation_blocker.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "family_audit_design_output_schema.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FAMILY_AUDIT_DESIGN_OUTPUT_SCHEMA_STAGE9229.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"

SUPPORTED_FAMILIES = [
    "structured_policy_probe",
    "bounded_decoder_ce_probe",
    "denoise_repair_probe",
]

ALLOWED_DESIGN_OUTPUT_FILES = [
    "family_specific_final_preexecution_audit_design.json",
    "family_specific_final_preexecution_audit_design.md",
    "test_family_specific_final_preexecution_audit_design.py",
]

REQUIRED_DESIGN_FIELDS = [
    "selected_family",
    "validated_request_ref",
    "inactive_template_ref",
    "source_inactive_ticket_ref",
    "source_inactive_ticket_audit_ref",
    "selected_manifest_ref",
    "selected_manifest_hash",
    "selected_loss_mask_ref",
    "selected_loss_mask_hash",
    "row_caps",
    "trainer_command_surface_expectations",
    "runtime_assertion_expectations",
    "telemetry_artifact_expectations",
    "safe_cleanup_dry_run_expectations",
    "authority_closure_expectations",
    "worktree_scope_expectations",
    "same_stage_execution_authorized",
    "next_stage_execution_authorized",
]

FAMILY_REQUIRED_FIELDS = {
    "structured_policy_probe": [
        "structured_aux_only_loss_mask_expected",
        "decoder_ce_weight_zero_expected",
        "denoise_weight_zero_expected",
        "row_field_logits_required",
        "confusion_and_collapse_audit_required",
    ],
    "bounded_decoder_ce_probe": [
        "bounded_decoder_only_loss_mask_expected",
        "target_token_cap_expected",
        "row_token_loss_required",
        "eos_short_junk_repetition_leak_audit_required",
        "decoder_delta_guard_required",
    ],
    "denoise_repair_probe": [
        "denoise_only_loss_mask_expected",
        "target_resolver_readonly_expected",
        "repair_pair_integrity_required",
        "repair_output_quality_required",
        "no_runtime_verifier_execution_expected",
    ],
}

FORBIDDEN_DESIGN_FIELDS = [
    "live_ticket_path",
    "trainer_command_to_execute",
    "model_output_path",
    "checkpoint_path",
    "cleanup_result_path",
    "runtime_result_path",
    "arxiv_inventory_path",
    "source_body_path",
    "patch_body_path",
]

CLOSED_FIELD_DEFAULTS = {
    "same_stage_execution_authorized": False,
    "next_stage_execution_authorized": False,
    "trainer_execution_authorized": False,
    "model_execution_authorized": False,
    "checkpoint_export_authorized": False,
    "cleanup_authorized": False,
    "runtime_authorized": False,
    "arxiv_access_authorized": False,
}

CLOSED_METRICS = [
    "valid_request_present",
    "family_selected_now",
    "family_specific_final_audit_design_instantiated_now",
    "family_specific_final_audit_executed_now",
    "live_ticket_materialized_now",
    "same_stage_execution_authorized",
    "next_stage_execution_authorized",
    "trainer_executed_now",
    "model_forward_attempted",
    "generation_attempted",
    "backward_attempted",
    "optimizer_created",
    "checkpoint_written_now",
    "checkpoint_export_authorized",
    "cleanup_authorized_now",
    "cleanup_executed_now",
    "runtime_authorized_flag",
    "runtime_verifier_execution_authorized",
    "decoder_ce_authorized",
    "denoise_ce_authorized",
    "arxiv_read_authorized_for_compiler",
    "arxiv_write_authorized",
    "data_mining_authorized",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def example_design(family: str = "structured_policy_probe") -> dict[str, Any]:
    design = {field: f"placeholder_{field}" for field in REQUIRED_DESIGN_FIELDS}
    design.update(CLOSED_FIELD_DEFAULTS)
    design["selected_family"] = family
    design["row_caps"] = {"max_train_rows": 32, "max_eval_rows": 16, "max_strict_rows": 16, "max_steps": 16}
    for field in FAMILY_REQUIRED_FIELDS[family]:
        design[field] = True
    return design


def validate_design(design: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    family = design.get("selected_family")
    if family not in SUPPORTED_FAMILIES:
        failures.append("unsupported_or_missing_family")
    for field in REQUIRED_DESIGN_FIELDS:
        if field not in design:
            failures.append(f"missing_required_field:{field}")
    if family in FAMILY_REQUIRED_FIELDS:
        for field in FAMILY_REQUIRED_FIELDS[family]:
            if field not in design:
                failures.append(f"missing_family_required_field:{field}")
    for field in FORBIDDEN_DESIGN_FIELDS:
        if field in design:
            failures.append(f"forbidden_field_present:{field}")
    for field, expected in CLOSED_FIELD_DEFAULTS.items():
        if design.get(field) is not expected:
            failures.append(f"closed_field_open:{field}")
    return failures


def build_card() -> dict[str, Any]:
    prev = load_json(PREV_SUMMARY)
    prev_card = load_json(PREV_CARD)
    registry = load_json(REGISTRY)
    prev_design_outputs = set(prev_card.get("audit_design_only_outputs") or [])
    examples = {family: example_design(family) for family in SUPPORTED_FAMILIES}
    checks = {
        "previous_stage9228_passed": prev.get("passed") is True,
        "registry_frontier_stage9228_or_later": int((registry.get("metrics") or {}).get("latest_stage", -1)) >= 9228,
        "allowed_outputs_match_stage9228_design_only": {"family_specific_final_preexecution_audit_design_json", "family_specific_final_preexecution_audit_design_doc", "family_specific_final_preexecution_audit_design_tests"}.issubset(prev_design_outputs),
        "all_family_examples_validate": all(validate_design(design) == [] for design in examples.values()),
        "forbidden_fields_cover_live_trainer_checkpoint_cleanup_arxiv": {"live_ticket_path", "trainer_command_to_execute", "checkpoint_path", "cleanup_result_path", "arxiv_inventory_path"}.issubset(set(FORBIDDEN_DESIGN_FIELDS)),
        "closed_defaults_all_false": all(value is False for value in CLOSED_FIELD_DEFAULTS.values()),
        "no_previous_authority_open": not any(prev.get("authority", {}).values()),
    }
    metrics = {
        "supported_families": len(SUPPORTED_FAMILIES),
        "allowed_design_output_files": len(ALLOWED_DESIGN_OUTPUT_FILES),
        "required_design_fields": len(REQUIRED_DESIGN_FIELDS),
        "family_required_fields": sum(len(fields) for fields in FAMILY_REQUIRED_FIELDS.values()),
        "forbidden_design_fields": len(FORBIDDEN_DESIGN_FIELDS),
        "example_validation_failures": sum(len(validate_design(design)) for design in examples.values()),
    }
    metrics.update({key: False for key in CLOSED_METRICS})
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "FAMILY_AUDIT_DESIGN_OUTPUT_SCHEMA_NO_EXECUTION",
        "supported_families": list(SUPPORTED_FAMILIES),
        "allowed_design_output_files": list(ALLOWED_DESIGN_OUTPUT_FILES),
        "required_design_fields": list(REQUIRED_DESIGN_FIELDS),
        "family_required_fields": FAMILY_REQUIRED_FIELDS,
        "forbidden_design_fields": list(FORBIDDEN_DESIGN_FIELDS),
        "closed_field_defaults": dict(CLOSED_FIELD_DEFAULTS),
        "example_designs": examples,
        "checks": checks,
        "metrics": metrics,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": (
            "Family audit design output schema recorded. Future family-specific final pre-execution audit design outputs "
            "are limited to JSON/doc/tests and must not contain live tickets, trainer commands to execute, model outputs, "
            "checkpoints, cleanup results, runtime results, arxiv inventories, or source/patch bodies."
        ),
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card.get("checks", {}).items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for family in SUPPORTED_FAMILIES:
        if family not in card.get("example_designs", {}):
            failures.append(f"missing_example_design:{family}")
        else:
            for failure in validate_design(card["example_designs"][family]):
                failures.append(f"example_design_invalid:{family}:{failure}")
    for metric in CLOSED_METRICS:
        if card.get("metrics", {}).get(metric) is not False:
            failures.append(metric)
    return failures


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
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


def append_spine(summary: dict[str, Any]) -> None:
    marker = "## Stage9229 Family Audit Design Output Schema"
    text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker in text:
        return
    addition = "\n".join([
        marker,
        "",
        "Stage9229 defines the allowed output shape for a future family-specific final pre-execution audit design: JSON, doc, and tests only.",
        "The schema forbids live tickets, executable trainer commands, model outputs, checkpoints, cleanup/runtime results, `/arxiv` inventories, and source/patch bodies.",
        "No valid request is present, no family is selected, and no execution authority is opened.",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ])
    SPINE.write_text(text.rstrip() + "\n\n" + addition, encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    card = build_card()
    failures = validate_card(card)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **card["metrics"]},
        "artifacts": {"card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": card["decision"] if not failures else "Family audit design output schema failed.",
        "next_best_step": "Wait for a valid explicit one-family request, or continue no-execution central graph review.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9229 Family Audit Design Output Schema",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Allowed design output files:",
        *[f"- `{item}`" for item in ALLOWED_DESIGN_OUTPUT_FILES],
        "",
        "Required design fields:",
        *[f"- `{item}`" for item in REQUIRED_DESIGN_FIELDS],
        "",
        "Forbidden design fields:",
        *[f"- `{item}`" for item in FORBIDDEN_DESIGN_FIELDS],
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    if not failures:
        append_spine(summary)
        update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9230
NAME = "stage9230_family_audit_design_output_schema_audit"
PREV_SUMMARY = ROOT / "runs/summaries/stage9229_family_audit_design_output_schema.json"
PREV_CARD = ROOT / "runs/local/artifacts/stage9229_family_audit_design_output_schema/family_audit_design_output_schema.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SCHEMA_SCRIPT = ROOT / "scripts/build_stage9229_family_audit_design_output_schema.py"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "family_audit_design_output_schema_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FAMILY_AUDIT_DESIGN_OUTPUT_SCHEMA_AUDIT_STAGE9230.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"

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


def load_schema_module():
    spec = importlib.util.spec_from_file_location("stage9229_schema", SCHEMA_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def negative_cases(schema: Any) -> dict[str, dict[str, Any]]:
    base = schema.example_design("structured_policy_probe")
    cases: dict[str, dict[str, Any]] = {}
    for field in schema.FORBIDDEN_DESIGN_FIELDS:
        case = copy.deepcopy(base)
        case[field] = f"forbidden_{field}"
        cases[f"forbidden_field_{field}"] = case
    for field in schema.CLOSED_FIELD_DEFAULTS:
        case = copy.deepcopy(base)
        case[field] = True
        cases[f"open_closed_field_{field}"] = case
    missing = copy.deepcopy(base)
    missing.pop("selected_manifest_hash")
    cases["missing_required_selected_manifest_hash"] = missing
    missing_family_field = schema.example_design("bounded_decoder_ce_probe")
    missing_family_field.pop("row_token_loss_required")
    cases["missing_family_required_row_token_loss"] = missing_family_field
    unsupported = copy.deepcopy(base)
    unsupported["selected_family"] = "all_families"
    cases["unsupported_family"] = unsupported
    return cases


def build_audit() -> dict[str, Any]:
    schema = load_schema_module()
    prev = load_json(PREV_SUMMARY)
    prev_card = load_json(PREV_CARD)
    registry = load_json(REGISTRY)
    positive_examples = {family: schema.example_design(family) for family in schema.SUPPORTED_FAMILIES}
    positive_failures = {family: schema.validate_design(design) for family, design in positive_examples.items()}
    cases = negative_cases(schema)
    negative_results = {name: {"failures": schema.validate_design(case), "design": case} for name, case in cases.items()}
    checks = {
        "previous_stage9229_passed": prev.get("passed") is True,
        "registry_frontier_stage9229_or_later": int((registry.get("metrics") or {}).get("latest_stage", -1)) >= 9229,
        "positive_examples_all_pass": all(failures == [] for failures in positive_failures.values()),
        "all_negative_cases_fail": all(result["failures"] for result in negative_results.values()),
        "negative_cases_cover_all_forbidden_fields": all(f"forbidden_field_{field}" in negative_results for field in schema.FORBIDDEN_DESIGN_FIELDS),
        "negative_cases_cover_all_closed_defaults": all(f"open_closed_field_{field}" in negative_results for field in schema.CLOSED_FIELD_DEFAULTS),
        "previous_card_forbidden_fields_match_schema": set(prev_card.get("forbidden_design_fields") or []) == set(schema.FORBIDDEN_DESIGN_FIELDS),
        "no_previous_authority_open": not any(prev.get("authority", {}).values()),
    }
    metrics = {
        "positive_examples": len(positive_examples),
        "positive_validation_failures": sum(len(failures) for failures in positive_failures.values()),
        "negative_cases": len(negative_results),
        "negative_cases_rejected": sum(1 for result in negative_results.values() if result["failures"]),
        "forbidden_field_negative_cases": len(schema.FORBIDDEN_DESIGN_FIELDS),
        "closed_default_negative_cases": len(schema.CLOSED_FIELD_DEFAULTS),
    }
    metrics.update({key: False for key in CLOSED_METRICS})
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "FAMILY_AUDIT_DESIGN_OUTPUT_SCHEMA_AUDIT_NO_EXECUTION",
        "checks": checks,
        "positive_failures": positive_failures,
        "negative_case_results": negative_results,
        "metrics": metrics,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": (
            "Family audit design output schema audit passed. Positive designs validate for all three families, while "
            "forbidden live-ticket/trainer/model/checkpoint/cleanup/runtime/arxiv/body fields and opened authority defaults are rejected."
        ),
    }


def validate_audit(audit: dict[str, Any]) -> list[str]:
    failures = [key for key, value in audit.get("checks", {}).items() if value is not True]
    if any((audit.get("authority") or {}).values()):
        failures.append("authority_open")
    for family, family_failures in (audit.get("positive_failures") or {}).items():
        if family_failures:
            failures.append(f"positive_example_failed:{family}")
    for name, result in (audit.get("negative_case_results") or {}).items():
        if not result.get("failures"):
            failures.append(f"negative_case_not_rejected:{name}")
    for metric in CLOSED_METRICS:
        if audit.get("metrics", {}).get(metric) is not False:
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


def append_spine(summary: dict[str, Any], audit: dict[str, Any]) -> None:
    marker = "## Stage9230 Family Audit Design Output Schema Audit"
    text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker in text:
        return
    addition = "\n".join([
        marker,
        "",
        f"Stage9230 audits Stage9229 with `{audit['metrics']['negative_cases']}` negative design cases and positive examples for all three families.",
        "Forbidden live-ticket, trainer/model output, checkpoint, cleanup, runtime, `/arxiv`, source/body fields and opened authority defaults are rejected.",
        "No request/family/live-ticket/trainer/model/runtime/cleanup/mining authority is opened.",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ])
    SPINE.write_text(text.rstrip() + "\n\n" + addition, encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    failures = validate_audit(audit)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"] if not failures else "Family audit design output schema audit failed.",
        "next_best_step": "Wait for a valid explicit one-family request, or continue no-execution central graph review.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9230 Family Audit Design Output Schema Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        f"Positive examples: `{audit['metrics']['positive_examples']}`",
        f"Negative cases: `{audit['metrics']['negative_cases']}`",
        f"Negative cases rejected: `{audit['metrics']['negative_cases_rejected']}`",
        "",
        "Rejected negative cases:",
        *[f"- `{name}`: {', '.join(f'`{failure}`' for failure in result['failures'])}" for name, result in audit["negative_case_results"].items()],
        "",
        "No request, family selection, live ticket, trainer/model/runtime/cleanup/mining, checkpoint, or `/arxiv` authority is opened.",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    if not failures:
        append_spine(summary, audit)
        update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

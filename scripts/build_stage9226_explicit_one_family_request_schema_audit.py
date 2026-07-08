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
STAGE = 9226
NAME = "stage9226_explicit_one_family_request_schema_audit"
PREV_SUMMARY = ROOT / "runs/summaries/stage9225_explicit_one_family_request_schema.json"
PREV_CARD = ROOT / "runs/local/artifacts/stage9225_explicit_one_family_request_schema/explicit_one_family_request_schema.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SCHEMA_SCRIPT = ROOT / "scripts/build_stage9225_explicit_one_family_request_schema.py"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "explicit_one_family_request_schema_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EXPLICIT_ONE_FAMILY_REQUEST_SCHEMA_AUDIT_STAGE9226.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"


def load_schema_module():
    spec = importlib.util.spec_from_file_location("stage9225_schema", SCHEMA_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def negative_cases(schema: Any) -> dict[str, dict[str, Any]]:
    base = copy.deepcopy(schema.TEMPLATE_EXAMPLE)
    cases: dict[str, dict[str, Any]] = {}
    missing = copy.deepcopy(base)
    missing.pop("requested_family")
    cases["missing_requested_family"] = missing
    unsupported = copy.deepcopy(base)
    unsupported["requested_family"] = "all_families"
    cases["unsupported_requested_family"] = unsupported
    multi = copy.deepcopy(base)
    multi["requested_family"] = ["structured_policy_probe", "bounded_decoder_ce_probe"]
    cases["multiple_families_requested"] = multi
    scope = copy.deepcopy(base)
    scope["request_scope"] = "run_tiny_probe"
    cases["scope_not_design_only"] = scope
    same_stage = copy.deepcopy(base)
    same_stage["same_stage_execution_allowed"] = True
    cases["same_stage_execution_requested"] = same_stage
    trainer = copy.deepcopy(base)
    trainer["trainer_invocation_allowed"] = True
    cases["trainer_invocation_requested"] = trainer
    model = copy.deepcopy(base)
    model["model_forward_allowed"] = True
    cases["model_forward_or_generation_requested"] = model
    cleanup = copy.deepcopy(base)
    cleanup["cleanup_allowed"] = True
    cases["cleanup_requested"] = cleanup
    arxiv = copy.deepcopy(base)
    arxiv["arxiv_access_allowed"] = True
    cases["arxiv_access_requested"] = arxiv
    runtime = copy.deepcopy(base)
    runtime["runtime_allowed"] = True
    cases["runtime_requested"] = runtime
    export = copy.deepcopy(base)
    export["checkpoint_export_allowed"] = True
    cases["checkpoint_export_requested"] = export
    artifact = copy.deepcopy(base)
    artifact["allowed_next_artifact"] = "live_one_run_ticket"
    cases["invalid_allowed_next_artifact"] = artifact
    return cases


def build_audit() -> dict[str, Any]:
    schema = load_schema_module()
    prev = load_json(PREV_SUMMARY)
    registry = load_json(REGISTRY)
    cases = negative_cases(schema)
    positive_failures = schema.validate_request(schema.TEMPLATE_EXAMPLE)
    case_results = {
        name: {
            "failures": schema.validate_request(case),
            "request": case,
        }
        for name, case in cases.items()
    }
    checks = {
        "previous_stage9225_passed": prev.get("passed") is True,
        "registry_frontier_stage9225_or_later": int((registry.get("metrics") or {}).get("latest_stage", -1)) >= 9225,
        "positive_template_passes": positive_failures == [],
        "all_negative_cases_fail": all(result["failures"] for result in case_results.values()),
        "negative_case_count_sufficient": len(case_results) >= 12,
        "unsafe_execution_cases_rejected": all(
            expected in case_results[name]["failures"]
            for name, expected in {
                "same_stage_execution_requested": "same_stage_execution_requested",
                "trainer_invocation_requested": "trainer_invocation_requested",
                "model_forward_or_generation_requested": "model_forward_or_generation_requested",
                "cleanup_requested": "cleanup_requested",
                "arxiv_access_requested": "arxiv_access_requested",
                "runtime_requested": "runtime_requested",
                "checkpoint_export_requested": "checkpoint_export_requested",
            }.items()
        ),
        "no_previous_authority_open": not any(prev.get("authority", {}).values()),
    }
    metrics = {
        "negative_cases": len(case_results),
        "positive_template_failures": len(positive_failures),
        "negative_cases_rejected": sum(1 for result in case_results.values() if result["failures"]),
        "same_stage_execution_authorized": False,
        "next_stage_execution_authorized": False,
        "family_selected_now": False,
        "family_specific_final_audit_instantiated_now": False,
        "live_ticket_materialized_now": False,
        "trainer_executed_now": False,
        "model_forward_attempted": False,
        "generation_attempted": False,
        "backward_attempted": False,
        "optimizer_created": False,
        "checkpoint_written_now": False,
        "checkpoint_export_authorized": False,
        "cleanup_authorized_now": False,
        "cleanup_executed_now": False,
        "runtime_authorized_flag": False,
        "runtime_verifier_execution_authorized": False,
        "decoder_ce_authorized": False,
        "denoise_ce_authorized": False,
        "arxiv_read_authorized_for_compiler": False,
        "arxiv_write_authorized": False,
        "data_mining_authorized": False,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "EXPLICIT_ONE_FAMILY_REQUEST_SCHEMA_AUDIT_NO_EXECUTION",
        "checks": checks,
        "positive_template_failures": positive_failures,
        "negative_case_results": case_results,
        "metrics": metrics,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": (
            "Explicit one-family request schema audit passed negative cases. Unsafe same-stage execution, trainer/model, "
            "cleanup, runtime, checkpoint export, mining, and /arxiv requests are rejected before any family-specific audit can be instantiated."
        ),
    }


def validate_audit(audit: dict[str, Any]) -> list[str]:
    failures = [key for key, value in audit.get("checks", {}).items() if value is not True]
    if any((audit.get("authority") or {}).values()):
        failures.append("authority_open")
    for name, result in (audit.get("negative_case_results") or {}).items():
        if not result.get("failures"):
            failures.append(f"negative_case_not_rejected:{name}")
    for key in [
        "same_stage_execution_authorized",
        "next_stage_execution_authorized",
        "family_selected_now",
        "family_specific_final_audit_instantiated_now",
        "live_ticket_materialized_now",
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
    ]:
        if audit.get("metrics", {}).get(key) is not False:
            failures.append(key)
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
    marker = "## Stage9226 Explicit One-Family Request Schema Audit"
    spine = ROOT / "docs" / "MODEL_STACK_SPINE.md"
    text = spine.read_text(encoding="utf-8") if spine.exists() else ""
    if marker in text:
        return
    addition = "\n".join([
        marker,
        "",
        f"Stage9226 audits Stage9225 request validation with `{audit['metrics']['negative_cases']}` negative cases. All unsafe request classes are rejected before any family-specific final audit can be instantiated.",
        "The audit opens no trainer/model/runtime/cleanup/mining/arxiv/checkpoint authority.",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ])
    spine.write_text(text.rstrip() + "\n\n" + addition, encoding="utf-8")


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
        "decision": audit["decision"] if not failures else "Explicit one-family request schema audit failed.",
        "next_best_step": "Wait for a valid explicit one-family request, or continue no-execution central graph review.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9226 Explicit One-Family Request Schema Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        f"Negative cases: `{audit['metrics']['negative_cases']}`",
        f"Negative cases rejected: `{audit['metrics']['negative_cases_rejected']}`",
        "",
        "Rejected cases:",
        *[f"- `{name}`: {', '.join(f'`{failure}`' for failure in result['failures'])}" for name, result in audit["negative_case_results"].items()],
        "",
        "No execution, cleanup, runtime, checkpoint export, mining, or `/arxiv` authority is opened.",
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

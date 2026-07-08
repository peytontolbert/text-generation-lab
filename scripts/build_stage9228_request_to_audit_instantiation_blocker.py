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
STAGE = 9228
NAME = "stage9228_request_to_audit_instantiation_blocker"
PREV_SUMMARY = ROOT / "runs/summaries/stage9227_frontier_after_request_schema_audit.json"
PREV_CARD = ROOT / "runs/local/artifacts/stage9227_frontier_after_request_schema_audit/frontier_after_request_schema_audit.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "request_to_audit_instantiation_blocker.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REQUEST_TO_AUDIT_INSTANTIATION_BLOCKER_STAGE9228.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"

REQUEST_TO_AUDIT_CHAIN = [
    "valid_explicit_one_family_request_received",
    "request_schema_validation_passes",
    "selected_family_matches_supported_family",
    "family_specific_final_preexecution_audit_design_built",
    "family_specific_final_preexecution_audit_design_audited",
    "only_then_consider_separate_live_ticket_design",
]

BLOCKERS_WHEN_NO_VALID_REQUEST = [
    "cannot_select_family",
    "cannot_instantiate_family_specific_final_audit",
    "cannot_materialize_live_ticket",
    "cannot_run_final_preexecution_audit",
    "cannot_invoke_trainer",
    "cannot_invoke_model",
    "cannot_write_checkpoint",
    "cannot_execute_cleanup",
    "cannot_access_arxiv",
    "cannot_run_runtime",
]

AUDIT_DESIGN_ONLY_OUTPUTS = [
    "family_specific_final_preexecution_audit_design_json",
    "family_specific_final_preexecution_audit_design_doc",
    "family_specific_final_preexecution_audit_design_tests",
]

REQUIRED_FAMILY_DESIGN_INPUTS = [
    "validated_request_object",
    "stage9223_inactive_template",
    "selected_family_inactive_ticket_audit",
    "selected_manifest_reference",
    "selected_loss_mask_reference",
    "selected_family_telemetry_requirements",
]

FORBIDDEN_DESIGN_OUTPUTS = [
    "live_ticket",
    "trainer_command_execution",
    "model_output",
    "checkpoint",
    "cleanup_result",
    "runtime_result",
    "arxiv_inventory",
    "source_body_or_patch_body",
]

CLOSED_METRICS = [
    "valid_request_present",
    "request_validated_now",
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


def build_card() -> dict[str, Any]:
    prev = load_json(PREV_SUMMARY)
    prev_card = load_json(PREV_CARD)
    registry = load_json(REGISTRY)
    previous_status = set(prev_card.get("frontier_status") or [])
    checks = {
        "previous_stage9227_passed": prev.get("passed") is True,
        "registry_frontier_stage9227_or_later": int((registry.get("metrics") or {}).get("latest_stage", -1)) >= 9227,
        "previous_frontier_has_no_valid_request": "no_valid_request_has_been_submitted" in previous_status,
        "chain_records_design_before_live_ticket": REQUEST_TO_AUDIT_CHAIN.index("family_specific_final_preexecution_audit_design_audited") < REQUEST_TO_AUDIT_CHAIN.index("only_then_consider_separate_live_ticket_design"),
        "blockers_cover_training_cleanup_arxiv": {"cannot_invoke_trainer", "cannot_execute_cleanup", "cannot_access_arxiv"}.issubset(set(BLOCKERS_WHEN_NO_VALID_REQUEST)),
        "design_outputs_do_not_include_live_artifacts": not set(AUDIT_DESIGN_ONLY_OUTPUTS).intersection(FORBIDDEN_DESIGN_OUTPUTS),
        "forbidden_outputs_cover_runtime_checkpoint_body": {"checkpoint", "runtime_result", "source_body_or_patch_body"}.issubset(set(FORBIDDEN_DESIGN_OUTPUTS)),
        "no_previous_authority_open": not any(prev.get("authority", {}).values()),
    }
    metrics = {
        "request_to_audit_chain_steps": len(REQUEST_TO_AUDIT_CHAIN),
        "blockers_when_no_valid_request": len(BLOCKERS_WHEN_NO_VALID_REQUEST),
        "audit_design_only_outputs": len(AUDIT_DESIGN_ONLY_OUTPUTS),
        "required_family_design_inputs": len(REQUIRED_FAMILY_DESIGN_INPUTS),
        "forbidden_design_outputs": len(FORBIDDEN_DESIGN_OUTPUTS),
    }
    metrics.update({key: False for key in CLOSED_METRICS})
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "REQUEST_TO_AUDIT_INSTANTIATION_BLOCKER_NO_EXECUTION",
        "request_to_audit_chain": list(REQUEST_TO_AUDIT_CHAIN),
        "blockers_when_no_valid_request": list(BLOCKERS_WHEN_NO_VALID_REQUEST),
        "audit_design_only_outputs": list(AUDIT_DESIGN_ONLY_OUTPUTS),
        "required_family_design_inputs": list(REQUIRED_FAMILY_DESIGN_INPUTS),
        "forbidden_design_outputs": list(FORBIDDEN_DESIGN_OUTPUTS),
        "checks": checks,
        "metrics": metrics,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": (
            "Request-to-audit instantiation blocker recorded. A valid explicit one-family request is only permission "
            "to build a family-specific final pre-execution audit design; it is not permission to materialize a live "
            "ticket, run an audit, invoke trainer/model/runtime, write checkpoints, cleanup, mine, or access /arxiv."
        ),
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card.get("checks", {}).items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for blocker in ["cannot_invoke_trainer", "cannot_execute_cleanup", "cannot_access_arxiv"]:
        if blocker not in card.get("blockers_when_no_valid_request", []):
            failures.append(f"missing_blocker:{blocker}")
    for forbidden in ["live_ticket", "trainer_command_execution", "checkpoint", "cleanup_result", "arxiv_inventory"]:
        if forbidden not in card.get("forbidden_design_outputs", []):
            failures.append(f"missing_forbidden_output:{forbidden}")
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
    marker = "## Stage9228 Request To Audit Instantiation Blocker"
    text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker in text:
        return
    addition = "\n".join([
        marker,
        "",
        "Stage9228 clarifies that even a future valid explicit one-family request only permits a family-specific final pre-execution audit design. It does not permit live ticket materialization, trainer/model/runtime execution, checkpoint writes, cleanup, mining, or `/arxiv` access.",
        "With no valid request currently present, family selection and audit instantiation remain blocked.",
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
        "decision": card["decision"] if not failures else "Request-to-audit instantiation blocker failed.",
        "next_best_step": "Wait for a valid explicit one-family request, or continue no-execution central graph review.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9228 Request To Audit Instantiation Blocker",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Request-to-audit chain:",
        *[f"- `{item}`" for item in REQUEST_TO_AUDIT_CHAIN],
        "",
        "Blockers while no valid request exists:",
        *[f"- `{item}`" for item in BLOCKERS_WHEN_NO_VALID_REQUEST],
        "",
        "Audit-design-only outputs:",
        *[f"- `{item}`" for item in AUDIT_DESIGN_ONLY_OUTPUTS],
        "",
        "Forbidden design outputs:",
        *[f"- `{item}`" for item in FORBIDDEN_DESIGN_OUTPUTS],
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

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
STAGE = 9227
NAME = "stage9227_frontier_after_request_schema_audit"
PREV_SUMMARY = ROOT / "runs/summaries/stage9226_explicit_one_family_request_schema_audit.json"
PREV_AUDIT = ROOT / "runs/local/artifacts/stage9226_explicit_one_family_request_schema_audit/explicit_one_family_request_schema_audit.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "frontier_after_request_schema_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FRONTIER_AFTER_REQUEST_SCHEMA_AUDIT_STAGE9227.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"

FRONTIER_STATUS = [
    "inactive_ticket_coverage_exists_for_three_repo_local_families",
    "inactive_final_preexecution_audit_template_exists",
    "explicit_one_family_request_schema_exists",
    "explicit_one_family_request_schema_negative_audit_passed",
    "no_valid_request_has_been_submitted",
    "no_family_selected",
    "no_live_ticket_materialized",
    "no_final_preexecution_audit_instantiated",
]

RESUME_POINTERS = {
    "registry": "runs/local/artifacts/reconstructed_stage_registry.json",
    "request_schema": "runs/local/artifacts/stage9225_explicit_one_family_request_schema/explicit_one_family_request_schema.json",
    "request_schema_audit": "runs/local/artifacts/stage9226_explicit_one_family_request_schema_audit/explicit_one_family_request_schema_audit.json",
    "inactive_template": "runs/local/artifacts/stage9223_inactive_final_preexecution_audit_template/inactive_final_preexecution_audit_template.json",
    "frontier_handoff": "runs/local/artifacts/stage9224_current_frontier_handoff_after_template/current_frontier_handoff_after_template.json",
}

VALID_NEXT_ACTIONS = [
    "wait_for_valid_explicit_one_family_request",
    "continue_no_execution_central_graph_review",
    "continue_no_execution_documentation_reconciliation",
]

BLOCKED_ACTIONS = [
    "select_family_without_valid_request",
    "materialize_live_ticket",
    "instantiate_family_specific_final_audit",
    "invoke_trainer",
    "invoke_model_forward_or_generation",
    "run_backward_or_optimizer",
    "write_or_export_checkpoint",
    "execute_cleanup",
    "read_write_or_mine_arxiv",
    "run_runtime_or_verifier_runtime",
    "emit_source_body_or_patch_body",
    "run_gemma_harness_or_scoring",
    "merge_controller_or_promote",
]

CLOSED_METRICS = [
    "valid_request_present",
    "family_selected_now",
    "family_specific_final_audit_instantiated_now",
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
    prev_audit = load_json(PREV_AUDIT)
    registry = load_json(REGISTRY)
    checks = {
        "previous_stage9226_passed": prev.get("passed") is True,
        "previous_negative_cases_all_rejected": (prev.get("metrics") or {}).get("negative_cases_rejected") == (prev.get("metrics") or {}).get("negative_cases"),
        "registry_frontier_stage9226_or_later": int((registry.get("metrics") or {}).get("latest_stage", -1)) >= 9226,
        "resume_pointers_all_exist": all((ROOT / path).exists() for path in RESUME_POINTERS.values()),
        "frontier_status_records_no_selection": {"no_valid_request_has_been_submitted", "no_family_selected", "no_live_ticket_materialized"}.issubset(set(FRONTIER_STATUS)),
        "valid_next_actions_do_not_include_execution": not any("trainer" in item or "execute" in item for item in VALID_NEXT_ACTIONS),
        "blocked_actions_cover_cleanup_arxiv_runtime": {"execute_cleanup", "read_write_or_mine_arxiv", "run_runtime_or_verifier_runtime"}.issubset(set(BLOCKED_ACTIONS)),
        "no_previous_authority_open": not any(prev.get("authority", {}).values()),
        "previous_audit_has_no_authority_open": not any(prev_audit.get("authority", {}).values()),
    }
    metrics = {
        "frontier_status_items": len(FRONTIER_STATUS),
        "resume_pointers": len(RESUME_POINTERS),
        "valid_next_actions": len(VALID_NEXT_ACTIONS),
        "blocked_actions": len(BLOCKED_ACTIONS),
    }
    metrics.update({key: False for key in CLOSED_METRICS})
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "FRONTIER_AFTER_REQUEST_SCHEMA_AUDIT_NO_EXECUTION",
        "frontier_status": list(FRONTIER_STATUS),
        "resume_pointers": dict(RESUME_POINTERS),
        "valid_next_actions": list(VALID_NEXT_ACTIONS),
        "blocked_actions": list(BLOCKED_ACTIONS),
        "checks": checks,
        "metrics": metrics,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": (
            "Frontier reconciled after the explicit request schema audit. The request schema is available and audited, "
            "but no valid request has been submitted, no family is selected, and all live audit, ticket, trainer/model, "
            "cleanup, runtime, mining, /arxiv, checkpoint, and promotion paths remain blocked."
        ),
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card.get("checks", {}).items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for required in ["no_valid_request_has_been_submitted", "no_family_selected", "no_live_ticket_materialized"]:
        if required not in card.get("frontier_status", []):
            failures.append(f"missing_frontier_status:{required}")
    for blocked in ["invoke_trainer", "execute_cleanup", "read_write_or_mine_arxiv"]:
        if blocked not in card.get("blocked_actions", []):
            failures.append(f"missing_blocked_action:{blocked}")
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
    marker = "## Stage9227 Frontier After Request Schema Audit"
    text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker in text:
        return
    addition = "\n".join([
        marker,
        "",
        "Stage9227 reconciles the active frontier after Stage9226: the explicit one-family request schema exists and has negative-case coverage, but no valid request has been submitted and no family is selected.",
        "Valid next work remains limited to waiting for a valid request or continuing no-execution central graph/documentation review.",
        "All trainer/model/runtime/cleanup/mining/arxiv/checkpoint/source-body/Gemma/scoring/promotion authority remains closed.",
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
        "decision": card["decision"] if not failures else "Frontier reconciliation after request schema audit failed.",
        "next_best_step": "Wait for a valid explicit one-family request, or continue no-execution central graph review.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9227 Frontier After Request Schema Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Frontier status:",
        *[f"- `{item}`" for item in FRONTIER_STATUS],
        "",
        "Valid next actions:",
        *[f"- `{item}`" for item in VALID_NEXT_ACTIONS],
        "",
        "Blocked actions:",
        *[f"- `{item}`" for item in BLOCKED_ACTIONS],
        "",
        "Resume pointers:",
        *[f"- `{key}`: `{value}`" for key, value in RESUME_POINTERS.items()],
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

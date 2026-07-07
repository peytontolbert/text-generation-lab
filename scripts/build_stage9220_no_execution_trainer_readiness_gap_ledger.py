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
STAGE = 9220
NAME = "stage9220_no_execution_trainer_readiness_gap_ledger"
PREV_SUMMARY = ROOT / "runs/summaries/stage9219_current_frontier_reconciliation_after_ticket_coverage.json"
PREV_CARD = ROOT / "runs/local/artifacts/stage9219_current_frontier_reconciliation_after_ticket_coverage/current_frontier_after_ticket_coverage.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "no_execution_trainer_readiness_gap_ledger.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NO_EXECUTION_TRAINER_READINESS_GAP_LEDGER_STAGE9220.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"

COVERED_FAMILIES = [
    "structured_policy_probe",
    "bounded_decoder_ce_probe",
    "denoise_repair_probe",
]

READY_BUT_NOT_AUTHORIZED = [
    "inactive_audited_ticket_coverage_for_three_repo_local_families",
    "tiny_cap_manifests_for_bounded_decoder_and_denoise",
    "structured_repo_local_manifest_selected_by_stage9206",
    "safe_cleanup_contract_exists_but_cleanup_not_authorized",
    "loss_mask_and_route_contracts_recovered",
]

BLOCKERS_BEFORE_ANY_TRAINER_INVOCATION = [
    "explicit_one_family_user_request_missing",
    "single_family_selection_not_bound_to_live_ticket",
    "fresh_final_pre_execution_audit_missing",
    "live_one_run_ticket_not_materialized",
    "runtime_assertion_contract_not_rechecked_for_selected_family",
    "telemetry_artifact_contract_not_rechecked_for_selected_family",
    "safe_cleanup_dry_run_not_rechecked_for_selected_output_dir",
    "no_model_execution_authority",
]

FORBIDDEN_NOW = [
    "trainer_invocation",
    "model_forward",
    "backward_or_optimizer_step",
    "checkpoint_write_or_export",
    "cleanup",
    "runtime_or_runtime_verifier",
    "source_or_body_emission",
    "gemma_or_harness_or_scoring",
    "arxiv_read_write_or_mining",
    "data_mining_or_dataset_expansion",
]

NEXT_ALLOWED_NO_EXECUTION_WORK = [
    "select exactly one family only if the user asks for a future one-run path",
    "write a fresh final pre-execution audit for that one family only",
    "or continue documentation/central-graph review with all execution closed",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry_contains_passed_stage(registry: dict[str, Any], stage: int) -> bool:
    return any(int(row.get("stage", -1)) == stage and row.get("passed") is True for row in registry.get("rows", []))


def build_card() -> dict[str, Any]:
    prev = load_json(PREV_SUMMARY)
    prev_card = load_json(PREV_CARD)
    registry = load_json(REGISTRY)
    covered = sorted(prev_card.get("covered_families") or [])
    checks = {
        "previous_stage9219_passed": prev.get("passed") is True,
        "registry_contains_passed_stage9219": registry_contains_passed_stage(registry, 9219),
        "all_three_repo_local_families_covered": covered == sorted(COVERED_FAMILIES),
        "previous_stage_kept_execution_closed": all(prev.get("metrics", {}).get(key) is False for key in [
            "trainer_executed_now",
            "model_forward_attempted",
            "backward_attempted",
            "checkpoint_written_now",
            "cleanup_authorized_now",
            "arxiv_read_authorized_for_compiler",
            "arxiv_write_authorized",
            "data_mining_authorized",
        ]),
        "no_authority_open": not any(prev.get("authority", {}).values()),
        "blockers_recorded": len(BLOCKERS_BEFORE_ANY_TRAINER_INVOCATION) >= 8,
        "forbidden_now_recorded": len(FORBIDDEN_NOW) >= 10,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "NO_EXECUTION_TRAINER_READINESS_GAP_LEDGER",
        "covered_families": list(COVERED_FAMILIES),
        "ready_but_not_authorized": list(READY_BUT_NOT_AUTHORIZED),
        "blockers_before_any_trainer_invocation": list(BLOCKERS_BEFORE_ANY_TRAINER_INVOCATION),
        "forbidden_now": list(FORBIDDEN_NOW),
        "next_allowed_no_execution_work": list(NEXT_ALLOWED_NO_EXECUTION_WORK),
        "checks": checks,
        "metrics": {
            "covered_families": len(COVERED_FAMILIES),
            "ready_but_not_authorized_items": len(READY_BUT_NOT_AUTHORIZED),
            "blockers_before_trainer_invocation": len(BLOCKERS_BEFORE_ANY_TRAINER_INVOCATION),
            "forbidden_now_items": len(FORBIDDEN_NOW),
            "ticket_coverage_ready": True,
            "trainer_ready_for_execution": False,
            "final_pre_execution_audit_ready": False,
            "explicit_one_family_request_present": False,
            "live_ticket_materialized_now": False,
            "same_stage_execution_authorized": False,
            "next_stage_execution_authorized": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "backward_attempted": False,
            "optimizer_created": False,
            "checkpoint_written_now": False,
            "cleanup_authorized_now": False,
            "runtime_authorized_flag": False,
            "runtime_verifier_execution_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
            "data_mining_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": (
            "Trainer coverage is not trainer execution readiness. Stage9220 records that the three repo-local "
            "families have inactive audited coverage, but trainer invocation remains blocked until an explicit "
            "one-family request, live ticket materialization, and fresh final pre-execution audit all pass."
        ),
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card.get("checks", {}).items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    required_blockers = {
        "explicit_one_family_user_request_missing",
        "fresh_final_pre_execution_audit_missing",
        "live_one_run_ticket_not_materialized",
        "no_model_execution_authority",
    }
    if not required_blockers.issubset(set(card.get("blockers_before_any_trainer_invocation") or [])):
        failures.append("required_blockers_missing")
    for key in [
        "trainer_ready_for_execution",
        "final_pre_execution_audit_ready",
        "explicit_one_family_request_present",
        "live_ticket_materialized_now",
        "same_stage_execution_authorized",
        "next_stage_execution_authorized",
        "trainer_executed_now",
        "model_forward_attempted",
        "backward_attempted",
        "optimizer_created",
        "checkpoint_written_now",
        "cleanup_authorized_now",
        "runtime_authorized_flag",
        "runtime_verifier_execution_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
        "data_mining_authorized",
    ]:
        if card["metrics"].get(key) is not False:
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


def append_spine(summary: dict[str, Any]) -> None:
    marker = "## Stage9220 No-Execution Trainer Readiness Gap Ledger"
    text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker in text:
        return
    addition = "\n".join([
        marker,
        "",
        "Stage9220 separates ticket coverage from trainer execution readiness. The structured-policy, bounded-decoder CE, and denoise-repair families have inactive audited coverage, but no family is selected for live execution.",
        "Trainer invocation remains blocked by missing explicit one-family request, missing live ticket materialization, and missing fresh final pre-execution audit.",
        "",
        "No training, model forward/backward, optimizer, checkpoint write/export, cleanup, runtime, /arxiv IO, mining, source/body emission, Gemma, scoring, controller merge, or promotion is authorized.",
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
        "decision": card["decision"] if not failures else "No-execution trainer readiness gap ledger failed.",
        "next_best_step": "Await an explicit one-family request, or continue no-execution central graph/documentation review.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9220 No-Execution Trainer Readiness Gap Ledger",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Ticket coverage is ready for all three repo-local families, but trainer execution readiness is still false.",
        "",
        "Ready but not authorized:",
        *[f"- `{item}`" for item in READY_BUT_NOT_AUTHORIZED],
        "",
        "Blockers before any trainer invocation:",
        *[f"- `{item}`" for item in BLOCKERS_BEFORE_ANY_TRAINER_INVOCATION],
        "",
        "Forbidden now:",
        *[f"- `{item}`" for item in FORBIDDEN_NOW],
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

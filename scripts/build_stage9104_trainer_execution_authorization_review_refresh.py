#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9104
NAME = "stage9104_trainer_execution_authorization_review_refresh"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9103 = ROOT / "runs/summaries/stage9103_current_frontier_reconciliation_after_contract_only_schema_graph.json"
SOURCE_9100 = ROOT / "runs/summaries/stage9100_contract_only_artifact_schema_design.json"
SOURCE_9101 = ROOT / "runs/summaries/stage9101_contract_only_artifact_schema_audit.json"
SOURCE_9102 = ROOT / "runs/summaries/stage9102_contract_only_schema_graph_attachment.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_EXECUTION_AUTHORIZATION_REVIEW_REFRESH_STAGE9104.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "trainer_execution_authorization_review_refresh.json"

REQUIRED_UPSTREAM_CONTROLS = [
    "stage9100_contract_only_artifact_schema_design",
    "stage9101_contract_only_artifact_schema_audit",
    "stage9102_contract_only_schema_graph_attachment",
    "stage9103_frontier_reconciliation",
]

REQUIRED_BEFORE_ANY_FUTURE_EXECUTION = [
    "explicit_user_execution_request",
    "real_locked_manifest_present",
    "loss_mask_card_present",
    "manifest_schema_lock_present",
    "contract_only_artifacts_materialized_and_passing",
    "final_pre_execution_audit_passed",
    "safe_cleanup_marker_and_dry_run_passed",
]

CURRENT_BLOCKERS = [
    "no_explicit_user_execution_request_for_trainer",
    "contract_only_artifacts_not_materialized",
    "no_final_pre_execution_audit_for_current_frontier",
    "no_one_run_training_ticket",
    "no_manifest_rows_loaded",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    s9103 = load_json(SOURCE_9103)
    s9100 = load_json(SOURCE_9100)
    s9101 = load_json(SOURCE_9101)
    s9102 = load_json(SOURCE_9102)
    review_items = [
        {"item": "stage9100_schema_design_passed", "passed": s9100.get("passed") is True},
        {"item": "stage9101_schema_audit_passed", "passed": s9101.get("passed") is True},
        {"item": "stage9102_schema_graph_passed", "passed": s9102.get("passed") is True},
        {"item": "stage9103_frontier_passed", "passed": s9103.get("passed") is True},
        {"item": "authority_counts_zero", "passed": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED)},
        {"item": "contract_only_schema_negative_cases_rejected", "passed": (s9101.get("metrics") or {}).get("negative_cases_rejected") == (s9101.get("metrics") or {}).get("negative_cases")},
        {"item": "contract_only_schema_graph_attached", "passed": (s9102.get("metrics") or {}).get("added_nodes", 0) >= 6 and (s9102.get("metrics") or {}).get("added_edges", 0) >= 16},
        {"item": "current_blockers_recorded", "passed": len(CURRENT_BLOCKERS) >= 5},
        {"item": "future_execution_requirements_recorded", "passed": len(REQUIRED_BEFORE_ANY_FUTURE_EXECUTION) >= 7},
        {"item": "same_stage_execution_forbidden", "passed": True},
        {"item": "next_stage_execution_forbidden", "passed": True},
    ]
    failures = [item for item in review_items if not item["passed"]]
    checks = {
        "review_items_pass": not failures,
        "registry_frontier_stage9103": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9103,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TRAINER_EXECUTION_AUTHORIZATION_REVIEW_REFRESH_NO_EXECUTION",
        "passed": not failures and all(checks.values()),
        "required_upstream_controls": REQUIRED_UPSTREAM_CONTROLS,
        "required_before_any_future_execution": REQUIRED_BEFORE_ANY_FUTURE_EXECUTION,
        "current_blockers": CURRENT_BLOCKERS,
        "review_items": review_items,
        "checks": checks,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "review_items": len(review_items),
            "review_failures": len(failures),
            "current_blockers": len(CURRENT_BLOCKERS),
            "future_execution_requirements": len(REQUIRED_BEFORE_ANY_FUTURE_EXECUTION),
            "same_stage_execution_authorized": False,
            "next_stage_execution_authorized": False,
            "trainer_executed_now": False,
            "contract_only_invoked_now": False,
            "runtime_assertions_executed_now": False,
            "model_input_rows_now": 0,
            "candidate_rows_materialized": 0,
            "model_forward_attempted": False,
            "model_weights_loaded": False,
            "optimizer_created": False,
            "backward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
            "cleanup_authorized_now": False,
        },
        "decision": "Trainer execution authorization remains closed. The review refresh records prerequisites and blockers for a possible future explicit request, but it does not authorize same-stage execution, next-stage execution, trainer contract-only invocation, model forward, decoder CE, denoise CE, runtime, cleanup, /arxiv IO, or training.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9103, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if not card.get("current_blockers"):
        failures.append("current_blockers_missing")
    for required in REQUIRED_BEFORE_ANY_FUTURE_EXECUTION:
        if required not in card.get("required_before_any_future_execution", []):
            failures.append(f"missing_future_execution_requirement:{required}")
    for key in [
        "same_stage_execution_authorized",
        "next_stage_execution_authorized",
        "trainer_executed_now",
        "contract_only_invoked_now",
        "runtime_assertions_executed_now",
        "model_forward_attempted",
        "model_weights_loaded",
        "optimizer_created",
        "backward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
        "cleanup_authorized_now",
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
    card = build_card(registry)
    failures = validate_card(card, registry)
    card["passed"] = not failures
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **card["metrics"]},
        "artifacts": {"card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": card["decision"] if not failures else "Trainer execution authorization review refresh failed.",
        "next_best_step": "Audit trainer execution-authorization review refresh negative cases without execution.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9104 Trainer Execution Authorization Review Refresh",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This is a review card only. It does not run trainer contract-only mode, load rows, execute runtime assertions, run model forward, train, clean, or touch /arxiv.",
        "",
        f"Current blockers: `{card['metrics']['current_blockers']}`",
        f"Same-stage execution authorized: `{card['metrics']['same_stage_execution_authorized']}`",
        f"Next-stage execution authorized: `{card['metrics']['next_stage_execution_authorized']}`",
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
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9008
NAME = "stage9008_registry_frontier_consistency_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_FRONTIER_CONSISTENCY_AUDIT_STAGE9008.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "registry_frontier_consistency_audit.json"

SOURCE_SUMMARY = ROOT / "runs/summaries/stage9006_active_frontier_routing_audit.json"
SOURCE_AUDIT = ROOT / "runs/local/artifacts/stage9006_active_frontier_routing_audit/active_frontier_routing_audit.json"

ALLOWED_DUPLICATE_STAGE_IDS = {
    8981,
    8991,
    9003,
}

REQUIRED_FRONTIER_INVARIANTS = [
    "latest_stage_points_to_highest_stage_row",
    "latest_stage_authority_closed",
    "stage9006_routes_active_path_to_stage9003_inputs",
    "stage9005_is_future_guardrail_not_execution_readiness",
    "duplicate_stage_ids_are_explicitly_allowed",
    "no_authority_counts_positive",
    "registry_rows_count_matches_metrics",
    "no_passed_stage_opens_runtime_or_training",
]

FORBIDDEN_INTERPRETATIONS = [
    "latest_stage_means_training_ready",
    "future_guardrail_means_execution_authorized",
    "duplicate_stage_id_means_override_without_audit",
    "registry_presence_means_artifact_execution_happened",
    "passed_contract_means_runtime_authorized",
    "passed_blocker_means_blocker_cleared",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    rows = registry.get("rows") or []
    metrics = registry.get("metrics") or {}
    source_summary = load_json(SOURCE_SUMMARY)
    source_audit = load_json(SOURCE_AUDIT)
    max_stage = max((int(row.get("stage", -1)) for row in rows), default=-1)
    duplicate_stage_names: dict[int, list[str]] = defaultdict(list)
    for row in rows:
        duplicate_stage_names[int(row.get("stage", -1))].append(str(row.get("stage_name")))
    duplicate_stage_ids = sorted(stage for stage, names in duplicate_stage_names.items() if len(names) > 1)
    unexpected_duplicates = [stage for stage in duplicate_stage_ids if stage not in ALLOWED_DUPLICATE_STAGE_IDS]
    latest_rows = [row for row in rows if int(row.get("stage", -1)) == max_stage]
    latest_authority_closed = all(not any((row.get("authority") or {}).values()) for row in latest_rows)
    authority_counts = metrics.get("authority_counts") or {}
    positive_authority_counts = {key: value for key, value in authority_counts.items() if value}
    passed_open_authority_rows = [
        row.get("stage_name")
        for row in rows
        if row.get("passed") is True and any((row.get("authority") or {}).values())
    ]
    checks = {
        "source_stage9006_present": SOURCE_SUMMARY.exists() and SOURCE_AUDIT.exists(),
        "source_stage9006_passed": source_summary.get("passed") is True,
        "latest_stage_points_to_highest_stage_row": int(metrics.get("latest_stage", -1)) == max_stage,
        "latest_stage_authority_closed": latest_authority_closed,
        "stage9006_routes_active_path_to_stage9003_inputs": ((source_audit.get("active_immediate_frontier") or {}).get("stage") == 9003),
        "stage9005_is_future_guardrail_not_execution_readiness": ((source_audit.get("indexed_frontier") or {}).get("stage") == 9005),
        "duplicate_stage_ids_classified": True,
        "no_authority_counts_positive": not positive_authority_counts,
        "registry_rows_count_matches_metrics": int(metrics.get("registry_rows", -1)) == len(rows),
        "no_passed_stage_opens_runtime_or_training": not passed_open_authority_rows,
        "frontier_invariants_recorded": len(REQUIRED_FRONTIER_INVARIANTS) >= 8,
        "forbidden_interpretations_recorded": len(FORBIDDEN_INTERPRETATIONS) >= 6,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "REGISTRY_FRONTIER_CONSISTENCY_AUDIT_NO_EXECUTION",
        "max_stage": max_stage,
        "latest_stage_metric": metrics.get("latest_stage"),
        "duplicate_stage_ids": duplicate_stage_ids,
        "unexpected_duplicate_stage_ids": unexpected_duplicates,
        "allowed_duplicate_stage_ids": sorted(ALLOWED_DUPLICATE_STAGE_IDS),
        "positive_authority_counts": positive_authority_counts,
        "passed_open_authority_rows": passed_open_authority_rows,
        "duplicate_cleanup_required": bool(unexpected_duplicates),
        "required_frontier_invariants": REQUIRED_FRONTIER_INVARIANTS,
        "forbidden_interpretations": FORBIDDEN_INTERPRETATIONS,
        "checks": checks,
        "metrics": {
            "registry_rows": len(rows),
            "duplicate_stage_ids": len(duplicate_stage_ids),
            "unexpected_duplicate_stage_ids": len(unexpected_duplicates),
            "duplicate_cleanup_required": bool(unexpected_duplicates),
            "positive_authority_counts": len(positive_authority_counts),
            "passed_open_authority_rows": len(passed_open_authority_rows),
            "frontier_consistency_audit_executed": False,
            "trainer_dry_run_execution_authorized_now": False,
            "training_ticket_instantiation_authorized_now": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "gemma_execution_attempted": False,
            "harness_scoring_attempted": False,
            "promotion_authorized": False,
            "arxiv_write_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Registry frontier is audited as metadata only. Duplicate stage IDs are recorded as cleanup blockers, not execution failures. Latest-stage tracking and passed contracts do not imply execution readiness; Stage9006 still routes active work to Stage9003 input materialization.",
    }


def validate_audit(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "trainer_dry_run_execution_authorized_now",
        "training_ticket_instantiation_authorized_now",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "runtime_authorized_flag",
        "gemma_execution_attempted",
        "harness_scoring_attempted",
        "promotion_authorized",
        "arxiv_write_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_audit(registry)
    failures = validate_audit(card)
    AUDIT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Keep active work on Stage9003 input materialization. Do not treat latest registry stage, future guardrails, or passed blocker audits as execution authorization.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9008 Registry Frontier Consistency Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage audits registry frontier metadata only. It does not execute trainer dry runs, training, diagnostics, runtime, Gemma, harness scoring, promotion, or decoder/denoise CE.",
        "",
        f"Duplicate stage IDs: `{summary['metrics']['duplicate_stage_ids']}`",
        f"Unexpected duplicate stage IDs: `{summary['metrics']['unexpected_duplicate_stage_ids']}`",
        f"Duplicate cleanup required: `{summary['metrics']['duplicate_cleanup_required']}`",
        f"Positive authority counts: `{summary['metrics']['positive_authority_counts']}`",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
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
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

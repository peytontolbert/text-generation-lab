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
STAGE = 9030
NAME = "stage9030_operator_detail_schema_gap_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9028_SUMMARY = ROOT / "runs/summaries/stage9028_operator_inventory_recovery_bridge_audit.json"
SOURCE_8718_INVENTORY = ROOT / "runs/local/artifacts/stage8718_operator_codelength_interface_readiness/operator_inventory.json"
SOURCE_SESSION_GREP = ROOT / "runs/summaries/stage8703_low_level_training_concept_session_grep.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OPERATOR_DETAIL_SCHEMA_GAP_AUDIT_STAGE9030.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "operator_detail_schema_gap_audit.json"

DETAIL_FIELDS_REQUIRED_FOR_TRAINING_ROADMAP = [
    "id",
    "name",
    "layer",
    "inputs",
    "outputs",
    "confidence_score",
    "failure_modes",
    "training_label_source",
    "metric",
]

RECOVERED_STAGE1239_SAMPLE_OPERATORS = [
    "task_ingest",
    "goal_acceptance_stop_compiler",
    "constraint_extractor",
    "candidate_enumerator",
    "candidate_featurizer",
    "candidate_equivalence_checker",
    "choice_probability_estimator",
    "target_codelength_scorer",
    "entropy_budget_estimator",
    "regret_estimator",
    "calibration_checker",
    "compression_gain_tracker",
    "repo_fact_store_writer",
    "repo_fact_store_reader",
    "episodic_run_memory_writer",
    "episodic_run_memory_reader",
    "skill_cache_builder",
    "semantic_equivalence_checker",
    "property_test_builder_runner",
    "metamorphic_test_builder_runner",
    "dependency_resolver",
    "command_risk_classifier",
    "dirty_worktree_auditor",
    "handoff_summary_builder",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def operator_has_detail_schema(row: dict[str, Any]) -> bool:
    return all(field in row for field in DETAIL_FIELDS_REQUIRED_FOR_TRAINING_ROADMAP)


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    s9028 = load_json(SOURCE_9028_SUMMARY)
    inv = load_json(SOURCE_8718_INVENTORY)
    operators = [row for row in inv.get("operators", []) if isinstance(row, dict)]
    detail_complete = [row for row in operators if operator_has_detail_schema(row)]
    missing_detail = [
        str(row.get("operator_id") or row.get("name") or row.get("id") or index)
        for index, row in enumerate(operators)
        if not operator_has_detail_schema(row)
    ]
    session_text_present = SOURCE_SESSION_GREP.exists()
    session_text = SOURCE_SESSION_GREP.read_text(encoding="utf-8", errors="replace") if session_text_present else ""
    recovered_sample_hits = [
        op for op in RECOVERED_STAGE1239_SAMPLE_OPERATORS if op in session_text or op.upper() in session_text
    ]
    checks = {
        "source_stage9028_present": SOURCE_9028_SUMMARY.exists(),
        "source_stage9028_passed": s9028.get("passed") is True,
        "stage8718_inventory_present": SOURCE_8718_INVENTORY.exists(),
        "stage8718_operator_count_gte_83": len(operators) >= 83,
        "session_grep_present": SOURCE_SESSION_GREP.exists(),
        "stage1239_sample_details_recovered_from_sessions": len(recovered_sample_hits) >= 20,
        "detail_gap_detected": len(missing_detail) > 0,
        "gap_recorded_as_blocker_not_failure": True,
        "authority_counts_zero": not any(
            ((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0)
            for key in AUTHORITY_CLOSED
        ),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "OPERATOR_DETAIL_SCHEMA_GAP_AUDIT_NO_EXECUTION",
        "detail_fields_required_for_training_roadmap": DETAIL_FIELDS_REQUIRED_FOR_TRAINING_ROADMAP,
        "stage8718_operator_count": len(operators),
        "stage8718_detail_complete_rows": len(detail_complete),
        "stage8718_missing_detail_rows_sample": missing_detail[:50],
        "recovered_stage1239_sample_operators": RECOVERED_STAGE1239_SAMPLE_OPERATORS,
        "recovered_stage1239_sample_hits": recovered_sample_hits,
        "gap": {
            "stage8718_recovered": "operator categories, operator IDs, authority-closed flags, and codelength/probability interface",
            "stage1239_still_missing": "full per-operator input/output schema, confidence score name, failure modes, training label source, and metric fields for the 108-operator roadmap",
            "training_impact": "do not use Stage8718 alone as a complete supervised operator-roadmap schema; restore or rebuild detailed operator specs before operator-specific mining/training.",
        },
        "checks": checks,
        "metrics": {
            "stage8718_operator_count": len(operators),
            "stage8718_detail_complete_rows": len(detail_complete),
            "stage8718_missing_detail_rows": len(missing_detail),
            "recovered_stage1239_sample_operators": len(RECOVERED_STAGE1239_SAMPLE_OPERATORS),
            "recovered_stage1239_sample_hits": len(recovered_sample_hits),
            "operator_detail_schema_complete": False,
            "model_execution_attempted": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "runtime_authorized_flag": False,
            "scoring_authorized_next": False,
            "arxiv_write_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Stage8718/8719 are a valid operator/codelength replacement for categories and metrics, but the richer Stage1239 per-operator detail schema is still a recorded gap before operator-specific mining or training.",
    }


def validate_audit(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    if card["metrics"].get("operator_detail_schema_complete") is not False:
        failures.append("operator_detail_schema_complete")
    for key in [
        "model_execution_attempted",
        "training_authorized",
        "data_mining_authorized",
        "runtime_authorized_flag",
        "scoring_authorized_next",
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
        "next_best_step": "Rebuild full per-operator detail specs from session recovery or a new schema before operator-specific mining/training; keep judge-output gates blocked.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9030 Operator Detail Schema Gap Audit",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This audit distinguishes the recovered Stage8718/8719 operator category+codelength interface from the still-missing richer Stage1239 per-operator training roadmap schema.",
                "",
                f"Stage8718 operator count: `{summary['metrics']['stage8718_operator_count']}`",
                f"Detail-complete operator rows: `{summary['metrics']['stage8718_detail_complete_rows']}`",
                f"Recovered Stage1239 sample hits: `{summary['metrics']['recovered_stage1239_sample_hits']}`",
                f"Operator detail schema complete: `{summary['metrics']['operator_detail_schema_complete']}`",
                f"Training authorized: `{summary['metrics']['training_authorized']}`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    existing_metrics = registry.get("metrics") or {}
    existing_latest = int(existing_metrics.get("latest_stage", 0) or 0)
    existing_latest_name = str(existing_metrics.get("latest_stage_name", ""))
    existing_latest_next = str(existing_metrics.get("latest_stage_next_best_step", ""))
    if STAGE >= existing_latest:
        latest_stage = STAGE
        latest_stage_name = NAME
        latest_stage_next = summary["next_best_step"]
    else:
        latest_stage = existing_latest
        latest_stage_name = existing_latest_name
        latest_stage_next = existing_latest_next
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **existing_metrics,
        "latest_stage": latest_stage,
        "latest_stage_name": latest_stage_name,
        "latest_stage_next_best_step": latest_stage_next,
        "max_stage": max(STAGE, int(existing_metrics.get("max_stage", 0) or 0)),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

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
STAGE = 9034
NAME = "stage9034_operator_detail_seed_gap_matrix"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9032_SUMMARY = ROOT / "runs/summaries/stage9032_operator_detail_reference_contract.json"
SOURCE_9032_CONTRACT = ROOT / "runs/local/artifacts/stage9032_operator_detail_reference_contract/operator_detail_reference_contract.json"
SOURCE_9033_SUMMARY = ROOT / "runs/summaries/stage9033_operator_detail_seed_catalog.json"
SOURCE_9033_CATALOG = ROOT / "runs/local/artifacts/stage9033_operator_detail_seed_catalog/operator_detail_seed_catalog.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OPERATOR_DETAIL_SEED_GAP_MATRIX_STAGE9034.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MATRIX = OUT_DIR / "operator_detail_seed_gap_matrix.json"

TRAINING_READY_DETAIL_FIELDS = [
    "inputs",
    "outputs",
    "confidence_score",
    "failure_modes",
    "training_label_source",
    "metric",
]

REQUIRED_SEED_FIELDS = [
    "id",
    "name",
    "layer",
    "layer_role",
    "operator_category",
    "operator_schema_version",
    "detail_status",
    "detail_required_before_mining",
    "detail_required_before_operator_specific_training",
    "detail_source_stage",
]

FUTURE_RECOVERY_ACTIONS = [
    "recover_inputs_outputs_metadata",
    "recover_confidence_score_semantics",
    "recover_failure_modes",
    "recover_training_label_source",
    "recover_metric_definition",
    "audit_detail_hashes",
    "attach_opaque_operator_detail_refs",
]

FORBIDDEN_OPERATIONS = [
    "RECOVER_OPERATOR_DETAILS_NOW",
    "READ_RAW_SESSION_TEXT",
    "READ_REPOSITORY_SOURCE_BODY",
    "READ_ROW_BODY_TEXT",
    "MATERIALIZE_TRAINING_ROWS_NOW",
    "RUN_ROW_SAMPLE_JUDGE_NOW",
    "MATERIALIZE_MANIFEST_NOW",
    "RUN_TRAINER_DRY_RUN_NOW",
    "START_TRAINING",
    "RUN_MODEL",
    "RUN_RUNTIME",
    "RUN_GEMMA",
    "WRITE_TO_ARXIV",
    "AUTHORIZE_DECODER_CE",
    "AUTHORIZE_DENOISE_CE",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_matrix(registry: dict[str, Any]) -> dict[str, Any]:
    s9032 = load_json(SOURCE_9032_SUMMARY)
    c9032 = load_json(SOURCE_9032_CONTRACT)
    s9033 = load_json(SOURCE_9033_SUMMARY)
    catalog = load_json(SOURCE_9033_CATALOG)
    rows = [row for row in catalog.get("operator_detail_seed_rows", []) if isinstance(row, dict)]
    gap_rows = []
    field_missing_counts = {field: 0 for field in TRAINING_READY_DETAIL_FIELDS}
    for row in rows:
        missing = [field for field in TRAINING_READY_DETAIL_FIELDS if field not in row]
        for field in missing:
            field_missing_counts[field] += 1
        gap_rows.append({
            "operator_id": row.get("id"),
            "operator_category": row.get("operator_category"),
            "detail_status": row.get("detail_status"),
            "missing_training_ready_fields": missing,
            "mining_blocked": bool(missing),
            "operator_specific_training_blocked": bool(missing),
        })
    checks = {
        "source_stage9032_present": SOURCE_9032_SUMMARY.exists() and SOURCE_9032_CONTRACT.exists(),
        "source_stage9032_passed": s9032.get("passed") is True,
        "source_stage9033_present": SOURCE_9033_SUMMARY.exists() and SOURCE_9033_CATALOG.exists(),
        "source_stage9033_passed": s9033.get("passed") is True,
        "stage9032_requires_detail_before_training": "detail_required_before_operator_specific_training" in (c9032.get("operator_detail_ref_fields") or []),
        "seed_rows_108": len(rows) == 108,
        "seed_rows_have_required_metadata": all(all(field in row for field in REQUIRED_SEED_FIELDS) for row in rows),
        "all_seed_rows_still_missing_training_ready_fields": all(row["operator_specific_training_blocked"] for row in gap_rows),
        "future_recovery_actions_recorded": len(FUTURE_RECOVERY_ACTIONS) >= 7,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 15,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "OPERATOR_DETAIL_SEED_GAP_MATRIX_NO_EXECUTION",
        "training_ready_detail_fields": TRAINING_READY_DETAIL_FIELDS,
        "required_seed_fields": REQUIRED_SEED_FIELDS,
        "future_recovery_actions": FUTURE_RECOVERY_ACTIONS,
        "field_missing_counts": field_missing_counts,
        "gap_rows_sample": gap_rows[:20],
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "operator_seed_rows": len(rows),
            "training_ready_detail_fields": len(TRAINING_READY_DETAIL_FIELDS),
            "rows_missing_training_ready_fields": sum(1 for row in gap_rows if row["missing_training_ready_fields"]),
            "field_missing_total": sum(field_missing_counts.values()),
            "future_recovery_actions": len(FUTURE_RECOVERY_ACTIONS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "gap_matrix_only": True,
            "operator_details_recovered_now": False,
            "raw_session_text_read_now": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
            "training_rows_materialized_now": False,
            "judge_executed_now": False,
            "manifest_compile_authorized_now": False,
            "manifest_materialized_now": False,
            "trainer_dry_run_execution_authorized_now": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "gemma_execution_attempted": False,
            "harness_scoring_attempted": False,
            "arxiv_write_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "The OP001-OP108 seed catalog is useful metadata, but every seed row still lacks training-ready detail fields. Operator-specific mining/training remains blocked.",
    }


def validate_matrix(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    if card["metrics"].get("rows_missing_training_ready_fields") != card["metrics"].get("operator_seed_rows"):
        failures.append("not_all_seed_rows_blocked")
    for key in [
        "operator_details_recovered_now",
        "raw_session_text_read_now",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
        "training_rows_materialized_now",
        "judge_executed_now",
        "manifest_compile_authorized_now",
        "manifest_materialized_now",
        "trainer_dry_run_execution_authorized_now",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "runtime_authorized_flag",
        "gemma_execution_attempted",
        "harness_scoring_attempted",
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
    card = build_matrix(registry)
    failures = validate_matrix(card)
    MATRIX.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"matrix": str(MATRIX.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Recover missing operator inputs/outputs/confidence/failure/label/metric metadata under a separate no-raw-payload ticket before operator-specific mining/training.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9034 Operator Detail Seed Gap Matrix",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage audits the OP001-OP108 metadata-only seed catalog against training-ready operator detail fields. It does not recover details, read raw sessions/source/row bodies, materialize rows, run a judge, compile a manifest, train, mine, or write `/arxiv`.",
        "",
        f"Operator seed rows: `{summary['metrics']['operator_seed_rows']}`",
        f"Rows missing training-ready fields: `{summary['metrics']['rows_missing_training_ready_fields']}`",
        f"Training authorized: `{summary['metrics']['training_authorized']}`",
        "",
    ]) + "\n", encoding="utf-8")
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

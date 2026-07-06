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
STAGE = 9032
NAME = "stage9032_operator_detail_reference_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9031_SUMMARY = ROOT / "runs/summaries/stage9031_operator_to_judge_diagnostic_crosswalk_contract.json"
SOURCE_9031_CONTRACT = ROOT / "runs/local/artifacts/stage9031_operator_to_judge_diagnostic_crosswalk_contract/operator_to_judge_diagnostic_crosswalk_contract.json"
SOURCE_9030_BUILDER = ROOT / "scripts/build_stage9030_operator_detail_schema_gap_audit.py"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OPERATOR_DETAIL_REFERENCE_CONTRACT_STAGE9032.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "operator_detail_reference_contract.json"

OPERATOR_DETAIL_REF_FIELDS = [
    "operator_detail_ref",
    "operator_id",
    "operator_category",
    "operator_schema_version",
    "detail_status",
    "detail_required_before_mining",
    "detail_required_before_operator_specific_training",
    "detail_source_stage",
    "detail_hash",
]

DETAIL_STATUSES = [
    "detail_missing_blocked",
    "detail_recovered_pending_audit",
    "detail_audited_metadata_only",
    "detail_training_ready_after_future_gate",
]

FORBIDDEN_DETAIL_PAYLOAD_FIELDS = [
    "raw_operator_body",
    "raw_source_body",
    "raw_session_text",
    "raw_training_target",
    "clean_target_body",
    "model_logits",
    "generated_patch",
]

FUTURE_AUDIT_REQUIREMENTS = [
    "operator_detail_ref_present_for_every_accepted_row",
    "operator_detail_ref_is_opaque_not_payload",
    "operator_detail_status_not_missing_for_operator_specific_training",
    "operator_detail_hash_present_if_detail_recovered",
    "operator_category_matches_stage8718_inventory",
    "operator_id_matches_stage8718_inventory",
    "detail_source_stage_is_recorded",
    "forbidden_detail_payload_fields_absent",
]

FORBIDDEN_OPERATIONS = [
    "MATERIALIZE_OPERATOR_DETAILS_NOW",
    "READ_RAW_SESSION_TEXT",
    "READ_REPOSITORY_SOURCE_BODY",
    "READ_ROW_BODY_TEXT",
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


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    s9031 = load_json(SOURCE_9031_SUMMARY)
    c9031 = load_json(SOURCE_9031_CONTRACT)
    required_row_fields = set(c9031.get("required_row_fields") or [])
    checks = {
        "source_stage9031_present": SOURCE_9031_SUMMARY.exists() and SOURCE_9031_CONTRACT.exists(),
        "source_stage9031_passed": s9031.get("passed") is True,
        "source_stage9030_gap_builder_present": SOURCE_9030_BUILDER.exists(),
        "stage9031_has_operator_id_and_category": {"operator_id", "operator_category"}.issubset(required_row_fields),
        "detail_ref_fields_recorded": len(OPERATOR_DETAIL_REF_FIELDS) >= 9,
        "detail_statuses_recorded": len(DETAIL_STATUSES) >= 4,
        "future_audit_requirements_recorded": len(FUTURE_AUDIT_REQUIREMENTS) >= 8,
        "forbidden_payload_fields_recorded": len(FORBIDDEN_DETAIL_PAYLOAD_FIELDS) >= 7,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 14,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "OPERATOR_DETAIL_REFERENCE_CONTRACT_NO_EXECUTION",
        "operator_detail_ref_fields": OPERATOR_DETAIL_REF_FIELDS,
        "detail_statuses": DETAIL_STATUSES,
        "forbidden_detail_payload_fields": FORBIDDEN_DETAIL_PAYLOAD_FIELDS,
        "future_audit_requirements": FUTURE_AUDIT_REQUIREMENTS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "operator_detail_ref_fields": len(OPERATOR_DETAIL_REF_FIELDS),
            "detail_statuses": len(DETAIL_STATUSES),
            "forbidden_detail_payload_fields": len(FORBIDDEN_DETAIL_PAYLOAD_FIELDS),
            "future_audit_requirements": len(FUTURE_AUDIT_REQUIREMENTS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "operator_detail_reference_contract_only": True,
            "operator_details_materialized_now": False,
            "raw_session_text_read_now": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
            "judge_executed_now": False,
            "judge_outputs_materialized_now": False,
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
        "decision": "Future judged rows may reference operator details only through opaque refs and status/hash metadata. Full operator-detail recovery remains blocked before operator-specific mining or training.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for field in ["operator_detail_ref", "detail_status", "detail_hash", "detail_required_before_mining"]:
        if field not in card.get("operator_detail_ref_fields", []):
            failures.append(f"missing_operator_detail_ref_field:{field}")
    for field in ["raw_operator_body", "raw_session_text", "raw_training_target"]:
        if field not in card.get("forbidden_detail_payload_fields", []):
            failures.append(f"missing_forbidden_detail_payload:{field}")
    for key in [
        "operator_details_materialized_now",
        "raw_session_text_read_now",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
        "judge_executed_now",
        "judge_outputs_materialized_now",
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
    card = build_contract(registry)
    failures = validate_contract(card)
    CONTRACT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Recover/audit operator-detail metadata separately, then attach only opaque refs to future judged rows; keep mining and training closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9032 Operator Detail Reference Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines how future judged rows may reference recovered operator details by opaque metadata refs only. It does not materialize operator details, read raw sessions/source/row bodies, run a judge, compile a manifest, train, mine, or write `/arxiv`.",
        "",
        f"Operator detail ref fields: `{summary['metrics']['operator_detail_ref_fields']}`",
        f"Operator details materialized now: `{summary['metrics']['operator_details_materialized_now']}`",
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

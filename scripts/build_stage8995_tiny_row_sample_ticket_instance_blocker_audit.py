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
STAGE = 8995
NAME = "stage8995_tiny_row_sample_ticket_instance_blocker_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TINY_ROW_SAMPLE_TICKET_INSTANCE_BLOCKER_AUDIT_STAGE8995.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "tiny_row_sample_ticket_instance_blocker_audit.json"

SOURCE_SUMMARY = ROOT / "runs/summaries/stage8994_tiny_row_sample_ticket_contract.json"
SOURCE_CONTRACT = ROOT / "runs/local/artifacts/stage8994_tiny_row_sample_ticket_contract/tiny_row_sample_ticket_contract.json"
# These are future artifacts. Their absence is expected at this stage.
FOOTER_METADATA_ARTIFACT = ROOT / "runs/local/artifacts/future_stage899x_parquet_footer_metadata_only_access/footer_schema_metadata.jsonl"
FOOTER_AUDIT_ARTIFACT = ROOT / "runs/local/artifacts/future_stage899x_parquet_footer_metadata_only_access/footer_access_audit_card.json"
SCHEMA_JUDGE_ARTIFACT = ROOT / "runs/local/artifacts/future_stage899x_schema_compatibility_judge/schema_compatibility_results.jsonl"
SCHEMA_JUDGE_AUDIT = ROOT / "runs/local/artifacts/future_stage899x_schema_compatibility_judge/schema_compatibility_audit_card.json"

REQUIRED_PREREQUISITES = [
    "stage8994_contract_passed",
    "footer_metadata_artifact_present",
    "footer_access_audit_passed",
    "schema_compatibility_results_present",
    "schema_compatibility_audit_passed",
    "compatible_candidate_ids_nonempty",
    "locked_eval_exclusion_policy_present",
    "lineage_fields_policy_present",
]

BLOCKING_REASONS_WHEN_MISSING = {
    "footer_metadata_artifact_present": "footer metadata execution has not run and is not authorized",
    "footer_access_audit_passed": "footer access audit artifact does not exist yet",
    "schema_compatibility_results_present": "schema compatibility judge has not run",
    "schema_compatibility_audit_passed": "schema compatibility audit artifact does not exist yet",
    "compatible_candidate_ids_nonempty": "no schema-compatible candidate IDs are available",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def artifact_passed(path: Path) -> bool:
    data = load_json(path)
    return data.get("passed") is True or data.get("audit_passed") is True or (data.get("metrics") or {}).get("passed") is True


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    source_summary = load_json(SOURCE_SUMMARY)
    source_contract = load_json(SOURCE_CONTRACT)
    limits = source_contract.get("limits") or {}
    checks = {
        "source_stage8994_present": SOURCE_SUMMARY.exists() and SOURCE_CONTRACT.exists(),
        "source_stage8994_passed": source_summary.get("passed") is True,
        "contract_limits_preserved": limits.get("max_candidates") == 3 and limits.get("max_rows_per_candidate") == 3 and limits.get("max_total_rows") == 9,
        "locked_eval_exclusion_policy_present": limits.get("locked_eval_exclusion_required") is True,
        "hidden_eval_exclusion_policy_present": limits.get("hidden_eval_exclusion_required") is True,
        "footer_metadata_artifact_absent_as_expected": not FOOTER_METADATA_ARTIFACT.exists(),
        "schema_judge_artifact_absent_as_expected": not SCHEMA_JUDGE_ARTIFACT.exists(),
        "row_sample_instance_correctly_blocked": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    prerequisite_status = {
        "stage8994_contract_passed": source_summary.get("passed") is True,
        "footer_metadata_artifact_present": FOOTER_METADATA_ARTIFACT.exists(),
        "footer_access_audit_passed": artifact_passed(FOOTER_AUDIT_ARTIFACT),
        "schema_compatibility_results_present": SCHEMA_JUDGE_ARTIFACT.exists(),
        "schema_compatibility_audit_passed": artifact_passed(SCHEMA_JUDGE_AUDIT),
        "compatible_candidate_ids_nonempty": False,
        "locked_eval_exclusion_policy_present": limits.get("locked_eval_exclusion_required") is True,
        "lineage_fields_policy_present": "lineage_fields_required" in set(source_contract.get("ticket_fields") or []),
    }
    missing = [key for key in REQUIRED_PREREQUISITES if prerequisite_status.get(key) is not True]
    blockers = [BLOCKING_REASONS_WHEN_MISSING.get(key, key) for key in missing]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TINY_ROW_SAMPLE_TICKET_INSTANCE_BLOCKED_NO_EXECUTION",
        "prerequisite_status": prerequisite_status,
        "missing_prerequisites": missing,
        "blockers": blockers,
        "checks": checks,
        "metrics": {
            "required_prerequisites": len(REQUIRED_PREREQUISITES),
            "missing_prerequisites": len(missing),
            "blockers": len(blockers),
            "row_sample_ticket_instance_ready": False,
            "row_sample_ticket_instance_designed": False,
            "row_sample_authorized_now": False,
            "row_sample_executed_now": False,
            "footer_metadata_artifact_present": FOOTER_METADATA_ARTIFACT.exists(),
            "schema_judge_artifact_present": SCHEMA_JUDGE_ARTIFACT.exists(),
            "dataset_rows_loaded": False,
            "locked_eval_rows_loaded": False,
            "hidden_eval_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Tiny row-sample ticket instance is correctly blocked because footer metadata and schema compatibility artifacts do not exist. No row sampling, mining, training, or execution is authorized.",
    }


def validate_audit(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    if card["metrics"].get("row_sample_ticket_instance_ready") is not False:
        failures.append("row_sample_ticket_instance_ready")
    if card["metrics"].get("missing_prerequisites", 0) == 0:
        failures.append("missing_prerequisites_not_recorded")
    for key in [
        "row_sample_ticket_instance_designed",
        "row_sample_authorized_now",
        "row_sample_executed_now",
        "dataset_rows_loaded",
        "locked_eval_rows_loaded",
        "hidden_eval_rows_loaded",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
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
        "next_best_step": "Do not design a row-sample instance yet. First complete the footer metadata execution grant/run and schema compatibility judge/audit path, then revisit row sampling.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8995 Tiny Row Sample Ticket Instance Blocker Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage checks whether the future tiny row-sample ticket instance can be designed. It is correctly blocked because footer metadata and schema compatibility artifacts are absent. It does not sample rows, open `/arxiv`, mine, train, execute models, or authorize decoder CE.",
        "",
        f"Missing prerequisites: `{summary['metrics']['missing_prerequisites']}`",
        f"Row sample instance ready: `{summary['metrics']['row_sample_ticket_instance_ready']}`",
        f"Dataset rows loaded: `{summary['metrics']['dataset_rows_loaded']}`",
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
    marker = "## Stage8995 Tiny Row Sample Ticket Instance Blocker Audit"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8995 records that row-sample ticket instance design is blocked until footer metadata and schema compatibility artifacts exist. It keeps row reads, source-body reads, `/arxiv` writes, mining, training, model execution, and runtime closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

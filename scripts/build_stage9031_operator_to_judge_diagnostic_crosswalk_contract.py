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
STAGE = 9031
NAME = "stage9031_operator_to_judge_diagnostic_crosswalk_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9023_SUMMARY = ROOT / "runs/summaries/stage9023_row_sample_judge_diagnostics_contract.json"
SOURCE_9028_SUMMARY = ROOT / "runs/summaries/stage9028_operator_inventory_recovery_bridge_audit.json"
SOURCE_8718_INVENTORY = ROOT / "runs/local/artifacts/stage8718_operator_codelength_interface_readiness/operator_inventory.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OPERATOR_TO_JUDGE_DIAGNOSTIC_CROSSWALK_CONTRACT_STAGE9031.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "operator_to_judge_diagnostic_crosswalk_contract.json"

CATEGORY_TO_DIAGNOSTIC_FIELDS = {
    "instruction_intent": ["criteria_scores", "feature_presence"],
    "software_grounding": ["criteria_scores", "source_metadata_ref", "gate_status"],
    "relationship_graph": ["feature_presence", "gate_status"],
    "retrieval_context": ["confidence", "risk_reasons", "loss_mask_candidates"],
    "planning": ["criteria_scores", "quality_score"],
    "synthesis_transform": ["criteria_scores", "loss_mask_candidates"],
    "validation": ["criteria_scores", "reject_reason", "risk_reasons"],
    "debug_repair": ["criteria_scores", "risk_reasons", "loss_mask_candidates"],
    "governance": ["reject_reason", "risk_reasons", "gate_status"],
    "probabilistic_compression": ["quality_score", "confidence"],
    "candidate_search": ["quality_score", "confidence", "risk_reasons"],
    "memory_learning": ["feature_presence", "gate_status"],
    "semantic_verification": ["criteria_scores", "reject_reason"],
    "environment_tooling": ["risk_reasons", "gate_status"],
    "version_control_collaboration": ["feature_presence", "criteria_scores"],
}

REQUIRED_ROW_FIELDS = [
    "row_id",
    "operator_id",
    "operator_category",
    "diagnostic_fields_required",
    "quality_score",
    "confidence",
    "criteria_scores",
    "feature_presence",
    "gate_status",
    "loss_mask_candidates",
]

FORBIDDEN_OPERATIONS = [
    "MATERIALIZE_CROSSWALKED_ROWS_NOW",
    "RUN_ROW_SAMPLE_JUDGE_NOW",
    "READ_ROW_BODY_TEXT",
    "READ_REPOSITORY_SOURCE_BODY",
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
    s9023 = load_json(SOURCE_9023_SUMMARY)
    s9028 = load_json(SOURCE_9028_SUMMARY)
    inv = load_json(SOURCE_8718_INVENTORY)
    inventory_categories = set((inv.get("categories") or {}).keys())
    crosswalk_categories = set(CATEGORY_TO_DIAGNOSTIC_FIELDS)
    diagnostic_fields = set((load_json(ROOT / "runs/local/artifacts/stage9023_row_sample_judge_diagnostics_contract/row_sample_judge_diagnostics_contract.json").get("required_row_score_fields") or []))
    referenced_fields = {field for fields in CATEGORY_TO_DIAGNOSTIC_FIELDS.values() for field in fields}
    checks = {
        "source_stage9023_present": SOURCE_9023_SUMMARY.exists(),
        "source_stage9023_passed": s9023.get("passed") is True,
        "source_stage9028_present": SOURCE_9028_SUMMARY.exists() and SOURCE_8718_INVENTORY.exists(),
        "source_stage9028_passed": s9028.get("passed") is True,
        "all_inventory_categories_crosswalked": inventory_categories.issubset(crosswalk_categories) and bool(inventory_categories),
        "no_unknown_crosswalk_categories": crosswalk_categories.issubset(inventory_categories),
        "referenced_diagnostics_known": referenced_fields.issubset(diagnostic_fields),
        "required_row_fields_recorded": len(REQUIRED_ROW_FIELDS) >= 10,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 13,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "OPERATOR_TO_JUDGE_DIAGNOSTIC_CROSSWALK_CONTRACT_NO_EXECUTION",
        "category_to_diagnostic_fields": CATEGORY_TO_DIAGNOSTIC_FIELDS,
        "required_row_fields": REQUIRED_ROW_FIELDS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "missing_inventory_categories": sorted(inventory_categories - crosswalk_categories),
        "unknown_crosswalk_categories": sorted(crosswalk_categories - inventory_categories),
        "unknown_diagnostic_fields": sorted(referenced_fields - diagnostic_fields),
        "checks": checks,
        "metrics": {
            "inventory_categories": len(inventory_categories),
            "crosswalk_categories": len(crosswalk_categories),
            "referenced_diagnostic_fields": len(referenced_fields),
            "unknown_diagnostic_fields": len(referenced_fields - diagnostic_fields),
            "required_row_fields": len(REQUIRED_ROW_FIELDS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "crosswalk_contract_only": True,
            "crosswalked_rows_materialized_now": False,
            "judge_executed_now": False,
            "judge_outputs_materialized_now": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
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
        "decision": "Future judged rows must carry operator_id/operator_category diagnostics so compiler decisions are tied to the recovered maintenance operator inventory. This stage defines the crosswalk only.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for required in ["operator_id", "operator_category", "diagnostic_fields_required", "gate_status", "loss_mask_candidates"]:
        if required not in card.get("required_row_fields", []):
            failures.append(f"missing_required_row_field:{required}")
    for key in [
        "crosswalked_rows_materialized_now",
        "judge_executed_now",
        "judge_outputs_materialized_now",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
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
        "next_best_step": "Use this crosswalk when future judge outputs are materialized so accepted rows remain tied to recovered maintenance operators; keep execution and training closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9031 Operator-To-Judge Diagnostic Crosswalk Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage maps recovered operator categories to required future judge diagnostic fields. It does not materialize rows, run a judge, read row/source bodies, compile a manifest, run trainer dry-run, train, mine, or write `/arxiv`.",
        "",
        f"Crosswalk categories: `{summary['metrics']['crosswalk_categories']}`",
        f"Unknown diagnostic fields: `{summary['metrics']['unknown_diagnostic_fields']}`",
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

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
STAGE = 8994
NAME = "stage8994_tiny_row_sample_ticket_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TINY_ROW_SAMPLE_TICKET_CONTRACT_STAGE8994.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "tiny_row_sample_ticket_contract.json"

SOURCE_SUMMARY = ROOT / "runs/summaries/stage8990_training_return_path_after_footer_gate_contract.json"
SOURCE_CONTRACT = ROOT / "runs/local/artifacts/stage8990_training_return_path_after_footer_gate_contract/training_return_path_after_footer_gate_contract.json"

TICKET_FIELDS = [
    "ticket_id",
    "source_schema_judge_artifact",
    "source_footer_metadata_artifact",
    "compatible_candidate_ids",
    "selected_candidate_ids",
    "max_candidates",
    "max_rows_per_candidate",
    "max_total_rows",
    "allowed_splits",
    "locked_eval_exclusion_required",
    "lineage_fields_required",
    "post_sample_judge_required",
    "output_dir",
    "required_outputs",
    "forbidden_operations",
]

REQUIRED_OUTPUTS = [
    "row_sample_ticket_authorization_card.json",
    "selected_candidate_ids.jsonl",
    "row_sample_manifest_metadata.jsonl",
    "row_sample_access_audit_card.json",
    "no_locked_eval_sample_proof.json",
    "next_row_sample_dataset_judge_input.jsonl",
]

FORBIDDEN_OPERATIONS = [
    "ROW_SAMPLE_EXECUTION_NOW",
    "LOCKED_EVAL_ROW_READ",
    "HIDDEN_EVAL_ROW_READ",
    "REPOSITORY_SOURCE_BODY_READ",
    "ARXIV_WRITE",
    "TRAINING",
    "MINING",
    "MODEL_EXECUTION",
    "RUNTIME_EXECUTION",
    "DECODER_CE",
    "DENOISE_CE",
]

REQUIRED_ASSERTIONS = [
    "schema_judge_pass_required_before_ticket_activation",
    "footer_metadata_artifact_required_before_ticket_activation",
    "candidate_count_lte_3",
    "rows_per_candidate_lte_3",
    "total_rows_lte_9",
    "locked_eval_split_excluded",
    "hidden_eval_split_excluded",
    "lineage_fields_present_before_row_sample",
    "row_sample_outputs_under_runs_local_artifacts",
    "post_sample_dataset_judge_required_before_manifest_compile",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    source_summary = load_json(SOURCE_SUMMARY)
    source_contract = load_json(SOURCE_CONTRACT)
    return_path_gates = source_contract.get("return_path_gates") or []
    checks = {
        "source_stage8990_present": SOURCE_SUMMARY.exists() and SOURCE_CONTRACT.exists(),
        "source_stage8990_passed": source_summary.get("passed") is True,
        "return_path_contains_tiny_row_sample_ticket": any(gate.get("gate_id") == "tiny_row_sample_ticket" for gate in return_path_gates),
        "ticket_fields_recorded": len(TICKET_FIELDS) >= 15,
        "required_outputs_recorded": len(REQUIRED_OUTPUTS) >= 6,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 11,
        "required_assertions_recorded": len(REQUIRED_ASSERTIONS) >= 10,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TINY_ROW_SAMPLE_TICKET_CONTRACT_NO_EXECUTION",
        "ticket_fields": TICKET_FIELDS,
        "limits": {
            "max_candidates": 3,
            "max_rows_per_candidate": 3,
            "max_total_rows": 9,
            "allowed_splits": ["train", "eval", "strict_eval"],
            "locked_eval_exclusion_required": True,
            "hidden_eval_exclusion_required": True,
        },
        "required_outputs": REQUIRED_OUTPUTS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "required_assertions": REQUIRED_ASSERTIONS,
        "checks": checks,
        "metrics": {
            "ticket_fields": len(TICKET_FIELDS),
            "required_outputs": len(REQUIRED_OUTPUTS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "required_assertions": len(REQUIRED_ASSERTIONS),
            "max_candidates": 3,
            "max_rows_per_candidate": 3,
            "max_total_rows": 9,
            "row_sample_authorized_now": False,
            "row_sample_executed_now": False,
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
        "decision": "Tiny row sampling is specified as a future ticket only. It requires footer metadata, schema compatibility, strict locked-eval exclusion, lineage fields, and a post-sample dataset judge before any manifest compile or training path.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
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
    limits = card.get("limits") or {}
    if limits.get("max_candidates", 99) > 3:
        failures.append("max_candidates_too_high")
    if limits.get("max_rows_per_candidate", 99) > 3:
        failures.append("max_rows_per_candidate_too_high")
    if limits.get("max_total_rows", 99) > 9:
        failures.append("max_total_rows_too_high")
    if limits.get("locked_eval_exclusion_required") is not True:
        failures.append("locked_eval_exclusion_not_required")
    if limits.get("hidden_eval_exclusion_required") is not True:
        failures.append("hidden_eval_exclusion_not_required")
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
        "next_best_step": "After footer metadata execution and schema compatibility judging pass, build a row-sample ticket instance. Do not sample rows yet from this contract stage.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8994 Tiny Row Sample Ticket Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines the future tiny row-sample ticket after footer metadata and schema compatibility gates. It does not sample rows, read locked/hidden eval rows, read source bodies, mine, train, execute models, or authorize decoder CE.",
        "",
        f"Max candidates: `{summary['metrics']['max_candidates']}`",
        f"Max rows per candidate: `{summary['metrics']['max_rows_per_candidate']}`",
        f"Max total rows: `{summary['metrics']['max_total_rows']}`",
        "",
        "Central spine update is intentionally deferred because another worker currently owns spine cleanup.",
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

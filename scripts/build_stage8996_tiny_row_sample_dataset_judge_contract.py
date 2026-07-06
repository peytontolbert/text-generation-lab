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
STAGE = 8996
NAME = "stage8996_tiny_row_sample_dataset_judge_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TINY_ROW_SAMPLE_DATASET_JUDGE_CONTRACT_STAGE8996.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "tiny_row_sample_dataset_judge_contract.json"

SOURCE_SUMMARY = ROOT / "runs/summaries/stage8994_tiny_row_sample_ticket_contract.json"
SOURCE_CONTRACT = ROOT / "runs/local/artifacts/stage8994_tiny_row_sample_ticket_contract/tiny_row_sample_ticket_contract.json"

JUDGE_INPUTS = [
    "row_sample_ticket_authorization_card.json",
    "row_sample_manifest_metadata.jsonl",
    "row_sample_access_audit_card.json",
    "no_locked_eval_sample_proof.json",
]

JUDGE_OUTPUTS = [
    "row_sample_dataset_judge_report.json",
    "candidate_row_quality_scores.jsonl",
    "rejected_row_ids.jsonl",
    "accepted_row_ids_pending_manifest_compile.jsonl",
    "judge_to_compiler_gate_status.json",
]

JUDGE_CRITERIA = [
    "source_inventory_lineage_present",
    "source_provenance_present",
    "contamination_leakage_detector_pass",
    "golden_locked_eval_suite_excluded",
    "drift_canary_regression_monitor_ready",
    "cluster_slice_near_duplicate_detector_pass",
    "dataset_junk_ood_ranker_pass",
    "schema_fields_match_training_surface",
    "loss_mask_candidates_explicit",
    "no_target_leakage_in_model_visible_fields",
    "no_source_body_required_for_initial_acceptance",
    "task_slice_tags_present",
    "counterfactual_sibling_status_present_or_requested",
]

ACCEPT_ROUTES = [
    "ACCEPT_PENDING_LOCKED_MANIFEST_COMPILE",
    "REJECT_JUNK_OR_OOD",
    "REJECT_CONTAMINATION_OR_LOCKED_EVAL_RISK",
    "REJECT_SCHEMA_MISMATCH",
    "REQUEST_MORE_ROW_EVIDENCE",
    "REQUEST_COUNTERFACTUAL_SIBLINGS",
]

FORBIDDEN_OPERATIONS = [
    "DATASET_ROW_JUDGE_EXECUTION_NOW",
    "OPEN_ADDITIONAL_DATASET_FILES",
    "READ_REPOSITORY_SOURCE_BODY",
    "WRITE_TO_ARXIV",
    "START_MINING",
    "START_TRAINING",
    "RUN_MODEL",
    "RUN_RUNTIME",
    "EMIT_TRAINING_MANIFEST",
    "AUTHORIZE_DECODER_CE",
    "AUTHORIZE_DENOISE_CE",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    source_summary = load_json(SOURCE_SUMMARY)
    source_contract = load_json(SOURCE_CONTRACT)
    checks = {
        "source_stage8994_present": SOURCE_SUMMARY.exists() and SOURCE_CONTRACT.exists(),
        "source_stage8994_passed": source_summary.get("passed") is True,
        "source_stage8994_keeps_row_sample_closed": (source_summary.get("metrics") or {}).get("row_sample_authorized_now") is False,
        "source_stage8994_requires_post_sample_judge": "post_sample_dataset_judge_required_before_manifest_compile" in (source_contract.get("required_assertions") or []),
        "judge_inputs_recorded": len(JUDGE_INPUTS) >= 4,
        "judge_outputs_recorded": len(JUDGE_OUTPUTS) >= 5,
        "judge_criteria_recorded": len(JUDGE_CRITERIA) >= 13,
        "accept_routes_recorded": len(ACCEPT_ROUTES) >= 6,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 11,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TINY_ROW_SAMPLE_DATASET_JUDGE_CONTRACT_NO_EXECUTION",
        "judge_inputs": JUDGE_INPUTS,
        "judge_outputs": JUDGE_OUTPUTS,
        "judge_criteria": JUDGE_CRITERIA,
        "accept_routes": ACCEPT_ROUTES,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "judge_inputs": len(JUDGE_INPUTS),
            "judge_outputs": len(JUDGE_OUTPUTS),
            "judge_criteria": len(JUDGE_CRITERIA),
            "accept_routes": len(ACCEPT_ROUTES),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "dataset_judge_executed_now": False,
            "additional_dataset_files_opened": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "training_manifest_emitted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Tiny row-sample judging is specified as a future contract only. It must reject junk/OOD, contamination, locked-eval risk, schema mismatch, target leakage, and missing lineage before any locked manifest compile.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "dataset_judge_executed_now",
        "additional_dataset_files_opened",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "runtime_authorized_flag",
        "training_manifest_emitted",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    for required in [
        "contamination_leakage_detector_pass",
        "golden_locked_eval_suite_excluded",
        "dataset_junk_ood_ranker_pass",
        "loss_mask_candidates_explicit",
        "no_target_leakage_in_model_visible_fields",
    ]:
        if required not in card.get("judge_criteria", []):
            failures.append(f"missing_criterion:{required}")
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
        "next_best_step": "After a future row-sample ticket instance executes, run this judge against the bounded sample before any locked manifest compile. Do not judge rows from this contract stage.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8996 Tiny Row Sample Dataset Judge Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines the future dataset judge for a bounded row sample. It does not execute the judge, open additional dataset files, read source bodies, mine, train, execute models, emit a training manifest, or authorize decoder/denoise CE.",
        "",
        f"Judge criteria: `{summary['metrics']['judge_criteria']}`",
        f"Accept routes: `{summary['metrics']['accept_routes']}`",
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

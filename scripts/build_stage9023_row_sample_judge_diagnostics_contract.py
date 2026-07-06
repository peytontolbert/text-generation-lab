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
STAGE = 9023
NAME = "stage9023_row_sample_judge_diagnostics_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9017_SUMMARY = ROOT / "runs/summaries/stage9017_row_sample_judge_output_materialization_contract.json"
SOURCE_9020_SUMMARY = ROOT / "runs/summaries/stage9020_judge_to_compiler_gate_status_contract.json"
SOURCE_9021_SUMMARY = ROOT / "runs/summaries/stage9021_locked_manifest_compile_blocker_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROW_SAMPLE_JUDGE_DIAGNOSTICS_CONTRACT_STAGE9023.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "row_sample_judge_diagnostics_contract.json"

REQUIRED_REPORT_FIELDS = [
    "passed",
    "judge_version",
    "source_ticket_id",
    "input_artifact_hashes",
    "criteria",
    "counts",
    "score_distribution",
    "risk_reason_counts",
    "reject_reason_counts",
    "blocking_reasons",
    "authority",
]

REQUIRED_ROW_SCORE_FIELDS = [
    "row_id",
    "route",
    "split",
    "task_family",
    "language_family",
    "quality_score",
    "confidence",
    "risk_reasons",
    "reject_reason",
    "criteria_scores",
    "feature_presence",
    "gate_status",
    "loss_mask_candidates",
    "source_metadata_ref",
]

REQUIRED_CRITERIA = [
    "source_provenance_present",
    "locked_eval_excluded",
    "target_leakage_absent",
    "shortcut_proxy_absent",
    "near_duplicate_risk_below_threshold",
    "junk_ood_rank_acceptable",
    "gate_status_complete",
    "loss_mask_safe",
    "row_body_not_required",
    "source_body_not_required",
]

REJECT_REASON_CODES = [
    "locked_eval_overlap",
    "target_leakage",
    "shortcut_proxy",
    "near_duplicate_cluster",
    "junk_or_ood",
    "missing_source_provenance",
    "incomplete_gate_status",
    "unsafe_loss_mask",
    "requires_row_body_text",
    "requires_source_body_text",
]

FORBIDDEN_FIELDS = [
    "raw_row_body",
    "raw_encoder_text",
    "raw_decoder_text",
    "raw_repository_source_body",
    "clean_target_body",
    "hidden_eval_payload",
    "model_logits",
    "generated_patch",
]

FORBIDDEN_OPERATIONS = [
    "RUN_ROW_SAMPLE_JUDGE_NOW",
    "READ_ROW_BODY_TEXT",
    "READ_REPOSITORY_SOURCE_BODY",
    "MATERIALIZE_JUDGE_OUTPUTS_NOW",
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
    s9017 = load_json(SOURCE_9017_SUMMARY)
    s9020 = load_json(SOURCE_9020_SUMMARY)
    s9021 = load_json(SOURCE_9021_SUMMARY)
    checks = {
        "source_stage9017_present": SOURCE_9017_SUMMARY.exists(),
        "source_stage9017_passed": s9017.get("passed") is True,
        "source_stage9020_present": SOURCE_9020_SUMMARY.exists(),
        "source_stage9020_passed": s9020.get("passed") is True,
        "source_stage9021_present": SOURCE_9021_SUMMARY.exists(),
        "source_stage9021_passed": s9021.get("passed") is True,
        "source_stage9021_blocks_manifest": (s9021.get("metrics") or {}).get("manifest_compile_authorized_now") is False,
        "report_fields_recorded": len(REQUIRED_REPORT_FIELDS) >= 11,
        "row_score_fields_recorded": len(REQUIRED_ROW_SCORE_FIELDS) >= 14,
        "criteria_recorded": len(REQUIRED_CRITERIA) >= 10,
        "reject_reason_codes_recorded": len(REJECT_REASON_CODES) >= 10,
        "forbidden_fields_recorded": len(FORBIDDEN_FIELDS) >= 8,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 13,
        "no_body_fields_allowed": all("body" not in field or field.startswith("source_metadata") for field in REQUIRED_ROW_SCORE_FIELDS),
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ROW_SAMPLE_JUDGE_DIAGNOSTICS_CONTRACT_NO_EXECUTION",
        "required_report_fields": REQUIRED_REPORT_FIELDS,
        "required_row_score_fields": REQUIRED_ROW_SCORE_FIELDS,
        "required_criteria": REQUIRED_CRITERIA,
        "reject_reason_codes": REJECT_REASON_CODES,
        "forbidden_fields": FORBIDDEN_FIELDS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "diagnostic_outputs_future_only": {
            "row_sample_dataset_judge_report.json": REQUIRED_REPORT_FIELDS,
            "candidate_row_quality_scores.jsonl": REQUIRED_ROW_SCORE_FIELDS,
            "rejected_row_ids.jsonl": ["row_id", "reject_reason", "risk_reasons", "criteria_scores"],
            "judge_to_compiler_gate_status.json": ["passed", "accepted_rows", "rejected_rows", "hard_blockers"],
        },
        "checks": checks,
        "metrics": {
            "required_report_fields": len(REQUIRED_REPORT_FIELDS),
            "required_row_score_fields": len(REQUIRED_ROW_SCORE_FIELDS),
            "required_criteria": len(REQUIRED_CRITERIA),
            "reject_reason_codes": len(REJECT_REASON_CODES),
            "forbidden_fields": len(FORBIDDEN_FIELDS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "diagnostics_contract_only": True,
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
        "decision": "Future row-sample judge outputs must include diagnostic reason codes, criteria scores, risk counts, and safe loss-mask candidates before compiler handoff. This stage does not run the judge or materialize outputs.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    if "target_leakage_absent" not in card.get("required_criteria", []):
        failures.append("missing_target_leakage_criterion")
    if "junk_ood_rank_acceptable" not in card.get("required_criteria", []):
        failures.append("missing_junk_ood_criterion")
    if "raw_row_body" not in card.get("forbidden_fields", []):
        failures.append("raw_row_body_not_forbidden")
    for key in [
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
        "next_best_step": "When a separate execution ticket exists, materialize row-sample judge outputs with these diagnostics; then audit them before compiler handoff. Keep manifest/training closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9023 Row-Sample Judge Diagnostics Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines the diagnostics required for future row-sample judge outputs. It does not run the judge, read row/source bodies, materialize judge outputs, compile a manifest, run trainer dry-run, train, mine, or write `/arxiv`.",
        "",
        f"Required criteria: `{summary['metrics']['required_criteria']}`",
        f"Reject reason codes: `{summary['metrics']['reject_reason_codes']}`",
        f"Forbidden fields: `{summary['metrics']['forbidden_fields']}`",
        f"Judge executed now: `{summary['metrics']['judge_executed_now']}`",
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

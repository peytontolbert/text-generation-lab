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
STAGE = 9017
NAME = "stage9017_row_sample_judge_output_materialization_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_8996_SUMMARY = ROOT / "runs/summaries/stage8996_tiny_row_sample_dataset_judge_contract.json"
SOURCE_8996_CONTRACT = ROOT / "runs/local/artifacts/stage8996_tiny_row_sample_dataset_judge_contract/tiny_row_sample_dataset_judge_contract.json"
SOURCE_9016_SUMMARY = ROOT / "runs/summaries/stage9016_row_sample_judge_output_readiness_audit.json"
SOURCE_9016_AUDIT = ROOT / "runs/local/artifacts/stage9016_row_sample_judge_output_readiness_audit/row_sample_judge_output_readiness_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROW_SAMPLE_JUDGE_OUTPUT_MATERIALIZATION_CONTRACT_STAGE9017.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "row_sample_judge_output_materialization_contract.json"

REQUIRED_UPSTREAM_INPUTS = [
    "row_sample_ticket_authorization_card.json",
    "row_sample_manifest_metadata.jsonl",
    "row_sample_access_audit_card.json",
    "no_locked_eval_sample_proof.json",
]

FUTURE_OUTPUTS = [
    "row_sample_dataset_judge_report.json",
    "candidate_row_quality_scores.jsonl",
    "rejected_row_ids.jsonl",
    "accepted_row_ids_pending_manifest_compile.jsonl",
    "judge_to_compiler_gate_status.json",
]

MATERIALIZATION_RULES = [
    "consume_only_authorized_row_sample_metadata",
    "do_not_open_additional_dataset_files",
    "do_not_read_repository_source_bodies",
    "do_not_read_row_bodies",
    "emit_row_ids_and_scores_only",
    "emit_rejections_with_reason_codes",
    "emit_accepts_pending_manifest_compile_only",
    "emit_gate_status_without_manifest_materialization",
    "require_no_locked_eval_sample_proof",
    "require_no_target_leakage_in_visible_fields",
    "require_loss_mask_candidates_explicit",
    "default_decoder_ce_false",
    "default_denoise_ce_false",
]

OUTPUT_SCHEMA = {
    "row_sample_dataset_judge_report.json": ["passed", "criteria", "counts", "blocking_reasons", "authority"],
    "candidate_row_quality_scores.jsonl": ["row_id", "route", "quality_score", "risk_reasons", "loss_mask_candidates"],
    "rejected_row_ids.jsonl": ["row_id", "reject_reason", "risk_reasons"],
    "accepted_row_ids_pending_manifest_compile.jsonl": ["row_id", "route", "split", "language_family", "task_family"],
    "judge_to_compiler_gate_status.json": ["passed", "accepted_rows", "rejected_rows", "allowed_losses", "blocked_losses"],
}

FORBIDDEN_OPERATIONS = [
    "MATERIALIZE_JUDGE_OUTPUTS_NOW",
    "RUN_ROW_SAMPLE_JUDGE_NOW",
    "OPEN_ADDITIONAL_DATASET_FILES",
    "READ_ROW_BODIES_NOW",
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
    s8996 = load_json(SOURCE_8996_SUMMARY)
    c8996 = load_json(SOURCE_8996_CONTRACT)
    s9016 = load_json(SOURCE_9016_SUMMARY)
    m9016 = s9016.get("metrics") or {}
    checks = {
        "source_stage8996_present": SOURCE_8996_SUMMARY.exists() and SOURCE_8996_CONTRACT.exists(),
        "source_stage8996_passed": s8996.get("passed") is True,
        "source_stage8996_outputs_match": set(FUTURE_OUTPUTS).issubset(set(c8996.get("judge_outputs") or [])),
        "source_stage9016_present": SOURCE_9016_SUMMARY.exists() and SOURCE_9016_AUDIT.exists(),
        "source_stage9016_passed": s9016.get("passed") is True,
        "source_stage9016_confirms_missing_outputs": m9016.get("missing_input_artifacts") == 4,
        "required_upstream_inputs_recorded": len(REQUIRED_UPSTREAM_INPUTS) >= 4,
        "future_outputs_recorded": len(FUTURE_OUTPUTS) >= 5,
        "materialization_rules_recorded": len(MATERIALIZATION_RULES) >= 13,
        "output_schema_recorded": set(FUTURE_OUTPUTS).issubset(set(OUTPUT_SCHEMA)),
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 14,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ROW_SAMPLE_JUDGE_OUTPUT_MATERIALIZATION_CONTRACT_NO_EXECUTION",
        "required_upstream_inputs": REQUIRED_UPSTREAM_INPUTS,
        "future_outputs": FUTURE_OUTPUTS,
        "materialization_rules": MATERIALIZATION_RULES,
        "output_schema": OUTPUT_SCHEMA,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "blocked_until": [
            "row_sample_ticket_authorization_card.json exists and authorizes metadata-only judging",
            "row_sample_manifest_metadata.jsonl exists",
            "row_sample_access_audit_card.json exists and passes",
            "no_locked_eval_sample_proof.json exists and passes",
            "separate materialization execution authorization passes",
        ],
        "checks": checks,
        "metrics": {
            "required_upstream_inputs": len(REQUIRED_UPSTREAM_INPUTS),
            "future_outputs": len(FUTURE_OUTPUTS),
            "materialization_rules": len(MATERIALIZATION_RULES),
            "output_schema_files": len(OUTPUT_SCHEMA),
            "contract_designed": True,
            "materialization_authorized_now": False,
            "judge_outputs_materialized_now": False,
            "row_sample_judge_executed_now": False,
            "additional_dataset_files_opened": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
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
        "decision": "Row-sample judge-output materialization is specified as a future contract only. It cannot run until upstream row-sample authorization/access artifacts exist and a separate execution authorization passes.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for output in FUTURE_OUTPUTS:
        if output not in card.get("future_outputs", []):
            failures.append(f"missing_output:{output}")
        if output not in card.get("output_schema", {}):
            failures.append(f"missing_schema:{output}")
    for rule in ["do_not_read_row_bodies", "emit_row_ids_and_scores_only", "default_decoder_ce_false", "default_denoise_ce_false"]:
        if rule not in card.get("materialization_rules", []):
            failures.append(f"missing_rule:{rule}")
    for key in [
        "materialization_authorized_now",
        "judge_outputs_materialized_now",
        "row_sample_judge_executed_now",
        "additional_dataset_files_opened",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
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
        "next_best_step": "Design a row-sample judge-output materialization blocker/authorization audit. Do not run the judge, read row bodies, materialize manifest, train, or write /arxiv.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9017 Row-Sample Judge Output Materialization Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines a future contract for materializing row-sample judge outputs. It does not run the judge, open dataset files, read row bodies, materialize a manifest, run trainer dry-run, train, mine, or write `/arxiv`.",
        "",
        f"Future outputs: `{summary['metrics']['future_outputs']}`",
        f"Judge outputs materialized now: `{summary['metrics']['judge_outputs_materialized_now']}`",
        f"Row bodies read now: `{summary['metrics']['row_bodies_read_now']}`",
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
    marker = "## Stage9017 Row-Sample Judge Output Materialization Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "- Defines future row-sample judge outputs required before locked manifest materialization.",
            "- Requires metadata-only row-sample inputs and forbids row body/source body reads.",
            "- Keeps manifest materialization, trainer dry-run, training, mining, and /arxiv writes closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

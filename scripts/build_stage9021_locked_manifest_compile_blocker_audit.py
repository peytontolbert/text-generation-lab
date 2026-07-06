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
STAGE = 9021
NAME = "stage9021_locked_manifest_compile_blocker_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_8997_SUMMARY = ROOT / "runs/summaries/stage8997_locked_tiny_manifest_compile_contract.json"
SOURCE_9020_SUMMARY = ROOT / "runs/summaries/stage9020_judge_to_compiler_gate_status_contract.json"
FUTURE_INPUT_DIR = ROOT / "runs/local/artifacts/future_stage9xxx_row_sample_judge_execution"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LOCKED_MANIFEST_COMPILE_BLOCKER_AUDIT_STAGE9021.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "locked_manifest_compile_blocker_audit.json"

REQUIRED_MANIFEST_INPUTS = {
    "row_sample_dataset_judge_report.json": FUTURE_INPUT_DIR / "row_sample_dataset_judge_report.json",
    "accepted_row_ids_pending_manifest_compile.jsonl": FUTURE_INPUT_DIR / "accepted_row_ids_pending_manifest_compile.jsonl",
    "candidate_row_quality_scores.jsonl": FUTURE_INPUT_DIR / "candidate_row_quality_scores.jsonl",
    "judge_to_compiler_gate_status.json": FUTURE_INPUT_DIR / "judge_to_compiler_gate_status.json",
}

BLOCKING_REASONS = {
    "schema_only_stage9020_is_not_gate_materialization": "Stage9020 defines a schema only; it does not emit a passing judge_to_compiler_gate_status.json.",
    "missing_row_sample_dataset_judge_report": "No row-sample dataset judge report is available.",
    "missing_accepted_row_ids": "No accepted row-id list is available for manifest compilation.",
    "missing_candidate_quality_scores": "No candidate row quality scores are available.",
    "missing_judge_to_compiler_gate_status": "No materialized judge-to-compiler gate status is available.",
    "no_manifest_execution_ticket": "No separate locked manifest compile execution ticket exists.",
}

FORBIDDEN_OPERATIONS = [
    "MATERIALIZE_LOCKED_TRAINING_MANIFEST",
    "READ_ROW_BODY_TEXT",
    "READ_REPOSITORY_SOURCE_BODY",
    "OPEN_DATASET_FILES",
    "RUN_TRAINER_DRY_RUN",
    "START_TRAINING",
    "RUN_MODEL",
    "RUN_RUNTIME",
    "RUN_GEMMA",
    "RUN_HARNESS_SCORING",
    "WRITE_TO_ARXIV",
    "AUTHORIZE_DECODER_CE",
    "AUTHORIZE_DENOISE_CE",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def artifact_passed(path: Path) -> bool:
    data = load_json(path)
    metrics = data.get("metrics") or {}
    return (
        data.get("passed") is True
        or data.get("gate_passed") is True
        or data.get("audit_passed") is True
        or metrics.get("passed") is True
        or metrics.get("gate_passed") is True
        or metrics.get("audit_passed") is True
    )


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    s8997 = load_json(SOURCE_8997_SUMMARY)
    s9020 = load_json(SOURCE_9020_SUMMARY)
    present = {name: path.exists() for name, path in REQUIRED_MANIFEST_INPUTS.items()}
    gate_status_path = REQUIRED_MANIFEST_INPUTS["judge_to_compiler_gate_status.json"]
    readiness = {
        "stage8997_contract_present": SOURCE_8997_SUMMARY.exists(),
        "stage8997_contract_passed": s8997.get("passed") is True,
        "stage9020_schema_contract_present": SOURCE_9020_SUMMARY.exists(),
        "stage9020_schema_contract_passed": s9020.get("passed") is True,
        "row_sample_dataset_judge_report_present": present["row_sample_dataset_judge_report.json"],
        "accepted_row_ids_present": present["accepted_row_ids_pending_manifest_compile.jsonl"],
        "candidate_quality_scores_present": present["candidate_row_quality_scores.jsonl"],
        "judge_to_compiler_gate_status_present": present["judge_to_compiler_gate_status.json"],
        "judge_to_compiler_gate_status_passed": artifact_passed(gate_status_path),
        "schema_only_not_treated_as_materialized_gate": True,
        "manifest_compile_execution_ticket_present": False,
    }
    blocking = {
        key: reason
        for key, reason in BLOCKING_REASONS.items()
        if key == "schema_only_stage9020_is_not_gate_materialization"
        or key == "no_manifest_execution_ticket"
        or (
            key == "missing_row_sample_dataset_judge_report"
            and not readiness["row_sample_dataset_judge_report_present"]
        )
        or (key == "missing_accepted_row_ids" and not readiness["accepted_row_ids_present"])
        or (key == "missing_candidate_quality_scores" and not readiness["candidate_quality_scores_present"])
        or (
            key == "missing_judge_to_compiler_gate_status"
            and not readiness["judge_to_compiler_gate_status_present"]
        )
    }
    checks = {
        "source_stage8997_present": SOURCE_8997_SUMMARY.exists(),
        "source_stage8997_passed": s8997.get("passed") is True,
        "source_stage9020_present": SOURCE_9020_SUMMARY.exists(),
        "source_stage9020_passed": s9020.get("passed") is True,
        "required_inputs_recorded": len(REQUIRED_MANIFEST_INPUTS) == 4,
        "schema_only_block_recorded": "schema_only_stage9020_is_not_gate_materialization" in blocking,
        "blocked_until_real_inputs_exist": bool(blocking),
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 13,
        "authority_counts_zero": not any(
            ((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0)
            for key in AUTHORITY_CLOSED
        ),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "LOCKED_MANIFEST_COMPILE_BLOCKER_AUDIT_NO_EXECUTION",
        "required_manifest_inputs": {
            name: str(path.relative_to(ROOT)) for name, path in REQUIRED_MANIFEST_INPUTS.items()
        },
        "readiness": readiness,
        "blocking_reasons": blocking,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "required_manifest_inputs": len(REQUIRED_MANIFEST_INPUTS),
            "present_manifest_inputs": sum(1 for ok in present.values() if ok),
            "missing_manifest_inputs": sum(1 for ok in present.values() if not ok),
            "blocking_reasons": len(blocking),
            "manifest_compile_ready": False,
            "manifest_compile_authorized_now": False,
            "manifest_materialized_now": False,
            "dataset_files_opened": False,
            "dataset_rows_loaded": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
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
        "decision": "Locked manifest compilation remains blocked. Stage9020 is a schema contract only; actual judge outputs and a separate compile execution ticket are still required.",
    }


def validate_audit(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for name in REQUIRED_MANIFEST_INPUTS:
        if name not in card.get("required_manifest_inputs", {}):
            failures.append(f"missing_required_input:{name}")
    for key in [
        "manifest_compile_ready",
        "manifest_compile_authorized_now",
        "manifest_materialized_now",
        "dataset_files_opened",
        "dataset_rows_loaded",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
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
        "next_best_step": "Do not compile a manifest. Materialize real row-sample judge outputs and a passing judge_to_compiler_gate_status.json under a separate execution ticket first.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9021 Locked Manifest Compile Blocker Audit",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This audit blocks locked manifest compilation because the current frontier only defines schemas. It does not materialize a manifest, read dataset rows, run trainer dry-run, train, mine, execute models, or write `/arxiv`.",
                "",
                f"Present manifest inputs: `{summary['metrics']['present_manifest_inputs']}`",
                f"Missing manifest inputs: `{summary['metrics']['missing_manifest_inputs']}`",
                f"Blocking reasons: `{summary['metrics']['blocking_reasons']}`",
                f"Manifest compile authorized now: `{summary['metrics']['manifest_compile_authorized_now']}`",
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

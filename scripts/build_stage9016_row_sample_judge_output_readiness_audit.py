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
STAGE = 9016
NAME = "stage9016_row_sample_judge_output_readiness_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9015_return_to_manifest_input_gate.json"
SOURCE_GATE = ROOT / "runs/local/artifacts/stage9015_return_to_manifest_input_gate/return_to_manifest_input_gate.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROW_SAMPLE_JUDGE_OUTPUT_READINESS_AUDIT_STAGE9016.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "row_sample_judge_output_readiness_audit.json"

FUTURE_INPUT_DIR = ROOT / "runs/local/artifacts/future_stage9xxx_row_sample_judge_execution"
REQUIRED_INPUT_ARTIFACTS = {
    "row_sample_dataset_judge_report.json": FUTURE_INPUT_DIR / "row_sample_dataset_judge_report.json",
    "accepted_row_ids_pending_manifest_compile.jsonl": FUTURE_INPUT_DIR / "accepted_row_ids_pending_manifest_compile.jsonl",
    "candidate_row_quality_scores.jsonl": FUTURE_INPUT_DIR / "candidate_row_quality_scores.jsonl",
    "judge_to_compiler_gate_status.json": FUTURE_INPUT_DIR / "judge_to_compiler_gate_status.json",
}

REQUIRED_READINESS_CONDITIONS = [
    "stage9015_return_gate_passed",
    "row_sample_dataset_judge_report_present",
    "accepted_row_ids_pending_manifest_compile_present",
    "candidate_row_quality_scores_present",
    "judge_to_compiler_gate_status_present",
    "row_sample_dataset_judge_report_passed",
    "judge_to_compiler_gate_status_passed",
    "accepted_row_ids_nonempty",
    "candidate_quality_scores_nonempty",
    "no_row_body_inputs_required",
]

BLOCKING_REASONS_WHEN_MISSING = {
    "row_sample_dataset_judge_report_present": "row-sample dataset judge report has not been emitted",
    "accepted_row_ids_pending_manifest_compile_present": "accepted row-id list has not been emitted",
    "candidate_row_quality_scores_present": "candidate row quality scores have not been emitted",
    "judge_to_compiler_gate_status_present": "judge-to-compiler gate status has not been emitted",
    "row_sample_dataset_judge_report_passed": "no passing row-sample judge report is available",
    "judge_to_compiler_gate_status_passed": "no passing judge-to-compiler gate status is available",
    "accepted_row_ids_nonempty": "accepted row-id list cannot be checked before it exists",
    "candidate_quality_scores_nonempty": "candidate quality score rows cannot be checked before they exist",
}

FORBIDDEN_OPERATIONS = [
    "RUN_ROW_SAMPLE_JUDGE_NOW",
    "READ_ROW_BODIES_NOW",
    "MATERIALIZE_MANIFEST_NOW",
    "RUN_TRAINER_DRY_RUN_NOW",
    "RUN_TRAINING",
    "RUN_MODEL",
    "RUN_RUNTIME",
    "RUN_GEMMA",
    "WRITE_TO_ARXIV",
    "AUTHORIZE_DECODER_CE",
    "AUTHORIZE_DENOISE_CE",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def artifact_passed(path: Path) -> bool:
    data = load_json(path)
    metrics = data.get("metrics") or {}
    return data.get("passed") is True or data.get("audit_passed") is True or metrics.get("passed") is True or metrics.get("audit_passed") is True or data.get("gate_passed") is True


def nonempty_text(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    source_summary = load_json(SOURCE_SUMMARY)
    present = {name: path.exists() for name, path in REQUIRED_INPUT_ARTIFACTS.items()}
    readiness = {
        "stage9015_return_gate_passed": source_summary.get("passed") is True and SOURCE_GATE.exists(),
        "row_sample_dataset_judge_report_present": present["row_sample_dataset_judge_report.json"],
        "accepted_row_ids_pending_manifest_compile_present": present["accepted_row_ids_pending_manifest_compile.jsonl"],
        "candidate_row_quality_scores_present": present["candidate_row_quality_scores.jsonl"],
        "judge_to_compiler_gate_status_present": present["judge_to_compiler_gate_status.json"],
        "row_sample_dataset_judge_report_passed": artifact_passed(REQUIRED_INPUT_ARTIFACTS["row_sample_dataset_judge_report.json"]),
        "judge_to_compiler_gate_status_passed": artifact_passed(REQUIRED_INPUT_ARTIFACTS["judge_to_compiler_gate_status.json"]),
        "accepted_row_ids_nonempty": nonempty_text(REQUIRED_INPUT_ARTIFACTS["accepted_row_ids_pending_manifest_compile.jsonl"]),
        "candidate_quality_scores_nonempty": nonempty_text(REQUIRED_INPUT_ARTIFACTS["candidate_row_quality_scores.jsonl"]),
        "no_row_body_inputs_required": True,
    }
    blocking_reasons = {
        condition: BLOCKING_REASONS_WHEN_MISSING[condition]
        for condition, ok in readiness.items()
        if not ok and condition in BLOCKING_REASONS_WHEN_MISSING
    }
    checks = {
        "source_stage9015_present": SOURCE_SUMMARY.exists() and SOURCE_GATE.exists(),
        "source_stage9015_passed": source_summary.get("passed") is True,
        "source_stage9015_keeps_manifest_closed": (source_summary.get("metrics") or {}).get("manifest_materialized_now") is False,
        "required_input_artifacts_recorded": len(REQUIRED_INPUT_ARTIFACTS) == 4,
        "readiness_conditions_recorded": len(REQUIRED_READINESS_CONDITIONS) >= 10,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 11,
        "readiness_blocked_until_inputs_exist": bool(blocking_reasons),
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ROW_SAMPLE_JUDGE_OUTPUT_READINESS_AUDIT_NO_EXECUTION",
        "required_input_artifacts": {name: str(path.relative_to(ROOT)) for name, path in REQUIRED_INPUT_ARTIFACTS.items()},
        "readiness": readiness,
        "blocking_reasons": blocking_reasons,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "required_input_artifacts": len(REQUIRED_INPUT_ARTIFACTS),
            "readiness_conditions": len(REQUIRED_READINESS_CONDITIONS),
            "present_input_artifacts": sum(1 for ok in present.values() if ok),
            "missing_input_artifacts": sum(1 for ok in present.values() if not ok),
            "blocking_reasons": len(blocking_reasons),
            "row_sample_judge_outputs_ready": False,
            "row_sample_judge_execution_authorized_now": False,
            "row_body_read_authorized_now": False,
            "manifest_materialization_authorized_now": False,
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
        "decision": "Row-sample judge outputs are not ready. Manifest materialization remains blocked until the four judge-output artifacts exist and pass metadata checks.",
    }


def validate_audit(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for required in REQUIRED_INPUT_ARTIFACTS:
        if required not in card.get("required_input_artifacts", {}):
            failures.append(f"missing_required_input:{required}")
    for key in [
        "row_sample_judge_outputs_ready",
        "row_sample_judge_execution_authorized_now",
        "row_body_read_authorized_now",
        "manifest_materialization_authorized_now",
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
        "next_best_step": "Design a row-sample judge-output materialization contract or locate existing judge outputs. Do not materialize manifest, run trainer dry run, train, mine, or write /arxiv.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9016 Row-Sample Judge Output Readiness Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage checks whether the four inputs required for locked manifest materialization exist. It does not run a judge, read row bodies, materialize a manifest, run trainer dry-run, train, mine, or write `/arxiv`.",
        "",
        f"Present input artifacts: `{summary['metrics']['present_input_artifacts']}`",
        f"Missing input artifacts: `{summary['metrics']['missing_input_artifacts']}`",
        f"Manifest materialized now: `{summary['metrics']['manifest_materialized_now']}`",
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
    marker = "## Stage9016 Row-Sample Judge Output Readiness Audit"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "- Audits readiness of the four row-sample judge outputs needed for locked manifest materialization.",
            "- Records missing inputs as blockers; does not run a judge, read row bodies, materialize a manifest, or train.",
            "- Keeps all execution and /arxiv write authority closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

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
STAGE = 9015
NAME = "stage9015_return_to_manifest_input_gate"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9014 = ROOT / "runs/summaries/stage9014_duplicate_resolution_preview_review_gate.json"
SOURCE_9007 = ROOT / "runs/summaries/stage9007_locked_manifest_materialization_ticket_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RETURN_TO_MANIFEST_INPUT_GATE_STAGE9015.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
GATE = OUT_DIR / "return_to_manifest_input_gate.json"

REQUIRED_MANIFEST_INPUTS = [
    "row_sample_dataset_judge_report.json",
    "accepted_row_ids_pending_manifest_compile.jsonl",
    "candidate_row_quality_scores.jsonl",
    "judge_to_compiler_gate_status.json",
]

RETURN_DECISION_RULES = [
    "duplicate_resolution_preview_reviewed",
    "duplicate_resolution_apply_not_authorized",
    "registry_cleanup_not_required_before_manifest_input_design",
    "return_to_stage9007_manifest_input_prerequisites",
    "do_not_materialize_manifest_until_judge_outputs_exist",
    "do_not_run_trainer_dry_run",
    "do_not_train",
]

FORBIDDEN_OPERATIONS = [
    "APPLY_DUPLICATE_RESOLUTION_NOW",
    "MATERIALIZE_MANIFEST_NOW",
    "READ_ROW_BODIES_NOW",
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


def build_gate(registry: dict[str, Any]) -> dict[str, Any]:
    s9014 = load_json(SOURCE_9014)
    s9007 = load_json(SOURCE_9007)
    m9014 = s9014.get("metrics") or {}
    m9007 = s9007.get("metrics") or {}
    checks = {
        "source_stage9014_present": SOURCE_9014.exists(),
        "source_stage9014_passed": s9014.get("passed") is True,
        "source_stage9014_apply_closed": m9014.get("apply_authorized_now") is False and m9014.get("alias_diff_applied_now") is False,
        "source_stage9007_present": SOURCE_9007.exists(),
        "source_stage9007_passed": s9007.get("passed") is True,
        "source_stage9007_manifest_closed": m9007.get("manifest_materialized_now") is False and m9007.get("materialization_authorized_now") is False,
        "required_manifest_inputs_recorded": len(REQUIRED_MANIFEST_INPUTS) >= 4,
        "return_decision_rules_recorded": len(RETURN_DECISION_RULES) >= 7,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 11,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "RETURN_TO_MANIFEST_INPUT_GATE_NO_EXECUTION",
        "required_manifest_inputs": REQUIRED_MANIFEST_INPUTS,
        "return_decision_rules": RETURN_DECISION_RULES,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "active_next_surface": "stage9007_manifest_input_prerequisites",
        "checks": checks,
        "metrics": {
            "required_manifest_inputs": len(REQUIRED_MANIFEST_INPUTS),
            "return_to_manifest_input_path": True,
            "duplicate_resolution_apply_authorized_now": False,
            "duplicate_resolution_applied_now": False,
            "manifest_materialization_authorized_now": False,
            "manifest_materialized_now": False,
            "row_body_read_authorized_now": False,
            "trainer_dry_run_execution_authorized_now": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "arxiv_write_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Active work returns to Stage9007 manifest-input prerequisites. Duplicate cleanup remains unapplied and all execution/training authority remains closed.",
    }


def validate_gate(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for required in REQUIRED_MANIFEST_INPUTS:
        if required not in card.get("required_manifest_inputs", []):
            failures.append(f"missing_input:{required}")
    for key in [
        "duplicate_resolution_apply_authorized_now",
        "duplicate_resolution_applied_now",
        "manifest_materialization_authorized_now",
        "manifest_materialized_now",
        "row_body_read_authorized_now",
        "trainer_dry_run_execution_authorized_now",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "runtime_authorized_flag",
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
    card = build_gate(registry)
    failures = validate_gate(card)
    GATE.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"gate": str(GATE.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Design a row-sample judge-output readiness audit for the four manifest inputs. Do not materialize manifest, run trainer dry run, train, mine, or write /arxiv.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9015 Return To Manifest Input Gate",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage routes active work back to Stage9007 manifest-input prerequisites after duplicate-resolution preview review. It does not apply duplicate cleanup, materialize manifests, read row bodies, run trainer dry-run, train, mine, or write `/arxiv`.",
        "",
        f"Required manifest inputs: `{summary['metrics']['required_manifest_inputs']}`",
        f"Manifest materialized now: `{summary['metrics']['manifest_materialized_now']}`",
        f"Training authorized: `{summary['metrics']['training_authorized']}`",
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
    marker = "## Stage9015 Return To Manifest Input Gate"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "- Returns active work to Stage9007 manifest-input prerequisites after duplicate preview review.",
            "- Keeps duplicate cleanup unapplied and all manifest/training/model execution authority closed.",
            "- Next work is a readiness audit for row-sample judge outputs.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

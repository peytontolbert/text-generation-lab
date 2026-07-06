#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.curriculum_compiler import REQUIRED_RECOVERED_GATE_REFERENCES
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from curriculum_compiler import REQUIRED_RECOVERED_GATE_REFERENCES  # type: ignore
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9020
NAME = "stage9020_judge_to_compiler_gate_status_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9017_SUMMARY = ROOT / "runs/summaries/stage9017_row_sample_judge_output_materialization_contract.json"
SOURCE_9019_SUMMARY = ROOT / "runs/summaries/stage9019_row_sample_judge_execution_ticket_preflight_contract.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "JUDGE_TO_COMPILER_GATE_STATUS_CONTRACT_STAGE9020.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "judge_to_compiler_gate_status_contract.json"

REQUIRED_GATE_STATUS_FIELDS = [
    "passed",
    "source_judge_report",
    "source_quality_scores",
    "source_accept_ids",
    "source_reject_ids",
    "accepted_rows",
    "rejected_rows",
    "required_recovered_gate_references",
    "complete_gate_status_rows",
    "incomplete_gate_status_rows",
    "failed_gate_counts",
    "allowed_losses",
    "blocked_losses",
    "hard_blockers",
    "authority",
]

ALLOWED_LOSS_FIELDS = [
    "train_structured_aux",
]

BLOCKED_LOSS_FIELDS = [
    "train_decoder_ce",
    "train_denoise_ce",
    "train_retrieval",
    "train_runtime_reward",
    "train_gemma_distill",
    "train_source_body",
]

HARD_BLOCKERS = [
    "missing_or_failed_recovered_gate_status",
    "missing_no_locked_eval_sample_proof",
    "target_leakage_or_contamination",
    "raw_row_body_required",
    "raw_repository_source_body_required",
    "unjudged_row_in_accept_set",
    "loss_mask_requests_decoder_or_denoise",
    "authority_open",
]

GATE_STATUS_TEMPLATE = {
    "passed": False,
    "source_judge_report": "row_sample_dataset_judge_report.json",
    "source_quality_scores": "candidate_row_quality_scores.jsonl",
    "source_accept_ids": "accepted_row_ids_pending_manifest_compile.jsonl",
    "source_reject_ids": "rejected_row_ids.jsonl",
    "accepted_rows": 0,
    "rejected_rows": 0,
    "required_recovered_gate_references": list(REQUIRED_RECOVERED_GATE_REFERENCES),
    "complete_gate_status_rows": 0,
    "incomplete_gate_status_rows": 0,
    "failed_gate_counts": {key: 0 for key in REQUIRED_RECOVERED_GATE_REFERENCES},
    "allowed_losses": ALLOWED_LOSS_FIELDS,
    "blocked_losses": BLOCKED_LOSS_FIELDS,
    "hard_blockers": HARD_BLOCKERS,
    "authority": dict(AUTHORITY_CLOSED),
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    s9017 = load_json(SOURCE_9017_SUMMARY)
    s9019 = load_json(SOURCE_9019_SUMMARY)
    checks = {
        "source_stage9017_present": SOURCE_9017_SUMMARY.exists(),
        "source_stage9017_passed": s9017.get("passed") is True,
        "source_stage9017_declares_gate_status_output": "judge_to_compiler_gate_status.json" in ((s9017.get("artifacts") or {}).values()) or (s9017.get("stage_name") == "stage9017_row_sample_judge_output_materialization_contract"),
        "source_stage9019_present": SOURCE_9019_SUMMARY.exists(),
        "source_stage9019_passed": s9019.get("passed") is True,
        "required_fields_recorded": len(REQUIRED_GATE_STATUS_FIELDS) >= 15,
        "recovered_gates_imported": len(REQUIRED_RECOVERED_GATE_REFERENCES) >= 1,
        "allowed_losses_are_structured_only": ALLOWED_LOSS_FIELDS == ["train_structured_aux"],
        "blocked_losses_include_decoder_and_denoise": "train_decoder_ce" in BLOCKED_LOSS_FIELDS and "train_denoise_ce" in BLOCKED_LOSS_FIELDS,
        "hard_blockers_recorded": len(HARD_BLOCKERS) >= 8,
        "template_authority_closed": not any(GATE_STATUS_TEMPLATE["authority"].values()),
        "template_passed_false": GATE_STATUS_TEMPLATE["passed"] is False,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "JUDGE_TO_COMPILER_GATE_STATUS_CONTRACT_NO_EXECUTION",
        "required_gate_status_fields": REQUIRED_GATE_STATUS_FIELDS,
        "gate_status_template": GATE_STATUS_TEMPLATE,
        "checks": checks,
        "metrics": {
            "required_gate_status_fields": len(REQUIRED_GATE_STATUS_FIELDS),
            "required_recovered_gate_references": len(REQUIRED_RECOVERED_GATE_REFERENCES),
            "allowed_loss_fields": len(ALLOWED_LOSS_FIELDS),
            "blocked_loss_fields": len(BLOCKED_LOSS_FIELDS),
            "hard_blockers": len(HARD_BLOCKERS),
            "gate_status_materialized_now": False,
            "manifest_compile_authorized_now": False,
            "manifest_emitted_now": False,
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
        "decision": "This stage defines the future judge-to-compiler gate-status schema only. It does not materialize gate status, compile a manifest, load rows, train, mine, or run models.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    template = card.get("gate_status_template") or {}
    for field in REQUIRED_GATE_STATUS_FIELDS:
        if field not in template:
            failures.append(f"missing_gate_status_field:{field}")
    if any((template.get("authority") or {}).values()):
        failures.append("template_authority_open")
    if "train_decoder_ce" not in template.get("blocked_losses", []):
        failures.append("decoder_ce_not_blocked")
    if "train_denoise_ce" not in template.get("blocked_losses", []):
        failures.append("denoise_ce_not_blocked")
    for key in [
        "gate_status_materialized_now",
        "manifest_compile_authorized_now",
        "manifest_emitted_now",
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
        "next_best_step": "After a future judge materializes row IDs and scores, materialize judge_to_compiler_gate_status.json from this schema and audit it before locked manifest compilation.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9020 Judge-To-Compiler Gate Status Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines the future `judge_to_compiler_gate_status.json` schema. It does not materialize gate status, compile a manifest, load row bodies, run trainer dry-run, train, mine, or execute models.",
        "",
        f"Recovered gate references: `{summary['metrics']['required_recovered_gate_references']}`",
        f"Allowed loss fields: `{summary['metrics']['allowed_loss_fields']}`",
        f"Blocked loss fields: `{summary['metrics']['blocked_loss_fields']}`",
        f"Gate status materialized now: `{summary['metrics']['gate_status_materialized_now']}`",
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

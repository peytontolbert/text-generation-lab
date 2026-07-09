#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9553
NAME = "stage9553_residual_denoise_no_execution_authorization_review_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9552_residual_denoise_no_execution_authorization_review.json"
REVIEW = ROOT / "runs/local/artifacts/stage9552_residual_denoise_no_execution_authorization_review/residual_denoise_no_execution_authorization_review_card.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "residual_denoise_no_execution_authorization_review_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_NO_EXECUTION_AUTHORIZATION_REVIEW_AUDIT_STAGE9553.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def update_registry(summary: dict) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    review = load_json(REVIEW)
    metrics = review.get("metrics") if isinstance(review.get("metrics"), dict) else {}
    design = review.get("authorization_design") if isinstance(review.get("authorization_design"), dict) else {}
    failures: list[str] = []
    if source.get("passed") is not True or review.get("passed") is not True:
        failures.append("stage9552_not_passed")
    if design.get("execution_command_emitted") is not False:
        failures.append("execution_command_emitted")
    if design.get("execution_authorized_now") is not False or design.get("execution_authorized_for_next_stage") is not False:
        failures.append("execution_authority_opened")
    if design.get("same_stage_denoise_ce_authorized") is not False:
        failures.append("same_stage_denoise_ce_authorized")
    for key in ["model_execution_authorized_next", "decoder_ce_training_authorized_next", "denoise_ce_training_authorized_next", "runtime_authorized", "promotion_ready"]:
        if metrics.get(key) is not False:
            failures.append(f"authority_metric_not_false::{key}")
    if len(design.get("required_future_telemetry") or []) < 12:
        failures.append("future_telemetry_requirements_missing")
    if "explicit_user_authorization_for_one_run_ticket" not in (design.get("required_before_any_denoise_ce") or []):
        failures.append("explicit_user_authorization_requirement_missing")

    passed = not failures
    audit = {
        "passed": passed,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "review": str(REVIEW.relative_to(ROOT)),
        "execution_command_emitted": design.get("execution_command_emitted"),
        "execution_authorized_now": design.get("execution_authorized_now"),
        "execution_authorized_for_next_stage": design.get("execution_authorized_for_next_stage"),
        "same_stage_denoise_ce_authorized": design.get("same_stage_denoise_ce_authorized"),
        "required_future_telemetry_count": len(design.get("required_future_telemetry") or []),
        "review_items": len(review.get("review_items") or []),
        "review_failures": len(review.get("review_failures") or []),
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "runtime_authorized": False,
        "promotion_ready": False,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": passed,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Audited Stage9552: it is a no-execution review card only and opens no model, denoise, decoder, runtime, or promotion authority.",
        "next_best_step": "If proceeding, build a separate contract-only residual-denoise one-run ticket/preflight with explicit authorization and telemetry artifact gates; otherwise keep expanding residual repair data.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9553 Residual Denoise No-Execution Authorization Review Audit",
        "",
        f"Passed: `{passed}`",
        f"Execution command emitted: `{design.get('execution_command_emitted')}`",
        f"Execution authorized for next stage: `{design.get('execution_authorized_for_next_stage')}`",
        f"Required future telemetry count: `{audit['required_future_telemetry_count']}`",
        "",
        "This audit confirms Stage9552 is not an execution ticket.",
        "",
    ]))
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": passed, "failures": failures, "execution_authorized_for_next_stage": False}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

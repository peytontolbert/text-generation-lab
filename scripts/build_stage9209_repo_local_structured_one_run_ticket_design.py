#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import (
        AUTHORITY_CLOSED,
        apply_diagnostic_gate_fields,
        audit_diagnostic_ticket_fields,
    )
    from manifest_path_validator import validate_manifest_input_path
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import (  # type: ignore
        AUTHORITY_CLOSED,
        apply_diagnostic_gate_fields,
        audit_diagnostic_ticket_fields,
    )
    from scripts.manifest_path_validator import validate_manifest_input_path  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9209
NAME = "stage9209_repo_local_structured_one_run_ticket_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9208 = ROOT / "runs/summaries/stage9208_repo_local_execution_review_matrix.json"
MATRIX = ROOT / "runs/local/artifacts/stage9208_repo_local_execution_review_matrix/repo_local_execution_review_matrix.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPO_LOCAL_STRUCTURED_ONE_RUN_TICKET_DESIGN_STAGE9209.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TICKET = OUT_DIR / "repo_local_structured_one_run_ticket_inactive.json"
AUDIT = OUT_DIR / "repo_local_structured_one_run_ticket_design_audit.json"

REQUIRED_LIMITS = {
    "mode": "structured_policy_probe",
    "max_train_rows": 32,
    "max_eval_rows": 16,
    "max_strict_rows": 16,
    "max_steps": 8,
    "batch_size": 2,
    "max_encoder_tokens": 256,
    "max_decoder_tokens": 64,
    "structured_aux_weight": 1.0,
    "decoder_ce_weight": 0.0,
    "denoise_weight": 0.0,
    "runtime": False,
    "final_checkpoint_export": False,
}

REQUIRED_BEFORE_EXECUTION = [
    "explicit_user_one_run_request",
    "fresh_pre_execution_audit_passed_after_ticket",
    "manifest_path_audit_passed",
    "loss_mask_enforcement_runtime_assertions",
    "telemetry_artifact_gate_required",
    "safe_cleanup_marker_and_dry_run_passed",
    "post_run_stage8902_diagnostics_required",
    "stage8903_diagnostics_closure_required",
    "no_final_checkpoint_export",
]

DENIED_NOW_OPERATIONS = [
    "materialize_executable_command",
    "run_trainer",
    "instantiate_model",
    "run_model_forward",
    "run_backward",
    "create_optimizer",
    "write_checkpoint",
    "export_checkpoint",
    "run_runtime",
    "call_gemma",
    "score_output",
    "emit_source_body",
    "walk_arxiv",
    "mine_repositories",
    "cleanup_checkpoints",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def structured_review(matrix: dict[str, Any]) -> dict[str, Any]:
    for item in matrix.get("family_reviews") or []:
        if item.get("mode") == "structured_policy_probe":
            return item
    return {}


def path_is_under_repo(path_text: str) -> bool:
    try:
        Path(path_text).resolve().relative_to(ROOT)
        return True
    except ValueError:
        return False


def build_ticket(review: dict[str, Any]) -> dict[str, Any]:
    manifest_path = str(review.get("manifest_path") or "")
    ticket = {
        "ticket_id": "stage9209_repo_local_structured_policy_one_run_ticket__inactive",
        "ticket_status": "DESIGN_ONLY_INACTIVE",
        "requested_stage": "future_unassigned",
        "requested_stage_name": "future_repo_local_structured_policy_one_run",
        "requested_capability": "tiny_structured_policy_probe",
        "source_stage": 9208,
        "source_bundle_id": review.get("bundle_id"),
        "source_manifest_path": manifest_path,
        "future_output_dir": str(ROOT / "runs/local/probes/stage9209_structured_policy_one_run_candidate"),
        "requires_explicit_user_authorization": True,
        "requires_fresh_pre_execution_audit": True,
        "requires_manifest_path_audit": True,
        "requires_loss_mask_enforcement_audit": True,
        "requires_post_run_telemetry_gate": True,
        "command_materialized": False,
        "execution_authorized_now": False,
        "allowed_operations_now": [],
        "denied_operations_now": list(DENIED_NOW_OPERATIONS),
        "required_before_execution": list(REQUIRED_BEFORE_EXECUTION),
        "required_limits": dict(REQUIRED_LIMITS),
        "authority": dict(AUTHORITY_CLOSED),
    }
    return apply_diagnostic_gate_fields(ticket)


def audit_ticket(ticket: dict[str, Any], source_9208: dict[str, Any], matrix: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    failures = audit_diagnostic_ticket_fields(ticket)
    if source_9208.get("passed") is not True:
        failures.append("source_stage9208_not_passed")
    if matrix.get("passed") is not True:
        failures.append("matrix_not_passed")
    if not review:
        failures.append("structured_review_missing")
    if review.get("review_failures"):
        failures.append("structured_review_has_failures")
    if review.get("mode") != "structured_policy_probe":
        failures.append("wrong_review_mode")
    if ticket.get("ticket_status") != "DESIGN_ONLY_INACTIVE":
        failures.append("ticket_not_design_only_inactive")
    if ticket.get("execution_authorized_now") is not False:
        failures.append("execution_authorized_now_not_false")
    if ticket.get("allowed_operations_now") != []:
        failures.append("allowed_operations_now_not_empty")
    if ticket.get("command_materialized") is not False:
        failures.append("command_materialized_not_false")
    if ticket.get("future_output_dir") and not path_is_under_repo(str(ticket["future_output_dir"])):
        failures.append("future_output_dir_outside_repo")
    if "/arxiv" in str(ticket.get("future_output_dir")):
        failures.append("future_output_dir_mentions_arxiv")
    limits = ticket.get("required_limits") or {}
    for key, expected in REQUIRED_LIMITS.items():
        if limits.get(key) != expected:
            failures.append(f"limit_mismatch:{key}")
    for required in REQUIRED_BEFORE_EXECUTION:
        if required not in (ticket.get("required_before_execution") or []):
            failures.append(f"missing_required_before_execution:{required}")
    for denied in DENIED_NOW_OPERATIONS:
        if denied not in (ticket.get("denied_operations_now") or []):
            failures.append(f"missing_denied_operation:{denied}")
    manifest = str(ticket.get("source_manifest_path") or "")
    if not manifest:
        failures.append("source_manifest_missing")
        manifest_validation = {"allowed": False, "failures": ["missing"]}
    else:
        rel_or_abs = manifest
        try:
            rel_or_abs = str(Path(manifest).resolve().relative_to(ROOT))
        except ValueError:
            pass
        manifest_validation = validate_manifest_input_path(rel_or_abs, repo_root=ROOT, must_exist=True)
        if not manifest_validation.get("allowed"):
            failures.append("source_manifest_path_not_allowed")
    if any((ticket.get("authority") or {}).values()):
        failures.append("authority_open")
    return {
        "passed": not failures,
        "failures": failures,
        "manifest_validation": manifest_validation,
        "diagnostic_contract_failures": audit_diagnostic_ticket_fields(ticket),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [
        row for row in registry.get("rows", [])
        if row.get("stage") != STAGE and row.get("stage_name") != NAME
    ]
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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_9208 = load_json(SOURCE_9208)
    matrix = load_json(MATRIX)
    review = structured_review(matrix)
    ticket = build_ticket(review)
    audit = audit_ticket(ticket, source_9208, matrix, review)
    TICKET.write_text(json.dumps(ticket, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": audit["failures"],
            "ticket_contract_failures": len(audit["diagnostic_contract_failures"]),
            "denied_operations_now": len(DENIED_NOW_OPERATIONS),
            "required_before_execution": len(REQUIRED_BEFORE_EXECUTION),
            "command_materialized": False,
            "execution_authorized_now": False,
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "cleanup_authorized_now": False,
        },
        "artifacts": {
            "ticket": str(TICKET.relative_to(ROOT)),
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": (
            "Designed an inactive repo-local structured-policy one-run ticket from the Stage9206 manifest. "
            "No command is materialized and no execution, cleanup, runtime, decoder CE, denoise CE, source/body, "
            "Gemma, scoring, or mining authority is opened."
        ) if audit["passed"] else "Repo-local structured one-run ticket design failed.",
        "next_best_step": (
            "Audit the inactive Stage9209 ticket design and then run a final pre-execution audit only if an "
            "explicit one-run execution request is made."
        ),
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9209 Repo-Local Structured One-Run Ticket Design",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage creates an inactive ticket design for a future tiny structured-policy one-run probe.",
                "It binds the real Stage9206 structured manifest but does not materialize an executable command.",
                "",
                "Still closed:",
                "- trainer execution",
                "- model forward/backward",
                "- checkpoint writes or export",
                "- cleanup",
                "- decoder CE and denoise CE",
                "- runtime, Gemma, harness, scoring, source/body emission, mining, and /arxiv access",
                "",
                f"Next: {summary['next_best_step']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

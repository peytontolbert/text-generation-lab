#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8886
NAME = "stage8886_stage8890_inactive_execution_ticket_design"
PLAN = ROOT / "runs/local/artifacts/stage8864_native_probe_preflight_gate/native_probe_preflight_plan.jsonl"
REVIEW = ROOT / "runs/summaries/stage8882_tiny_structured_probe_execution_authorization_review.json"
TELEMETRY = ROOT / "runs/summaries/stage8862_native_probe_interpretability_artifact_contract.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "STAGE8890_INACTIVE_EXECUTION_TICKET_DESIGN_STAGE8886.md"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}

GATED_OPERATIONS = [
    "load_checkpoint",
    "run_forward",
    "decode_tokens",
    "write_model_output_artifact",
    "compute_decoder_ce",
    "compute_denoise_ce",
    "run_runtime",
    "call_gemma",
    "score_output",
    "emit_source_body",
    "promote_model",
]

FORBIDDEN_CLEANUP_PATHS = ["/", "/data", "/arxiv", str(ROOT)]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_plan(path: Path) -> dict[str, Any]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 1:
        raise SystemExit(f"expected exactly one Stage8890 candidate plan row, got {len(rows)}")
    return rows[0]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    plan = load_plan(PLAN)
    review = load_json(REVIEW)
    telemetry = load_json(TELEMETRY)
    ticket = {
        "ticket_id": "stage8890_tiny_structured_policy_probe_candidate__draft_inactive",
        "ticket_status": "DRAFT_INACTIVE",
        "requested_stage": 8890,
        "requested_stage_name": "stage8890_tiny_structured_policy_probe_candidate",
        "request_scope": "tiny_structured_policy_probe_candidate_only",
        "requires_explicit_user_authorization": True,
        "requires_fresh_pre_execution_audit": True,
        "requires_artifact_gate": True,
        "command_materialized": False,
        "execution_authorized_now": False,
        "allowed_operations": [],
        "denied_operations": list(GATED_OPERATIONS),
        "allowed_loss_weights": {
            "structured_aux_weight": 1.0,
            "decoder_ce_weight": 0.0,
            "denoise_weight": 0.0,
        },
        "dataset_scope": {
            "source_manifest": plan.get("source_manifest"),
            "objective_family": plan.get("objective_family"),
            "max_train_rows": plan.get("max_train_rows"),
            "max_eval_rows": plan.get("max_eval_rows"),
            "max_strict_rows": plan.get("max_strict_rows"),
            "required_trainable_fields": plan.get("required_trainable_fields", []),
        },
        "runtime_scope": {
            "mode": plan.get("mode"),
            "implementation": plan.get("implementation"),
            "batch_size": plan.get("batch_size"),
            "max_steps": plan.get("max_steps"),
            "max_encoder_tokens": plan.get("max_encoder_tokens"),
            "max_decoder_tokens": plan.get("max_decoder_tokens"),
            "model_execution_authorized_now": False,
            "decoder_ce_authorized_now": False,
            "denoise_ce_authorized_now": False,
            "runtime_authorized_now": False,
        },
        "artifact_scope": {
            "output_root": plan.get("output_dir"),
            "allowed_write_kinds": [
                "structured_probe_telemetry_after_future_explicit_authorization_only"
            ],
            "forbidden_write_kinds": [
                "final_checkpoint",
                "promotion_marker",
                "runtime_result",
                "gemma_score",
                "source_body",
                "hidden_reference_artifact",
            ],
            "required_interpretability_artifacts": plan.get("required_interpretability_artifacts", []),
            "post_run_artifact_gate": plan.get("post_run_artifact_gate", {}),
            "no_overwrite_existing": True,
        },
        "checkpoint_scope": {
            "final_checkpoint_export": False,
            "temporary_checkpoint_cleanup_policy": plan.get("cleanup_policy"),
            "cleanup_forbidden_paths": FORBIDDEN_CLEANUP_PATHS,
        },
        "expiry_policy": "single_future_stage_request_only_expires_if_stage8890_plan_changes",
        "reviewer": "stage8886_design_only_no_execution",
        "audit_log_ref": "runs/summaries/stage8887_stage8890_inactive_execution_ticket_gate_audit.json",
    }
    design_checks = [
        {"item": "prior_review_passed", "passed": review.get("passed") is True},
        {"item": "telemetry_contract_passed", "passed": telemetry.get("passed") is True},
        {"item": "ticket_inactive", "passed": ticket["ticket_status"] == "DRAFT_INACTIVE"},
        {"item": "no_allowed_operations", "passed": ticket["allowed_operations"] == []},
        {"item": "all_gated_operations_denied", "passed": set(GATED_OPERATIONS).issubset(set(ticket["denied_operations"]))},
        {"item": "decoder_ce_closed", "passed": ticket["allowed_loss_weights"]["decoder_ce_weight"] == 0.0},
        {"item": "denoise_ce_closed", "passed": ticket["allowed_loss_weights"]["denoise_weight"] == 0.0},
        {"item": "tiny_caps_preserved", "passed": ticket["dataset_scope"]["max_train_rows"] <= 32 and ticket["dataset_scope"]["max_eval_rows"] <= 16 and ticket["dataset_scope"]["max_strict_rows"] <= 16 and ticket["runtime_scope"]["max_steps"] <= 8},
        {"item": "artifact_gate_required", "passed": ticket["artifact_scope"]["post_run_artifact_gate"].get("required") is True},
        {"item": "arxiv_cleanup_forbidden", "passed": "/arxiv" in ticket["checkpoint_scope"]["cleanup_forbidden_paths"]},
        {"item": "authority_closed", "passed": not any(AUTHORITY_CLOSED.values())},
    ]
    failures = [check for check in design_checks if not check["passed"]]
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "design_checks": len(design_checks),
            "design_failures": len(failures),
            "ticket_status": ticket["ticket_status"],
            "execution_authorized_now": False,
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "command_materialized": False,
            "allowed_operations": len(ticket["allowed_operations"]),
            "denied_operations": len(ticket["denied_operations"]),
        },
        "ticket": ticket,
        "design_checks": design_checks,
        "artifacts": {
            "ticket": str((OUT_DIR / "stage8890_inactive_execution_ticket.json").relative_to(ROOT)),
            "source_plan": str(PLAN.relative_to(ROOT)),
            "source_review": str(REVIEW.relative_to(ROOT)),
        },
        "decision": "Draft inactive Stage8890 ticket designed. It does not authorize execution and materializes no command." if not failures else "Inactive ticket design failed; do not proceed.",
        "next_best_step": "Audit this inactive ticket. If it passes, keep Stage8890 reserved for an explicit future one-run execution request; do not run from this design stage.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "stage8890_inactive_execution_ticket.json").write_text(json.dumps(ticket, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "stage8890_inactive_execution_ticket_design_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8886 Stage8890 Inactive Execution Ticket Design",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage creates a draft inactive ticket only. It does not materialize a command and does not authorize model execution, decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, controller merge, or promotion.",
        "",
        f"Ticket status: `{ticket['ticket_status']}`",
        f"Allowed operations: `{len(ticket['allowed_operations'])}`",
        f"Denied operations: `{len(ticket['denied_operations'])}`",
        f"Design failures: `{len(failures)}`",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()

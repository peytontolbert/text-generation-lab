#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8887
NAME = "stage8887_stage8890_inactive_execution_ticket_gate_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8886_stage8890_inactive_execution_ticket_design.json"
SOURCE_TICKET = ROOT / "runs/local/artifacts/stage8886_stage8890_inactive_execution_ticket_design/stage8890_inactive_execution_ticket.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "STAGE8890_INACTIVE_EXECUTION_TICKET_GATE_AUDIT_STAGE8887.md"

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

REQUIRED_DENIED = {
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
}

REQUIRED_ARTIFACTS = {
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "feature_ablation_attribution.jsonl",
    "activation_patch_recovery.jsonl",
    "row_dynamics_history.jsonl",
    "module_delta_norms.json",
    "field_exact_by_cell.json",
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def under_runs_local_probes(path_text: str) -> bool:
    return path_text.startswith("runs/local/probes/") and ".." not in Path(path_text).parts


def main() -> None:
    design = load(SOURCE_SUMMARY)
    ticket = load(SOURCE_TICKET)
    loss = ticket.get("allowed_loss_weights") or {}
    dataset = ticket.get("dataset_scope") or {}
    runtime = ticket.get("runtime_scope") or {}
    artifact = ticket.get("artifact_scope") or {}
    checkpoint = ticket.get("checkpoint_scope") or {}
    denied = set(ticket.get("denied_operations") or [])
    cleanup_forbidden = set(checkpoint.get("cleanup_forbidden_paths") or [])
    required_artifacts = set(artifact.get("required_interpretability_artifacts") or [])
    gate_checks = [
        {"item": "source_design_passed", "passed": design.get("passed") is True},
        {"item": "ticket_status_inactive", "passed": ticket.get("ticket_status") == "DRAFT_INACTIVE"},
        {"item": "requires_explicit_user_authorization", "passed": ticket.get("requires_explicit_user_authorization") is True},
        {"item": "requires_fresh_pre_execution_audit", "passed": ticket.get("requires_fresh_pre_execution_audit") is True},
        {"item": "execution_authorized_now_false", "passed": ticket.get("execution_authorized_now") is False},
        {"item": "command_not_materialized", "passed": ticket.get("command_materialized") is False and "command" not in ticket},
        {"item": "allowed_operations_empty", "passed": ticket.get("allowed_operations") == []},
        {"item": "all_required_operations_denied", "passed": REQUIRED_DENIED.issubset(denied)},
        {"item": "structured_aux_only", "passed": loss.get("structured_aux_weight") == 1.0 and loss.get("decoder_ce_weight") == 0.0 and loss.get("denoise_weight") == 0.0},
        {"item": "tiny_caps_preserved", "passed": dataset.get("max_train_rows") <= 32 and dataset.get("max_eval_rows") <= 16 and dataset.get("max_strict_rows") <= 16 and runtime.get("max_steps") <= 8},
        {"item": "output_root_scoped", "passed": under_runs_local_probes(str(artifact.get("output_root", "")))},
        {"item": "artifact_gate_required", "passed": (artifact.get("post_run_artifact_gate") or {}).get("required") is True and (artifact.get("post_run_artifact_gate") or {}).get("fail_if_missing_or_empty") is True},
        {"item": "required_interpretability_artifacts_complete", "passed": REQUIRED_ARTIFACTS.issubset(required_artifacts)},
        {"item": "no_final_checkpoint_export", "passed": checkpoint.get("final_checkpoint_export") is False},
        {"item": "safe_cleanup_policy", "passed": checkpoint.get("temporary_checkpoint_cleanup_policy") == "safe_cleanup_checkpoints_only"},
        {"item": "root_data_arxiv_repo_cleanup_forbidden", "passed": {"/", "/data", "/arxiv", str(ROOT)}.issubset(cleanup_forbidden)},
        {"item": "authority_closed", "passed": not any(AUTHORITY_CLOSED.values()) and not any((design.get("authority") or {}).values())},
    ]
    failures = [check for check in gate_checks if not check["passed"]]
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "gate_checks": len(gate_checks),
            "gate_failures": len(failures),
            "execution_authorized_now": False,
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "ticket_status": ticket.get("ticket_status"),
            "command_materialized": False,
            "allowed_operations": len(ticket.get("allowed_operations") or []),
            "denied_operations": len(denied),
            "required_artifact_count": len(required_artifacts),
        },
        "gate_checks": gate_checks,
        "ticket_ref": str(SOURCE_TICKET.relative_to(ROOT)),
        "decision": "Inactive Stage8890 ticket gate passed. It remains non-executing and can only support a future explicit one-run request." if not failures else "Inactive Stage8890 ticket gate failed; do not use the ticket.",
        "next_best_step": "Reconcile Stage8886-8887 into the registry. Stage8890 remains unrun and requires explicit future authorization before any model execution.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8887 Stage8890 Inactive Execution Ticket Gate Audit",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Gate failures: `{len(failures)}`",
        f"Execution authorized now: `{card['metrics']['execution_authorized_now']}`",
        f"Allowed operations: `{card['metrics']['allowed_operations']}`",
        f"Denied operations: `{card['metrics']['denied_operations']}`",
        "",
        "The ticket remains inactive. It cannot run a model, train decoder CE, train denoise CE, execute runtime, write source/body output, call Gemma/harness/scoring, export checkpoints, or promote.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()

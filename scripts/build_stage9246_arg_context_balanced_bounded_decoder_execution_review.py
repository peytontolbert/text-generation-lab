#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED, apply_diagnostic_gate_fields, audit_diagnostic_ticket_fields
    from manifest_path_validator import validate_manifest_input_path
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED, apply_diagnostic_gate_fields, audit_diagnostic_ticket_fields  # type: ignore
    from scripts.manifest_path_validator import validate_manifest_input_path  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9246
NAME = "stage9246_arg_context_balanced_bounded_decoder_execution_review"
SOURCE_PACKAGE = ROOT / "runs/summaries/stage9244_source_backed_arg_context_balanced_bounded_decoder_tiny_package.json"
SOURCE_PREFLIGHT = ROOT / "runs/summaries/stage9245_arg_context_balanced_target_100m_contract_only_preflight.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ARG_CONTEXT_BALANCED_BOUNDED_DECODER_EXECUTION_REVIEW_STAGE9246.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TICKET = OUT_DIR / "arg_context_balanced_bounded_decoder_execution_review_inactive.json"
AUDIT = OUT_DIR / "arg_context_balanced_bounded_decoder_execution_review_audit.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

MANIFEST = "runs/local/artifacts/stage9244_source_backed_arg_context_balanced_bounded_decoder_tiny_package/source_backed_arg_context_balanced_bounded_decoder_tiny_manifest.jsonl"
OUTPUT_DIR = "runs/local/artifacts/stage9247_arg_context_balanced_target_100m_bounded_tiny_probe/bounded_decoder_probe"
RUN_ID = "stage9247_arg_context_balanced_target_100m_bounded_tiny_probe"

REQUIRED_LIMITS = {
    "mode": "bounded_decoder_ce_probe",
    "probe_scale": "target_100m",
    "implementation": "transformer",
    "max_train_rows": 32,
    "max_eval_rows": 16,
    "max_strict_rows": 16,
    "max_steps": 16,
    "batch_size": 2,
    "max_encoder_tokens": 256,
    "max_decoder_tokens": 768,
    "learning_rate": 5e-5,
    "decoder_ce_weight": 1.0,
    "structured_aux_weight": 0.0,
    "denoise_weight": 0.0,
    "generation_audit_enabled": True,
    "max_generation_rows": 16,
    "max_generation_tokens": 96,
    "runtime": False,
    "gemma": False,
    "harness": False,
    "scoring": False,
    "source_body_emission": False,
    "final_checkpoint_export": False,
    "cleanup_checkpoints_after_probe": True,
}

REQUIRED_BEFORE_EXECUTION = [
    "explicit_user_one_run_execution_authorization",
    "fresh_pre_execution_audit_passed_after_this_review",
    "manifest_sha256_matches_stage9245",
    "tokenizer_hashlock_matches_repo_local_1506_bpe",
    "loss_mask_enforcement_runtime_assertions",
    "safe_cleanup_marker_and_dry_run_passed",
    "post_run_generation_quality_diagnostics_required",
    "metrics_interpretation_blocked_until_diagnostics_pass",
    "no_final_checkpoint_export",
    "runtime_gemma_harness_scoring_closed",
]

DENIED_NOW_OPERATIONS = [
    "run_trainer",
    "instantiate_model",
    "run_model_forward",
    "run_training_step",
    "run_backward",
    "create_optimizer",
    "generate_model_output",
    "write_checkpoint",
    "export_checkpoint",
    "open_runtime",
    "call_gemma",
    "run_harness",
    "score_output",
    "emit_source_body",
    "promote_model",
    "walk_arxiv",
    "mine_repositories",
    "cleanup_checkpoints",
]

FUTURE_ARGV = [
    "conda", "run", "-n", "trellis", "python", "legacy_src/scripts/train_agentkernel_lite_encdec.py",
    "--repo-root", str(ROOT),
    "--manifest", MANIFEST,
    "--mode", "bounded_decoder_ce_probe",
    "--max-train-rows", "32",
    "--max-eval-rows", "16",
    "--max-strict-rows", "16",
    "--max-steps", "16",
    "--max-decoder-tokens", "768",
    "--decoder-ce-weight", "1.0",
    "--structured-aux-weight", "0.0",
    "--denoise-weight", "0.0",
    "--require-loss-mask-enforcement-audit",
    "--no-final-checkpoint-export",
    "--cleanup-checkpoints-after-probe",
    "--skip-final-model-save", "1",
    "--output-dir", OUTPUT_DIR,
    "--run-id", RUN_ID,
    "--batch-size", "2",
    "--max-encoder-tokens", "256",
    "--learning-rate", "5e-5",
    "--implementation", "transformer",
    "--probe-scale", "target_100m",
    "--model-config", "configs/model/agentkernel_100m_seq2seq_recovered_target.json",
    "--tokenizer-json", "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json",
    "--tokenizer-config", "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json",
    "--tokenizer-hashlock", "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json",
    "--enable-generation-audit",
    "--max-generation-rows", "16",
    "--max-generation-tokens", "96",
    "--execution-authorized-for-recovery-probe",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def path_under_repo(path_text: str) -> bool:
    try:
        (ROOT / path_text if not Path(path_text).is_absolute() else Path(path_text)).resolve().relative_to(ROOT)
        return True
    except ValueError:
        return False


def build_ticket(source_preflight: dict[str, Any]) -> dict[str, Any]:
    ticket = {
        "ticket_id": "stage9246_arg_context_balanced_bounded_decoder_execution_review__inactive",
        "ticket_status": "DESIGN_ONLY_INACTIVE",
        "requested_stage": 9247,
        "requested_stage_name": RUN_ID,
        "requested_capability": "tiny_arg_context_balanced_target_100m_bounded_decoder_ce_probe",
        "source_stage": 9245,
        "source_manifest_path": MANIFEST,
        "source_manifest_sha256": (source_preflight.get("metrics") or {}).get("manifest_sha256"),
        "future_output_dir": OUTPUT_DIR,
        "future_argv": list(FUTURE_ARGV),
        "command_materialized_for_review_only": True,
        "command_executable_now": False,
        "requires_explicit_user_authorization": True,
        "requires_fresh_pre_execution_audit": True,
        "execution_authorized_now": False,
        "model_execution_authorized_now": False,
        "decoder_ce_training_authorized_now": False,
        "allowed_operations_now": [],
        "denied_operations_now": list(DENIED_NOW_OPERATIONS),
        "required_before_execution": list(REQUIRED_BEFORE_EXECUTION),
        "required_limits": dict(REQUIRED_LIMITS),
        "authority": dict(AUTHORITY_CLOSED),
    }
    return apply_diagnostic_gate_fields(ticket)


def audit_ticket(ticket: dict[str, Any], source_package: dict[str, Any], source_preflight: dict[str, Any]) -> dict[str, Any]:
    failures = audit_diagnostic_ticket_fields(ticket)
    if source_package.get("passed") is not True:
        failures.append("source_stage9244_not_passed")
    if source_preflight.get("passed") is not True:
        failures.append("source_stage9245_not_passed")
    if ticket.get("ticket_status") != "DESIGN_ONLY_INACTIVE":
        failures.append("ticket_not_design_only_inactive")
    if ticket.get("execution_authorized_now") is not False:
        failures.append("execution_authorized_now_not_false")
    if ticket.get("model_execution_authorized_now") is not False:
        failures.append("model_execution_authorized_now_not_false")
    if ticket.get("decoder_ce_training_authorized_now") is not False:
        failures.append("decoder_ce_training_authorized_now_not_false")
    if ticket.get("allowed_operations_now") != []:
        failures.append("allowed_operations_now_not_empty")
    if ticket.get("command_executable_now") is not False:
        failures.append("command_executable_now_not_false")
    if not ticket.get("requires_explicit_user_authorization"):
        failures.append("explicit_user_authorization_not_required")
    if any((ticket.get("authority") or {}).values()):
        failures.append("authority_open")
    for key, expected in REQUIRED_LIMITS.items():
        if (ticket.get("required_limits") or {}).get(key) != expected:
            failures.append(f"limit_mismatch:{key}")
    for item in REQUIRED_BEFORE_EXECUTION:
        if item not in (ticket.get("required_before_execution") or []):
            failures.append(f"missing_required_before_execution:{item}")
    for item in DENIED_NOW_OPERATIONS:
        if item not in (ticket.get("denied_operations_now") or []):
            failures.append(f"missing_denied_operation:{item}")
    if not path_under_repo(str(ticket.get("future_output_dir") or "")):
        failures.append("future_output_dir_not_under_repo")
    if "/arxiv" in str(ticket.get("future_output_dir") or ""):
        failures.append("future_output_dir_mentions_arxiv")
    manifest_validation = validate_manifest_input_path(MANIFEST, repo_root=ROOT, must_exist=True)
    if not manifest_validation.get("allowed"):
        failures.append("source_manifest_path_not_allowed")
    if (source_preflight.get("metrics") or {}).get("model_execution_attempted") is not False:
        failures.append("source_stage9245_attempted_execution")
    return {
        "passed": not failures,
        "failures": failures,
        "manifest_validation": manifest_validation,
        "diagnostic_contract_failures": audit_diagnostic_ticket_fields(ticket),
    }


def negative_cases(ticket: dict[str, Any], source_package: dict[str, Any], source_preflight: dict[str, Any]) -> list[dict[str, Any]]:
    cases: list[tuple[str, dict[str, Any]]] = []
    mutated = copy.deepcopy(ticket); mutated["execution_authorized_now"] = True; cases.append(("execution_authorized_now_true", mutated))
    mutated = copy.deepcopy(ticket); mutated["model_execution_authorized_now"] = True; cases.append(("model_execution_authorized_now_true", mutated))
    mutated = copy.deepcopy(ticket); mutated["decoder_ce_training_authorized_now"] = True; cases.append(("decoder_ce_training_authorized_now_true", mutated))
    mutated = copy.deepcopy(ticket); mutated["allowed_operations_now"] = ["run_trainer"]; cases.append(("allowed_operations_now_not_empty", mutated))
    mutated = copy.deepcopy(ticket); mutated["denied_operations_now"] = [item for item in mutated["denied_operations_now"] if item != "run_trainer"]; cases.append(("run_trainer_not_denied", mutated))
    mutated = copy.deepcopy(ticket); mutated["future_output_dir"] = "/arxiv/blocked"; cases.append(("future_output_dir_arxiv", mutated))
    mutated = copy.deepcopy(ticket); mutated["required_limits"]["max_train_rows"] = 128; cases.append(("max_train_rows_widened", mutated))
    mutated = copy.deepcopy(ticket); mutated["required_limits"]["runtime"] = True; cases.append(("runtime_opened", mutated))
    mutated = copy.deepcopy(ticket); mutated["authority"]["model_execution_authorized_next"] = True; cases.append(("authority_open", mutated))
    results = []
    for name, case_ticket in cases:
        audit = audit_ticket(case_ticket, source_package, source_preflight)
        results.append({"case": name, "rejected": audit["passed"] is False, "failures": audit["failures"]})
    return results


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source_package = load_json(SOURCE_PACKAGE)
    source_preflight = load_json(SOURCE_PREFLIGHT)
    ticket = build_ticket(source_preflight)
    audit = audit_ticket(ticket, source_package, source_preflight)
    negatives = negative_cases(ticket, source_package, source_preflight)
    all_negatives_rejected = all(item["rejected"] for item in negatives)
    if not all_negatives_rejected:
        audit["failures"].append("negative_cases_not_rejected")
        audit["passed"] = False
    TICKET.write_text(json.dumps(ticket, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    AUDIT.write_text(json.dumps({**audit, "negative_cases": negatives}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": audit["failures"],
            "diagnostic_contract_failures": len(audit["diagnostic_contract_failures"]),
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives if item["rejected"]),
            "command_materialized_for_review_only": True,
            "command_executable_now": False,
            "execution_authorized_now": False,
            "model_execution_authorized_now": False,
            "decoder_ce_training_authorized_now": False,
            "runtime_authorized_flag": False,
        },
        "artifacts": {"ticket": str(TICKET.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built an inactive execution review for the Stage9244/9245 argument/context-balanced target-100M bounded tiny probe. It records the future command but authorizes no execution." if audit["passed"] else "Argument/context-balanced bounded decoder execution review failed.",
        "next_best_step": "If the user explicitly authorizes one tiny execution, run the reviewed Stage9247 command; otherwise continue no-execution data/compiler work.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9246 Argument/Context-Balanced Bounded Decoder Execution Review",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage records an inactive future one-run command for the Stage9244 argument/context-balanced bounded decoder manifest after the Stage9245 contract-only preflight. It does not execute trainer or authorize model execution now.",
        "",
        f"Ticket: `{summary['artifacts']['ticket']}`",
        f"Negative cases rejected: `{summary['metrics']['negative_cases_rejected']}` / `{summary['metrics']['negative_cases']}`",
        f"Execution authorized now: `{summary['metrics']['execution_authorized_now']}`",
        f"Command executable now: `{summary['metrics']['command_executable_now']}`",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ]) + "\n", encoding="utf-8")
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()

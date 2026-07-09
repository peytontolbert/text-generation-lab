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
STAGE = 9554
NAME = "stage9554_residual_denoise_one_run_ticket_preflight_design"
SOURCE_REVIEW = ROOT / "runs/summaries/stage9553_residual_denoise_no_execution_authorization_review_audit.json"
REAL_ROWS = ROOT / "runs/local/artifacts/stage9545_residual_repair_route_manifest/residual_repair_route_manifest.jsonl"
DESIGN_ROWS = ROOT / "runs/local/artifacts/stage9549_residual_denoise_design_examples/residual_denoise_design_examples.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TICKET = OUT_DIR / "residual_denoise_one_run_ticket_preflight_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_ONE_RUN_TICKET_PREFLIGHT_DESIGN_STAGE9554.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

COMMAND_TEMPLATE = [
    "conda", "run", "-n", "trellis", "python", "legacy_src/scripts/train_agentkernel_lite_encdec.py",
    "--repo-root", ".",
    "--manifest", "<future_combined_residual_denoise_manifest.jsonl>",
    "--mode", "residual_denoise_probe",
    "--max-train-rows", "24",
    "--max-eval-rows", "8",
    "--max-strict-rows", "8",
    "--max-steps", "16",
    "--decoder-ce-weight", "0",
    "--structured-aux-weight", "0",
    "--denoise-weight", "1",
    "--require-loss-mask-enforcement-audit",
    "--no-final-checkpoint-export",
    "--cleanup-checkpoints-after-probe",
    "--skip-final-model-save", "1",
    "--output-dir", "runs/local/artifacts/<future_stage_residual_denoise_tiny_probe>",
    "--run-id", "<future_stage_residual_denoise_tiny_probe>",
    "--probe-scale", "target_100m",
    "--model-config", "configs/model/agentkernel_100m_seq2seq_recovered_target.json",
    "--tokenizer-json", "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json",
    "--tokenizer-config", "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json",
]
REQUIRED_PREFLIGHT_CHECKS = [
    "stage9551_shortcut_balance_passed",
    "stage9553_no_execution_review_passed",
    "future_combined_manifest_exists_and_hash_locked",
    "loss_mask_has_only_denoise_ce_enabled",
    "decoder_ce_rows_zero",
    "runtime_reward_rows_zero",
    "authority_rows_zero",
    "target_length_under_cap",
    "raw_effective_labels_absent_from_model_input",
    "safe_output_dir_under_runs_local_artifacts",
    "safe_cleanup_marker_present",
    "required_telemetry_artifacts_declared",
    "explicit_execution_authorization_card_present",
]
REQUIRED_TELEMETRY = [
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_token_loss.jsonl",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
    "sample_generation_audit.json",
    "feature_ablation_attribution.jsonl",
    "activation_patch_recovery.jsonl",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


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
    review = load_json(SOURCE_REVIEW)
    real = load_jsonl(REAL_ROWS)
    design = load_jsonl(DESIGN_ROWS)
    failures: list[str] = []
    if review.get("passed") is not True:
        failures.append("stage9553_review_audit_not_passed")
    if len(real) != 29:
        failures.append("real_residual_row_count_mismatch")
    if len(design) != 15:
        failures.append("design_row_count_mismatch")

    ticket = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "failures": failures,
        "source_review": str(SOURCE_REVIEW.relative_to(ROOT)),
        "candidate_sources": {
            "real_residual_rows": str(REAL_ROWS.relative_to(ROOT)),
            "design_rows": str(DESIGN_ROWS.relative_to(ROOT)),
            "real_residual_row_count": len(real),
            "design_row_count": len(design),
            "filtered_target_bucket_row_count_from_stage9551": 41,
        },
        "ticket_type": "contract_only_preflight_design",
        "execution_command_emitted": False,
        "command_template_not_runnable_until_materialized": COMMAND_TEMPLATE,
        "execution_authorized_now": False,
        "execution_authorized_for_next_stage": False,
        "denoise_ce_authorized_now": False,
        "decoder_ce_authorized_now": False,
        "runtime_authorized_now": False,
        "required_prefight_checks": REQUIRED_PREFLIGHT_CHECKS,
        "required_future_telemetry": REQUIRED_TELEMETRY,
        "future_probe_caps": {"max_train_rows": 24, "max_eval_rows": 8, "max_strict_rows": 8, "max_steps": 16, "probe_scale": "target_100m"},
        "blocked_until": [
            "future_combined_residual_denoise_manifest_materialized",
            "contract_only_manifest_preflight_passed",
            "explicit_execution_authorization_review_passed",
            "safe_cleanup_contract_asserted",
        ],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "real_residual_row_count": len(real),
            "design_row_count": len(design),
            "execution_command_emitted": False,
            "execution_authorized_for_next_stage": False,
            "denoise_ce_authorized_now": False,
            "required_prefight_checks": len(REQUIRED_PREFLIGHT_CHECKS),
            "required_future_telemetry_count": len(REQUIRED_TELEMETRY),
        },
    }
    TICKET.write_text(json.dumps(ticket, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": ticket["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **ticket["metrics"], "failures": failures},
        "artifacts": {"ticket": str(TICKET.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Designed a contract-only residual-denoise one-run ticket shell. It is not runnable, emits no execution command, and requires a separate manifest preflight plus explicit execution authorization.",
        "next_best_step": "Audit Stage9554; then materialize a combined residual-denoise manifest and run contract-only manifest preflight before any execution authorization.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9554 Residual Denoise One-Run Ticket Preflight Design",
        "",
        f"Passed: `{ticket['passed']}`",
        "Execution command emitted: `False`",
        "Execution authorized for next stage: `False`",
        "Denoise CE authorized now: `False`",
        "",
        "This is a contract-only shell. The command template contains placeholders and cannot be run until a future manifest preflight and explicit execution authorization pass.",
        "",
    ]))
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": ticket["passed"], "failures": failures, "execution_authorized_for_next_stage": False}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

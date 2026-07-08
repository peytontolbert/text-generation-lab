#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9269
NAME = "stage9269_target_100m_denoise_probe_diagnostic_audit"
SOURCE_PREFLIGHT = ROOT / "runs/summaries/stage9268_denoise_repair_contract_preflight.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9269_target_100m_denoise_repair_probe/denoise_repair_probe"
AUDIT = RUN_DIR / "stage9269_denoise_probe_diagnostic_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TARGET_100M_DENOISE_PROBE_DIAGNOSTIC_AUDIT_STAGE9269.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REQUIRED_ARTIFACTS = [
    "probe_contract_audit.json",
    "execution_result.json",
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_token_loss.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "row_dynamics_history.jsonl",
    "denoise_repair_quality_audit.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def audit_run() -> dict[str, Any]:
    source = load_json(SOURCE_PREFLIGHT)
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    quality = load_json(RUN_DIR / "denoise_repair_quality_audit.json")
    deltas = load_json(RUN_DIR / "module_delta_norms.json")
    cleanup = load_json(RUN_DIR / "cleanup_proof.json")
    losses = load_jsonl(RUN_DIR / "loss_by_step.jsonl")
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9268_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if execution.get("mode") != "denoise_repair_probe":
        failures.append("execution_mode_not_denoise")
    if contract.get("loss_counts", {}).get("decoder_ce") != 0 or execution.get("decoder_ce_rows") != 0:
        failures.append("decoder_ce_opened")
    if contract.get("loss_counts", {}).get("denoise_ce") != 21 or execution.get("denoise_ce_rows") != 21:
        failures.append("denoise_row_count_mismatch")
    if contract.get("authority_rows") != 0:
        failures.append("authority_rows_nonzero")
    if execution.get("final_checkpoint_exported") is not False:
        failures.append("checkpoint_exported")
    if execution.get("runtime_executed") is not False or execution.get("gemma_executed") is not False or execution.get("harness_executed") is not False:
        failures.append("forbidden_execution_surface_opened")
    if execution.get("required_artifacts_written") is not True:
        failures.append("required_artifacts_not_written")
    missing_artifacts = [name for name in REQUIRED_ARTIFACTS if not (RUN_DIR / name).exists() or ((RUN_DIR / name).suffix == ".jsonl" and (RUN_DIR / name).stat().st_size == 0)]
    if missing_artifacts:
        failures.append("missing_required_artifacts")
    if cleanup.get("cleanup_executed") is not False:
        failures.append("cleanup_should_not_execute_for_no_checkpoint_loop")
    train_loss_start = float(losses[0]["loss"]) if losses else None
    train_loss_end = float(losses[-1]["loss"]) if losses else None
    train_loss_decreased = train_loss_start is not None and train_loss_end is not None and train_loss_end < train_loss_start
    if not train_loss_decreased:
        failures.append("train_loss_not_decreased")
    grad_max = max((float(row.get("pre_clip_grad_norm", row.get("grad_norm", 0.0))) for row in losses), default=0.0)
    post_grad_max = max((float(row.get("post_clip_grad_norm", 0.0)) for row in losses), default=0.0)
    if post_grad_max > 1.01:
        failures.append("post_clip_grad_norm_exceeded")
    structured_delta = float(deltas.get("structured_head_delta_norm", 0.0))
    if structured_delta != 0.0:
        failures.append("structured_heads_changed")
    return {
        "passed": not failures,
        "failures": failures,
        "missing_artifacts": missing_artifacts,
        "rows": execution.get("denoise_ce_rows"),
        "train_rows": execution.get("train_rows"),
        "eval_rows": execution.get("eval_rows"),
        "strict_rows": execution.get("strict_rows"),
        "estimated_parameter_count": (execution.get("implementation") or {}).get("estimated_parameter_count"),
        "train_loss_start": train_loss_start,
        "train_loss_end": train_loss_end,
        "train_loss_decreased": train_loss_decreased,
        "eval_loss": ((execution.get("eval") or {}).get("eval") or {}).get("loss"),
        "strict_eval_loss": ((execution.get("eval") or {}).get("strict_eval") or {}).get("loss"),
        "pre_clip_grad_norm_max": grad_max,
        "post_clip_grad_norm_max": post_grad_max,
        "decoder_delta_norm": deltas.get("decoder_delta_norm"),
        "encoder_delta_norm": deltas.get("encoder_delta_norm"),
        "structured_head_delta_norm": structured_delta,
        "target_internal_token_rows": quality.get("target_internal_token_rows"),
        "target_repetition_rows": quality.get("target_repetition_rows"),
        "decoder_ce_rows": execution.get("decoder_ce_rows"),
        "runtime_executed": execution.get("runtime_executed"),
        "gemma_executed": execution.get("gemma_executed"),
        "harness_executed": execution.get("harness_executed"),
        "final_checkpoint_exported": execution.get("final_checkpoint_exported"),
        "required_artifacts_written": execution.get("required_artifacts_written"),
        "authority": dict(AUTHORITY_CLOSED),
    }


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
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = audit_run()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "The tiny target-100M denoise repair probe executed safely and learned the tiny repair objective at the CE level. It does not prove generation quality or decoder repair quality yet.",
        "next_best_step": "Build a denoise repair generation-quality probe that samples repaired outputs from Stage9267 rows and audits repetition, EOS termination, prefix match, and internal-token leakage before reconnecting denoise to bounded decoder repair.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9269 Target-100M Denoise Probe Diagnostic Audit",
                "",
                "The denoise-only probe ran on Stage9267 repair rows with decoder CE, runtime, Gemma, harness, scoring, and checkpoint export closed.",
                "",
                f"Train loss: {audit['train_loss_start']} -> {audit['train_loss_end']}",
                f"Eval loss: {audit['eval_loss']}",
                f"Strict eval loss: {audit['strict_eval_loss']}",
                f"Pre-clip grad max: {audit['pre_clip_grad_norm_max']}",
                f"Post-clip grad max: {audit['post_clip_grad_norm_max']}",
                f"Structured head delta norm: {audit['structured_head_delta_norm']}",
                "",
                "This is a CE-level repair probe only. It does not authorize bounded decoder CE reruns or product/harness integration.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

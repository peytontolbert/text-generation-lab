#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9568
NAME = "stage9568_residual_denoise_target_rendered_tiny_probe"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9567_residual_denoise_target_rendered_contract_preflight_audit.json"
COMMAND_JSON = ROOT / "runs/local/artifacts/stage9566_residual_denoise_target_rendered_manifest/residual_denoise_target_rendered_commands.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9568_residual_denoise_target_rendered_tiny_probe/denoise_repair_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "residual_denoise_target_rendered_tiny_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_TARGET_RENDERED_TINY_PROBE_STAGE9568.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def count_jsonl(path: Path) -> int:
    return len(load_jsonl(path))


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    commands = load_json(COMMAND_JSON)
    execution_command = commands.get("future_execution_command") if isinstance(commands.get("future_execution_command"), list) else []
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9567_not_passed")
    auth = source.get("authority") if isinstance(source.get("authority"), dict) else {}
    if auth.get("model_execution_authorized_next") is not True or auth.get("denoise_ce_training_authorized_next") is not True:
        failures.append("stage9567_did_not_authorize_next_probe")
    if not execution_command:
        failures.append("missing_future_execution_command")
    if "--execution-authorized-for-recovery-probe" not in execution_command:
        failures.append("execution_command_missing_authorization_flag")
    if "--contract-only" in execution_command:
        failures.append("execution_command_is_contract_only")
    completed = None
    if not failures:
        completed = subprocess.run(execution_command, cwd=ROOT, text=True, capture_output=True, check=False)
        if completed.returncode != 0:
            failures.append("execution_command_failed")
    execution_result = load_json(RUN_DIR / "execution_result.json")
    quality = load_json(RUN_DIR / "denoise_repair_quality_audit.json")
    token_rows = load_jsonl(RUN_DIR / "row_token_loss.jsonl")
    step_rows = load_jsonl(RUN_DIR / "loss_by_step.jsonl")
    if not execution_result:
        failures.append("missing_execution_result")
    if execution_result and execution_result.get("required_artifacts_written") is not True:
        failures.append("required_artifacts_not_written")
    if execution_result and execution_result.get("denoise_ce_rows") != 41:
        failures.append("denoise_ce_rows_not_41")
    if execution_result and execution_result.get("decoder_ce_rows") != 0:
        failures.append("decoder_ce_rows_present")
    if execution_result and execution_result.get("runtime_executed") is not False:
        failures.append("runtime_executed")
    if execution_result and execution_result.get("final_checkpoint_exported") is not False:
        failures.append("final_checkpoint_exported")
    non_eos_token_rows = [row for row in token_rows if int(row.get("token_count", 0)) > 1 or int(row.get("eos_position", 0)) != 0]
    if not non_eos_token_rows:
        failures.append("target_rendering_still_eos_only")
    nonzero_loss_steps = [row for row in step_rows if float(row.get("loss", 0.0)) > 0.0]
    nonzero_grad_steps = [row for row in step_rows if float(row.get("grad_norm", 0.0)) > 0.0]
    if not nonzero_loss_steps:
        failures.append("no_nonzero_loss_steps")
    if not nonzero_grad_steps:
        failures.append("no_nonzero_grad_steps")
    telemetry_counts = {
        "loss_by_step": count_jsonl(RUN_DIR / "loss_by_step.jsonl"),
        "eval_loss_by_checkpoint": count_jsonl(RUN_DIR / "eval_loss_by_checkpoint.jsonl"),
        "row_token_loss": count_jsonl(RUN_DIR / "row_token_loss.jsonl"),
        "row_gradient_norms": count_jsonl(RUN_DIR / "row_gradient_norms.jsonl"),
        "activation_summary": count_jsonl(RUN_DIR / "activation_summary.jsonl"),
        "row_dynamics_history": count_jsonl(RUN_DIR / "row_dynamics_history.jsonl"),
    }
    for key, value in telemetry_counts.items():
        if value <= 0:
            failures.append(f"empty_telemetry:{key}")
    passed = not failures
    audit = {
        "passed": passed,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "command_json": str(COMMAND_JSON.relative_to(ROOT)),
        "run_dir": str(RUN_DIR.relative_to(ROOT)),
        "returncode": None if completed is None else completed.returncode,
        "stdout_tail": "" if completed is None else completed.stdout[-4000:],
        "stderr_tail": "" if completed is None else completed.stderr[-4000:],
        "telemetry_counts": telemetry_counts,
        "token_loss_rows": len(token_rows),
        "non_eos_token_loss_rows": len(non_eos_token_rows),
        "loss_steps": len(step_rows),
        "nonzero_loss_steps": len(nonzero_loss_steps),
        "nonzero_grad_steps": len(nonzero_grad_steps),
        "train_rows": execution_result.get("train_rows"),
        "eval_rows": execution_result.get("eval_rows"),
        "strict_rows": execution_result.get("strict_rows"),
        "max_steps": execution_result.get("max_steps"),
        "denoise_ce_rows": execution_result.get("denoise_ce_rows"),
        "decoder_ce_rows": execution_result.get("decoder_ce_rows"),
        "generated_rows": execution_result.get("generated_rows"),
        "contentful_generation_rate": execution_result.get("contentful_generation_rate"),
        "short_or_junk_rate": execution_result.get("short_or_junk_rate"),
        "degenerate_repetition_rate": execution_result.get("degenerate_repetition_rate"),
        "target_prefix_match_rate": execution_result.get("target_prefix_match_rate"),
        "quality": quality,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": passed,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "execution_result": str((RUN_DIR / "execution_result.json").relative_to(ROOT)) if (RUN_DIR / "execution_result.json").exists() else None, "quality_audit": str((RUN_DIR / "denoise_repair_quality_audit.json").relative_to(ROOT)) if (RUN_DIR / "denoise_repair_quality_audit.json").exists() else None, "doc": str(DOC.relative_to(ROOT))},
        "decision": "Executed the target-rendered residual-denoise tiny probe. This stage validates that the target rendering fix produced non-EOS supervised decoder tokens.",
        "next_best_step": "Audit Stage9568 quality and decide whether to add more residual-denoise rows or adjust generation/eval criteria before widening.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9568 Residual Denoise Target-Rendered Tiny Probe", "", f"Passed: `{passed}`", f"Train/eval/strict rows: `{execution_result.get('train_rows')}` / `{execution_result.get('eval_rows')}` / `{execution_result.get('strict_rows')}`", f"Non-EOS token-loss rows: `{len(non_eos_token_rows)}`", f"Nonzero loss steps: `{len(nonzero_loss_steps)}`", f"Generated rows: `{execution_result.get('generated_rows')}`", "", "No promotion, runtime, harness, Gemma, source/body emission, or decoder CE is authorized by this run.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": passed, "train_rows": execution_result.get("train_rows"), "generated_rows": execution_result.get("generated_rows"), "non_eos_token_loss_rows": len(non_eos_token_rows), "nonzero_loss_steps": len(nonzero_loss_steps), "failures": failures}, indent=2, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

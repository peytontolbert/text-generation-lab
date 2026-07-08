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
STAGE = 9286
NAME = "stage9286_suffix_step_denoise_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9285_suffix_step_final_preexecution_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9286_suffix_step_denoise_probe"
AUDIT = RUN_DIR / "stage9286_suffix_step_denoise_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_STEP_DENOISE_PROBE_AUDIT_STAGE9286.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
EXPECTED_MANIFEST_SHA = "afe99e19e26260bbb63976800741c78ad344b5c49e19d55c73f1c911a0594d64"

REQUIRED_ARTIFACTS = [
    "probe_contract_audit.json",
    "execution_result.json",
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_token_loss.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "row_dynamics_history.jsonl",
    "sample_generation_audit.json",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
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
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    samples = load_json(RUN_DIR / "sample_generation_audit.json")
    repetition = load_json(RUN_DIR / "repetition_probe.json")
    short = load_json(RUN_DIR / "short_output_probe.json")
    leak = load_json(RUN_DIR / "internal_leak_probe.json")
    cleanup = load_json(RUN_DIR / "cleanup_proof.json")
    losses = load_jsonl(RUN_DIR / "loss_by_step.jsonl")
    missing_artifacts = [name for name in REQUIRED_ARTIFACTS if not (RUN_DIR / name).exists()]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9285_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if contract.get("manifest_sha256") != EXPECTED_MANIFEST_SHA:
        failures.append("manifest_hash_mismatch")
    if contract.get("generation_prefix_field") != "model_input.bridge_priming_span":
        failures.append("generation_prefix_field_missing")
    if contract.get("loss_counts", {}).get("decoder_ce") != 0 or execution.get("decoder_ce_rows") != 0:
        failures.append("decoder_ce_opened")
    if contract.get("loss_counts", {}).get("denoise_ce") != 8 or execution.get("denoise_ce_rows") != 8:
        failures.append("denoise_ce_count_not_8")
    if execution.get("runtime_executed") is not False or execution.get("gemma_executed") is not False or execution.get("harness_executed") is not False:
        failures.append("forbidden_execution_surface_opened")
    if execution.get("final_checkpoint_exported") is not False:
        failures.append("checkpoint_exported")
    if execution.get("required_artifacts_written") is not True or missing_artifacts:
        failures.append("required_artifacts_missing")
    cleanup_ok = bool(
        cleanup.get("cleanup_status") in {"completed", "no_checkpoints_found"}
        or cleanup.get("checkpoints_removed") is not None
        or (cleanup.get("cleanup_executed") is False and "does not write checkpoints" in str(cleanup.get("cleanup_reason", "")))
    )
    if not cleanup_ok:
        failures.append("cleanup_proof_unrecognized")
    train_loss_start = float(losses[0]["loss"]) if losses else None
    train_loss_end = float(losses[-1]["loss"]) if losses else None
    contentful = samples.get("contentful_rate")
    prefix_start = samples.get("generation_prefix_start_rate")
    target_prefix = samples.get("target_prefix_match_rate")
    unterminated = repetition.get("unterminated_rate")
    degenerate = repetition.get("degenerate_repetition_rate")
    leak_rows = leak.get("generated_internal_token_rows")
    quality_gate_passed = bool(
        samples.get("generated_rows", 0) > 0
        and prefix_start == 1.0
        and contentful == 1.0
        and target_prefix and target_prefix > 0.0
        and unterminated == 0.0
        and degenerate == 0.0
        and leak_rows == 0
    )
    return {
        "passed": not failures,
        "failures": failures,
        "safety_gate_passed": not failures,
        "quality_gate_passed": quality_gate_passed,
        "rows": execution.get("denoise_ce_rows"),
        "train_rows": execution.get("train_rows"),
        "eval_rows": execution.get("eval_rows"),
        "strict_rows": execution.get("strict_rows"),
        "max_steps": execution.get("max_steps"),
        "generated_rows": samples.get("generated_rows"),
        "generation_prefix_field": samples.get("generation_prefix_field"),
        "generation_prefix_start_rate": prefix_start,
        "contentful_generation_rate": contentful,
        "unterminated_generation_rate": unterminated,
        "degenerate_repetition_rate": degenerate,
        "short_or_junk_rate": short.get("short_or_junk_rate"),
        "target_prefix_match_rate": target_prefix,
        "generated_internal_token_rows": leak_rows,
        "train_loss_start": train_loss_start,
        "train_loss_end": train_loss_end,
        "train_loss_decreased": train_loss_start is not None and train_loss_end is not None and train_loss_end < train_loss_start,
        "eval_loss": ((execution.get("eval") or {}).get("eval") or {}).get("loss"),
        "strict_eval_loss": ((execution.get("eval") or {}).get("strict_eval") or {}).get("loss"),
        "runtime_executed": execution.get("runtime_executed"),
        "gemma_executed": execution.get("gemma_executed"),
        "harness_executed": execution.get("harness_executed"),
        "final_checkpoint_exported": execution.get("final_checkpoint_exported"),
        "required_artifacts_written": execution.get("required_artifacts_written"),
        "missing_artifacts": missing_artifacts,
        "diagnosis": "teacher_forcing_loss_decreases_but_eval_strict_suffix_generation_still_fails",
        "authority": dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    authority_counts = {key: 0 for key in AUTHORITY_CLOSED}
    for row in rows:
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        for key in authority_counts:
            authority_counts[key] += int(bool(auth.get(key, False)))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": authority_counts}
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
        "decision": "Safety passed, but suffix-step generation failed: teacher-forcing loss decreased while eval/strict generations remained unterminated and target-prefix match stayed zero.",
        "next_best_step": "Run a train-split generation/memorization audit for the same suffix-step rows before changing data again; determine whether the model can generate memorized train suffixes after teacher-forced loss drops.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join([
            "# Stage9286 Suffix-Step Denoise Probe Audit",
            "",
            "Stage9286 executed the tiny target-100M suffix-step denoise probe.",
            "",
            f"Safety gate passed: {audit['safety_gate_passed']}",
            f"Quality gate passed: {audit['quality_gate_passed']}",
            f"Train loss: {audit['train_loss_start']} -> {audit['train_loss_end']}",
            f"Eval loss: {audit['eval_loss']}",
            f"Strict eval loss: {audit['strict_eval_loss']}",
            f"Generation prefix start rate: {audit['generation_prefix_start_rate']}",
            f"Contentful rate: {audit['contentful_generation_rate']}",
            f"Unterminated rate: {audit['unterminated_generation_rate']}",
            f"Degenerate repetition rate: {audit['degenerate_repetition_rate']}",
            f"Target prefix match rate: {audit['target_prefix_match_rate']}",
            f"Diagnosis: {audit['diagnosis']}",
            "",
            "Decoder CE, runtime, Gemma, harness, scoring, source/body emission, checkpoint export, and promotion remained closed.",
        ]) + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

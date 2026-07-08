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
STAGE = 9294
NAME = "stage9294_one_next_token_suffix_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9293_one_next_token_final_preexecution_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9294_one_next_token_suffix_probe"
AUDIT = RUN_DIR / "stage9294_one_next_token_suffix_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ONE_NEXT_TOKEN_SUFFIX_PROBE_AUDIT_STAGE9294.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
EXPECTED_MANIFEST_SHA = "f0c15145c5f4b49705e611bf47a293e3df98254fc9209332772e9b941a2cf04c"

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
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def _split_generation_summary(samples: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    by_split: dict[str, dict[str, int]] = {}
    for row in samples:
        split = str(row.get("split") or "unknown")
        bucket = by_split.setdefault(
            split,
            {
                "rows": 0,
                "target_prefix_match_rows": 0,
                "exact_match_rows": 0,
                "unterminated_rows": 0,
                "degenerate_repetition_rows": 0,
                "internal_token_leak_rows": 0,
            },
        )
        bucket["rows"] += 1
        bucket["target_prefix_match_rows"] += int(bool(row.get("target_prefix_match")))
        bucket["exact_match_rows"] += int(bool(row.get("exact_match")))
        bucket["unterminated_rows"] += int(not bool(row.get("stopped_on_eos")))
        bucket["degenerate_repetition_rows"] += int(bool(row.get("degenerate_repetition")))
        bucket["internal_token_leak_rows"] += int(bool(row.get("internal_token_leak")))
    return by_split


def audit_run() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    samples_card = load_json(RUN_DIR / "sample_generation_audit.json")
    repetition = load_json(RUN_DIR / "repetition_probe.json")
    short = load_json(RUN_DIR / "short_output_probe.json")
    leak = load_json(RUN_DIR / "internal_leak_probe.json")
    cleanup = load_json(RUN_DIR / "cleanup_proof.json")
    losses = load_jsonl(RUN_DIR / "loss_by_step.jsonl")
    samples = samples_card.get("samples") if isinstance(samples_card.get("samples"), list) else []
    missing_artifacts = [name for name in REQUIRED_ARTIFACTS if not (RUN_DIR / name).exists()]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9293_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if contract.get("manifest_sha256") != EXPECTED_MANIFEST_SHA:
        failures.append("manifest_hash_mismatch")
    if contract.get("generation_audit_splits") != "train,eval,strict_eval":
        failures.append("generation_audit_splits_not_train_eval_strict")
    if contract.get("generation_prefix_field") != "model_input.bridge_priming_span":
        failures.append("generation_prefix_field_missing")
    if contract.get("loss_counts", {}).get("decoder_ce") != 0 or execution.get("decoder_ce_rows") != 0:
        failures.append("decoder_ce_opened")
    if contract.get("loss_counts", {}).get("denoise_ce") != 6 or execution.get("denoise_ce_rows") != 6:
        failures.append("denoise_ce_count_not_6")
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
    split_generation_summary = _split_generation_summary(samples)
    train = split_generation_summary.get("train", {"rows": 0, "target_prefix_match_rows": 0, "unterminated_rows": 0})
    train_one_token_generation_passed = bool(
        train.get("rows") == 4
        and train.get("target_prefix_match_rows") == 4
        and train.get("unterminated_rows") == 0
    )
    safety_gate_passed = not failures
    quality_gate_passed = bool(
        safety_gate_passed
        and samples_card.get("generated_rows") == 6
        and samples_card.get("generation_prefix_start_rate") == 1.0
        and samples_card.get("target_prefix_match_rate") == 1.0
        and repetition.get("unterminated_rate") == 0.0
        and repetition.get("degenerate_repetition_rate") == 0.0
        and leak.get("generated_internal_token_rows") == 0
    )
    return {
        "passed": safety_gate_passed,
        "failures": failures,
        "safety_gate_passed": safety_gate_passed,
        "quality_gate_passed": quality_gate_passed,
        "train_one_token_generation_passed": train_one_token_generation_passed,
        "rows": execution.get("denoise_ce_rows"),
        "train_rows": execution.get("train_rows"),
        "eval_rows": execution.get("eval_rows"),
        "strict_rows": execution.get("strict_rows"),
        "max_steps": execution.get("max_steps"),
        "generated_rows": samples_card.get("generated_rows"),
        "generation_audit_splits": contract.get("generation_audit_splits"),
        "generation_prefix_field": samples_card.get("generation_prefix_field"),
        "generation_prefix_start_rate": samples_card.get("generation_prefix_start_rate"),
        "contentful_generation_rate": samples_card.get("contentful_rate"),
        "target_prefix_match_rate": samples_card.get("target_prefix_match_rate"),
        "exact_match_rows": samples_card.get("exact_match_rows"),
        "unterminated_generation_rate": repetition.get("unterminated_rate"),
        "degenerate_repetition_rate": repetition.get("degenerate_repetition_rate"),
        "short_or_junk_rate": short.get("short_or_junk_rate"),
        "generated_internal_token_rows": leak.get("generated_internal_token_rows"),
        "train_loss_start": train_loss_start,
        "train_loss_end": train_loss_end,
        "train_loss_decreased": train_loss_start is not None and train_loss_end is not None and train_loss_end < train_loss_start,
        "eval_loss": ((execution.get("eval") or {}).get("eval") or {}).get("loss"),
        "strict_eval_loss": ((execution.get("eval") or {}).get("strict_eval") or {}).get("loss"),
        "split_generation_summary": split_generation_summary,
        "runtime_executed": execution.get("runtime_executed"),
        "gemma_executed": execution.get("gemma_executed"),
        "harness_executed": execution.get("harness_executed"),
        "final_checkpoint_exported": execution.get("final_checkpoint_exported"),
        "required_artifacts_written": execution.get("required_artifacts_written"),
        "missing_artifacts": missing_artifacts,
        "diagnosis": "one_next_token_free_run_suffix_generation_fails_despite_teacher_forced_loss_drop",
        "authority": dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
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
        "decision": "Safety passed, but one-next-token suffix generation failed: teacher-forced denoise loss dropped while every train/eval/strict generation missed the first suffix token and stayed unterminated.",
        "next_best_step": "Add a boundary next-token logit/rank audit at the bridge prefix, then patch generation or training if the correct suffix token is not top-ranked after teacher-forced optimization.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join([
            "# Stage9294 One-Next-Token Suffix Probe Audit",
            "",
            "Stage9294 executed the tiny target-100M one-next-token suffix denoise probe.",
            "",
            f"Safety gate passed: {audit['safety_gate_passed']}",
            f"Quality gate passed: {audit['quality_gate_passed']}",
            f"Train one-token generation passed: {audit['train_one_token_generation_passed']}",
            f"Train loss: {audit['train_loss_start']} -> {audit['train_loss_end']}",
            f"Eval loss: {audit['eval_loss']}",
            f"Strict eval loss: {audit['strict_eval_loss']}",
            f"Generation prefix start rate: {audit['generation_prefix_start_rate']}",
            f"Target prefix match rate: {audit['target_prefix_match_rate']}",
            f"Unterminated rate: {audit['unterminated_generation_rate']}",
            f"Degenerate repetition rate: {audit['degenerate_repetition_rate']}",
            f"Internal token leak rows: {audit['generated_internal_token_rows']}",
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

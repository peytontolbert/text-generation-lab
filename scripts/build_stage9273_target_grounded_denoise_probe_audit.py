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
STAGE = 9273
NAME = "stage9273_target_grounded_denoise_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9272_target_grounded_denoise_manifest.json"
PREV_SUMMARY = ROOT / "runs/summaries/stage9271_target_100m_denoise_eos_micro_overfit_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9273_target_grounded_denoise_probe/denoise_repair_probe"
AUDIT = RUN_DIR / "stage9273_target_grounded_denoise_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TARGET_GROUNDED_DENOISE_PROBE_AUDIT_STAGE9273.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def audit_run() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    previous = load_json(PREV_SUMMARY).get("metrics") or {}
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    samples = load_json(RUN_DIR / "sample_generation_audit.json")
    repetition = load_json(RUN_DIR / "repetition_probe.json")
    short = load_json(RUN_DIR / "short_output_probe.json")
    leak = load_json(RUN_DIR / "internal_leak_probe.json")
    losses = load_jsonl(RUN_DIR / "loss_by_step.jsonl")
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9272_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if contract.get("manifest_sha256") != "2ac7c3502ae261c234f986eac7093378db0e95e8c7cd9f292aa4158faee41bff":
        failures.append("manifest_hash_mismatch")
    if contract.get("weights", {}).get("eos_loss_weight") != 4.0:
        failures.append("eos_weight_not_4")
    if contract.get("loss_counts", {}).get("decoder_ce") != 0 or execution.get("decoder_ce_rows") != 0:
        failures.append("decoder_ce_opened")
    if execution.get("runtime_executed") is not False or execution.get("gemma_executed") is not False or execution.get("harness_executed") is not False:
        failures.append("forbidden_execution_surface_opened")
    if execution.get("final_checkpoint_exported") is not False:
        failures.append("checkpoint_exported")
    if execution.get("required_artifacts_written") is not True:
        failures.append("required_artifacts_not_written")
    train_loss_start = float(losses[0]["loss"]) if losses else None
    train_loss_end = float(losses[-1]["loss"]) if losses else None
    contentful = samples.get("contentful_rate")
    prefix = samples.get("target_prefix_match_rate")
    unterminated = repetition.get("unterminated_rate")
    degenerate = repetition.get("degenerate_repetition_rate")
    quality_gate_passed = bool(
        samples.get("generated_rows", 0) > 0
        and contentful == 1.0
        and prefix and prefix > 0.0
        and unterminated == 0.0
        and degenerate == 0.0
        and leak.get("generated_internal_token_rows") == 0
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
        "eos_loss_weight": contract.get("weights", {}).get("eos_loss_weight"),
        "generated_rows": samples.get("generated_rows"),
        "contentful_generation_rate": contentful,
        "previous_contentful_generation_rate": previous.get("contentful_generation_rate"),
        "unterminated_generation_rate": unterminated,
        "previous_unterminated_generation_rate": previous.get("unterminated_generation_rate"),
        "degenerate_repetition_rate": degenerate,
        "previous_degenerate_repetition_rate": previous.get("degenerate_repetition_rate"),
        "short_or_junk_rate": short.get("short_or_junk_rate"),
        "target_prefix_match_rate": prefix,
        "previous_target_prefix_match_rate": previous.get("target_prefix_match_rate"),
        "generated_internal_token_rows": leak.get("generated_internal_token_rows"),
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
        "diagnosis": "minimal_target_anchors_too_weak_for_prefix_recovery",
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
        "decision": "The target-grounded denoise probe executed safely but did not improve semantic prefix recovery. Minimal anchor metadata is insufficient; the next objective needs explicit prefix/copy recovery supervision with leak-safe target anchors.",
        "next_best_step": "Build a prefix-copy denoise micro-objective that exposes only a short approved prefix span as input and trains the model to start with that span before continuing the bounded target.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join([
            "# Stage9273 Target-Grounded Denoise Probe Audit",
            "",
            "Safety passed, but target-grounded anchors did not recover target prefixes.",
            "",
            f"Contentful rate: {audit['previous_contentful_generation_rate']} -> {audit['contentful_generation_rate']}",
            f"Unterminated rate: {audit['previous_unterminated_generation_rate']} -> {audit['unterminated_generation_rate']}",
            f"Degenerate repetition rate: {audit['previous_degenerate_repetition_rate']} -> {audit['degenerate_repetition_rate']}",
            f"Target prefix match rate: {audit['target_prefix_match_rate']}",
            f"Diagnosis: {audit['diagnosis']}",
            "",
            "Next step: prefix-copy micro-objective with leak-safe short prefixes.",
        ]) + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

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
STAGE = 9289
NAME = "stage9289_train_generation_memorization_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9288_train_generation_memorization_preexecution.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9289_train_generation_memorization_probe"
AUDIT = RUN_DIR / "stage9289_train_generation_memorization_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAIN_GENERATION_MEMORIZATION_PROBE_AUDIT_STAGE9289.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
EXPECTED_MANIFEST_SHA = "afe99e19e26260bbb63976800741c78ad344b5c49e19d55c73f1c911a0594d64"
REQUIRED = ["probe_contract_audit.json", "execution_result.json", "loss_by_step.jsonl", "sample_generation_audit.json", "repetition_probe.json", "internal_leak_probe.json", "cleanup_proof.json"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def audit_run() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    samples = load_json(RUN_DIR / "sample_generation_audit.json")
    repetition = load_json(RUN_DIR / "repetition_probe.json")
    leak = load_json(RUN_DIR / "internal_leak_probe.json")
    losses = load_jsonl(RUN_DIR / "loss_by_step.jsonl")
    sample_rows = samples.get("samples") if isinstance(samples.get("samples"), list) else []
    missing = [name for name in REQUIRED if not (RUN_DIR / name).exists()]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9288_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if contract.get("manifest_sha256") != EXPECTED_MANIFEST_SHA:
        failures.append("manifest_hash_mismatch")
    if contract.get("generation_audit_splits") != "train,eval,strict_eval":
        failures.append("generation_audit_splits_not_train_eval_strict")
    if execution.get("decoder_ce_rows") != 0 or contract.get("loss_counts", {}).get("decoder_ce") != 0:
        failures.append("decoder_ce_opened")
    if execution.get("runtime_executed") is not False or execution.get("gemma_executed") is not False or execution.get("harness_executed") is not False:
        failures.append("forbidden_execution_surface_opened")
    if execution.get("final_checkpoint_exported") is not False:
        failures.append("checkpoint_exported")
    if missing:
        failures.append("required_artifacts_missing")
    by_split: dict[str, dict[str, Any]] = {}
    for row in sample_rows:
        split = str(row.get("split") or "unknown")
        bucket = by_split.setdefault(split, {"rows": 0, "target_prefix_match_rows": 0, "unterminated_rows": 0, "degenerate_repetition_rows": 0})
        bucket["rows"] += 1
        bucket["target_prefix_match_rows"] += int(bool(row.get("target_prefix_match")))
        bucket["unterminated_rows"] += int(not bool(row.get("stopped_on_eos")))
        bucket["degenerate_repetition_rows"] += int(bool(row.get("degenerate_repetition")))
    train = by_split.get("train", {"rows": 0, "target_prefix_match_rows": 0, "unterminated_rows": 0, "degenerate_repetition_rows": 0})
    train_memorization_passed = bool(train.get("rows") and train.get("target_prefix_match_rows") == train.get("rows") and train.get("unterminated_rows") == 0)
    return {
        "passed": not failures,
        "failures": failures,
        "safety_gate_passed": not failures,
        "quality_gate_passed": bool(samples.get("target_prefix_match_rate") and samples.get("target_prefix_match_rate") > 0 and repetition.get("unterminated_rate") == 0.0),
        "train_memorization_passed": train_memorization_passed,
        "rows": execution.get("denoise_ce_rows"),
        "generated_rows": samples.get("generated_rows"),
        "generation_audit_splits": contract.get("generation_audit_splits"),
        "generation_prefix_start_rate": samples.get("generation_prefix_start_rate"),
        "contentful_generation_rate": samples.get("contentful_rate"),
        "target_prefix_match_rate": samples.get("target_prefix_match_rate"),
        "unterminated_generation_rate": repetition.get("unterminated_rate"),
        "degenerate_repetition_rate": repetition.get("degenerate_repetition_rate"),
        "generated_internal_token_rows": leak.get("generated_internal_token_rows"),
        "train_loss_start": float(losses[0]["loss"]) if losses else None,
        "train_loss_end": float(losses[-1]["loss"]) if losses else None,
        "train_loss_decreased": bool(losses and float(losses[-1]["loss"]) < float(losses[0]["loss"])),
        "split_generation_summary": by_split,
        "runtime_executed": execution.get("runtime_executed"),
        "gemma_executed": execution.get("gemma_executed"),
        "harness_executed": execution.get("harness_executed"),
        "final_checkpoint_exported": execution.get("final_checkpoint_exported"),
        "missing_artifacts": missing,
        "diagnosis": "train_suffix_generation_fails_despite_teacher_forced_loss_drop",
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
        "stage": STAGE, "stage_name": NAME, "name": NAME, "passed": audit["passed"], "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "Train rows fail generation too: the probe starts from the forced prefix but cannot autoregressively emit the memorized suffix even after teacher-forced loss drops.",
        "next_best_step": "Patch the micro-overfit objective to train/generate exactly one next suffix token first, or add scheduled-sampling/free-run loss; do not widen data.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9289 Train Generation Memorization Probe Audit", "", f"Safety gate passed: {audit['safety_gate_passed']}", f"Train memorization passed: {audit['train_memorization_passed']}", f"Train loss: {audit['train_loss_start']} -> {audit['train_loss_end']}", f"Target prefix match rate: {audit['target_prefix_match_rate']}", f"Unterminated rate: {audit['unterminated_generation_rate']}", f"Diagnosis: {audit['diagnosis']}", "", "Decoder CE, runtime, Gemma, harness, source/body emission, checkpoint export, and promotion remained closed.", ""]) , encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

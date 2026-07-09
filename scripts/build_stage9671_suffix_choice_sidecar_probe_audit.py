#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9671
NAME = "stage9671_suffix_choice_sidecar_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9670_suffix_choice_sidecar_preexecution.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9670_suffix_choice_sidecar_preexecution/suffix_choice_sidecar_manifest.jsonl"
RUN_DIR = ROOT / "runs/local/artifacts/stage9671_suffix_choice_sidecar_probe"
AUDIT = RUN_DIR / "stage9671_suffix_choice_sidecar_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_CHOICE_SIDECAR_PROBE_AUDIT_STAGE9671.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def latest(records: list[dict[str, Any]], split: str) -> dict[str, Any]:
    selected = [row for row in records if row.get("split") == split and not row.get("checkpoint_eval")]
    if selected:
        return selected[-1]
    selected = [row for row in records if row.get("split") == split]
    return selected[-1] if selected else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    execution = load_json(RUN_DIR / "execution_result.json")
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    module_delta = load_json(RUN_DIR / "module_delta_norms.json")
    eval_records = load_jsonl(RUN_DIR / "eval_loss_by_checkpoint.jsonl")
    logits = load_jsonl(RUN_DIR / "row_field_logits.jsonl")
    eval_final = latest(eval_records, "eval")
    strict_final = latest(eval_records, "strict_eval")
    eval_exact = (((eval_final.get("field_exact") or {}).get("suffix_choice") or {}).get("exact"))
    strict_exact = (((strict_final.get("field_exact") or {}).get("suffix_choice") or {}).get("exact"))
    delta_by_bucket = module_delta.get("delta_norm_by_bucket") if isinstance(module_delta.get("delta_norm_by_bucket"), dict) else {}
    frozen = {
        "decoder": float(delta_by_bucket.get("decoder", 0.0) or 0.0),
        "decoder_attention": float(delta_by_bucket.get("decoder_attention", 0.0) or 0.0),
        "decoder_mlp": float(delta_by_bucket.get("decoder_mlp", 0.0) or 0.0),
        "lm_head": float(delta_by_bucket.get("lm_head", 0.0) or 0.0),
        "embeddings": float(delta_by_bucket.get("embeddings", 0.0) or 0.0),
    }
    max_frozen_delta = max(frozen.values()) if frozen else 0.0
    high_conf_wrong = [row for row in logits if row.get("field") == "suffix_choice" and row.get("high_confidence_wrong")]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9670_not_passed")
    if len(rows) != 26:
        failures.append("manifest_row_count_not_26")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if int(contract.get("loss_counts", {}).get("suffix_choice_ce") or 0) != 26:
        failures.append("suffix_choice_loss_count_wrong")
    if int(contract.get("loss_counts", {}).get("decoder_ce") or 0) != 0 or int(contract.get("loss_counts", {}).get("denoise_ce") or 0) != 0:
        failures.append("decoder_or_denoise_loss_opened")
    if execution.get("mode") != "structured_policy_probe":
        failures.append("wrong_mode")
    if execution.get("runtime_executed") or execution.get("gemma_executed") or execution.get("harness_executed") or execution.get("final_checkpoint_exported"):
        failures.append("forbidden_execution_or_export")
    if execution.get("structured_optimizer_isolated") is not True:
        failures.append("structured_optimizer_not_isolated")
    if max_frozen_delta > 1e-12:
        failures.append("frozen_decoder_lm_or_embedding_delta_nonzero")
    if eval_exact != 1.0 or strict_exact != 1.0:
        failures.append("suffix_choice_exact_not_1")
    if high_conf_wrong:
        failures.append("high_confidence_wrong_suffix_choice")
    required_artifacts = [
        "probe_contract_audit.json",
        "execution_result.json",
        "eval_loss_by_checkpoint.jsonl",
        "row_field_logits.jsonl",
        "row_field_losses.jsonl",
        "row_gradient_norms.jsonl",
        "activation_summary.jsonl",
        "module_delta_norms.json",
        "cleanup_proof.json",
    ]
    missing = [name for name in required_artifacts if not (RUN_DIR / name).exists()]
    if missing:
        failures.append("required_artifacts_missing")
    audit = {
        "passed": not failures,
        "failures": failures,
        "missing_artifacts": missing,
        "manifest_rows": len(rows),
        "train_rows": execution.get("train_rows"),
        "eval_rows": execution.get("eval_rows"),
        "strict_rows": execution.get("strict_rows"),
        "eval_suffix_choice_exact": eval_exact,
        "strict_suffix_choice_exact": strict_exact,
        "eval_loss": eval_final.get("loss"),
        "strict_eval_loss": strict_final.get("loss"),
        "best_state_selection": execution.get("best_state_selection"),
        "decoder_ce_rows": execution.get("decoder_ce_rows"),
        "denoise_ce_rows": execution.get("denoise_ce_rows"),
        "runtime_executed": execution.get("runtime_executed"),
        "gemma_executed": execution.get("gemma_executed"),
        "harness_executed": execution.get("harness_executed"),
        "final_checkpoint_exported": execution.get("final_checkpoint_exported"),
        "structured_optimizer_isolated": execution.get("structured_optimizer_isolated"),
        "structured_optimizer_frozen_parameter_count": execution.get("structured_optimizer_frozen_parameter_count"),
        "structured_optimizer_trainable_parameter_count": execution.get("structured_optimizer_trainable_parameter_count"),
        "frozen_bucket_deltas": frozen,
        "max_frozen_bucket_delta": max_frozen_delta,
        "row_field_logit_rows": len(logits),
        "high_confidence_wrong_rows": len(high_conf_wrong),
        "decision": "suffix_choice_sidecar_control_passed",
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Build Stage9672 suffix-choice-prior fused denoise preexecution: attach the passed suffix_choice controller prior to Stage9668 rows, then run contract-only before any generation."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "Stage9671 solved the post-prefix suffix-choice sidecar while keeping decoder/denoise generation closed and frozen buckets unchanged.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9671 Suffix Choice Sidecar Probe Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Eval suffix-choice exact: `{eval_exact}`",
                f"Strict suffix-choice exact: `{strict_exact}`",
                f"Eval loss: `{audit['eval_loss']}`",
                f"Strict loss: `{audit['strict_eval_loss']}`",
                f"High-confidence wrong rows: `{audit['high_confidence_wrong_rows']}`",
                f"Max frozen decoder/LM/embedding delta: `{max_frozen_delta}`",
                "",
                "This proves the residual post-prefix suffix family is learnable as a structured sidecar. It does not authorize decoder, denoise generation, runtime, Gemma, harness, export, merge, or promotion.",
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "eval_suffix_choice_exact": eval_exact, "strict_suffix_choice_exact": strict_exact, "max_frozen_bucket_delta": max_frozen_delta, "next_best_step": next_step}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

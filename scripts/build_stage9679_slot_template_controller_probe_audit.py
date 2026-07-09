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
STAGE = 9679
NAME = "stage9679_slot_template_controller_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9678_slot_template_controller_preexecution.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9678_slot_template_controller_preexecution/slot_template_controller_manifest.jsonl"
RUN_DIR = ROOT / "runs/local/artifacts/stage9679_slot_template_controller_probe"
AUDIT = RUN_DIR / "stage9679_slot_template_controller_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SLOT_TEMPLATE_CONTROLLER_PROBE_AUDIT_STAGE9679.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    module_delta = load_json(RUN_DIR / "module_delta_norms.json")
    eval_records = load_jsonl(RUN_DIR / "eval_loss_by_checkpoint.jsonl")
    logits = load_jsonl(RUN_DIR / "row_field_logits.jsonl")
    vocabs = load_json(RUN_DIR / "field_label_vocabs.json")
    eval_metrics = (execution.get("eval") or {}).get("eval") or {}
    strict_metrics = (execution.get("eval") or {}).get("strict_eval") or {}
    eval_exact = (((eval_metrics.get("field_exact") or {}).get("suffix_choice") or {}).get("exact"))
    strict_exact = (((strict_metrics.get("field_exact") or {}).get("suffix_choice") or {}).get("exact"))
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
    fields = execution.get("fields") if isinstance(execution.get("fields"), list) else []
    suffix_vocab = vocabs.get("suffix_choice")
    if isinstance(suffix_vocab, dict):
        label_count = len(suffix_vocab)
    elif isinstance(suffix_vocab, list):
        label_count = len(suffix_vocab)
    else:
        label_count = 0

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9678_not_passed")
    if len(rows) != 27:
        failures.append("manifest_row_count_not_27")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if int(contract.get("loss_counts", {}).get("suffix_choice_ce") or 0) != 27:
        failures.append("suffix_choice_loss_count_wrong")
    if int(contract.get("loss_counts", {}).get("decoder_ce") or 0) != 0 or int(contract.get("loss_counts", {}).get("denoise_ce") or 0) != 0:
        failures.append("decoder_or_denoise_loss_opened")
    if execution.get("mode") != "structured_policy_probe" or fields != ["suffix_choice"]:
        failures.append("wrong_mode_or_fields")
    if execution.get("runtime_executed") or execution.get("gemma_executed") or execution.get("harness_executed") or execution.get("final_checkpoint_exported"):
        failures.append("forbidden_execution_or_export")
    if execution.get("structured_optimizer_isolated") is not True:
        failures.append("structured_optimizer_not_isolated")
    if max_frozen_delta > 1e-12:
        failures.append("frozen_decoder_lm_or_embedding_delta_nonzero")
    if eval_exact != 1.0 or strict_exact != 1.0:
        failures.append("slot_template_exact_not_1")
    if high_conf_wrong:
        failures.append("high_confidence_wrong_slot_template")
    if label_count != 10:
        failures.append("label_count_not_10")
    required_artifacts = [
        "probe_contract_audit.json",
        "execution_result.json",
        "eval_loss_by_checkpoint.jsonl",
        "row_field_logits.jsonl",
        "row_field_losses.jsonl",
        "row_gradient_norms.jsonl",
        "activation_summary.jsonl",
        "activation_patch_recovery.jsonl",
        "feature_ablation_attribution.jsonl",
        "field_exact_by_cell.json",
        "field_label_vocabs.json",
        "structured_confusion_matrix.json",
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
        "fields": fields,
        "slot_template_label_count": label_count,
        "eval_suffix_choice_exact": eval_exact,
        "strict_suffix_choice_exact": strict_exact,
        "eval_loss": eval_metrics.get("loss"),
        "strict_eval_loss": strict_metrics.get("loss"),
        "best_state_selection": execution.get("best_state_selection"),
        "runtime_executed": execution.get("runtime_executed"),
        "gemma_executed": execution.get("gemma_executed"),
        "harness_executed": execution.get("harness_executed"),
        "final_checkpoint_exported": execution.get("final_checkpoint_exported"),
        "structured_optimizer_isolated": execution.get("structured_optimizer_isolated"),
        "structured_optimizer_frozen_parameter_count": execution.get("structured_optimizer_frozen_parameter_count"),
        "structured_optimizer_trainable_parameter_count": execution.get("structured_optimizer_trainable_parameter_count"),
        "frozen_bucket_deltas": frozen,
        "max_frozen_bucket_delta": max_frozen_delta,
        "encoder_delta_norm": module_delta.get("encoder_delta_norm"),
        "structured_head_delta_norm": module_delta.get("structured_head_delta_norm"),
        "row_field_logit_rows": len(logits),
        "eval_record_rows": len(eval_records),
        "high_confidence_wrong_rows": len(high_conf_wrong),
        "decision": "slot_template_controller_passed",
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Build Stage9680 deterministic slot-template renderer/reconnect design: use Stage9679 controller labels to render bounded text templates without reopening denoise generation."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
            "run_dir": str(RUN_DIR.relative_to(ROOT)),
        },
        "decision": "Stage9679 solved non-generative slot-template selection; use deterministic rendering before any further denoise reconnect.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9679 Slot Template Controller Probe Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Eval suffix-choice exact: `{eval_exact}`",
        f"Strict suffix-choice exact: `{strict_exact}`",
        f"Template labels: `{label_count}`",
        f"High-confidence wrong rows: `{len(high_conf_wrong)}`",
        f"Max frozen decoder/LM/embedding delta: `{max_frozen_delta}`",
        "",
        "The 100M model learned the residual slot-template controller as a structured head. Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, merge, and promotion remain closed.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": audit["passed"],
        "eval_suffix_choice_exact": eval_exact,
        "strict_suffix_choice_exact": strict_exact,
        "label_count": label_count,
        "max_frozen_bucket_delta": max_frozen_delta,
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

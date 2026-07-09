#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9704
NAME = "stage9704_symbol_binding_rebalanced_target100m_execution_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9703_symbol_binding_rebalanced_target100m_contract_preflight_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9704_symbol_binding_rebalanced_target100m_execution/symbol_binding_probe"
MANIFEST = ROOT / "runs/local/artifacts/stage9700_symbol_binding_repair_compiler/symbol_binding_tiny_rebalanced.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "symbol_binding_rebalanced_target100m_execution_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SYMBOL_BINDING_REBALANCED_TARGET100M_EXECUTION_STAGE9704.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def label(row: dict[str, Any]) -> str:
    return str((row.get("clean_state") or {}).get("binding_action"))


def current_scheduler_exposure(rows: list[dict[str, Any]], *, max_steps: int, batch_size: int) -> dict[str, Any]:
    train_rows = [row for row in rows if row.get("split") == "train"]
    used = []
    for step in range(1, max_steps + 1):
        for offset in range(batch_size):
            used.append(train_rows[(step * batch_size + offset) % len(train_rows)])
    all_counts = Counter(label(row) for row in train_rows)
    used_counts = Counter(label(row) for row in used)
    return {
        "train_rows": len(train_rows),
        "max_steps": max_steps,
        "batch_size": batch_size,
        "unique_train_rows_seen": len({row.get("row_id") for row in used}),
        "train_label_counts": dict(all_counts),
        "used_label_counts": dict(used_counts),
        "missing_train_labels_in_used_batches": sorted(set(all_counts) - set(used_counts)),
        "underexposed_labels": sorted(label for label, total in all_counts.items() if used_counts.get(label, 0) < max(1, total // 2)),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
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
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    result = load_json(RUN_DIR / "execution_result.json")
    confusion = load_json(RUN_DIR / "structured_confusion_matrix.json")
    deltas = load_json(RUN_DIR / "module_delta_norms.json")
    ablation_rows = load_jsonl(RUN_DIR / "feature_ablation_attribution.jsonl")
    manifest_rows = load_jsonl(MANIFEST)
    exposure = current_scheduler_exposure(manifest_rows, max_steps=8, batch_size=2)
    modes = sorted({item.get("ablation_mode") for row in ablation_rows for item in row.get("feature_attribution", [])})
    eval_exact = (((result.get("eval") or {}).get("eval") or {}).get("field_exact") or {}).get("symbol_binding", {}).get("exact")
    strict_exact = (((result.get("eval") or {}).get("strict_eval") or {}).get("field_exact") or {}).get("symbol_binding", {}).get("exact")
    buckets = deltas.get("delta_norm_by_bucket") or {}
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9703_not_passed")
    if result.get("required_artifacts_written") is not True:
        failures.append("required_artifacts_not_written")
    if (result.get("implementation") or {}).get("estimated_parameter_count") != 102703145:
        failures.append("unexpected_parameter_count")
    if result.get("native_feature_ablation_audit_required") is not True or result.get("native_feature_ablation_rows") != 32:
        failures.append("native_ablation_missing_or_wrong_count")
    if modes != ["native_grouped_mask_rerun"]:
        failures.append(f"unexpected_ablation_modes:{modes}")
    for key in ["runtime_executed", "gemma_executed", "harness_executed", "final_checkpoint_exported"]:
        if result.get(key):
            failures.append(f"closed_boundary_opened:{key}")
    for bucket in ["decoder", "decoder_attention", "decoder_mlp", "embeddings", "lm_head"]:
        if float(buckets.get(bucket, 0.0) or 0.0) != 0.0:
            failures.append(f"frozen_bucket_moved:{bucket}")
    quality_passed = bool(eval_exact and strict_exact and float(eval_exact) >= 0.85 and float(strict_exact) >= 0.85)
    collapse = (confusion.get("symbol_binding") or {})
    prediction_collapse_label = "BIND_CALL_TO_SYMBOL" if all(set(preds) == {"BIND_CALL_TO_SYMBOL"} for preds in collapse.values()) else None
    next_step = "Patch Stage9705 structured sampler/exposure: start at step-1, cycle all train rows, and/or add label-balanced batches before rerunning target-100M."
    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": quality_passed,
        "promotion_ready": False,
        "failures": failures,
        "source_stage9703_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "run_dir": str(RUN_DIR.relative_to(ROOT)),
        "metrics": {
            "estimated_parameter_count": (result.get("implementation") or {}).get("estimated_parameter_count"),
            "eval_symbol_binding_exact": eval_exact,
            "strict_symbol_binding_exact": strict_exact,
            "prediction_collapse_label": prediction_collapse_label,
            "native_ablation_rows": result.get("native_feature_ablation_rows"),
            "ablation_modes": modes,
            "decoder_delta_norm": deltas.get("decoder_delta_norm"),
        },
        "scheduler_exposure": exposure,
        "confusion": confusion,
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": quality_passed,
        "promotion_ready": False,
        "created_at_unix": int(time.time()),
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "metrics": audit["metrics"],
        "scheduler_exposure": exposure,
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9704 Symbol-Binding Rebalanced Target-100M Execution",
        "",
        "Stage9704 executed the repaired source-backed symbol-binding probe on the recovered target-100M transformer with native grouped ablations enabled.",
        "",
        "## Result",
        "",
        f"- Execution boundary passed: `{not failures}`",
        f"- Quality passed: `{quality_passed}`",
        f"- Eval exact: `{eval_exact}`",
        f"- Strict exact: `{strict_exact}`",
        f"- Prediction collapse label: `{prediction_collapse_label}`",
        f"- Missing train labels in used batches: `{exposure['missing_train_labels_in_used_batches']}`",
        "",
        "The run remained safe, but the 8-step scheduler underexposed train labels and never trained on `RETRIEVE_MORE`. Fix the sampler before another target-100M run.",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

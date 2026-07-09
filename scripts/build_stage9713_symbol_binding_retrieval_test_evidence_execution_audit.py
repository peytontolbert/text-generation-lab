#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9713
NAME = "stage9713_symbol_binding_retrieval_test_evidence_execution_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9712_symbol_binding_retrieval_test_evidence_contract_preflight_audit.json"
RUN = ROOT / "runs/local/artifacts/stage9713_symbol_binding_retrieval_test_evidence_target100m_execution/symbol_binding_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "symbol_binding_retrieval_test_evidence_execution_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SYMBOL_BINDING_RETRIEVAL_TEST_EVIDENCE_EXECUTION_STAGE9713.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def confusion_pairs(confusion: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for matrix in confusion.values():
        if isinstance(matrix, dict):
            for target, preds in matrix.items():
                if isinstance(preds, dict):
                    for pred, count in preds.items():
                        out[f"{target}->{pred}"] = int(count)
    return dict(sorted(out.items()))


def per_label(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("target"))].append(row)
    out: dict[str, Any] = {}
    for target, group in sorted(grouped.items()):
        out[target] = {
            "rows": len(group),
            "exact": round(sum(1 for row in group if row.get("correct")) / len(group), 6),
            "pred_counts": dict(Counter(str(row.get("pred")) for row in group)),
        }
    return out


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
    result = load_json(RUN / "execution_result.json")
    confusion = load_json(RUN / "structured_confusion_matrix.json")
    deltas = load_json(RUN / "module_delta_norms.json")
    logits = load_jsonl(RUN / "row_field_logits.jsonl")
    eval_exact = result.get("eval", {}).get("eval", {}).get("field_exact", {}).get("symbol_binding", {}).get("exact")
    strict_exact = result.get("eval", {}).get("strict_eval", {}).get("field_exact", {}).get("symbol_binding", {}).get("exact")
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9712_not_passed")
    if result.get("required_artifacts_written") is not True:
        failures.append("required_artifacts_missing")
    if result.get("structured_batch_sampler") != "label_balanced_by_primary_field":
        failures.append("sampler_not_label_balanced")
    if result.get("native_feature_ablation_rows") != 44:
        failures.append(f"native_ablation_rows_not_44:{result.get('native_feature_ablation_rows')}")
    for key in ["runtime_executed", "gemma_executed", "harness_executed", "final_checkpoint_exported"]:
        if result.get(key):
            failures.append(f"closed_boundary_opened:{key}")
    buckets = deltas.get("delta_norm_by_bucket") or {}
    for bucket in ["decoder", "decoder_attention", "decoder_mlp", "embeddings", "lm_head"]:
        if float(buckets.get(bucket, 0.0) or 0.0) != 0.0:
            failures.append(f"frozen_bucket_moved:{bucket}")
    label_stats = per_label(logits)
    quality = bool(eval_exact and strict_exact and eval_exact >= 0.85 and strict_exact >= 0.85)
    next_step = (
        "Build Stage9714 isolated binary/ternary objectives for test coverage binding and retrieve-more gating; mixed five-way symbol binding still hides those two transitions."
    )
    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": quality,
        "promotion_ready": False,
        "failures": failures,
        "source_stage9712_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "run_dir": str(RUN.relative_to(ROOT)),
        "metrics": {
            "eval_symbol_binding_exact": eval_exact,
            "strict_symbol_binding_exact": strict_exact,
            "estimated_parameter_count": result.get("implementation", {}).get("estimated_parameter_count"),
            "native_ablation_rows": result.get("native_feature_ablation_rows"),
            "structured_batch_sampler": result.get("structured_batch_sampler"),
            "decoder_delta_norm": deltas.get("decoder_delta_norm"),
        },
        "confusion_pairs": confusion_pairs(confusion),
        "per_label": label_stats,
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": quality,
        "promotion_ready": False,
        "created_at_unix": int(time.time()),
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "run_dir": str(RUN.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "metrics": audit["metrics"],
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9713 Symbol-Binding Retrieval/Test Evidence Execution",
                "",
                f"- Execution boundary passed: `{not failures}`",
                f"- Quality passed: `{quality}`",
                f"- Eval exact: `{eval_exact}`",
                f"- Strict exact: `{strict_exact}`",
                f"- Decoder delta norm: `{deltas.get('decoder_delta_norm')}`",
                "",
                "## Diagnosis",
                "",
                "- ABSTAIN_UNBOUND, BIND_IMPORT_TO_MODULE, and BIND_CALL_TO_SYMBOL are now mostly learned.",
                "- BIND_TEST_TO_SYMBOL remains 0 exact and collapses to ABSTAIN_UNBOUND.",
                "- RETRIEVE_MORE remains 0 exact and splits between ABSTAIN_UNBOUND and BIND_CALL_TO_SYMBOL.",
                "",
                "## Next",
                "",
                next_step,
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

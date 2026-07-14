#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _write_bounded_choice_eval_audit

ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11141
NAME = "stage11141_evidence_item_conditioned_gated_postrun_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "evidence_item_conditioned_gated_postrun_audit.json"
RESERVED_AUDIT_JSON = OUT_DIR / "reserved_residual_candidate_bounded_choice_eval.json"
RESERVED_ROWS_JSONL = OUT_DIR / "reserved_residual_candidate_rows_scored.jsonl"

RUNTIME_BUNDLE = ARTIFACTS / "stage11140_evidence_item_conditioned_gated_probe" / "runtime_model" / "runtime_model_bundle.json"
VALIDATION_JSON = ARTIFACTS / "stage11140_evidence_item_conditioned_gated_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_eval.json"
STRICT_JSON = ARTIFACTS / "stage11140_evidence_item_conditioned_gated_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_strict_eval.json"
EXECUTION_JSON = ARTIFACTS / "stage11140_evidence_item_conditioned_gated_probe" / "bounded_decoder_probe" / "execution_result.json"
RESERVED_ROWS = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence" / "reserved_residual_candidates.jsonl"
SUPPORT_ROWS = ARTIFACTS / "stage11131_evidence_item_support_package" / "added_evidence_item_option_rows.jsonl"
PACKAGE_SUMMARY = ARTIFACTS / "stage11131_evidence_item_support_package" / "evidence_item_support_package.json"
BASELINE_POSTRUN = ARTIFACTS / "stage11117_trainable_evidence_support_postrun_audit" / "trainable_evidence_support_postrun_audit.json"

TORCH_THREADS = max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))
torch.set_num_threads(TORCH_THREADS)
torch.set_num_interop_threads(max(1, min(4, TORCH_THREADS)))
EVAL_DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def audit_accuracy(card: dict[str, Any]) -> float | None:
    value = card.get("constrained_choice_top1_accuracy")
    return float(value) if isinstance(value, (int, float)) else None


def metric_block(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get(field), bool)]
    correct = sum(1 for row in scored if row.get(field) is True)
    return {
        "rows": len(rows),
        "scored_rows": len(scored),
        "correct": correct,
        "exact_accuracy": (correct / len(scored)) if scored else None,
    }


def group_metrics(rows: list[dict[str, Any]], group_field: str, result_field: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(group_field) or "unknown")].append(row)
    return {key: metric_block(bucket, result_field) for key, bucket in sorted(buckets.items())}


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer, dict[str, Any], str]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = dict(bundle.get("metadata") or {})
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    model.to(EVAL_DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tokenizer, init_card, str(metadata.get("bounded_choice_aux_source") or "encoder_option_retrieval")


def overlap_report(strict_rows: list[dict[str, Any]], reserved_rows: list[dict[str, Any]], support_rows: list[dict[str, Any]]) -> dict[str, Any]:
    strict_ids = {str(row.get("row_id") or "") for row in strict_rows}
    reserved_ids = {str(row.get("row_id") or "") for row in reserved_rows}
    support_ids = {str(row.get("row_id") or "") for row in support_rows}
    strict_roots = {str(row.get("source_root_id") or "") for row in strict_rows if row.get("source_root_id")}
    reserved_roots = {str(row.get("source_root_id") or "") for row in reserved_rows if row.get("source_root_id")}
    support_roots = {str(row.get("source_root_id") or "") for row in support_rows if row.get("source_root_id")}
    return {
        "support_row_ids_overlap_strict": sorted(support_ids & strict_ids),
        "support_row_ids_overlap_reserved": sorted(support_ids & reserved_ids),
        "support_source_roots_overlap_strict": sorted(support_roots & strict_roots),
        "support_source_roots_overlap_reserved": sorted(support_roots & reserved_roots),
        "strict_singleton_option_rows": [
            str(row.get("row_id") or "")
            for row in strict_rows
            if len(list(row.get("option_labels") or [])) == 1
        ],
    }


def baseline_value(baseline: dict[str, Any] | None, *keys: str) -> Any:
    current: Any = baseline
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def main() -> None:
    execution = load_json(EXECUTION_JSON)
    validation = load_json(VALIDATION_JSON)
    strict = load_json(STRICT_JSON)
    reserved_rows = load_jsonl(RESERVED_ROWS)
    support_rows = load_jsonl(SUPPORT_ROWS)
    package_summary = load_json(PACKAGE_SUMMARY)
    baseline = load_json(BASELINE_POSTRUN) if BASELINE_POSTRUN.exists() else None
    source_by_id = {str(row.get("row_id") or ""): row for row in reserved_rows}

    model, tokenizer, init_card, scorer_source = load_runtime()
    reserved_card = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=reserved_rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name="reserved_residual_candidate_slice",
        bounded_choice_aux_source=scorer_source,
        eval_batch_size=8,
    )

    enriched_cards = []
    for row in list(reserved_card.get("row_cards") or []):
        source = source_by_id.get(str(row.get("row_id") or ""), {})
        merged = dict(row)
        for key in ["language_family", "repo_family", "repo_id", "task_type", "source_root_id", "split_role"]:
            merged[key] = source.get(key)
        enriched_cards.append(merged)

    write_json(RESERVED_AUDIT_JSON, reserved_card)
    write_jsonl(RESERVED_ROWS_JSONL, enriched_cards)

    validation_accuracy = audit_accuracy(validation)
    strict_accuracy = audit_accuracy(strict)
    reserved_accuracy = audit_accuracy(reserved_card)
    reserved_evidence_rows = [row for row in enriched_cards if str(row.get("task_type") or "") == "evidence_citation"]
    reserved_evidence = metric_block(reserved_evidence_rows, "constrained_choice_match")

    baseline_validation = baseline_value(baseline, "successor_surface_result", "validation_accuracy")
    baseline_strict = baseline_value(baseline, "successor_surface_result", "strict_accuracy")
    baseline_reserved = baseline_value(baseline, "reserved_candidate_result", "overall", "exact_accuracy")
    baseline_reserved_evidence = baseline_value(baseline, "reserved_candidate_result", "by_task_type", "evidence_citation", "exact_accuracy")

    strict_gate = strict_accuracy is not None and strict_accuracy >= (22 / 23)
    validation_gate = validation_accuracy is not None and validation_accuracy >= (20 / 23)
    reserved_gate = reserved_accuracy is not None and reserved_accuracy > 0.5
    reserved_evidence_gate = reserved_evidence.get("exact_accuracy") is not None and float(reserved_evidence["exact_accuracy"]) > (4 / 9)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Audit the stage11140 evidence-item conditioned-gated runtime against unchanged successor validation/strict and untouched reserved residual candidates.",
            "This tests evidence-only conditioned-gated option geometry, not role-name support or a custom scorer head.",
        ],
        "bounded_choice_aux_source": scorer_source,
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "execution_result": rel(EXECUTION_JSON),
            "successor_validation": rel(VALIDATION_JSON),
            "successor_strict": rel(STRICT_JSON),
            "reserved_rows": rel(RESERVED_ROWS),
            "support_rows": rel(SUPPORT_ROWS),
            "package_summary": rel(PACKAGE_SUMMARY),
            "baseline_postrun": rel(BASELINE_POSTRUN) if BASELINE_POSTRUN.exists() else None,
        },
        "support_package_metrics": package_summary.get("metrics"),
        "successor_surface_result": {
            "validation_accuracy": validation_accuracy,
            "validation_miss_rows": [r.get("row_id") for r in validation.get("row_cards", []) if not r.get("constrained_choice_match")],
            "strict_accuracy": strict_accuracy,
            "strict_miss_rows": [r.get("row_id") for r in strict.get("row_cards", []) if not r.get("constrained_choice_match")],
        },
        "reserved_candidate_result": {
            "overall": metric_block(enriched_cards, "constrained_choice_match"),
            "evidence_citation": reserved_evidence,
            "by_language": group_metrics(enriched_cards, "language_family", "constrained_choice_match"),
            "by_repo_family": group_metrics(enriched_cards, "repo_family", "constrained_choice_match"),
            "by_task_type": group_metrics(enriched_cards, "task_type", "constrained_choice_match"),
            "rows_with_target_rank_1": reserved_card.get("rows_with_target_rank_1"),
            "mismatches": [
                {
                    k: row.get(k)
                    for k in [
                        "row_id",
                        "language_family",
                        "repo_family",
                        "task_type",
                        "target_text",
                        "constrained_choice_top1_label",
                        "target_rank_full_vocab",
                        "full_vocab_top1_text",
                    ]
                }
                for row in enriched_cards
                if row.get("constrained_choice_match") is False
            ],
        },
        "anti_cheat_audit": overlap_report(list(strict.get("row_cards") or []), reserved_rows, support_rows),
        "delta_vs_stage11117": {
            "successor_validation_accuracy": None if baseline_validation is None or validation_accuracy is None else validation_accuracy - float(baseline_validation),
            "successor_strict_accuracy": None if baseline_strict is None or strict_accuracy is None else strict_accuracy - float(baseline_strict),
            "reserved_candidate_accuracy": None if baseline_reserved is None or reserved_accuracy is None else reserved_accuracy - float(baseline_reserved),
            "reserved_evidence_accuracy": None if baseline_reserved_evidence is None or reserved_evidence.get("exact_accuracy") is None else float(reserved_evidence["exact_accuracy"]) - float(baseline_reserved_evidence),
        },
        "promotion_gate_result": {
            "strict_preserved_at_22_of_23_or_better": strict_gate,
            "validation_preserved_at_20_of_23_or_better": validation_gate,
            "reserved_improved_above_5_of_10": reserved_gate,
            "reserved_evidence_improved_above_4_of_9": reserved_evidence_gate,
            "promotable_frontier_gain": bool(strict_gate and validation_gate and reserved_gate and reserved_evidence_gate),
        },
        "decision": (
            "evidence_item_conditioned_gated_probe_promotable_frontier_gain"
            if strict_gate and validation_gate and reserved_gate and reserved_evidence_gate
            else "evidence_item_conditioned_gated_probe_diagnostic_only"
        ),
        "runtime_bundle": {
            "weights_sha256": (((execution.get("summary") or {}).get("runtime_model_bundle") or {}).get("weights_sha256")),
            "runtime_initialization": init_card,
        },
        "next_best_step": (
            "Promote only if reserved moved; otherwise use this as evidence that role-name removal alone does not solve scorer/objective mismatch."
        ),
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "reserved_audit_json": rel(RESERVED_AUDIT_JSON),
            "reserved_rows_jsonl": rel(RESERVED_ROWS_JSONL),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

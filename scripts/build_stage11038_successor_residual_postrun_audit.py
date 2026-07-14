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
STAGE = 11038
NAME = "stage11038_successor_residual_postrun_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "successor_residual_postrun_audit.json"
RESERVED_AUDIT_JSON = OUT_DIR / "reserved_residual_candidate_bounded_choice_eval.json"
RESERVED_ROWS_JSONL = OUT_DIR / "reserved_residual_candidate_rows_scored.jsonl"

RUNTIME_BUNDLE = ARTIFACTS / "stage11037_successor_residual_probe" / "runtime_model" / "runtime_model_bundle.json"
VALIDATION_JSON = ARTIFACTS / "stage11037_successor_residual_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_eval.json"
STRICT_JSON = ARTIFACTS / "stage11037_successor_residual_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_strict_eval.json"
EXECUTION_JSON = ARTIFACTS / "stage11037_successor_residual_probe" / "bounded_decoder_probe" / "execution_result.json"
RESERVED_ROWS = ARTIFACTS / "stage11035_successor_residual_support_package" / "reserved_residual_candidates.jsonl"

TORCH_THREADS = max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))
torch.set_num_threads(TORCH_THREADS)
torch.set_num_interop_threads(max(1, min(4, TORCH_THREADS)))
EVAL_DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


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


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer, dict[str, Any]]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    model.to(EVAL_DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tokenizer, init_card


def main() -> None:
    execution = load_json(EXECUTION_JSON)
    validation = load_json(VALIDATION_JSON)
    strict = load_json(STRICT_JSON)
    reserved_rows = load_jsonl(RESERVED_ROWS)
    source_by_id = {str(row.get("row_id") or ""): row for row in reserved_rows}

    model, tokenizer, init_card = load_runtime()
    reserved_card = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=reserved_rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name="reserved_residual_candidate_slice",
        bounded_choice_aux_source="encoder_option_retrieval",
        eval_batch_size=8,
    )

    row_cards = list(reserved_card.get("row_cards") or [])
    enriched_cards = []
    for row in row_cards:
        source = source_by_id.get(str(row.get("row_id") or ""), {})
        merged = dict(row)
        merged["language_family"] = source.get("language_family")
        merged["repo_family"] = source.get("repo_family")
        merged["repo_id"] = source.get("repo_id")
        merged["task_type"] = source.get("task_type")
        enriched_cards.append(merged)

    write_json(RESERVED_AUDIT_JSON, reserved_card)
    write_jsonl(RESERVED_ROWS_JSONL, enriched_cards)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Audit the stage11037 runtime against the stage10896 successor validation/strict surface and the reserved 10-row residual candidate bank.",
            "Keep the successor strict surface and the reserved residual bank analytically separate so verifier-transition and evidence generalization are explicit."
        ],
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "execution_result": rel(EXECUTION_JSON),
            "successor_validation": rel(VALIDATION_JSON),
            "successor_strict": rel(STRICT_JSON),
            "reserved_rows": rel(RESERVED_ROWS),
        },
        "successor_surface_result": {
            "validation_accuracy": validation.get("constrained_choice_top1_accuracy"),
            "validation_miss_rows": [r.get("row_id") for r in validation.get("row_cards", []) if not r.get("constrained_choice_match")],
            "strict_accuracy": strict.get("constrained_choice_top1_accuracy"),
            "strict_miss_rows": [r.get("row_id") for r in strict.get("row_cards", []) if not r.get("constrained_choice_match")],
        },
        "reserved_candidate_result": {
            "overall": metric_block(enriched_cards, "constrained_choice_match"),
            "by_language": group_metrics(enriched_cards, "language_family", "constrained_choice_match"),
            "by_repo_family": group_metrics(enriched_cards, "repo_family", "constrained_choice_match"),
            "by_task_type": group_metrics(enriched_cards, "task_type", "constrained_choice_match"),
            "rows_with_target_rank_1": reserved_card.get("rows_with_target_rank_1"),
            "mismatches": [
                {k: row.get(k) for k in ["row_id", "language_family", "repo_family", "task_type", "target_text", "constrained_choice_top1_label", "target_rank_full_vocab", "full_vocab_top1_text"]}
                for row in enriched_cards
                if row.get("constrained_choice_match") is False
            ],
        },
        "headline": {
            "successor_validation_accuracy": validation.get("constrained_choice_top1_accuracy"),
            "successor_strict_accuracy": strict.get("constrained_choice_top1_accuracy"),
            "reserved_candidate_accuracy": reserved_card.get("constrained_choice_top1_accuracy"),
        },
        "runtime_bundle": {
            "weights_sha256": ((execution.get("summary") or {}).get("runtime_model_bundle") or {}).get("weights_sha256"),
            "runtime_initialization": init_card,
        },
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

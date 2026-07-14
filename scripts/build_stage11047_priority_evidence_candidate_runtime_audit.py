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
STAGE = 11047
NAME = "stage11047_priority_evidence_candidate_runtime_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "priority_evidence_candidate_runtime_audit.json"
CANDIDATE_AUDIT_JSON = OUT_DIR / "bounded_choice_eval_priority_evidence_candidates.json"
SCORED_ROWS_JSONL = OUT_DIR / "priority_evidence_candidates_scored.jsonl"

RUNTIME_BUNDLE = ARTIFACTS / "stage11037_successor_residual_probe" / "runtime_model" / "runtime_model_bundle.json"
CANDIDATE_ROWS = ARTIFACTS / "stage11045_priority_evidence_bounded_candidate_conversion" / "bounded_candidate_rows.jsonl"

TORCH_THREADS = max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))
torch.set_num_threads(TORCH_THREADS)
torch.set_num_interop_threads(max(1, min(4, TORCH_THREADS)))
EVAL_DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
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
    candidate_rows = load_jsonl(CANDIDATE_ROWS)
    source_by_id = {str(row.get("row_id") or ""): row for row in candidate_rows}

    model, tokenizer, init_card = load_runtime()
    audit = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=candidate_rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name="priority_evidence_candidate_slice",
        bounded_choice_aux_source="encoder_option_retrieval",
        eval_batch_size=8,
    )

    row_cards = list(audit.get("row_cards") or [])
    enriched = []
    for row in row_cards:
        source = source_by_id.get(str(row.get("row_id") or ""), {})
        merged = dict(row)
        for key in ["language_family", "repo_family", "repo_id", "task_type", "source_root_id", "source_preview_row_id"]:
            merged[key] = source.get(key)
        enriched.append(merged)

    write_json(CANDIDATE_AUDIT_JSON, audit)
    write_jsonl(SCORED_ROWS_JSONL, enriched)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "priority_evidence_candidate_slice_scored",
        "claim_scope": [
            "Score the anti-cheat-clean stage11045 priority evidence candidate slice with the latest executed 100M runtime.",
            "Measure whether the new bounded evidence rows are learnable by the current runtime before turning them into a larger training branch.",
        ],
        "headline_findings": [
            "This slice directly tests whether the current 100M runtime can prefer verifier-and-test-constraint over candidate-change-surface on the newly materialized rows.",
            "It should be interpreted as a candidate-slice check only; these rows are not yet admitted strict eval.",
        ],
        "metrics": {
            "overall": metric_block(enriched, "constrained_choice_match"),
            "by_language": group_metrics(enriched, "language_family", "constrained_choice_match"),
            "by_repo_family": group_metrics(enriched, "repo_family", "constrained_choice_match"),
            "rows_with_target_rank_1": audit.get("rows_with_target_rank_1"),
        },
        "mismatches": [
            {
                k: row.get(k)
                for k in [
                    "row_id",
                    "language_family",
                    "repo_family",
                    "target_text",
                    "constrained_choice_top1_label",
                    "target_rank_full_vocab",
                    "full_vocab_top1_text",
                ]
            }
            for row in enriched
            if row.get("constrained_choice_match") is False
        ],
        "runtime_bundle": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "runtime_initialization": init_card,
        },
        "next_best_step": "If the runtime scores well here, compare Gemma on the same 5 rows under the same option-scoring interface; if it fails here, keep these rows candidate-only and use them as the next residual support slice.",
        "source_artifacts": {
            "candidate_rows": rel(CANDIDATE_ROWS),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "audit_json": rel(CANDIDATE_AUDIT_JSON),
            "scored_rows_jsonl": rel(SCORED_ROWS_JSONL),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

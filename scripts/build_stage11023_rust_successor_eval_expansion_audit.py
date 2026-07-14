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
STAGE = 11023
NAME = "stage11023_rust_successor_eval_expansion_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "rust_successor_eval_expansion_audit.json"

RUNTIME_BUNDLE = ARTIFACTS / "stage11020_fresh_root_extension_probe_fixed" / "runtime_model" / "runtime_model_bundle.json"
SUCCESSOR_ROWS = ARTIFACTS / "stage11022_rust_successor_eval_expansion_package" / "fresh_rust_successor_eval_expanded.jsonl"

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


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def metric_block(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get(field), bool)]
    correct = sum(1 for row in scored if row.get(field) is True)
    return {"rows": len(rows), "scored_rows": len(scored), "correct": correct, "exact_accuracy": (correct / len(scored)) if scored else None}


def group_metrics(rows: list[dict[str, Any]], group_field: str, result_field: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(group_field) or "unknown")].append(row)
    return {key: metric_block(bucket, result_field) for key, bucket in sorted(buckets.items())}


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    model.to(EVAL_DEVICE)
    model.eval()
    return model, tokenizer


def main() -> None:
    rows = load_jsonl(SUCCESSOR_ROWS)
    model, tokenizer = load_runtime()
    audit = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name="fresh_rust_successor_eval_expanded",
        bounded_choice_aux_source="encoder_option_retrieval",
        eval_batch_size=8,
    )
    out_path = OUT_DIR / "bounded_choice_eval_audit_fresh_rust_successor_eval_expanded.json"
    renamed = OUT_DIR / "fresh_rust_successor_eval_expanded.json"
    if out_path.exists():
        out_path.replace(renamed)

    row_cards = audit.get("row_cards") or []
    mismatches = [
        {k: row.get(k) for k in ["row_id", "task_type", "target_text", "constrained_choice_top1_label", "target_rank_full_vocab", "full_vocab_top1_text"]}
        for row in row_cards
        if row.get("constrained_choice_match") is False
    ]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "rust_successor_eval_expansion_audited",
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "successor_rows": rel(SUCCESSOR_ROWS),
        },
        "metrics": {
            "rows": audit.get("constrained_choice_rows"),
            "exact_accuracy": audit.get("constrained_choice_top1_accuracy"),
            "full_vocab_accuracy": audit.get("full_vocab_top1_accuracy"),
            "rows_with_target_rank_1": audit.get("rows_with_target_rank_1"),
        },
        "by_bundle": group_metrics(row_cards, "row_id", "constrained_choice_match"),
        "mismatches": mismatches,
        "artifacts": {
            "summary_json": rel(SUMMARY_JSON),
            "expanded_audit_json": rel(renamed),
        },
    }
    write_json(SUMMARY_JSON, summary)


if __name__ == "__main__":
    main()

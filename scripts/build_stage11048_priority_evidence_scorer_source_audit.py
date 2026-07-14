#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
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
STAGE = 11048
NAME = "stage11048_priority_evidence_scorer_source_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "priority_evidence_scorer_source_audit.json"

RUNTIME_BUNDLE = ARTIFACTS / "stage11037_successor_residual_probe" / "runtime_model" / "runtime_model_bundle.json"
ROWS_JSONL = ARTIFACTS / "stage11045_priority_evidence_bounded_candidate_conversion" / "bounded_candidate_rows.jsonl"
SOURCES = [
    "decoder_first_step",
    "encoder_pooled",
    "encoder_option_retrieval",
    "encoder_option_retrieval_conditioned",
    "encoder_option_retrieval_evidence_role_map",
    "encoder_option_retrieval_dynamic_productized",
]

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
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_jsonl(ROWS_JSONL)
    model, tokenizer, init_card = load_runtime()

    per_source: dict[str, Any] = {}
    summary_rows: list[dict[str, Any]] = []

    for source in SOURCES:
        card = _write_bounded_choice_eval_audit(
            OUT_DIR,
            model=model,
            rows=rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=8,
            split_name=f"priority_evidence_{source}",
            bounded_choice_aux_source=source,
            eval_batch_size=8,
        )
        per_source[source] = card
        summary_rows.append(
            {
                "source": source,
                "rows": card.get("rows"),
                "constrained_choice_rows": card.get("constrained_choice_rows"),
                "constrained_choice_top1_accuracy": card.get("constrained_choice_top1_accuracy"),
                "full_vocab_top1_accuracy": card.get("full_vocab_top1_accuracy"),
                "rows_with_target_rank_1": card.get("rows_with_target_rank_1"),
            }
        )

    def mismatches_for(source: str) -> list[dict[str, Any]]:
        card = per_source[source]
        return [
            {
                k: row.get(k)
                for k in [
                    "row_id",
                    "target_text",
                    "constrained_choice_top1_label",
                    "constrained_choice_match",
                    "full_vocab_top1_text",
                    "target_rank_full_vocab",
                ]
            }
            for row in card.get("row_cards", [])
            if row.get("constrained_choice_match") is False
        ]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "priority_evidence_scorer_sources_audited",
        "claim_scope": [
            "Compare scorer sources on the anti-cheat-clean 5-row priority evidence slice using the same executed stage11037 runtime.",
            "Determine whether the current failure is specific to encoder_option_retrieval or broader across bounded scorer interfaces.",
        ],
        "runtime_bundle": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "runtime_initialization": init_card,
        },
        "summary_rows": summary_rows,
        "headline_findings": [
            "This comparison distinguishes full-vocab decoder signal from constrained-choice scorer behavior on the exact same 5 rows.",
            "A source that succeeds here would be a direct candidate for either inference-side scoring or a training objective change on the residual lane.",
        ],
        "mismatches": {source: mismatches_for(source) for source in SOURCES},
        "next_best_step": "Use the best-performing source on this 5-row slice as the next scorer-policy candidate, or patch the retrieval scorer if no source cleanly beats the current interface.",
        "source_artifacts": {
            "candidate_rows": rel(ROWS_JSONL),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

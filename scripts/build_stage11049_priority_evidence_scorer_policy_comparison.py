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
STAGE = 11049
NAME = "stage11049_priority_evidence_scorer_policy_comparison"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "priority_evidence_scorer_policy_comparison.json"

RUNTIME_BUNDLE = ARTIFACTS / "stage11037_successor_residual_probe" / "runtime_model" / "runtime_model_bundle.json"
STRICT_ROWS = ARTIFACTS / "stage11035_successor_residual_support_package" / "agentkernel_lite_encdec_strict_eval.jsonl"
EVAL_ROWS = ARTIFACTS / "stage11035_successor_residual_support_package" / "agentkernel_lite_encdec_validation.jsonl"
SLICE_ROWS = ARTIFACTS / "stage11045_priority_evidence_bounded_candidate_conversion" / "bounded_candidate_rows.jsonl"

BASE_SOURCE = "encoder_option_retrieval"
ALT_SOURCE = "encoder_option_retrieval_evidence_role_map"

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


def summarize_card(card: dict[str, Any]) -> dict[str, Any]:
    rows = list(card.get("row_cards") or [])
    evidence_rows = [row for row in rows if "evidence_citation" in str(row.get("row_id") or "")]
    verifier_rows = [row for row in rows if "verifier_outcome" in str(row.get("row_id") or "")]
    return {
        "rows": card.get("rows"),
        "constrained_choice_rows": card.get("constrained_choice_rows"),
        "constrained_choice_top1_accuracy": card.get("constrained_choice_top1_accuracy"),
        "full_vocab_top1_accuracy": card.get("full_vocab_top1_accuracy"),
        "rows_with_target_rank_1": card.get("rows_with_target_rank_1"),
        "evidence_rows": len(evidence_rows),
        "evidence_accuracy": (
            sum(1 for row in evidence_rows if row.get("constrained_choice_match") is True) / len(evidence_rows)
            if evidence_rows else None
        ),
        "verifier_rows": len(verifier_rows),
        "verifier_accuracy": (
            sum(1 for row in verifier_rows if row.get("constrained_choice_match") is True) / len(verifier_rows)
            if verifier_rows else None
        ),
    }


def mismatch_ids(card: dict[str, Any]) -> list[str]:
    return [str(row.get("row_id") or "") for row in (card.get("row_cards") or []) if row.get("constrained_choice_match") is False]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model, tokenizer, init_card = load_runtime()

    datasets = {
        "successor_eval": load_jsonl(EVAL_ROWS),
        "successor_strict": load_jsonl(STRICT_ROWS),
        "priority_evidence_slice": load_jsonl(SLICE_ROWS),
    }

    results: dict[str, dict[str, Any]] = {}
    for dataset_name, rows in datasets.items():
        results[dataset_name] = {}
        for source in [BASE_SOURCE, ALT_SOURCE]:
            card = _write_bounded_choice_eval_audit(
                OUT_DIR,
                model=model,
                rows=rows,
                tokenizer=tokenizer,
                max_encoder_tokens=768,
                max_decoder_tokens=8,
                split_name=f"{dataset_name}_{source}",
                bounded_choice_aux_source=source,
                eval_batch_size=8,
            )
            results[dataset_name][source] = {
                "summary": summarize_card(card),
                "mismatch_ids": mismatch_ids(card),
            }

    comparison = {}
    for dataset_name in datasets:
        base = results[dataset_name][BASE_SOURCE]["summary"]
        alt = results[dataset_name][ALT_SOURCE]["summary"]
        comparison[dataset_name] = {
            "base_source": BASE_SOURCE,
            "alt_source": ALT_SOURCE,
            "base_accuracy": base["constrained_choice_top1_accuracy"],
            "alt_accuracy": alt["constrained_choice_top1_accuracy"],
            "delta_accuracy": (
                (alt["constrained_choice_top1_accuracy"] - base["constrained_choice_top1_accuracy"])
                if base["constrained_choice_top1_accuracy"] is not None and alt["constrained_choice_top1_accuracy"] is not None
                else None
            ),
            "base_evidence_accuracy": base["evidence_accuracy"],
            "alt_evidence_accuracy": alt["evidence_accuracy"],
            "base_verifier_accuracy": base["verifier_accuracy"],
            "alt_verifier_accuracy": alt["verifier_accuracy"],
        }

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "priority_evidence_scorer_policy_compared",
        "claim_scope": [
            "Compare the current runtime scorer against the evidence-role-mapped scorer on the 23-row successor overlay and the 5-row priority evidence slice.",
            "Check whether the stronger scorer on the residual slice is safe enough to adopt without silently regressing the current overlay frontier.",
        ],
        "runtime_bundle": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "runtime_initialization": init_card,
        },
        "comparison": comparison,
        "results": results,
        "headline_findings": [
            "The evidence-role-mapped scorer should only be considered for adoption if it improves the new slice without damaging the current successor overlay.",
            "This comparison is the minimum honest gate before any inference-side scorer policy change.",
        ],
        "next_best_step": "If the role-mapped scorer lifts the 5-row slice and does not regress the 23-row overlay, freeze it as a candidate scoring policy for evidence rows; otherwise keep it diagnostic-only.",
        "source_artifacts": {
            "successor_eval_rows": rel(EVAL_ROWS),
            "successor_strict_rows": rel(STRICT_ROWS),
            "priority_evidence_slice": rel(SLICE_ROWS),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

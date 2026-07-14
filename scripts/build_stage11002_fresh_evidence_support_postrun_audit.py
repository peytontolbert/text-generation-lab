#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import torch

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import _bounded_choice_pairwise_feature_dim, _load_runtime_model_bundle, _write_bounded_choice_eval_audit

ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11002
NAME = "stage11002_fresh_evidence_support_postrun_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_evidence_support_postrun_audit.json"
RUNTIME_BUNDLE = ARTIFACTS / "stage11001_fresh_evidence_support_probe" / "runtime_model" / "runtime_model_bundle.json"
CANDIDATE_ROWS = ARTIFACTS / "stage10998_fresh_evidence_branch_package" / "strict_candidate_rows.jsonl"
OVERLAY_STRICT = ARTIFACTS / "stage10998_fresh_evidence_branch_package" / "overlay_strict_rows.jsonl"
OVERLAY_VAL = ARTIFACTS / "stage10998_fresh_evidence_branch_package" / "overlay_validation_rows.jsonl"

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


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def summarize(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "rows": int(card.get("rows") or 0),
        "exact_accuracy": card.get("constrained_choice_top1_accuracy"),
        "full_vocab_top1_accuracy": card.get("full_vocab_top1_accuracy"),
        "rows_with_target_rank_1": card.get("rows_with_target_rank_1"),
        "miss_rows": [row.get("row_id") for row in card.get("row_cards", []) if row.get("constrained_choice_match") is False],
    }


def load_runtime():
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    source = str(metadata.get("bounded_choice_aux_source") or "encoder_option_retrieval")
    if source == "encoder_option_retrieval_pairwise" and not hasattr(model, "bounded_choice_pair_head"):
        pair_input_dim = _bounded_choice_pairwise_feature_dim(model)
        pair_hidden_dim = int(getattr(getattr(model, "config", None), "retrieval_head_dim", 0) or 0) or int(getattr(getattr(model, "config", None), "d_model", 0) or 0)
        model.bounded_choice_pair_head = torch.nn.Sequential(
            torch.nn.Linear(pair_input_dim, pair_hidden_dim, bias=True),
            torch.nn.SiLU(),
            torch.nn.Linear(pair_hidden_dim, 1, bias=True),
        )
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    model.to(EVAL_DEVICE)
    model.eval()
    return model, tokenizer, init_card, source


def main() -> None:
    model, tokenizer, init_card, source = load_runtime()
    candidate_card = _write_bounded_choice_eval_audit(OUT_DIR, model=model, rows=load_jsonl(CANDIDATE_ROWS), tokenizer=tokenizer, max_encoder_tokens=768, max_decoder_tokens=8, split_name="fresh_candidate_strict", bounded_choice_aux_source=source, eval_batch_size=8)
    overlay_val = _write_bounded_choice_eval_audit(OUT_DIR, model=model, rows=load_jsonl(OVERLAY_VAL), tokenizer=tokenizer, max_encoder_tokens=768, max_decoder_tokens=8, split_name="overlay_eval_reference", bounded_choice_aux_source=source, eval_batch_size=8)
    overlay_strict = _write_bounded_choice_eval_audit(OUT_DIR, model=model, rows=load_jsonl(OVERLAY_STRICT), tokenizer=tokenizer, max_encoder_tokens=768, max_decoder_tokens=8, split_name="overlay_strict_reference", bounded_choice_aux_source=source, eval_batch_size=8)
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Measure whether a probe trained only on the fresh 12-row replenishment support set improves the reserved fresh candidate slice.",
            "Keep overlay references side-by-side so any fresh-root gain is weighed against canary preservation.",
        ],
        "runtime_bundle": rel(RUNTIME_BUNDLE),
        "runtime_initialization": init_card,
        "bounded_choice_aux_source": source,
        "fresh_candidate_slice": summarize(candidate_card),
        "overlay_reference": {
            "eval": summarize(overlay_val),
            "strict": summarize(overlay_strict),
        },
        "next_best_step": "If fresh candidate accuracy improves without material overlay regression, promote these replenishment rows into the next clean training branch; otherwise hold them and continue source expansion.",
    }
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

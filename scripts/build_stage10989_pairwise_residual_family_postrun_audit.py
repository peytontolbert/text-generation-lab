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
STAGE = 10989
NAME = "stage10989_pairwise_residual_family_postrun_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "pairwise_residual_family_postrun_audit.json"
RUNTIME_BUNDLE = ARTIFACTS / "stage10988_pairwise_residual_family_support_probe" / "runtime_model" / "runtime_model_bundle.json"
OVERLAY_VAL = ARTIFACTS / "stage10983_clean_residual_family_support_package" / "agentkernel_lite_encdec_validation.jsonl"
OVERLAY_STRICT = ARTIFACTS / "stage10983_clean_residual_family_support_package" / "agentkernel_lite_encdec_strict_eval.jsonl"
SUCCESSOR_ROWS = ARTIFACTS / "stage10963_expanded_evidence_successor_family" / "expanded_successor_rows.jsonl"
PYTHON_ROWS = ARTIFACTS / "stage10902_python_verifier_transition_candidate_slice" / "strict_candidate_rows.jsonl"

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
    overlay_val = _write_bounded_choice_eval_audit(OUT_DIR, model=model, rows=load_jsonl(OVERLAY_VAL), tokenizer=tokenizer, max_encoder_tokens=768, max_decoder_tokens=8, split_name="eval_pairwise_contract", bounded_choice_aux_source=source, eval_batch_size=8)
    overlay_strict = _write_bounded_choice_eval_audit(OUT_DIR, model=model, rows=load_jsonl(OVERLAY_STRICT), tokenizer=tokenizer, max_encoder_tokens=768, max_decoder_tokens=8, split_name="strict_eval_pairwise_contract", bounded_choice_aux_source=source, eval_batch_size=8)
    successor_card = _write_bounded_choice_eval_audit(OUT_DIR, model=model, rows=load_jsonl(SUCCESSOR_ROWS), tokenizer=tokenizer, max_encoder_tokens=768, max_decoder_tokens=8, split_name="expanded_successor_family", bounded_choice_aux_source=source, eval_batch_size=8)
    python_card = _write_bounded_choice_eval_audit(OUT_DIR, model=model, rows=load_jsonl(PYTHON_ROWS), tokenizer=tokenizer, max_encoder_tokens=768, max_decoder_tokens=8, split_name="python_verifier_transition_candidate_slice", bounded_choice_aux_source=source, eval_batch_size=8)
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Audit the pairwise-scorer runtime against the unchanged overlay and the two live residual slices.",
            "Measure whether a runtime-relevant scorer architecture change improves the residual boundaries without regressing the honest heldout frontier.",
        ],
        "runtime_bundle": rel(RUNTIME_BUNDLE),
        "runtime_initialization": init_card,
        "bounded_choice_aux_source": source,
        "overlay": {"eval": summarize(overlay_val), "strict": summarize(overlay_strict)},
        "expanded_successor_family": summarize(successor_card),
        "python_verifier_transition_candidate_slice": summarize(python_card),
        "next_best_step": "Compare these results against stage10986 and the standing overlay baseline to decide whether the pairwise scorer is worth productizing or whether a deeper target/interface change is still needed.",
    }
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

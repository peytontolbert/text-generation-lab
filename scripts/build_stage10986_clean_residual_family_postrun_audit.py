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
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _write_bounded_choice_eval_audit

ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10986
NAME = "stage10986_clean_residual_family_postrun_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "clean_residual_family_postrun_audit.json"
RUNTIME_BUNDLE = ARTIFACTS / "stage10985_clean_residual_family_support_probe" / "runtime_model" / "runtime_model_bundle.json"
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
        "correct": int(card.get("constrained_choice_correct") or 0),
        "exact_accuracy": card.get("constrained_choice_top1_accuracy"),
        "full_vocab_top1_accuracy": card.get("full_vocab_top1_accuracy"),
        "rows_with_target_rank_1": card.get("rows_with_target_rank_1"),
    }


def load_runtime():
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    model.to(EVAL_DEVICE)
    model.eval()
    return model, tokenizer, init_card

def main() -> None:
    model, tokenizer, init_card = load_runtime()

    overlay_val_rows = load_jsonl(OVERLAY_VAL)
    overlay_strict_rows = load_jsonl(OVERLAY_STRICT)
    successor_rows = load_jsonl(SUCCESSOR_ROWS)
    python_rows = load_jsonl(PYTHON_ROWS)

    overlay_val = _write_bounded_choice_eval_audit(OUT_DIR, model=model, rows=overlay_val_rows, tokenizer=tokenizer, max_encoder_tokens=768, max_decoder_tokens=8, split_name="eval_raw_contract", bounded_choice_aux_source="encoder_option_retrieval", eval_batch_size=8)
    overlay_strict = _write_bounded_choice_eval_audit(OUT_DIR, model=model, rows=overlay_strict_rows, tokenizer=tokenizer, max_encoder_tokens=768, max_decoder_tokens=8, split_name="strict_eval_raw_contract", bounded_choice_aux_source="encoder_option_retrieval", eval_batch_size=8)
    successor_card = _write_bounded_choice_eval_audit(OUT_DIR, model=model, rows=successor_rows, tokenizer=tokenizer, max_encoder_tokens=768, max_decoder_tokens=8, split_name="expanded_successor_family", bounded_choice_aux_source="encoder_option_retrieval", eval_batch_size=8)
    python_card = _write_bounded_choice_eval_audit(OUT_DIR, model=model, rows=python_rows, tokenizer=tokenizer, max_encoder_tokens=768, max_decoder_tokens=8, split_name="python_verifier_transition_candidate_slice", bounded_choice_aux_source="encoder_option_retrieval", eval_batch_size=8)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Audit the clean-curriculum runtime against the unchanged 23-row overlay plus the two live residual slices.",
            "Measure whether the larger clean support package moved evidence or verifier boundaries without regressing the honest overlay.",
        ],
        "runtime_bundle": rel(RUNTIME_BUNDLE),
        "runtime_initialization": init_card,
        "overlay": {
            "eval": summarize(overlay_val),
            "strict": summarize(overlay_strict),
        },
        "expanded_successor_family": summarize(successor_card),
        "python_verifier_transition_candidate_slice": summarize(python_card),
        "next_best_step": "Compare these results against stage10978 and the current canary baseline to decide whether the larger clean curriculum is a real promotion candidate or just another preservation run.",
    }
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

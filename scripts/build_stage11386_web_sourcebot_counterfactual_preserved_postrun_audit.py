#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
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

ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11386
NAME = "stage11386_web_sourcebot_counterfactual_preserved_postrun_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_sourcebot_counterfactual_preserved_postrun_audit.json"
RUNTIME = ART / "stage11385_web_sourcebot_counterfactual_preserved_probe/runtime_model/runtime_model_bundle.json"
BASELINE = ART / "stage11374_web_sourcebot_combined_current_score/web_sourcebot_combined_current_score.json"
SPLITS = {
    "stage11383_train_support": ART / "stage11383_web_sourcebot_abstention_counterfactual_combined_package/web_sourcebot_abstention_counterfactual_combined_rows.jsonl",
    "sourcebot_combined_support": ART / "stage11374_web_sourcebot_combined_current_score/web_sourcebot_combined_support_rows.jsonl",
    "llama_stack_web_heldout": ART / "stage11361_web_llama_stack_executed_heldout_rows/web_llama_stack_executed_heldout_rows.jsonl",
    "canary_strict": ART / "stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_strict_rows.jsonl",
    "canary_validation": ART / "stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_validation_rows.jsonl",
}
SCORERS = ["encoder_option_retrieval_evidence_judgment_head", "encoder_option_retrieval", "encoder_option_retrieval_verifier_conditioned", "decoder_first_step"]

torch.set_num_threads(max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8"))))
torch.set_num_interop_threads(2)
DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def load_runtime():
    bundle = read_json(RUNTIME)
    metadata = bundle["metadata"]
    cfg = AgentKernelLiteTransformerConfig.from_recovered_target_json(read_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(cfg)
    init = _load_runtime_model_bundle(RUNTIME, model=model)
    model.to(DEVICE)
    model.eval()
    tok = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tok, init


def metric(card: dict[str, Any]) -> dict[str, Any]:
    rows = card.get("row_cards") or []
    scored = [r for r in rows if isinstance(r.get("constrained_choice_match"), bool)]
    correct = sum(1 for r in scored if r.get("constrained_choice_match"))
    return {"rows": len(rows), "scored_rows": len(scored), "correct": correct, "exact_accuracy": correct / len(scored) if scored else None}


def misses(card: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "row_id": r.get("row_id"),
            "target_text": r.get("target_text"),
            "predicted": r.get("constrained_choice_top1_label"),
            "full_vocab_top1_text": r.get("full_vocab_top1_text"),
            "target_rank_full_vocab": r.get("target_rank_full_vocab"),
        }
        for r in (card.get("row_cards") or [])
        if r.get("constrained_choice_match") is False
    ]


def main() -> None:
    if not RUNTIME.exists():
        raise SystemExit(f"missing runtime model: {RUNTIME}")
    OUT.mkdir(parents=True, exist_ok=True)
    model, tok, init = load_runtime()
    scored: dict[str, Any] = {}
    for scorer in SCORERS:
        scored[scorer] = {}
        for split, path in SPLITS.items():
            card = _write_bounded_choice_eval_audit(
                OUT,
                model=model,
                rows=read_jsonl(path),
                tokenizer=tok,
                max_encoder_tokens=768,
                max_decoder_tokens=8,
                split_name=f"{split}_{scorer}",
                bounded_choice_aux_source=scorer,
                eval_batch_size=8,
            )
            scored[scorer][split] = {"metric": metric(card), "misses": misses(card)}
    product = "encoder_option_retrieval_evidence_judgment_head"
    product_metrics = {k: v["metric"] for k, v in scored[product].items()}
    baseline = read_json(BASELINE).get("product_metrics", {})
    gates = {
        "sourcebot_improved": product_metrics.get("sourcebot_combined_support", {}).get("correct", 0) > baseline.get("sourcebot_combined_support", {}).get("correct", 0),
        "heldout_improved": product_metrics.get("llama_stack_web_heldout", {}).get("correct", 0) > baseline.get("llama_stack_web_heldout", {}).get("correct", 0),
        "strict_preserved": product_metrics.get("canary_strict", {}).get("correct") == 22,
        "validation_preserved": product_metrics.get("canary_validation", {}).get("correct", 0) >= 20,
    }
    decision = "accept_stage11385_as_diagnostic_support_runtime_keep_stage11200_frontier" if all(gates.values()) else "reject_stage11385_keep_stage11200_frontier"
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "decision": decision,
        "runtime_initialization": init,
        "product_scorer": product,
        "baseline_product_metrics": baseline,
        "product_metrics": product_metrics,
        "gates": gates,
        "scored": scored,
        "source_artifacts": {"runtime": rel(RUNTIME), "baseline": rel(BASELINE), **{k: rel(v) for k, v in SPLITS.items()}},
        "outputs": {"summary": rel(SUMMARY)},
        "recommended_next_action": "If validation still regresses, stop this support path and mine fresh Web roots; if preserved with transfer, keep runtime diagnostic-only until same-manifest Gemma comparison is refreshed.",
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "gates": gates, "product_metrics": product_metrics}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

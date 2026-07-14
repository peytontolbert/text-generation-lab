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
STAGE = 11391
NAME = "stage11391_openhands_web_heldout_candidate_score_audit"
OUT = ART / NAME
SUMMARY = OUT / "openhands_web_heldout_candidate_score_audit.json"
ROWS = ART / "stage11390_openhands_unit_verifier_heldout_candidate_rows/openhands_unit_verifier_heldout_candidate_rows.jsonl"
CANARY_STRICT = ART / "stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_strict_rows.jsonl"
CANARY_VALIDATION = ART / "stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_validation_rows.jsonl"
RUNTIMES = {
    "stage11200_frontier": ART / "stage11200_role_focused_residual_probe/runtime_model/runtime_model_bundle.json",
    "stage11385_sourcebot_counterfactual_rejected": ART / "stage11385_web_sourcebot_counterfactual_preserved_probe/runtime_model/runtime_model_bundle.json",
}
SCORERS = [
    "encoder_option_retrieval_evidence_judgment_head",
    "encoder_option_retrieval_evidence_ledger_head",
    "encoder_option_retrieval_verifier_conditioned",
    "encoder_option_retrieval",
    "decoder_first_step",
]

torch.set_num_threads(max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8"))))
torch.set_num_interop_threads(2)
DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def load_runtime(runtime: Path):
    bundle = read_json(runtime)
    metadata = bundle["metadata"]
    cfg = AgentKernelLiteTransformerConfig.from_recovered_target_json(read_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(cfg)
    init = _load_runtime_model_bundle(runtime, model=model)
    model.to(DEVICE)
    model.eval()
    tok = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tok, init


def metric(card: dict[str, Any]) -> dict[str, Any]:
    row_cards = card.get("row_cards") or []
    scored = [r for r in row_cards if isinstance(r.get("constrained_choice_match"), bool)]
    correct = sum(1 for r in scored if r.get("constrained_choice_match"))
    return {
        "rows": len(row_cards),
        "scored_rows": len(scored),
        "correct": correct,
        "exact_accuracy": correct / len(scored) if scored else None,
    }


def misses(card: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for r in card.get("row_cards") or []:
        if r.get("constrained_choice_match") is False:
            out.append(
                {
                    "row_id": r.get("row_id"),
                    "task_type": r.get("task_type"),
                    "target_text": r.get("target_text"),
                    "predicted": r.get("constrained_choice_top1_label"),
                    "full_vocab_top1_text": r.get("full_vocab_top1_text"),
                    "target_rank_full_vocab": r.get("target_rank_full_vocab"),
                }
            )
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    splits = {
        "openhands_web_heldout_candidate": read_jsonl(ROWS),
        "canary_strict": read_jsonl(CANARY_STRICT),
        "canary_validation": read_jsonl(CANARY_VALIDATION),
    }
    scored: dict[str, Any] = {}
    for runtime_name, runtime_path in RUNTIMES.items():
        if not runtime_path.exists():
            scored[runtime_name] = {"missing_runtime": rel(runtime_path)}
            continue
        model, tok, init = load_runtime(runtime_path)
        runtime_scores: dict[str, Any] = {"runtime_initialization": init, "scores": {}}
        for scorer in SCORERS:
            runtime_scores["scores"][scorer] = {}
            for split_name, rows in splits.items():
                card = _write_bounded_choice_eval_audit(
                    OUT,
                    model=model,
                    rows=rows,
                    tokenizer=tok,
                    max_encoder_tokens=768,
                    max_decoder_tokens=8,
                    split_name=f"{runtime_name}_{split_name}_{scorer}",
                    bounded_choice_aux_source=scorer,
                    eval_batch_size=8,
                )
                runtime_scores["scores"][scorer][split_name] = {"metric": metric(card), "misses": misses(card)}
        scored[runtime_name] = runtime_scores
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    product_scorer = "encoder_option_retrieval_evidence_judgment_head"
    product_metrics = {
        runtime_name: {
            split: payload["metric"]
            for split, payload in runtime_card.get("scores", {}).get(product_scorer, {}).items()
        }
        for runtime_name, runtime_card in scored.items()
        if isinstance(runtime_card, dict) and "scores" in runtime_card
    }
    frontier_metric = product_metrics.get("stage11200_frontier", {}).get("openhands_web_heldout_candidate", {})
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "decision": "openhands_web_heldout_candidate_scored_no_training",
        "claim_scope": "three OpenHands unit-verifier roots; heldout-candidate Web smoke slice, not a broad Web claim",
        "product_scorer": product_scorer,
        "frontier_metric": frontier_metric,
        "product_metrics": product_metrics,
        "scored": scored,
        "source_artifacts": {
            "heldout_candidate_rows": rel(ROWS),
            "canary_strict": rel(CANARY_STRICT),
            "canary_validation": rel(CANARY_VALIDATION),
            **{f"runtime_{k}": rel(v) for k, v in RUNTIMES.items()},
        },
        "outputs": {"summary": rel(SUMMARY)},
        "recommended_next_action": "Run Gemma on the same Stage11390 row manifest, then decide whether these OpenHands roots should enter strict Web successor or remain diagnostic.",
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"frontier_metric": frontier_metric, "product_metrics": product_metrics}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

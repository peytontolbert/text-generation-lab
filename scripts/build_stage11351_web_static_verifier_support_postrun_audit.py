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

ART = ROOT / "runs/local/artifacts"
STAGE = 11351
NAME = "stage11351_web_static_verifier_support_postrun_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_static_verifier_support_postrun_audit.json"
RUNTIME = ART / "stage11350_web_static_verifier_support_probe/runtime_model/runtime_model_bundle.json"
SPLITS = {
    "web_static_verifier_train_support": ART / "stage11347_web_static_verifier_maintainer_rows/web_static_verifier_train_support_rows.jsonl",
    "canary_strict": ART / "stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_strict_rows.jsonl",
    "canary_validation": ART / "stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_validation_rows.jsonl",
    "web_source_snippet_support": ART / "stage11338_web_source_snippet_evidence_materialization/web_source_snippet_evidence_rows.jsonl",
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
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


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
    row_cards = card.get("row_cards") or []
    scored = [r for r in row_cards if isinstance(r.get("constrained_choice_match"), bool)]
    correct = sum(1 for r in scored if r.get("constrained_choice_match"))
    return {"rows": len(row_cards), "scored_rows": len(scored), "correct": correct, "exact_accuracy": correct / len(scored) if scored else None}


def misses(card: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for r in card.get("row_cards") or []:
        if r.get("constrained_choice_match") is False:
            out.append({
                "row_id": r.get("row_id"),
                "target_text": r.get("target_text"),
                "predicted": r.get("constrained_choice_top1_label"),
                "full_vocab_top1_text": r.get("full_vocab_top1_text"),
                "target_rank_full_vocab": r.get("target_rank_full_vocab"),
            })
    return out[:80]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    model, tok, init = load_runtime()
    scored: dict[str, Any] = {}
    for scorer in SCORERS:
        scored[scorer] = {}
        for split, path in SPLITS.items():
            rows = read_jsonl(path)
            card = _write_bounded_choice_eval_audit(
                OUT,
                model=model,
                rows=rows,
                tokenizer=tok,
                max_encoder_tokens=768,
                max_decoder_tokens=8,
                split_name=f"{split}_{scorer}",
                bounded_choice_aux_source=scorer,
                eval_batch_size=8,
            )
            scored[scorer][split] = {"metric": metric(card), "misses": misses(card)}
    product_scorer = "encoder_option_retrieval_evidence_judgment_head"
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "decision": "web_static_verifier_support_postrun_audit_complete",
        "runtime_initialization": init,
        "product_scorer": product_scorer,
        "product_metrics": {k: v["metric"] for k, v in scored[product_scorer].items()},
        "scored": scored,
        "source_artifacts": {"runtime": rel(RUNTIME), **{k: rel(v) for k, v in SPLITS.items()}},
        "outputs": {"summary": rel(SUMMARY)},
        "recommended_next_action": "Accept Stage11350 only if web_static_verifier_train_support improves above 8/18 and canary strict remains 22/22 with validation >=20/23; otherwise reject and keep Stage11200.",
    }
    write_json(SUMMARY, summary)
    print(json.dumps({"product_metrics": summary["product_metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

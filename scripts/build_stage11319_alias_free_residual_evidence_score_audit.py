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

ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11319
NAME = "stage11319_alias_free_residual_evidence_score_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY = OUT_DIR / "alias_free_residual_evidence_score_audit.json"
ROWS = ARTIFACTS / "stage11318_alias_free_residual_evidence_item_materialization/alias_free_residual_evidence_item_rows.jsonl"
MAT = ARTIFACTS / "stage11318_alias_free_residual_evidence_item_materialization/alias_free_residual_evidence_item_materialization.json"
FRONTIER = ARTIFACTS / "stage11200_role_focused_residual_probe/runtime_model/runtime_model_bundle.json"
SCORERS = ["encoder_option_retrieval_verifier_conditioned", "encoder_option_retrieval_evidence_judgment_head", "encoder_option_retrieval", "decoder_first_step"]

torch.set_num_threads(max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8"))))
torch.set_num_interop_threads(2)
DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_runtime():
    bundle = read_json(FRONTIER)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(read_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init = _load_runtime_model_bundle(FRONTIER, model=model)
    model.to(DEVICE)
    model.eval()
    tok = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tok, init


def metric(card: dict[str, Any]) -> dict[str, Any]:
    rows = card.get("row_cards") or []
    scored = [r for r in rows if isinstance(r.get("constrained_choice_match"), bool)]
    correct = sum(1 for r in scored if r.get("constrained_choice_match"))
    return {"rows": len(rows), "scored_rows": len(scored), "correct": correct, "exact_accuracy": correct / len(scored) if scored else None}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(ROWS)
    mat = read_json(MAT)
    model, tok, init = load_runtime()
    scored = {}
    for scorer in SCORERS:
        card = _write_bounded_choice_eval_audit(
            OUT_DIR,
            model=model,
            rows=rows,
            tokenizer=tok,
            max_encoder_tokens=768,
            max_decoder_tokens=8,
            split_name=f"alias_free_residual_{scorer}",
            bounded_choice_aux_source=scorer,
            eval_batch_size=8,
        )
        misses = []
        for r in card.get("row_cards") or []:
            if r.get("constrained_choice_match") is False:
                misses.append({
                    "row_id": r.get("row_id"),
                    "target_text": r.get("target_text"),
                    "predicted": r.get("constrained_choice_top1_label"),
                    "full_vocab_top1_text": r.get("full_vocab_top1_text"),
                    "target_rank_full_vocab": r.get("target_rank_full_vocab"),
                })
        scored[scorer] = {"metric": metric(card), "misses": misses}
    best = max(scored.items(), key=lambda kv: kv[1]["metric"]["correct"] if kv[1]["metric"]["correct"] is not None else -1)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "decision": "alias_free_residual_evidence_score_audit_complete",
        "runtime_initialization": init,
        "materialization_counts": mat.get("counts"),
        "materialization_audit": mat.get("audit"),
        "best_scorer": best[0],
        "best_metric": best[1]["metric"],
        "scored": scored,
        "interpretation": [
            "Alias-free residual replacements are a harder and more honest check than role-alias residual rows.",
            "Blocked Rust symptom rows should be replaced from fresh source material; the available prompt does not contain alias-free symptom/call-path evidence matching the hidden gold role.",
            "This audit is not a frontier claim; it determines whether replacement rows are usable for the next eval package.",
        ],
        "source_artifacts": {"rows": rel(ROWS), "materialization": rel(MAT), "frontier_runtime": rel(FRONTIER)},
        "outputs": {"summary_json": rel(SUMMARY)},
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

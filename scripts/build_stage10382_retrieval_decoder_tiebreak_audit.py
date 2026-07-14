#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer, build_batch
from legacy_src.agentkernel_lite.training_loop import _bounded_choice_option_logits, _load_runtime_model_bundle

NAME = "stage10382_retrieval_decoder_tiebreak_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = ROOT / "runs/local/artifacts/stage10378_balanced_residual_probe_execution_request/balanced_residual_probe_manifest.jsonl"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10379_balanced_residual_probe/runtime_model/runtime_model_bundle.json"
MARGIN_GRID = [0.001, 0.0025, 0.005, 0.01, 0.015, 0.02]
DECODER_DELTA_GRID = [0.0, 0.25, 0.5, 1.0]


def _load_rows() -> list[dict[str, object]]:
    rows = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("split") == "strict_eval":
            rows.append(row)
    rows.sort(key=lambda row: str(row["row_id"]))
    return rows


def _load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer]:
    bundle = json.loads(RUNTIME_BUNDLE.read_text(encoding="utf-8"))
    metadata = bundle["metadata"]
    model_config = json.loads(Path(str(metadata["model_config"])).read_text(encoding="utf-8"))
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(model_config)
    model = AgentKernelLiteTransformerSeq2Seq(config)
    _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(
        Path(str(metadata["tokenizer_json"])),
        Path(str(metadata["tokenizer_config"])),
    )
    model.eval()
    return model, tokenizer


def _score_row(model: AgentKernelLiteTransformerSeq2Seq, tokenizer: AgentKernelBPETokenizer, row: dict[str, object]) -> dict[str, object]:
    batch = build_batch([row], max_encoder_tokens=768, max_decoder_tokens=8, tokenizer=tokenizer)
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
    first_step_logits = out["decoder_logits"][0, 0]
    pooled = out["pooled"][0]
    retrieval_logits, option_pairs, _ = _bounded_choice_option_logits(
        row=row,
        tokenizer=tokenizer,
        source="encoder_option_retrieval",
        first_step_logits_row=first_step_logits,
        pooled_row=pooled,
        model=model,
        untied_head=None,
    )
    decoder_logits, _, _ = _bounded_choice_option_logits(
        row=row,
        tokenizer=tokenizer,
        source="decoder_first_step",
        first_step_logits_row=first_step_logits,
        pooled_row=pooled,
        model=model,
        untied_head=None,
    )
    retrieval_scores = {label: float(retrieval_logits[idx].item()) for idx, (label, _) in enumerate(option_pairs)}
    decoder_scores = {label: float(decoder_logits[idx].item()) for idx, (label, _) in enumerate(option_pairs)}
    retrieval_order = sorted(retrieval_scores, key=retrieval_scores.get, reverse=True)
    decoder_order = sorted(decoder_scores, key=decoder_scores.get, reverse=True)
    return {
        "row_id": row["row_id"],
        "target": row["decoder_text"],
        "retrieval_order": retrieval_order,
        "decoder_order": decoder_order,
        "retrieval_scores": retrieval_scores,
        "decoder_scores": decoder_scores,
        "retrieval_margin": retrieval_scores[retrieval_order[0]] - retrieval_scores[retrieval_order[1]] if len(retrieval_order) > 1 else 999.0,
        "decoder_advantage_over_retrieval": decoder_scores[decoder_order[0]] - decoder_scores[retrieval_order[0]],
    }


def _predict(row: dict[str, object], margin_threshold: float, decoder_delta_threshold: float) -> str:
    retrieval_order = row["retrieval_order"]
    decoder_order = row["decoder_order"]
    if (
        row["retrieval_margin"] <= margin_threshold
        and decoder_order[0] != retrieval_order[0]
        and row["decoder_advantage_over_retrieval"] >= decoder_delta_threshold
    ):
        return decoder_order[0]
    return retrieval_order[0]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = _load_rows()
    model, tokenizer = _load_runtime()
    scored_rows = [_score_row(model, tokenizer, row) for row in rows]

    baseline_correct = sum(1 for row in scored_rows if row["retrieval_order"][0] == row["target"])
    baseline_accuracy = baseline_correct / len(scored_rows)
    candidates: list[dict[str, object]] = []
    for margin_threshold in MARGIN_GRID:
        for decoder_delta_threshold in DECODER_DELTA_GRID:
            correct = 0
            misses = []
            flips = []
            for row in scored_rows:
                pred = _predict(row, margin_threshold, decoder_delta_threshold)
                if pred == row["target"]:
                    correct += 1
                else:
                    misses.append({"row_id": row["row_id"], "target": row["target"], "pred": pred})
                if pred != row["retrieval_order"][0]:
                    flips.append(
                        {
                            "row_id": row["row_id"],
                            "target": row["target"],
                            "retrieval_pred": row["retrieval_order"][0],
                            "decoder_pred": row["decoder_order"][0],
                            "hybrid_pred": pred,
                            "retrieval_margin": row["retrieval_margin"],
                            "decoder_advantage_over_retrieval": row["decoder_advantage_over_retrieval"],
                        }
                    )
            candidates.append(
                {
                    "margin_threshold": margin_threshold,
                    "decoder_delta_threshold": decoder_delta_threshold,
                    "correct": correct,
                    "rows": len(scored_rows),
                    "accuracy": correct / len(scored_rows),
                    "improvement_over_baseline": (correct / len(scored_rows)) - baseline_accuracy,
                    "flips": flips,
                    "misses": misses,
                }
            )

    candidates.sort(key=lambda card: (card["accuracy"], -len(card["flips"])), reverse=True)
    payload = {
        "stage_name": NAME,
        "runtime_bundle": str(RUNTIME_BUNDLE),
        "rows": len(scored_rows),
        "baseline_accuracy": baseline_accuracy,
        "baseline_correct": baseline_correct,
        "top_candidates": candidates[:10],
    }
    out_path = OUT_DIR / "retrieval_decoder_tiebreak_audit.json"
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()

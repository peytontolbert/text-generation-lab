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

NAME = "stage10381_residual_retrieval_score_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = ROOT / "runs/local/artifacts/stage10378_balanced_residual_probe_execution_request/balanced_residual_probe_manifest.jsonl"
STRICT_AUDIT = ROOT / "runs/local/artifacts/stage10379_balanced_residual_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
RUNTIMES = {
    "stage10373": ROOT / "runs/local/artifacts/stage10373_honest_frontier_runtime_earlysave/runtime_model/runtime_model_bundle.json",
    "stage10379": ROOT / "runs/local/artifacts/stage10379_balanced_residual_probe/runtime_model/runtime_model_bundle.json",
}


def _load_runtime(runtime_bundle: Path) -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer]:
    bundle = json.loads(runtime_bundle.read_text(encoding="utf-8"))
    metadata = bundle["metadata"]
    model_config = json.loads(Path(str(metadata["model_config"])).read_text(encoding="utf-8"))
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(model_config)
    model = AgentKernelLiteTransformerSeq2Seq(config)
    _load_runtime_model_bundle(runtime_bundle, model=model)
    tokenizer = AgentKernelBPETokenizer(
        Path(str(metadata["tokenizer_json"])),
        Path(str(metadata["tokenizer_config"])),
    )
    model.eval()
    return model, tokenizer


def _residual_ids() -> set[str]:
    data = json.loads(STRICT_AUDIT.read_text(encoding="utf-8"))
    return {
        row["row_id"]
        for row in data["row_cards"]
        if not row.get("constrained_choice_match")
    }


def _residual_rows() -> list[dict[str, object]]:
    wanted = _residual_ids()
    rows = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("row_id") in wanted:
            rows.append(row)
    rows.sort(key=lambda row: str(row["row_id"]))
    return rows


def _audit_row(model: AgentKernelLiteTransformerSeq2Seq, tokenizer: AgentKernelBPETokenizer, row: dict[str, object]) -> dict[str, object]:
    batch = build_batch([row], max_encoder_tokens=768, max_decoder_tokens=8, tokenizer=tokenizer)
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
    first_step_logits = out["decoder_logits"][0, 0]
    pooled = out["pooled"][0]
    retrieval_logits, option_pairs, retrieval_reason = _bounded_choice_option_logits(
        row=row,
        tokenizer=tokenizer,
        source="encoder_option_retrieval",
        first_step_logits_row=first_step_logits,
        pooled_row=pooled,
        model=model,
        untied_head=None,
    )
    conditioned_logits, _, conditioned_reason = _bounded_choice_option_logits(
        row=row,
        tokenizer=tokenizer,
        source="encoder_option_retrieval_conditioned",
        first_step_logits_row=first_step_logits,
        pooled_row=pooled,
        model=model,
        untied_head=None,
    )
    decoder_logits, _, decoder_reason = _bounded_choice_option_logits(
        row=row,
        tokenizer=tokenizer,
        source="decoder_first_step",
        first_step_logits_row=first_step_logits,
        pooled_row=pooled,
        model=model,
        untied_head=None,
    )

    def pack_scores(logits: torch.Tensor | None, reason: str | None) -> list[dict[str, object]]:
        if logits is None:
            return [{"error": reason or "missing_logits"}]
        scores = []
        for idx, (label, token_id) in enumerate(option_pairs):
            value = (((row.get("standalone_projection_source") or {}).get("opaque_options")) or [])[idx]["value"]
            scores.append(
                {
                    "label": label,
                    "token_id": token_id,
                    "value": value,
                    "logit": float(logits[idx].item()),
                }
            )
        scores.sort(key=lambda item: item["logit"], reverse=True)
        return scores

    return {
        "row_id": row["row_id"],
        "decoder_text": row.get("decoder_text"),
        "prompt_text": row.get("prompt_text"),
        "retrieval_scores": pack_scores(retrieval_logits, retrieval_reason),
        "conditioned_retrieval_scores": pack_scores(conditioned_logits, conditioned_reason),
        "decoder_option_scores": pack_scores(decoder_logits, decoder_reason),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = _residual_rows()
    payload: dict[str, object] = {"rows": [row["row_id"] for row in rows], "runtimes": {}}
    for runtime_name, runtime_bundle in RUNTIMES.items():
        model, tokenizer = _load_runtime(runtime_bundle)
        payload["runtimes"][runtime_name] = {
            "runtime_bundle": str(runtime_bundle),
            "row_audits": [_audit_row(model, tokenizer, row) for row in rows],
        }
    out_path = OUT_DIR / "residual_retrieval_score_audit.json"
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()

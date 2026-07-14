#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _write_bounded_choice_eval_audit

NAME = "stage10380_residual_option_source_comparison_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = ROOT / "runs/local/artifacts/stage10378_balanced_residual_probe_execution_request/balanced_residual_probe_manifest.jsonl"
RUNTIMES = {
    "stage10373": ROOT / "runs/local/artifacts/stage10373_honest_frontier_runtime_earlysave/runtime_model/runtime_model_bundle.json",
    "stage10379": ROOT / "runs/local/artifacts/stage10379_balanced_residual_probe/runtime_model/runtime_model_bundle.json",
}
SOURCES = [
    "decoder_first_step",
    "encoder_pooled",
    "encoder_option_retrieval",
    "encoder_option_retrieval_conditioned",
]


def _load_rows() -> list[dict[str, object]]:
    rows = [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [row for row in rows if row.get("split") == "strict_eval"]


def _load_model_and_tokenizer(runtime_bundle: Path) -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer, dict[str, object]]:
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
    return model, tokenizer, bundle


def _misses(card: dict[str, object]) -> list[dict[str, object]]:
    misses: list[dict[str, object]] = []
    for row in card.get("row_cards", []):
        if row.get("constrained_choice_match"):
            continue
        misses.append(
            {
                "row_id": row["row_id"],
                "target_text": row.get("target_text"),
                "constrained_choice_top1_label": row.get("constrained_choice_top1_label"),
                "full_vocab_top1_text": row.get("full_vocab_top1_text"),
                "target_rank_full_vocab": row.get("target_rank_full_vocab"),
            }
        )
    return misses


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    strict_rows = _load_rows()
    summary: list[dict[str, object]] = []
    detailed: dict[str, dict[str, object]] = {}

    for runtime_name, runtime_bundle in RUNTIMES.items():
        runtime_out = OUT_DIR / runtime_name
        runtime_out.mkdir(parents=True, exist_ok=True)
        model, tokenizer, bundle = _load_model_and_tokenizer(runtime_bundle)
        runtime_detail: dict[str, object] = {
            "runtime_bundle": str(runtime_bundle),
            "weights_sha256": bundle.get("weights_sha256"),
            "sources": {},
        }
        for source in SOURCES:
            card = _write_bounded_choice_eval_audit(
                runtime_out,
                model=model,
                rows=strict_rows,
                tokenizer=tokenizer,
                max_encoder_tokens=768,
                max_decoder_tokens=8,
                split_name=f"strict_eval_{source}",
                bounded_choice_aux_source=source,
                eval_batch_size=8,
            )
            runtime_detail["sources"][source] = {
                "rows": card["rows"],
                "constrained_choice_top1_accuracy": card["constrained_choice_top1_accuracy"],
                "full_vocab_top1_accuracy": card["full_vocab_top1_accuracy"],
                "rows_with_target_rank_1": card["rows_with_target_rank_1"],
                "misses": _misses(card),
            }
            summary.append(
                {
                    "runtime": runtime_name,
                    "source": source,
                    "rows": card["rows"],
                    "constrained_choice_top1_accuracy": card["constrained_choice_top1_accuracy"],
                    "full_vocab_top1_accuracy": card["full_vocab_top1_accuracy"],
                    "rows_with_target_rank_1": card["rows_with_target_rank_1"],
                }
            )
        detailed[runtime_name] = runtime_detail

    payload = {
        "stage_name": NAME,
        "manifest": str(MANIFEST),
        "strict_rows": len(strict_rows),
        "summary": summary,
        "detailed": detailed,
    }
    out_path = OUT_DIR / "residual_option_source_comparison_summary.json"
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

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
OUT_DIR = ROOT / "runs/local/artifacts/stage10324_option_source_comparison_probe"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10303_hf_local_support_probe/runtime_model/runtime_model_bundle.json"
MANIFEST = ROOT / "runs/local/artifacts/stage10307_source_backed_action_support_plus_execution_request/source_backed_action_support_plus_manifest.jsonl"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]
    strict_rows = [row for row in rows if row.get("split") == "strict_eval"]

    bundle = json.loads(RUNTIME_BUNDLE.read_text(encoding="utf-8"))
    metadata = bundle["metadata"]
    model_config = json.loads(Path(metadata["model_config"]).read_text(encoding="utf-8"))
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(model_config)
    model = AgentKernelLiteTransformerSeq2Seq(config)
    _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(Path(metadata["tokenizer_json"]), Path(metadata["tokenizer_config"]))

    summary: list[dict[str, object]] = []
    for source in ["decoder_first_step", "encoder_pooled", "encoder_option_retrieval", "encoder_option_retrieval_conditioned"]:
        card = _write_bounded_choice_eval_audit(
            OUT_DIR,
            model=model,
            rows=strict_rows,
            tokenizer=tokenizer,
            max_encoder_tokens=896,
            max_decoder_tokens=8,
            split_name=f"strict_eval_{source}",
            bounded_choice_aux_source=source,
            eval_batch_size=8,
        )
        summary.append({
            "source": source,
            "rows": card["rows"],
            "constrained_choice_top1_accuracy": card["constrained_choice_top1_accuracy"],
            "full_vocab_top1_accuracy": card["full_vocab_top1_accuracy"],
            "rows_with_target_rank_1": card["rows_with_target_rank_1"],
        })

    (OUT_DIR / "option_source_comparison_summary.json").write_text(
        json.dumps({"runtime_bundle": str(RUNTIME_BUNDLE), "summary": summary}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import json
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


ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10833
NAME = "stage10833_current_option_source_comparison_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "current_option_source_comparison_audit.json"

RUNTIME_BUNDLE = ARTIFACTS / "stage10829_evidence_role_support_probe" / "runtime_model" / "runtime_model_bundle.json"
STRICT_ROWS = ARTIFACTS / "stage10827_evidence_role_augmented_support_package" / "agentkernel_lite_encdec_strict_eval.jsonl"
EVAL_ROWS = ARTIFACTS / "stage10827_evidence_role_augmented_support_package" / "agentkernel_lite_encdec_validation.jsonl"

SOURCES = [
    "decoder_first_step",
    "encoder_option_retrieval",
    "encoder_option_retrieval_conditioned",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    if torch.cuda.is_available():
        model = model.to(torch.device("cuda"))
    tokenizer = AgentKernelBPETokenizer(
        Path(str(metadata["tokenizer_json"])),
        Path(str(metadata["tokenizer_config"])),
    )
    model.eval()
    return model, tokenizer


def summarize(card: dict[str, Any]) -> dict[str, Any]:
    rows = card.get("row_cards") or []
    task_summary: dict[str, dict[str, Any]] = {}
    for row in rows:
        task = str(row["row_id"]).split("::")[-2]
        stats = task_summary.setdefault(task, {"correct": 0, "total": 0, "exact": 0.0})
        stats["total"] += 1
        if row.get("constrained_choice_match") is True:
            stats["correct"] += 1
    for stats in task_summary.values():
        stats["exact"] = stats["correct"] / stats["total"] if stats["total"] else 0.0
    return {
        "rows": card.get("rows"),
        "constrained_choice_top1_accuracy": card.get("constrained_choice_top1_accuracy"),
        "full_vocab_top1_accuracy": card.get("full_vocab_top1_accuracy"),
        "rows_with_target_rank_1": card.get("rows_with_target_rank_1"),
        "task_summary": dict(sorted(task_summary.items())),
        "misses": [row for row in rows if row.get("constrained_choice_match") is not True],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    strict_rows = load_rows(STRICT_ROWS)
    eval_rows = load_rows(EVAL_ROWS)
    model, tokenizer = load_runtime()

    results: dict[str, Any] = {}
    for source in SOURCES:
        strict_card = _write_bounded_choice_eval_audit(
            OUT_DIR,
            model=model,
            rows=strict_rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=8,
            split_name=f"strict_eval_{source}",
            bounded_choice_aux_source=source,
            eval_batch_size=8,
        )
        eval_card = _write_bounded_choice_eval_audit(
            OUT_DIR,
            model=model,
            rows=eval_rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=8,
            split_name=f"eval_{source}",
            bounded_choice_aux_source=source,
            eval_batch_size=8,
        )
        results[source] = {
            "strict_eval": summarize(strict_card),
            "eval": summarize(eval_card),
        }

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "runtime_bundle": str(RUNTIME_BUNDLE.relative_to(ROOT)),
        "strict_manifest": str(STRICT_ROWS.relative_to(ROOT)),
        "eval_manifest": str(EVAL_ROWS.relative_to(ROOT)),
        "results": results,
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

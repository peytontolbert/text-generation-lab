#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
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
STAGE = 11033
NAME = "stage11033_next_root_support_postrun_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "next_root_support_postrun_audit.json"
RESERVED_AUDIT_JSON = OUT_DIR / "reserved_candidate_bounded_choice_eval.json"
RESERVED_ROWS_JSONL = OUT_DIR / "reserved_candidate_rows_scored.jsonl"

RUNTIME_BUNDLE = ARTIFACTS / "stage11032_next_root_support_probe" / "runtime_model" / "runtime_model_bundle.json"
OVERLAY_EVAL_JSON = ARTIFACTS / "stage11032_next_root_support_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_eval.json"
OVERLAY_STRICT_JSON = ARTIFACTS / "stage11032_next_root_support_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_strict_eval.json"
EXECUTION_JSON = ARTIFACTS / "stage11032_next_root_support_probe" / "bounded_decoder_probe" / "execution_result.json"
RESERVED_ROWS = ARTIFACTS / "stage11030_next_root_support_package" / "reserved_next_root_candidates.jsonl"

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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def metric_block(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get(field), bool)]
    correct = sum(1 for row in scored if row.get(field) is True)
    return {
        "rows": len(rows),
        "scored_rows": len(scored),
        "correct": correct,
        "exact_accuracy": (correct / len(scored)) if scored else None,
    }


def group_metrics(rows: list[dict[str, Any]], group_field: str, result_field: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(group_field) or "unknown")].append(row)
    return {key: metric_block(bucket, result_field) for key, bucket in sorted(buckets.items())}


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer, dict[str, Any]]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    model.to(EVAL_DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tokenizer, init_card


def main() -> None:
    execution = load_json(EXECUTION_JSON)
    overlay_eval = load_json(OVERLAY_EVAL_JSON)
    overlay_strict = load_json(OVERLAY_STRICT_JSON)
    reserved_rows = load_jsonl(RESERVED_ROWS)

    model, tokenizer, init_card = load_runtime()
    reserved_card = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=reserved_rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name="reserved_candidate_slice",
        bounded_choice_aux_source="encoder_option_retrieval",
        eval_batch_size=8,
    )

    row_cards = list(reserved_card.get("row_cards") or [])
    write_json(RESERVED_AUDIT_JSON, reserved_card)
    write_jsonl(RESERVED_ROWS_JSONL, row_cards)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Audit the stage11032 runtime against the unchanged overlay and the enlarged 9-row reserved next-root candidate slice.",
            "Separate overlay preservation from candidate-slice movement so the next-root support package can be judged honestly.",
        ],
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "execution_result": rel(EXECUTION_JSON),
            "overlay_eval": rel(OVERLAY_EVAL_JSON),
            "overlay_strict": rel(OVERLAY_STRICT_JSON),
            "reserved_rows": rel(RESERVED_ROWS),
        },
        "overlay_result": {
            "eval_accuracy": overlay_eval.get("constrained_choice_top1_accuracy"),
            "strict_accuracy": overlay_strict.get("constrained_choice_top1_accuracy"),
            "eval_miss_rows": [r.get("row_id") for r in overlay_eval.get("row_cards", []) if not r.get("constrained_choice_match")],
            "strict_miss_rows": [r.get("row_id") for r in overlay_strict.get("row_cards", []) if not r.get("constrained_choice_match")],
        },
        "reserved_candidate_result": {
            "overall": metric_block(row_cards, "constrained_choice_match"),
            "by_language": group_metrics(row_cards, "language_family", "constrained_choice_match"),
            "by_repo_family": group_metrics(row_cards, "repo_family", "constrained_choice_match"),
            "rows_with_target_rank_1": reserved_card.get("rows_with_target_rank_1"),
            "mismatches": [
                {k: row.get(k) for k in ["row_id", "target_text", "constrained_choice_top1_label", "target_rank_full_vocab", "full_vocab_top1_text"]}
                for row in row_cards
                if row.get("constrained_choice_match") is False
            ],
        },
        "headline": {
            "overlay_eval_accuracy": overlay_eval.get("constrained_choice_top1_accuracy"),
            "overlay_strict_accuracy": overlay_strict.get("constrained_choice_top1_accuracy"),
            "reserved_candidate_accuracy": reserved_card.get("constrained_choice_top1_accuracy"),
        },
        "runtime_bundle": {
            "weights_sha256": ((execution.get("summary") or {}).get("runtime_model_bundle") or {}).get("weights_sha256"),
            "runtime_initialization": init_card,
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "reserved_audit_json": rel(RESERVED_AUDIT_JSON),
            "reserved_rows_jsonl": rel(RESERVED_ROWS_JSONL),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

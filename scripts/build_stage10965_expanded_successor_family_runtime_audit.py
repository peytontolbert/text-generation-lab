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
STAGE = 10965
NAME = "stage10965_expanded_successor_family_runtime_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "expanded_successor_family_runtime_audit.json"
ROWS_JSONL = OUT_DIR / "expanded_successor_family_rows.jsonl"

RUNTIME_BUNDLE = ARTIFACTS / "stage10960_clean_explicit_ledger_support_probe" / "runtime_model" / "runtime_model_bundle.json"
FAMILY_ROWS = ARTIFACTS / "stage10963_expanded_evidence_successor_family" / "expanded_successor_rows.jsonl"

TORCH_THREADS = max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))
torch.set_num_threads(TORCH_THREADS)
torch.set_num_interop_threads(max(1, min(4, TORCH_THREADS)))
EVAL_DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get("constrained_choice_match"), bool)]
    correct = sum(1 for row in scored if row.get("constrained_choice_match") is True)
    return {
        "rows": len(rows),
        "scored_rows": len(scored),
        "correct": correct,
        "exact_accuracy": (correct / len(scored)) if scored else None,
    }


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer, dict[str, Any]]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    model.to(EVAL_DEVICE)
    model.eval()
    return model, tokenizer, init_card


def main() -> None:
    family_rows = []
    for row in load_jsonl(FAMILY_ROWS):
        updated = dict(row)
        updated["split"] = "strict_eval"
        family_rows.append(updated)
    model, tokenizer, init_card = load_runtime()
    audit = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=family_rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name="expanded_successor_family",
        bounded_choice_aux_source="encoder_option_retrieval",
        eval_batch_size=8,
    )
    row_cards = list(audit.get("row_cards") or [])
    write_jsonl(ROWS_JSONL, row_cards)

    by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_queue: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in row_cards:
        row_id = str(row.get("row_id") or "")
        parts = row_id.split("::")
        queue_id = parts[1] if len(parts) > 1 else "unknown"
        variant = parts[-1] if parts else "unknown"
        by_variant[variant].append(row)
        by_queue[queue_id].append(row)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "runtime_bundle": rel(RUNTIME_BUNDLE),
        "runtime_initialization": init_card,
        "overall": summarize(row_cards),
        "by_variant": {variant: summarize(rows) for variant, rows in sorted(by_variant.items())},
        "by_queue": {queue_id: summarize(rows) for queue_id, rows in sorted(by_queue.items())},
        "findings": [
            "If ledger variants outperform raw variants on the same roots, visible verifier materialization is still a meaningful lever.",
            "If all variants stay flat on the same roots, the next honest branch is fresh roots or scorer architecture rather than more geometry shuffling.",
        ],
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "rows_jsonl": rel(ROWS_JSONL),
        },
    }
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

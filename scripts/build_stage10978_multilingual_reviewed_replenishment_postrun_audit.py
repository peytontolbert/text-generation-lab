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
STAGE = 10978
NAME = "stage10978_multilingual_reviewed_replenishment_postrun_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "multilingual_reviewed_replenishment_postrun_audit.json"
RUNTIME_BUNDLE = ARTIFACTS / "stage10977_multilingual_reviewed_replenishment_support_probe" / "runtime_model" / "runtime_model_bundle.json"
OVERLAY_VAL = ARTIFACTS / "stage10975_multilingual_reviewed_replenishment_support_package" / "agentkernel_lite_encdec_validation.jsonl"
OVERLAY_STRICT = ARTIFACTS / "stage10975_multilingual_reviewed_replenishment_support_package" / "agentkernel_lite_encdec_strict_eval.jsonl"
CANDIDATE_ROWS = ARTIFACTS / "stage10974_multilingual_reviewed_replenishment_package" / "strict_candidate_rows.jsonl"

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


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get("constrained_choice_match"), bool)]
    correct = sum(1 for row in scored if row.get("constrained_choice_match") is True)
    return {"rows": len(rows), "scored_rows": len(scored), "correct": correct, "exact_accuracy": (correct / len(scored)) if scored else None}


def infer_language(row: dict[str, Any]) -> str:
    language = str(row.get("language_family") or "")
    if language:
        return language
    row_id = str(row.get("row_id") or "")
    for candidate in ("python", "c_cpp", "rust", "web_js_ts_html"):
        if candidate in row_id:
            return candidate
    if "cpp_" in row_id or "::cpp" in row_id or "parametergolf" in row_id or "agentkernel" in row_id:
        return "c_cpp"
    return "unknown"


def by_language(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[infer_language(row)].append(row)
    return {k: summarize(v) for k, v in sorted(buckets.items())}


def load_runtime():
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
    model, tokenizer, init_card = load_runtime()
    overlay_eval = _write_bounded_choice_eval_audit(OUT_DIR, model=model, rows=load_jsonl(OVERLAY_VAL), tokenizer=tokenizer, max_encoder_tokens=768, max_decoder_tokens=8, split_name="eval_raw_contract", bounded_choice_aux_source="encoder_option_retrieval", eval_batch_size=8)
    overlay_strict = _write_bounded_choice_eval_audit(OUT_DIR, model=model, rows=load_jsonl(OVERLAY_STRICT), tokenizer=tokenizer, max_encoder_tokens=768, max_decoder_tokens=8, split_name="strict_eval_raw_contract", bounded_choice_aux_source="encoder_option_retrieval", eval_batch_size=8)
    candidates = []
    for row in load_jsonl(CANDIDATE_ROWS):
        updated = dict(row)
        updated["split"] = "strict_eval"
        candidates.append(updated)
    candidate_card = _write_bounded_choice_eval_audit(OUT_DIR, model=model, rows=candidates, tokenizer=tokenizer, max_encoder_tokens=768, max_decoder_tokens=8, split_name="reviewed_replenishment_candidate_slice", bounded_choice_aux_source="encoder_option_retrieval", eval_batch_size=8)
    candidate_rows = list(candidate_card.get("row_cards") or [])
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "runtime_bundle": rel(RUNTIME_BUNDLE),
        "runtime_initialization": init_card,
        "overlay": {
            "eval_accuracy": overlay_eval.get("constrained_choice_top1_accuracy"),
            "strict_accuracy": overlay_strict.get("constrained_choice_top1_accuracy"),
            "strict_miss_rows": [r.get("row_id") for r in overlay_strict.get("row_cards", []) if not r.get("constrained_choice_match")],
        },
        "reviewed_replenishment_candidates": {
            "overall": summarize(candidate_rows),
            "by_language": by_language(candidate_rows),
            "miss_rows": [r.get("row_id") for r in candidate_rows if not r.get("constrained_choice_match")],
        },
        "findings": [
            "A useful result preserves the frozen 23-row overlay and improves the 6-row reviewed replenishment candidate slice.",
            "If the overlay stays flat and the replenishment candidates stay flat, the next move is a larger support curriculum or new heldout supply, not another tiny probe on the same geometry.",
        ],
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

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
STAGE = 10969
NAME = "stage10969_role_bias_postrun_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "role_bias_postrun_audit.json"

RUNTIME_BUNDLE = ARTIFACTS / "stage10968_role_bias_support_probe" / "runtime_model" / "runtime_model_bundle.json"
OVERLAY_VAL = ARTIFACTS / "stage10934_explicit_verifier_ledger_support_package" / "agentkernel_lite_encdec_validation.jsonl"
OVERLAY_STRICT = ARTIFACTS / "stage10934_explicit_verifier_ledger_support_package" / "agentkernel_lite_encdec_strict_eval.jsonl"
SLICE_ROWS = ARTIFACTS / "stage10915_evidence_successor_strict_candidates" / "strict_candidate_rows.jsonl"
FAMILY_ROWS = ARTIFACTS / "stage10963_expanded_evidence_successor_family" / "expanded_successor_rows.jsonl"

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


def by_group(rows: list[dict[str, Any]], key_fn) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[key_fn(row)].append(row)
    return {key: summarize(bucket) for key, bucket in sorted(buckets.items())}


def load_runtime():
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    if metadata.get("bounded_choice_aux_source") == "encoder_option_retrieval_role_bias" and not hasattr(model, "bounded_choice_role_head"):
        model.bounded_choice_role_head = torch.nn.Linear(config.d_model, 3, bias=True)
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    model.to(EVAL_DEVICE)
    model.eval()
    return model, tokenizer, init_card


def main() -> None:
    model, tokenizer, init_card = load_runtime()
    overlay_eval = _write_bounded_choice_eval_audit(OUT_DIR, model=model, rows=load_jsonl(OVERLAY_VAL), tokenizer=tokenizer, max_encoder_tokens=768, max_decoder_tokens=8, split_name="eval_raw_contract", bounded_choice_aux_source="encoder_option_retrieval", eval_batch_size=8)
    overlay_strict = _write_bounded_choice_eval_audit(OUT_DIR, model=model, rows=load_jsonl(OVERLAY_STRICT), tokenizer=tokenizer, max_encoder_tokens=768, max_decoder_tokens=8, split_name="strict_eval_raw_contract", bounded_choice_aux_source="encoder_option_retrieval", eval_batch_size=8)
    slice_card = _write_bounded_choice_eval_audit(OUT_DIR, model=model, rows=load_jsonl(SLICE_ROWS), tokenizer=tokenizer, max_encoder_tokens=768, max_decoder_tokens=8, split_name="successor_slice", bounded_choice_aux_source="encoder_option_retrieval", eval_batch_size=8)
    family_rows = []
    for row in load_jsonl(FAMILY_ROWS):
        updated = dict(row)
        updated["split"] = "strict_eval"
        family_rows.append(updated)
    family_card = _write_bounded_choice_eval_audit(OUT_DIR, model=model, rows=family_rows, tokenizer=tokenizer, max_encoder_tokens=768, max_decoder_tokens=8, split_name="expanded_successor_family", bounded_choice_aux_source="encoder_option_retrieval", eval_batch_size=8)
    family_row_cards = list(family_card.get("row_cards") or [])
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
        "successor_slice": summarize(list(slice_card.get("row_cards") or [])),
        "expanded_family": {
            "overall": summarize(family_row_cards),
            "by_queue": by_group(family_row_cards, lambda row: (str(row.get("row_id") or "").split("::")[1] if "::" in str(row.get("row_id") or "") else "unknown")),
            "by_variant": by_group(family_row_cards, lambda row: (str(row.get("row_id") or "").split("::")[-1] if "::" in str(row.get("row_id") or "") else "unknown")),
        },
        "findings": [
            "A meaningful role-bias result must preserve the 22/23 strict overlay and improve either the 3-row successor slice or the 24-row expanded family.",
            "If neither surface moves, the next honest branch is fresh roots rather than more scorer shaping on the current reviewed supply.",
        ],
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

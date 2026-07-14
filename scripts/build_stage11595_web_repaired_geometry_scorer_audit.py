#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _write_bounded_choice_eval_audit

ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11595
NAME = "stage11595_web_repaired_geometry_scorer_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_repaired_geometry_scorer_audit.json"
RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
ROWSETS = {
    "repaired_train": ART / "stage11594_web_verifier_attached_repaired_geometry_package/web_verifier_attached_repaired_train_rows.jsonl",
    "repaired_successor_strict": ART / "stage11594_web_verifier_attached_repaired_geometry_package/web_verifier_attached_repaired_successor_strict_rows.jsonl",
    "filtered_strict": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "residual_bank": ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl",
}
SOURCES = [
    "encoder_option_retrieval_evidence_judgment_head",
    "encoder_option_retrieval",
    "encoder_option_retrieval_verifier_conditioned",
    "encoder_option_retrieval_dynamic_productized",
    "encoder_option_retrieval_semantic_candidate_head",
]

torch.set_num_threads(max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8"))))
try:
    torch.set_num_interop_threads(max(1, min(4, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))))
except RuntimeError:
    pass
DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out.setdefault("prompt_text", out.get("input_text") or "")
    out.setdefault("decoder_text", out.get("target_text") or out.get("bounded_choice_target_label") or "")
    source = dict(out.get("standalone_projection_source") or {})
    source.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = source
    if not isinstance(out.get("target"), dict):
        out["target"] = {"decoder_text": out.get("decoder_text"), "bounded_choice_target_label": out.get("bounded_choice_target_label") or out.get("target_text")}
    return out


def load_runtime() -> tuple[Any, Any, dict[str, Any]]:
    bundle = load_json(RUNTIME)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME, model=model)
    model.to(DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tokenizer, init_card


def metric(card: dict[str, Any]) -> dict[str, Any]:
    row_cards = card.get("row_cards") or []
    misses = [row.get("row_id") for row in row_cards if row.get("constrained_choice_match") is not True]
    return {
        "rows": card.get("rows"),
        "correct": card.get("constrained_choice_correct"),
        "coverage": card.get("constrained_choice_coverage"),
        "accuracy": card.get("constrained_choice_top1_accuracy"),
        "target_counts": dict(Counter(str(row.get("bounded_choice_target_label")) for row in row_cards)),
        "prediction_counts": dict(Counter(str(row.get("constrained_choice_top1_label")) for row in row_cards)),
        "miss_count": len(misses),
        "miss_examples": misses[:10],
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rowsets = {name: [normalize_row(row) for row in load_jsonl(path)] for name, path in ROWSETS.items()}
    model, tokenizer, init_card = load_runtime()
    results: dict[str, Any] = {}
    for source in SOURCES:
        results[source] = {}
        for name, rows in rowsets.items():
            try:
                card = _write_bounded_choice_eval_audit(
                    OUT / source,
                    model=model,
                    rows=rows,
                    tokenizer=tokenizer,
                    max_encoder_tokens=768,
                    max_decoder_tokens=16,
                    split_name=name,
                    bounded_choice_aux_source=source,
                    eval_batch_size=8,
                )
                results[source][name] = metric(card)
            except Exception as exc:
                results[source][name] = {"error": type(exc).__name__, "message": str(exc)}
    selected = results.get("encoder_option_retrieval_evidence_judgment_head", {})
    strict_correct = int((selected.get("repaired_successor_strict") or {}).get("correct") or 0)
    train_correct = int((selected.get("repaired_train") or {}).get("correct") or 0)
    decision = "repaired_geometry_train_probe_not_ready" if strict_correct == 0 and train_correct < 80 else "repaired_geometry_train_probe_candidate"
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "device": str(DEVICE),
        "runtime": rel(RUNTIME),
        "results": results,
        "runtime_initialization": init_card,
        "interpretation": [
            "If selected scorer is near-zero on repaired train and strict rows, training would still be a scorer/objective change, not simple support data ingestion.",
            "Dynamic/productized scorer may be diagnostic but is not selected product scorer unless preservation gates also pass.",
        ],
        "source_artifacts": {name: rel(path) for name, path in ROWSETS.items()},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    compact = {source: {name: {"correct": card.get("correct"), "rows": card.get("rows"), "pred": card.get("prediction_counts"), "error": card.get("error")} for name, card in by_set.items()} for source, by_set in results.items()}
    print(json.dumps({"decision": decision, "compact": compact}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

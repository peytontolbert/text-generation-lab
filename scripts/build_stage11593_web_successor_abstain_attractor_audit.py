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
STAGE = 11593
NAME = "stage11593_web_successor_abstain_attractor_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_successor_abstain_attractor_audit.json"
RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
ROWS = ART / "stage11590_web_moderate_task_aware_contrast_probe_request/web_moderate_task_aware_contrast_successor_strict_rows.jsonl"
SCORER = "encoder_option_retrieval_evidence_judgment_head"

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


def options(row: dict[str, Any]) -> list[dict[str, Any]]:
    return list(((row.get("standalone_projection_source") or {}).get("opaque_options") or []))


def with_options(row: dict[str, Any], opts: list[dict[str, Any]], suffix: str) -> dict[str, Any]:
    out = dict(row)
    out["row_id"] = f"{row.get('row_id')}::{suffix}"
    src = dict(out.get("standalone_projection_source") or {})
    src["opaque_options"] = opts
    out["standalone_projection_source"] = src
    return out


def variant_rows(rows: list[dict[str, Any]], variant: str) -> list[dict[str, Any]]:
    transformed: list[dict[str, Any]] = []
    for row in rows:
        opts = [dict(opt) for opt in options(row)]
        if variant == "original":
            transformed.append(with_options(row, opts, variant))
            continue
        if variant == "abstain_removed":
            kept = [opt for opt in opts if str(opt.get("semantic_role") or "") != "abstain_insufficient_evidence"]
            transformed.append(with_options(row, kept, variant))
            continue
        if variant == "abstain_value_neutralized":
            for opt in opts:
                if str(opt.get("semantic_role") or "") == "abstain_insufficient_evidence":
                    opt["value"] = "opaque_non_answer_candidate"
                    opt["text"] = "opaque_non_answer_candidate"
            transformed.append(with_options(row, opts, variant))
            continue
        if variant == "semantic_role_as_value":
            for opt in opts:
                role = str(opt.get("semantic_role") or opt.get("value") or "")
                opt["value"] = role
                opt["text"] = role
            transformed.append(with_options(row, opts, variant))
            continue
        raise ValueError(variant)
    return transformed


def metric(card: dict[str, Any]) -> dict[str, Any]:
    row_cards = card.get("row_cards") or []
    return {
        "rows": card.get("rows"),
        "correct": card.get("constrained_choice_correct"),
        "coverage": card.get("constrained_choice_coverage"),
        "accuracy": card.get("constrained_choice_top1_accuracy"),
        "target_counts": dict(Counter(str(row.get("bounded_choice_target_label")) for row in row_cards)),
        "prediction_counts": dict(Counter(str(row.get("constrained_choice_top1_label")) for row in row_cards)),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    base_rows = [normalize_row(row) for row in load_jsonl(ROWS)]
    model, tokenizer, init_card = load_runtime()
    variants = ["original", "abstain_removed", "abstain_value_neutralized", "semantic_role_as_value"]
    results: dict[str, Any] = {}
    for variant in variants:
        rows = variant_rows(base_rows, variant)
        card = _write_bounded_choice_eval_audit(
            OUT,
            model=model,
            rows=rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=16,
            split_name=variant,
            bounded_choice_aux_source=SCORER,
            eval_batch_size=8,
        )
        results[variant] = metric(card)
    decision = "abstain_option_geometry_is_material" if results["abstain_removed"].get("correct", 0) > results["original"].get("correct", 0) else "abstain_option_geometry_not_sufficient"
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "device": str(DEVICE),
        "scorer": SCORER,
        "runtime": rel(RUNTIME),
        "rows": rel(ROWS),
        "results": results,
        "runtime_initialization": init_card,
        "interpretation": [
            "original tests the actual successor strict geometry.",
            "abstain_removed tests whether option D is dominating the selected scorer.",
            "abstain_value_neutralized tests lexical ABSTAIN_INSUFFICIENT_EVIDENCE attraction while preserving four options.",
            "semantic_role_as_value is diagnostic only; it exposes hidden role metadata and is not promotable as a maintainer eval claim.",
        ],
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "results": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

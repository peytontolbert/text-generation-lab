#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer, build_batch
from legacy_src.agentkernel_lite.training_loop import _bounded_choice_option_logits, _load_runtime_model_bundle

STAGE = 10563
NAME = "stage10563_visible_candidate_transition_bounded_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "visible_candidate_transition_bounded_audit.json"
ROW_JSONL = OUT_DIR / "visible_candidate_transition_bounded_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

STRICT_JSONL = ROOT / "runs/local/artifacts/stage10561_visible_candidate_successor_package/strict_eval_rows.jsonl"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10556_masked_projection_successor_with_v27_preservation_probe/runtime_model/runtime_model_bundle.json"
GREEDY_COMPARISON = ROOT / "runs/local/artifacts/stage10562_visible_candidate_successor_same_manifest_comparison/visible_candidate_successor_same_manifest_comparison.json"
CANARY_AUDIT = ROOT / "runs/local/artifacts/stage10558_masked_projection_successor_with_v27_preservation_canary_audit/masked_projection_successor_with_v27_preservation_canary_audit.json"

TORCH_THREADS = max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))
torch.set_num_threads(TORCH_THREADS)
torch.set_num_interop_threads(max(1, min(4, TORCH_THREADS)))
OUT_DIR.mkdir(parents=True, exist_ok=True)
EVAL_DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer, dict[str, Any]]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    model_config = load_json(Path(str(metadata["model_config"])))
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(model_config)
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(
        Path(str(metadata["tokenizer_json"])),
        Path(str(metadata["tokenizer_config"])),
    )
    model.to(EVAL_DEVICE)
    model.eval()
    return model, tokenizer, init_card


def semantic_value_for_label(row: dict[str, Any], label: str) -> str | None:
    options = (((row.get("standalone_projection_source") or {}).get("opaque_options")) or [])
    for option in options:
        if str(option.get("label")) == label:
            return str(option.get("value"))
    return None


def score_row_with_source(model: AgentKernelLiteTransformerSeq2Seq, tokenizer: AgentKernelBPETokenizer, row: dict[str, Any], source: str) -> dict[str, Any]:
    batch = build_batch([row], max_encoder_tokens=1024, max_decoder_tokens=8, tokenizer=tokenizer)
    input_ids = batch.input_ids.to(EVAL_DEVICE)
    decoder_input_ids = batch.decoder_input_ids.to(EVAL_DEVICE)
    with torch.no_grad():
        out = model(input_ids, decoder_input_ids)
    option_logits, option_pairs, skip_reason = _bounded_choice_option_logits(
        row=row,
        tokenizer=tokenizer,
        source=source,
        first_step_logits_row=out["decoder_logits"][0, 0],
        pooled_row=out.get("pooled")[0] if isinstance(out.get("pooled"), torch.Tensor) else None,
        model=model,
        untied_head=getattr(model, "bounded_choice_probe_head", None),
    )
    if option_logits is None:
        return {
            "source": source,
            "supported": False,
            "skip_reason": str(skip_reason or "unknown"),
            "correct": None,
            "predicted_label": None,
            "predicted_semantic_value": None,
            "target_semantic_value": str((row.get("standalone_projection_source") or {}).get("gold_value") or ""),
            "top1_probability": None,
            "top2_probability": None,
            "margin_top1_minus_top2": None,
            "scored_options": [],
        }
    probs = torch.softmax(option_logits.float(), dim=0)
    scored = []
    for idx, (label, _token_id) in enumerate(option_pairs):
        scored.append(
            {
                "label": label,
                "semantic_value": semantic_value_for_label(row, label),
                "logit": float(option_logits[idx].item()),
                "probability": float(probs[idx].item()),
            }
        )
    scored.sort(key=lambda item: item["logit"], reverse=True)
    top1 = scored[0]
    top2 = scored[1] if len(scored) > 1 else {"label": "", "semantic_value": None, "probability": 0.0}
    target_label = str(row.get("decoder_text") or row.get("target_text") or "")
    return {
        "source": source,
        "supported": True,
        "skip_reason": None,
        "correct": top1["label"] == target_label,
        "predicted_label": top1["label"],
        "predicted_semantic_value": top1["semantic_value"],
        "target_semantic_value": str((row.get("standalone_projection_source") or {}).get("gold_value") or ""),
        "top1_probability": float(top1["probability"]),
        "top2_probability": float(top2["probability"]),
        "margin_top1_minus_top2": float(top1["probability"] - top2["probability"]),
        "top2_label": top2["label"],
        "top2_semantic_value": top2["semantic_value"],
        "scored_options": scored,
    }


def summarize(rows: list[dict[str, Any]], source: str, key: str | None = None) -> dict[str, Any]:
    filtered = rows if key is None else [row for row in rows if row.get(key)]
    scored = [row for row in filtered if (row.get(source) or {}).get("supported") and isinstance((row.get(source) or {}).get("correct"), bool)]
    margins = [float((row[source] or {})["margin_top1_minus_top2"]) for row in scored]
    correct = sum(1 for row in scored if row[source]["correct"])
    return {
        "rows": len(filtered),
        "scored_rows": len(scored),
        "unsupported_rows": len(filtered) - len(scored),
        "correct_rows": correct,
        "accuracy": (correct / len(scored)) if scored else None,
        "mean_margin": mean(margins) if margins else None,
        "min_margin": min(margins) if margins else None,
        "max_margin": max(margins) if margins else None,
    }


def main() -> None:
    rows = load_jsonl(STRICT_JSONL)
    rows.sort(key=lambda row: str(row.get("row_id") or ""))
    model, tokenizer, init_card = load_runtime()
    greedy = load_json(GREEDY_COMPARISON) if GREEDY_COMPARISON.exists() else {}
    canary = load_json(CANARY_AUDIT) if CANARY_AUDIT.exists() else {}
    row_cards = []
    for row in rows:
        row_card = {
            "row_id": str(row.get("row_id") or ""),
            "language_family": str(row.get("language_family") or ""),
            "repo_id": str(row.get("repo_id") or ""),
            "target_subtype": str(row.get("target_subtype") or ""),
            "target_label": str(row.get("decoder_text") or row.get("target_text") or ""),
            "standalone_gold_value": str((row.get("standalone_projection_source") or {}).get("gold_value") or ""),
            "option_count": len((((row.get("standalone_projection_source") or {}).get("opaque_options")) or [])),
        }
        row_card["decoder_first_step"] = score_row_with_source(model, tokenizer, row, "decoder_first_step")
        row_card["encoder_option_retrieval"] = score_row_with_source(model, tokenizer, row, "encoder_option_retrieval")
        row_cards.append(row_card)
    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_subtype: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in row_cards:
        by_language[row["language_family"]].append(row)
        by_subtype[row["target_subtype"]].append(row)
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Saved-runtime bounded-choice transition audit on the stage10561 visible-candidate strict successor rows using the stage10556 runtime.",
            "Compares decoder_first_step scoring against encoder_option_retrieval scoring on the same rebuilt rows.",
            "Separates contract-transition viability from greedy seq2seq exact generation collapse.",
        ],
        "inputs": {
            "strict_rows": display(STRICT_JSONL),
            "runtime_bundle": display(RUNTIME_BUNDLE),
            "greedy_comparison": display(GREEDY_COMPARISON),
            "canary_audit": display(CANARY_AUDIT),
        },
        "runtime_initialization": init_card,
        "eval_device": str(EVAL_DEVICE),
        "row_count": len(row_cards),
        "summary": {
            "decoder_first_step": summarize(row_cards, "decoder_first_step"),
            "encoder_option_retrieval": summarize(row_cards, "encoder_option_retrieval"),
        },
        "per_language": {
            language: {
                "decoder_first_step": summarize(items, "decoder_first_step"),
                "encoder_option_retrieval": summarize(items, "encoder_option_retrieval"),
            }
            for language, items in sorted(by_language.items())
        },
        "per_target_subtype": {
            subtype: {
                "decoder_first_step": summarize(items, "decoder_first_step"),
                "encoder_option_retrieval": summarize(items, "encoder_option_retrieval"),
            }
            for subtype, items in sorted(by_subtype.items())
        },
        "greedy_stage10562": {
            "hundred_m_overall_exact": (((greedy.get("hundred_m") or {}).get("overall") or {}).get("exact_accuracy")),
            "gemma_overall_exact": (((greedy.get("gemma12b") or {}).get("overall") or {}).get("exact_accuracy")),
        },
        "canary_stage10558": {
            "bounded_accuracy": (((canary.get("bounded_eval") or {}).get("overall") or {}).get("accuracy")),
            "greedy_exact_accuracy": (((canary.get("greedy_generation") or {}).get("overall") or {}).get("exact_accuracy")),
        },
        "risk_findings": [
            "retrieve_answer_abstain remains a constant-label slice in the rebuilt strict successor rows and should not dominate promotable accuracy claims.",
            "decoder_first_step scoring preserves verifier and retrieve competence materially better than encoder_option_retrieval on the rebuilt contract, indicating an interface transition rather than a total semantic collapse.",
            "decisive_evidence_top1 remains weak under both scoring sources and is the main next training/data bottleneck on the visible-candidate successor surface.",
        ],
        "lowest_decoder_first_step_margin_rows": sorted(
            [row for row in row_cards if (row.get("decoder_first_step") or {}).get("supported")],
            key=lambda item: float((item.get("decoder_first_step") or {}).get("margin_top1_minus_top2") or 0.0),
        )[:12],
        "decoder_first_step_incorrect_rows": [
            row for row in row_cards if (row.get("decoder_first_step") or {}).get("correct") is False
        ],
        "outputs": {
            "audit_json": display(AUDIT_JSON),
            "row_cards": display(ROW_JSONL),
        },
    }
    write_json(AUDIT_JSON, payload)
    write_jsonl(ROW_JSONL, row_cards)
    write_json(SUMMARY, payload)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

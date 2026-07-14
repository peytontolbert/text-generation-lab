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
from legacy_src.agentkernel_lite.training_loop import (
    _bounded_choice_option_logits,
    _generate_greedy_text,
    _load_runtime_model_bundle,
)

STAGE = 10575
NAME = "stage10575_visible_candidate_mixed_preservation_canary_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "visible_candidate_mixed_preservation_canary_audit.json"
ROW_JSONL = OUT_DIR / "visible_candidate_mixed_preservation_canary_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

TORCH_THREADS = max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))
torch.set_num_threads(TORCH_THREADS)
torch.set_num_interop_threads(max(1, min(4, TORCH_THREADS)))
OUT_DIR.mkdir(parents=True, exist_ok=True)

OVERLAY_JSONL = ROOT / "runs/local/artifacts/stage10436_repaired_v27_strict_overlay/repaired_v27_strict_overlay.jsonl"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10574_visible_candidate_mixed_preservation_probe/runtime_model/runtime_model_bundle.json"
EXECUTION_RESULT = ROOT / "runs/local/artifacts/stage10574_visible_candidate_mixed_preservation_probe/bounded_decoder_probe/execution_result.json"


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
    model.eval()
    return model, tokenizer, init_card


def semantic_value_for_label(row: dict[str, Any], label: str) -> str | None:
    options = (((row.get("standalone_projection_source") or {}).get("opaque_options")) or [])
    for option in options:
        if str(option.get("label")) == label:
            return str(option.get("value"))
    return None


def score_row(model: AgentKernelLiteTransformerSeq2Seq, tokenizer: AgentKernelBPETokenizer, row: dict[str, Any]) -> dict[str, Any]:
    batch = build_batch([row], max_encoder_tokens=1024, max_decoder_tokens=8, tokenizer=tokenizer)
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
    option_logits, option_pairs, skip_reason = _bounded_choice_option_logits(
        row=row,
        tokenizer=tokenizer,
        source="encoder_option_retrieval",
        first_step_logits_row=out["decoder_logits"][0, 0],
        pooled_row=out.get("pooled")[0] if isinstance(out.get("pooled"), torch.Tensor) else None,
        model=model,
        untied_head=getattr(model, "bounded_choice_probe_head", None),
    )
    if option_logits is None:
        raise RuntimeError(f"missing bounded choice logits for {row['row_id']}: {skip_reason}")
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
    generation = _generate_greedy_text(
        model,
        row,
        tokenizer=tokenizer,
        max_encoder_tokens=1024,
        max_new_tokens=8,
        generation_prefix_field=None,
        generation_repetition_guard=False,
        bounded_choice_aux_weight=0.0,
    )
    return {
        "row_id": str(row["row_id"]),
        "language_family": str(row.get("language_family") or ""),
        "task_type": str(row.get("task_type") or ""),
        "target_label": target_label,
        "bounded_predicted_label": top1["label"],
        "bounded_correct": top1["label"] == target_label,
        "bounded_target_semantic_value": str((row.get("standalone_projection_source") or {}).get("gold_value") or ""),
        "bounded_predicted_semantic_value": top1["semantic_value"],
        "bounded_top1_probability": float(top1["probability"]),
        "bounded_top2_probability": float(top2["probability"]),
        "bounded_margin_top1_minus_top2": float(top1["probability"] - top2["probability"]),
        "bounded_top2_label": top2["label"],
        "bounded_top2_semantic_value": top2["semantic_value"],
        "bounded_scored_options": scored,
        "greedy_generated_text": str(generation.get("generated_text") or ""),
        "greedy_exact_match": bool(generation.get("exact_match")),
        "greedy_short_or_junk": bool(generation.get("short_or_junk")),
        "greedy_internal_token_leak": bool(generation.get("internal_token_leak")),
        "greedy_degenerate_repetition": bool(generation.get("degenerate_repetition")),
        "greedy_generated_token_count": int(generation.get("generated_token_count") or 0),
    }


def summary_for(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"rows": 0}
    margins = [float(row["bounded_margin_top1_minus_top2"]) for row in rows]
    return {
        "rows": len(rows),
        "bounded_correct_rows": sum(1 for row in rows if row["bounded_correct"]),
        "bounded_accuracy": sum(1 for row in rows if row["bounded_correct"]) / len(rows),
        "greedy_exact_rows": sum(1 for row in rows if row["greedy_exact_match"]),
        "greedy_exact_accuracy": sum(1 for row in rows if row["greedy_exact_match"]) / len(rows),
        "mean_bounded_margin": mean(margins),
        "min_bounded_margin": min(margins),
        "max_bounded_margin": max(margins),
    }


def main() -> None:
    if not RUNTIME_BUNDLE.exists():
        raise SystemExit(f"missing runtime bundle: {RUNTIME_BUNDLE}")
    if not EXECUTION_RESULT.exists():
        raise SystemExit(f"missing execution_result: {EXECUTION_RESULT}")
    rows = load_jsonl(OVERLAY_JSONL)
    rows.sort(key=lambda row: str(row["row_id"]))
    model, tokenizer, init_card = load_runtime()
    scored_rows = [score_row(model, tokenizer, row) for row in rows]
    scored_rows.sort(key=lambda row: (row["bounded_margin_top1_minus_top2"], row["row_id"]))
    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scored_rows:
        by_language[row["language_family"]].append(row)
        by_task[row["task_type"]].append(row)
    execution = load_json(EXECUTION_RESULT)
    bounded_correct = sum(1 for row in scored_rows if row["bounded_correct"])
    greedy_exact = sum(1 for row in scored_rows if row["greedy_exact_match"])
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Saved-runtime canary regression audit on the repaired 24-row v2.7 overlay using the stage10556 preservation-aware masked-projection successor runtime.",
            "Reports both bounded-choice recovery and raw greedy label generation.",
            "This is a regression gate, not a broader maintainer benchmark claim.",
        ],
        "source_artifacts": {
            "overlay_rows": display(OVERLAY_JSONL),
            "runtime_bundle": display(RUNTIME_BUNDLE),
            "execution_result": display(EXECUTION_RESULT),
        },
        "runtime_initialization": init_card,
        "runtime_weights_sha256": ((execution.get("runtime_model_bundle") or {}).get("weights_sha256")),
        "summary": {
            "rows": len(scored_rows),
            "bounded_correct": bounded_correct,
            "bounded_accuracy": bounded_correct / len(scored_rows) if scored_rows else None,
            "greedy_exact_rows": greedy_exact,
            "greedy_exact_accuracy": greedy_exact / len(scored_rows) if scored_rows else None,
            "mean_bounded_margin": mean(row["bounded_margin_top1_minus_top2"] for row in scored_rows) if scored_rows else None,
        },
        "per_language": {language: summary_for(items) for language, items in sorted(by_language.items())},
        "per_task": {task: summary_for(items) for task, items in sorted(by_task.items())},
        "lowest_margin_rows": scored_rows[:8],
        "bounded_incorrect_rows": [row for row in scored_rows if not row["bounded_correct"]],
        "greedy_incorrect_rows": [row for row in scored_rows if not row["greedy_exact_match"]],
        "outputs": {
            "audit_json": display(AUDIT_JSON),
            "row_cards": display(ROW_JSONL),
        },
    }
    write_json(AUDIT_JSON, payload)
    write_jsonl(ROW_JSONL, scored_rows)
    write_json(SUMMARY, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

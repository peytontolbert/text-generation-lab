#!/usr/bin/env python3
from __future__ import annotations

import json
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

STAGE = 10438
NAME = "stage10438_repaired_v27_strict_overlay_saved_runtime_margin_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "repaired_v27_strict_overlay_saved_runtime_margin_audit.json"
ROW_JSONL = OUT_DIR / "repaired_v27_strict_overlay_saved_runtime_margin_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

OVERLAY_JSONL = ROOT / "runs/local/artifacts/stage10436_repaired_v27_strict_overlay/repaired_v27_strict_overlay.jsonl"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/runtime_model/runtime_model_bundle.json"


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


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    model_config = load_json(Path(str(metadata["model_config"])))
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(model_config)
    model = AgentKernelLiteTransformerSeq2Seq(config)
    _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(
        Path(str(metadata["tokenizer_json"])),
        Path(str(metadata["tokenizer_config"])),
    )
    model.eval()
    return model, tokenizer


def semantic_value_for_label(row: dict[str, Any], label: str) -> str | None:
    options = (((row.get("standalone_projection_source") or {}).get("opaque_options")) or [])
    for option in options:
        if str(option.get("label")) == label:
            return str(option.get("value"))
    return None


def summary_for(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"rows": 0}
    margins = [float(row["margin_top1_minus_top2"]) for row in rows]
    return {
        "rows": len(rows),
        "correct_rows": sum(1 for row in rows if row["correct"]),
        "incorrect_rows": sum(1 for row in rows if not row["correct"]),
        "mean_margin": mean(margins),
        "min_margin": min(margins),
        "max_margin": max(margins),
    }


def score_row(model: AgentKernelLiteTransformerSeq2Seq, tokenizer: AgentKernelBPETokenizer, row: dict[str, Any]) -> dict[str, Any]:
    batch = build_batch([row], max_encoder_tokens=768, max_decoder_tokens=8, tokenizer=tokenizer)
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
    top2 = scored[1] if len(scored) > 1 else {"label": "", "semantic_value": None, "logit": 0.0, "probability": 0.0}
    target = str(row.get("decoder_text") or "")
    return {
        "row_id": row["row_id"],
        "language_family": row.get("language_family"),
        "task_type": row.get("task_type"),
        "predicted_label": top1["label"],
        "target_label": target,
        "correct": top1["label"] == target,
        "predicted_semantic_value": top1["semantic_value"],
        "target_semantic_value": str((row.get("standalone_projection_source") or {}).get("gold_value") or ""),
        "top1_probability": float(top1["probability"]),
        "top2_probability": float(top2["probability"]),
        "margin_top1_minus_top2": float(top1["probability"] - top2["probability"]),
        "top2_label": top2["label"],
        "top2_semantic_value": top2["semantic_value"],
        "scored_options": scored,
    }


def main() -> None:
    rows = load_jsonl(OVERLAY_JSONL)
    rows.sort(key=lambda row: str(row["row_id"]))
    model, tokenizer = load_runtime()
    scored_rows = [score_row(model, tokenizer, row) for row in rows]
    scored_rows.sort(key=lambda row: (row["margin_top1_minus_top2"], row["row_id"]))
    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scored_rows:
        by_language[str(row["language_family"])].append(row)
        by_task[str(row["task_type"])].append(row)
    correct = sum(1 for row in scored_rows if row["correct"])
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Saved-runtime scorer audit on the repaired v2.7 strict overlay only.",
            "This checks whether the current 100M runtime preserves its strict performance after leak-hardening rewrites.",
        ],
        "source_artifacts": {
            "overlay_rows": display(OVERLAY_JSONL),
            "runtime_bundle": display(RUNTIME_BUNDLE),
        },
        "summary": {
            "rows": len(scored_rows),
            "correct": correct,
            "accuracy": correct / len(scored_rows) if scored_rows else None,
            "mean_margin": mean(row["margin_top1_minus_top2"] for row in scored_rows) if scored_rows else None,
        },
        "per_language": {language: summary_for(items) for language, items in sorted(by_language.items())},
        "per_task": {task: summary_for(items) for task, items in sorted(by_task.items())},
        "lowest_margin_rows": scored_rows[:8],
        "incorrect_rows": [row for row in scored_rows if not row["correct"]],
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

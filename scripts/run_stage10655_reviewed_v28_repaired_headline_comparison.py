#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq  # noqa: E402
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer, build_batch  # noqa: E402
from legacy_src.agentkernel_lite.training_loop import _bounded_choice_option_logits, _load_runtime_model_bundle  # noqa: E402

STAGE = 10655
NAME = "stage10655_reviewed_v28_repaired_headline_comparison"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_PATH = OUT_DIR / "reviewed_v28_repaired_headline_comparison.json"
ROWS_PATH = OUT_DIR / "reviewed_v28_repaired_headline_rows.jsonl"

ROWS_SOURCE = ROOT / "runs/local/artifacts/stage10654_reviewed_v28_headline_prompt_contract_repair/headline_strict_eval_repaired.jsonl"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/runtime_model/runtime_model_bundle.json"
MODEL_ID = "gemma3:12b"

TORCH_THREADS = max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))
torch.set_num_threads(TORCH_THREADS)
torch.set_num_interop_threads(max(1, min(4, TORCH_THREADS)))
EVAL_DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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


def ollama_generate(*, prompt: str, model: str = MODEL_ID, seed: int = 0, temperature: float = 0.0) -> str:
    payload = json.dumps(
        {"model": model, "prompt": prompt, "stream": False, "options": {"seed": seed, "temperature": temperature}}
    ).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.loads(response.read().decode("utf-8"))
    return str(body.get("response") or "").strip()


def normalize_label(text: str, options: list[dict[str, Any]]) -> str:
    raw = str(text).strip()
    if not raw:
        return ""
    labels = [str(item.get("label") or "").strip() for item in options if str(item.get("label") or "").strip()]
    label_to_value = {
        str(item.get("label") or "").strip(): str(item.get("value") or "").strip()
        for item in options
        if str(item.get("label") or "").strip()
    }
    first_line = raw.splitlines()[0].strip()
    if first_line in labels:
        return first_line
    patterns = [r"\*\*([A-Z])\*\*", r"\b([A-Z])\b(?=\s*[:.])", r"\banswer\s+is\s+([A-Z])\b", r"\boption\s+([A-Z])\b"]
    for pattern in patterns:
        for match in re.finditer(pattern, raw, flags=re.IGNORECASE):
            candidate = match.group(1).upper()
            if candidate in labels:
                return candidate
    lowered = raw.lower()
    for label, value in label_to_value.items():
        if value and value.lower() in lowered:
            return label
    return first_line


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    model_config = load_json(Path(str(metadata["model_config"])))
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(model_config)
    model = AgentKernelLiteTransformerSeq2Seq(config)
    _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    model.to(EVAL_DEVICE)
    model.eval()
    return model, tokenizer


def score_hundred_m_row(model: AgentKernelLiteTransformerSeq2Seq, tokenizer: AgentKernelBPETokenizer, row: dict[str, Any]) -> dict[str, Any]:
    batch = build_batch([row], max_encoder_tokens=768, max_decoder_tokens=8, tokenizer=tokenizer)
    input_ids = batch.input_ids.to(EVAL_DEVICE)
    decoder_input_ids = batch.decoder_input_ids.to(EVAL_DEVICE)
    with torch.no_grad():
        out = model(input_ids, decoder_input_ids)
    option_logits, option_pairs, skip_reason = _bounded_choice_option_logits(
        row=row,
        tokenizer=tokenizer,
        source="encoder_option_retrieval",
        first_step_logits_row=out["decoder_logits"][0, 0],
        pooled_row=out.get("pooled")[0] if isinstance(out.get("pooled"), torch.Tensor) else None,
        model=model,
        untied_head=getattr(model, "bounded_choice_probe_head", None),
    )
    if option_logits is None or not option_pairs:
        return {"predicted_label": "", "correct": False, "skip_reason": skip_reason or "no_option_logits"}
    probs = torch.softmax(option_logits.float(), dim=0)
    scored = []
    for idx, (label, _token_id) in enumerate(option_pairs):
        scored.append(
            {
                "label": str(label),
                "logit": float(option_logits[idx].item()),
                "probability": float(probs[idx].item()),
            }
        )
    scored.sort(key=lambda item: item["logit"], reverse=True)
    predicted_label = scored[0]["label"]
    return {"predicted_label": predicted_label, "correct": predicted_label == str(row.get("target_text") or "")}


def main() -> None:
    rows = load_jsonl(ROWS_SOURCE)
    model, tokenizer = load_runtime()
    result_rows: list[dict[str, Any]] = []
    for row in rows:
        hundred = score_hundred_m_row(model, tokenizer, row)
        gemma_raw = ollama_generate(prompt=str(row["prompt_text"]))
        gemma_label = normalize_label(gemma_raw, list(row.get("opaque_options") or []))
        result_rows.append(
            {
                "row_id": row["row_id"],
                "language_family": row["language_family"],
                "task_type": row["task_type"],
                "target_text": row["target_text"],
                "hundred_m_predicted_label": hundred["predicted_label"],
                "hundred_m_correct": hundred["correct"],
                "gemma12b_predicted_label": gemma_label,
                "gemma12b_correct": gemma_label == str(row["target_text"]),
                "gemma12b_raw_output": gemma_raw,
            }
        )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "rows_source": display(ROWS_SOURCE),
        "runtime_bundle": display(RUNTIME_BUNDLE),
        "model_id": MODEL_ID,
        "hundred_m": metric_block(result_rows, "hundred_m_correct"),
        "gemma12b": metric_block(result_rows, "gemma12b_correct"),
        "delta_exact_accuracy": (metric_block(result_rows, "hundred_m_correct")["exact_accuracy"] or 0.0)
        - (metric_block(result_rows, "gemma12b_correct")["exact_accuracy"] or 0.0),
        "by_language": {
            "hundred_m": group_metrics(result_rows, "language_family", "hundred_m_correct"),
            "gemma12b": group_metrics(result_rows, "language_family", "gemma12b_correct"),
        },
        "by_task_type": {
            "hundred_m": group_metrics(result_rows, "task_type", "hundred_m_correct"),
            "gemma12b": group_metrics(result_rows, "task_type", "gemma12b_correct"),
        },
        "claim_boundary": [
            "This comparison covers only the repaired 24-row headline slice.",
            "The 4 evidence_citation rows use opaque evidence IDs in the prompt contract; other headline rows remain unchanged.",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY_PATH, summary)
    write_jsonl(ROWS_PATH, result_rows)
    print(SUMMARY_PATH)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
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


STAGE = 10916
NAME = "stage10916_evidence_successor_candidate_slice_comparison"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "evidence_successor_candidate_slice_comparison.json"
HUNDRED_ROWS_JSONL = OUT_DIR / "hundred_m_rows.jsonl"
GEMMA_ROWS_JSONL = OUT_DIR / "gemma_rows.jsonl"
COMBINED_ROWS_JSONL = OUT_DIR / "combined_rows.jsonl"

STRICT_ROWS = ROOT / "runs" / "local" / "artifacts" / "stage10915_evidence_successor_strict_candidates" / "strict_candidate_rows.jsonl"
RUNTIME_BUNDLE = ROOT / "runs" / "local" / "artifacts" / "stage10890_flash_attn_alias_safe_multilingual_support_probe" / "runtime_model" / "runtime_model_bundle.json"
MODEL_ID = "gemma3:12b"
OPTION_SOURCE = "encoder_option_retrieval"

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


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def metric_block(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get(field), bool)]
    correct = sum(1 for row in scored if row.get(field) is True)
    return {"rows": len(rows), "scored_rows": len(scored), "correct": correct, "exact_accuracy": (correct / len(scored)) if scored else None}


def group_metrics(rows: list[dict[str, Any]], group_field: str, result_field: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(group_field) or "unknown")].append(row)
    return {key: metric_block(bucket, result_field) for key, bucket in sorted(buckets.items())}


def normalize_label(text: str, options: list[dict[str, Any]]) -> str:
    raw = str(text).strip()
    if not raw:
        return ""
    labels = [str(item.get("label") or "").strip() for item in options if str(item.get("label") or "").strip()]
    first_line = raw.splitlines()[0].strip()
    if first_line in labels:
        return first_line
    for pattern in [r"\*\*([A-Z])\*\*", r"\b([A-Z])\b(?=\s*[:.])", r"\banswer\s+is\s+([A-Z])\b", r"\boption\s+([A-Z])\b"]:
        for match in re.finditer(pattern, raw, flags=re.IGNORECASE):
            candidate = match.group(1).upper()
            if candidate in labels:
                return candidate
    lowered = raw.lower()
    for item in options:
        label = str(item.get("label") or "").strip()
        value = str(item.get("value") or "").strip().lower()
        if label and value and value in lowered:
            return label
    return first_line


def ollama_generate(*, prompt: str, model: str = MODEL_ID, seed: int = 0, temperature: float = 0.0) -> str:
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False, "options": {"seed": seed, "temperature": temperature}}).encode("utf-8")
    request = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.loads(response.read().decode("utf-8"))
    return str(body.get("response") or "").strip()


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
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-existing-gemma", action="store_true")
    args = parser.parse_args()

    rows = load_jsonl(STRICT_ROWS)
    rows.sort(key=lambda row: str(row.get("row_id") or ""))
    model, tokenizer, init_card = load_runtime()
    strict_card = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name="strict_candidate_slice",
        bounded_choice_aux_source=OPTION_SOURCE,
        eval_batch_size=8,
    )
    hundred_rows = list(strict_card.get("row_cards") or [])
    write_jsonl(HUNDRED_ROWS_JSONL, hundred_rows)

    existing = {str(row.get("row_id") or ""): row for row in load_jsonl(GEMMA_ROWS_JSONL)} if args.reuse_existing_gemma else {}
    gemma_rows = []
    for row in rows:
        row_id = str(row.get("row_id") or "")
        options = [item for item in row.get("opaque_options") or [] if isinstance(item, dict)]
        if row_id in existing:
            raw = str(existing[row_id].get("gemma12b_raw_output") or "")
        else:
            raw = ollama_generate(prompt=str(row.get("prompt_text") or row.get("input_text") or ""))
        normalized = normalize_label(raw, options)
        gemma_rows.append(
            {
                "row_id": row_id,
                "gemma12b_raw_output": raw,
                "gemma12b_predicted_label": normalized,
                "gemma12b_correct": normalized == str(row.get("target_text") or ""),
            }
        )
    write_jsonl(GEMMA_ROWS_JSONL, gemma_rows)

    hundred_by_id = {str(row.get("row_id") or ""): row for row in hundred_rows}
    gemma_by_id = {str(row.get("row_id") or ""): row for row in gemma_rows}
    combined = []
    for row in rows:
        row_id = str(row.get("row_id") or "")
        current = hundred_by_id.get(row_id) or {}
        combined.append(
            {
                "row_id": row_id,
                "repo_id": row.get("repo_id"),
                "language_family": row.get("language_family"),
                "task_type": row.get("task_type"),
                "target_text": row.get("target_text"),
                "target_value": next((item["value"] for item in row.get("opaque_options") or [] if item.get("label") == row.get("target_text")), None),
                **current,
                **(gemma_by_id.get(row_id) or {}),
            }
        )
    write_jsonl(COMBINED_ROWS_JSONL, combined)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Diagnostic scoring only on the 3-row fresh evidence successor candidate slice.",
            "This slice is non-promotable and exists to test whether the current multilingual retrieval interface still collapses B-vs-F on fresh Python/C++ reviewed candidates.",
        ],
        "runtime_bundle": display(RUNTIME_BUNDLE),
        "runtime_initialization": init_card,
        "hundred_m": {
            "overall": metric_block(combined, "constrained_choice_match"),
            "by_repo": group_metrics(combined, "repo_id", "constrained_choice_match"),
            "by_language": group_metrics(combined, "language_family", "constrained_choice_match"),
        },
        "gemma12b": {
            "overall": metric_block(combined, "gemma12b_correct"),
            "by_repo": group_metrics(combined, "repo_id", "gemma12b_correct"),
            "by_language": group_metrics(combined, "language_family", "gemma12b_correct"),
            "model_id": MODEL_ID,
        },
        "rows": combined,
        "artifacts": {
            "strict_rows": display(STRICT_ROWS),
            "hundred_rows": display(HUNDRED_ROWS_JSONL),
            "gemma_rows": display(GEMMA_ROWS_JSONL),
            "combined_rows": display(COMBINED_ROWS_JSONL),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

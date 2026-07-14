#!/usr/bin/env python3
from __future__ import annotations

import json
import os
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

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer, _row_text, _target_text, build_batch
from legacy_src.agentkernel_lite.training_loop import (
    _has_degenerate_repetition,
    _has_internal_token,
    _is_short_or_junk,
    _load_runtime_model_bundle,
)

STAGE = 10546
NAME = "stage10546_masked_projection_successor_same_manifest_comparison"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_PATH = OUT_DIR / "masked_projection_successor_same_manifest_comparison.json"
HUNDRED_ROWS_PATH = OUT_DIR / "hundred_m_rows.jsonl"
GEMMA_ROWS_PATH = OUT_DIR / "gemma_rows.jsonl"
COMBINED_ROWS_PATH = OUT_DIR / "combined_rows.jsonl"
PROGRESS_PATH = OUT_DIR / "progress.json"

STRICT_ROWS = ROOT / "runs/local/artifacts/stage10543_masked_projection_successor_package/strict_eval_rows.jsonl"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10545_masked_projection_successor_probe/runtime_model/runtime_model_bundle.json"
EXECUTION_RESULT = ROOT / "runs/local/artifacts/stage10545_masked_projection_successor_probe/bounded_decoder_probe/execution_result.json"
MODEL_ID = "gemma3:12b"

TORCH_THREADS = max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))
torch.set_num_threads(TORCH_THREADS)
torch.set_num_interop_threads(max(1, min(4, TORCH_THREADS)))
OUT_DIR.mkdir(parents=True, exist_ok=True)
EVAL_DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
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


def write_progress(payload: dict[str, Any]) -> None:
    write_json(PROGRESS_PATH, payload)


def progress_card(*, phase: str, completed_rows: int, total_rows: int, gemma_completed: int = 0, hundred_completed: int = 0) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "phase": phase,
        "completed_rows": int(completed_rows),
        "total_rows": int(total_rows),
        "hundred_m_completed_rows": int(hundred_completed),
        "gemma_completed_rows": int(gemma_completed),
    }


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def prompt_surface_hash(rows: list[dict[str, Any]]) -> str:
    payload = [
        {
            "row_id": str(row.get("row_id") or ""),
            "surface_text": _row_text(row),
            "target_text": str(row.get("target_text") or ""),
        }
        for row in sorted(rows, key=lambda item: str(item.get("row_id") or ""))
    ]
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def exact_match(predicted: str, target: str) -> bool:
    return str(predicted).strip() == str(target).strip()


def semantic_match(*, target_subtype: str, predicted: str, target: str) -> bool:
    predicted_text = str(predicted).strip()
    target_text = str(target).strip()
    if target_subtype == "retrieve_answer_abstain":
        return predicted_text == target_text
    if target_subtype == "decisive_evidence":
        try:
            predicted_value = json.loads(predicted_text)
            target_value = json.loads(target_text)
        except Exception:
            return False
        if not isinstance(predicted_value, list) or not isinstance(target_value, list):
            return False
        return predicted_value == target_value
    return predicted_text == target_text


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


def verdicts(hundred: dict[str, Any], gemma: dict[str, Any]) -> dict[str, Any]:
    keys = sorted(set(hundred) | set(gemma))
    out: dict[str, Any] = {}
    wins_100m = 0
    wins_gemma = 0
    ties = 0
    for key in keys:
        h = (hundred.get(key) or {}).get("exact_accuracy")
        g = (gemma.get(key) or {}).get("exact_accuracy")
        if h is None or g is None:
            verdict = "unscored"
        elif h > g:
            verdict = "100m_better"
            wins_100m += 1
        elif g > h:
            verdict = "gemma_better"
            wins_gemma += 1
        else:
            verdict = "tie"
            ties += 1
        out[key] = {
            "hundred_m_exact_accuracy": h,
            "gemma12b_exact_accuracy": g,
            "delta_hundred_m_minus_gemma": None if h is None or g is None else h - g,
            "verdict": verdict,
            "rows": (hundred.get(key) or gemma.get(key) or {}).get("rows"),
        }
    out["_summary"] = {"hundred_m": wins_100m, "gemma12b": wins_gemma, "ties": ties}
    return out


def ollama_generate(*, prompt: str, model: str = MODEL_ID, seed: int = 0, temperature: float = 0.0) -> str:
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"seed": seed, "temperature": temperature},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.loads(response.read().decode("utf-8"))
    return str(body.get("response") or "").strip()


def build_gemma_prompt(row: dict[str, Any]) -> str:
    return "\n".join(
        [
            "You are reconstructing a software-maintenance transition target from a structured maintainer state.",
            "Return only the exact target text.",
            "Do not explain your answer.",
            "",
            "Structured state:",
            _row_text(row),
        ]
    )


def load_rows(limit: int | None = None) -> list[dict[str, Any]]:
    rows = load_jsonl(STRICT_ROWS)
    rows.sort(key=lambda row: str(row.get("row_id") or ""))
    if limit is not None:
        rows = rows[:limit]
    return rows


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


def generate_greedy_text_on_device(
    model: AgentKernelLiteTransformerSeq2Seq,
    row: dict[str, Any],
    *,
    tokenizer: AgentKernelBPETokenizer,
    max_encoder_tokens: int,
    max_new_tokens: int,
) -> dict[str, Any]:
    batch = build_batch([row], max_encoder_tokens=max_encoder_tokens, max_decoder_tokens=2, tokenizer=tokenizer)
    input_ids = batch.input_ids.to(EVAL_DEVICE)
    bos_id = int(getattr(tokenizer, "bos_id", 1))
    eos_id = int(getattr(tokenizer, "eos_id", 2))
    pad_id = int(getattr(tokenizer, "pad_id", 0))
    decoder_ids = torch.tensor([[bos_id]], dtype=torch.long, device=EVAL_DEVICE)
    generated_ids: list[int] = []
    with torch.inference_mode():
        for _step_idx in range(max(0, max_new_tokens)):
            out = model(input_ids, decoder_ids)
            next_logits = out["decoder_logits"][0, -1]
            next_id = int(torch.argmax(next_logits).item())
            generated_ids.append(next_id)
            decoder_ids = torch.cat(
                [decoder_ids, torch.tensor([[next_id]], dtype=torch.long, device=EVAL_DEVICE)],
                dim=1,
            )
            if next_id == eos_id:
                break
    clean_ids = [idx for idx in generated_ids if idx not in {pad_id, bos_id, eos_id}]
    text = tokenizer.decode(clean_ids)
    target = _target_text(row)
    return {
        "generated_text": text,
        "exact_match": exact_match(text, target),
        "generated_token_count": len(clean_ids),
        "short_or_junk": _is_short_or_junk(text, target_text=target),
        "internal_token_leak": _has_internal_token(text),
        "degenerate_repetition": _has_degenerate_repetition(clean_ids, text),
    }


def run_hundred_m(rows: list[dict[str, Any]], *, max_encoder_tokens: int, max_generation_tokens: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    model, tokenizer, init_card = load_runtime()
    row_cards: list[dict[str, Any]] = []
    total = len(rows)
    for idx, row in enumerate(rows, start=1):
        sample = generate_greedy_text_on_device(
            model,
            row,
            tokenizer=tokenizer,
            max_encoder_tokens=max_encoder_tokens,
            max_new_tokens=max_generation_tokens,
        )
        row_cards.append(
            {
                "row_id": str(row.get("row_id") or ""),
                "language_family": str(row.get("language_family") or ""),
                "repo_id": str(row.get("repo_id") or ""),
                "target_subtype": str(row.get("target_subtype") or ""),
                "target_text": str(row.get("target_text") or ""),
                "hundred_m_generated_text": str(sample.get("generated_text") or ""),
                "hundred_m_exact_match": bool(sample.get("exact_match")),
                "hundred_m_semantic_match": semantic_match(
                    target_subtype=str(row.get("target_subtype") or ""),
                    predicted=str(sample.get("generated_text") or ""),
                    target=str(row.get("target_text") or ""),
                ),
                "hundred_m_generated_token_count": int(sample.get("generated_token_count") or 0),
                "hundred_m_short_or_junk": bool(sample.get("short_or_junk")),
                "hundred_m_internal_token_leak": bool(sample.get("internal_token_leak")),
                "hundred_m_degenerate_repetition": bool(sample.get("degenerate_repetition")),
            }
        )
        write_jsonl(HUNDRED_ROWS_PATH, row_cards)
        write_progress(progress_card(phase="hundred_m", completed_rows=idx, total_rows=total, hundred_completed=idx))
    return row_cards, init_card


def run_gemma(rows: list[dict[str, Any]], *, dry_run: bool, reuse_existing: bool) -> list[dict[str, Any]]:
    existing = {str(row.get("row_id") or ""): row for row in load_jsonl(GEMMA_ROWS_PATH)} if reuse_existing else {}
    row_cards: list[dict[str, Any]] = []
    total = len(rows)
    for idx, row in enumerate(rows, start=1):
        row_id = str(row.get("row_id") or "")
        prompt = build_gemma_prompt(row)
        if reuse_existing and row_id in existing:
            raw = str(existing[row_id].get("gemma12b_generated_text") or "")
        elif dry_run:
            raw = "[dry-run]"
        else:
            raw = ollama_generate(prompt=prompt)
        row_cards.append(
            {
                "row_id": row_id,
                "language_family": str(row.get("language_family") or ""),
                "repo_id": str(row.get("repo_id") or ""),
                "target_subtype": str(row.get("target_subtype") or ""),
                "target_text": str(row.get("target_text") or ""),
                "gemma12b_prompt": prompt,
                "gemma12b_generated_text": raw,
                "gemma12b_exact_match": None if dry_run else exact_match(raw, str(row.get("target_text") or "")),
                "gemma12b_semantic_match": None
                if dry_run
                else semantic_match(
                    target_subtype=str(row.get("target_subtype") or ""),
                    predicted=raw,
                    target=str(row.get("target_text") or ""),
                ),
            }
        )
        write_jsonl(GEMMA_ROWS_PATH, row_cards)
        write_progress(progress_card(phase="gemma", completed_rows=idx, total_rows=total, gemma_completed=idx, hundred_completed=total))
    return row_cards


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reuse-existing-gemma", action="store_true")
    parser.add_argument("--skip-gemma", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-encoder-tokens", type=int, default=1024)
    parser.add_argument("--max-generation-tokens", type=int, default=1024)
    args = parser.parse_args()

    rows = load_rows(limit=args.limit)
    write_progress(progress_card(phase="startup", completed_rows=0, total_rows=len(rows)))
    if not rows:
        raise SystemExit("no strict rows found")
    if not RUNTIME_BUNDLE.exists():
        raise SystemExit(f"missing runtime bundle: {RUNTIME_BUNDLE}")
    if not EXECUTION_RESULT.exists():
        raise SystemExit(f"missing execution result: {EXECUTION_RESULT}")

    hundred_rows, init_card = run_hundred_m(
        rows,
        max_encoder_tokens=args.max_encoder_tokens,
        max_generation_tokens=args.max_generation_tokens,
    )
    write_jsonl(HUNDRED_ROWS_PATH, hundred_rows)

    gemma_rows = [] if args.skip_gemma else run_gemma(rows, dry_run=args.dry_run, reuse_existing=args.reuse_existing_gemma)
    if gemma_rows:
        write_jsonl(GEMMA_ROWS_PATH, gemma_rows)

    by_hundred = {str(row["row_id"]): row for row in hundred_rows}
    by_gemma = {str(row["row_id"]): row for row in gemma_rows}
    combined_rows: list[dict[str, Any]] = []
    for row in rows:
        row_id = str(row.get("row_id") or "")
        combined_rows.append(
            {
                "row_id": row_id,
                "language_family": str(row.get("language_family") or ""),
                "repo_id": str(row.get("repo_id") or ""),
                "target_subtype": str(row.get("target_subtype") or ""),
                "target_text": str(row.get("target_text") or ""),
                **(by_hundred.get(row_id) or {}),
                **(by_gemma.get(row_id) or {}),
            }
        )
    write_jsonl(COMBINED_ROWS_PATH, combined_rows)

    hundred_metrics = metric_block(combined_rows, "hundred_m_exact_match")
    gemma_metrics = metric_block(combined_rows, "gemma12b_exact_match")
    hundred_semantic_metrics = metric_block(combined_rows, "hundred_m_semantic_match")
    gemma_semantic_metrics = metric_block(combined_rows, "gemma12b_semantic_match")
    by_language_100m = group_metrics(combined_rows, "language_family", "hundred_m_exact_match")
    by_language_gemma = group_metrics(combined_rows, "language_family", "gemma12b_exact_match")
    by_language_100m_semantic = group_metrics(combined_rows, "language_family", "hundred_m_semantic_match")
    by_language_gemma_semantic = group_metrics(combined_rows, "language_family", "gemma12b_semantic_match")
    by_subtype_100m = group_metrics(combined_rows, "target_subtype", "hundred_m_exact_match")
    by_subtype_gemma = group_metrics(combined_rows, "target_subtype", "gemma12b_exact_match")
    by_subtype_100m_semantic = group_metrics(combined_rows, "target_subtype", "hundred_m_semantic_match")
    by_subtype_gemma_semantic = group_metrics(combined_rows, "target_subtype", "gemma12b_semantic_match")

    execution = load_json(EXECUTION_RESULT)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Same-surface seq2seq generation on the strict rows from stage10543 using the stage10545 masked-projection successor runtime.",
            "Exact-match and semantic-match comparison only.",
            "Bootstrap-heldout successor slice limited to decisive_evidence_top1, retrieve_answer_abstain, and verifier_outcome_masked.",
        ],
        "row_count": len(rows),
        "prompt_surface_hash": prompt_surface_hash(rows),
        "runtime_bundle": display(RUNTIME_BUNDLE),
        "runtime_initialization": init_card,
        "eval_device": str(EVAL_DEVICE),
        "hundred_m_runtime_weights_sha256": ((execution.get("runtime_model_bundle") or {}).get("weights_sha256")),
        "hundred_m": {
            "overall": hundred_metrics,
            "overall_semantic": hundred_semantic_metrics,
            "by_language": by_language_100m,
            "by_language_semantic": by_language_100m_semantic,
            "by_target_subtype": by_subtype_100m,
            "by_target_subtype_semantic": by_subtype_100m_semantic,
        },
        "gemma12b": {
            "executed": not args.skip_gemma and not args.dry_run,
            "overall": gemma_metrics,
            "overall_semantic": gemma_semantic_metrics,
            "by_language": by_language_gemma,
            "by_language_semantic": by_language_gemma_semantic,
            "by_target_subtype": by_subtype_gemma,
            "by_target_subtype_semantic": by_subtype_gemma_semantic,
            "model_id": MODEL_ID,
        },
        "verdict_by_language": verdicts(by_language_100m, by_language_gemma),
        "verdict_by_language_semantic": verdicts(by_language_100m_semantic, by_language_gemma_semantic),
        "artifacts": {
            "strict_rows": display(STRICT_ROWS),
            "hundred_m_rows": display(HUNDRED_ROWS_PATH),
            "gemma_rows": display(GEMMA_ROWS_PATH),
            "combined_rows": display(COMBINED_ROWS_PATH),
        },
    }
    write_progress(progress_card(phase="complete", completed_rows=len(rows), total_rows=len(rows), gemma_completed=(0 if args.skip_gemma else len(rows)), hundred_completed=len(rows)))
    write_json(SUMMARY_PATH, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

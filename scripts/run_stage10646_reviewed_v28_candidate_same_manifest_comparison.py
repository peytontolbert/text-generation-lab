#!/usr/bin/env python3
from __future__ import annotations

import argparse
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

from legacy_src.agentkernel_lite.modeling_transformer import (  # noqa: E402
    AgentKernelLiteTransformerConfig,
    AgentKernelLiteTransformerSeq2Seq,
)
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer, build_batch  # noqa: E402
from legacy_src.agentkernel_lite.training_loop import (  # noqa: E402
    _bounded_choice_option_logits,
    _load_runtime_model_bundle,
)

STAGE = 10646
NAME = "stage10646_reviewed_v28_candidate_same_manifest_comparison"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_PATH = OUT_DIR / "reviewed_v28_candidate_same_manifest_comparison.json"
ROWS_PATH = OUT_DIR / "reviewed_v28_candidate_same_manifest_rows.jsonl"
PROGRESS_PATH = OUT_DIR / "progress.json"

PACKAGE_DIR = ROOT / "runs/local/artifacts/stage10645_reviewed_v28_candidate_manifest_package"
HEADLINE_ROWS = PACKAGE_DIR / "headline_strict_eval.jsonl"
RUST_REPLACEMENT_ROWS = PACKAGE_DIR / "rust_replacement_experiment_eval.jsonl"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/runtime_model/runtime_model_bundle.json"
EXECUTION_RESULT = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/bounded_decoder_probe/execution_result.json"
MODEL_ID = "gemma3:12b"

TORCH_THREADS = max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))
torch.set_num_threads(TORCH_THREADS)
torch.set_num_interop_threads(max(1, min(4, TORCH_THREADS)))
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


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def write_progress(payload: dict[str, Any]) -> None:
    write_json(PROGRESS_PATH, payload)


def prompt_surface_hash(rows: list[dict[str, Any]]) -> str:
    payload = []
    for row in sorted(rows, key=lambda item: str(item.get("row_id") or "")):
        payload.append(
            {
                "row_id": row.get("row_id"),
                "slice_name": row.get("slice_name"),
                "language_family": row.get("language_family"),
                "task_type": row.get("task_type"),
                "prompt_text": row.get("prompt_text"),
                "target_text": row.get("target_text"),
                "opaque_options": (((row.get("standalone_projection_source") or {}).get("opaque_options")) or []),
            }
        )
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


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
    patterns = [
        r"\*\*([A-Z])\*\*",
        r"\b([A-Z])\b(?=\s*[:.])",
        r"\banswer\s+is\s+([A-Z])\b",
        r"\boption\s+([A-Z])\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, raw, flags=re.IGNORECASE):
            candidate = match.group(1).upper()
            if candidate in labels:
                return candidate
    lowered = raw.lower()
    for label, value in label_to_value.items():
        if value and value.lower() in lowered:
            return label
    for line in raw.splitlines():
        cleaned = line.strip()
        for label in labels:
            if cleaned == label:
                return label
            if cleaned.startswith(f"{label}.") or cleaned.startswith(f"{label}:") or cleaned.startswith(f"{label} "):
                return label
    return first_line


def semantic_value_for_label(row: dict[str, Any], label: str) -> str | None:
    options = (((row.get("standalone_projection_source") or {}).get("opaque_options")) or [])
    for option in options:
        if str(option.get("label")) == label:
            return str(option.get("value"))
    return None


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


def score_hundred_m_row(
    model: AgentKernelLiteTransformerSeq2Seq,
    tokenizer: AgentKernelBPETokenizer,
    row: dict[str, Any],
) -> dict[str, Any]:
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
    if option_logits is None:
        raise RuntimeError(f"missing bounded choice logits for {row['row_id']}: {skip_reason}")
    probs = torch.softmax(option_logits.float(), dim=0)
    scored = []
    for idx, (label, _token_id) in enumerate(option_pairs):
        scored.append(
            {
                "label": str(label),
                "semantic_value": semantic_value_for_label(row, str(label)),
                "logit": float(option_logits[idx].item()),
                "probability": float(probs[idx].item()),
            }
        )
    scored.sort(key=lambda item: item["logit"], reverse=True)
    top1 = scored[0]
    top2 = scored[1] if len(scored) > 1 else {"label": "", "semantic_value": None, "probability": 0.0}
    target_label = str(row.get("target_text") or "")
    return {
        "predicted_label": top1["label"],
        "predicted_semantic_value": top1["semantic_value"],
        "correct": top1["label"] == target_label,
        "top1_probability": float(top1["probability"]),
        "top2_probability": float(top2["probability"]),
        "margin_top1_minus_top2": float(top1["probability"] - top2["probability"]),
        "target_label": target_label,
        "target_semantic_value": str((row.get("standalone_projection_source") or {}).get("gold_value") or ""),
        "scored_options": scored,
    }


def load_rows(*, limit_headline: int | None, limit_rust: int | None) -> list[dict[str, Any]]:
    rows = []
    headline = load_jsonl(HEADLINE_ROWS)
    rust = load_jsonl(RUST_REPLACEMENT_ROWS)
    headline.sort(key=lambda row: str(row.get("row_id") or ""))
    rust.sort(key=lambda row: str(row.get("row_id") or ""))
    if limit_headline is not None:
        headline = headline[:limit_headline]
    if limit_rust is not None:
        rust = rust[:limit_rust]
    for row in headline:
        copied = dict(row)
        copied["slice_name"] = "headline_strict"
        rows.append(copied)
    for row in rust:
        copied = dict(row)
        copied["slice_name"] = "rust_replacement_experiment"
        rows.append(copied)
    rows.sort(key=lambda row: (str(row.get("slice_name") or ""), str(row.get("row_id") or "")))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reuse-existing", action="store_true")
    parser.add_argument("--limit-headline", type=int, default=None)
    parser.add_argument("--limit-rust", type=int, default=None)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_rows(limit_headline=args.limit_headline, limit_rust=args.limit_rust)
    model, tokenizer, init_card = load_runtime()

    existing_rows = {}
    if args.reuse_existing and ROWS_PATH.exists():
        existing_rows = {str(row.get("row_id") or ""): row for row in load_jsonl(ROWS_PATH)}

    combined_rows: list[dict[str, Any]] = []
    total = len(rows)
    for idx, row in enumerate(rows, start=1):
        hundred = score_hundred_m_row(model, tokenizer, row)
        prompt = str(row.get("prompt_text") or row.get("prompt") or "")
        options = [item for item in (((row.get("standalone_projection_source") or {}).get("opaque_options")) or []) if isinstance(item, dict)]
        raw = "[dry-run]"
        pred = None
        gemma_correct = None
        row_id = str(row.get("row_id") or "")
        if args.reuse_existing and row_id in existing_rows:
            raw = str(existing_rows[row_id].get("gemma12b_raw_output") or "")
        elif not args.dry_run:
            raw = ollama_generate(prompt=prompt)
        if not args.dry_run:
            pred = normalize_label(raw, options)
            gemma_correct = pred == str(row.get("target_text") or "")
        combined_rows.append(
            {
                "row_id": row_id,
                "slice_name": str(row.get("slice_name") or ""),
                "language_family": str(row.get("language_family") or ""),
                "task_type": str(row.get("task_type") or ""),
                "repo_family": str(row.get("repo_family") or ""),
                "repo_id": str(row.get("repo_id") or ""),
                "source_bundle_id": row.get("source_bundle_id"),
                "claim_role": row.get("claim_role"),
                "selected_test_anchor": bool(row.get("selected_test_anchor")),
                "verifier_anchor": bool(row.get("verifier_anchor")),
                "abstention_heavy": bool(row.get("abstention_heavy")),
                "source_heldout_admissible": bool(row.get("source_heldout_admissible")),
                "target_text": row.get("target_text"),
                "prompt_text": prompt,
                "opaque_options": options,
                "hundred_m_predicted_label": hundred["predicted_label"],
                "hundred_m_predicted_semantic_value": hundred["predicted_semantic_value"],
                "hundred_m_correct": hundred["correct"],
                "hundred_m_top1_probability": hundred["top1_probability"],
                "hundred_m_top2_probability": hundred["top2_probability"],
                "hundred_m_margin_top1_minus_top2": hundred["margin_top1_minus_top2"],
                "hundred_m_scored_options": hundred["scored_options"],
                "gemma12b_raw_output": raw,
                "gemma12b_predicted_label": pred,
                "gemma12b_correct": gemma_correct,
            }
        )
        write_jsonl(ROWS_PATH, combined_rows)
        write_progress(
            {
                "stage": STAGE,
                "stage_name": NAME,
                "created_at_utc": now_utc(),
                "phase": "scoring",
                "completed_rows": idx,
                "total_rows": total,
            }
        )

    hundred_metrics = metric_block(combined_rows, "hundred_m_correct")
    gemma_metrics = metric_block(combined_rows, "gemma12b_correct")

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "dry_run": args.dry_run,
        "model_id": MODEL_ID,
        "rows_path": display(ROWS_PATH),
        "headline_rows_source": display(HEADLINE_ROWS),
        "rust_replacement_rows_source": display(RUST_REPLACEMENT_ROWS),
        "runtime_bundle": display(RUNTIME_BUNDLE),
        "runtime_weights_sha256": init_card.get("weights_sha256"),
        "prompt_surface_hash": prompt_surface_hash(rows),
        "hundred_m": hundred_metrics,
        "gemma12b": gemma_metrics,
        "delta_exact_accuracy": None
        if args.dry_run or hundred_metrics["exact_accuracy"] is None or gemma_metrics["exact_accuracy"] is None
        else hundred_metrics["exact_accuracy"] - gemma_metrics["exact_accuracy"],
        "by_slice": {
            "hundred_m": group_metrics(combined_rows, "slice_name", "hundred_m_correct"),
            "gemma12b": group_metrics(combined_rows, "slice_name", "gemma12b_correct"),
        },
        "by_language": {
            "hundred_m": group_metrics(combined_rows, "language_family", "hundred_m_correct"),
            "gemma12b": group_metrics(combined_rows, "language_family", "gemma12b_correct"),
        },
        "by_task_type": {
            "hundred_m": group_metrics(combined_rows, "task_type", "hundred_m_correct"),
            "gemma12b": group_metrics(combined_rows, "task_type", "gemma12b_correct"),
        },
        "by_verifier_anchor": {
            "hundred_m": group_metrics(combined_rows, "verifier_anchor", "hundred_m_correct"),
            "gemma12b": group_metrics(combined_rows, "verifier_anchor", "gemma12b_correct"),
        },
        "by_selected_test_anchor": {
            "hundred_m": group_metrics(combined_rows, "selected_test_anchor", "hundred_m_correct"),
            "gemma12b": group_metrics(combined_rows, "selected_test_anchor", "gemma12b_correct"),
        },
        "by_abstention_heavy": {
            "hundred_m": group_metrics(combined_rows, "abstention_heavy", "hundred_m_correct"),
            "gemma12b": group_metrics(combined_rows, "abstention_heavy", "gemma12b_correct"),
        },
        "slice_verdicts": verdicts(
            group_metrics(combined_rows, "slice_name", "hundred_m_correct"),
            group_metrics(combined_rows, "slice_name", "gemma12b_correct"),
        ),
        "language_verdicts": verdicts(
            group_metrics(combined_rows, "language_family", "hundred_m_correct"),
            group_metrics(combined_rows, "language_family", "gemma12b_correct"),
        ),
        "claim_boundary": [
            "headline_strict rows preserve the current same-manifest multilingual headline path.",
            "rust_replacement_experiment rows test reviewed Rust alternatives and must not be merged into the headline claim without explicit promotion.",
            "The 100M side is scored with the frozen stage10422 runtime bundle and the same bounded-choice option-retrieval scorer family.",
            "Gemma is scored by direct generation against the exact same prompt-visible rows and label normalization contract.",
        ],
    }

    write_json(SUMMARY_PATH, payload)
    write_progress({"stage": STAGE, "stage_name": NAME, "created_at_utc": now_utc(), "phase": "complete", "completed_rows": total, "total_rows": total})
    print(json.dumps({"summary": str(SUMMARY_PATH), "rows": len(combined_rows)}, indent=2))


if __name__ == "__main__":
    main()

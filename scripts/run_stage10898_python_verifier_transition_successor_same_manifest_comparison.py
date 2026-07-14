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

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _write_bounded_choice_eval_audit


STAGE = 10898
NAME = "stage10898_python_verifier_transition_successor_same_manifest_comparison"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "python_verifier_transition_successor_same_manifest_comparison.json"
HUNDRED_STRICT_ROWS_JSONL = OUT_DIR / "hundred_m_strict_rows.jsonl"
HUNDRED_EVAL_ROWS_JSONL = OUT_DIR / "hundred_m_eval_rows.jsonl"
GEMMA_STRICT_ROWS_JSONL = OUT_DIR / "gemma_strict_rows.jsonl"
COMBINED_STRICT_ROWS_JSONL = OUT_DIR / "combined_strict_rows.jsonl"
PROGRESS_JSON = OUT_DIR / "progress.json"

PACKAGE_DIR = ROOT / "runs" / "local" / "artifacts" / "stage10896_python_verifier_transition_strict_successor"
STRICT_ROWS = PACKAGE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
EVAL_ROWS = PACKAGE_DIR / "agentkernel_lite_encdec_validation.jsonl"
SUCCESSOR_AUDIT_JSON = ROOT / "runs" / "local" / "artifacts" / "stage10897_python_verifier_transition_strict_successor_audit" / "python_verifier_transition_strict_successor_audit.json"
RUNTIME_BUNDLE = ROOT / "runs" / "local" / "artifacts" / "stage10890_flash_attn_alias_safe_multilingual_support_probe" / "runtime_model" / "runtime_model_bundle.json"
EXECUTION_RESULT = ROOT / "runs" / "local" / "artifacts" / "stage10890_flash_attn_alias_safe_multilingual_support_probe" / "bounded_decoder_probe" / "execution_result.json"
MODEL_ID = "gemma3:12b"
OPTION_SOURCE = "encoder_option_retrieval"

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


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def progress_card(*, phase: str, completed_rows: int, total_rows: int, gemma_completed: int = 0) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "phase": phase,
        "completed_rows": int(completed_rows),
        "total_rows": int(total_rows),
        "gemma_completed_rows": int(gemma_completed),
    }


def write_progress(payload: dict[str, Any]) -> None:
    write_json(PROGRESS_JSON, payload)


def prompt_surface_hash(rows: list[dict[str, Any]]) -> str:
    payload = []
    for row in sorted(rows, key=lambda item: str(item.get("row_id") or "")):
        payload.append(
            {
                "row_id": row.get("row_id"),
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


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows = load_jsonl(path)
    rows.sort(key=lambda row: str(row.get("row_id") or ""))
    return rows


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer, dict[str, Any]]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(
        Path(str(metadata["tokenizer_json"])),
        Path(str(metadata["tokenizer_config"])),
    )
    model.to(EVAL_DEVICE)
    model.eval()
    return model, tokenizer, init_card


def score_rows(model: AgentKernelLiteTransformerSeq2Seq, tokenizer: AgentKernelBPETokenizer, rows: list[dict[str, Any]], *, split_name: str) -> dict[str, Any]:
    return _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name=split_name,
        bounded_choice_aux_source=OPTION_SOURCE,
        eval_batch_size=8,
    )


def run_gemma(rows: list[dict[str, Any]], *, dry_run: bool, reuse_existing: bool) -> list[dict[str, Any]]:
    existing = {str(row.get("row_id") or ""): row for row in load_jsonl(GEMMA_STRICT_ROWS_JSONL)} if reuse_existing else {}
    row_cards: list[dict[str, Any]] = []
    total = len(rows)
    for idx, row in enumerate(rows, start=1):
        row_id = str(row.get("row_id") or "")
        prompt = str(row.get("prompt_text") or row.get("input_text") or "")
        options = [item for item in (((row.get("standalone_projection_source") or {}).get("opaque_options")) or []) if isinstance(item, dict)]
        if reuse_existing and row_id in existing:
            raw = str(existing[row_id].get("gemma12b_raw_output") or "")
        elif dry_run:
            raw = "[dry-run]"
        else:
            raw = ollama_generate(prompt=prompt)
        pred = None if dry_run else normalize_label(raw, options)
        correct = None if dry_run else pred == str(row.get("target_text") or "")
        row_cards.append(
            {
                "row_id": row_id,
                "language_family": str(row.get("language_family") or ""),
                "repo_id": str(row.get("repo_id") or ""),
                "task_type": str(row.get("task_type") or ""),
                "target_text": str(row.get("target_text") or ""),
                "gemma12b_raw_output": raw,
                "gemma12b_predicted_label": pred,
                "gemma12b_correct": correct,
            }
        )
        write_jsonl(GEMMA_STRICT_ROWS_JSONL, row_cards)
        write_progress(progress_card(phase="gemma", completed_rows=idx, total_rows=total, gemma_completed=idx))
    return row_cards


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reuse-existing-gemma", action="store_true")
    parser.add_argument("--skip-gemma", action="store_true")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    strict_rows = load_rows(STRICT_ROWS)
    eval_rows = load_rows(EVAL_ROWS)
    if not strict_rows:
        raise SystemExit("no strict rows found")
    if not eval_rows:
        raise SystemExit("no eval rows found")
    if not RUNTIME_BUNDLE.exists():
        raise SystemExit(f"missing runtime bundle: {RUNTIME_BUNDLE}")
    if not EXECUTION_RESULT.exists():
        raise SystemExit(f"missing execution result: {EXECUTION_RESULT}")

    write_progress(progress_card(phase="startup", completed_rows=0, total_rows=len(strict_rows)))

    model, tokenizer, init_card = load_runtime()
    strict_card = score_rows(model, tokenizer, strict_rows, split_name="strict_eval_successor")
    eval_card = score_rows(model, tokenizer, eval_rows, split_name="eval_successor")
    hundred_strict_rows = list(strict_card.get("row_cards") or [])
    hundred_eval_rows = list(eval_card.get("row_cards") or [])
    write_jsonl(HUNDRED_STRICT_ROWS_JSONL, hundred_strict_rows)
    write_jsonl(HUNDRED_EVAL_ROWS_JSONL, hundred_eval_rows)

    gemma_rows = [] if args.skip_gemma else run_gemma(strict_rows, dry_run=args.dry_run, reuse_existing=args.reuse_existing_gemma)

    hundred_by_id = {str(row.get("row_id") or ""): row for row in hundred_strict_rows}
    gemma_by_id = {str(row.get("row_id") or ""): row for row in gemma_rows}
    combined_rows: list[dict[str, Any]] = []
    for row in strict_rows:
        row_id = str(row.get("row_id") or "")
        combined_rows.append(
            {
                "row_id": row_id,
                "language_family": row.get("language_family"),
                "task_type": row.get("task_type"),
                "repo_id": row.get("repo_id"),
                "repo_family": row.get("repo_family"),
                "source_bundle_id": row.get("source_bundle_id"),
                "selected_test_anchor": bool(row.get("selected_test_anchor")),
                "verifier_anchor": bool(row.get("verifier_anchor")),
                "abstention_heavy": bool(row.get("abstention_heavy")),
                "target_text": row.get("target_text"),
                **(hundred_by_id.get(row_id) or {}),
                **(gemma_by_id.get(row_id) or {}),
            }
        )
    write_jsonl(COMBINED_STRICT_ROWS_JSONL, combined_rows)

    execution = load_json(EXECUTION_RESULT)
    successor_audit = load_json(SUCCESSOR_AUDIT_JSON)
    by_language_100m = group_metrics(combined_rows, "language_family", "constrained_choice_match")
    by_language_gemma = group_metrics(combined_rows, "language_family", "gemma12b_correct")
    by_task_100m = group_metrics(combined_rows, "task_type", "constrained_choice_match")
    by_task_gemma = group_metrics(combined_rows, "task_type", "gemma12b_correct")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Score the stage10896 strict successor slice with the saved stage10890 100M runtime under the same bounded-choice policy family used by the current standalone frontier.",
            "Compare Gemma-12B on the exact same strict successor rows using direct opaque-choice prompting.",
            "Treat the result as a new heldout baseline because the Python strict verifier row has been replaced.",
        ],
        "runtime_bundle": display(RUNTIME_BUNDLE),
        "runtime_initialization": init_card,
        "runtime_source_execution": display(EXECUTION_RESULT),
        "successor_package": display(PACKAGE_DIR / "python_verifier_transition_strict_successor.json"),
        "successor_audit": display(SUCCESSOR_AUDIT_JSON),
        "prompt_surface_hash": prompt_surface_hash(strict_rows),
        "scoring_policy": {
            "bounded_choice_aux_source": OPTION_SOURCE,
            "eval_device": str(EVAL_DEVICE),
        },
        "hundred_m": {
            "strict_overall": metric_block(combined_rows, "constrained_choice_match"),
            "eval_overall": {
                "rows": eval_card.get("rows"),
                "constrained_choice_top1_accuracy": eval_card.get("constrained_choice_top1_accuracy"),
                "full_vocab_top1_accuracy": eval_card.get("full_vocab_top1_accuracy"),
            },
            "by_language": by_language_100m,
            "by_task_type": by_task_100m,
            "runtime_weights_sha256": (execution.get("runtime_model_bundle") or {}).get("weights_sha256"),
        },
        "gemma12b": {
            "executed": not args.skip_gemma and not args.dry_run,
            "strict_overall": metric_block(combined_rows, "gemma12b_correct"),
            "by_language": by_language_gemma,
            "by_task_type": by_task_gemma,
            "model_id": MODEL_ID,
        },
        "strict_verdict_by_language": verdicts(by_language_100m, by_language_gemma),
        "strict_verdict_by_task_type": verdicts(by_task_100m, by_task_gemma),
        "row_change_context": successor_audit.get("row_changes"),
        "residual_100m_miss_set": [row for row in combined_rows if row.get("constrained_choice_match") is not True],
        "residual_gemma_miss_set": [row for row in combined_rows if row.get("gemma12b_correct") is not True],
        "artifacts": {
            "strict_rows": display(STRICT_ROWS),
            "eval_rows": display(EVAL_ROWS),
            "hundred_m_strict_rows": display(HUNDRED_STRICT_ROWS_JSONL),
            "hundred_m_eval_rows": display(HUNDRED_EVAL_ROWS_JSONL),
            "gemma_strict_rows": display(GEMMA_STRICT_ROWS_JSONL),
            "combined_strict_rows": display(COMBINED_STRICT_ROWS_JSONL),
        },
        "claim_boundary": {
            "same_as_stage10882_surface": False,
            "new_heldout_baseline_required": True,
            "single_python_successor_row_replaced": True,
            "train_support_unchanged_vs_stage10881": successor_audit.get("metrics", {}).get("train_rows_unchanged"),
        },
    }
    write_progress(progress_card(phase="complete", completed_rows=len(strict_rows), total_rows=len(strict_rows), gemma_completed=(0 if args.skip_gemma else len(strict_rows))))
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

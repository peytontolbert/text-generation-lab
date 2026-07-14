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

ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11224
NAME = "stage11224_binary_candidate_validity_same_manifest_comparison"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "binary_candidate_validity_same_manifest_comparison.json"
ROWS_JSONL = ARTIFACTS / "stage11223_clean_residual_binary_candidate_validity_eval/binary_candidate_validity_eval_rows.jsonl"
BASE_RUNTIME = ARTIFACTS / "stage11200_role_focused_residual_probe/runtime_model/runtime_model_bundle.json"
BINARY_RUNTIME = ARTIFACTS / "stage11220_candidate_validity_support_probe/runtime_model/runtime_model_bundle.json"
GEMMA_ROWS_JSONL = OUT_DIR / "gemma_rows.jsonl"
COMBINED_ROWS_JSONL = OUT_DIR / "combined_rows.jsonl"
MODEL_ID = "gemma3:12b"
SCORER = "encoder_option_retrieval_verifier_conditioned"

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
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_runtime(path: Path) -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer, dict[str, Any]]:
    bundle = load_json(path)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(path, model=model)
    model.to(EVAL_DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tokenizer, init_card


def normalize_label(text: str, options: list[dict[str, Any]]) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    labels = [str(item.get("label") or "").strip() for item in options if str(item.get("label") or "").strip()]
    first_line = raw.splitlines()[0].strip()
    if first_line in labels:
        return first_line
    for pattern in [r"\*\*([A-Z])\*\*", r"\b([A-Z])\b(?=\s*[:.])", r"\banswer\s+is\s+([A-Z])\b", r"\boption\s+([A-Z])\b", r"^([A-Z])\b"]:
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


def ollama_generate(prompt: str, model: str = MODEL_ID, seed: int = 0, temperature: float = 0.0) -> str:
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False, "options": {"seed": seed, "temperature": temperature}}).encode("utf-8")
    request = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.loads(response.read().decode("utf-8"))
    return str(body.get("response") or "").strip()


def root_id(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("row_id") or "missing")


def metric(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get(field), bool)]
    correct = sum(1 for row in scored if row.get(field) is True)
    return {"rows": len(rows), "scored_rows": len(scored), "correct": correct, "exact_accuracy": correct / len(scored) if scored else None}


def group(rows: list[dict[str, Any]], group_field: str, result_field: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(group_field) or "unknown")].append(row)
    return {key: metric(bucket, result_field) for key, bucket in sorted(buckets.items())}


def cluster_metric(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[root_id(row)].append(row)
    solved = 0
    scored = 0
    cards = []
    for rid, bucket in sorted(buckets.items()):
        sub = [row for row in bucket if isinstance(row.get(field), bool)]
        if not sub:
            cards.append({"root_id": rid, "rows": len(bucket), "scored_rows": 0, "solved": None})
            continue
        ok = all(row.get(field) is True for row in sub)
        scored += 1
        solved += int(ok)
        cards.append({"root_id": rid, "rows": len(bucket), "scored_rows": len(sub), "solved": ok})
    return {"clusters": len(buckets), "scored_clusters": scored, "solved_clusters": solved, "cluster_exact_accuracy": solved / scored if scored else None, "cluster_cards": cards}


def enrich(card: dict[str, Any], source_rows: list[dict[str, Any]], prefix: str) -> dict[str, dict[str, Any]]:
    by_id = {str(row.get("row_id") or ""): row for row in source_rows}
    out = {}
    for row in card.get("row_cards") or []:
        source = by_id.get(str(row.get("row_id") or ""), {})
        projection = source.get("standalone_projection_source") or {}
        out[str(row.get("row_id") or "")] = {
            f"{prefix}_correct": row.get("constrained_choice_match"),
            f"{prefix}_predicted_label": row.get("constrained_choice_top1_label"),
            f"{prefix}_full_vocab_top1": row.get("full_vocab_top1_text"),
            f"{prefix}_target_rank_full_vocab": row.get("target_rank_full_vocab"),
            "binary_target_value": projection.get("gold_value"),
            "candidate_role": projection.get("candidate_role"),
            "source_row_id": source.get("source_row_id"),
            "root_id": source.get("root_id"),
            "language_family": source.get("language_family"),
            "repo_family": source.get("repo_family"),
            "task_type": source.get("task_type"),
        }
    return out


def score_runtime(runtime_path: Path, rows: list[dict[str, Any]], split_name: str, prefix: str) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    model, tokenizer, init_card = load_runtime(runtime_path)
    card = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name=split_name,
        bounded_choice_aux_source=SCORER,
        eval_batch_size=8,
    )
    return init_card, enrich(card, rows, prefix)


def row_summary(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    return {
        "overall": metric(rows, field),
        "clustered": cluster_metric(rows, field),
        "by_language": group(rows, "language_family", field),
        "by_binary_target": group(rows, "binary_target_value", field),
        "by_candidate_role": group(rows, "candidate_role", field),
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-existing-gemma", action="store_true")
    args = parser.parse_args()

    rows = load_jsonl(ROWS_JSONL)
    base_init, base_cards = score_runtime(BASE_RUNTIME, rows, "binary_candidate_validity_base_runtime", "base_100m")
    binary_init, binary_cards = score_runtime(BINARY_RUNTIME, rows, "binary_candidate_validity_binary_support_runtime", "binary_support_100m")

    existing_gemma = {str(row.get("row_id") or ""): row for row in load_jsonl(GEMMA_ROWS_JSONL)} if args.reuse_existing_gemma else {}
    gemma_rows = []
    combined = []
    for row in rows:
        row_id = str(row.get("row_id") or "")
        options = [item for item in row.get("opaque_options") or [] if isinstance(item, dict)]
        if row_id in existing_gemma:
            raw = str(existing_gemma[row_id].get("gemma12b_raw_output") or "")
        else:
            raw = ollama_generate(str(row.get("prompt_text") or row.get("input_text") or ""))
        pred = normalize_label(raw, options)
        gemma_correct = pred == str(row.get("target_text") or "")
        gemma = {
            "row_id": row_id,
            "gemma12b_raw_output": raw,
            "gemma12b_predicted_label": pred,
            "gemma12b_correct": gemma_correct,
        }
        gemma_rows.append(gemma)
        projection = row.get("standalone_projection_source") or {}
        combined.append(
            {
                "row_id": row_id,
                "source_row_id": row.get("source_row_id"),
                "root_id": root_id(row),
                "language_family": row.get("language_family"),
                "repo_family": row.get("repo_family"),
                "task_type": row.get("task_type"),
                "candidate_role": projection.get("candidate_role"),
                "binary_target_value": projection.get("gold_value"),
                "target_text": row.get("target_text"),
                **(base_cards.get(row_id) or {}),
                **(binary_cards.get(row_id) or {}),
                **gemma,
            }
        )
    write_jsonl(GEMMA_ROWS_JSONL, gemma_rows)
    write_jsonl(COMBINED_ROWS_JSONL, combined)

    paired = {}
    for name, field in [
        ("base_100m_vs_gemma", "base_100m_correct"),
        ("binary_support_100m_vs_gemma", "binary_support_100m_correct"),
    ]:
        wins_100m = wins_gemma = ties = 0
        for row in combined:
            a = row.get(field) is True
            b = row.get("gemma12b_correct") is True
            if a and not b:
                wins_100m += 1
            elif b and not a:
                wins_gemma += 1
            else:
                ties += 1
        paired[name] = {"wins_100m": wins_100m, "wins_gemma": wins_gemma, "ties": ties}

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "binary_candidate_validity_same_manifest_compared",
        "claim_scope": [
            "Diagnostic same-manifest comparison on binary candidate-validity rows derived from clean residual evidence rows.",
            "Not promotable as a benchmark because the slice is residual-derived; use it to decide whether binary evidence validity should become a native v2.7/v2.8 target.",
        ],
        "source_artifacts": {
            "rows": rel(ROWS_JSONL),
            "base_runtime": rel(BASE_RUNTIME),
            "binary_support_runtime": rel(BINARY_RUNTIME),
        },
        "scorer": SCORER,
        "base_100m": {"runtime_initialization": base_init, **row_summary(combined, "base_100m_correct")},
        "binary_support_100m": {"runtime_initialization": binary_init, **row_summary(combined, "binary_support_100m_correct")},
        "gemma12b": {"model_id": MODEL_ID, **row_summary(combined, "gemma12b_correct")},
        "paired_row_verdict": paired,
        "rows": combined,
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "gemma_rows_jsonl": rel(GEMMA_ROWS_JSONL),
            "combined_rows_jsonl": rel(COMBINED_ROWS_JSONL),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

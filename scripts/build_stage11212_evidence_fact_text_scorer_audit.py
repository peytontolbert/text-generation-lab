#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
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
STAGE = 11212
NAME = "stage11212_evidence_fact_text_scorer_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "evidence_fact_text_scorer_audit.json"

RUNTIME_BUNDLE = ARTIFACTS / "stage11200_role_focused_residual_probe/runtime_model/runtime_model_bundle.json"
STRICT_ROWS = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
VALIDATION_ROWS = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_validation.jsonl"
BANK_ROWS = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"
BASELINE_100M = ARTIFACTS / "stage11196_clean_residual_successor_100m_score/clean_residual_successor_100m_score.json"
GEMMA_BASELINE = ARTIFACTS / "stage11197_clean_residual_successor_gemma_comparison/clean_residual_successor_gemma_comparison.json"

TORCH_THREADS = max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))
torch.set_num_threads(TORCH_THREADS)
torch.set_num_interop_threads(max(1, min(4, TORCH_THREADS)))
EVAL_DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def root_id(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("row_id") or "missing")


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer, dict[str, Any]]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    model.to(EVAL_DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tokenizer, init_card


def enrich(card: dict[str, Any], source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(row.get("row_id") or ""): row for row in source_rows}
    out = []
    for row in card.get("row_cards") or []:
        source = by_id.get(str(row.get("row_id") or ""), {})
        merged = dict(row)
        for key in ["language_family", "repo_family", "task_type", "root_id", "source_root_id", "residual_successor_source"]:
            merged[key] = source.get(key)
        projection = source.get("standalone_projection_source") or {}
        merged["gold_value"] = projection.get("gold_value") or source.get("gold_value")
        out.append(merged)
    return out


def metric(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get("constrained_choice_match"), bool)]
    correct = sum(1 for row in scored if row.get("constrained_choice_match") is True)
    return {"rows": len(rows), "scored_rows": len(scored), "correct": correct, "exact_accuracy": correct / len(scored) if scored else None}


def group(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(field) or "unknown")].append(row)
    return {key: metric(value) for key, value in sorted(buckets.items())}


def cluster_metric(rows: list[dict[str, Any]]) -> dict[str, Any]:
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        clusters[root_id(row)].append(row)
    solved = 0
    scored_clusters = 0
    for cluster_rows in clusters.values():
        scored = [row for row in cluster_rows if isinstance(row.get("constrained_choice_match"), bool)]
        if not scored:
            continue
        scored_clusters += 1
        if all(row.get("constrained_choice_match") is True for row in scored):
            solved += 1
    return {"clusters": len(clusters), "scored_clusters": scored_clusters, "solved_clusters": solved, "cluster_exact_accuracy": solved / scored_clusters if scored_clusters else None}


def misses(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "row_id": row.get("row_id"),
            "root_id": root_id(row),
            "language_family": row.get("language_family"),
            "repo_family": row.get("repo_family"),
            "task_type": row.get("task_type"),
            "gold_value": row.get("gold_value"),
            "target_text": row.get("target_text"),
            "predicted": row.get("constrained_choice_top1_label"),
            "full_vocab_top1_text": row.get("full_vocab_top1_text"),
            "target_rank_full_vocab": row.get("target_rank_full_vocab"),
        }
        for row in rows
        if row.get("constrained_choice_match") is False
    ]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_metric": metric(rows),
        "cluster_metric": cluster_metric(rows),
        "by_language": group(rows, "language_family"),
        "by_task": group(rows, "task_type"),
        "by_gold_value": group(rows, "gold_value"),
        "misses": misses(rows),
    }


def score(model: AgentKernelLiteTransformerSeq2Seq, tokenizer: AgentKernelBPETokenizer, rows: list[dict[str, Any]], split: str, scorer: str) -> dict[str, Any]:
    card = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name=f"{split}_{scorer}",
        bounded_choice_aux_source=scorer,
        eval_batch_size=8,
    )
    return summarize(enrich(card, rows))


def nested_get(payload: dict[str, Any], path: list[str]) -> Any:
    cur: Any = payload
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def main() -> None:
    strict_rows = load_jsonl(STRICT_ROWS)
    validation_rows = load_jsonl(VALIDATION_ROWS)
    bank_rows = load_jsonl(BANK_ROWS)
    baseline_100m = load_json(BASELINE_100M)
    gemma = load_json(GEMMA_BASELINE)
    model, tokenizer, init_card = load_runtime()

    scorers = [
        "encoder_option_retrieval_verifier_conditioned",
        "encoder_option_retrieval_evidence_fact_text",
        "encoder_option_retrieval_evidence_ledger_head",
    ]
    results = {}
    for scorer in scorers:
        results[scorer] = {
            "strict": score(model, tokenizer, strict_rows, "strict", scorer),
            "validation": score(model, tokenizer, validation_rows, "validation", scorer),
            "residual": score(model, tokenizer, bank_rows, "clean_residual_successor", scorer),
        }

    product = results["encoder_option_retrieval_evidence_fact_text"]
    strict_metric = product["strict"]["row_metric"]
    residual_metric = product["residual"]["row_metric"]
    baseline_row_acc = nested_get(baseline_100m, ["productized_result", "row_metric", "exact_accuracy"])
    gemma_row_acc = nested_get(gemma, ["gemma_result", "row_metric", "exact_accuracy"])
    if gemma_row_acc is None:
        gemma_row_acc = nested_get(gemma, ["comparison", "gemma_row_accuracy"])
    decision = "diagnostic_only"
    if strict_metric.get("correct") == 22 and residual_metric.get("exact_accuracy") is not None:
        if baseline_row_acc is not None and residual_metric["exact_accuracy"] > baseline_row_acc:
            decision = "candidate_scorer_positive_strict_preserved_residual_improved"
        if gemma_row_acc is not None and residual_metric["exact_accuracy"] > gemma_row_acc:
            decision = "candidate_scorer_positive_beats_gemma"
    if strict_metric.get("correct") != 22:
        decision = "candidate_scorer_rejected_strict_regression"

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": decision,
        "new_scorer_under_test": "encoder_option_retrieval_evidence_fact_text",
        "interpretation": "Scores evidence-citation options using row-local visible evidence text instead of only role names.",
        "results": results,
        "baseline_100m_row_accuracy": baseline_row_acc,
        "gemma_row_accuracy": gemma_row_acc,
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "strict_rows": rel(STRICT_ROWS),
            "validation_rows": rel(VALIDATION_ROWS),
            "bank_rows": rel(BANK_ROWS),
        },
        "runtime_initialization": init_card,
        "outputs": {"summary_json": rel(SUMMARY_JSON)},
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

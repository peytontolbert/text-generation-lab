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
STAGE = 11231
NAME = "stage11231_verifier_constraint_contrast_postrun_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "verifier_constraint_contrast_postrun_audit.json"

RUNTIME_BUNDLE = ARTIFACTS / "stage11230_verifier_constraint_contrast_probe/runtime_model/runtime_model_bundle.json"
STRICT_ROWS = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
VALIDATION_ROWS = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_validation.jsonl"
RESIDUAL_BANK = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"
BASELINE = ARTIFACTS / "stage11196_clean_residual_successor_100m_score/clean_residual_successor_100m_score.json"
GEMMA = ARTIFACTS / "stage11197_clean_residual_successor_gemma_comparison/clean_residual_successor_gemma_comparison.json"

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


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def root_id(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("row_id") or "missing")


def enrich(card: dict[str, Any], source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(row.get("row_id") or ""): row for row in source_rows}
    out = []
    for row in card.get("row_cards") or []:
        source = by_id.get(str(row.get("row_id") or ""), {})
        projection = source.get("standalone_projection_source") or {}
        merged = dict(row)
        for key in ["language_family", "repo_family", "task_type", "root_id", "source_root_id", "residual_successor_source"]:
            merged[key] = source.get(key)
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
    return {key: metric(bucket) for key, bucket in sorted(buckets.items())}


def cluster_metric(rows: list[dict[str, Any]]) -> dict[str, Any]:
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        clusters[root_id(row)].append(row)
    solved = 0
    scored = 0
    for bucket in clusters.values():
        sub = [row for row in bucket if isinstance(row.get("constrained_choice_match"), bool)]
        if not sub:
            continue
        scored += 1
        solved += int(all(row.get("constrained_choice_match") is True for row in sub))
    return {"clusters": len(clusters), "scored_clusters": scored, "solved_clusters": solved, "cluster_exact_accuracy": solved / scored if scored else None}


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


def score_rows(model: AgentKernelLiteTransformerSeq2Seq, tokenizer: AgentKernelBPETokenizer, rows: list[dict[str, Any]], split_name: str) -> list[dict[str, Any]]:
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
    return enrich(card, rows)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_metric": metric(rows),
        "cluster_metric": cluster_metric(rows),
        "by_language": group(rows, "language_family"),
        "by_task": group(rows, "task_type"),
        "by_gold_value": group(rows, "gold_value"),
        "misses": misses(rows),
    }


def nested(payload: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    cur: Any = payload
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def main() -> None:
    strict_rows = load_jsonl(STRICT_ROWS)
    validation_rows = load_jsonl(VALIDATION_ROWS)
    residual_rows = load_jsonl(RESIDUAL_BANK)
    baseline = load_json(BASELINE)
    gemma = load_json(GEMMA)

    model, tokenizer, init_card = load_runtime()
    strict = score_rows(model, tokenizer, strict_rows, f"strict_eval_{SCORER}")
    validation = score_rows(model, tokenizer, validation_rows, f"validation_{SCORER}")
    residual = score_rows(model, tokenizer, residual_rows, f"clean_residual_successor_{SCORER}")

    strict_summary = summarize(strict)
    validation_summary = summarize(validation)
    residual_summary = summarize(residual)
    verifier_rows = [row for row in residual if row.get("gold_value") == "verifier_and_test_constraint"]
    verifier_metric = metric(verifier_rows)
    gates = {
        "clean_strict_22_of_22": nested(strict_summary, ["row_metric", "correct"]) == 22 and nested(strict_summary, ["row_metric", "scored_rows"]) == 22,
        "clean_residual_above_5_of_10": nested(residual_summary, ["row_metric", "correct"], 0) > 5 and nested(residual_summary, ["row_metric", "scored_rows"]) == 10,
        "verifier_constraint_above_0_of_3": verifier_metric.get("correct", 0) > 0 and verifier_metric.get("scored_rows") == 3,
    }
    promoted = all(gates.values())
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "promotion_candidate" if promoted else "diagnostic_negative_or_partial",
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "strict_rows": rel(STRICT_ROWS),
            "validation_rows": rel(VALIDATION_ROWS),
            "residual_bank": rel(RESIDUAL_BANK),
            "baseline": rel(BASELINE),
            "gemma": rel(GEMMA),
        },
        "scorer": SCORER,
        "gates": gates,
        "key_metrics": {
            "strict_accuracy": nested(strict_summary, ["row_metric", "exact_accuracy"]),
            "validation_accuracy": nested(validation_summary, ["row_metric", "exact_accuracy"]),
            "residual_accuracy": nested(residual_summary, ["row_metric", "exact_accuracy"]),
            "residual_cluster_accuracy": nested(residual_summary, ["cluster_metric", "cluster_exact_accuracy"]),
            "verifier_and_test_constraint_accuracy": verifier_metric.get("exact_accuracy"),
            "baseline_residual_accuracy": nested(baseline, ["productized_result", "row_metric", "exact_accuracy"]),
            "gemma_residual_accuracy": nested(gemma, ["gemma12b", "overall", "exact_accuracy"]),
        },
        "strict": strict_summary,
        "validation": validation_summary,
        "residual": residual_summary,
        "verifier_and_test_constraint_residual": {
            "row_metric": verifier_metric,
            "misses": misses(verifier_rows),
        },
        "runtime_initialization": init_card,
        "outputs": {"summary_json": rel(SUMMARY_JSON)},
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

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
STAGE = 11228
NAME = "stage11228_balanced_candidate_validity_postrun_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "balanced_candidate_validity_postrun_audit.json"

RUNTIME_BUNDLE = ARTIFACTS / "stage11227_balanced_candidate_validity_probe/runtime_model/runtime_model_bundle.json"
STRICT_ROWS = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
VALIDATION_ROWS = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_validation.jsonl"
RESIDUAL_BANK = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"
BINARY_EVAL = ARTIFACTS / "stage11223_clean_residual_binary_candidate_validity_eval/binary_candidate_validity_eval_rows.jsonl"
BASE_BINARY_COMPARISON = ARTIFACTS / "stage11224_binary_candidate_validity_same_manifest_comparison/binary_candidate_validity_same_manifest_comparison.json"

SCORER = "encoder_option_retrieval_verifier_conditioned"
POSITIVE_VALUE = "DECISIVE_EVIDENCE_ITEM"
NEGATIVE_VALUE = "DISTRACTOR_OR_INSUFFICIENT_EVIDENCE_ITEM"

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


def semantic_value(row: dict[str, Any]) -> str:
    return str((row.get("standalone_projection_source") or {}).get("gold_value") or row.get("gold_value") or "")


def candidate_role(row: dict[str, Any]) -> str:
    return str((row.get("standalone_projection_source") or {}).get("candidate_role") or row.get("gold_value") or "")


def enrich(card: dict[str, Any], source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(row.get("row_id") or ""): row for row in source_rows}
    out = []
    for row in card.get("row_cards") or []:
        source = by_id.get(str(row.get("row_id") or ""), {})
        projection = source.get("standalone_projection_source") or {}
        merged = dict(row)
        for key in [
            "language_family",
            "repo_family",
            "task_type",
            "root_id",
            "source_root_id",
            "source_row_id",
            "residual_successor_source",
        ]:
            merged[key] = source.get(key)
        merged["gold_value"] = projection.get("gold_value") or source.get("gold_value")
        merged["candidate_role"] = projection.get("candidate_role")
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
    cards = []
    for rid, cluster_rows in sorted(clusters.items()):
        sub = [row for row in cluster_rows if isinstance(row.get("constrained_choice_match"), bool)]
        if not sub:
            cards.append({"root_id": rid, "rows": len(cluster_rows), "scored_rows": 0, "solved": None})
            continue
        ok = all(row.get("constrained_choice_match") is True for row in sub)
        scored += 1
        solved += int(ok)
        cards.append({"root_id": rid, "rows": len(cluster_rows), "scored_rows": len(sub), "solved": ok})
    return {"clusters": len(clusters), "scored_clusters": scored, "solved_clusters": solved, "cluster_exact_accuracy": solved / scored if scored else None, "cluster_cards": cards}


def misses(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "row_id": row.get("row_id"),
            "root_id": root_id(row),
            "language_family": row.get("language_family"),
            "repo_family": row.get("repo_family"),
            "task_type": row.get("task_type"),
            "gold_value": row.get("gold_value"),
            "candidate_role": row.get("candidate_role"),
            "target_text": row.get("target_text"),
            "predicted": row.get("constrained_choice_top1_label"),
            "full_vocab_top1_text": row.get("full_vocab_top1_text"),
            "target_rank_full_vocab": row.get("target_rank_full_vocab"),
        }
        for row in rows
        if row.get("constrained_choice_match") is False
    ]


def score_rows(
    *,
    model: AgentKernelLiteTransformerSeq2Seq,
    tokenizer: AgentKernelBPETokenizer,
    rows: list[dict[str, Any]],
    split_name: str,
) -> list[dict[str, Any]]:
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
        "by_candidate_role": group(rows, "candidate_role"),
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
    binary_rows = load_jsonl(BINARY_EVAL)
    baseline_binary = load_json(BASE_BINARY_COMPARISON)

    model, tokenizer, init_card = load_runtime()
    strict = score_rows(model=model, tokenizer=tokenizer, rows=strict_rows, split_name=f"strict_eval_{SCORER}")
    validation = score_rows(model=model, tokenizer=tokenizer, rows=validation_rows, split_name=f"validation_{SCORER}")
    residual = score_rows(model=model, tokenizer=tokenizer, rows=residual_rows, split_name=f"clean_residual_successor_{SCORER}")
    binary = score_rows(model=model, tokenizer=tokenizer, rows=binary_rows, split_name=f"binary_candidate_validity_eval_{SCORER}")

    strict_summary = summarize(strict)
    validation_summary = summarize(validation)
    residual_summary = summarize(residual)
    binary_summary = summarize(binary)
    positive = [row for row in binary if row.get("gold_value") == POSITIVE_VALUE]
    negative = [row for row in binary if row.get("gold_value") == NEGATIVE_VALUE]
    positive_metric = metric(positive)
    negative_metric = metric(negative)
    baseline_positive_acc = nested(baseline_binary, ["binary_support_100m", "by_binary_target", POSITIVE_VALUE, "exact_accuracy"])
    residual_acc = nested(residual_summary, ["row_metric", "exact_accuracy"])
    strict_acc = nested(strict_summary, ["row_metric", "exact_accuracy"])
    binary_positive_acc = positive_metric.get("exact_accuracy")
    binary_negative_acc = negative_metric.get("exact_accuracy")
    gates = {
        "clean_strict_22_of_22": nested(strict_summary, ["row_metric", "correct"]) == 22 and nested(strict_summary, ["row_metric", "scored_rows"]) == 22,
        "clean_residual_at_least_5_of_10": nested(residual_summary, ["row_metric", "correct"], 0) >= 5 and nested(residual_summary, ["row_metric", "scored_rows"]) == 10,
        "binary_positive_recall_improved": (binary_positive_acc is not None and baseline_positive_acc is not None and binary_positive_acc > baseline_positive_acc),
        "binary_both_classes_nonzero_correct": positive_metric.get("correct", 0) > 0 and negative_metric.get("correct", 0) > 0,
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
            "binary_eval": rel(BINARY_EVAL),
            "baseline_binary_comparison": rel(BASE_BINARY_COMPARISON),
        },
        "scorer": SCORER,
        "gates": gates,
        "key_metrics": {
            "strict_accuracy": strict_acc,
            "validation_accuracy": nested(validation_summary, ["row_metric", "exact_accuracy"]),
            "residual_accuracy": residual_acc,
            "binary_accuracy": nested(binary_summary, ["row_metric", "exact_accuracy"]),
            "binary_positive_decisive_accuracy": binary_positive_acc,
            "binary_negative_distractor_accuracy": binary_negative_acc,
            "baseline_binary_positive_decisive_accuracy": baseline_positive_acc,
        },
        "strict": strict_summary,
        "validation": validation_summary,
        "residual": residual_summary,
        "binary_candidate_validity": {
            **binary_summary,
            "positive_decisive_metric": positive_metric,
            "negative_distractor_metric": negative_metric,
        },
        "runtime_initialization": init_card,
        "outputs": {"summary_json": rel(SUMMARY_JSON)},
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

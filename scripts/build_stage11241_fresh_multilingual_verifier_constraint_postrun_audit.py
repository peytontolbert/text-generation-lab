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
STAGE = 11241
NAME = "stage11241_fresh_multilingual_verifier_constraint_postrun_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_multilingual_verifier_constraint_postrun_audit.json"

RUNTIME_BUNDLE = ARTIFACTS / "stage11240_fresh_multilingual_verifier_constraint_probe/runtime_model/runtime_model_bundle.json"
REQUEST_SUMMARY = ARTIFACTS / "stage11239_fresh_multilingual_verifier_constraint_probe_request/fresh_multilingual_verifier_constraint_probe_request.json"
STRICT_ROWS = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
VALIDATION_ROWS = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_validation.jsonl"
RESIDUAL_BANK = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"
FRESH_VALIDATION = ARTIFACTS / "stage11238_fresh_multilingual_verifier_constraint_package/fresh_verifier_constraint_validation_rows.jsonl"
FRESH_STRICT = ARTIFACTS / "stage11238_fresh_multilingual_verifier_constraint_package/fresh_verifier_constraint_strict_rows.jsonl"
BASELINE_100M = ARTIFACTS / "stage11196_clean_residual_successor_100m_score/clean_residual_successor_100m_score.json"
GEMMA_BASELINE = ARTIFACTS / "stage11197_clean_residual_successor_gemma_comparison/clean_residual_successor_gemma_comparison.json"
SCORER = "encoder_option_retrieval_verifier_conditioned"

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


def gold_value(source: dict[str, Any]) -> Any:
    projection = source.get("standalone_projection_source") or {}
    return projection.get("source_gold_value") or projection.get("gold_value") or source.get("semantic_target_value") or source.get("gold_value")


def enrich(card: dict[str, Any], source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(row.get("row_id") or ""): row for row in source_rows}
    out = []
    for scored in card.get("row_cards") or []:
        source = by_id.get(str(scored.get("row_id") or ""), {})
        merged = dict(scored)
        for key in ["language", "language_family", "repo_family", "task_type", "root_id", "source_root_id", "source_row_id", "residual_successor_source", "semantic_target_value"]:
            merged[key] = source.get(key)
        merged["gold_value"] = gold_value(source)
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
    for bucket in clusters.values():
        scored = [row for row in bucket if isinstance(row.get("constrained_choice_match"), bool)]
        if not scored:
            continue
        scored_clusters += 1
        solved += int(all(row.get("constrained_choice_match") is True for row in scored))
    return {"clusters": len(clusters), "scored_clusters": scored_clusters, "solved_clusters": solved, "cluster_exact_accuracy": solved / scored_clusters if scored_clusters else None}


def misses(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "row_id": row.get("row_id"),
            "root_id": root_id(row),
            "language_family": row.get("language_family") or row.get("language"),
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
    request = load_json(REQUEST_SUMMARY)
    baseline = load_json(BASELINE_100M)
    gemma = load_json(GEMMA_BASELINE)
    strict_rows = load_jsonl(STRICT_ROWS)
    validation_rows = load_jsonl(VALIDATION_ROWS)
    residual_rows = load_jsonl(RESIDUAL_BANK)
    fresh_validation_rows = load_jsonl(FRESH_VALIDATION)
    fresh_strict_rows = load_jsonl(FRESH_STRICT)

    model, tokenizer, init_card = load_runtime()
    strict = score_rows(model, tokenizer, strict_rows, f"clean_strict_{SCORER}")
    validation = score_rows(model, tokenizer, validation_rows, f"clean_validation_{SCORER}")
    residual = score_rows(model, tokenizer, residual_rows, f"clean_residual_{SCORER}")
    fresh_validation = score_rows(model, tokenizer, fresh_validation_rows, f"fresh_validation_{SCORER}")
    fresh_strict = score_rows(model, tokenizer, fresh_strict_rows, f"fresh_strict_{SCORER}")

    strict_summary = summarize(strict)
    validation_summary = summarize(validation)
    residual_summary = summarize(residual)
    fresh_validation_summary = summarize(fresh_validation)
    fresh_strict_summary = summarize(fresh_strict)
    verifier_residual = [row for row in residual if row.get("gold_value") == "verifier_and_test_constraint"]
    verifier_residual_metric = metric(verifier_residual)

    gates = {
        "clean_strict_22_of_22": nested(strict_summary, ["row_metric", "correct"]) == 22 and nested(strict_summary, ["row_metric", "scored_rows"]) == 22,
        "clean_validation_at_least_20_of_23": nested(validation_summary, ["row_metric", "correct"], 0) >= 20 and nested(validation_summary, ["row_metric", "scored_rows"]) == 23,
        "clean_residual_above_5_of_10": nested(residual_summary, ["row_metric", "correct"], 0) > 5 and nested(residual_summary, ["row_metric", "scored_rows"]) == 10,
        "verifier_constraint_residual_above_0_of_3": verifier_residual_metric.get("correct", 0) > 0 and verifier_residual_metric.get("scored_rows") == 3,
        "fresh_validation_reported": nested(fresh_validation_summary, ["row_metric", "scored_rows"]) == len(fresh_validation_rows),
        "fresh_strict_reported": nested(fresh_strict_summary, ["row_metric", "scored_rows"]) == len(fresh_strict_rows),
    }
    promoted = all(gates.values())
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "promotion_candidate" if promoted else "diagnostic_negative_or_partial",
        "scorer": SCORER,
        "gates": gates,
        "request_metrics": request.get("metrics"),
        "baseline_reference": {
            "stage11196_100m_residual_row_metric": nested(baseline, ["scores", "row_metric"]),
            "stage11197_gemma_residual": nested(gemma, ["comparison", "gemma"]),
        },
        "runtime_initialization": init_card,
        "runtime_bundle": load_json(RUNTIME_BUNDLE),
        "summaries": {
            "clean_strict": strict_summary,
            "clean_validation": validation_summary,
            "clean_residual": residual_summary,
            "fresh_validation": fresh_validation_summary,
            "fresh_strict": fresh_strict_summary,
            "verifier_constraint_residual_metric": verifier_residual_metric,
        },
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "request_summary": rel(REQUEST_SUMMARY),
            "clean_strict_rows": rel(STRICT_ROWS),
            "clean_validation_rows": rel(VALIDATION_ROWS),
            "residual_bank": rel(RESIDUAL_BANK),
            "fresh_validation_rows": rel(FRESH_VALIDATION),
            "fresh_strict_rows": rel(FRESH_STRICT),
        },
        "outputs": {"summary_json": rel(SUMMARY_JSON)},
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

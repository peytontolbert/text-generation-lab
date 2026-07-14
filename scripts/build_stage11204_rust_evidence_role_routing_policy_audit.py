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
STAGE = 11204
NAME = "stage11204_rust_evidence_role_routing_policy_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "rust_evidence_role_routing_policy_audit.json"
RUNTIME_BUNDLE = ARTIFACTS / "stage11202_evidence_role_head_probe/runtime_model/runtime_model_bundle.json"
STRICT_ROWS = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
VALIDATION_ROWS = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_validation.jsonl"
BANK_ROWS = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"
BASELINE_100M = ARTIFACTS / "stage11196_clean_residual_successor_100m_score/clean_residual_successor_100m_score.json"
GEMMA_BASELINE = ARTIFACTS / "stage11197_clean_residual_successor_gemma_comparison/clean_residual_successor_gemma_comparison.json"

ROLE_VALUES = {
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "nearby_definition_or_usage_context",
    "external_analogue_reference",
    "algorithmic_background_reference",
}

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


def option_map(row: dict[str, Any]) -> dict[str, str]:
    options = ((row.get("standalone_projection_source") or {}).get("opaque_options") or row.get("opaque_options") or [])
    return {str(opt.get("label") or "").strip(): str(opt.get("value") or "").strip() for opt in options if isinstance(opt, dict)}


def is_role_option_row(row: dict[str, Any]) -> bool:
    values = set(option_map(row).values())
    return bool(values & ROLE_VALUES)


def route_to_role_head(row: dict[str, Any]) -> bool:
    return (
        str(row.get("language_family") or "") == "rust"
        and str(row.get("task_type") or "") == "evidence_citation"
        and is_role_option_row(row)
    )


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
        merged["option_value_by_label"] = option_map(source)
        merged["routed_to_role_head"] = route_to_role_head(source)
        return_value = merged["option_value_by_label"].get(str(merged.get("constrained_choice_top1_label") or ""))
        merged["predicted_value"] = return_value
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
        solved += 1 if all(row.get("constrained_choice_match") is True for row in scored) else 0
    return {"clusters": len(clusters), "scored_clusters": scored_clusters, "solved_clusters": solved, "cluster_exact_accuracy": solved / scored_clusters if scored_clusters else None}


def misses(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "row_id": row.get("row_id"),
        "root_id": root_id(row),
        "language_family": row.get("language_family"),
        "repo_family": row.get("repo_family"),
        "task_type": row.get("task_type"),
        "gold_value": row.get("gold_value"),
        "target_text": row.get("target_text"),
        "predicted": row.get("constrained_choice_top1_label"),
        "predicted_value": row.get("predicted_value"),
        "routed_to_role_head": row.get("routed_to_role_head"),
    } for row in rows if row.get("constrained_choice_match") is False]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_metric": metric(rows),
        "cluster_metric": cluster_metric(rows),
        "by_language": group(rows, "language_family"),
        "by_task": group(rows, "task_type"),
        "by_gold_value": group(rows, "gold_value"),
        "routed_rows": sum(1 for row in rows if row.get("routed_to_role_head")),
        "misses": misses(rows),
    }


def score(model, tokenizer, rows: list[dict[str, Any]], split: str, source: str) -> list[dict[str, Any]]:
    card = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name=f"{split}_{source}",
        bounded_choice_aux_source=source,
        eval_batch_size=8,
    )
    return enrich(card, rows)


def hybrid_rows(base_rows: list[dict[str, Any]], role_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    role_by_id = {str(row.get("row_id") or ""): row for row in role_rows}
    out = []
    for base in base_rows:
        role = role_by_id.get(str(base.get("row_id") or ""))
        if role is not None and role.get("routed_to_role_head"):
            merged = dict(role)
            merged["policy_source"] = "rust_evidence_role_head"
        else:
            merged = dict(base)
            merged["policy_source"] = "base_verifier_conditioned"
        out.append(merged)
    return out


def nested_get(payload: dict[str, Any], path: list[str], default: Any = None) -> Any:
    cur: Any = payload
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def main() -> None:
    model, tokenizer, init_card = load_runtime()
    datasets = {
        "clean_strict": load_jsonl(STRICT_ROWS),
        "clean_validation": load_jsonl(VALIDATION_ROWS),
        "clean_residual_successor": load_jsonl(BANK_ROWS),
    }
    base_source = "encoder_option_retrieval_verifier_conditioned"
    role_source = "encoder_option_retrieval_evidence_role_head"
    results = {}
    for name, rows in datasets.items():
        base = score(model, tokenizer, rows, name, base_source)
        role = score(model, tokenizer, rows, name, role_source)
        hybrid = hybrid_rows(base, role)
        results[name] = {
            "base": summarize(base),
            "role_head": summarize(role),
            "hybrid": summarize(hybrid),
        }
    baseline = load_json(BASELINE_100M)
    gemma = load_json(GEMMA_BASELINE)
    baseline_row = nested_get(baseline, ["productized_result", "row_metric", "exact_accuracy"])
    baseline_cluster = nested_get(baseline, ["productized_result", "cluster_metric", "cluster_exact_accuracy"])
    gemma_row = nested_get(gemma, ["gemma12b", "overall", "exact_accuracy"])
    gemma_cluster = nested_get(gemma, ["gemma12b", "clustered", "cluster_exact_accuracy"])
    residual = results["clean_residual_successor"]["hybrid"]
    strict = results["clean_strict"]["hybrid"]
    residual_row = nested_get(residual, ["row_metric", "exact_accuracy"])
    residual_cluster = nested_get(residual, ["cluster_metric", "cluster_exact_accuracy"])
    strict_ok = strict["row_metric"]["correct"] == 22 and strict["row_metric"]["scored_rows"] == 22
    improves = residual_row is not None and baseline_row is not None and residual_row > baseline_row
    beats_or_ties_gemma_row = residual_row is not None and gemma_row is not None and residual_row >= gemma_row
    beats_gemma_cluster = residual_cluster is not None and gemma_cluster is not None and residual_cluster > gemma_cluster
    decision = "hybrid_policy_diagnostic_only"
    if strict_ok and improves and beats_or_ties_gemma_row and beats_gemma_cluster:
        decision = "hybrid_policy_promising_needs_fresh_holdout_confirmation"
    elif not strict_ok:
        decision = "hybrid_policy_rejected_strict_regression"
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": decision,
        "policy": {
            "base_source": base_source,
            "role_source": role_source,
            "routing_rule": "Use role head only for rust evidence_citation rows with semantic evidence-role options; otherwise use verifier-conditioned base scorer.",
        },
        "results": results,
        "comparison": {
            "baseline_100m_row_accuracy": baseline_row,
            "baseline_100m_cluster_accuracy": baseline_cluster,
            "gemma_row_accuracy": gemma_row,
            "gemma_cluster_accuracy": gemma_cluster,
            "hybrid_residual_row_accuracy": residual_row,
            "hybrid_residual_cluster_accuracy": residual_cluster,
            "row_delta_vs_baseline_100m": residual_row - baseline_row if residual_row is not None and baseline_row is not None else None,
            "cluster_delta_vs_baseline_100m": residual_cluster - baseline_cluster if residual_cluster is not None and baseline_cluster is not None else None,
            "row_delta_vs_gemma": residual_row - gemma_row if residual_row is not None and gemma_row is not None else None,
            "cluster_delta_vs_gemma": residual_cluster - gemma_cluster if residual_cluster is not None and gemma_cluster is not None else None,
        },
        "promotion_gate": {
            "strict_preserved_22_of_22": strict_ok,
            "residual_improved_vs_stage11196": improves,
            "row_beats_or_ties_gemma": beats_or_ties_gemma_row,
            "cluster_beats_gemma": beats_gemma_cluster,
            "promotable_without_fresh_holdout": False,
        },
        "runtime_initialization": init_card,
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "strict_rows": rel(STRICT_ROWS),
            "validation_rows": rel(VALIDATION_ROWS),
            "bank_rows": rel(BANK_ROWS),
            "baseline_100m": rel(BASELINE_100M),
            "gemma_baseline": rel(GEMMA_BASELINE),
        },
        "outputs": {"summary_json": rel(SUMMARY_JSON)},
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

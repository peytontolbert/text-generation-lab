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
STAGE = 11257
NAME = "stage11257_fact_rich_evidence_fact_pairwise_postrun_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fact_rich_evidence_fact_pairwise_postrun_audit.json"
RUNTIME_BUNDLE = ARTIFACTS / "stage11256_fact_rich_evidence_fact_pairwise_probe/runtime_model/runtime_model_bundle.json"
PACKAGE_SUMMARY = ARTIFACTS / "stage11249_fact_rich_evidence_option_package/fact_rich_evidence_option_package.json"
BASELINE_AUDIT = ARTIFACTS / "stage11250_fact_rich_evidence_option_baseline_audit/fact_rich_evidence_option_baseline_audit.json"
CLEAN_STRICT = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
CLEAN_VALIDATION = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_validation.jsonl"
VALIDATION_ROWS = ARTIFACTS / "stage11249_fact_rich_evidence_option_package/fact_rich_evidence_option_validation_rows.jsonl"
STRICT_ROWS = ARTIFACTS / "stage11249_fact_rich_evidence_option_package/fact_rich_evidence_option_strict_rows.jsonl"
RESIDUAL_BANK = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"
SCORERS = ["encoder_option_retrieval_evidence_fact_pairwise", "encoder_option_retrieval_verifier_conditioned", "encoder_option_retrieval_evidence_fact_text"]
PRODUCT_SCORER = "encoder_option_retrieval_evidence_fact_pairwise"
BASELINE_SCORER = "encoder_option_retrieval_verifier_conditioned"

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


def gold_value(source: dict[str, Any]) -> Any:
    projection = source.get("standalone_projection_source") or {}
    return projection.get("gold_value") or source.get("semantic_target_value") or source.get("gold_value")


def enrich(card: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(row.get("row_id") or ""): row for row in rows}
    out = []
    for scored in card.get("row_cards") or []:
        source = by_id.get(str(scored.get("row_id") or ""), {})
        merged = dict(scored)
        for key in ["language", "language_family", "repo_family", "task_type", "root_id", "source_root_id", "semantic_target_value", "evidence_role_grounding_target"]:
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


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_metric": metric(rows),
        "by_language": group(rows, "language_family"),
        "by_gold_value": group(rows, "gold_value"),
        "miss_count": sum(1 for row in rows if row.get("constrained_choice_match") is False),
        "misses": [
            {
                "row_id": row.get("row_id"),
                "language_family": row.get("language_family"),
                "repo_family": row.get("repo_family"),
                "gold_value": row.get("gold_value"),
                "target_text": row.get("target_text"),
                "predicted": row.get("constrained_choice_top1_label"),
                "full_vocab_top1_text": row.get("full_vocab_top1_text"),
                "target_rank_full_vocab": row.get("target_rank_full_vocab"),
            }
            for row in rows
            if row.get("constrained_choice_match") is False
        ][:20],
    }


def score(model, tokenizer, rows: list[dict[str, Any]], split: str, scorer: str) -> list[dict[str, Any]]:
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
    return enrich(card, rows)


def main() -> None:
    package = load_json(PACKAGE_SUMMARY)
    baseline = load_json(BASELINE_AUDIT)
    clean_strict_rows = load_jsonl(CLEAN_STRICT)
    clean_validation_rows = load_jsonl(CLEAN_VALIDATION)
    validation = load_jsonl(VALIDATION_ROWS)
    strict = load_jsonl(STRICT_ROWS)
    residual = load_jsonl(RESIDUAL_BANK)
    model, tokenizer, init_card = load_runtime()
    scored: dict[str, Any] = {}
    for scorer in SCORERS:
        scored[scorer] = {
            "clean_validation": summarize(score(model, tokenizer, clean_validation_rows, "clean_validation", scorer)),
            "clean_strict": summarize(score(model, tokenizer, clean_strict_rows, "clean_strict", scorer)),
            "validation": summarize(score(model, tokenizer, validation, "validation", scorer)),
            "strict": summarize(score(model, tokenizer, strict, "strict", scorer)),
            "residual": summarize(score(model, tokenizer, residual, "residual", scorer)),
        }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "fact_rich_evidence_fact_pairwise_postrun_audit_complete",
        "package_counts": package.get("counts"),
        "runtime_initialization": init_card,
        "gates": {
            "product_clean_strict_22_of_22": scored[PRODUCT_SCORER]["clean_strict"]["row_metric"]["correct"] == 22,
            "product_clean_validation_at_least_20_of_23": scored[PRODUCT_SCORER]["clean_validation"]["row_metric"]["correct"] >= 20,
            "product_residual_above_5_of_10": scored[PRODUCT_SCORER]["residual"]["row_metric"]["correct"] > 5,
            "product_verifier_residual_nonzero": scored[PRODUCT_SCORER]["residual"]["by_gold_value"].get("verifier_and_test_constraint", {}).get("correct", 0) > 0,
            "product_fact_rich_validation_improved_vs_baseline": scored[PRODUCT_SCORER]["validation"]["row_metric"]["correct"] > baseline["scored"][BASELINE_SCORER]["validation"]["row_metric"]["correct"],
            "product_fact_rich_strict_improved_vs_baseline": scored[PRODUCT_SCORER]["strict"]["row_metric"]["correct"] > baseline["scored"][BASELINE_SCORER]["strict"]["row_metric"]["correct"],
        },
        "baseline_stage11250_verifier_conditioned_reference": {
            "validation": baseline["scored"][BASELINE_SCORER]["validation"]["row_metric"],
            "strict": baseline["scored"][BASELINE_SCORER]["strict"]["row_metric"],
            "residual": baseline["scored"][BASELINE_SCORER]["residual"]["row_metric"],
        },
        "scored": scored,
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "baseline_audit": rel(BASELINE_AUDIT),
            "package_summary": rel(PACKAGE_SUMMARY),
            "clean_validation_rows": rel(CLEAN_VALIDATION),
            "clean_strict_rows": rel(CLEAN_STRICT),
            "validation_rows": rel(VALIDATION_ROWS),
            "strict_rows": rel(STRICT_ROWS),
            "residual_bank": rel(RESIDUAL_BANK),
        },
        "outputs": {"summary_json": rel(SUMMARY_JSON)},
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

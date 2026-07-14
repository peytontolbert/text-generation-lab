#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter, defaultdict
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
STAGE = 11183
NAME = "stage11183_contract_evidence_support_postrun_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "contract_evidence_support_postrun_audit.json"

RUNTIME_BUNDLE = ARTIFACTS / "stage11182_contract_evidence_support_probe/runtime_model/runtime_model_bundle.json"
EXECUTION_JSON = ARTIFACTS / "stage11182_contract_evidence_support_probe/bounded_decoder_probe/execution_result.json"
PACKAGE_JSON = ARTIFACTS / "stage11180_cleaned_plus_contract_evidence_support_package/cleaned_plus_contract_evidence_support_package.json"
ADDED_ROWS = ARTIFACTS / "stage11180_cleaned_plus_contract_evidence_support_package/added_contract_aware_evidence_rows.jsonl"
VALIDATION_ROWS = ARTIFACTS / "stage11180_cleaned_plus_contract_evidence_support_package/agentkernel_lite_encdec_validation.jsonl"
STRICT_ROWS = ARTIFACTS / "stage11180_cleaned_plus_contract_evidence_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
RESERVED_ROWS = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence/reserved_residual_candidates.jsonl"
BASELINE_POSTRUN = ARTIFACTS / "stage11171_external_fail_to_pass_support_postrun_audit/external_fail_to_pass_support_postrun_audit.json"

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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


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


def accuracy(card: dict[str, Any]) -> float | None:
    value = card.get("constrained_choice_top1_accuracy")
    return float(value) if isinstance(value, (int, float)) else None


def enrich(card: dict[str, Any], source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(row.get("row_id") or ""): row for row in source_rows}
    out = []
    for row in card.get("row_cards") or []:
        source = by_id.get(str(row.get("row_id") or ""), {})
        merged = dict(row)
        for key in ["language_family", "repo_family", "task_type", "root_id", "source_root_id"]:
            merged[key] = source.get(key)
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


def miss_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "row_id": row.get("row_id"),
            "language_family": row.get("language_family"),
            "repo_family": row.get("repo_family"),
            "task_type": row.get("task_type"),
            "target_text": row.get("target_text"),
            "predicted": row.get("constrained_choice_top1_label"),
            "full_vocab_top1_text": row.get("full_vocab_top1_text"),
            "target_rank_full_vocab": row.get("target_rank_full_vocab"),
        }
        for row in rows
        if row.get("constrained_choice_match") is False
    ]


def roots(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("root_id") or row.get("source_root_id") or "") for row in rows if row.get("root_id") or row.get("source_root_id")}


def main() -> None:
    execution = load_json(EXECUTION_JSON)
    package = load_json(PACKAGE_JSON)
    added = load_jsonl(ADDED_ROWS)
    validation_rows = load_jsonl(VALIDATION_ROWS)
    strict_rows = load_jsonl(STRICT_ROWS)
    reserved_rows = load_jsonl(RESERVED_ROWS)
    baseline = load_json(BASELINE_POSTRUN) if BASELINE_POSTRUN.exists() else {}

    model, tokenizer, init_card = load_runtime()
    sources = ["encoder_option_retrieval", "encoder_option_retrieval_verifier_conditioned"]
    cards: dict[str, dict[str, Any]] = {}
    enriched: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for source in sources:
        cards[source] = {}
        enriched[source] = {}
        for split_name, rows in [
            ("clean_validation", validation_rows),
            ("clean_strict", strict_rows),
            ("reserved_residual", reserved_rows),
        ]:
            card = _write_bounded_choice_eval_audit(
                OUT_DIR,
                model=model,
                rows=rows,
                tokenizer=tokenizer,
                max_encoder_tokens=768,
                max_decoder_tokens=8,
                split_name=f"{split_name}_{source}",
                bounded_choice_aux_source=source,
                eval_batch_size=8,
            )
            cards[source][split_name] = card
            enriched[source][split_name] = enrich(card, rows)

    product_source = "encoder_option_retrieval_verifier_conditioned"
    product_strict = enriched[product_source]["clean_strict"]
    product_validation = enriched[product_source]["clean_validation"]
    product_reserved = enriched[product_source]["reserved_residual"]
    product_reserved_evidence = [row for row in product_reserved if row.get("task_type") == "evidence_citation"]

    base_reserved = enriched["encoder_option_retrieval"]["reserved_residual"]
    base_reserved_evidence = [row for row in base_reserved if row.get("task_type") == "evidence_citation"]

    support_roots = roots(added)
    strict_roots = roots(strict_rows)
    validation_roots = roots(validation_rows)
    reserved_roots = roots(reserved_rows)

    baseline_strict = (((baseline.get("successor_surface_result") or {}).get("strict_accuracy")))
    baseline_validation = (((baseline.get("successor_surface_result") or {}).get("validation_accuracy")))
    baseline_reserved = ((((baseline.get("reserved_candidate_result") or {}).get("overall") or {}).get("exact_accuracy")))
    baseline_reserved_evidence = ((((baseline.get("reserved_candidate_result") or {}).get("evidence_citation") or {}).get("exact_accuracy")))

    product_strict_metric = metric(product_strict)
    product_validation_metric = metric(product_validation)
    product_reserved_metric = metric(product_reserved)
    product_reserved_evidence_metric = metric(product_reserved_evidence)

    promotion_gate = {
        "clean_strict_preserved_or_improved": product_strict_metric["exact_accuracy"] is not None and product_strict_metric["exact_accuracy"] >= 1.0,
        "clean_validation_not_regressed": baseline_validation is not None and product_validation_metric["exact_accuracy"] is not None and product_validation_metric["exact_accuracy"] >= float(baseline_validation),
        "reserved_residual_improved": baseline_reserved is not None and product_reserved_metric["exact_accuracy"] is not None and product_reserved_metric["exact_accuracy"] > float(baseline_reserved),
        "reserved_evidence_improved": baseline_reserved_evidence is not None and product_reserved_evidence_metric["exact_accuracy"] is not None and product_reserved_evidence_metric["exact_accuracy"] > float(baseline_reserved_evidence),
        "no_support_root_overlap": not bool(support_roots & (strict_roots | validation_roots | reserved_roots)),
    }

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "diagnostic_promotable" if all(promotion_gate.values()) else "diagnostic_flat_or_regressed",
        "claim_scope": [
            "Audit stage11182 after adding contract-aware evidence train support.",
            "Use productized verifier-conditioned scorer for strict/validation/reserved headline accounting.",
            "Keep added evidence rows train-support-only; do not count them as heldout wins.",
        ],
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "execution_result": rel(EXECUTION_JSON),
            "support_package": rel(PACKAGE_JSON),
            "added_rows": rel(ADDED_ROWS),
            "validation_rows": rel(VALIDATION_ROWS),
            "strict_rows": rel(STRICT_ROWS),
            "reserved_rows": rel(RESERVED_ROWS),
            "baseline_postrun": rel(BASELINE_POSTRUN) if BASELINE_POSTRUN.exists() else None,
        },
        "package_metrics": package.get("metrics"),
        "execution": {
            "runtime_executed": execution.get("runtime_executed"),
            "weights_sha256": ((execution.get("runtime_model_bundle") or {}).get("weights_sha256")),
            "manifest_sha256": execution.get("manifest_sha256"),
        },
        "productized_scorer_result": {
            "source": product_source,
            "clean_strict": product_strict_metric,
            "clean_validation": product_validation_metric,
            "reserved_residual": product_reserved_metric,
            "reserved_evidence": product_reserved_evidence_metric,
            "strict_misses": miss_rows(product_strict),
            "validation_misses": miss_rows(product_validation),
            "reserved_misses": miss_rows(product_reserved),
            "reserved_by_task": group(product_reserved, "task_type"),
            "reserved_by_language": group(product_reserved, "language_family"),
        },
        "base_scorer_result": {
            "source": "encoder_option_retrieval",
            "clean_strict": metric(enriched["encoder_option_retrieval"]["clean_strict"]),
            "clean_validation": metric(enriched["encoder_option_retrieval"]["clean_validation"]),
            "reserved_residual": metric(base_reserved),
            "reserved_evidence": metric(base_reserved_evidence),
            "reserved_misses": miss_rows(base_reserved),
        },
        "delta_vs_stage11171": {
            "product_clean_strict": None if baseline_strict is None else product_strict_metric["exact_accuracy"] - float(baseline_strict),
            "product_clean_validation": None if baseline_validation is None else product_validation_metric["exact_accuracy"] - float(baseline_validation),
            "product_reserved_residual": None if baseline_reserved is None else product_reserved_metric["exact_accuracy"] - float(baseline_reserved),
            "product_reserved_evidence": None if baseline_reserved_evidence is None else product_reserved_evidence_metric["exact_accuracy"] - float(baseline_reserved_evidence),
        },
        "anti_cheat": {
            "support_roots_overlap_strict": sorted(support_roots & strict_roots),
            "support_roots_overlap_validation": sorted(support_roots & validation_roots),
            "support_roots_overlap_reserved": sorted(support_roots & reserved_roots),
            "added_rows": len(added),
            "added_by_gold_value": dict(sorted(Counter(str((row.get("standalone_projection_source") or {}).get("gold_value") or "missing") for row in added).items())),
            "added_by_language": dict(sorted(Counter(str(row.get("language_family") or "missing") for row in added).items())),
        },
        "promotion_gate": promotion_gate,
        "runtime_initialization": init_card,
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

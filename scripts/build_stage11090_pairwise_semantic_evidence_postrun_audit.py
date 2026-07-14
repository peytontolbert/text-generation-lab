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
from legacy_src.agentkernel_lite.training_loop import _bounded_choice_pairwise_feature_dim, _load_runtime_model_bundle, _write_bounded_choice_eval_audit


ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11090
NAME = "stage11090_pairwise_semantic_evidence_postrun_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "pairwise_semantic_evidence_postrun_audit.json"
RESERVED_AUDIT_JSON = OUT_DIR / "reserved_residual_candidate_bounded_choice_eval.json"
RESERVED_ROWS_JSONL = OUT_DIR / "reserved_residual_candidate_rows_scored.jsonl"

RUNTIME_BUNDLE = ARTIFACTS / "stage11089_pairwise_semantic_evidence_probe" / "runtime_model" / "runtime_model_bundle.json"
VALIDATION_JSON = ARTIFACTS / "stage11089_pairwise_semantic_evidence_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_eval.json"
STRICT_JSON = ARTIFACTS / "stage11089_pairwise_semantic_evidence_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_strict_eval.json"
EXECUTION_JSON = ARTIFACTS / "stage11089_pairwise_semantic_evidence_probe" / "bounded_decoder_probe" / "execution_result.json"
RESERVED_ROWS = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence" / "reserved_residual_candidates.jsonl"
BASELINE_AUDIT = ARTIFACTS / "stage11086_semantic_evidence_support_postrun_audit" / "semantic_evidence_support_postrun_audit.json"
PACKAGE_SUMMARY = ARTIFACTS / "stage11082_ready_lane_semantic_evidence_support_package" / "ready_lane_semantic_evidence_support_package.json"

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
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def load_runtime():
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    source = str(metadata.get("bounded_choice_aux_source") or "encoder_option_retrieval_pairwise")
    if source == "encoder_option_retrieval_pairwise" and not hasattr(model, "bounded_choice_pair_head"):
        pair_input_dim = _bounded_choice_pairwise_feature_dim(model)
        pair_hidden_dim = int(getattr(getattr(model, "config", None), "retrieval_head_dim", 0) or 0) or int(getattr(getattr(model, "config", None), "d_model", 0) or 0)
        model.bounded_choice_pair_head = torch.nn.Sequential(
            torch.nn.Linear(pair_input_dim, pair_hidden_dim, bias=True),
            torch.nn.SiLU(),
            torch.nn.Linear(pair_hidden_dim, 1, bias=True),
        )
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    model.to(EVAL_DEVICE)
    model.eval()
    return model, tokenizer, init_card, source


def audit_accuracy(card: dict[str, Any]) -> float | None:
    value = card.get("constrained_choice_top1_accuracy")
    return float(value) if isinstance(value, (int, float)) else None


def main() -> None:
    execution = load_json(EXECUTION_JSON)
    validation = load_json(VALIDATION_JSON)
    strict = load_json(STRICT_JSON)
    reserved_rows = load_jsonl(RESERVED_ROWS)
    baseline = load_json(BASELINE_AUDIT)
    package_summary = load_json(PACKAGE_SUMMARY)
    source_by_id = {str(row.get("row_id") or ""): row for row in reserved_rows}

    model, tokenizer, init_card, source = load_runtime()
    reserved_card = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=reserved_rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name="reserved_residual_candidate_slice",
        bounded_choice_aux_source=source,
        eval_batch_size=8,
    )

    enriched_cards = []
    for row in list(reserved_card.get("row_cards") or []):
        source_row = source_by_id.get(str(row.get("row_id") or ""), {})
        merged = dict(row)
        for key in ["language_family", "repo_family", "repo_id", "task_type", "source_root_id", "split_role"]:
            merged[key] = source_row.get(key)
        enriched_cards.append(merged)

    write_json(RESERVED_AUDIT_JSON, reserved_card)
    write_jsonl(RESERVED_ROWS_JSONL, enriched_cards)

    clean_validation_accuracy = audit_accuracy(validation)
    clean_strict_accuracy = audit_accuracy(strict)
    reserved_accuracy = audit_accuracy(reserved_card)

    baseline_clean = baseline["cleaned_canary_result"]
    baseline_reserved = baseline["reserved_candidate_result"]["overall"]["exact_accuracy"]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Audit the pairwise-scorer runtime on the current semantic-evidence support package against the unchanged cleaned canary and reserved residual bank.",
            "Decide whether scorer-architecture change improves the blocked evidence lane better than the stage11085 semantic-support-only branch.",
        ],
        "bounded_choice_aux_source": source,
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "execution_result": rel(EXECUTION_JSON),
            "clean_validation_audit": rel(VALIDATION_JSON),
            "clean_strict_audit": rel(STRICT_JSON),
            "reserved_rows": rel(RESERVED_ROWS),
            "baseline_audit": rel(BASELINE_AUDIT),
            "support_package": rel(PACKAGE_SUMMARY),
        },
        "support_package_metrics": package_summary.get("metrics"),
        "cleaned_canary_result": {
            "validation_accuracy": clean_validation_accuracy,
            "validation_miss_rows": [r.get("row_id") for r in validation.get("row_cards", []) if not r.get("constrained_choice_match")],
            "strict_accuracy": clean_strict_accuracy,
            "strict_miss_rows": [r.get("row_id") for r in strict.get("row_cards", []) if not r.get("constrained_choice_match")],
        },
        "reserved_candidate_result": {
            "overall": metric_block(enriched_cards, "constrained_choice_match"),
            "by_language": group_metrics(enriched_cards, "language_family", "constrained_choice_match"),
            "by_repo_family": group_metrics(enriched_cards, "repo_family", "constrained_choice_match"),
            "by_task_type": group_metrics(enriched_cards, "task_type", "constrained_choice_match"),
            "rows_with_target_rank_1": reserved_card.get("rows_with_target_rank_1"),
            "mismatches": [
                {
                    k: row.get(k)
                    for k in [
                        "row_id",
                        "language_family",
                        "repo_family",
                        "task_type",
                        "target_text",
                        "constrained_choice_top1_label",
                        "target_rank_full_vocab",
                        "full_vocab_top1_text",
                    ]
                }
                for row in enriched_cards
                if row.get("constrained_choice_match") is False
            ],
        },
        "delta_vs_stage11086": {
            "clean_validation_accuracy": None if baseline_clean["validation_accuracy"] is None or clean_validation_accuracy is None else clean_validation_accuracy - float(baseline_clean["validation_accuracy"]),
            "clean_strict_accuracy": None if baseline_clean["strict_accuracy"] is None or clean_strict_accuracy is None else clean_strict_accuracy - float(baseline_clean["strict_accuracy"]),
            "reserved_candidate_accuracy": None if baseline_reserved is None or reserved_accuracy is None else reserved_accuracy - float(baseline_reserved),
        },
        "headline_findings": [
            "This branch is only useful if the pairwise scorer moves the reserved evidence bank beyond the flat 0.5 result from stage11086 without regressing the cleaned canary.",
            "The semantic-support-only negative result is the immediate baseline; any improvement here would isolate scorer architecture as the missing lever.",
            "If this also stays flat, the next move is fresh heldout root families or a new evidence-role-specific scorer head rather than more reuse of current families.",
        ],
        "runtime_bundle": {
            "weights_sha256": (((execution.get("summary") or {}).get("runtime_model_bundle") or {}).get("weights_sha256")),
            "runtime_initialization": init_card,
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "reserved_audit_json": rel(RESERVED_AUDIT_JSON),
            "reserved_rows_jsonl": rel(RESERVED_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

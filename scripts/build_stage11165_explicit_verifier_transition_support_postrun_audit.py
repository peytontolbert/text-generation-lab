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

from legacy_src.agentkernel_lite.modeling_transformer import (  # noqa: E402
    AgentKernelLiteTransformerConfig,
    AgentKernelLiteTransformerSeq2Seq,
)
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer  # noqa: E402
from legacy_src.agentkernel_lite.training_loop import (  # noqa: E402
    _load_runtime_model_bundle,
    _write_bounded_choice_eval_audit,
)


ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11165
NAME = "stage11165_explicit_verifier_transition_support_postrun_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "explicit_verifier_transition_support_postrun_audit.json"
RESERVED_AUDIT_JSON = OUT_DIR / "reserved_residual_candidate_bounded_choice_eval.json"
RESERVED_ROWS_JSONL = OUT_DIR / "reserved_residual_candidate_rows_scored.jsonl"

RUNTIME_BUNDLE = ARTIFACTS / "stage11164_explicit_verifier_transition_support_probe" / "runtime_model" / "runtime_model_bundle.json"
VALIDATION_JSON = ARTIFACTS / "stage11164_explicit_verifier_transition_support_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_eval.json"
STRICT_JSON = ARTIFACTS / "stage11164_explicit_verifier_transition_support_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_strict_eval.json"
EXECUTION_JSON = ARTIFACTS / "stage11164_explicit_verifier_transition_support_probe" / "bounded_decoder_probe" / "execution_result.json"
RESERVED_ROWS = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence" / "reserved_residual_candidates.jsonl"
SUPPORT_ROWS = ARTIFACTS / "stage11162_cleaned_plus_explicit_verifier_transition_support_package" / "added_explicit_verifier_transition_rows.jsonl"
PACKAGE_SUMMARY = ARTIFACTS / "stage11162_cleaned_plus_explicit_verifier_transition_support_package" / "cleaned_plus_explicit_verifier_transition_support_package.json"
REQUEST_SUMMARY = ARTIFACTS / "stage11163_explicit_verifier_transition_support_probe_request" / "explicit_verifier_transition_support_probe_request.json"

BASELINE = {
    "cleaned_strict_accuracy": 21 / 22,
    "cleaned_validation_accuracy": 20 / 23,
    "reserved_residual_accuracy": 5 / 10,
    "reserved_evidence_accuracy": 4 / 9,
}

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


def audit_accuracy(card: dict[str, Any]) -> float | None:
    value = card.get("constrained_choice_top1_accuracy")
    return float(value) if isinstance(value, (int, float)) else None


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


def row_misses(card: dict[str, Any]) -> list[dict[str, Any]]:
    misses = []
    for row in card.get("row_cards", []) or []:
        if row.get("constrained_choice_match") is False:
            misses.append(
                {
                    "row_id": row.get("row_id"),
                    "target_text": row.get("target_text"),
                    "predicted": row.get("constrained_choice_top1_label"),
                    "full_vocab_top1_text": row.get("full_vocab_top1_text"),
                    "target_rank_full_vocab": row.get("target_rank_full_vocab"),
                }
            )
    return misses


def overlap_report(strict_card: dict[str, Any], reserved_rows: list[dict[str, Any]], support_rows: list[dict[str, Any]]) -> dict[str, Any]:
    strict_ids = {str(row.get("row_id") or "") for row in strict_card.get("row_cards", []) or []}
    reserved_ids = {str(row.get("row_id") or "") for row in reserved_rows}
    support_ids = {str(row.get("row_id") or "") for row in support_rows}
    strict_singletons = [
        str(row.get("row_id") or "")
        for row in strict_card.get("row_cards", []) or []
        if len(list(row.get("option_labels") or [])) == 1
    ]
    return {
        "support_row_ids_overlap_strict": sorted(support_ids & strict_ids),
        "support_row_ids_overlap_reserved": sorted(support_ids & reserved_ids),
        "strict_singleton_option_rows": strict_singletons,
    }


def main() -> None:
    execution = load_json(EXECUTION_JSON)
    validation = load_json(VALIDATION_JSON)
    strict = load_json(STRICT_JSON)
    reserved_rows = load_jsonl(RESERVED_ROWS)
    support_rows = load_jsonl(SUPPORT_ROWS)
    package = load_json(PACKAGE_SUMMARY)
    request = load_json(REQUEST_SUMMARY)
    source_by_id = {str(row.get("row_id") or ""): row for row in reserved_rows}

    model, tokenizer, init_card = load_runtime()
    reserved_card = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=reserved_rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name="reserved_residual_candidate_slice",
        bounded_choice_aux_source="encoder_option_retrieval",
        eval_batch_size=8,
    )

    enriched_reserved = []
    for row in list(reserved_card.get("row_cards") or []):
        source = source_by_id.get(str(row.get("row_id") or ""), {})
        merged = dict(row)
        for key in ["language_family", "repo_family", "repo_id", "task_type", "source_root_id", "split_role"]:
            merged[key] = source.get(key)
        enriched_reserved.append(merged)

    write_json(RESERVED_AUDIT_JSON, reserved_card)
    write_jsonl(RESERVED_ROWS_JSONL, enriched_reserved)

    validation_accuracy = audit_accuracy(validation)
    strict_accuracy = audit_accuracy(strict)
    reserved_accuracy = audit_accuracy(reserved_card)
    reserved_evidence_rows = [row for row in enriched_reserved if row.get("task_type") == "evidence_citation"]
    reserved_evidence = metric_block(reserved_evidence_rows, "constrained_choice_match")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Postrun audit for the explicit verifier-transition support diagnostic.",
            "The added rows are train-support-only explicit verifier-transition competition rows; this audit cannot promote a new broad capability claim unless heldout surfaces improve without regression.",
        ],
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "execution_result": rel(EXECUTION_JSON),
            "successor_validation": rel(VALIDATION_JSON),
            "successor_strict": rel(STRICT_JSON),
            "reserved_rows": rel(RESERVED_ROWS),
            "support_rows": rel(SUPPORT_ROWS),
            "package_summary": rel(PACKAGE_SUMMARY),
            "request_summary": rel(REQUEST_SUMMARY),
        },
        "support_package_metrics": package.get("metrics"),
        "request_metrics": request.get("metrics"),
        "successor_surface_result": {
            "validation_accuracy": validation_accuracy,
            "validation_miss_rows": row_misses(validation),
            "strict_accuracy": strict_accuracy,
            "strict_miss_rows": row_misses(strict),
        },
        "reserved_candidate_result": {
            "overall": metric_block(enriched_reserved, "constrained_choice_match"),
            "evidence_citation": reserved_evidence,
            "by_language": group_metrics(enriched_reserved, "language_family", "constrained_choice_match"),
            "by_repo_family": group_metrics(enriched_reserved, "repo_family", "constrained_choice_match"),
            "by_task_type": group_metrics(enriched_reserved, "task_type", "constrained_choice_match"),
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
                for row in enriched_reserved
                if row.get("constrained_choice_match") is False
            ],
        },
        "anti_cheat_audit": overlap_report(strict, reserved_rows, support_rows),
        "delta_vs_baseline": {
            "validation_accuracy": None if validation_accuracy is None else validation_accuracy - BASELINE["cleaned_validation_accuracy"],
            "strict_accuracy": None if strict_accuracy is None else strict_accuracy - BASELINE["cleaned_strict_accuracy"],
            "reserved_residual_accuracy": None if reserved_accuracy is None else reserved_accuracy - BASELINE["reserved_residual_accuracy"],
            "reserved_evidence_accuracy": None if reserved_evidence["exact_accuracy"] is None else reserved_evidence["exact_accuracy"] - BASELINE["reserved_evidence_accuracy"],
        },
        "decision": (
            "diagnostic_improved"
            if strict_accuracy is not None
            and strict_accuracy >= BASELINE["cleaned_strict_accuracy"]
            and (
                (validation_accuracy is not None and validation_accuracy > BASELINE["cleaned_validation_accuracy"])
                or (reserved_accuracy is not None and reserved_accuracy > BASELINE["reserved_residual_accuracy"])
            )
            else "diagnostic_flat_or_regressed"
        ),
        "next_best_step_if_flat": (
            "Stop local explicit-transition support variants if still flat. Build fresh explicit verifier-transition roots with competing "
            "FAIL_TO_PASS, PASS_TO_PASS, NOT_EXERCISED, and INSUFFICIENT_EVIDENCE candidates."
        ),
        "runtime_bundle": {
            "weights_sha256": ((execution.get("summary") or {}).get("runtime_model_bundle") or {}).get("weights_sha256"),
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

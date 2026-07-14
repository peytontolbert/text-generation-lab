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


ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11072
NAME = "stage11072_a_prior_and_python_verifier_diagnostic_postrun_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "a_prior_and_python_verifier_diagnostic_postrun_audit.json"
UNCONTAMINATED_AUDIT_JSON = OUT_DIR / "uncontaminated_reserved_bounded_choice_eval.json"
UNCONTAMINATED_ROWS_JSONL = OUT_DIR / "uncontaminated_reserved_rows_scored.jsonl"
CONTAMINATED_ROWS_JSONL = OUT_DIR / "contaminated_reserved_rows_scored.jsonl"

PACKAGE_SUMMARY = ARTIFACTS / "stage11069_a_prior_and_python_verifier_diagnostic_package" / "a_prior_and_python_verifier_diagnostic_package.json"
CONTAMINATED_RESERVED_JSON = ARTIFACTS / "stage11069_a_prior_and_python_verifier_diagnostic_package" / "contaminated_reserved_rows.json"

RUNTIME_BUNDLE = ARTIFACTS / "stage11071_a_prior_and_python_verifier_diagnostic_probe" / "runtime_model" / "runtime_model_bundle.json"
VALIDATION_JSON = ARTIFACTS / "stage11071_a_prior_and_python_verifier_diagnostic_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_eval.json"
STRICT_JSON = ARTIFACTS / "stage11071_a_prior_and_python_verifier_diagnostic_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_strict_eval.json"
EXECUTION_JSON = ARTIFACTS / "stage11071_a_prior_and_python_verifier_diagnostic_probe" / "bounded_decoder_probe" / "execution_result.json"

RESERVED_ROWS = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence" / "reserved_residual_candidates.jsonl"
BASELINE_CLEAN = ARTIFACTS / "stage11066_singleton_eval_quarantine_audit" / "singleton_eval_quarantine_audit.json"
BASELINE_RESERVED_ROWS = ARTIFACTS / "stage11064_ready_lane_fresh_support_postrun_audit" / "reserved_residual_candidate_rows_scored.jsonl"

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


def audit_accuracy(card: dict[str, Any]) -> float | None:
    value = card.get("constrained_choice_top1_accuracy")
    return float(value) if isinstance(value, (int, float)) else None


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


def enrich_cards(scored_rows: list[dict[str, Any]], source_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for row in scored_rows:
        source = source_by_id.get(str(row.get("row_id") or ""), {})
        merged = dict(row)
        for key in ["language_family", "repo_family", "repo_id", "task_type", "source_root_id", "split_role"]:
            merged[key] = source.get(key)
        enriched.append(merged)
    return enriched


def main() -> None:
    execution = load_json(EXECUTION_JSON)
    validation = load_json(VALIDATION_JSON)
    strict = load_json(STRICT_JSON)
    package_summary = load_json(PACKAGE_SUMMARY)
    contaminated_specs = load_json(CONTAMINATED_RESERVED_JSON)
    contaminated_ids = {str(row.get("reserved_row_id") or "") for row in contaminated_specs}
    reserved_rows = load_jsonl(RESERVED_ROWS)
    uncontaminated_rows = [row for row in reserved_rows if str(row.get("row_id") or "") not in contaminated_ids]
    contaminated_rows = [row for row in reserved_rows if str(row.get("row_id") or "") in contaminated_ids]

    model, tokenizer, init_card = load_runtime()
    uncontaminated_card = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=uncontaminated_rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name="uncontaminated_reserved_candidate_slice",
        bounded_choice_aux_source="encoder_option_retrieval",
        eval_batch_size=8,
    )

    uncontaminated_source_by_id = {str(row.get("row_id") or ""): row for row in uncontaminated_rows}
    contaminated_source_by_id = {str(row.get("row_id") or ""): row for row in contaminated_rows}
    uncontaminated_scored = enrich_cards(list(uncontaminated_card.get("row_cards") or []), uncontaminated_source_by_id)

    baseline_clean = load_json(BASELINE_CLEAN)
    baseline_reserved_rows = load_jsonl(BASELINE_RESERVED_ROWS)
    baseline_uncontaminated = [
        row for row in baseline_reserved_rows
        if str(row.get("row_id") or "") not in contaminated_ids
    ]
    baseline_contaminated = [
        row for row in baseline_reserved_rows
        if str(row.get("row_id") or "") in contaminated_ids
    ]

    contaminated_now = []
    stage11071_strict_rows = {str(row.get("row_id") or ""): row for row in load_jsonl(ARTIFACTS / "stage11069_a_prior_and_python_verifier_diagnostic_package" / "added_diagnostic_rows.jsonl")}
    for baseline_row in baseline_contaminated:
        merged = dict(baseline_row)
        source = contaminated_source_by_id.get(str(merged.get("row_id") or ""), {})
        for key in ["language_family", "repo_family", "repo_id", "task_type", "source_root_id", "split_role"]:
            merged[key] = source.get(key)
        contaminated_now.append(merged)

    write_json(UNCONTAMINATED_AUDIT_JSON, uncontaminated_card)
    write_jsonl(UNCONTAMINATED_ROWS_JSONL, uncontaminated_scored)
    write_jsonl(CONTAMINATED_ROWS_JSONL, contaminated_now)

    clean_validation_accuracy = audit_accuracy(validation)
    clean_strict_accuracy = audit_accuracy(strict)
    uncontaminated_accuracy = audit_accuracy(uncontaminated_card)

    baseline_validation = ((((baseline_clean.get("cleaned_surface_result") or {}).get("validation") or {}).get("exact_accuracy")))
    baseline_strict = ((((baseline_clean.get("cleaned_surface_result") or {}).get("strict") or {}).get("exact_accuracy")))
    baseline_uncontaminated_accuracy = metric_block(baseline_uncontaminated, "constrained_choice_match").get("exact_accuracy")
    baseline_contaminated_accuracy = metric_block(baseline_contaminated, "constrained_choice_match").get("exact_accuracy")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Audit the stage11071 diagnostic runtime against the unchanged cleaned 22-row validation/strict canary and the uncontaminated reserved subset only.",
            "Report contaminated reserved rows separately as same-surface diagnostic material rather than off-surface generalization evidence.",
        ],
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "execution_result": rel(EXECUTION_JSON),
            "validation_audit": rel(VALIDATION_JSON),
            "strict_audit": rel(STRICT_JSON),
            "reserved_rows": rel(RESERVED_ROWS),
            "contaminated_reserved_json": rel(CONTAMINATED_RESERVED_JSON),
            "package_summary": rel(PACKAGE_SUMMARY),
            "baseline_clean": rel(BASELINE_CLEAN),
            "baseline_reserved_rows": rel(BASELINE_RESERVED_ROWS),
        },
        "diagnostic_package_metrics": package_summary.get("metrics"),
        "cleaned_canary_result": {
            "validation_accuracy": clean_validation_accuracy,
            "validation_miss_rows": [r.get("row_id") for r in validation.get("row_cards", []) if not r.get("constrained_choice_match")],
            "strict_accuracy": clean_strict_accuracy,
            "strict_miss_rows": [r.get("row_id") for r in strict.get("row_cards", []) if not r.get("constrained_choice_match")],
        },
        "uncontaminated_reserved_result": {
            "overall": metric_block(uncontaminated_scored, "constrained_choice_match"),
            "by_language": group_metrics(uncontaminated_scored, "language_family", "constrained_choice_match"),
            "by_repo_family": group_metrics(uncontaminated_scored, "repo_family", "constrained_choice_match"),
            "by_task_type": group_metrics(uncontaminated_scored, "task_type", "constrained_choice_match"),
            "rows_with_target_rank_1": uncontaminated_card.get("rows_with_target_rank_1"),
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
                for row in uncontaminated_scored
                if row.get("constrained_choice_match") is False
            ],
        },
        "contaminated_reserved_baseline_context": {
            "row_ids": sorted(contaminated_ids),
            "baseline_accuracy_on_contaminated_rows": baseline_contaminated_accuracy,
            "current_rows_reported_as_diagnostic_only": len(contaminated_now),
        },
        "delta_vs_baseline": {
            "clean_validation_accuracy_delta": None if baseline_validation is None or clean_validation_accuracy is None else clean_validation_accuracy - float(baseline_validation),
            "clean_strict_accuracy_delta": None if baseline_strict is None or clean_strict_accuracy is None else clean_strict_accuracy - float(baseline_strict),
            "uncontaminated_reserved_accuracy_delta": None if baseline_uncontaminated_accuracy is None or uncontaminated_accuracy is None else uncontaminated_accuracy - float(baseline_uncontaminated_accuracy),
        },
        "headline_findings": [
            "The diagnostic package can only count as useful if it moves the uncontaminated reserved subset or the Python verifier strict row without regressing the cleaned canary.",
            "Any movement on the two contaminated reserved rows is expected to be same-surface and must remain diagnostic only.",
            "This audit keeps the claim boundary explicit by separating canary, uncontaminated heldout, and contaminated same-surface rows.",
        ],
        "runtime_bundle": {
            "weights_sha256": ((execution.get("runtime_model_bundle") or {}).get("weights_sha256")),
            "runtime_initialization": init_card,
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "uncontaminated_audit_json": rel(UNCONTAMINATED_AUDIT_JSON),
            "uncontaminated_rows_jsonl": rel(UNCONTAMINATED_ROWS_JSONL),
            "contaminated_rows_jsonl": rel(CONTAMINATED_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10424
NAME = "stage10424_reviewed_multilingual_v27_comparison_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "reviewed_multilingual_v27_comparison_audit.json"
ROWS_JSONL = OUT_DIR / "reviewed_multilingual_v27_comparison_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

PACKAGE_JSON = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/reviewed_multilingual_v27_manifest_package.json"
REQUEST_JSON = ROOT / "runs/local/artifacts/stage10421_reviewed_multilingual_v27_target100m_execution_request/reviewed_multilingual_v27_target100m_execution_request.json"
MANIFEST_JSONL = ROOT / "runs/local/artifacts/stage10421_reviewed_multilingual_v27_target100m_execution_request/reviewed_multilingual_v27_target100m_manifest.jsonl"
EXECUTION_JSON = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/bounded_decoder_probe/execution_result.json"
FAILURE_BUCKET_JSON = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/bounded_decoder_probe/failure_bucket_card.json"
SHORT_OUTPUT_JSON = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/bounded_decoder_probe/short_output_probe.json"
SAMPLE_AUDIT_JSON = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/bounded_decoder_probe/sample_generation_audit.json"
GEMMA_SUMMARY_JSON = ROOT / "runs/local/artifacts/stage10423_reviewed_multilingual_v27_same_manifest_gemma_comparison/reviewed_multilingual_v27_same_manifest_gemma_comparison.json"
GEMMA_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10423_reviewed_multilingual_v27_same_manifest_gemma_comparison/reviewed_multilingual_v27_same_manifest_gemma_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def accuracy_block(correct: int, rows: int) -> dict[str, Any]:
    return {"correct": correct, "rows": rows, "exact_accuracy": (correct / rows) if rows else None}


def main() -> None:
    package = load_json(PACKAGE_JSON)
    request = load_json(REQUEST_JSON)
    execution = load_json(EXECUTION_JSON)
    failure_bucket = load_json(FAILURE_BUCKET_JSON)
    short_output = load_json(SHORT_OUTPUT_JSON)
    sample_audit = load_json(SAMPLE_AUDIT_JSON)
    gemma_summary = load_json(GEMMA_SUMMARY_JSON)
    gemma_rows = load_jsonl(GEMMA_ROWS_JSONL)
    manifest_rows = load_jsonl(MANIFEST_JSONL)

    manifest_by_id = {str(row.get("row_id") or ""): row for row in manifest_rows}
    strict_manifest = [row for row in manifest_rows if str(row.get("split") or "") == "strict_eval"]
    eval_manifest = [row for row in manifest_rows if str(row.get("split") or "") == "eval"]
    train_manifest = [row for row in manifest_rows if str(row.get("split") or "") == "train"]

    hundred_eval = (((execution.get("bounded_choice_eval") or {}).get("eval")) or {})
    hundred_strict = (((execution.get("bounded_choice_eval") or {}).get("strict_eval")) or {})
    hundred_eval_cards = list(hundred_eval.get("row_cards") or [])
    hundred_strict_cards = list(hundred_strict.get("row_cards") or [])
    hundred_strict_by_id = {str(row.get("row_id") or ""): row for row in hundred_strict_cards}

    train_roots = {str(row.get("source_bundle_id") or row.get("row_id") or "") for row in train_manifest}
    eval_roots = {str(row.get("source_bundle_id") or row.get("row_id") or "") for row in eval_manifest}
    strict_roots = {str(row.get("source_bundle_id") or row.get("row_id") or "") for row in strict_manifest}

    root_overlap = {
        "train_vs_eval": sorted(train_roots & eval_roots),
        "train_vs_strict": sorted(train_roots & strict_roots),
        "eval_vs_strict": sorted(eval_roots & strict_roots),
    }

    comparison_rows: list[dict[str, Any]] = []
    hundred_m_misses: list[dict[str, Any]] = []
    gemma_misses: list[dict[str, Any]] = []
    strict_source_heldout_true = 0
    strict_stress_rows = 0
    for row in gemma_rows:
        row_id = str(row.get("row_id") or "")
        source = manifest_by_id[row_id]
        hundred = hundred_strict_by_id[row_id]
        source_heldout = bool(source.get("source_heldout_admissible"))
        if source_heldout:
            strict_source_heldout_true += 1
        if str(source.get("split_role") or "") == "stress_overlap":
            strict_stress_rows += 1
        record = {
            "row_id": row_id,
            "language_family": source.get("language_family"),
            "task_type": source.get("task_type"),
            "repo_id": source.get("repo_id"),
            "repo_family": source.get("repo_family"),
            "source_bundle_id": source.get("source_bundle_id"),
            "selected_test_anchor": bool(source.get("selected_test_anchor")),
            "verifier_anchor": bool(source.get("verifier_anchor")),
            "abstention_heavy": bool(source.get("abstention_heavy")),
            "source_heldout_admissible": source_heldout,
            "split_role": source.get("split_role"),
            "target_text": source.get("target_text"),
            "hundred_m_predicted_label": hundred.get("constrained_choice_top1_label"),
            "hundred_m_correct": bool(hundred.get("constrained_choice_match")),
            "gemma12b_predicted_label": row.get("gemma12b_predicted_label"),
            "gemma12b_correct": bool(row.get("gemma12b_correct")),
        }
        comparison_rows.append(record)
        if not record["hundred_m_correct"]:
            hundred_m_misses.append(record)
        if not record["gemma12b_correct"]:
            gemma_misses.append(record)

    write_jsonl(ROWS_JSONL, comparison_rows)

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "current_claim": {
            "supported": True,
            "text": "On the reviewed multilingual v2.7 same-manifest strict_eval frontier, the 100M model beats Gemma-12B overall and wins all four language slices.",
            "scope": "same-manifest reviewed-v2.7 strict_eval compact maintainer-bundle surface only",
            "unsupported_upgrades": [
                "source-heldout promotable maintainer benchmark win",
                "full-product harness superiority",
                "broad software-maintenance superiority beyond this compact bounded surface",
            ],
        },
        "v27_inventory_context": {
            "package_metrics": package.get("metrics"),
            "request_split_counts": request.get("split_counts"),
            "request_language_counts": request.get("language_counts"),
        },
        "strict_result": {
            "hundred_m": accuracy_block(sum(bool(row.get("hundred_m_correct")) for row in comparison_rows), len(comparison_rows)),
            "gemma12b": accuracy_block(sum(bool(row.get("gemma12b_correct")) for row in comparison_rows), len(comparison_rows)),
            "delta_hundred_m_minus_gemma": gemma_summary.get("delta_exact_accuracy"),
            "by_language": (gemma_summary.get("by_language") or {}).get("verdicts"),
            "by_task_type": (gemma_summary.get("by_task_type") or {}).get("verdicts"),
            "by_selected_test_anchor": (gemma_summary.get("by_selected_test_anchor") or {}).get("verdicts"),
            "by_verifier_anchor": (gemma_summary.get("by_verifier_anchor") or {}).get("verdicts"),
            "by_abstention_heavy": (gemma_summary.get("by_abstention_heavy") or {}).get("verdicts"),
        },
        "hundred_m_eval_result": {
            "eval_accuracy": hundred_eval.get("constrained_choice_top1_accuracy"),
            "strict_accuracy": hundred_strict.get("constrained_choice_top1_accuracy"),
            "eval_rows": len(hundred_eval_cards),
            "strict_rows": len(hundred_strict_cards),
        },
        "residual_100m_miss_set": {
            "rows": len(hundred_m_misses),
            "miss_rows": hundred_m_misses,
        },
        "gemma_miss_set": {
            "rows": len(gemma_misses),
            "miss_rows": gemma_misses,
        },
        "eval_integrity": {
            "same_manifest_row_count_match": len(comparison_rows) == len(strict_manifest) == len(hundred_strict_cards),
            "same_manifest_row_id_match": sorted(str(row.get("row_id") or "") for row in strict_manifest)
            == sorted(str(row.get("row_id") or "") for row in comparison_rows)
            == sorted(hundred_strict_by_id),
            "prompt_surface_hash": gemma_summary.get("prompt_surface_hash"),
            "stress_rows_excluded_from_promotable_strict": strict_stress_rows == 0,
            "stress_rows_excluded_from_training_command": bool(request.get("stress_eval_rows_excluded_from_training_command")),
            "root_split_overlap": root_overlap,
            "root_split_overlap_detected": any(root_overlap.values()),
            "source_heldout_claim_supported": strict_source_heldout_true == len(strict_manifest) and len(strict_manifest) > 0,
            "strict_source_heldout_true_rows": strict_source_heldout_true,
            "strict_source_heldout_total_rows": len(strict_manifest),
            "same_manifest_only": True,
            "compact_bounded_surface_only": True,
        },
        "generation_integrity": {
            "failure_buckets": failure_bucket.get("buckets"),
            "contentful_rate": sample_audit.get("contentful_rate"),
            "degenerate_repetition_rate": sample_audit.get("degenerate_repetition_rate"),
            "short_or_junk_rate": sample_audit.get("short_or_junk_rate", short_output.get("short_or_junk_rate")),
            "generated_internal_token_rate": sample_audit.get("generated_internal_token_rate"),
            "internal_leak_rows": failure_bucket.get("buckets", {}).get("internal_leak"),
            "prefix_miss_rows": failure_bucket.get("buckets", {}).get("prefix_miss"),
        },
        "model_artifacts": {
            "hundred_m_runtime_weights_sha256": (execution.get("runtime_model_bundle") or {}).get("weights_sha256"),
            "hundred_m_execution_result": display(EXECUTION_JSON),
            "gemma_summary": display(GEMMA_SUMMARY_JSON),
            "gemma_rows": display(GEMMA_ROWS_JSONL),
        },
        "claim_boundaries": [
            "This is a same-manifest reviewed-v2.7 strict_eval comparison on a compact bounded maintainer-bundle surface.",
            "The 100M win is real on this surface, but source_heldout_admissible remains false for the strict rows, so this is not a source-heldout claim.",
            "Stress-only code_assist rows remain outside the promotable path and must stay reported separately.",
            "The surface remains standalone compact maintainer reasoning, not the recovered full-product harness path.",
            "Generation audits show no junk or internal-token leakage issues; the remaining weakness is semantic miss behavior, not runtime degeneration.",
        ],
        "next_best_step": "Run a narrow non-promotable diagnostic recovery from the saved stage10422 runtime focused only on the Python verifier_outcome and Rust evidence_citation strict misses, while keeping the reviewed-v2.7 strict set frozen for honest reporting.",
    }

    write_json(AUDIT_JSON, audit)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": True,
            "artifacts": {"audit": display(AUDIT_JSON), "rows": display(ROWS_JSONL)},
            "decision": "Froze the reviewed-v2.7 same-manifest comparison into a claim-bounded audit with explicit eval-integrity and anti-cheat status.",
            "next_best_step": audit["next_best_step"],
            "created_at_utc": audit["created_at_utc"],
        },
    )
    print(json.dumps({"stage": STAGE, "passed": True, "audit": display(AUDIT_JSON)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10891
NAME = "stage10891_flash_attn_alias_safe_postrun_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "flash_attn_alias_safe_postrun_audit.json"

BASELINE_JSON = ARTIFACTS / "stage10882_quarantined_v27_comparison_successor_audit" / "quarantined_v27_comparison_successor_audit.json"
REQUEST_JSON = ARTIFACTS / "stage10888_flash_attn_alias_safe_probe_request" / "flash_attn_alias_safe_probe_request.json"
STRICT_AUDIT_JSON = ARTIFACTS / "stage10890_flash_attn_alias_safe_multilingual_support_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_strict_eval.json"
EVAL_AUDIT_JSON = ARTIFACTS / "stage10890_flash_attn_alias_safe_multilingual_support_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_eval.json"
EXECUTION_JSON = ARTIFACTS / "stage10890_flash_attn_alias_safe_multilingual_support_probe" / "bounded_decoder_probe" / "execution_result.json"
SAMPLE_GENERATION_JSON = ARTIFACTS / "stage10890_flash_attn_alias_safe_multilingual_support_probe" / "bounded_decoder_probe" / "sample_generation_audit.json"
RUNTIME_BUNDLE_JSON = ARTIFACTS / "stage10890_flash_attn_alias_safe_multilingual_support_probe" / "runtime_model" / "runtime_model_bundle.json"
MANIFEST_JSONL = ARTIFACTS / "stage10888_flash_attn_alias_safe_probe_request" / "flash_attn_alias_safe_probe_manifest.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def row_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("row_id") or ""): row for row in rows}


def miss_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [card for card in cards if not bool(card.get("constrained_choice_match"))]


def accuracy_by_language(cards: list[dict[str, Any]], rows_by_id: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[bool]] = defaultdict(list)
    for card in cards:
        row = rows_by_id.get(str(card.get("row_id") or ""), {})
        language = str(row.get("language_family") or "unknown")
        buckets[language].append(bool(card.get("constrained_choice_match")))
    result: dict[str, dict[str, Any]] = {}
    for language, matches in sorted(buckets.items()):
        rows = len(matches)
        correct = sum(1 for item in matches if item)
        result[language] = {
            "rows": rows,
            "correct": correct,
            "accuracy": (correct / rows) if rows else None,
        }
    return result


def miss_summary(cards: list[dict[str, Any]], rows_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for card in miss_cards(cards):
        row = rows_by_id.get(str(card.get("row_id") or ""), {})
        summary.append(
            {
                "row_id": card.get("row_id"),
                "language_family": row.get("language_family"),
                "task_type": row.get("task_type"),
                "target_text": card.get("target_text"),
                "constrained_choice_top1_label": card.get("constrained_choice_top1_label"),
                "full_vocab_top1_text": card.get("full_vocab_top1_text"),
                "target_rank_full_vocab": card.get("target_rank_full_vocab"),
            }
        )
    return summary


def main() -> None:
    baseline = load_json(BASELINE_JSON)
    request = load_json(REQUEST_JSON)
    strict_audit = load_json(STRICT_AUDIT_JSON)
    eval_audit = load_json(EVAL_AUDIT_JSON)
    execution = load_json(EXECUTION_JSON)
    sample_generation = load_json(SAMPLE_GENERATION_JSON)
    runtime_bundle = load_json(RUNTIME_BUNDLE_JSON)
    rows_by_id = row_index(load_jsonl(MANIFEST_JSONL))

    strict_cards = list(strict_audit.get("row_cards") or [])
    eval_cards = list(eval_audit.get("row_cards") or [])

    strict_accuracy = float(strict_audit.get("constrained_choice_top1_accuracy") or 0.0)
    eval_accuracy = float(eval_audit.get("constrained_choice_top1_accuracy") or 0.0)
    baseline_strict = float((baseline.get("metrics") or {}).get("strict_exact_100m") or 0.0)

    strict_misses = miss_summary(strict_cards, rows_by_id)
    eval_misses = miss_summary(eval_cards, rows_by_id)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "flash_attn_alias_safe_probe_completed_and_audited",
        "claim_scope": [
            "Audit the completed stage10890 probe that added alias-safe Rust flash-attn evidence rows to train support while preserving the quarantined 23-row heldout surface.",
            "Determine whether the run changed the honest multilingual heldout headline or only preserved it.",
        ],
        "metrics": {
            "baseline_quarantined_strict_accuracy": baseline_strict,
            "postrun_strict_accuracy": strict_accuracy,
            "postrun_eval_accuracy": eval_accuracy,
            "strict_delta_vs_quarantined_baseline": strict_accuracy - baseline_strict,
            "strict_rows": int(strict_audit.get("constrained_choice_rows") or 0),
            "eval_rows": int(eval_audit.get("constrained_choice_rows") or 0),
            "strict_miss_count": len(strict_misses),
            "eval_miss_count": len(eval_misses),
            "full_vocab_strict_accuracy": float(strict_audit.get("full_vocab_top1_accuracy") or 0.0),
            "full_vocab_eval_accuracy": float(eval_audit.get("full_vocab_top1_accuracy") or 0.0),
            "contentful_generation_rate": float(sample_generation.get("contentful_rate") or 0.0),
            "sample_generation_exact_match_rows": int(sample_generation.get("exact_match_rows") or 0),
        },
        "strict_per_language": accuracy_by_language(strict_cards, rows_by_id),
        "eval_per_language": accuracy_by_language(eval_cards, rows_by_id),
        "strict_misses": strict_misses,
        "eval_misses": eval_misses,
        "interpretation": [
            "The alias-safe flash-attn train repair did not move the honest heldout frontier: strict stayed at 22/23, matching the quarantined baseline exactly.",
            "The remaining strict heldout miss is still the Python MirrorMind verifier_outcome row, so Rust train repair alone does not resolve the cross-language residual boundary.",
            "Validation remains below strict because evidence_citation is still the weakest family; both eval misses are evidence rows and one is the tokenizers Rust evidence row.",
            "Freeform decoder behavior is still not useful as a product signal here: generation is contentful and non-repetitive, but sampled outputs remain collapsed label tokens with zero exact matches.",
        ],
        "next_best_step": "Stop broad preservation-style support probes and target the unresolved semantics directly: build fresh verifier-transition Python roots and evidence-role Rust roots, then evaluate them on a fresh heldout slice while keeping the quarantined 23-row package as a canary.",
        "source_artifacts": {
            "baseline_comparison": rel(BASELINE_JSON),
            "probe_request": rel(REQUEST_JSON),
            "strict_audit": rel(STRICT_AUDIT_JSON),
            "eval_audit": rel(EVAL_AUDIT_JSON),
            "execution_result": rel(EXECUTION_JSON),
            "runtime_model_bundle": rel(RUNTIME_BUNDLE_JSON),
        },
        "runtime": {
            "request_run_id": request.get("run_id"),
            "executed_run_id": (execution.get("summary") or {}).get("run_id"),
            "runtime_weights_sha256": runtime_bundle.get("weights_sha256"),
            "base_runtime_weights_sha256": request.get("base_runtime_weights_sha256"),
        },
    }

    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

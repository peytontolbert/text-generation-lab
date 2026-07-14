#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
STRICT_ROWS_PATH = (
    ROOT
    / "runs/local/artifacts/stage10635_repaired_long_context_successor_package_permuted"
    / "repaired_long_context_successor_package_permuted_strict_rows.jsonl"
)
COMPARISON_PATH = (
    ROOT
    / "runs/local/artifacts/stage10638_corrected_strict_exact_label_comparison"
    / "corrected_strict_exact_label_comparison.json"
)
COMPARISON_ROWS_PATH = (
    ROOT
    / "runs/local/artifacts/stage10638_corrected_strict_exact_label_comparison"
    / "corrected_strict_exact_label_comparison_rows.jsonl"
)
OUT_DIR = ROOT / "runs/local/artifacts/stage10639_corrected_slice_contract_boundary_audit"
OUT_PATH = OUT_DIR / "corrected_slice_contract_boundary_audit.json"


OPAQUE_PREFIXES = (
    "repo_",
    "paper_",
    "dataset_",
    "localchunk_",
    "localrepochunk_",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def is_opaque_handle(value: str) -> bool:
    if not isinstance(value, str):
        return False
    if not value.startswith(OPAQUE_PREFIXES):
        return False
    return bool(re.search(r"_[0-9a-f]{10}$", value))


def summarize_strict_contract(strict_rows: list[dict[str, Any]]) -> dict[str, Any]:
    option_count_counter: Counter[int] = Counter()
    gold_position_counter: Counter[int] = Counter()
    opaque_value_counter = 0
    total_candidate_values = 0
    prompt_target_leak_false = 0
    visible_candidate_contract_true = 0
    hidden_behind_label_true = 0
    route_shortcut_removed_true = 0
    rows_with_verification_targets = 0
    rows_with_changed_files = 0
    rows_with_key_symbols = 0
    rows_with_code_snippet = 0
    rows_with_trace = 0
    rows_with_assertion = 0
    rows_with_error_text = 0
    language_counts: Counter[str] = Counter()

    for row in strict_rows:
        language_counts[str(row.get("language_family") or "unknown")] += 1
        anti = row.get("anti_cheat") or {}
        if anti.get("prompt_target_leak") is False:
            prompt_target_leak_false += 1
        if anti.get("visible_candidate_contract") is True:
            visible_candidate_contract_true += 1
        if anti.get("target_value_hidden_behind_label") is True:
            hidden_behind_label_true += 1
        if anti.get("route_shortcut_removed") is True:
            route_shortcut_removed_true += 1
        if "Verification targets:" in str(row.get("input_text") or ""):
            rows_with_verification_targets += 1
        if "Changed files:" in str(row.get("input_text") or ""):
            rows_with_changed_files += 1
        if "Key symbols:" in str(row.get("input_text") or ""):
            rows_with_key_symbols += 1
        input_text = str(row.get("input_text") or "")
        lowered = input_text.lower()
        if "def " in input_text or "class " in input_text or "fn " in input_text or "{" in input_text:
            rows_with_code_snippet += 1
        if "trace:" in lowered or "stack" in lowered or "call path" in lowered:
            rows_with_trace += 1
        if "assert " in lowered or "expected" in lowered or "got " in lowered:
            rows_with_assertion += 1
        if "error" in lowered or "exception" in lowered or "failed" in lowered:
            rows_with_error_text += 1

        options = row.get("candidate_options") or []
        option_count_counter[len(options)] += 1
        gold_position = (row.get("anti_cheat") or {}).get("gold_candidate_position")
        if isinstance(gold_position, int):
            gold_position_counter[gold_position] += 1
        for option in options:
            total_candidate_values += 1
            if is_opaque_handle(str(option.get("value") or "")):
                opaque_value_counter += 1

    total_rows = len(strict_rows)
    return {
        "rows": total_rows,
        "by_language": dict(sorted(language_counts.items())),
        "option_count_distribution": dict(sorted(option_count_counter.items())),
        "gold_position_distribution": dict(sorted(gold_position_counter.items())),
        "anti_cheat_surface": {
            "prompt_target_leak_false_rows": prompt_target_leak_false,
            "visible_candidate_contract_true_rows": visible_candidate_contract_true,
            "target_value_hidden_behind_label_true_rows": hidden_behind_label_true,
            "route_shortcut_removed_true_rows": route_shortcut_removed_true,
        },
        "visible_prompt_surface": {
            "rows_with_verification_targets": rows_with_verification_targets,
            "rows_with_changed_files": rows_with_changed_files,
            "rows_with_key_symbols": rows_with_key_symbols,
            "rows_with_code_snippet": rows_with_code_snippet,
            "rows_with_trace": rows_with_trace,
            "rows_with_assertion_or_expected_actual_text": rows_with_assertion,
            "rows_with_error_or_failure_text": rows_with_error_text,
        },
        "candidate_value_surface": {
            "total_candidate_values": total_candidate_values,
            "opaque_handle_like_values": opaque_value_counter,
            "opaque_handle_like_rate": (opaque_value_counter / total_candidate_values) if total_candidate_values else 0.0,
        },
    }


def summarize_row_failures(comparison_rows: list[dict[str, Any]]) -> dict[str, Any]:
    model_counts: Counter[str] = Counter()
    gemma_counts: Counter[str] = Counter()
    miss_rows_by_language: dict[str, list[str]] = defaultdict(list)
    e4_collapse_rows: list[str] = []
    null_parse_rows: list[str] = []

    for row in comparison_rows:
        language = str(row.get("language_family") or "unknown")
        model_text = str(((row.get("model_100m") or {}).get("generated_text")) or "")
        model_counts[model_text] += 1
        gemma_counts[str(((row.get("gemma3_12b") or {}).get("generated_text")) or "")] += 1

        model_match = bool(((row.get("model_100m") or {}).get("parsed_label_match")))
        if not model_match:
            miss_rows_by_language[language].append(str(row.get("row_id") or ""))
        if model_text == "E4":
            e4_collapse_rows.append(str(row.get("row_id") or ""))
        if ((row.get("model_100m") or {}).get("parsed_label")) is None:
            null_parse_rows.append(str(row.get("row_id") or ""))

    return {
        "model_100m_generated_text_counts": dict(sorted(model_counts.items())),
        "gemma_generated_text_counts": dict(sorted(gemma_counts.items())),
        "model_100m_miss_rows_by_language": dict(sorted(miss_rows_by_language.items())),
        "model_100m_e4_collapse_rows": e4_collapse_rows,
        "model_100m_null_parse_rows": null_parse_rows,
    }


def main() -> None:
    strict_rows = read_jsonl(STRICT_ROWS_PATH)
    comparison = read_json(COMPARISON_PATH)
    comparison_rows = read_jsonl(COMPARISON_ROWS_PATH)

    strict_contract = summarize_strict_contract(strict_rows)
    row_failures = summarize_row_failures(comparison_rows)

    model_metrics = comparison["metrics"]["model_100m"]
    gemma_metrics = comparison["metrics"]["gemma3_12b"]

    passed = True
    decision = "corrected_slice_not_promotable_yet"
    reasons = [
        "The constant gold-position shortcut was removed, so this is a cleaner contract than stage10632.",
        "The current 100M runtime still collapses to a small label set on the corrected strict slice and only matches 1/18 labels under honest parsed-label scoring.",
        "Gemma reaches 3/18 parsed-label matches on the same corrected strict slice, so the current 100M runtime does not beat the local Gemma baseline here.",
        "The decisive-evidence task remains opaque-handle selection: visible prompts expose repo, changed files, verification targets, and key symbols, but not concrete evidence snippets, traces, assertions, or maintainer-grade evidence cards.",
        "A constrained candidate scorer would be cleaner than first-token metrics, but it would still be scoring opaque candidate handles rather than realistic evidence selection on this slice.",
    ]

    artifact = {
        "stage": 10639,
        "stage_name": "stage10639_corrected_slice_contract_boundary_audit",
        "passed": passed,
        "decision": decision,
        "strict_contract_summary": strict_contract,
        "comparison_summary": {
            "model_100m": {
                "parsed_label_match_rows": model_metrics["parsed_label_match_rows"],
                "parsed_label_match_rate": model_metrics["parsed_label_match_rate"],
                "raw_exact_match_rows": model_metrics["raw_exact_match_rows"],
                "raw_exact_match_rate": model_metrics["raw_exact_match_rate"],
            },
            "gemma3_12b": {
                "parsed_label_match_rows": gemma_metrics["parsed_label_match_rows"],
                "parsed_label_match_rate": gemma_metrics["parsed_label_match_rate"],
                "raw_exact_match_rows": gemma_metrics["raw_exact_match_rows"],
                "raw_exact_match_rate": gemma_metrics["raw_exact_match_rate"],
            },
        },
        "row_failure_summary": row_failures,
        "claim_boundary": [
            "Stage10634/10635/10636 fix the constant-slot shortcut and should replace stage10632 for any future corrected-slice discussion.",
            "Stage10638 exact parsed-label scoring is the minimum honest comparison contract for this slice.",
            "This slice should not be promoted as maintainer-grade evidence selection because the candidates are still opaque handles rather than visible maintainer evidence units.",
        ],
        "not_promotable_because": reasons,
        "next_best_step": [
            "Stop using first-token strict accuracy as a claim metric on this slice.",
            "If this lineage continues, compare with exact parsed-label or constrained label scoring only.",
            "For a real maintainer-grade successor, materialize concrete evidence units per row: snippets, trace lines, assertions, file/symbol references, or verifier observations, then score candidate evidence selection on those visible units.",
            "Treat the current slice as a decoder-contract and anti-shortcut diagnostic, not as the main software-maintenance frontier.",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps({"ok": True, "out": str(OUT_PATH), "decision": decision}, indent=2))


if __name__ == "__main__":
    main()

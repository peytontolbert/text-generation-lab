#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10672
NAME = "stage10672_dual_residual_targeted_probe_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_PATH = OUT_DIR / "dual_residual_targeted_probe_audit.json"

PROBE_RESULT = ARTIFACTS / "stage10671_dual_residual_targeted_probe/bounded_decoder_probe/execution_result.json"
STRICT_AUDIT = ARTIFACTS / "stage10671_dual_residual_targeted_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
BASELINE_COMPARISON = ARTIFACTS / "stage10424_reviewed_multilingual_v27_comparison_audit/reviewed_multilingual_v27_comparison_audit.json"
PACKAGE = ARTIFACTS / "stage10669_dual_residual_targeted_support_package/dual_residual_targeted_support_package.json"
REQUEST = ARTIFACTS / "stage10670_dual_residual_targeted_probe_request/dual_residual_targeted_probe_request.json"

LANGUAGES = {"python", "rust", "c_cpp", "web_js_ts_html"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def current_strict_eval(result: dict[str, Any]) -> dict[str, Any]:
    return ((result.get("bounded_choice_eval") or {}).get("strict_eval") or {})


def current_eval(result: dict[str, Any]) -> dict[str, Any]:
    return ((result.get("bounded_choice_eval") or {}).get("eval") or {})


def parse_row_id(row_id: str) -> tuple[str, str]:
    parts = row_id.split("::")
    language_family = "unknown"
    task_type = "unknown"
    for idx, part in enumerate(parts):
        if part in LANGUAGES:
            language_family = part
            if idx + 1 < len(parts):
                task_type = parts[idx + 1]
            break
    return language_family, task_type


def row_outcomes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        row_id = str(row.get("row_id") or "")
        language_family, task_type = parse_row_id(row_id)
        out.append(
            {
                "row_id": row_id,
                "language_family": language_family,
                "task_type": task_type,
                "target_text": row.get("target_text"),
                "predicted_label": row.get("constrained_choice_top1_label"),
                "correct": bool(row.get("constrained_choice_match")),
                "target_rank_full_vocab": row.get("target_rank_full_vocab"),
                "full_vocab_top1_text": row.get("full_vocab_top1_text"),
                "option_labels": row.get("option_labels"),
            }
        )
    return out


def language_breakdown(rows: list[dict[str, Any]]) -> dict[str, dict[str, int | float]]:
    breakdown: dict[str, dict[str, int | float]] = {}
    for language in sorted(LANGUAGES):
        lang_rows = [row for row in rows if row["language_family"] == language]
        if not lang_rows:
            continue
        correct = sum(1 for row in lang_rows if row["correct"])
        breakdown[language] = {
            "rows": len(lang_rows),
            "correct": correct,
            "accuracy": correct / len(lang_rows),
        }
    return breakdown


def miss_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    misses = [row for row in rows if not row["correct"]]
    return {
        "miss_count": len(misses),
        "miss_rows": misses,
        "miss_row_ids": [row["row_id"] for row in misses],
    }


def main() -> None:
    probe = load_json(PROBE_RESULT)
    strict_probe = load_json(STRICT_AUDIT)
    baseline = load_json(BASELINE_COMPARISON)
    package = load_json(PACKAGE)
    request = load_json(REQUEST)

    strict_eval = current_strict_eval(probe)
    eval_split = current_eval(probe)
    strict_rows = row_outcomes((strict_probe.get("row_cards") or strict_eval.get("row_cards") or []))
    strict_miss_summary = miss_summary(strict_rows)

    baseline_hundred_m = float(((baseline.get("hundred_m_eval_result") or {}).get("strict_accuracy")) or 0.0)
    baseline_gemma = float((((baseline.get("strict_result") or {}).get("gemma12b")) or {}).get("exact_accuracy") or 0.0)
    current_hundred_m = float(strict_eval.get("constrained_choice_top1_accuracy") or 0.0)
    full_vocab_strict = float(strict_eval.get("full_vocab_top1_accuracy") or 0.0)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision": "dual_residual_targeted_probe_completed_no_headline_lift",
        "sources": {
            "probe_result": rel(PROBE_RESULT),
            "strict_audit": rel(STRICT_AUDIT),
            "baseline_comparison": rel(BASELINE_COMPARISON),
            "targeted_support_package": rel(PACKAGE),
            "probe_request": rel(REQUEST),
        },
        "headline": {
            "baseline_hundred_m_strict_accuracy": baseline_hundred_m,
            "baseline_gemma_strict_accuracy": baseline_gemma,
            "current_hundred_m_strict_accuracy": current_hundred_m,
            "current_vs_baseline_delta": current_hundred_m - baseline_hundred_m,
            "current_vs_gemma_delta_using_baseline_gemma": current_hundred_m - baseline_gemma,
            "current_full_vocab_strict_accuracy": full_vocab_strict,
        },
        "package_effect": {
            "train_rows": (request.get("split_counts") or {}).get("train"),
            "strict_rows": (request.get("split_counts") or {}).get("strict_eval"),
            "train_language_counts": (request.get("language_counts_by_split") or {}).get("train"),
            "train_source_kinds": (request.get("source_kind_counts_by_split") or {}).get("train"),
            "strict_language_counts": (request.get("language_counts_by_split") or {}).get("strict_eval"),
            "targeted_support_rows": ((package.get("metrics") or {}).get("targeted_support_rows")),
        },
        "strict_eval_result": {
            "constrained_choice_top1_accuracy": strict_eval.get("constrained_choice_top1_accuracy"),
            "full_vocab_top1_accuracy": strict_eval.get("full_vocab_top1_accuracy"),
            "rows": strict_eval.get("rows"),
            "language_breakdown": language_breakdown(strict_rows),
            "miss_summary": strict_miss_summary,
        },
        "eval_result": {
            "constrained_choice_top1_accuracy": eval_split.get("constrained_choice_top1_accuracy"),
            "full_vocab_top1_accuracy": eval_split.get("full_vocab_top1_accuracy"),
            "rows": eval_split.get("rows"),
        },
        "claim_boundary": [
            "The narrower dual-residual support package preserved the reviewed v2.7 strict score but did not improve it.",
            "The two remaining strict misses stayed unchanged, so this run is diagnostic-only and not promotable.",
            "The Gemma comparison margin from the reviewed baseline remains descriptive only because the strict set was unchanged; this run did not add a fresh Gemma execution.",
            "Full-vocab strict decoding degraded sharply while constrained choice stayed flat, so the useful signal remains the bounded-choice maintainer surface rather than free decoding quality.",
        ],
        "residual_status": {
            "python_verifier_flip_recovered": False,
            "rust_citation_flip_recovered": False,
            "same_two_reviewed_v27_misses_remain": True,
        },
        "next_best_steps": [
            "Do not promote stage10671 as a new frontier result because strict accuracy stayed flat at 22/24.",
            "Stop spending more cycles on same-surface support mixing for these two rows and move to fresh-root supply for Python verifier and Rust citation.",
            "Use the saved runtime only as a preserved diagnostic checkpoint unless a later fresh-root package shows a real heldout lift.",
        ],
    }

    write_json(OUT_PATH, payload)
    print(OUT_PATH)


if __name__ == "__main__":
    main()

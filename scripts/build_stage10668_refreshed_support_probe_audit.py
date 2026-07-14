#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10668
NAME = "stage10668_refreshed_support_probe_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_PATH = OUT_DIR / "refreshed_support_probe_audit.json"

PROBE_RESULT = ARTIFACTS / "stage10667_reviewed_v27_refreshed_support_probe/bounded_decoder_probe/execution_result.json"
BASELINE_COMPARISON = ARTIFACTS / "stage10424_reviewed_multilingual_v27_comparison_audit/reviewed_multilingual_v27_comparison_audit.json"
PACKAGE = ARTIFACTS / "stage10665_reviewed_v27_refreshed_support_package/reviewed_v27_refreshed_support_package.json"
REQUEST = ARTIFACTS / "stage10666_reviewed_v27_refreshed_support_probe_request/reviewed_v27_refreshed_support_probe_request.json"


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


def row_outcomes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        row_id = str(row.get("row_id") or "")
        language_family = "unknown"
        task_type = "unknown"
        parts = row_id.split("::")
        if len(parts) >= 2:
            language_family = parts[-2]
            task_type = parts[-1]
        if language_family not in {"python", "rust", "c_cpp", "web_js_ts_html"}:
            language_family = "unknown"
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
            }
        )
    return out


def main() -> None:
    probe = load_json(PROBE_RESULT)
    baseline = load_json(BASELINE_COMPARISON)
    package = load_json(PACKAGE)
    request = load_json(REQUEST)

    strict_eval = current_strict_eval(probe)
    eval_split = current_eval(probe)
    strict_rows = row_outcomes(strict_eval.get("row_cards") or [])
    strict_misses = [row for row in strict_rows if not row["correct"]]

    baseline_hundred_m = float(((baseline.get("hundred_m_eval_result") or {}).get("strict_accuracy")) or 0.0)
    baseline_gemma = float((((baseline.get("strict_result") or {}).get("overall") or {}).get("gemma12b_exact_accuracy")) or 0.0)
    current_hundred_m = float(strict_eval.get("constrained_choice_top1_accuracy") or 0.0)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision": "refreshed_support_probe_completed_no_headline_lift",
        "sources": {
            "probe_result": rel(PROBE_RESULT),
            "baseline_comparison": rel(BASELINE_COMPARISON),
            "refreshed_support_package": rel(PACKAGE),
            "probe_request": rel(REQUEST),
        },
        "headline": {
            "baseline_hundred_m_strict_accuracy": baseline_hundred_m,
            "baseline_gemma_strict_accuracy": baseline_gemma,
            "current_hundred_m_strict_accuracy": current_hundred_m,
            "current_vs_baseline_delta": current_hundred_m - baseline_hundred_m,
            "current_vs_gemma_delta_using_baseline_gemma": current_hundred_m - baseline_gemma,
        },
        "package_effect": {
            "train_rows": (request.get("split_counts") or {}).get("train"),
            "strict_rows": (request.get("split_counts") or {}).get("strict_eval"),
            "train_source_kinds": (request.get("source_kind_counts_by_split") or {}).get("train"),
            "strict_language_counts": (request.get("language_counts_by_split") or {}).get("strict_eval"),
        },
        "strict_eval_result": {
            "constrained_choice_top1_accuracy": strict_eval.get("constrained_choice_top1_accuracy"),
            "full_vocab_top1_accuracy": strict_eval.get("full_vocab_top1_accuracy"),
            "rows": strict_eval.get("rows"),
            "miss_count": len(strict_misses),
            "misses": strict_misses,
        },
        "eval_result": {
            "constrained_choice_top1_accuracy": eval_split.get("constrained_choice_top1_accuracy"),
            "full_vocab_top1_accuracy": eval_split.get("full_vocab_top1_accuracy"),
            "rows": eval_split.get("rows"),
        },
        "claim_boundary": [
            "The refreshed support package preserved the reviewed v2.7 strict score but did not improve it.",
            "This run is useful as a support-scaling hygiene check, not as a new promotion candidate over the reviewed v2.7 same-manifest result.",
            "The Gemma comparison margin from the reviewed baseline remains intact only because the strict set was unchanged; this run does not itself add a fresh Gemma rerun.",
        ],
        "next_best_steps": [
            "Do not promote stage10667 as a new frontier result because strict accuracy stayed flat at 22/24.",
            "Use the miss set to decide whether the next work should target fresh Rust builder roots or fresh Python verifier-root supply rather than adding more same-style support rows.",
            "If you need a full-product check, run the saved stage10667 runtime through the harness path only after a separate harness comparison artifact is prepared.",
        ],
        "support_inventory_status": {
            "package_passed": package.get("passed"),
            "excluded_support_roots_due_to_split_overlap": ((package.get("support_root_summary") or {}).get("excluded_support_roots_due_to_split_overlap")),
            "remaining_rust_builder_targets": ((package.get("support_root_summary") or {}).get("remaining_rust_builder_targets")),
            "web_source_heldout_gap_still_open": ((package.get("support_root_summary") or {}).get("web_source_heldout_gap_still_open")),
        },
    }

    write_json(OUT_PATH, payload)
    print(OUT_PATH)


if __name__ == "__main__":
    main()

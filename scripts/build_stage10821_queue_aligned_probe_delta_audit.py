#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10821
NAME = "stage10821_queue_aligned_probe_delta_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "queue_aligned_probe_delta_audit.json"

BASE_RESULT = ARTIFACTS / "stage10808_raw_role_option_value_probe" / "bounded_decoder_probe" / "execution_result.json"
NEW_RESULT = ARTIFACTS / "stage10820_queue_aligned_multilingual_support_probe" / "bounded_decoder_probe" / "execution_result.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def lang_from_row_id(row_id: str) -> str:
    if "::python::" in row_id:
        return "python"
    if "::rust::" in row_id:
        return "rust"
    if "::web_js_ts_html::" in row_id:
        return "web_js_ts_html"
    return "c_cpp"


def split_summary(result: dict[str, Any], split: str) -> dict[str, Any]:
    cards = result["bounded_choice_eval"][split]["row_cards"]
    exact = sum(1 for row in cards if row.get("constrained_choice_match") is True)
    misses = [
        {
            "row_id": row["row_id"],
            "target_label": row.get("bounded_choice_target_label"),
            "predicted_label": row.get("constrained_choice_top1_label"),
            "full_vocab_top1_text": row.get("full_vocab_top1_text"),
            "target_rank_full_vocab": row.get("target_rank_full_vocab"),
        }
        for row in cards
        if row.get("constrained_choice_match") is not True
    ]
    by_language: dict[str, dict[str, int | float]] = {}
    for row in cards:
        language = lang_from_row_id(row["row_id"])
        stats = by_language.setdefault(language, {"correct": 0, "total": 0, "exact": 0.0})
        stats["total"] += 1
        if row.get("constrained_choice_match") is True:
            stats["correct"] += 1
    for stats in by_language.values():
        stats["exact"] = stats["correct"] / stats["total"] if stats["total"] else 0.0
    return {
        "rows": len(cards),
        "correct": exact,
        "exact": exact / len(cards) if cards else 0.0,
        "misses": misses,
        "by_language": by_language,
    }


def main() -> None:
    base = load_json(BASE_RESULT)
    new = load_json(NEW_RESULT)
    base_strict = split_summary(base, "strict_eval")
    new_strict = split_summary(new, "strict_eval")
    base_eval = split_summary(base, "eval")
    new_eval = split_summary(new, "eval")

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "base_result": str(BASE_RESULT.relative_to(ROOT)),
        "new_result": str(NEW_RESULT.relative_to(ROOT)),
        "decision": "no_frontier_movement",
        "headline": {
            "strict_exact_before": base_strict["exact"],
            "strict_exact_after": new_strict["exact"],
            "strict_delta": new_strict["exact"] - base_strict["exact"],
            "eval_exact_before": base_eval["exact"],
            "eval_exact_after": new_eval["exact"],
            "eval_delta": new_eval["exact"] - base_eval["exact"],
        },
        "strict_miss_set_unchanged": sorted(m["row_id"] for m in base_strict["misses"]) == sorted(m["row_id"] for m in new_strict["misses"]),
        "eval_miss_set_unchanged": sorted(m["row_id"] for m in base_eval["misses"]) == sorted(m["row_id"] for m in new_eval["misses"]),
        "strict_before": base_strict,
        "strict_after": new_strict,
        "eval_before": base_eval,
        "eval_after": new_eval,
        "interpretation": [
            "The queue-aligned multilingual support probe preserved the repaired v2.7 frontier but did not improve it.",
            "The remaining strict misses are still the Python verifier_outcome row and the Rust tokenizers evidence_citation row.",
            "Admitted Python queue support did not regress C/C++ or web, but it also did not move the multilingual standalone baseline.",
        ],
        "next_best_step": [
            "Do not promote stage10820 as a new standalone frontier.",
            "Keep stage10820 as evidence that the new admitted queue support is hygiene-safe.",
            "Invest the next data work in fresh disjoint verifier and Rust citation roots rather than more same-frontier support accumulation.",
        ],
    }
    write_json(OUT_JSON, audit)
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

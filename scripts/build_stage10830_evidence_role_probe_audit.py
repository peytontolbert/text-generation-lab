#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10830
NAME = "stage10830_evidence_role_probe_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "evidence_role_probe_audit.json"

BASE_RESULT = ARTIFACTS / "stage10820_queue_aligned_multilingual_support_probe" / "bounded_decoder_probe" / "execution_result.json"
NEW_RESULT = ARTIFACTS / "stage10829_evidence_role_support_probe" / "bounded_decoder_probe" / "execution_result.json"
CONTRACT_AUDIT = ARTIFACTS / "stage10829_evidence_role_support_probe" / "bounded_decoder_probe" / "probe_contract_audit.json"
GEN_AUDIT = ARTIFACTS / "stage10829_evidence_role_support_probe" / "bounded_decoder_probe" / "sample_generation_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def language_from_row_id(row_id: str) -> str:
    if "::python::" in row_id:
        return "python"
    if "::rust::" in row_id:
        return "rust"
    if "::web_js_ts_html::" in row_id:
        return "web_js_ts_html"
    return "c_cpp"


def task_from_row_id(row_id: str) -> str:
    return row_id.split("::")[-2]


def split_summary(result: dict[str, Any], split: str) -> dict[str, Any]:
    cards = result["bounded_choice_eval"][split]["row_cards"]
    correct = sum(1 for row in cards if row.get("constrained_choice_match") is True)
    by_task = defaultdict(lambda: {"correct": 0, "total": 0, "exact": 0.0})
    by_language = defaultdict(lambda: {"correct": 0, "total": 0, "exact": 0.0})
    misses: list[dict[str, Any]] = []
    rank_improvements: list[dict[str, Any]] = []
    for row in cards:
        task = task_from_row_id(row["row_id"])
        language = language_from_row_id(row["row_id"])
        by_task[task]["total"] += 1
        by_language[language]["total"] += 1
        if row.get("constrained_choice_match") is True:
            by_task[task]["correct"] += 1
            by_language[language]["correct"] += 1
        else:
            misses.append(
                {
                    "row_id": row["row_id"],
                    "language_family": language,
                    "task_type": task,
                    "target_label": row.get("bounded_choice_target_label"),
                    "predicted_label": row.get("constrained_choice_top1_label"),
                    "full_vocab_top1_text": row.get("full_vocab_top1_text"),
                    "target_rank_full_vocab": row.get("target_rank_full_vocab"),
                }
            )
    for bucket in (by_task, by_language):
        for stats in bucket.values():
            stats["exact"] = stats["correct"] / stats["total"] if stats["total"] else 0.0
    return {
        "rows": len(cards),
        "correct": correct,
        "exact": correct / len(cards) if cards else 0.0,
        "by_task": dict(sorted(by_task.items())),
        "by_language": dict(sorted(by_language.items())),
        "misses": misses,
    }


def index_cards(result: dict[str, Any], split: str) -> dict[str, dict[str, Any]]:
    return {row["row_id"]: row for row in result["bounded_choice_eval"][split]["row_cards"]}


def compare_ranks(base: dict[str, Any], new: dict[str, Any], split: str) -> list[dict[str, Any]]:
    base_cards = index_cards(base, split)
    new_cards = index_cards(new, split)
    deltas: list[dict[str, Any]] = []
    for row_id, new_row in new_cards.items():
        base_row = base_cards[row_id]
        base_rank = base_row.get("target_rank_full_vocab")
        new_rank = new_row.get("target_rank_full_vocab")
        if isinstance(base_rank, int) and isinstance(new_rank, int) and base_rank != new_rank:
            deltas.append(
                {
                    "row_id": row_id,
                    "language_family": language_from_row_id(row_id),
                    "task_type": task_from_row_id(row_id),
                    "base_target_rank_full_vocab": base_rank,
                    "new_target_rank_full_vocab": new_rank,
                    "delta": base_rank - new_rank,
                    "base_predicted_label": base_row.get("constrained_choice_top1_label"),
                    "new_predicted_label": new_row.get("constrained_choice_top1_label"),
                }
            )
    deltas.sort(key=lambda item: (item["delta"], item["row_id"]), reverse=True)
    return deltas


def miss_set(summary: dict[str, Any]) -> list[str]:
    return sorted(item["row_id"] for item in summary["misses"])


def main() -> None:
    base = load_json(BASE_RESULT)
    new = load_json(NEW_RESULT)
    contract = load_json(CONTRACT_AUDIT)
    generation = load_json(GEN_AUDIT)

    base_eval = split_summary(base, "eval")
    base_strict = split_summary(base, "strict_eval")
    new_eval = split_summary(new, "eval")
    new_strict = split_summary(new, "strict_eval")

    eval_rank_deltas = compare_ranks(base, new, "eval")
    strict_rank_deltas = compare_ranks(base, new, "strict_eval")

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "base_result": str(BASE_RESULT.relative_to(ROOT)),
        "new_result": str(NEW_RESULT.relative_to(ROOT)),
        "contract_audit": str(CONTRACT_AUDIT.relative_to(ROOT)),
        "generation_audit": str(GEN_AUDIT.relative_to(ROOT)),
        "decision": "clean_plateau_margin_only",
        "headline": {
            "base_eval_exact": base_eval["exact"],
            "new_eval_exact": new_eval["exact"],
            "base_strict_exact": base_strict["exact"],
            "new_strict_exact": new_strict["exact"],
            "eval_delta": new_eval["exact"] - base_eval["exact"],
            "strict_delta": new_strict["exact"] - base_strict["exact"],
            "eval_miss_set_unchanged": miss_set(base_eval) == miss_set(new_eval),
            "strict_miss_set_unchanged": miss_set(base_strict) == miss_set(new_strict),
            "contract_passed": contract.get("passed") is True,
            "generation_contentful_rate": generation.get("contentful_rate"),
            "generation_exact_match_rows": generation.get("exact_match_rows"),
            "generation_short_or_junk_rate": generation.get("short_or_junk_rate"),
            "generation_degenerate_repetition_rate": generation.get("degenerate_repetition_rate"),
        },
        "base_eval": base_eval,
        "new_eval": new_eval,
        "base_strict_eval": base_strict,
        "new_strict_eval": new_strict,
        "eval_rank_deltas": eval_rank_deltas,
        "strict_rank_deltas": strict_rank_deltas,
        "notable_rank_movements": {
            "strict_top_improvements": strict_rank_deltas[:8],
            "eval_top_improvements": eval_rank_deltas[:8],
        },
        "findings": [
            "Evidence-role support kept the standalone package clean but did not improve top-line exact accuracy over stage10820.",
            "The eval and strict miss sets are unchanged, so the probe is not promotable as a new frontier.",
            "Generation mechanics are clean but semantically weak: contentful one-token outputs remain dominated by the same letter token and exact-match generation is still zero on sampled rows.",
            "The residual structure is unchanged: Python MirrorMind verifier_outcome remains a true semantic miss, while the Rust tokenizers evidence_citation lane remains entangled with scorer alignment.",
            "Evidence_citation remains the weakest cross-split family, so semantic evidence-role supervision alone did not yet flip the family-level decisions.",
        ],
        "next_best_steps": [
            "Do not promote stage10829 as a new frontier; treat it as a clean diagnostic probe.",
            "Move evidence_citation from answer-letter training toward option-value / evidence-role scoring with explicit decisive-supporting-distractor semantics in the scorer path.",
            "Build fresh Python verifier-transition roots where the target is the selected verifier/test transition rather than a compact label slot.",
            "Keep the 24-row standalone frontier as a canary only and require any next probe to improve fresh heldout evidence/verifier roots, not just same-frontier margins.",
        ],
    }
    write_json(OUT_JSON, audit)
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

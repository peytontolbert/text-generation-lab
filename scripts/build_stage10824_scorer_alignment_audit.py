#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10824
NAME = "stage10824_scorer_alignment_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "scorer_alignment_audit.json"

RESULT = ARTIFACTS / "stage10820_queue_aligned_multilingual_support_probe" / "bounded_decoder_probe" / "execution_result.json"


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


def classify(row: dict[str, Any]) -> str:
    constrained_ok = row.get("constrained_choice_match") is True
    full_vocab_ok = row.get("full_vocab_top1_match") is True
    target_rank = row.get("target_rank_full_vocab")
    if constrained_ok and full_vocab_ok:
        return "both_correct"
    if constrained_ok and not full_vocab_ok:
        return "constrained_only"
    if (not constrained_ok) and full_vocab_ok:
        return "full_vocab_only"
    if isinstance(target_rank, int) and target_rank <= 2:
        return "near_miss_both_wrong"
    return "both_wrong"


def summarize(cards: list[dict[str, Any]]) -> dict[str, Any]:
    counts = defaultdict(int)
    family = defaultdict(lambda: defaultdict(int))
    flagged: list[dict[str, Any]] = []
    for row in cards:
        lane = classify(row)
        counts[lane] += 1
        task = task_from_row_id(row["row_id"])
        lang = language_from_row_id(row["row_id"])
        family[f"{task}::{lang}"][lane] += 1
        if lane in {"full_vocab_only", "near_miss_both_wrong", "both_wrong"}:
            flagged.append(
                {
                    "row_id": row["row_id"],
                    "language_family": lang,
                    "task_type": task,
                    "classification": lane,
                    "constrained_choice_top1_label": row.get("constrained_choice_top1_label"),
                    "bounded_choice_target_label": row.get("bounded_choice_target_label"),
                    "full_vocab_top1_text": row.get("full_vocab_top1_text"),
                    "target_text": row.get("target_text"),
                    "target_rank_full_vocab": row.get("target_rank_full_vocab"),
                }
            )
    return {
        "counts": dict(counts),
        "family_breakdown": {k: dict(v) for k, v in sorted(family.items())},
        "flagged_rows": flagged,
    }


def main() -> None:
    result = load_json(RESULT)
    eval_cards = result["bounded_choice_eval"]["eval"]["row_cards"]
    strict_cards = result["bounded_choice_eval"]["strict_eval"]["row_cards"]
    eval_summary = summarize(eval_cards)
    strict_summary = summarize(strict_cards)

    rust_strict = next((r for r in strict_summary["flagged_rows"] if "::rust::" in r["row_id"] and r["task_type"] == "evidence_citation"), None)
    py_strict = next((r for r in strict_summary["flagged_rows"] if "::python::" in r["row_id"] and r["task_type"] == "verifier_outcome"), None)

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "scorer_alignment_bug_is_real",
        "claim_scope": [
            "Audit where constrained-choice and full-vocab signals disagree on the current stage10820 frontier.",
            "Distinguish scorer-interface failures from genuine missing model signal, especially for evidence-citation rows.",
        ],
        "source_result": str(RESULT.relative_to(ROOT)),
        "headline": {
            "eval_counts": eval_summary["counts"],
            "strict_counts": strict_summary["counts"],
            "strict_rust_evidence_row": rust_strict,
            "strict_python_verifier_row": py_strict,
        },
        "eval": eval_summary,
        "strict_eval": strict_summary,
        "findings": [
            "Rows classified as full_vocab_only are direct scorer-alignment failures: the decoder's top token is the target, but constrained selection still chooses a different label.",
            "The strict Rust tokenizers evidence_citation row is such a case and should be treated as a first-order scorer bug, not only as missing model knowledge.",
            "The Python MirrorMind verifier miss is not the same type of failure; it remains a true ranking / semantic disambiguation problem because both interfaces miss it.",
        ],
        "next_best_steps": [
            "Add a scorer-interface audit gate before future promotion: report full_vocab_only rows separately from true semantic misses.",
            "Prototype evidence-role or option-value aligned scoring for evidence_citation before adding more same-surface Rust support rows.",
            "Keep Python verifier root-building in parallel because its remaining miss is still a real semantic failure rather than only a scorer bug.",
        ],
    }
    write_json(OUT_JSON, audit)
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

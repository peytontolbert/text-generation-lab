#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10825
NAME = "stage10825_hybrid_scorer_policy_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "hybrid_scorer_policy_audit.json"

RESULT = ARTIFACTS / "stage10820_queue_aligned_multilingual_support_probe" / "bounded_decoder_probe" / "execution_result.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def task_from_row_id(row_id: str) -> str:
    return row_id.split("::")[-2]


def language_from_row_id(row_id: str) -> str:
    if "::python::" in row_id:
        return "python"
    if "::rust::" in row_id:
        return "rust"
    if "::web_js_ts_html::" in row_id:
        return "web_js_ts_html"
    return "c_cpp"


def apply_policy(row: dict[str, Any]) -> tuple[str, str]:
    constrained = str(row.get("constrained_choice_top1_label") or "")
    full_vocab = str(row.get("full_vocab_top1_text") or "")
    option_labels = set(str(x) for x in (row.get("option_labels") or []))
    task = task_from_row_id(str(row["row_id"]))
    if task == "evidence_citation" and full_vocab in option_labels and full_vocab and full_vocab != constrained:
        return full_vocab, "evidence_citation_full_vocab_override"
    return constrained, "constrained_baseline"


def summarize(cards: list[dict[str, Any]]) -> dict[str, Any]:
    before_correct = 0
    after_correct = 0
    changed_rows: list[dict[str, Any]] = []
    by_language_before: dict[str, list[int]] = {}
    by_language_after: dict[str, list[int]] = {}

    for row in cards:
        rid = str(row["row_id"])
        lang = language_from_row_id(rid)
        target = str(row.get("bounded_choice_target_label") or "")
        before = str(row.get("constrained_choice_top1_label") or "")
        after, route = apply_policy(row)

        by_language_before.setdefault(lang, [0, 0])
        by_language_after.setdefault(lang, [0, 0])
        by_language_before[lang][1] += 1
        by_language_after[lang][1] += 1

        if before == target:
            before_correct += 1
            by_language_before[lang][0] += 1
        if after == target:
            after_correct += 1
            by_language_after[lang][0] += 1

        if after != before:
            changed_rows.append(
                {
                    "row_id": rid,
                    "language_family": lang,
                    "task_type": task_from_row_id(rid),
                    "target_label": target,
                    "baseline_label": before,
                    "policy_label": after,
                    "full_vocab_top1_text": row.get("full_vocab_top1_text"),
                    "target_rank_full_vocab": row.get("target_rank_full_vocab"),
                    "policy_route": route,
                    "baseline_correct": before == target,
                    "policy_correct": after == target,
                }
            )

    return {
        "rows": len(cards),
        "baseline_correct": before_correct,
        "baseline_exact": before_correct / len(cards) if cards else 0.0,
        "policy_correct": after_correct,
        "policy_exact": after_correct / len(cards) if cards else 0.0,
        "delta": (after_correct - before_correct) / len(cards) if cards else 0.0,
        "changed_rows": changed_rows,
        "by_language_before": {
            lang: {"correct": vals[0], "total": vals[1], "exact": vals[0] / vals[1] if vals[1] else 0.0}
            for lang, vals in sorted(by_language_before.items())
        },
        "by_language_after": {
            lang: {"correct": vals[0], "total": vals[1], "exact": vals[0] / vals[1] if vals[1] else 0.0}
            for lang, vals in sorted(by_language_after.items())
        },
    }


def main() -> None:
    result = load_json(RESULT)
    eval_cards = result["bounded_choice_eval"]["eval"]["row_cards"]
    strict_cards = result["bounded_choice_eval"]["strict_eval"]["row_cards"]
    eval_summary = summarize(eval_cards)
    strict_summary = summarize(strict_cards)

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "hybrid_evidence_scorer_policy_audited",
        "claim_scope": [
            "Test a narrowly scoped scorer-policy override using full-vocab top token only for evidence_citation rows.",
            "Measure whether scorer repair is a credible next lever for the current standalone plateau.",
        ],
        "policy_definition": {
            "name": "evidence_citation_full_vocab_override_v0",
            "rule": "For evidence_citation rows only, if full_vocab_top1_text is itself a valid option label and differs from constrained_choice_top1_label, use full_vocab_top1_text.",
        },
        "source_result": str(RESULT.relative_to(ROOT)),
        "eval": eval_summary,
        "strict_eval": strict_summary,
        "headline": {
            "strict_baseline_exact": strict_summary["baseline_exact"],
            "strict_policy_exact": strict_summary["policy_exact"],
            "strict_delta": strict_summary["delta"],
            "eval_baseline_exact": eval_summary["baseline_exact"],
            "eval_policy_exact": eval_summary["policy_exact"],
            "eval_delta": eval_summary["delta"],
        },
        "findings": [
            "If this narrow policy only changes the strict Rust evidence row and does not hurt eval, scorer repair is a real standalone lever rather than just an explanatory audit.",
            "If it also changes unrelated evidence rows incorrectly, then the current full-vocab signal is too noisy for a simple override and deeper evidence-role scoring work is still required.",
        ],
        "next_best_steps": [
            "If the audit is positive, build a scorer-policy comparison artifact that reports baseline vs hybrid policy explicitly for the same frontier.",
            "If the audit is neutral or harmful, keep the current constrained scorer and prioritize semantic evidence-role supervision instead.",
        ],
    }
    write_json(OUT_JSON, audit)
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

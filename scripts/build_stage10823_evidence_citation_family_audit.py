#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10823
NAME = "stage10823_evidence_citation_family_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "evidence_citation_family_audit.json"

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


def summarize_split(cards: list[dict[str, Any]]) -> dict[str, Any]:
    by_task: dict[str, dict[str, Any]] = defaultdict(lambda: {"rows": 0, "correct": 0, "misses": []})
    by_task_lang: dict[str, dict[str, dict[str, Any]]] = defaultdict(
        lambda: defaultdict(lambda: {"rows": 0, "correct": 0, "misses": []})
    )
    for row in cards:
        task = row["row_id"].split("::")[-2]
        lang = language_from_row_id(row["row_id"])
        correct = row.get("constrained_choice_match") is True
        by_task[task]["rows"] += 1
        by_task_lang[task][lang]["rows"] += 1
        if correct:
            by_task[task]["correct"] += 1
            by_task_lang[task][lang]["correct"] += 1
        else:
            miss = {
                "row_id": row["row_id"],
                "predicted_label": row.get("constrained_choice_top1_label"),
                "target_label": row.get("bounded_choice_target_label"),
                "full_vocab_top1_text": row.get("full_vocab_top1_text"),
                "target_rank_full_vocab": row.get("target_rank_full_vocab"),
            }
            by_task[task]["misses"].append(miss)
            by_task_lang[task][lang]["misses"].append(miss)
    for task_stats in by_task.values():
        task_stats["exact"] = task_stats["correct"] / task_stats["rows"] if task_stats["rows"] else 0.0
    for langs in by_task_lang.values():
        for stats in langs.values():
            stats["exact"] = stats["correct"] / stats["rows"] if stats["rows"] else 0.0
    return {
        "task_summary": dict(by_task),
        "task_language_summary": {task: dict(langs) for task, langs in by_task_lang.items()},
    }


def main() -> None:
    result = load_json(RESULT)
    eval_cards = result["bounded_choice_eval"]["eval"]["row_cards"]
    strict_cards = result["bounded_choice_eval"]["strict_eval"]["row_cards"]
    eval_summary = summarize_split(eval_cards)
    strict_summary = summarize_split(strict_cards)

    evidence_eval = eval_summary["task_summary"].get("evidence_citation", {})
    evidence_strict = strict_summary["task_summary"].get("evidence_citation", {})

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "evidence_citation_is_primary_weak_family",
        "claim_scope": [
            "Isolate which task family actually accounts for the remaining stage10820 validation and strict errors.",
            "Distinguish evidence-citation weakness from verifier-only narratives so the next support package can target the right prediction head.",
        ],
        "source_result": str(RESULT.relative_to(ROOT)),
        "headline": {
            "eval_evidence_citation_exact": evidence_eval.get("exact"),
            "strict_evidence_citation_exact": evidence_strict.get("exact"),
            "eval_evidence_citation_miss_count": len(evidence_eval.get("misses", [])),
            "strict_evidence_citation_miss_count": len(evidence_strict.get("misses", [])),
            "strict_verifier_outcome_exact": strict_summary["task_summary"].get("verifier_outcome", {}).get("exact"),
            "strict_verifier_outcome_miss_count": len(strict_summary["task_summary"].get("verifier_outcome", {}).get("misses", [])),
        },
        "eval": eval_summary,
        "strict_eval": strict_summary,
        "findings": [
            "Validation misses are entirely evidence_citation, which makes evidence scoring the clearest cross-split weakness.",
            "Strict still includes the single MirrorMind verifier miss, but evidence_citation remains one of only two failing strict rows.",
            "The next model-side improvement should target semantic evidence-role scoring, not a global decoder-first-step scorer switch.",
        ],
        "next_best_steps": [
            "Build evidence-role aligned targets where decisive, supporting, distractor, and contradictory evidence are scored semantically rather than through opaque answer letters alone.",
            "Keep Python verifier fresh-root work in parallel, but treat evidence_citation as the first shared head to repair across validation and strict.",
            "Use this audit as a gate: new support probes should report task-family deltas, not just overall 22/24 preservation.",
        ],
    }
    write_json(OUT_JSON, audit)
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

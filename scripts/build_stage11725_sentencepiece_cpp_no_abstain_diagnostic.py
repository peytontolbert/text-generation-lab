#!/usr/bin/env python3
"""No-abstain diagnostic for sentencepiece C++ source-heldout smoke rows.

This is intentionally non-promotable. It tests whether Stage11722 failed
because the row geometry invited abstention despite only static verifier
anchors. It reuses the same source/evidence, removes only the abstain option,
and records the result as diagnostic evidence.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11725
NAME = "stage11725_sentencepiece_cpp_no_abstain_diagnostic"
OUT = ART / NAME
SUMMARY = OUT / "sentencepiece_cpp_no_abstain_diagnostic.json"
DIAG_ROWS = OUT / "sentencepiece_cpp_no_abstain_diagnostic_rows.jsonl"
SCORED_ROWS = OUT / "sentencepiece_cpp_no_abstain_score_rows.jsonl"

STAGE11722 = ROOT / "scripts/build_stage11722_sentencepiece_cpp_source_heldout_100m_score.py"
spec = importlib.util.spec_from_file_location("stage11722_for_11725", STAGE11722)
if spec is None or spec.loader is None:
    raise RuntimeError(f"failed to import {STAGE11722}")
stage11722 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage11722)

SCORERS = [
    "decoder_first_step",
    "encoder_option_retrieval",
    "encoder_option_retrieval_verifier_conditioned",
    "encoder_option_retrieval_evidence_judgment_head",
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def no_abstain_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    remap_task = {
        "patch_impact_or_abstain": "patch_impact",
        "verifier_outcome_or_abstain": "verifier_outcome",
    }
    out = []
    for row in rows:
        rr = dict(row)
        rr["row_id"] = f"{row['row_id']}::no_abstain_diagnostic"
        rr["task_type"] = remap_task.get(str(row.get("task_type")), row.get("task_type"))
        rr["opaque_options"] = [
            dict(opt)
            for opt in row.get("opaque_options") or []
            if str(opt.get("role") or "") != "abstain_insufficient_evidence"
            and str(opt.get("value") or "") != "ABSTAIN_INSUFFICIENT_EVIDENCE"
        ]
        rr["split"] = "diagnostic_eval"
        rr["split_role"] = "source_heldout_geometry_diagnostic_no_abstain"
        rr["strict_eval_eligible"] = False
        rr["non_promotable_reason"] = "abstain_option_removed_to_test_stage11722_failure_geometry"
        rr["anti_cheat"] = dict(rr.get("anti_cheat") or {})
        rr["anti_cheat"]["strict_eval_eligible"] = False
        rr["anti_cheat"]["diagnostic_geometry_mutation"] = "removed_abstain_option"
        out.append(rr)
    return out


def metric(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get("correct"), bool)]
    correct = sum(1 for row in scored if row.get("correct") is True)
    return {
        "rows": len(rows),
        "scored_rows": len(scored),
        "correct": correct,
        "accuracy": correct / len(scored) if scored else None,
        "coverage": len(scored) / len(rows) if rows else None,
        "predicted_labels": dict(Counter(str(row.get("predicted_label")) for row in scored).most_common()),
    }


def enrich(card: dict[str, Any], rows: list[dict[str, Any]], scorer: str) -> list[dict[str, Any]]:
    by_id = {str(row.get("row_id")): row for row in rows}
    out = []
    for scored in card.get("row_cards") or []:
        source = by_id.get(str(scored.get("row_id")), {})
        pred = str(scored.get("constrained_choice_top1_label") or "")
        target = str(scored.get("bounded_choice_target_label") or "")
        pred_opt = next((opt for opt in source.get("opaque_options") or [] if str(opt.get("label") or "") == pred), {})
        target_opt = next((opt for opt in source.get("opaque_options") or [] if str(opt.get("label") or "") == target), {})
        out.append(
            {
                "scorer": scorer,
                "row_id": scored.get("row_id"),
                "task_type": source.get("task_type"),
                "target_label": target,
                "target_role": target_opt.get("role"),
                "target_value": target_opt.get("value") or source.get("target_value"),
                "predicted_label": pred,
                "predicted_role": pred_opt.get("role"),
                "predicted_value": pred_opt.get("value"),
                "correct": scored.get("constrained_choice_match"),
                "full_vocab_top1_text": scored.get("full_vocab_top1_text"),
                "target_rank_full_vocab": scored.get("target_rank_full_vocab"),
                "option_labels": scored.get("option_labels"),
            }
        )
    return out


def grouped(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get("task_type") or "unknown")].append(row)
    return {key: metric(value) for key, value in sorted(buckets.items())}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = stage11722.load_jsonl(stage11722.ROWS)
    diagnostic_source_rows = no_abstain_rows(raw)
    rows = stage11722.render_rows(diagnostic_source_rows)
    write_jsonl(DIAG_ROWS, rows)
    leak = stage11722.prompt_leak_audit(rows)
    model, tokenizer, init_card = stage11722.load_runtime()

    all_scored: list[dict[str, Any]] = []
    metrics_by_scorer: dict[str, Any] = {}
    by_task: dict[str, Any] = {}
    for scorer in SCORERS:
        card = stage11722._write_bounded_choice_eval_audit(
            OUT,
            model=model,
            rows=rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=8,
            split_name=f"sentencepiece_cpp_no_abstain__{scorer}",
            bounded_choice_aux_source=scorer,
            eval_batch_size=4,
        )
        scored = enrich(card, rows, scorer)
        metrics_by_scorer[scorer] = metric(scored)
        by_task[scorer] = grouped(scored)
        all_scored.extend(scored)

    selected = metrics_by_scorer["encoder_option_retrieval_evidence_judgment_head"]
    best = max(metrics_by_scorer.items(), key=lambda item: (item[1]["correct"], item[1]["coverage"] or 0.0))
    gates = {
        "non_promotable_by_design": True,
        "no_prompt_target_label_leaks": leak["prompt_target_label_leaks"] == 0,
        "no_prompt_target_value_leaks": leak["prompt_target_value_leaks"] == 0,
        "selected_product_scorer_improves_over_stage11722": selected["correct"] > 0,
        "selected_product_scorer_all_correct": selected["correct"] == 4,
    }
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "no_abstain_geometry_recovers_sentencepiece_smoke"
        if selected["correct"] > 0
        else "no_abstain_geometry_still_fails_sentencepiece_smoke",
        "passed": True,
        "metrics_by_scorer": metrics_by_scorer,
        "by_task_by_scorer": by_task,
        "best_scorer": {"name": best[0], "metric": best[1]},
        "prompt_leak_audit": leak,
        "gates": gates,
        "runtime": {
            "runtime_bundle": rel(stage11722.RUNTIME_BUNDLE),
            "init_card": init_card,
        },
        "interpretation": [
            "This is a non-promotable geometry diagnostic, not a source-heldout benchmark result.",
            "It removes the abstain option from Stage11720 to test whether Stage11722 was dominated by abstain attraction.",
            "If this improves, executable verifier materialization or clearer selected-test task framing is required before strict scoring.",
            "If this still fails, the current model/scorers do not handle this source-heldout sentencepiece root even without abstain.",
        ],
        "source_artifacts": {
            "stage11720_rows": rel(stage11722.ROWS),
            "stage11722_score": rel(stage11722.SUMMARY),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "diagnostic_rows": rel(DIAG_ROWS),
            "scored_rows": rel(SCORED_ROWS),
        },
    }
    write_json(SUMMARY, artifact)
    write_jsonl(SCORED_ROWS, all_scored)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "selected": selected, "best_scorer": artifact["best_scorer"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

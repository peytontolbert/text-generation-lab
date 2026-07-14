#!/usr/bin/env python3
"""Diagnostic scorer sweep for Stage11729 bigram Python source-heldout rows."""

from __future__ import annotations

import importlib.util
import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11730
NAME = "stage11730_bigram_python_scorer_diagnostic"
OUT = ART / NAME
SUMMARY = OUT / "bigram_python_scorer_diagnostic.json"
ROWS_OUT = OUT / "bigram_python_scorer_diagnostic_rows.jsonl"

STAGE11729 = ROOT / "scripts/build_stage11729_bigram_python_source_heldout_100m_score.py"
spec = importlib.util.spec_from_file_location("stage11729_for_11730", STAGE11729)
if spec is None or spec.loader is None:
    raise RuntimeError(f"failed to import {STAGE11729}")
stage11729 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage11729)

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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw_rows = stage11729.stage11722.load_jsonl(stage11729.ROWS)
    rows = stage11729.render_rows(raw_rows)
    leak = stage11729.stage11722.prompt_leak_audit(rows)
    model, tokenizer, init_card = stage11729.stage11722.load_runtime()

    all_rows: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}
    for scorer in SCORERS:
        card = stage11729.stage11722._write_bounded_choice_eval_audit(
            OUT,
            model=model,
            rows=rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=8,
            split_name=f"bigram_python_source_heldout_smoke__{scorer}",
            bounded_choice_aux_source=scorer,
            eval_batch_size=4,
        )
        scored = enrich(card, rows, scorer)
        metrics[scorer] = metric(scored)
        all_rows.extend(scored)
    best = max(metrics.items(), key=lambda item: (item[1]["correct"], item[1]["coverage"] or 0.0))
    product = metrics["encoder_option_retrieval_evidence_judgment_head"]
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "bigram_python_existing_scorer_can_recover_all_rows"
        if best[1]["correct"] == 4
        else "bigram_python_verifier_miss_persists_across_existing_scorers",
        "passed": True,
        "metrics_by_scorer": metrics,
        "best_scorer": {"name": best[0], "metric": best[1]},
        "product_scorer_metric": product,
        "prompt_leak_audit": leak,
        "runtime": {
            "runtime_bundle": rel(stage11729.stage11722.RUNTIME_BUNDLE),
            "init_card": init_card,
        },
        "interpretation": [
            "This diagnostic checks whether the Python source-heldout verifier miss is product-scorer-specific.",
            "The row remains non-Gemma-comparison evidence until same-manifest Gemma and permutation audits are attached.",
        ],
        "source_artifacts": {
            "stage11729_score": rel(stage11729.SUMMARY),
            "stage11728_rows": rel(stage11729.ROWS),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "row_cards": rel(ROWS_OUT),
        },
    }
    write_json(SUMMARY, artifact)
    write_jsonl(ROWS_OUT, all_rows)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "best_scorer": artifact["best_scorer"], "metrics_by_scorer": metrics}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUM = ROOT / "runs/summaries"
STAGE = 11510
NAME = "stage11510_selected_frontier_same_manifest_gemma_comparison"
OUT = ART / NAME
SUMMARY = OUT / "selected_frontier_same_manifest_gemma_comparison.json"
ROWS_OUT = OUT / "matched_comparison_rows.jsonl"

AUDIT = ART / "stage11508_preservation_strengthened_evidence_judgment_postrun_audit/preservation_strengthened_evidence_judgment_postrun_audit.json"
HUNDRED_AUDIT = ART / "stage11508_preservation_strengthened_evidence_judgment_postrun_audit/bounded_choice_eval_audit_old_canary_strict_encoder_option_retrieval_evidence_judgment_head.json"
DECISION = SUM / "stage11509_preservation_strengthened_frontier_promotion_decision.json"
GEMMA_CLEANED = ART / "stage11148_cleaned_strict_gemma_rescore/cleaned_strict_gemma_rows.jsonl"
GEMMA_MISSING = ART / "stage11149_missing_cleaned_strict_gemma_row/missing_cleaned_strict_gemma_rows.jsonl"
GEMMA_FALLBACK = ART / "stage10423_reviewed_multilingual_v27_same_manifest_gemma_comparison/reviewed_multilingual_v27_same_manifest_gemma_rows.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def metric(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    correct = sum(1 for row in rows if bool(row.get(key)))
    total = len(rows)
    return {"rows": total, "correct": correct, "accuracy": correct / total if total else None}


def grouped(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(field) or "unknown")].append(row)
    out = {}
    for value, items in sorted(buckets.items()):
        h = metric(items, "hundred_m_correct")
        g = metric(items, "gemma12b_correct")
        out[value] = {
            "rows": len(items),
            "hundred_m_correct": h["correct"],
            "hundred_m_accuracy": h["accuracy"],
            "gemma_correct": g["correct"],
            "gemma_accuracy": g["accuracy"],
        }
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    audit = load_json(AUDIT)
    decision = load_json(DECISION)
    product = load_json(HUNDRED_AUDIT)
    row_cards = product.get("row_cards") or []
    hundred_by_id = {str(row.get("row_id") or ""): row for row in row_cards}

    gemma_rows = []
    for path in [GEMMA_CLEANED, GEMMA_MISSING, GEMMA_FALLBACK]:
        gemma_rows.extend(load_jsonl(path))
    gemma_by_id: dict[str, dict[str, Any]] = {}
    for row in gemma_rows:
        row_id = str(row.get("row_id") or "")
        if row_id and row_id not in gemma_by_id:
            gemma_by_id[row_id] = row

    matched = []
    missing_gemma = []
    for row_id, h in sorted(hundred_by_id.items()):
        g = gemma_by_id.get(row_id)
        if not g:
            missing_gemma.append(row_id)
            continue
        matched.append({
            "row_id": row_id,
            "language_family": g.get("language_family"),
            "repo_family": g.get("repo_family"),
            "task_type": g.get("task_type"),
            "target_text": h.get("bounded_choice_target_label") or g.get("target_text"),
            "hundred_m_predicted_label": h.get("constrained_choice_top1_label"),
            "hundred_m_correct": bool(h.get("constrained_choice_match")),
            "hundred_m_full_vocab_top1_text": h.get("full_vocab_top1_text"),
            "hundred_m_target_rank_full_vocab": h.get("target_rank_full_vocab"),
            "hundred_m_runtime_stage": 11507,
            "hundred_m_scorer": "encoder_option_retrieval_evidence_judgment_head",
            "gemma12b_model": g.get("gemma12b_model", "gemma3:12b"),
            "gemma12b_predicted_label": g.get("gemma12b_predicted_label"),
            "gemma12b_correct": bool(g.get("gemma12b_correct")),
        })

    h_metric = metric(matched, "hundred_m_correct")
    g_metric = metric(matched, "gemma12b_correct")
    delta = None if h_metric["accuracy"] is None or g_metric["accuracy"] is None else h_metric["accuracy"] - g_metric["accuracy"]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": not missing_gemma and len(matched) == len(row_cards),
        "decision": "stage11507_runtime_beats_gemma12b_on_matched_old_canary_strict_rows" if not missing_gemma and h_metric["correct"] > g_metric["correct"] else "comparison_incomplete_or_not_win",
        "claim_scope": "matched old-canary strict compact maintainer-choice rows under declared Stage11507 product scorer; not broad freeform repair",
        "metrics": {
            "matched_rows": len(matched),
            "hundred_m_rows": len(row_cards),
            "missing_gemma_rows": missing_gemma,
            "hundred_m_correct": h_metric["correct"],
            "hundred_m_accuracy": h_metric["accuracy"],
            "gemma_correct": g_metric["correct"],
            "gemma_accuracy": g_metric["accuracy"],
            "delta_accuracy": delta,
            "by_language": grouped(matched, "language_family"),
            "by_task_type": grouped(matched, "task_type"),
        },
        "runtime": decision.get("selected_frontier_after_decision"),
        "promotion_gates": audit.get("promotion_gates"),
        "source_artifacts": {
            "hundred_m_summary_audit": rel(AUDIT),
            "hundred_m_row_card_audit": rel(HUNDRED_AUDIT),
            "frontier_decision": rel(DECISION),
            "gemma_cleaned_rows": rel(GEMMA_CLEANED),
            "gemma_missing_row": rel(GEMMA_MISSING),
            "gemma_fallback_rows": rel(GEMMA_FALLBACK),
        },
        "outputs": {"summary_json": rel(SUMMARY), "matched_rows_jsonl": rel(ROWS_OUT)},
    }
    write_jsonl(ROWS_OUT, matched)
    write_json(SUMMARY, summary)
    SUM.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUM / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

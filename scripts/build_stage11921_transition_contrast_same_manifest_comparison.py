#!/usr/bin/env python3
"""Compare Stage11919 routed transition scorer against existing Stage11916 Gemma outputs."""

from __future__ import annotations

import json
import time
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 11921
NAME = "stage11921_transition_contrast_same_manifest_comparison"
OUT = ROOT / "runs/local/artifacts" / NAME
SUMMARY = OUT / "transition_contrast_same_manifest_comparison.json"
ROWS_OUT = OUT / "transition_contrast_same_manifest_rows.jsonl"

ROWS = ROOT / "runs/local/artifacts/stage11897_transition_record_projection_rows/transition_projection_rows.jsonl"
STAGE11916_ROWS = ROOT / "runs/local/artifacts/stage11916_transition_projection_same_manifest_gemma_comparison/transition_projection_same_manifest_gemma_rows.jsonl"
STAGE11920_CARD = ROOT / "runs/local/artifacts/stage11920_transition_contrast_routed_postrun_audit/stage11919_transition_contrast_head_only/bounded_choice_eval_audit_transition_projection__semantic_candidate_head.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def prompt_surface_hash(rows: list[dict[str, Any]]) -> str:
    payload = [
        {
            "row_id": row.get("row_id"),
            "language_family": row.get("language_family"),
            "task_type": row.get("task_type"),
            "prompt_text": row.get("prompt_text"),
            "target_text": row.get("target_text"),
            "opaque_options": row.get("opaque_options") or [],
        }
        for row in sorted(rows, key=lambda item: str(item.get("row_id") or ""))
    ]
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def metric(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get(field), bool)]
    correct = sum(1 for row in scored if row.get(field) is True)
    return {"rows": len(rows), "scored_rows": len(scored), "correct": correct, "accuracy": correct / len(scored) if scored else None}


def group_metric(rows: list[dict[str, Any]], group_field: str, result_field: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(group_field))].append(row)
    return {key: metric(bucket, result_field) for key, bucket in sorted(buckets.items())}


def verdicts(hundred: dict[str, Any], gemma: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    summary = {"100m": 0, "gemma": 0, "ties": 0, "unscored": 0}
    for key in sorted(set(hundred) | set(gemma)):
        h = (hundred.get(key) or {}).get("accuracy")
        g = (gemma.get(key) or {}).get("accuracy")
        if h is None or g is None:
            verdict = "unscored"
            summary["unscored"] += 1
        elif h > g:
            verdict = "100m_better"
            summary["100m"] += 1
        elif g > h:
            verdict = "gemma_better"
            summary["gemma"] += 1
        else:
            verdict = "tie"
            summary["ties"] += 1
        out[key] = {
            "hundred_m_accuracy": h,
            "gemma12b_accuracy": g,
            "delta": None if h is None or g is None else h - g,
            "verdict": verdict,
            "rows": (hundred.get(key) or gemma.get(key) or {}).get("rows"),
        }
    out["_summary"] = summary
    return out


def main() -> None:
    rows = read_jsonl(ROWS)
    gemma_rows = {str(row.get("row_id")): row for row in read_jsonl(STAGE11916_ROWS)}
    card = read_json(STAGE11920_CARD)
    hundred_cards = {str(row.get("row_id")): row for row in card.get("row_cards") or []}
    comparison: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: str(item.get("row_id") or "")):
        row_id = str(row.get("row_id") or "")
        hundred = hundred_cards[row_id]
        gemma = gemma_rows[row_id]
        comparison.append(
            {
                "row_id": row_id,
                "language_family": row.get("language_family"),
                "task_type": row.get("task_type"),
                "root_id": row.get("root_id"),
                "target_text": row.get("bounded_choice_target_label") or row.get("target_text"),
                "hundred_m_scorer": "routed:transition_projection=encoder_option_retrieval_semantic_candidate_head",
                "hundred_m_runtime": rel(ROOT / "runs/local/artifacts/stage11919_transition_projection_contrast_head_only_probe/runtime_model/runtime_model_bundle.json"),
                "hundred_m_predicted_label": hundred.get("constrained_choice_top1_label"),
                "hundred_m_correct": hundred.get("constrained_choice_match"),
                "gemma12b_model": gemma.get("gemma12b_model"),
                "gemma12b_raw_output": gemma.get("gemma12b_raw_output"),
                "gemma12b_predicted_label": gemma.get("gemma12b_predicted_label"),
                "gemma12b_correct": gemma.get("gemma12b_correct"),
            }
        )
    write_jsonl(ROWS_OUT, comparison)

    by_language_100m = group_metric(comparison, "language_family", "hundred_m_correct")
    by_language_gemma = group_metric(comparison, "language_family", "gemma12b_correct")
    by_task_100m = group_metric(comparison, "task_type", "hundred_m_correct")
    by_task_gemma = group_metric(comparison, "task_type", "gemma12b_correct")
    hundred = metric(comparison, "hundred_m_correct")
    gemma = metric(comparison, "gemma12b_correct")
    delta = hundred["accuracy"] - gemma["accuracy"]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "do_not_promote_as_transition_projection_win" if delta <= 0 else "promote_transition_projection_candidate",
        "rows": len(comparison),
        "prompt_surface_hash": prompt_surface_hash(rows),
        "hundred_m": {"overall": hundred, "by_language": by_language_100m, "by_task": by_task_100m},
        "gemma12b": {"overall": gemma, "by_language": by_language_gemma, "by_task": by_task_gemma, "reused_stage11916_outputs": True},
        "delta_vs_gemma12b": delta,
        "verdict_by_language": verdicts(by_language_100m, by_language_gemma),
        "verdict_by_task": verdicts(by_task_100m, by_task_gemma),
        "source_artifacts": {
            "rows": rel(ROWS),
            "stage11916_gemma_rows": rel(STAGE11916_ROWS),
            "stage11920_100m_card": rel(STAGE11920_CARD),
        },
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS_OUT)},
        "claim_boundary": [
            "Same-manifest compact transition-projection comparison only.",
            "Gemma outputs are reused from Stage11916 because the row manifest is unchanged.",
            "This does not establish full-product patch repair or freeform generation.",
        ],
    }
    write_json(SUMMARY, summary)
    print(json.dumps({"decision": summary["decision"], "hundred_m": hundred, "gemma12b": gemma, "delta_vs_gemma12b": delta}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

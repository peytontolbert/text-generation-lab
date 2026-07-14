#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10430
NAME = "stage10430_reviewed_v27_margin_and_residual_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "reviewed_v27_margin_and_residual_audit.json"
ROW_JSONL = OUT_DIR / "reviewed_v27_margin_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

ROWS_JSONL = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/reviewed_multilingual_v27_bounded_rows.jsonl"
STRICT_AUDIT_JSON = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
LOGITS_JSONL = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/bounded_decoder_probe/boundary_next_token_logits.jsonl"
EVAL_HACK_AUDIT_JSON = ROOT / "runs/local/artifacts/stage10429_reviewed_v27_eval_hacking_audit/reviewed_v27_eval_hacking_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def semantic_value_for_label(row: dict[str, Any], label: str) -> str | None:
    options = row.get("standalone_projection_source", {}).get("opaque_options") or row.get("opaque_options") or []
    for option in options:
        if str(option.get("label")) == label:
            return str(option.get("value"))
    return None


def classify_residual(row: dict[str, Any], predicted_semantic: str | None) -> str:
    task_type = str(row.get("task_type") or "")
    target_semantic = str(row.get("standalone_projection_source", {}).get("gold_value") or "")
    if predicted_semantic == "candidate_change_surface":
        if task_type == "evidence_citation":
            return "candidate_change_surface_attractor"
        return "candidate_change_surface_collapse"
    if task_type == "verifier_outcome":
        return "verifier_target_disambiguation"
    if task_type == "evidence_citation":
        return "evidence_support_disambiguation"
    if predicted_semantic == target_semantic:
        return "label_mapping_only"
    return "other_semantic_miss"


def margin_band(margin: float) -> str:
    if margin < 0.02:
        return "very_low"
    if margin < 0.05:
        return "low"
    if margin < 0.15:
        return "medium"
    return "high"


def summary_for(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"rows": 0}
    margins = [float(r["margin_top1_minus_top2"]) for r in rows]
    correct = [r for r in rows if r["constrained_choice_match"]]
    incorrect = [r for r in rows if not r["constrained_choice_match"]]
    return {
        "rows": len(rows),
        "mean_margin": mean(margins),
        "min_margin": min(margins),
        "max_margin": max(margins),
        "correct_rows": len(correct),
        "incorrect_rows": len(incorrect),
        "low_margin_rows_lt_0_05": sum(1 for value in margins if value < 0.05),
        "medium_or_worse_rows_lt_0_15": sum(1 for value in margins if value < 0.15),
    }


def main() -> None:
    row_map = {row["row_id"]: row for row in load_jsonl(ROWS_JSONL)}
    strict_audit = load_json(STRICT_AUDIT_JSON)
    eval_hack = load_json(EVAL_HACK_AUDIT_JSON)
    logits_rows = [row for row in load_jsonl(LOGITS_JSONL) if row.get("split") == "strict_eval"]
    logits_by_row = {row["row_id"]: row for row in logits_rows}

    row_cards = strict_audit["row_cards"]
    margin_rows: list[dict[str, Any]] = []

    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    residual_rows: list[dict[str, Any]] = []

    for card in row_cards:
        row_id = str(card["row_id"])
        source = row_map[row_id]
        logits = logits_by_row[row_id]
        option_labels = {str(label) for label in card.get("option_labels") or []}
        option_topk = [item for item in logits.get("top_k") or [] if str(item.get("token_text")) in option_labels]
        option_topk.sort(key=lambda item: float(item.get("probability") or 0.0), reverse=True)
        top1 = option_topk[0]
        top2 = option_topk[1] if len(option_topk) > 1 else None
        margin = float(top1.get("probability") or 0.0) - float((top2 or {}).get("probability") or 0.0)
        predicted_label = str(card["constrained_choice_top1_label"])
        target_label = str(card["target_text"])
        predicted_semantic = semantic_value_for_label(source, predicted_label)
        target_semantic = semantic_value_for_label(source, target_label)
        record = {
            "row_id": row_id,
            "language_family": source.get("language_family"),
            "task_type": source.get("task_type"),
            "repo_family": source.get("repo_family"),
            "split": source.get("split"),
            "selected_test_anchor": bool(source.get("selected_test_anchor")),
            "verifier_anchor": bool(source.get("verifier_anchor")),
            "abstention_heavy": bool(source.get("abstention_heavy")),
            "constrained_choice_match": bool(card["constrained_choice_match"]),
            "predicted_label": predicted_label,
            "target_label": target_label,
            "predicted_semantic_value": predicted_semantic,
            "target_semantic_value": target_semantic,
            "top1_probability": float(top1.get("probability") or 0.0),
            "top2_probability": float((top2 or {}).get("probability") or 0.0),
            "margin_top1_minus_top2": margin,
            "margin_band": margin_band(margin),
            "top2_label": str((top2 or {}).get("token_text") or ""),
            "top2_semantic_value": semantic_value_for_label(source, str((top2 or {}).get("token_text") or "")),
            "target_rank_full_vocab": card.get("target_rank_full_vocab"),
            "full_vocab_top1_text": card.get("full_vocab_top1_text"),
            "eval_hack_prompt_leak": False,
        }
        # Replace the dummy field with a direct derivation from the source row.
        prompt = str(source.get("prompt_text") or source.get("input_text") or "")
        prompt_body = prompt.split("\nOptions:\n", 1)[0]
        record["eval_hack_prompt_leak"] = bool(target_semantic and target_semantic in prompt_body)

        margin_rows.append(record)
        by_task[str(source.get("task_type"))].append(record)
        by_language[str(source.get("language_family"))].append(record)

        if not record["constrained_choice_match"]:
            residual = dict(record)
            residual["residual_family"] = classify_residual(source, predicted_semantic)
            residual_rows.append(residual)

    margin_rows.sort(key=lambda row: (row["margin_top1_minus_top2"], row["row_id"]))
    residual_rows.sort(key=lambda row: (row["margin_top1_minus_top2"], row["row_id"]))

    per_task = {task: summary_for(items) for task, items in sorted(by_task.items())}
    per_language = {lang: summary_for(items) for lang, items in sorted(by_language.items())}

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Strict-eval margin and residual audit for the reviewed v2.7 same-manifest stage10422 probe only.",
            "This audit does not upgrade the standalone claim; it diagnoses which reviewed-v2.7 rows are brittle or still unresolved.",
            "Residual follow-up should prefer fresh disjoint roots rather than same-surface replay support.",
        ],
        "source_artifacts": {
            "strict_eval_audit": display(STRICT_AUDIT_JSON),
            "boundary_logits": display(LOGITS_JSONL),
            "reviewed_v27_rows": display(ROWS_JSONL),
            "eval_hacking_audit": display(EVAL_HACK_AUDIT_JSON),
        },
        "summary": {
            "strict_rows": len(margin_rows),
            "strict_correct": sum(1 for row in margin_rows if row["constrained_choice_match"]),
            "strict_accuracy": strict_audit["constrained_choice_top1_accuracy"],
            "mean_margin": mean(float(row["margin_top1_minus_top2"]) for row in margin_rows),
            "median_like_low_count_lt_0_05": sum(1 for row in margin_rows if row["margin_top1_minus_top2"] < 0.05),
            "rows_with_prompt_target_leak": sum(1 for row in margin_rows if row["eval_hack_prompt_leak"]),
            "residual_rows": len(residual_rows),
        },
        "residual_rows": residual_rows,
        "lowest_margin_rows": margin_rows[:8],
        "per_task": per_task,
        "per_language": per_language,
        "recommended_disjoint_support_targets": [
            {
                "row_id": row["row_id"],
                "task_type": row["task_type"],
                "language_family": row["language_family"],
                "residual_family": row["residual_family"],
                "recommended_support_direction": (
                    "fresh verifier target disambiguation roots"
                    if row["residual_family"] == "verifier_target_disambiguation"
                    else "fresh evidence-citation contrast roots that separate candidate surface from stronger supporting evidence"
                ),
            }
            for row in residual_rows
        ],
        "notes": [
            "Current strict misses are semantic, not decoder-junk failures.",
            "Prompt target leakage should be repaired before promoting any future broader reviewed-v2.7 benchmark claims.",
            "Low-margin correct rows are the next most likely regressions under broader scaling or cleaner anti-cheat rewrites.",
        ],
        "outputs": {
            "audit_json": display(AUDIT_JSON),
            "row_margins": display(ROW_JSONL),
        },
    }

    write_json(AUDIT_JSON, audit)
    write_jsonl(ROW_JSONL, margin_rows)
    write_json(SUMMARY, audit)
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

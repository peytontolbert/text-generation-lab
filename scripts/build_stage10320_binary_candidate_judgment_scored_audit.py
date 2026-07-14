#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10320
NAME = "stage10320_binary_candidate_judgment_scored_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "binary_candidate_judgment_scored_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASE_RESULT = ROOT / "runs/local/artifacts/stage10308_source_backed_action_support_plus_probe/bounded_decoder_probe/execution_result.json"
BASE_STRICT = ROOT / "runs/local/artifacts/stage10308_source_backed_action_support_plus_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
NEW_RESULT = ROOT / "runs/local/artifacts/stage10319_binary_candidate_judgment_scored_probe/bounded_decoder_probe/execution_result.json"
NEW_STRICT = ROOT / "runs/local/artifacts/stage10319_binary_candidate_judgment_scored_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def strict_summary(result: dict[str, Any]) -> dict[str, Any]:
    strict = result["bounded_choice_eval"]["strict_eval"]
    return {
        "rows": strict["rows"],
        "constrained_choice_top1_accuracy": strict["constrained_choice_top1_accuracy"],
        "full_vocab_top1_accuracy": strict["full_vocab_top1_accuracy"],
        "rows_with_target_rank_1": strict["rows_with_target_rank_1"],
    }


def by_slice(strict_audit: dict[str, Any]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for row in strict_audit["row_cards"]:
        parts = row["row_id"].split("::")
        key = f"{parts[-4]}::{parts[-3]}"
        card = out.setdefault(key, {"rows": 0, "correct": 0})
        card["rows"] += 1
        if row["constrained_choice_match"]:
            card["correct"] += 1
    return out


def compare_slices(base: dict[str, dict[str, int]], new: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in sorted(set(base) | set(new)):
        base_rows = base.get(key, {"rows": 0, "correct": 0})
        new_rows = new.get(key, {"rows": 0, "correct": 0})
        base_acc = (base_rows["correct"] / base_rows["rows"]) if base_rows["rows"] else None
        new_acc = (new_rows["correct"] / new_rows["rows"]) if new_rows["rows"] else None
        rows.append({
            "slice": key,
            "base_correct": base_rows["correct"],
            "base_rows": base_rows["rows"],
            "base_accuracy": base_acc,
            "new_correct": new_rows["correct"],
            "new_rows": new_rows["rows"],
            "new_accuracy": new_acc,
            "delta_accuracy": None if base_acc is None or new_acc is None else (new_acc - base_acc),
        })
    return rows


def build() -> dict[str, Any]:
    base_result = read_json(BASE_RESULT)
    new_result = read_json(NEW_RESULT)
    base_strict = read_json(BASE_STRICT)
    new_strict = read_json(NEW_STRICT)
    base_summary = strict_summary(base_result)
    new_summary = strict_summary(new_result)
    slice_deltas = compare_slices(by_slice(base_strict), by_slice(new_strict))
    unchanged = all((row["delta_accuracy"] or 0.0) == 0.0 for row in slice_deltas)
    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "decision": "rejected_for_frontier_promotion",
        "verdict": "binary_candidate_judgment_auxiliary_changed_latent_ranking_but_not_strict_behavior",
        "base_run_id": base_result["run_id"],
        "new_run_id": new_result["run_id"],
        "base_runtime_weights_sha256": base_result["runtime_model_bundle"]["weights_sha256"],
        "new_runtime_weights_sha256": new_result["runtime_model_bundle"]["weights_sha256"],
        "strict_base": base_summary,
        "strict_new": new_summary,
        "strict_deltas": {
            "constrained_choice_top1_accuracy": new_summary["constrained_choice_top1_accuracy"] - base_summary["constrained_choice_top1_accuracy"],
            "full_vocab_top1_accuracy": new_summary["full_vocab_top1_accuracy"] - base_summary["full_vocab_top1_accuracy"],
            "rows_with_target_rank_1": new_summary["rows_with_target_rank_1"] - base_summary["rows_with_target_rank_1"],
        },
        "slice_deltas": slice_deltas,
        "strict_slice_outcomes_unchanged": unchanged,
        "frontier_promotion_supported": False,
        "main_findings": [
            "Strict constrained-choice accuracy stayed exactly flat at 0.7007874015748031.",
            "Rows with target rank 1 improved from 16 to 23, but none of those ranking gains flipped a strict row outcome.",
            "The previously weak python and web action-taking slices remained at 0 strict accuracy.",
            "The branch is therefore useful as evidence about latent ranking, not as a promotable frontier improvement.",
        ],
        "recommended_next_move": "Pivot away from binary YES/NO candidate judgment auxiliary rows and test a richer objective that changes the final constrained decision boundary directly.",
    }
    write_json(AUDIT_JSON, audit)
    write_json(SUMMARY, {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": audit["created_at_utc"],
        "decision": audit["decision"],
        "frontier_promotion_supported": audit["frontier_promotion_supported"],
        "strict_delta": audit["strict_deltas"]["constrained_choice_top1_accuracy"],
        "target_rank_1_delta": audit["strict_deltas"]["rows_with_target_rank_1"],
    })
    return audit


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True))

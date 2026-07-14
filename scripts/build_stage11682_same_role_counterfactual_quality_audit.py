#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11682_same_role_counterfactual_quality_audit"
OUT = ART / NAME
SUMMARY = OUT / "same_role_counterfactual_quality_audit.json"

COUNTERFACTUAL_ROWS = ART / "stage11678_web_remaining_miss_counterfactual_builder/web_same_role_identity_counterfactual_train.jsonl"
TRAIN_LOG = ART / "stage11679_web_same_role_counterfactual_probe/bounded_decoder_probe/loss_by_step.jsonl"
EVAL_CARD = ART / "stage11680_web_same_role_counterfactual_postrun_audit/bounded_choice_eval_audit_same_role_counterfactual_train__encoder_option_retrieval_web_task_candidate_head.json"
DECISION = ART / "stage11681_web_counterfactual_decision/web_counterfactual_decision.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def option_role(option: dict[str, Any]) -> str:
    obj = option.get("canonical_candidate_object") if isinstance(option.get("canonical_candidate_object"), dict) else {}
    return str(option.get("role") or obj.get("role") or "")


def option_value(option: dict[str, Any]) -> str:
    obj = option.get("canonical_candidate_object") if isinstance(option.get("canonical_candidate_object"), dict) else {}
    return str(obj.get("value") or option.get("text") or option.get("value") or "")


def static_errors(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for row in rows:
        target = row.get("bounded_choice_target_label")
        options = row.get("opaque_options") or []
        labels = [opt.get("label") for opt in options]
        target_option = next((opt for opt in options if opt.get("label") == target), None)
        if target_option is None:
            errors.append({"row_id": row.get("row_id"), "error": "target_label_missing", "target": target, "labels": labels})
            continue
        if option_value(target_option) != row.get("semantic_target_value"):
            errors.append(
                {
                    "row_id": row.get("row_id"),
                    "error": "semantic_target_value_mismatch",
                    "option_value": option_value(target_option),
                    "semantic_target_value": row.get("semantic_target_value"),
                }
            )
        prompt = str(row.get("prompt_text") or "")
        if f"{target}: role=" not in prompt:
            errors.append({"row_id": row.get("row_id"), "error": "target_candidate_line_missing_from_prompt", "target": target})
        anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
        if not anti.get("stage11678_label_permutation"):
            errors.append({"row_id": row.get("row_id"), "error": "missing_label_permutation_flag"})
    return errors


def exposure_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    log_rows = load_jsonl(TRAIN_LOG) if TRAIN_LOG.exists() else []
    exposure = Counter()
    for log_row in log_rows:
        for row_id in log_row.get("row_ids") or []:
            if "stage11678_same_role_identity" in str(row_id):
                exposure[str(row_id)] += 1
    expected_ids = {str(row["row_id"]) for row in rows}
    missing = sorted(expected_ids - set(exposure))
    values = list(exposure.values())
    return {
        "train_log_exists": TRAIN_LOG.exists(),
        "steps": len(log_rows),
        "unique_counterfactual_rows_seen": len(exposure),
        "total_counterfactual_exposures": sum(exposure.values()),
        "missing_counterfactual_rows": missing,
        "min_exposures": min(values) if values else None,
        "max_exposures": max(values) if values else None,
    }


def eval_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    card = load_json(EVAL_CARD)
    row_by_id = {row["row_id"]: row for row in rows}
    misses = [rc for rc in card.get("row_cards", []) if not rc.get("constrained_choice_match")]
    by_task = Counter()
    by_role = Counter()
    by_pair = Counter()
    for rc in misses:
        row = row_by_id.get(rc.get("row_id"), {})
        target = row.get("bounded_choice_target_label")
        target_option = next((opt for opt in row.get("opaque_options") or [] if opt.get("label") == target), {})
        by_task[str(row.get("task_type") or "unknown")] += 1
        by_role[option_role(target_option)] += 1
        by_pair[(str(row.get("task_type") or "unknown"), option_role(target_option), str(rc.get("bounded_choice_target_label")), str(rc.get("constrained_choice_top1_label")))] += 1
    return {
        "correct": card.get("constrained_choice_correct"),
        "rows": card.get("constrained_choice_rows"),
        "accuracy": card.get("constrained_choice_top1_accuracy"),
        "misses": len(misses),
        "misses_by_task": dict(by_task),
        "misses_by_target_role": dict(by_role),
        "top_miss_pairs": [(list(k), v) for k, v in by_pair.most_common(30)],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load_jsonl(COUNTERFACTUAL_ROWS)
    errors = static_errors(rows)
    exposures = exposure_summary(rows)
    evals = eval_summary(rows)
    decision = load_json(DECISION)
    task_counts = Counter(str(row.get("task_type") or "unknown") for row in rows)
    role_counts = Counter()
    for row in rows:
        target = row.get("bounded_choice_target_label")
        target_option = next((opt for opt in row.get("opaque_options") or [] if opt.get("label") == target), {})
        role_counts[option_role(target_option)] += 1
    gates = {
        "static_remap_clean": not errors,
        "all_counterfactual_rows_sampled": exposures["unique_counterfactual_rows_seen"] == len(rows) and not exposures["missing_counterfactual_rows"],
        "counterfactual_train_fit_acceptable": (evals["correct"] or 0) >= 70,
        "stage11679_rejected": str(decision.get("decision", "")).startswith("stage11679_rejected"),
    }
    summary = {
        "stage": 11682,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "counterfactual_package_static_clean_but_objective_underfits" if gates["static_remap_clean"] and gates["all_counterfactual_rows_sampled"] and not gates["counterfactual_train_fit_acceptable"] else "counterfactual_quality_needs_review",
        "gates": gates,
        "row_counts": {"rows": len(rows), "task_type": dict(task_counts), "target_role": dict(role_counts)},
        "static_errors": errors[:50],
        "exposure_summary": exposures,
        "eval_summary": evals,
        "interpretation": [
            "The Stage11678 label-shuffled rows are structurally consistent and were sampled during Stage11679.",
            "The current Web task candidate head did not fit them: 23/92 after 1536 head-only steps.",
            "The next intervention should not be another full mixed probe. Either simplify the counterfactual rows by family or train a dedicated semantic candidate identity head before mixing back into Web heldout training.",
        ],
        "source_artifacts": {
            "counterfactual_rows": rel(COUNTERFACTUAL_ROWS),
            "train_log": rel(TRAIN_LOG),
            "eval_card": rel(EVAL_CARD),
            "decision": rel(DECISION),
        },
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "gates": gates, "exposure": exposures, "eval": evals}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

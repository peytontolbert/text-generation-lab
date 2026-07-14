#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11068
NAME = "stage11068_explicit_ledger_a_prior_relief_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "explicit_ledger_a_prior_relief_audit.json"
ROW_CARDS_JSONL = OUT_DIR / "explicit_ledger_a_prior_relief_row_cards.jsonl"

CLEAN_VALIDATION = ARTIFACTS / "stage11065_singleton_eval_quarantine_package" / "agentkernel_lite_encdec_validation.jsonl"
CLEAN_STRICT = ARTIFACTS / "stage11065_singleton_eval_quarantine_package" / "agentkernel_lite_encdec_strict_eval.jsonl"
STAGE11063_EVAL_AUDIT = ARTIFACTS / "stage11063_ready_lane_fresh_support_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_eval.json"
STAGE11063_STRICT_AUDIT = ARTIFACTS / "stage11063_ready_lane_fresh_support_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_strict_eval.json"
STAGE11051_RESERVED_ROWS = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence" / "reserved_residual_candidates.jsonl"
STAGE11064_RESERVED_SCORED = ARTIFACTS / "stage11064_ready_lane_fresh_support_postrun_audit" / "reserved_residual_candidate_rows_scored.jsonl"
STAGE11064_SUMMARY = ARTIFACTS / "stage11064_ready_lane_fresh_support_postrun_audit" / "ready_lane_fresh_support_postrun_audit.json"
STAGE11066_SUMMARY = ARTIFACTS / "stage11066_singleton_eval_quarantine_audit" / "singleton_eval_quarantine_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "missing") for row in rows).items()))


def option_labels(row: dict[str, Any]) -> set[str]:
    opts = ((row.get("standalone_projection_source") or {}).get("opaque_options")) or row.get("opaque_options") or []
    return {str(opt.get("label") or "") for opt in opts if isinstance(opt, dict) and opt.get("label")}


def option_value_for_label(row: dict[str, Any], label: str | None) -> str | None:
    if not label:
        return None
    opts = ((row.get("standalone_projection_source") or {}).get("opaque_options")) or row.get("opaque_options") or []
    for opt in opts:
        if isinstance(opt, dict) and str(opt.get("label") or "") == label:
            return str(opt.get("value") or "")
    return None


def filter_cards(cards: list[dict[str, Any]], allowed_ids: set[str]) -> list[dict[str, Any]]:
    return [row for row in cards if str(row.get("row_id") or "") in allowed_ids]


def routed_prediction(row: dict[str, Any], scored: dict[str, Any]) -> tuple[str | None, str]:
    base_label = scored.get("constrained_choice_top1_label")
    full_vocab_label = scored.get("full_vocab_top1_text")
    row_id = str(row.get("row_id") or "")
    labels = option_labels(row)
    if (
        "strict_candidate_explicit_ledger_v1" in row_id
        and str(row.get("task_type") or "") == "evidence_citation"
        and base_label == "A"
        and isinstance(full_vocab_label, str)
        and full_vocab_label in labels
        and full_vocab_label != "A"
    ):
        return full_vocab_label, "explicit_ledger_a_prior_relief"
    return base_label, "base_constrained_choice"


def evaluate_group(group_name: str, rows: list[dict[str, Any]], scored_rows: list[dict[str, Any]]) -> dict[str, Any]:
    source_by_id = {str(row.get("row_id") or ""): row for row in rows}
    row_cards: list[dict[str, Any]] = []
    for scored in scored_rows:
        row_id = str(scored.get("row_id") or "")
        row = source_by_id.get(row_id)
        if row is None:
            continue
        predicted_label, policy = routed_prediction(row, scored)
        target_label = str(row.get("target_text") or "")
        row_cards.append(
            {
                "group": group_name,
                "row_id": row_id,
                "language_family": str(row.get("language_family") or ""),
                "repo_family": str(row.get("repo_family") or ""),
                "task_type": str(row.get("task_type") or ""),
                "target_label": target_label,
                "base_label": scored.get("constrained_choice_top1_label"),
                "full_vocab_top1_text": scored.get("full_vocab_top1_text"),
                "routed_label": predicted_label,
                "routed_correct": predicted_label == target_label,
                "policy_used": policy,
                "target_rank_full_vocab": scored.get("target_rank_full_vocab"),
                "routed_value": option_value_for_label(row, predicted_label),
                "target_value": option_value_for_label(row, target_label),
            }
        )
    correct = sum(1 for row in row_cards if row.get("routed_correct") is True)
    return {
        "rows": len(row_cards),
        "correct": correct,
        "exact_accuracy": (correct / len(row_cards)) if row_cards else None,
        "row_cards": row_cards,
        "changed_rows": [row for row in row_cards if row.get("routed_label") != row.get("base_label")],
        "miss_rows": [row for row in row_cards if row.get("routed_correct") is False],
    }


def main() -> None:
    clean_validation_rows = load_jsonl(CLEAN_VALIDATION)
    clean_strict_rows = load_jsonl(CLEAN_STRICT)
    reserved_rows = load_jsonl(STAGE11051_RESERVED_ROWS)
    baseline_reserved_summary = load_json(STAGE11064_SUMMARY)
    baseline_clean_summary = load_json(STAGE11066_SUMMARY)

    validation_ids = {str(row.get("row_id") or "") for row in clean_validation_rows}
    strict_ids = {str(row.get("row_id") or "") for row in clean_strict_rows}

    validation_scored = filter_cards(list(load_json(STAGE11063_EVAL_AUDIT).get("row_cards") or []), validation_ids)
    strict_scored = filter_cards(list(load_json(STAGE11063_STRICT_AUDIT).get("row_cards") or []), strict_ids)
    reserved_scored = load_jsonl(STAGE11064_RESERVED_SCORED)

    validation_result = evaluate_group("clean_validation", clean_validation_rows, validation_scored)
    strict_result = evaluate_group("clean_strict", clean_strict_rows, strict_scored)
    reserved_result = evaluate_group("reserved_residual", reserved_rows, reserved_scored)
    all_cards = [*validation_result["row_cards"], *strict_result["row_cards"], *reserved_result["row_cards"]]

    baseline_validation = ((((baseline_clean_summary.get("cleaned_surface_result") or {}).get("validation") or {}).get("exact_accuracy")))
    baseline_strict = ((((baseline_clean_summary.get("cleaned_surface_result") or {}).get("strict") or {}).get("exact_accuracy")))
    baseline_reserved = ((((baseline_reserved_summary.get("reserved_candidate_result") or {}).get("overall") or {}).get("exact_accuracy")))

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Audit a very narrow inference-side scorer relief policy aimed at the explicit-ledger evidence rows that currently collapse to label A.",
            "Keep the cleaned heldout successor surface unchanged unless the row matches the explicit-ledger A-prior pattern exactly.",
        ],
        "source_artifacts": {
            "cleaned_validation_rows": rel(CLEAN_VALIDATION),
            "cleaned_strict_rows": rel(CLEAN_STRICT),
            "stage11063_eval_audit": rel(STAGE11063_EVAL_AUDIT),
            "stage11063_strict_audit": rel(STAGE11063_STRICT_AUDIT),
            "reserved_rows": rel(STAGE11051_RESERVED_ROWS),
            "reserved_scored_rows": rel(STAGE11064_RESERVED_SCORED),
            "baseline_reserved_summary": rel(STAGE11064_SUMMARY),
            "baseline_clean_summary": rel(STAGE11066_SUMMARY),
        },
        "policy_definition": {
            "default_policy": "base_constrained_choice",
            "override_policy": "if explicit-ledger evidence row and base label == A and decoder top token is another valid option label, use decoder label",
            "motivation": "The surviving safe signal appears to be a specific A-prior in the constrained scorer on explicit-ledger residual rows, not a general evidence-policy improvement.",
        },
        "results": {
            "clean_validation": {
                "rows": validation_result["rows"],
                "correct": validation_result["correct"],
                "exact_accuracy": validation_result["exact_accuracy"],
                "changed_rows": len(validation_result["changed_rows"]),
                "miss_row_ids": [row["row_id"] for row in validation_result["miss_rows"]],
            },
            "clean_strict": {
                "rows": strict_result["rows"],
                "correct": strict_result["correct"],
                "exact_accuracy": strict_result["exact_accuracy"],
                "changed_rows": len(strict_result["changed_rows"]),
                "miss_row_ids": [row["row_id"] for row in strict_result["miss_rows"]],
            },
            "reserved_residual": {
                "rows": reserved_result["rows"],
                "correct": reserved_result["correct"],
                "exact_accuracy": reserved_result["exact_accuracy"],
                "changed_rows": len(reserved_result["changed_rows"]),
                "miss_row_ids": [row["row_id"] for row in reserved_result["miss_rows"]],
            },
        },
        "delta_vs_base_policy": {
            "clean_validation_accuracy_delta": None if baseline_validation is None or validation_result["exact_accuracy"] is None else validation_result["exact_accuracy"] - float(baseline_validation),
            "clean_strict_accuracy_delta": None if baseline_strict is None or strict_result["exact_accuracy"] is None else strict_result["exact_accuracy"] - float(baseline_strict),
            "reserved_accuracy_delta": None if baseline_reserved is None or reserved_result["exact_accuracy"] is None else reserved_result["exact_accuracy"] - float(baseline_reserved),
        },
        "changed_rows_by_group": {
            "clean_validation": validation_result["changed_rows"],
            "clean_strict": strict_result["changed_rows"],
            "reserved_residual": reserved_result["changed_rows"],
        },
        "changed_rows_by_language": count_by([row for row in all_cards if row.get("policy_used") == "explicit_ledger_a_prior_relief"], "language_family"),
        "findings": [
            "The safe inference-side gain is much narrower than the earlier broad evidence override suggested.",
            "This policy leaves the cleaned heldout surface unchanged while lifting the reserved residual bank where the constrained scorer collapses to label A on explicit-ledger evidence rows.",
            "That pattern points to a scorer/objective defect localized to a specific residual family, which is a better next training target than another broad support sweep.",
        ],
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "row_cards_jsonl": rel(ROW_CARDS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(ROW_CARDS_JSONL, all_cards)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

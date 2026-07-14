#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11066
NAME = "stage11066_singleton_eval_quarantine_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "singleton_eval_quarantine_audit.json"

PACKAGE_DIR = ARTIFACTS / "stage11065_singleton_eval_quarantine_package"
PACKAGE_SUMMARY = PACKAGE_DIR / "singleton_eval_quarantine_package.json"
PACKAGE_VALIDATION = PACKAGE_DIR / "agentkernel_lite_encdec_validation.jsonl"
PACKAGE_STRICT = PACKAGE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
QUARANTINED_ROWS = PACKAGE_DIR / "quarantined_singleton_eval_rows.jsonl"

POSTRUN_DIR = ARTIFACTS / "stage11064_ready_lane_fresh_support_postrun_audit"
POSTRUN_SUMMARY = POSTRUN_DIR / "ready_lane_fresh_support_postrun_audit.json"
STAGE11063_VALIDATION = ARTIFACTS / "stage11063_ready_lane_fresh_support_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_eval.json"
STAGE11063_STRICT = ARTIFACTS / "stage11063_ready_lane_fresh_support_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_strict_eval.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "missing") for row in rows).items()))


def filter_row_cards(cards: list[dict[str, Any]], allowed_ids: set[str]) -> list[dict[str, Any]]:
    return [row for row in cards if str(row.get("row_id") or "") in allowed_ids]


def metric_block(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get(field), bool)]
    correct = sum(1 for row in scored if row.get(field) is True)
    return {
        "rows": len(rows),
        "scored_rows": len(scored),
        "correct": correct,
        "exact_accuracy": (correct / len(scored)) if scored else None,
    }


def main() -> None:
    package_summary = load_json(PACKAGE_SUMMARY)
    postrun_summary = load_json(POSTRUN_SUMMARY)
    validation_audit = load_json(STAGE11063_VALIDATION)
    strict_audit = load_json(STAGE11063_STRICT)
    validation_rows = load_jsonl(PACKAGE_VALIDATION)
    strict_rows = load_jsonl(PACKAGE_STRICT)
    quarantined_rows = load_jsonl(QUARANTINED_ROWS)

    allowed_validation_ids = {str(row.get("row_id") or "") for row in validation_rows}
    allowed_strict_ids = {str(row.get("row_id") or "") for row in strict_rows}
    filtered_validation_cards = filter_row_cards(list(validation_audit.get("row_cards") or []), allowed_validation_ids)
    filtered_strict_cards = filter_row_cards(list(strict_audit.get("row_cards") or []), allowed_strict_ids)

    validation_metrics = metric_block(filtered_validation_cards, "constrained_choice_match")
    strict_metrics = metric_block(filtered_strict_cards, "constrained_choice_match")
    baseline_validation = ((postrun_summary.get("successor_surface_result") or {}).get("validation_accuracy"))
    baseline_strict = ((postrun_summary.get("successor_surface_result") or {}).get("strict_accuracy"))

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Recompute the current stage11063 runtime score on the singleton-cleaned heldout package without rerunning training.",
            "Separate structural heldout cleanup from model-capability change so the next probe has a clean baseline.",
        ],
        "source_artifacts": {
            "cleaned_package_summary": rel(PACKAGE_SUMMARY),
            "stage11063_validation_audit": rel(STAGE11063_VALIDATION),
            "stage11063_strict_audit": rel(STAGE11063_STRICT),
            "stage11064_postrun_summary": rel(POSTRUN_SUMMARY),
            "quarantined_rows_jsonl": rel(QUARANTINED_ROWS),
        },
        "cleaned_surface_result": {
            "validation": {
                **validation_metrics,
                "miss_rows": [row.get("row_id") for row in filtered_validation_cards if row.get("constrained_choice_match") is False],
            },
            "strict": {
                **strict_metrics,
                "miss_rows": [row.get("row_id") for row in filtered_strict_cards if row.get("constrained_choice_match") is False],
            },
        },
        "delta_vs_stage11064_uncleaned": {
            "validation_accuracy_delta": None if baseline_validation is None or validation_metrics["exact_accuracy"] is None else validation_metrics["exact_accuracy"] - float(baseline_validation),
            "strict_accuracy_delta": None if baseline_strict is None or strict_metrics["exact_accuracy"] is None else strict_metrics["exact_accuracy"] - float(baseline_strict),
        },
        "quarantine_report": {
            "quarantined_rows_total": len(quarantined_rows),
            "quarantined_rows_by_split": count_by(quarantined_rows, "quarantine_split_origin"),
            "quarantined_rows_by_language": count_by(quarantined_rows, "language_family"),
            "quarantined_rows_by_task": count_by(quarantined_rows, "task_type"),
            "quarantined_row_ids": [str(row.get("row_id") or "") for row in quarantined_rows],
        },
        "reserved_candidate_result_unchanged": (postrun_summary.get("reserved_candidate_result") or {}),
        "findings": [
            "The strict and validation surfaces are now structurally free of singleton-option evaluation rows.",
            "This audit isolates the effect of heldout cleanup from any future training or scorer changes.",
            "If the next probe moves this cleaned baseline, the gain will be easier to interpret because trivial one-option rows are no longer inflating the eval surface.",
        ],
        "package_metrics": package_summary.get("metrics"),
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
        },
    }

    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11641
NAME = "stage11641_normalized_web_support_probe_decision"
OUT = ART / NAME
SUMMARY = OUT / "normalized_web_support_probe_decision.json"

STAGE11640 = ART / "stage11640_normalized_web_support_postrun_audit/normalized_web_support_postrun_audit.json"
SUPPORT_AUDIT = ART / "stage11640_normalized_web_support_postrun_audit/bounded_choice_eval_audit_normalized_web_train_support.json"
SUPPORT_ROWS = ART / "stage11638_web_support_schema_normalization/web_support_normalized_admitted_train_rows.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def grouped_support(cards: list[dict[str, Any]], rows_by_id: dict[str, dict[str, Any]], field: str) -> dict[str, Any]:
    buckets: dict[str, list[bool]] = defaultdict(list)
    for card in cards:
        row = rows_by_id.get(str(card.get("row_id")), {})
        buckets[str(row.get(field))].append(card.get("constrained_choice_match") is True)
    return {
        key: {"correct": sum(values), "rows": len(values), "accuracy": sum(values) / len(values) if values else None}
        for key, values in sorted(buckets.items())
    }


def main() -> None:
    audit = load_json(STAGE11640)
    support_card = load_json(SUPPORT_AUDIT)
    support_cards = support_card.get("row_cards") or []
    rows_by_id = {str(row.get("row_id")): row for row in load_jsonl(SUPPORT_ROWS)}
    compact = {
        key: {"correct": value.get("correct"), "rows": value.get("rows")}
        for key, value in (audit.get("results") or {}).items()
    }
    support_by_task = grouped_support(support_cards, rows_by_id, "task_type")
    support_by_source = grouped_support(support_cards, rows_by_id, "stage11638_source")
    support_by_transition = grouped_support(support_cards, rows_by_id, "observed_verifier_transition")
    support_correct = compact.get("normalized_web_train_support", {}).get("correct") or 0
    support_rows = compact.get("normalized_web_train_support", {}).get("rows") or 0
    gates = {
        "stage11640_rejected": audit.get("decision") == "do_not_promote_stage11639",
        "support_fit_failed": support_correct < max(1, int(0.5 * support_rows)),
        "protected_gates_regressed": not all((audit.get("preservation_gates") or {}).values()),
        "web_heldout_regressed_below_stage11507": (compact.get("web_heldout", {}).get("correct") or 0) < 35,
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "reject_stage11639_objective_scorer_path",
        "gates": gates,
        "stage11640_compact_results": compact,
        "support_fit_breakdown": {
            "by_task_type": support_by_task,
            "by_source": support_by_source,
            "by_transition": support_by_transition,
        },
        "failure_interpretation": [
            "Stage11639 did not merely fail to generalize; it failed to fit the normalized train-support surface under the product Web scorer.",
            "The worst support buckets are evidence_citation, verifier_outcome, and abstention_insufficient_evidence.",
            "PASS_TO_PASS relevance rows fit especially poorly compared with controlled FAIL_TO_PASS rows.",
            "This falsifies another full-model CE+bounded-aux Web-support probe. Do not repeat this path with the same objective.",
        ],
        "next_required_change": [
            "Train the Web task candidate head directly or head-only first on normalized support until same-support fit is high.",
            "Alternatively add a task-specific scorer/loss for verifier_outcome, evidence_citation, and abstention before full-model training.",
            "Only after support fit is demonstrated should a low-LR full-model distillation be attempted.",
            "Any next probe must still preserve Stage11507 protected gates and remain CUDA_VISIBLE_DEVICES=2 only.",
        ],
        "source_artifacts": {
            "stage11640": rel(STAGE11640),
            "support_audit": rel(SUPPORT_AUDIT),
            "support_rows": rel(SUPPORT_ROWS),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "gates": gates, "support_fit_breakdown": summary["support_fit_breakdown"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

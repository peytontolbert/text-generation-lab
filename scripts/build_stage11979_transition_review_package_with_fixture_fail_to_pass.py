#!/usr/bin/env python3
"""Merge source-backed review rows with controlled fixture FAIL_TO_PASS support."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11979
NAME = "stage11979_transition_review_package_with_fixture_fail_to_pass"
OUT = ART / NAME
SUMMARY = OUT / "transition_review_package_with_fixture_fail_to_pass.json"
ROWS = OUT / "transition_review_package_with_fixture_fail_to_pass.jsonl"
SOURCE_ROWS = ART / "stage11976_transition_root_250_review_package_gate/transition_root_250_admitted_review_package.jsonl"
FIXTURE_ROWS = ART / "stage11978_controlled_fixture_fail_to_pass_materialization/controlled_fixture_fail_to_pass_review_rows.jsonl"

STATUS_FLOORS = {"FAIL_TO_PASS": 50, "PASS_TO_PASS": 100, "PASS_CURRENT_BUILD": 40, "PASS_CURRENT_BUILD_AND_RUN": 40, "INSUFFICIENT_EVIDENCE": 40, "NOT_EXERCISED": 40}
LANG_FLOORS = {"python": 50, "rust": 50, "c_cpp": 50}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def status(row: dict[str, Any]) -> str:
    return str(row.get("observed_verifier_transition") or "UNKNOWN")


def main() -> None:
    source = read_jsonl(SOURCE_ROWS)
    fixture = read_jsonl(FIXTURE_ROWS)
    rows = []
    for row in source:
        row = dict(row)
        row["stage11979_supply_class"] = "source_backed_review"
        rows.append(row)
    for row in fixture:
        row = dict(row)
        row["stage11979_supply_class"] = "controlled_fixture_train_support_only"
        row["strict_eval_eligible"] = False
        row["train_support_only"] = True
        rows.append(row)
    write_jsonl(ROWS, rows)
    status_counts = Counter(status(row) for row in rows)
    supply_counts = Counter(row.get("stage11979_supply_class") for row in rows)
    lang_counts = Counter(str(row.get("language_family") or "unknown") for row in rows)
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "transition_review_package_with_fixture_fail_to_pass_ready_not_trainable",
        "source_artifacts": {"source_review_rows": rel(SOURCE_ROWS), "controlled_fixture_rows": rel(FIXTURE_ROWS)},
        "package_summary": {"rows": len(rows), "status_counts": dict(status_counts), "supply_class_counts": dict(supply_counts), "language_row_counts": dict(lang_counts)},
        "remaining_to_transition_root_250_floor": {"status_remaining": {k: max(0, v - status_counts.get(k, 0)) for k, v in STATUS_FLOORS.items()}, "language_remaining": {k: max(0, v - lang_counts.get(k, 0)) for k, v in LANG_FLOORS.items()}},
        "quality_decision": {"train_package_ready": False, "reason": ["Only one FAIL_TO_PASS row exists and it is controlled-fixture train-support-only.", "No fresh Rust rows are present.", "C/C++ rows remain absent from admitted review package.", "Scale remains 16 rows, far below Stage11967 Transition-Root-250 requirements."]},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS)},
        "next_stage_recommendation": {"stage": "stage11980_transition_root_supply_next_actions", "action": "Prioritize fresh Rust source acquisition and real repo FAIL_TO_PASS materialization; keep Stage11979 as support-only replay, not a training frontier."},
    }
    write_json(SUMMARY, artifact)
    print(json.dumps({"decision": artifact["decision"], "package_summary": artifact["package_summary"], "quality_decision": artifact["quality_decision"], "next": artifact["next_stage_recommendation"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

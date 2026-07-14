#!/usr/bin/env python3
"""Roll up Stage11971-11973 materialization supply against Stage11967 deficits."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11974
NAME = "stage11974_transition_root_250_materialization_rollup"
OUT = ART / NAME
SUMMARY = OUT / "transition_root_250_materialization_rollup.json"
REVIEW_ROWS = OUT / "transition_root_250_review_rows_rollup.jsonl"
STAGE11967 = ART / "stage11967_transition_root_250_supply_contract/transition_root_250_supply_contract.json"
STAGE11972_ROWS = ART / "stage11972_transition_root_250_probe_admission_audit/transition_root_250_admitted_review_rows.jsonl"
STAGE11972_SUMMARY = ART / "stage11972_transition_root_250_probe_admission_audit/transition_root_250_probe_admission_audit.json"
STAGE11973_RECORDS = ART / "stage11973_transition_root_250_controlled_mutation_probe/controlled_fail_to_pass_transition_records_review_queue.jsonl"
STAGE11973_SUMMARY = ART / "stage11973_transition_root_250_controlled_mutation_probe/transition_root_250_controlled_mutation_probe.json"

MIN_STATUS_RECORDS = {
    "FAIL_TO_PASS": 50,
    "PASS_TO_PASS": 100,
    "PASS_CURRENT_BUILD": 40,
    "PASS_CURRENT_BUILD_AND_RUN": 40,
    "INSUFFICIENT_EVIDENCE": 40,
    "NOT_EXERCISED": 40,
}
MIN_LANGUAGE_ROOTS = {"python": 50, "rust": 50, "c_cpp": 50}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def row_status(row: dict[str, Any]) -> str:
    return str(row.get("observed_verifier_transition") or (row.get("standalone_projection_source") or {}).get("observed_verifier_transition") or "UNKNOWN")


def row_root(row: dict[str, Any]) -> str:
    return str(row.get("source_root_id") or row.get("root_id") or row.get("root_lineage_key") or row.get("record_id") or "")


def main() -> None:
    contract = read_json(STAGE11967)
    stage11972_summary = read_json(STAGE11972_SUMMARY)
    stage11973_summary = read_json(STAGE11973_SUMMARY)
    rows = read_jsonl(STAGE11972_ROWS)
    fail_to_pass_records = read_jsonl(STAGE11973_RECORDS)
    # Convert controlled records are not bounded rows yet; keep them separate unless present.
    combined_rows = rows[:]
    write_jsonl(REVIEW_ROWS, combined_rows)
    status_counts = Counter(row_status(row) for row in combined_rows)
    language_roots: dict[str, set[str]] = {}
    for row in combined_rows:
        lang = str(row.get("language_family") or "unknown")
        language_roots.setdefault(lang, set()).add(row_root(row))
    language_root_counts = {lang: len(values) for lang, values in sorted(language_roots.items())}
    status_remaining = {status: max(0, needed - status_counts.get(status, 0)) for status, needed in MIN_STATUS_RECORDS.items()}
    language_remaining = {lang: max(0, needed - language_root_counts.get(lang, 0)) for lang, needed in MIN_LANGUAGE_ROOTS.items()}
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "materialization_rollup_complete_not_trainable",
        "source_artifacts": {
            "stage11967_contract": rel(STAGE11967),
            "stage11972_admitted_rows": rel(STAGE11972_ROWS),
            "stage11972_summary": rel(STAGE11972_SUMMARY),
            "stage11973_records": rel(STAGE11973_RECORDS),
            "stage11973_summary": rel(STAGE11973_SUMMARY),
        },
        "stage11972_admission_summary": stage11972_summary.get("admission_summary"),
        "stage11973_mutation_summary": stage11973_summary.get("summary"),
        "rollup_supply": {
            "review_rows": len(combined_rows),
            "unique_roots": len({row_root(row) for row in combined_rows}),
            "status_counts": dict(status_counts),
            "language_root_counts": language_root_counts,
            "controlled_fail_to_pass_records": len(fail_to_pass_records),
        },
        "remaining_against_root_250_floor_from_new_supply_only": {
            "status_record_remaining": status_remaining,
            "language_root_remaining": language_remaining,
        },
        "quality_decision": {
            "train_package_ready": False,
            "reason": [
                "Only PASS_CURRENT_BUILD review rows are currently admitted after source-backed/skipped-test cleanup.",
                "No controlled FAIL_TO_PASS record admitted in Stage11973.",
                "Fresh Rust source supply remains unresolved after excluding tokenizers/candle.",
                "The review rows are useful evidence, but they are far below Stage11967 Transition-Root-250 floors.",
            ],
        },
        "next_stage_recommendation": {
            "stage": "stage11975_transition_root_250_probe_expansion_and_mutation_repair",
            "action": "Expand source-backed probes beyond 20 roots, prioritize roots with real executed tests, and add controlled mutations only after baseline PASS_TO_PASS is proven.",
            "specific_actions": [
                "Add a probe mode that searches multiple test targets per root and records the first source-backed PASS_TO_PASS.",
                "Reject collect-only roots from FAIL_TO_PASS mutation attempts.",
                "Acquire or hydrate fresh Rust roots outside tokenizers/candle.",
                "Only then build a Stage11976 train-support package.",
            ],
        },
        "outputs": {"summary": rel(SUMMARY), "review_rows": rel(REVIEW_ROWS)},
        "notes": {
            "base_python_environment": "Known broken torch namespace can cause false failures for ML repos; probe logs preserve these as INSUFFICIENT_EVIDENCE rather than trainable failures.",
            "trellis_environment": "Useful for model runtime but not sufficient to hydrate every repo dependency, e.g. einx missing frozendict.",
        },
    }
    write_json(SUMMARY, artifact)
    print(json.dumps({"decision": artifact["decision"], "rollup_supply": artifact["rollup_supply"], "quality_decision": artifact["quality_decision"], "next": artifact["next_stage_recommendation"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

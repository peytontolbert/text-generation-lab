#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12385_combined_train_support_ledger_v15_dedup"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SOURCE_LEDGER = ROOT / "runs/summaries/stage12383_combined_train_support_ledger_v14.json"
SOURCE_ROWS = ROOT / "runs/local/artifacts/stage12383_combined_train_support_ledger_v14/combined_selected_test_rows_v14.jsonl"
NON_SELECTED_BASE_ROWS = 91
RISKY_FIELDS = ["strict_eval_eligible", "source_heldout_admissible", "level3_admitted", "patch_trace_admitted", "repair_claim_admitted"]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def dedupe(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    seen: set[str] = set()
    kept: list[dict] = []
    duplicates: list[dict] = []
    for row in rows:
        row_id = row.get("row_id")
        if row_id in seen:
            duplicates.append(row)
        else:
            seen.add(row_id)
            kept.append(row)
    return kept, duplicates


def risky_counts(rows: list[dict]) -> dict:
    counts: Counter[str] = Counter()
    for row in rows:
        admission = row.get("admission") or {}
        for field in RISKY_FIELDS:
            if admission.get(field) or row.get(field):
                counts[field] += 1
    return dict(counts)


def raw_command_rows(rows: list[dict]) -> int:
    patterns = ["command=", "Observed command", "node_modules/.bin", "vitest run", "pytest "]
    return sum(1 for row in rows if any(pattern in (row.get("input_text") or "") for pattern in patterns))


def generic_non_candidate_targets(rows: list[dict]) -> int:
    return sum(
        1 for row in rows
        if row.get("task_family") != "transition_candidate_selection"
        and ("candidate_0" in (row.get("target_semantic_id") or "") or "candidate_selected_test_backed" in (row.get("target_semantic_id") or ""))
    )


def main() -> None:
    source = read_json(SOURCE_LEDGER)
    rows = read_jsonl(SOURCE_ROWS)
    kept, duplicates = dedupe(rows)
    language_counts: Counter[str] = Counter({"session_unknown_language": NON_SELECTED_BASE_ROWS})
    task_counts: Counter[str] = Counter({"event_local_transition_observation": NON_SELECTED_BASE_ROWS})
    source_counts: Counter[str] = Counter()
    for row in kept:
        language_counts[row.get("language_family") or "session_unknown_language"] += 1
        task_counts[row.get("task_family") or row.get("record_type") or "unknown"] += 1
        source_counts[row.get("stage") or "unknown"] += 1
    total = NON_SELECTED_BASE_ROWS + len(kept)
    raw_count = raw_command_rows(kept)
    generic_count = generic_non_candidate_targets(kept)
    risky = risky_counts(kept)
    ledger = dict(source)
    ledger.update({
        "stage": STAGE,
        "decision": "combined_train_support_ledger_v15_dedup_ready_500_not_reached" if not duplicates and raw_count == 0 and generic_count == 0 and not risky else "combined_train_support_ledger_v15_dedup_authoritative_with_prior_duplicates_removed",
        "training_allowed": False,
        "claim_boundary": "Authoritative deduped current ledger. Training remains blocked until 500-row target and QC gates are met.",
        "supersedes": [str(SOURCE_LEDGER)],
        "current_admitted_train_support_tasks": total,
        "remaining_gap_to_500": max(0, 500 - total),
        "non_selected_base_rows": NON_SELECTED_BASE_ROWS,
        "selected_test_rows_admitted_after_audit": len(kept),
        "selected_test_duplicate_rows_removed": len(duplicates),
        "source_counts": dict(source_counts),
        "language_counts": dict(language_counts),
        "task_family_or_record_type_counts": dict(task_counts),
        "risky_claim_counts_should_be_zero": risky,
        "selected_test_raw_command_rows_should_be_zero": raw_count,
        "selected_test_generic_non_candidate_targets_should_be_zero": generic_count,
        "duplicate_row_ids_should_be_zero": len(duplicates),
        "duplicate_row_id_counts": dict(Counter(row.get("row_id") for row in duplicates)),
        "training_blockers": [
            "500_train_support_target_not_reached",
            "luxon_re_render_or_defer_decision_needed",
            "Open-SWE transformation rows not yet admitted under Stage12364 policy",
        ],
    })
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "combined_selected_test_rows_v15_dedup.jsonl", kept)
    write_jsonl(OUT / "duplicate_selected_test_rows_v15.jsonl", duplicates)
    (OUT / "combined_train_support_ledger_v15_dedup.json").write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

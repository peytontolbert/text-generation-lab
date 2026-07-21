#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12324_combined_train_support_ledger"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

SOURCES = {
    "stage12320_event_local_observation": ROOT / "runs/local/artifacts/stage12320_event_local_semantic_review_admission/event_local_observation_train_support_admitted_rows.jsonl",
    "stage12322_rust_cpp_selected_test": ROOT / "runs/local/artifacts/stage12322_priority_rust_cpp_selected_test_admission/priority_rust_cpp_selected_test_train_support_rows.jsonl",
    "stage12323_v4_event_local": ROOT / "runs/local/artifacts/stage12323_v4_event_local_review_admission/v4_event_local_train_support_admitted_rows.jsonl",
    "stage12326_direct_python_selected_test": ROOT / "runs/local/artifacts/stage12326_direct_python_selected_test_admission/direct_python_selected_test_train_support_rows.jsonl",
    "stage12331_luxon_web_selected_test": ROOT / "runs/local/artifacts/stage12331_luxon_web_selected_test_admission/luxon_web_selected_test_train_support_rows.jsonl",
}
TARGET = 500


def read_jsonl(path: Path):
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_counts = {}
    language_counts = Counter()
    task_counts = Counter()
    risky_counts = Counter()
    train_rows = 0
    for source_name, path in SOURCES.items():
        rows = read_jsonl(path)
        source_counts[source_name] = len(rows)
        train_rows += len(rows)
        for row in rows:
            language_counts[row.get("language_family") or "session_unknown_language"] += 1
            task_counts[row.get("task_family") or row.get("record_type") or "unknown"] += 1
            for field in ["strict_eval_eligible", "source_heldout_admissible", "level3_admitted", "patch_trace_admitted", "repair_claim_admitted"]:
                admission = row.get("admission") or {}
                if admission.get(field):
                    risky_counts[field] += 1
    ledger = {
        "stage": STAGE,
        "decision": "combined_train_support_ledger_ready_500_not_reached",
        "claim_boundary": "Counting admitted train-support rows only. Does not authorize model training by itself and does not claim strict/source-heldout/Level-3 repair readiness.",
        "training_allowed": False,
        "target_train_support_tasks": TARGET,
        "current_admitted_train_support_tasks": train_rows,
        "remaining_gap_to_500": max(0, TARGET - train_rows),
        "source_counts": source_counts,
        "language_counts": dict(language_counts),
        "task_family_or_record_type_counts": dict(task_counts),
        "risky_claim_counts_should_be_zero": dict(risky_counts),
        "next_supply_lanes": [
            {
                "lane": "stage12321_remaining_v4_needs_extraction",
                "available_candidates": 27,
                "expected_additional_rows": "unknown_until_Stage12316_style_extraction",
            },
            {
                "lane": "stage12321_linked_v4_unadmitted_due_caps_or_prior_admission",
                "available_candidates": "bounded; inspect Stage12323 blocked refs",
                "expected_additional_rows": "small unless caps loosened or new source diversity added",
            },
            {
                "lane": "multisource_selected_test_or_transition_roots",
                "available_candidates": "required for remaining majority of gap",
                "expected_additional_rows": "need ~384 more after current ledger",
            },
        ],
        "plateau_guard": [
            "Do not count review candidates as train-support rows.",
            "Do not count event-local observation/status rows as Level-3 repair episodes.",
            "Do not loosen dominance caps to hit 500 from the same few chats.",
            "Next scale must add source diversity, not duplicate transition functions.",
        ],
    }
    (OUT / "combined_train_support_ledger.json").write_text(
        json.dumps(ledger, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "COMBINED_TRAIN_SUPPORT_LEDGER_STAGE12324.md").write_text(
        "# Stage12324 Combined Train-Support Ledger\n\n"
        f"Current admitted train-support tasks: `{train_rows}` / `{TARGET}`.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

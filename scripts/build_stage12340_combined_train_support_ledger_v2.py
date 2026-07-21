#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12340_combined_train_support_ledger_v2"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
TARGET = 500
SOURCES = {
    "stage12320_event_local_observation": ROOT / "runs/local/artifacts/stage12320_event_local_semantic_review_admission/event_local_observation_train_support_admitted_rows.jsonl",
    "stage12322_rust_cpp_selected_test": ROOT / "runs/local/artifacts/stage12322_priority_rust_cpp_selected_test_admission/priority_rust_cpp_selected_test_train_support_rows.jsonl",
    "stage12323_v4_event_local": ROOT / "runs/local/artifacts/stage12323_v4_event_local_review_admission/v4_event_local_train_support_admitted_rows.jsonl",
    "stage12326_direct_python_selected_test": ROOT / "runs/local/artifacts/stage12326_direct_python_selected_test_admission/direct_python_selected_test_train_support_rows.jsonl",
    "stage12331_luxon_web_selected_test": ROOT / "runs/local/artifacts/stage12331_luxon_web_selected_test_admission/luxon_web_selected_test_train_support_rows.jsonl",
    "stage12339_openclaw_web_selected_test": ROOT / "runs/local/artifacts/stage12339_openclaw_web_selected_test_admission/openclaw_web_selected_test_train_support_rows.jsonl",
}


def read_jsonl(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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
            admission = row.get("admission") or {}
            for field in [
                "strict_eval_eligible",
                "source_heldout_admissible",
                "level3_admitted",
                "patch_trace_admitted",
                "repair_claim_admitted",
            ]:
                if admission.get(field):
                    risky_counts[field] += 1
    ledger = {
        "stage": STAGE,
        "decision": "combined_train_support_ledger_v2_ready_500_not_reached",
        "claim_boundary": "Counting admitted train-support rows only. Does not authorize model training by itself and does not claim strict/source-heldout/Level-3 repair readiness.",
        "training_allowed": False,
        "target_train_support_tasks": TARGET,
        "current_admitted_train_support_tasks": train_rows,
        "remaining_gap_to_500": max(0, TARGET - train_rows),
        "delta_vs_stage12324": train_rows - 141,
        "source_counts": source_counts,
        "language_counts": dict(language_counts),
        "task_family_or_record_type_counts": dict(task_counts),
        "risky_claim_counts_should_be_zero": dict(risky_counts),
        "next_supply_lanes": [
            {
                "lane": "open_swe_priority_safe_transition_extractor",
                "available_candidates": 50,
                "expected_additional_rows": "candidate_or_qc_only_first; no train-support until deterministic admission stage",
            },
            {
                "lane": "web_no_install_focused_verifier_recovery",
                "available_candidates": "OpenClaw has one admitted root; remaining candidates require focused execution or env repair",
                "expected_additional_rows": "small, source-diverse selected-test support only",
            },
            {
                "lane": "repair_patch_trace_sources",
                "available_candidates": "Bears/SWE-bench need authoritative before-after verifier proof",
                "expected_additional_rows": "blocked until same-source patch-effect proof exists",
            },
        ],
        "plateau_guard": [
            "Do not count review candidates as train-support rows.",
            "Do not count event-local observation/status rows as Level-3 repair episodes.",
            "Do not loosen dominance caps to hit 500 from the same few chats.",
            "Do not count PASS_TO_PASS focused verifier rows as repair proof.",
            "Next scale must add source diversity, not duplicate transition functions.",
        ],
    }
    (OUT / "combined_train_support_ledger_v2.json").write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "COMBINED_TRAIN_SUPPORT_LEDGER_V2_STAGE12340.md").write_text(
        "# Stage12340 Combined Train-Support Ledger V2\n\n"
        f"Current admitted train-support tasks: `{train_rows}` / `{TARGET}`.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

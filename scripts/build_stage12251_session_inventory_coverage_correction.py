#!/usr/bin/env python3
"""Build Stage12251 session inventory coverage correction.

Stage12250 intentionally introduced a multi-source decomposition contract, but
its observed session census only looked at one current_raw normalized-event
subset. This correction records the broader session-derived source inventory so
future root mining does not undercount available session material.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12251_session_inventory_coverage_correction"
BASE = ROOT / "runs/local/artifacts/session_like_source_inventory_real"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"_missing": str(path.relative_to(ROOT))}
    return json.loads(path.read_text(encoding="utf-8"))


def count_lines(path: Path) -> int | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        return sum(1 for _ in f)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def summary_entry(label: str, rel_summary: str, rel_rows: str | None = None) -> dict[str, Any]:
    summary_path = ROOT / rel_summary
    rows_path = ROOT / rel_rows if rel_rows else None
    summary = read_json(summary_path)
    return {
        "label": label,
        "summary_path": rel_summary,
        "rows_path": rel_rows,
        "line_count": count_lines(rows_path) if rows_path else None,
        "summary": summary,
    }


def main() -> int:
    pools = [
        summary_entry(
            "current_raw_normalized_events",
            "runs/local/artifacts/session_like_source_inventory_real/current_raw_parsed_bounded_jsonl_metadata/session_parse_summary.json",
            "runs/local/artifacts/session_like_source_inventory_real/current_raw_parsed_bounded_jsonl_metadata/normalized_session_events.jsonl",
        ),
        summary_entry(
            "current_recent96_normalized_events",
            "runs/local/artifacts/session_like_source_inventory_real/current_recent96_parsed_bounded_jsonl_metadata/session_parse_summary.json",
            "runs/local/artifacts/session_like_source_inventory_real/current_recent96_parsed_bounded_jsonl_metadata/normalized_session_events.jsonl",
        ),
        summary_entry(
            "broad_parsed_normalized_events",
            "runs/local/artifacts/session_like_source_inventory_real/parsed_bounded_jsonl_metadata/session_parse_summary.json",
            "runs/local/artifacts/session_like_source_inventory_real/parsed_bounded_jsonl_metadata/normalized_session_events.jsonl",
        ),
        summary_entry(
            "current_recent96_execution_traces",
            "runs/local/artifacts/session_like_source_inventory_real/current_recent96_session_execution_traces/session_execution_trace_summary.json",
            "runs/local/artifacts/session_like_source_inventory_real/current_recent96_session_execution_traces/session_execution_traces.jsonl",
        ),
        summary_entry(
            "session_execution_traces",
            "runs/local/artifacts/session_like_source_inventory_real/session_execution_traces/session_execution_trace_summary.json",
            "runs/local/artifacts/session_like_source_inventory_real/session_execution_traces/session_execution_traces.jsonl",
        ),
        summary_entry(
            "base_local_root_session_episodes",
            "runs/local/artifacts/session_like_source_inventory_real/local_root_session_episodes/local_root_session_episode_summary.json",
            "runs/local/artifacts/session_like_source_inventory_real/local_root_session_episodes/local_root_session_episodes.jsonl",
        ),
        summary_entry(
            "best_bootstrap_stage10100",
            "runs/local/artifacts/stage10100_true_source_backed_multilingual_session_inventory_audit/true_source_backed_multilingual_session_inventory_audit.json",
            "runs/local/artifacts/stage10100_true_source_backed_multilingual_session_inventory_audit/true_source_backed_multilingual_session_inventory_rows.jsonl",
        ),
    ]

    normalized_event_total = sum(
        int((p["summary"].get("parsed_event_rows") or 0))
        for p in pools
        if "normalized_events" in p["label"]
    )
    normalized_session_upper_sum = sum(
        int((p["summary"].get("parsed_sessions") or 0))
        for p in pools
        if "normalized_events" in p["label"]
    )
    execution_trace_total = sum(
        int((p["summary"].get("trace_count") or 0))
        for p in pools
        if "execution_traces" in p["label"]
    )

    correction = {
        "stage": STAGE,
        "artifact_type": "session_inventory_coverage_correction",
        "decision": "stage12250_census_was_partial_correct_to_multisource_session_inventory",
        "training_allowed": False,
        "claim_boundary": (
            "Correction/control artifact only. Counts are source-pool inventory counts, not deduped admitted roots. "
            "No training rows are admitted."
        ),
        "correction": {
            "incorrect_or_incomplete_reading": "Treating current_raw_parsed_bounded_jsonl_metadata as the whole session corpus.",
            "correct_reading": (
                "current_raw is one subset. There are broader parsed, current_recent96, execution-trace, "
                "episode, packable, and stage10100 session-derived pools. These must be inventoried and "
                "deduped into root candidates before admission."
            ),
            "stage12250_status": "valid decomposition schema, incomplete observed source census",
        },
        "aggregate_source_pool_counts_before_dedupe": {
            "normalized_event_rows_sum": normalized_event_total,
            "normalized_parsed_session_count_sum_upper_bound": normalized_session_upper_sum,
            "execution_trace_rows_sum": execution_trace_total,
            "note": "These are not deduped. Some pools overlap by source/session/derived variant.",
        },
        "source_pools": pools,
        "why_345k_single_session_pool_looked_wrong": [
            "The 345k count came only from current_raw_parsed_bounded_jsonl_metadata.",
            "That file has 9 parsed_sessions and is dominated by one large agentkernel session.",
            "Broader parsed_bounded_jsonl_metadata reports 103 parsed_sessions.",
            "current_recent96_parsed_bounded_jsonl_metadata reports 16 parsed_sessions.",
            "Execution trace pools add about 39.7k trace rows across their own session subsets.",
        ],
        "corrected_next_stage_requirements": [
            "Scan all session-derived pools listed here, not only current_raw.",
            "Emit source_pool_id and source_variant_id for every candidate to prevent duplicate-derived roots.",
            "Dedupe by root_lineage_key, repo_family, task signature, changed paths, selected tests, and source session hash.",
            "Report source-pool coverage before and after dedupe.",
            "Only after dedupe, split into level_0/1/2/3/4 admission candidates.",
        ],
        "revised_next_stage_sequence": [
            {
                "stage": "stage12252_multisource_session_pool_indexer",
                "purpose": "Index all session-derived pools and emit dedupe keys plus raw-source availability.",
                "training_allowed": False,
            },
            {
                "stage": "stage12253_session_root_candidate_deduper",
                "purpose": "Collapse overlapping variants into root candidates and report candidate count by source family and language.",
                "training_allowed": False,
            },
            {
                "stage": "stage12254_raw_session_trace_rehydrator",
                "purpose": "For high-value candidates, recover raw command output, patch bodies, verifier logs, and state updates.",
                "training_allowed": False,
            },
            {
                "stage": "stage12255_multisource_root_admission_rollup",
                "purpose": "Admit candidates by evidence level without counting derived variants as roots.",
                "training_allowed": False,
            },
        ],
        "quality_invariant": (
            "More session pools should increase candidate-root recall, but admission remains based on same-source evidence and root-level dedupe."
        ),
    }

    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", correction)
    write_json(out_dir / "session_inventory_coverage_correction.json", correction)
    md = f"""# Stage12251 Session Inventory Coverage Correction

## Decision

`{correction["decision"]}`

No training is allowed.

## Correction

Stage12250's schema is useful, but its observed session census was partial. It only measured `current_raw_parsed_bounded_jsonl_metadata`, which has 9 parsed sessions. That is not the whole session-derived corpus.

Broader source pools include:

- `current_raw`: 345,487 events / 9 parsed sessions
- `current_recent96`: 351,732 events / 16 parsed sessions
- `parsed_bounded`: 241,043 events / 103 parsed sessions
- execution trace pools: 39,678 trace rows before dedupe
- local/augmented/packable episode variants, often 56-row derived views
- Stage10100 inventory with 56 best-bootstrap rows across Python/C++/Web

## Correct Interpretation

The problem is not that only 9 sessions exist. The problem is that prior stages looked at a partial subset and then converted too little of the broader source inventory into deduped root candidates.

Next stages must index all session pools, dedupe derived variants, then admit by evidence level.
"""
    write_text(out_dir / "SESSION_INVENTORY_COVERAGE_CORRECTION_STAGE12251.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "SESSION_INVENTORY_COVERAGE_CORRECTION_STAGE12251.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

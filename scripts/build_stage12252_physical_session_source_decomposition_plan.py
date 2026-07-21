#!/usr/bin/env python3
"""Build Stage12252 physical session source decomposition plan.

This corrects the previous partial-session framing by making physical session
files the parent inventory and all parsed/episode/pack/stage101 artifacts child
views that must be deduped before root admission.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12252_physical_session_source_decomposition_plan"


def read_json(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    if not path.exists():
        return {"_missing": rel}
    return json.loads(path.read_text(encoding="utf-8"))


def line_count(rel: str) -> int | None:
    path = ROOT / rel
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


def stage101_entry(stage: str, rel: str) -> dict[str, Any]:
    return {"stage": stage, "path": rel, "line_count": line_count(rel)}


def main() -> int:
    root_card = read_json("runs/local/artifacts/session_like_source_inventory_real/session_inventory_root_card.json")
    counts_by_root = read_json("runs/local/artifacts/session_like_source_inventory_real/session_inventory_counts_by_root.json")
    correction = read_json("runs/summaries/stage12251_session_inventory_coverage_correction.json")

    parsed_pools = [
        {
            "pool_id": "parsed_bounded_all",
            "summary": "runs/local/artifacts/session_like_source_inventory_real/parsed_bounded_jsonl_metadata/session_parse_summary.json",
            "rows": "runs/local/artifacts/session_like_source_inventory_real/parsed_bounded_jsonl_metadata/normalized_session_events.jsonl",
        },
        {
            "pool_id": "current_raw_parsed",
            "summary": "runs/local/artifacts/session_like_source_inventory_real/current_raw_parsed_bounded_jsonl_metadata/session_parse_summary.json",
            "rows": "runs/local/artifacts/session_like_source_inventory_real/current_raw_parsed_bounded_jsonl_metadata/normalized_session_events.jsonl",
        },
        {
            "pool_id": "current_recent96_parsed",
            "summary": "runs/local/artifacts/session_like_source_inventory_real/current_recent96_parsed_bounded_jsonl_metadata/session_parse_summary.json",
            "rows": "runs/local/artifacts/session_like_source_inventory_real/current_recent96_parsed_bounded_jsonl_metadata/normalized_session_events.jsonl",
        },
    ]
    for pool in parsed_pools:
        pool["summary_json"] = read_json(pool["summary"])
        pool["line_count"] = line_count(pool["rows"])

    trace_pools = [
        {
            "pool_id": "session_execution_traces",
            "summary": "runs/local/artifacts/session_like_source_inventory_real/session_execution_traces/session_execution_trace_summary.json",
            "rows": "runs/local/artifacts/session_like_source_inventory_real/session_execution_traces/session_execution_traces.jsonl",
        },
        {
            "pool_id": "current_recent96_session_execution_traces",
            "summary": "runs/local/artifacts/session_like_source_inventory_real/current_recent96_session_execution_traces/session_execution_trace_summary.json",
            "rows": "runs/local/artifacts/session_like_source_inventory_real/current_recent96_session_execution_traces/session_execution_traces.jsonl",
        },
    ]
    for pool in trace_pools:
        pool["summary_json"] = read_json(pool["summary"])
        pool["line_count"] = line_count(pool["rows"])

    downstream_views = [
        stage101_entry("stage10100_inventory_rows", "runs/local/artifacts/stage10100_true_source_backed_multilingual_session_inventory_audit/true_source_backed_multilingual_session_inventory_rows.jsonl"),
        stage101_entry("stage10101_shortcut_rows", "runs/local/artifacts/stage10101_real_session_edit_localization_bootstrap_shortcut_audit/real_session_edit_localization_bootstrap_shortcut_rows.jsonl"),
        stage101_entry("stage10102_candidates", "runs/local/artifacts/stage10102_real_session_candidate_competition_request/real_session_candidate_competition_rows.jsonl"),
        stage101_entry("stage10103_bootstrap_packet", "runs/local/artifacts/stage10103_real_session_candidate_competition_bootstrap_packet/real_session_candidate_competition_bootstrap_packet.jsonl"),
        stage101_entry("stage10103_drops", "runs/local/artifacts/stage10103_real_session_candidate_competition_bootstrap_packet/real_session_candidate_competition_bootstrap_drops.jsonl"),
        stage101_entry("stage10104_review_packets", "runs/local/artifacts/stage10104_real_session_bootstrap_review_packets/real_session_bootstrap_review_packets.jsonl"),
        stage101_entry("stage10109_replenishment_candidates", "runs/local/artifacts/stage10109_real_session_multilingual_replenishment_ledger/real_session_multilingual_replenishment_candidates.jsonl"),
        stage101_entry("stage10110_low_risk_carryforward", "runs/local/artifacts/stage10108_real_session_shortcut_safe_successor_request/real_session_low_risk_carryforward_rows.jsonl"),
        stage101_entry("stage10110_quarantined_shortcut", "runs/local/artifacts/stage10108_real_session_shortcut_safe_successor_request/real_session_quarantined_shortcut_rows.jsonl"),
    ]

    plan = {
        "stage": STAGE,
        "artifact_type": "physical_session_source_decomposition_plan",
        "decision": "physical_session_files_are_parent_inventory_derivative_pools_are_child_views",
        "training_allowed": False,
        "claim_boundary": (
            "Plan/control artifact only. Counts describe inventory and derivative views, not admitted roots. "
            "No row admission or training is authorized."
        ),
        "parent_inventory": {
            "root_card": root_card,
            "counts_by_root": counts_by_root,
        },
        "corrected_understanding": [
            "The corpus is not 9 sessions. The 9-session count belongs only to current_raw parsed metadata.",
            "Physical session inventory has 1,739 files across Codex sessions, Cursor chats, and Cursor projects.",
            "Parsed/event/trace/episode/pack/stage101xx files are derivative views and may overlap.",
            "The root campaign must begin with physical source indexing, then attach derivative views by source file/session lineage.",
            "Root admission must happen after dedupe, not per derivative artifact.",
        ],
        "derivative_views": {
            "parsed_event_pools": parsed_pools,
            "execution_trace_pools": trace_pools,
            "stage101xx_views": downstream_views,
        },
        "decomposition_pipeline": [
            {
                "step": "physical_source_index",
                "output": "physical_source_records.jsonl",
                "required_fields": [
                    "physical_source_id",
                    "source_root_label",
                    "source_path",
                    "source_hash",
                    "size_bytes",
                    "mtime_utc",
                    "source_kind",
                ],
            },
            {
                "step": "derivative_view_attach",
                "output": "source_view_edges.jsonl",
                "required_fields": [
                    "physical_source_id",
                    "view_pool_id",
                    "view_record_id",
                    "session_id_hint",
                    "event_count",
                    "trace_count",
                    "episode_id",
                    "pack_id",
                ],
            },
            {
                "step": "candidate_root_projection",
                "output": "candidate_root_records.jsonl",
                "required_fields": [
                    "root_id",
                    "root_lineage_key",
                    "physical_source_ids",
                    "view_record_ids",
                    "repo_family",
                    "language_family",
                    "task_signature",
                    "changed_paths",
                    "selected_tests",
                    "patch_evidence_available",
                    "verifier_output_available",
                    "state_transition_available",
                ],
            },
            {
                "step": "dedupe_and_admission",
                "output": "root_admission_records.jsonl",
                "required_fields": [
                    "root_id",
                    "dedupe_cluster_id",
                    "admission_level",
                    "blocked_reason_codes",
                    "allowed_training_lanes",
                    "strict_eval_eligible",
                    "train_support_eligible",
                ],
            },
        ],
        "dedupe_keys": [
            "source_hash",
            "session_id_hint",
            "repo_family",
            "task_signature_digest",
            "changed_paths_digest",
            "selected_tests_digest",
            "patch_diff_digest",
            "verifier_command_digest",
        ],
        "next_stage_requests": [
            {
                "stage": "stage12253_physical_session_source_indexer",
                "purpose": "Index all 1,739 physical session-like files and emit parent physical_source_records.",
                "training_allowed": False,
            },
            {
                "stage": "stage12254_session_derivative_view_attacher",
                "purpose": "Attach parsed events, execution traces, local episodes, packs, and Stage101xx rows to physical source records.",
                "training_allowed": False,
            },
            {
                "stage": "stage12255_session_root_candidate_projector",
                "purpose": "Project deduped candidate roots from attached source views with evidence availability flags.",
                "training_allowed": False,
            },
            {
                "stage": "stage12256_session_root_admission_audit",
                "purpose": "Admit by level_0/1/2/3/4 and report actual candidate roots toward 500.",
                "training_allowed": False,
            },
        ],
        "quality_rules": [
            "Do not add line counts across derivative pools as unique source count.",
            "Do not count Stage101xx rows as raw sessions; they are downstream views.",
            "Do not admit a root until physical source lineage and derivative view lineage are recorded.",
            "Do not count Cursor project files as software-maintainer roots until task/repo/action/verifier evidence is extracted.",
            "Do not train from this inventory until root admission levels are assigned.",
        ],
        "supersedes_or_refines": [
            "stage12250_multisource_root_decomposition_contract observed census",
            "stage12251_session_inventory_coverage_correction",
        ],
    }

    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", plan)
    write_json(out_dir / "physical_session_source_decomposition_plan.json", plan)
    md = f"""# Stage12252 Physical Session Source Decomposition Plan

## Decision

`{plan["decision"]}`

No training is allowed.

## Corrected Parent Inventory

- physical session-like files: `{root_card.get("total_files")}`
- source roots: `{root_card.get("source_root_labels")}`
- total bytes: `{root_card.get("total_bytes")}`
- Codex session JSONLs: `{counts_by_root.get("codex_sessions", {}).get("file_count")}`
- Cursor chat DBs: `{counts_by_root.get("cursor_chats", {}).get("file_count")}`
- Cursor project files: `{counts_by_root.get("cursor_projects", {}).get("file_count")}`

## Core Fix

Start from physical source files, then attach derivative views. Do not start from one parsed subset and assume it represents the corpus.

The next stages should produce:

1. `physical_source_records.jsonl`
2. `source_view_edges.jsonl`
3. `candidate_root_records.jsonl`
4. `root_admission_records.jsonl`

That is how we turn real source volume into 500 high-quality roots without double-counting pack/episode variants.
"""
    write_text(out_dir / "PHYSICAL_SESSION_SOURCE_DECOMPOSITION_PLAN_STAGE12252.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "PHYSICAL_SESSION_SOURCE_DECOMPOSITION_PLAN_STAGE12252.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build Stage12254 source coverage lesson/gate.

This records the dataset lesson from the Stage12250/12251 correction and turns
it into a fail-closed checklist for future miners and training package builders.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12254_source_coverage_lesson_gate"


def load_json(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    if not path.exists():
        return {"_missing": rel}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def main() -> int:
    source_index = load_json("runs/summaries/stage12253_physical_session_source_indexer.json")
    correction = load_json("runs/summaries/stage12251_session_inventory_coverage_correction.json")
    physical_plan = load_json("runs/summaries/stage12252_physical_session_source_decomposition_plan.json")
    coverage = source_index.get("coverage") or {}
    root_card = (physical_plan.get("parent_inventory") or {}).get("root_card") or {}
    counts = (physical_plan.get("parent_inventory") or {}).get("counts_by_root") or {}
    codex_count = (counts.get("codex_sessions") or {}).get("file_count")
    total_files = root_card.get("total_files") or coverage.get("expected_total_files")

    gate = {
        "stage": STAGE,
        "artifact_type": "source_coverage_lesson_gate",
        "decision": "future_miners_must_reconcile_to_physical_parent_inventory_or_fail_closed",
        "training_allowed": False,
        "claim_boundary": (
            "Lesson/gate artifact only. It admits no data and authorizes no training. "
            "It defines mandatory checks that would have caught the Stage12250 partial-corpus mistake."
        ),
        "lesson_learned": {
            "failure": (
                "A derivative parsed subset with 9 current_raw sessions was treated as if it represented the session corpus. "
                "The actual physical parent inventory contains 1,739 session-like files."
            ),
            "root_cause": (
                "Miners were allowed to report row/event/session counts without reconciling to a physical parent inventory, "
                "without parsed coverage percentages, and without separating derivative views from source parents."
            ),
            "corrective_principle": (
                "Source coverage is a first-class dataset invariant. A parsed/event/episode/pack pool is only a child view until "
                "it attaches to a physical parent source and passes dedupe/admission."
            ),
        },
        "mandatory_gates": [
            {
                "gate": "physical_parent_inventory_loaded",
                "required": {
                    "source_roots": ["codex_sessions", "cursor_chats", "cursor_projects"],
                    "total_physical_files": total_files,
                    "codex_session_files": codex_count,
                },
                "fail_closed_if": "parent inventory missing, stale, or not reported before derivative mining",
            },
            {
                "gate": "parsed_coverage_percent_reported",
                "required_fields": [
                    "covered_physical_sources",
                    "eligible_parent_sources",
                    "all_parent_sources",
                    "covered_over_eligible_percent",
                    "covered_over_all_percent",
                ],
                "example_failure": "current_raw parsed: 9/758 Codex sessions and 9/1739 all physical files, so partial view only",
            },
            {
                "gate": "derivative_parent_separation",
                "required_fields": [
                    "physical_source_id",
                    "view_pool_id",
                    "source_variant_id",
                    "view_record_id",
                    "session_id_hint",
                    "join_confidence",
                ],
                "fail_closed_if": "parsed events, traces, episodes, packs, or Stage101xx rows are counted as raw sessions or roots",
            },
            {
                "gate": "no_row_count_substitution",
                "required_counters": [
                    "event_count",
                    "trace_count",
                    "episode_count",
                    "candidate_root_count",
                    "parsed_root_count",
                    "joined_root_count",
                    "qc_passed_root_count",
                    "admitted_root_count",
                ],
                "fail_closed_if": "events/traces/rows/projections are reported as roots",
            },
            {
                "gate": "dedupe_before_admission",
                "required_dedupe_keys": [
                    "source_hash_or_source_file_hash",
                    "session_id_hint",
                    "root_lineage_key",
                    "repo_family",
                    "task_signature_digest",
                    "changed_paths_digest",
                    "selected_tests_digest",
                    "patch_diff_digest",
                    "verifier_command_digest",
                ],
                "fail_closed_if": "root admission is attempted on derivative rows before cluster dedupe",
            },
            {
                "gate": "admission_level_after_lineage",
                "required_levels": [
                    "level_0_context_only",
                    "level_1_verifier_only_no_patch",
                    "level_2_patch_context_no_execution",
                    "level_3_single_step_closed_loop",
                    "level_4_multi_step_maintainer_episode",
                    "external_comparable_repair",
                ],
                "fail_closed_if": "training manifest emitted before source-family mix and admission-level mix reports pass",
            },
        ],
        "source_index_status": {
            "stage12253_coverage_pass": coverage.get("coverage_pass"),
            "expected_total_files": coverage.get("expected_total_files"),
            "observed_physical_source_records": coverage.get("observed_physical_source_records"),
            "coverage_by_root": coverage.get("coverage_by_root"),
        },
        "required_next_implementation": {
            "stage": "stage12255_physical_session_path_hash_rehydrator",
            "why": (
                "Stage12253 records only relative_path_hash. Existing parsed derivative rows use source_file_hash derived "
                "from full source path. To attach exactly, scan physical roots and compute non-content path hashes without "
                "emitting raw session content."
            ),
            "training_allowed": False,
        },
        "refines": [
            "stage12250_multisource_root_decomposition_contract",
            "stage12251_session_inventory_coverage_correction",
            "stage12252_physical_session_source_decomposition_plan",
            "stage12253_physical_session_source_indexer",
        ],
    }

    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", gate)
    write_json(out_dir / "source_coverage_lesson_gate.json", gate)
    md = f"""# Stage12254 Source Coverage Lesson Gate

## Decision

`{gate["decision"]}`

No training is allowed.

## Lesson Learned

A derivative parsed subset cannot represent the corpus unless it reconciles to the physical parent inventory. The `current_raw` parsed pool had 9 sessions, but the parent inventory has `{total_files}` physical session-like files. This would have been caught by requiring parsed coverage percentages against the parent denominator.

## Mandatory Rule

Every future miner must report:

- physical parent coverage,
- parsed/view coverage percentages,
- derivative-vs-parent separation,
- root dedupe clusters,
- admission levels after dedupe,
- source-family and admission-level mix before training.

If any of those are missing, the stage fails closed.
"""
    write_text(out_dir / "SOURCE_COVERAGE_LESSON_GATE_STAGE12254.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "SOURCE_COVERAGE_LESSON_GATE_STAGE12254.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

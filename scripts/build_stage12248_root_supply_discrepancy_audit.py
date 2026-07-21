#!/usr/bin/env python3
"""Build Stage12248 root-supply discrepancy audit.

This is a control artifact only. It explains why large session/action volume is
not becoming admitted high-quality maintainer roots, without weakening the
closed-loop admission gates.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12248_root_supply_discrepancy_audit"


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


def records_seen(summary: dict[str, Any], suffix: str) -> int | None:
    for row in summary.get("inputs_scanned") or []:
        path = row.get("path", "")
        if path.endswith(suffix):
            return row.get("records_seen")
    return None


def main() -> int:
    stage10516 = load_json("runs/summaries/stage10516_long_context_root_state_compiler.json")
    stage12200 = load_json("runs/summaries/stage12200_same_source_patch_trace_episode_miner.json")
    stage12201 = load_json("runs/summaries/stage12201_patch_evidence_recovery.json")
    stage12202 = load_json("runs/summaries/stage12202_level3_readiness_joiner.json")
    stage12242 = load_json("runs/summaries/stage12242_maintainer_500_candidate_intake_rollup.json")
    stage12247 = load_json("runs/summaries/stage12247_plateau_avoidance_graph_aligned_dataset_plan.json")

    raw_events = records_seen(stage12200, "normalized_session_events.jsonl")
    rollup_counts = stage12242.get("rollup_counts", {})

    audit = {
        "stage": STAGE,
        "artifact_type": "root_supply_discrepancy_audit",
        "decision": "bottleneck_is_pre_admission_candidate_mining_and_same_source_joining_not_gate_strictness",
        "training_allowed": False,
        "claim_boundary": (
            "Control/audit artifact only. It explains why large Codex session/action volume "
            "has not become 500 admitted maintainer roots. It admits no rows and authorizes no training."
        ),
        "headline": {
            "raw_session_events_seen_by_stage12200": raw_events,
            "stage10516_compiled_root_records": (stage10516.get("metrics") or {}).get("compiled_root_records"),
            "stage12242_candidate_backlog_total_reported": rollup_counts.get("candidate_backlog_total_reported"),
            "stage12242_admitted_external_comparable_repair_roots": rollup_counts.get("admitted_external_comparable_repair_roots"),
            "stage12200_promoted_same_source_episodes": stage12200.get("episode_count"),
            "stage12201_recovered_level_2_patch_contexts": stage12201.get("recovered_level_2_episode_count"),
            "stage12201_recovered_level_3_episodes": stage12201.get("recovered_level_3_episode_count"),
            "stage12202_level3_ready_episodes": stage12202.get("level3_ready_episode_count"),
            "stage12202_verifier_transition_join_count": stage12202.get("verifier_transition_join_count"),
        },
        "main_flaw": (
            "The project has high raw action/session volume, but much of it is either structural/teacher-state supervision "
            "or bounded projection rows. The current 500-root campaign sees only already-surfaced candidates, while many raw "
            "session events are not converted into root-candidate records with repo lineage, patch/action/verifier joins, and "
            "candidate-action sets. The volume is lost before admission, not because the final gates are incorrectly strict."
        ),
        "why_hundreds_of_sessions_do_not_equal_500_roots": [
            {
                "mechanism": "root_identity_is_semantic_lineage_not_row_or_action_count",
                "evidence": "Stage12241/12242 count roots by repo/task/lineage. Variants, projections, action events, and repeated rows do not count as independent roots.",
            },
            {
                "mechanism": "long_context_compiler_roots_are_not_literal_closed_loop_episodes",
                "evidence": "Stage10516 produced 784 compiled roots, but its claim boundary says event streams are structural reconstructions from supervision artifacts, not literal terminal logs.",
            },
            {
                "mechanism": "stage12200_reads_raw_events_but_promotes_zero_same_source_episodes",
                "evidence": f"Stage12200 saw {raw_events} normalized session events, but promoted 0 episodes and blocked 185 candidates.",
            },
            {
                "mechanism": "most_blocked_candidates_lack_core_closed_loop_fields",
                "evidence": "Stage12200 top blockers include repo_commit_before_missing=180, state_before_missing=122, bounded_row_counted_as_full_episode=120, patch_diff_missing=120, verification_intent_missing=120, repo_root_missing=114.",
            },
            {
                "mechanism": "patch_context_recovery_stops_at_level_2_without_verifier_output",
                "evidence": "Stage12201 recovered 29 patch-context episodes, but 0 level-3 episodes because verifier command output and candidate action sets were not recovered.",
            },
            {
                "mechanism": "same_lineage_patch_command_verifier_join_is_missing",
                "evidence": "Stage12202 scanned existing verifier candidates but made only 1 verifier transition join and admitted 0 level-3 episodes; 28/29 lacked same-lineage verifier output.",
            },
            {
                "mechanism": "candidate_backlog_is_not_exhaustive_session_mining",
                "evidence": "Stage12242 reports 195 candidate/backlog roots and 0 admitted external comparable repair roots; it is a scout/intake rollup, not an exhaustive parse of every session/action.",
            },
        ],
        "gates_assessment": {
            "are_gates_too_strict": False,
            "reason": (
                "The hard gates are blocking known false positives: bounded rows counted as episodes, test-added-only patches, "
                "dependency/env failures, cross-source joins, commit metadata without command output, PASS_TO_PASS/current-state "
                "observations counted as repair, and selected-test intent counted as observed action."
            ),
            "what_to_fix_instead": [
                "mine raw session events and recent execution traces directly into root-candidate records",
                "recover same-source patch/action/verifier/state joins",
                "separate level_1 verifier-only, level_2 patch-context, level_3 closed-loop, and level_4 multi-step episodes",
                "run deterministic admission after materialization, not before raw sources are indexed",
            ],
        },
        "source_pools_underused_or_misclassified": [
            {
                "source": "session_like_source_inventory_real/current_raw_parsed_bounded_jsonl_metadata/normalized_session_events.jsonl",
                "known_volume": raw_events,
                "current_issue": "read by stage12200 but not producing direct all-session root candidate mining/admission at scale",
                "next_action": "parse into typed session episodes, then emit root-candidate records with blockers per root",
            },
            {
                "source": "stage10516_long_context_root_state_compiler",
                "known_volume": (stage10516.get("metrics") or {}).get("compiled_root_records"),
                "current_issue": "useful root/state curriculum, but structural reconstruction and Python-heavy; not repair-proof closed-loop data",
                "next_action": "route as auxiliary/root-state curriculum, not admitted repair roots",
            },
            {
                "source": "stage12201 recovered patch contexts",
                "known_volume": stage12201.get("recovered_level_2_episode_count"),
                "current_issue": "same-source diff context exists, but command output/verifier/state transitions are missing",
                "next_action": "join only same-session/same-root verifier outputs or execute authorized replay batch",
            },
            {
                "source": "stage12206 pass/fail verifier observations",
                "known_volume": stage12247.get("current_counters", {}).get("admitted_auxiliary_roots"),
                "current_issue": "verifier observations are useful level_1 support, not patch repair episodes",
                "next_action": "keep as verifier/stop-policy auxiliary unless paired with same-source patch/action/state evidence",
            },
        ],
        "next_stage_sequence": [
            {
                "stage": "stage12249_session_event_root_candidate_miner_request",
                "purpose": "Mine raw normalized session events/recent execution traces directly into root-candidate records with lineage, language, repo, task, patch/action/verifier availability, and blocker codes.",
                "training_allowed": False,
            },
            {
                "stage": "stage12250_same_source_session_trace_parser_request",
                "purpose": "Parse selected session candidates into ordered typed events: file/search/command/patch/test/final, with state_before/state_after placeholders and exact source refs.",
                "training_allowed": False,
            },
            {
                "stage": "stage12251_patch_command_verifier_joiner_request",
                "purpose": "Join only same-source/same-lineage patch diffs, chosen actions, command output, verifier results, and state updates. Reject cross-source fabrication.",
                "training_allowed": False,
            },
            {
                "stage": "stage12252_candidate_action_synthesizer_request",
                "purpose": "For joined traces, synthesize 5-action candidate sets with 3 semantic hard negatives; keep loss disabled until QC passes.",
                "training_allowed": False,
            },
            {
                "stage": "stage12253_root_admission_rollup_v2",
                "purpose": "Report candidate/parsed/joined/executed/QC-passed/admitted counts separately by language, repo, status, and level.",
                "training_allowed": False,
            },
        ],
        "quality_invariants": [
            "Do not count actions, rows, projections, variants, or planned commands as roots.",
            "Do not count PASS_TO_PASS/current-state verifier observations as repair proof.",
            "Do not count level_1 verifier-only rows toward level_3/level_4 closed-loop floors.",
            "Do not join patch evidence from one source with verifier output from another source.",
            "Do not train until level_3+ floor and patch-trace floor pass under Stage12195.",
        ],
        "source_stage_refs": [
            "stage10516_long_context_root_state_compiler",
            "stage12195_unbounded_software_task_completion_spine",
            "stage12198_layered_research_ledgers",
            "stage12200_same_source_patch_trace_episode_miner",
            "stage12201_patch_evidence_recovery",
            "stage12202_level3_readiness_joiner",
            "stage12242_maintainer_500_candidate_intake_rollup",
            "stage12247_plateau_avoidance_graph_aligned_dataset_plan",
        ],
    }

    out_dir = ROOT / "runs" / "local" / "artifacts" / STAGE
    summary_path = ROOT / "runs" / "summaries" / f"{STAGE}.json"
    write_json(out_dir / "root_supply_discrepancy_audit.json", audit)
    write_json(summary_path, audit)

    md = f"""# Stage12248 Root Supply Discrepancy Audit

## Decision

`{audit["decision"]}`

No training is allowed from this artifact.

## Core Finding

We are not short on raw activity. We are short on admitted root-level closed-loop evidence.

- Stage12200 saw `{raw_events}` normalized session events.
- Stage10516 compiled `{audit["headline"]["stage10516_compiled_root_records"]}` structural roots.
- Stage12242 reports `{audit["headline"]["stage12242_candidate_backlog_total_reported"]}` campaign candidate/backlog roots.
- Admitted external comparable repair roots remain `{audit["headline"]["stage12242_admitted_external_comparable_repair_roots"]}`.
- Level-3 ready episodes remain `{audit["headline"]["stage12202_level3_ready_episodes"]}`.

## Why The Volume Collapses

1. Root identity is repo/task/lineage, not row/action/session count.
2. Many historical roots are structural teacher-state reconstructions, not literal tool traces.
3. The same-source patch miner promoted zero full episodes.
4. Patch recovery found level-2 patch context, but not command-output-backed closed-loop transitions.
5. The joiner could not safely connect patch/action/verifier/state under the same lineage.
6. The 195-root campaign rollup is a scout/backlog view, not exhaustive raw session mining.

## Gate Assessment

The gates are not the main flaw. They are blocking false progress:

- bounded rows counted as episodes,
- commit metadata without command output,
- cross-source patch/verifier joins,
- PASS_TO_PASS/current-state observations counted as repair,
- selected-test intent counted as observed action,
- test-added-only or dependency/env failures counted as maintainer repair.

## Next Stages

1. `stage12249_session_event_root_candidate_miner_request`
2. `stage12250_same_source_session_trace_parser_request`
3. `stage12251_patch_command_verifier_joiner_request`
4. `stage12252_candidate_action_synthesizer_request`
5. `stage12253_root_admission_rollup_v2`

The route to 500 high-quality roots is to mine raw session events into root candidates, then join same-source patch/action/verifier/state evidence. Do not weaken Stage12195/12213 gates.
"""
    write_text(out_dir / "ROOT_SUPPLY_DISCREPANCY_AUDIT_STAGE12248.md", md)
    print(summary_path)
    print(out_dir / "ROOT_SUPPLY_DISCREPANCY_AUDIT_STAGE12248.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

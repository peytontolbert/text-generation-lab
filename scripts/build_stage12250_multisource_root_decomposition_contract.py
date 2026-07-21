#!/usr/bin/env python3
"""Build Stage12250 multi-source root decomposition contract.

The contract defines how raw session events, long-context roots, verifier logs,
and commit/diff sources should be decomposed into a common root/task/evidence
ledger before admission. It is intentionally source-agnostic and does not admit
rows or authorize training.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12250_multisource_root_decomposition_contract"
SESSION_EVENTS = ROOT / "runs/local/artifacts/session_like_source_inventory_real/current_raw_parsed_bounded_jsonl_metadata/normalized_session_events.jsonl"


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


def session_event_census() -> dict[str, Any]:
    event_types: Counter[str] = Counter()
    tools: Counter[str] = Counter()
    command_heads: Counter[str] = Counter()
    sessions: Counter[str] = Counter()
    repos: Counter[str] = Counter()
    source_hashes: Counter[str] = Counter()
    n = 0
    if not SESSION_EVENTS.exists():
        return {"missing": str(SESSION_EVENTS)}
    with SESSION_EVENTS.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            n += 1
            event_types[str(row.get("normalized_event_type") or "")] += 1
            tools[str(row.get("tool_name") or "")] += 1
            command_heads[str(row.get("command_head") or "")] += 1
            sessions[str(row.get("session_id_hint") or "")] += 1
            repos[str(row.get("repo_hint") or "")] += 1
            source_hashes[str(row.get("source_file_hash") or "")] += 1
    return {
        "total_events": n,
        "unique_sessions": len(sessions),
        "unique_source_files": len(source_hashes),
        "repo_hints_top": repos.most_common(20),
        "event_types": event_types.most_common(),
        "tools_top": tools.most_common(30),
        "command_heads_top": command_heads.most_common(40),
        "top_sessions": sessions.most_common(20),
    }


def main() -> int:
    stage10516 = load_json("runs/summaries/stage10516_long_context_root_state_compiler.json")
    stage12248 = load_json("runs/summaries/stage12248_root_supply_discrepancy_audit.json")
    census = session_event_census()
    compiled_metrics = stage10516.get("metrics") or {}

    contract = {
        "stage": STAGE,
        "artifact_type": "multisource_root_decomposition_contract",
        "decision": "build_source_normalization_layer_before_more_scale_claims",
        "training_allowed": False,
        "claim_boundary": (
            "Contract/control artifact only. Defines source decomposition and admission levels. "
            "It does not admit roots, create training rows, or authorize model training."
        ),
        "motivation": {
            "problem": "Raw session/action volume and long-context roots are not flowing into admitted maintainer roots at the needed scale.",
            "specific_failure": stage12248.get("decision"),
            "target": "Scale toward 500 high-quality root records first, then per-language 1000-root campaigns, without collapsing source quality or admission semantics.",
        },
        "observed_source_census": {
            "session_events": census,
            "stage10516_compiled_long_context_roots": compiled_metrics.get("compiled_root_records"),
            "stage10516_compiled_multitarget_rows": compiled_metrics.get("compiled_multitarget_rows"),
            "stage10516_language_counts": compiled_metrics.get("language_counts"),
        },
        "key_interpretation": [
            "The 345k normalized session events are evidence/action records, not 345k roots.",
            "The normalized session event file currently has only 9 session IDs and is heavily dominated by one agentkernel session.",
            "The long-context compiler has 784 useful compiled roots, but they are structural/teacher-state roots, not literal closed-loop repair episodes.",
            "The correct unit is a normalized source root with attached evidence, task, verifier, events, split lineage, and admission level.",
            "Every source must emit the same root/task/evidence schema before any training manifest is built.",
        ],
        "canonical_decomposition_schema": {
            "source_record": [
                "source_record_id",
                "source_family",
                "source_path",
                "source_hash",
                "source_timestamp",
                "extractor_version",
            ],
            "root_record": [
                "root_id",
                "root_lineage_key",
                "repo_id",
                "repo_family",
                "language_family",
                "task_family",
                "snapshot_before",
                "snapshot_after",
                "environment_id",
                "source_family_id",
                "split_component_candidate",
                "admission_level_candidate",
            ],
            "task_record": [
                "task_id",
                "root_id",
                "task_prompt_or_objective",
                "success_criteria",
                "selected_verifier_identity",
                "verifier_evidence_type",
                "expected_status_family",
            ],
            "event_record": [
                "event_id",
                "root_id",
                "episode_id",
                "order_index",
                "event_type",
                "actor",
                "tool_name",
                "command",
                "cwd",
                "file_refs",
                "content_ref",
                "output_ref",
                "exit_status",
            ],
            "evidence_record": [
                "evidence_id",
                "root_id",
                "evidence_type",
                "artifact_path",
                "content_digest",
                "visible_before_action",
                "role",
                "lineage_safe",
            ],
            "transition_record": [
                "transition_id",
                "root_id",
                "state_before_ref",
                "candidate_action_set_ref",
                "chosen_action_ref",
                "observation_ref",
                "patch_trace_ref_or_no_patch_reason",
                "verifier_result_ref",
                "state_after_ref",
                "stop_continue_label",
            ],
            "admission_record": [
                "root_id",
                "admission_level",
                "allowed_training_lanes",
                "blocked_reason_codes",
                "strict_eval_eligible",
                "train_support_eligible",
                "quality_score",
                "anti_cheat_status",
            ],
        },
        "source_routing": [
            {
                "source_family": "normalized_codex_session_events",
                "input": str(SESSION_EVENTS.relative_to(ROOT)),
                "primary_use": "event/evidence index and candidate root discovery",
                "not_sufficient_for": "level_3 closed-loop unless raw command output/patch/verifier records are joined from same source",
                "next_extractor": "stage12251_session_event_root_candidate_miner",
            },
            {
                "source_family": "raw_codex_session_files",
                "input": "session_like_source_inventory_real raw session files",
                "primary_use": "recover full command output, patch bodies, apply_patch events, final responses, and state updates",
                "not_sufficient_for": "admission without root/task/verifier identity",
                "next_extractor": "stage12252_same_source_session_trace_parser",
            },
            {
                "source_family": "long_context_compiled_roots_stage10516",
                "input": "stage10516 compiled_root_records / compiled_typed_events / compiled_multitarget_rows",
                "primary_use": "level_0/auxiliary root-state curriculum and retrieval/evidence projections",
                "not_sufficient_for": "repair-proof or source-heldout closed-loop claims",
                "next_extractor": "stage12254_long_context_root_to_auxiliary_ledger_converter",
            },
            {
                "source_family": "external_commit_pair_sources",
                "input": "external_repo_commit_family_v2 and scale_v2 commit pools",
                "primary_use": "source-bearing diff candidates and potential FAIL_TO_PASS repair roots",
                "not_sufficient_for": "admission without before-fail/apply/after-pass command output",
                "next_extractor": "stage12249_replay_preflight_execution_request",
            },
            {
                "source_family": "verifier_observation_logs",
                "input": "stage11579/stage11580/stage12123/stage12144/stage12145/stage12206/stage12209 style logs",
                "primary_use": "level_1 verifier interpretation and stop-policy support",
                "not_sufficient_for": "patch repair proof unless joined same-lineage with a patch/action tuple",
                "next_extractor": "stage12255_verifier_observation_to_level1_ledger_converter",
            },
        ],
        "admission_ladder": {
            "level_0_context_or_state": "Root/task/evidence context without executed verifier or patch. Useful for retrieval/state compression.",
            "level_1_verifier_observation": "Command/verifier output with no patch trace. Useful for verifier interpretation and stop/continue.",
            "level_2_patch_context": "Real source diff/patch context with verifier intent but no command output. Useful for patch candidate mining only.",
            "level_3_single_step_closed_loop": "state_before, chosen action, observation, patch or no-patch reason, verifier result, state_after, stop/continue.",
            "level_4_multi_step_maintainer_episode": "Two or more linked level_3 transitions under one task/root with terminal decision.",
            "external_comparable_repair": "before-fail, apply source patch, after-pass under same verifier identity and same root lineage.",
        },
        "scale_targets_without_quality_loss": {
            "first_campaign": {
                "candidate_roots": 500,
                "level_3_plus_floor": 20,
                "patch_trace_floor": 8,
                "external_comparable_repair_floor": 25,
                "languages_min": 3,
                "repo_families_min": 10,
            },
            "per_language_campaign": {
                "python_roots": 1000,
                "rust_roots": 1000,
                "c_cpp_roots": 1000,
                "web_js_ts_html_roots": 1000,
                "note": "Counts must be admitted root records by level, not event rows or projections.",
            },
        },
        "hard_anti_plateau_rules": [
            "Every extractor reports event_count, candidate_root_count, parsed_root_count, joined_root_count, qc_passed_root_count, and admitted_root_count separately.",
            "Every training package reports source-family mix and admission-level mix before training.",
            "No source family may silently dominate a campaign; cap dominant repo/session families or mark train-only.",
            "Long-context roots and session roots may share schema, but their admission levels must stay separate.",
            "A raw event without command output is an index entry, not a verifier observation.",
            "A verifier observation without patch/action state is not a closed-loop episode.",
            "A patch without before/after verifier evidence is not a comparable repair root.",
        ],
        "next_stage_sequence": [
            {
                "stage": "stage12251_session_event_root_candidate_miner",
                "purpose": "Group normalized session events by session, repo, file refs, commands, patches, and likely task boundaries; emit root candidates with blockers.",
                "training_allowed": False,
            },
            {
                "stage": "stage12252_raw_session_trace_rehydrator",
                "purpose": "Open raw session files for selected candidates and recover full command output, apply_patch bodies, and final state evidence.",
                "training_allowed": False,
            },
            {
                "stage": "stage12253_multisource_root_ledger_builder",
                "purpose": "Merge normalized session, long-context, verifier-observation, and commit-pair candidates into one ledger with source-family and admission-level tags.",
                "training_allowed": False,
            },
            {
                "stage": "stage12254_root_admission_rollup_v3",
                "purpose": "Report campaign progress by root level and source family; block training until level-specific floors pass.",
                "training_allowed": False,
            },
        ],
    }

    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", contract)
    write_json(out_dir / "multisource_root_decomposition_contract.json", contract)

    md = f"""# Stage12250 Multi-Source Root Decomposition Contract

## Decision

`{contract["decision"]}`

No rows are admitted and no training is allowed.

## What This Fixes

`345k` session events becoming `~200` candidate roots is not acceptable for the campaign, but the fix is not to count events as roots. The fix is to break every source into the same artifact ledger:

`source_record -> root_record -> task_record -> event_record -> evidence_record -> transition_record -> admission_record`

## Current Census

- normalized session events: `{census.get("total_events")}`
- unique normalized sessions: `{census.get("unique_sessions")}`
- unique normalized source files: `{census.get("unique_source_files")}`
- Stage10516 compiled long-context roots: `{compiled_metrics.get("compiled_root_records")}`
- Stage10516 language counts: `{compiled_metrics.get("language_counts")}`

## Key Rule

Events, rows, projections, logs, and variants are not root scale. Root scale is admitted root records with source family, lineage, evidence, verifier status, and admission level.

## Next Stages

1. `stage12251_session_event_root_candidate_miner`
2. `stage12252_raw_session_trace_rehydrator`
3. `stage12253_multisource_root_ledger_builder`
4. `stage12254_root_admission_rollup_v3`
"""
    write_text(out_dir / "MULTISOURCE_ROOT_DECOMPOSITION_CONTRACT_STAGE12250.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "MULTISOURCE_ROOT_DECOMPOSITION_CONTRACT_STAGE12250.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12304_canonical_root_mining_spine_alignment"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

LEDGER_SUMMARY = ROOT / "runs/local/artifacts/stage12198_layered_research_ledgers/layered_research_ledgers_summary.json"
DATASET_LEDGER = ROOT / "runs/local/artifacts/stage12198_layered_research_ledgers/dataset_source_ledger.jsonl"
S12237 = ROOT / "runs/summaries/stage12237_current_training_control_board.json"
S12248 = ROOT / "runs/summaries/stage12248_root_supply_discrepancy_audit.json"
S12295 = ROOT / "runs/summaries/stage12295_transition_function_ledger.json"
S12300 = ROOT / "runs/summaries/stage12300_root_repaired_horizon_projection_candidates.json"
S12302 = ROOT / "runs/summaries/stage12302_transition_function_graph_control_board.json"
S12303 = ROOT / "runs/summaries/stage12303_semantic_transition_function_reconstruction.json"


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Path, rows: list[dict]) -> int:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)


def dataset_ledger_profile() -> dict:
    rows = list(iter_jsonl(DATASET_LEDGER) or [])
    status_counts = Counter(r.get("status") or "unknown" for r in rows)
    train_authority_counts = Counter(r.get("train_authority") or "unknown" for r in rows)
    late_stage_candidates = [
        r
        for r in rows
        if (r.get("stage") or 0) >= 11900
        and any(
            token in (r.get("stage_name") or "")
            for token in ["transition", "root", "episode", "source", "verifier", "patch", "session"]
        )
    ]
    return {
        "record_count": len(rows),
        "status_counts_top": dict(status_counts.most_common(12)),
        "train_authority_counts_top": dict(train_authority_counts.most_common(12)),
        "late_stage_transition_source_records": len(late_stage_candidates),
        "late_stage_transition_source_examples": [
            {
                "stage": r.get("stage"),
                "stage_name": r.get("stage_name"),
                "status": r.get("status"),
                "train_authority": r.get("train_authority"),
                "artifact_paths": (r.get("artifact_paths") or [])[:3],
            }
            for r in late_stage_candidates[:20]
        ],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ledger_summary = read_json(LEDGER_SUMMARY)
    s12237 = read_json(S12237)
    s12248 = read_json(S12248)
    s12295 = read_json(S12295)
    s12300 = read_json(S12300)
    s12302 = read_json(S12302)
    s12303 = read_json(S12303)
    dataset_profile = dataset_ledger_profile()

    source_pools = [
        {
            "pool_id": "codex_horizon_transition_graph",
            "primary_artifacts": [
                "runs/local/artifacts/stage12295_transition_function_ledger/transition_function_ledger.jsonl",
                "runs/local/artifacts/stage12300_root_repaired_horizon_projection_candidates/root_repaired_horizon_projection_candidates.jsonl",
                "runs/local/artifacts/stage12303_semantic_transition_function_reconstruction/semantic_transition_reconstruction_work_items.jsonl",
            ],
            "current_volume": {
                "stage12295_ledger_records": s12295.get("ledger_records"),
                "stage12300_root_repaired_candidates": s12300.get("projection_candidates"),
                "stage12303_reconstruction_work_items": s12303.get("reconstruction_work_items"),
            },
            "current_language_mix": s12303.get("work_item_language_counts", {}),
            "admission_level_today": "level_1_to_level_2_auxiliary_transition_projection",
            "canonical_root_potential": "medium",
            "expansion_value": "High-volume short-horizon transition functions after semantic state/rule assignment.",
            "blockers": [
                "raw observed action labels must be replaced with maintainer semantic labels",
                "candidate role markers must not enter model-visible fields",
                "state_update labels require semantic review",
                "non-Python/non-Web roots are currently missing in the admitted reconstruction set",
            ],
            "next_action": "stage12304/12305 semantic rule assignment, then root-balanced train-support package only if floors pass",
        },
        {
            "pool_id": "session_like_source_inventory_real",
            "primary_artifacts": [
                "runs/local/artifacts/stage12256_live_physical_session_inventory_refresh/live_physical_source_records.jsonl",
                "runs/local/artifacts/stage12260_codex_chat_task_boundary_miner",
            ],
            "current_volume": {
                "physical_session_like_files": 1739,
                "normalized_session_events_reported": 345487,
                "patch_verifier_ref_windows_reported": 2059,
            },
            "admission_level_today": "candidate_source_only_until_episode_graph_join",
            "canonical_root_potential": "high",
            "expansion_value": "Best route to Level-3/Level-4 roots if same-source patch/action/verifier/state joins are recovered.",
            "blockers": [
                "task windows are not episode graphs",
                "source_root_label and de-overlap must be enforced",
                "patch/verifier co-presence is not causality",
                "session dominance caps required",
            ],
            "next_action": "profile capped windows, materialize episode_graph_candidate records, then quality-gate Level-3 tuples",
        },
        {
            "pool_id": "transition_root_250_and_transition_support_rollups",
            "primary_artifacts": [
                "runs/local/artifacts/stage11975_transition_root_250_probe_expansion/transition_root_250_probe_expansion_review_rows.jsonl",
                "runs/local/artifacts/stage12056_transition_support_rollup_v35/transition_support_rows_v35.jsonl",
            ],
            "admission_level_today": "auxiliary_transition_support_or_diagnostic",
            "canonical_root_potential": "medium",
            "expansion_value": "Useful for task-family balance and replay, but must be re-rooted and anti-cheat checked before canonical claims.",
            "blockers": [
                "older support rows may not have ordered events/state updates",
                "some rows are projections rather than same-source episodes",
                "must avoid reusing protected/heldout roots",
            ],
            "next_action": "mine only root-disjoint rows with candidate sets and verifier/status fields, then route as auxiliary unless Level-3 tuple exists",
        },
        {
            "pool_id": "long_context_compiled_sources",
            "primary_artifacts": [
                "runs/local/artifacts/strict_long_context_train_ready_plus_audit_v1",
                "runs/local/artifacts/stage10516_long_context_root_state_compiler",
                "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout",
            ],
            "admission_level_today": "level_0_to_level_1_context_or_retrieval_support",
            "canonical_root_potential": "medium",
            "expansion_value": "Good for root/task/state scaffolding and evidence ledgers, not enough alone for closed-loop maintainer episodes.",
            "blockers": [
                "must recover ordered actions/observations/verifier outputs",
                "heldout/source split must be root-level",
                "avoid opaque handle reconstruction and target leaks",
            ],
            "next_action": "join with verifier/action logs before claiming Level-3; otherwise use for context/evidence projections only",
        },
        {
            "pool_id": "external_commit_patch_corpora",
            "primary_artifacts": [
                "external_repo_commit_family_v2",
                "stage12244_commit_pair_replay_queue",
                "stage12290_to_stage12293_patch_effect_replay_exhaustion",
            ],
            "admission_level_today": "level_2_patch_context_candidate",
            "canonical_root_potential": "high_if_verifier_logs_exist",
            "expansion_value": "Best path to comparable FAIL_TO_PASS repair roots, but current replay queue found zero PE2 rows.",
            "blockers": [
                "current smoke queue exhausted with before_did_not_fail cases",
                "needs real before-fail/after-pass verifier proof",
                "non-Python supply still weak",
            ],
            "next_action": "retarget to sources with authoritative verifier logs or executable local tests, not broad commit pairs",
        },
    ]

    canonical_schema = {
        "root": [
            "canonical_root_id",
            "repo_family",
            "language_family",
            "source_root_label",
            "root_lineage_key",
            "split_group_id",
            "source_pool_id",
            "admission_level",
        ],
        "episode": [
            "episode_id",
            "task_window_id",
            "ordered_events_ref",
            "task_intent_ref",
            "horizon_level",
            "same_source_join_proof",
        ],
        "transition": [
            "transition_id",
            "state_before_ref",
            "candidate_action_set",
            "chosen_action_target_only",
            "observation_target_only",
            "verifier_result_target_only",
            "state_after_or_update_target_only",
            "stop_continue_target_only",
            "semantic_rule_id",
            "transition_function_key",
        ],
        "claim_gates": [
            "train_support_allowed",
            "strict_eval_eligible",
            "source_heldout_admissible",
            "external_comparable_patch_trace_countable",
            "external_fail_to_pass_countable",
            "level_3_countable",
            "level_4_countable",
        ],
    }

    summary = {
        "stage": STAGE,
        "decision": "canonical_root_mining_spine_aligned_training_still_blocked",
        "claim_boundary": "This stage aligns source pools to the central unbounded spine. It admits no rows and emits no training request.",
        "training_allowed": False,
        "central_spine_facts": {
            "valid_unit": "root+task -> ordered_events -> state_before -> candidate_actions -> chosen_action -> observation -> verifier_result -> state_after -> stop_continue",
            "level_3_floor_from_spine": {
                "level_3_plus_episodes": 20,
                "patch_trace_episodes": 8,
                "repositories": 10,
                "languages": 3,
            },
            "current_level_3_plus_episode_supply": 0,
            "current_patch_trace_episode_supply": 0,
        },
        "ledger_profile": {
            "stage12198_record_counts": ledger_summary.get("record_counts", {}),
            "dataset_source_ledger": dataset_profile,
        },
        "current_blockers": {
            "stage12237_decision": s12237.get("decision"),
            "stage12248_decision": s12248.get("decision"),
            "stage12302_decision": s12302.get("decision"),
            "stage12303_decision": s12303.get("decision"),
        },
        "source_pools": source_pools,
        "canonical_schema": canonical_schema,
        "next_subagent_work_orders": [
            {
                "name": "source_pool_materializer",
                "task": "For each source pool, emit 25 canonical_root_candidate records with level labels and missing fields, not training rows.",
            },
            {
                "name": "semantic_rule_assigner",
                "task": "Assign deterministic semantic_rule_id and state code only when pre-action state supports it; otherwise block.",
            },
            {
                "name": "language_gap_miner",
                "task": "Find Rust and C/C++ canonical roots with ordered events and verifier outputs; do not reuse protected heldout roots.",
            },
            {
                "name": "episode_graph_join_auditor",
                "task": "Check same-source ordering and causality for patch/action/verifier/state joins; reject co-presence.",
            },
        ],
        "next_stage": "stage12305_canonical_root_candidate_materialization_queue",
    }

    write_jsonl(OUT / "canonical_root_source_pools.jsonl", source_pools)
    (OUT / "canonical_root_schema.json").write_text(json.dumps(canonical_schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "canonical_root_mining_spine_alignment.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "CANONICAL_ROOT_MINING_SPINE_ALIGNMENT_STAGE12304.md").write_text(
        "# Stage12304 Canonical Root Mining Spine Alignment\n\n"
        "No training rows are admitted. This stage routes source pools into canonical root/episode/transition levels.\n\n"
        "## Decision\n\n"
        f"`{summary['decision']}`\n\n"
        "## Source Pools\n\n"
        + "\n".join(f"- `{pool['pool_id']}`: {pool['admission_level_today']} ({pool['canonical_root_potential']} potential)" for pool in source_pools)
        + "\n\n## Next Stage\n\n"
        "`stage12305_canonical_root_candidate_materialization_queue`\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

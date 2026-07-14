#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'runs' / 'local' / 'artifacts'

STAGE = 10758
NAME = 'stage10758_python_residual_packet_promotability_audit'
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / 'python_residual_packet_promotability_audit.json'
QUEUE_JSONL = OUT_DIR / 'python_residual_packet_promotability_queue.jsonl'
PROMOTION_MAP_JSONL = OUT_DIR / 'python_packet_promotion_map.jsonl'
RUN_SUMMARY = ROOT / 'runs' / 'summaries' / f'{NAME}.json'

BACKLOG_JSONL = ARTIFACTS / 'stage10757_residual_packet_materialization_backlog' / 'materialization_backlog.jsonl'
HF_REPAIRED_PACKET = ARTIFACTS / 'stage10499_hf_local_multitest_packet_repair' / 'hf_local_multitest_repaired_packet.json'
HF_REPAIRED_AUDIT = ARTIFACTS / 'stage10500_hf_local_multitest_repair_audit' / 'hf_local_multitest_repair_audit.json'
AGENTKERNEL_MANIFEST = ARTIFACTS / 'stage10687_reviewed_v27_plus_two_fresh_rust_support_package' / 'reviewed_v27_plus_two_fresh_rust_root_manifest.jsonl'

HF_TARGET_BUNDLE = 'stage10300::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_26t23_27_57_019bfca2_aa35_7502_b929_649a_src_code_assist_agents_hf_local_py_src_code_assist_agents_hf_local_planner_py_sr_3fb1ce61a2_aug_1500000_8b46e7f662::python'
AGENTKERNEL_TARGET_BUNDLE = 'stage10110::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14_24_54_019d39fb_c43d_7e62_b055_b00b_agent_kernel_cycle_runner_py_agent_kernel_improvement_py_agent_kernel_learning_c_6a4dce0d0c_aug_1500000_8b46e7f662::python_successor'


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + '\n')


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    backlog = load_jsonl(BACKLOG_JSONL)
    hf_packet = load_json(HF_REPAIRED_PACKET)
    hf_audit = load_json(HF_REPAIRED_AUDIT)
    agentkernel_manifest = load_jsonl(AGENTKERNEL_MANIFEST)

    backlog_by_bundle = {str(row['bundle_id']): row for row in backlog}
    hf_row = dict(backlog_by_bundle[HF_TARGET_BUNDLE])
    agentkernel_row = dict(backlog_by_bundle[AGENTKERNEL_TARGET_BUNDLE])

    agentkernel_manifest_row = next(
        row for row in agentkernel_manifest
        if str(row.get('root_id')) == 'stage10110::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14_24_54_019d39fb_c43d_7e62_b055_b00b_agent_kernel_cycle_runner_py_agent_kernel_improvement_py_agent_kernel_learning_c_6a4dce0d0c_aug_1500000_8b46e7f662::python_implementation_vs_implementation'
    )

    queue_rows: list[dict[str, Any]] = []
    promotion_rows: list[dict[str, Any]] = []

    queue_rows.append(
        {
            'language_family': 'python',
            'bundle_id': HF_TARGET_BUNDLE,
            'repo_id': 'code_assist',
            'current_lane_state': hf_row['readiness'],
            'decision': 'promotable_via_existing_repaired_packet',
            'repaired_packet_bundle_id': str(hf_packet['bundle']['bundle_id']),
            'repaired_packet_path': rel(HF_REPAIRED_PACKET),
            'repaired_packet_audit': rel(HF_REPAIRED_AUDIT),
            'candidate_count': int(len(hf_packet['bundle']['candidate_id_map'])),
            'verifier_count': int(len(hf_packet['bundle']['verifier_id_map'])),
            'preview_rows_count': int(hf_packet['bundle']['preview_rows_count']),
            'opaque_candidate_options': bool(hf_audit['anti_cheat_checks']['candidate_options_opaque']),
            'opaque_verifier_options': bool(hf_audit['anti_cheat_checks']['verifier_options_opaque']),
            'prompt_target_leak_false': bool(hf_audit['anti_cheat_checks']['prompt_target_leak_false']),
            'remaining_limit': list(hf_packet.get('known_limits') or []),
            'next_action': 'rebase stage10756 hf_local deferred lane onto the repaired packet lineage for future bounded execution materialization',
            'promotion_boundary': 'train_support_upgrade_ready; not strict-eval promotable by itself',
        }
    )

    queue_rows.append(
        {
            'language_family': 'python',
            'bundle_id': AGENTKERNEL_TARGET_BUNDLE,
            'repo_id': 'agentkernel',
            'current_lane_state': agentkernel_row['readiness'],
            'decision': 'not_promotable_compressed_successor_only',
            'manifest_record_type': str(agentkernel_manifest_row['record_type']),
            'selected_tests_count': int(agentkernel_manifest_row['selected_tests_count']),
            'visible_evidence_key_count': int(agentkernel_manifest_row['visible_evidence_key_count']),
            'successor_row_source': bool(agentkernel_manifest_row['successor_row_source']),
            'packet_dir_present': bool(agentkernel_row['packet_dir']),
            'materialized_candidate_count': int(agentkernel_row['candidate_path_count']),
            'materialized_verifier_anchor_count': int(agentkernel_row['selected_test_or_anchor_count']),
            'blocking_reason': 'existing lineage still bottoms out in compressed successor-row evidence rather than a reviewed repaired packet with explicit anti-cheat-clean verifier geometry',
            'next_action': 'keep agentkernel on geometry/materialization work until a repaired non-compressed packet exists',
            'promotion_boundary': 'quarantine_from_probe_requests',
        }
    )

    promotion_rows.append(
        {
            'source_bundle_id': HF_TARGET_BUNDLE,
            'replacement_packet_bundle_id': str(hf_packet['bundle']['bundle_id']),
            'replacement_packet_path': rel(HF_REPAIRED_PACKET),
            'replacement_packet_audit': rel(HF_REPAIRED_AUDIT),
            'eligible_for_train_support_refresh': True,
            'eligible_for_strict_eval_claim': False,
            'claim_note': 'Use as a richer anti-cheat-clean verifier support lane only; do not convert this directly into a heldout improvement claim.',
        }
    )
    promotion_rows.append(
        {
            'source_bundle_id': AGENTKERNEL_TARGET_BUNDLE,
            'replacement_packet_bundle_id': None,
            'replacement_packet_path': None,
            'replacement_packet_audit': None,
            'eligible_for_train_support_refresh': False,
            'eligible_for_strict_eval_claim': False,
            'claim_note': 'No repaired packet lineage found. Keep out of probe requests until explicit evidence geometry is rebuilt.',
        }
    )

    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'decision': 'python_residual_promotability_audited',
        'claim_scope': [
            'Audit whether the two deferred Python residual packets are truly blocked on missing materialization, or whether existing repaired packet lineages already make one lane usable.',
            'Distinguish recoverable hf_local packet supply from agentkernel compressed-successor supply so future probe requests stop treating both as equivalent.',
            'This is a support-lane promotability artifact, not a new model score claim.',
        ],
        'headline_findings': [
            'The deferred hf_local lane is already recoverable through the stage10499 repaired packet plus stage10500 anti-cheat audit.',
            'The deferred agentkernel lane is still not promotable because its current local lineage remains compressed successor-row evidence rather than a repaired packet with explicit visible evidence roles.',
            'Python residual supply should therefore split into one support-refresh-ready lane and one quarantined geometry-rebuild lane.',
        ],
        'queue_counts': {
            'python_lanes_audited': 2,
            'promotable_via_existing_packet': 1,
            'still_blocked_compressed_only': 1,
        },
        'source_artifacts': {
            'backlog': rel(BACKLOG_JSONL),
            'hf_repaired_packet': rel(HF_REPAIRED_PACKET),
            'hf_repaired_audit': rel(HF_REPAIRED_AUDIT),
            'agentkernel_manifest': rel(AGENTKERNEL_MANIFEST),
        },
        'next_best_step': 'Refresh the next multilingual support package by swapping the deferred hf_local scaffold lane for the repaired packet lineage, while leaving agentkernel quarantined until a non-compressed repaired packet exists.',
        'outputs': {
            'summary': rel(SUMMARY_JSON),
            'queue': rel(QUEUE_JSONL),
            'promotion_map': rel(PROMOTION_MAP_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(QUEUE_JSONL, queue_rows)
    write_jsonl(PROMOTION_MAP_JSONL, promotion_rows)
    write_json(
        RUN_SUMMARY,
        {
            'stage': STAGE,
            'passed': True,
            'decision': summary['decision'],
            'summary': rel(SUMMARY_JSON),
            'queue': rel(QUEUE_JSONL),
        },
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
